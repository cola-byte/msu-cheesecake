"""Read-only MSU menu feasibility probe; no scheduler or notification delivery."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from filter_menus import filter_records, write_review

BASE = "https://msu.api.nutrislice.com"


def get_json(url, path, refresh=False, offline=False):
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    if offline:
        raise FileNotFoundError(f"Offline mode: missing cached source {path}")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "MSU-Menu-Feasibility-Probe/0.1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8-sig")
            result = json.loads(payload)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            time.sleep(0.3)
            return result
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            delay = error.headers.get("Retry-After", "")
            # Stop instead of ignoring an unusually long server backoff.
            if delay.isdigit() and int(delay) > 30:
                raise
            time.sleep(int(delay) if delay.isdigit() else 2 ** (attempt + 1))


def inspect_week(school, meal, anchor, start, end, cache, refresh, offline=False):
    template = meal["urls"]["full_menu_by_date_api_url_template"]
    url = BASE + template.format(year=anchor.year, month=anchor.month, day=anchor.day) + "/"
    key = f"{school['slug']}__{meal['slug']}__{anchor.isoformat()}.json"
    result = {"location": school["name"], "meal": meal["name"], "source_url": url, "days": [], "items": []}
    try:
        data = get_json(url, cache / key, refresh, offline)
        if not isinstance(data.get("days"), list):
            raise ValueError("Unexpected response: days is missing or not a list")
        result["last_updated"] = data.get("last_updated")
        for day in data["days"]:
            current = date.fromisoformat(day["date"])
            if not start <= current <= end:
                continue
            items = day["menu_items"]
            result["days"].append({
                "date": day["date"],
                "food_count": sum(bool(item.get("food")) for item in items),
                "has_unpublished_menus": day.get("has_unpublished_menus"),
            })
            sections = {}
            for item in items:
                if item.get("is_section_title"):
                    sections[(item.get("menu_id"), item.get("station_id"))] = item.get("text", "")
            for item in items:
                food = item.get("food") or {}
                name = food.get("name", "")
                if not food:
                    continue
                info = day.get("menu_info", {}).get(str(item.get("menu_id")), {})
                result["items"].append({
                    "date": day["date"], "location": school["name"], "location_slug": school["slug"],
                    "meal": meal["name"], "meal_slug": meal["slug"], "name": name,
                    "description": food.get("description"), "subtext": food.get("subtext"),
                    "ingredients": food.get("ingredients"), "food_category": food.get("food_category"),
                    "section": sections.get((item.get("menu_id"), item.get("station_id"))),
                    "station": info.get("section_options", {}).get("display_name"),
                    "food_id": food.get("id"), "menu_item_id": item.get("id"),
                    "menu_url": f"https://msu.nutrislice.com/menu/{school['slug']}/{meal['slug']}/{day['date']}",
                    "source_url": url,
                    "source_file": str(cache / key), "source_last_updated": data.get("last_updated"),
                })
        result["status"] = "ok"
    except Exception as error:
        result.update(status="error", error=f"{type(error).__name__}: {error}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, help="First MSU-local date; defaults to Monday of the current MSU week")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--locations", nargs="*", help="Optional exact restaurant slugs; otherwise all published locations")
    parser.add_argument("--refresh", action="store_true", help="Download again instead of reusing saved evidence")
    parser.add_argument("--offline", action="store_true", help="Use only saved source responses; never contact the website")
    parser.add_argument("--output", type=Path, default=Path("probe-output"))
    args = parser.parse_args()
    if args.offline and args.refresh:
        parser.error("--offline and --refresh cannot be combined")
    if not 1 <= args.days <= 14:
        parser.error("--days must be between 1 and 14")
    if args.start is None:
        try:
            today = datetime.now(ZoneInfo("America/Detroit")).date()
        except ZoneInfoNotFoundError:
            parser.error("Timezone data unavailable. Use --start YYYY-MM-DD or install tzdata: python -m pip install tzdata")
        args.start = today - timedelta(days=today.weekday())
    start, end = args.start, args.start + timedelta(days=args.days - 1)
    out = args.output
    cache = out / "raw"
    schools = get_json(BASE + "/menu/api/schools/", cache / "schools.json", args.refresh, args.offline)
    if not isinstance(schools, list) or not schools:
        raise ValueError("Unexpected location list schema")
    if args.locations:
        unknown = set(args.locations) - {s["slug"] for s in schools}
        if unknown:
            parser.error(f"Unknown locations: {sorted(unknown)}")
        schools = [s for s in schools if s["slug"] in args.locations]
    # Nutrislice returns Sunday-Saturday weeks. Cover both API weeks when needed.
    anchors = sorted({start + timedelta(days=i) - timedelta(days=(start + timedelta(days=i)).isoweekday() % 7) for i in range(args.days)})
    jobs = [(s, m, a) for s in schools for m in s["active_menu_types"] for a in anchors]
    if not jobs:
        parser.error("No active menu sources were returned; cannot verify the menus")
    results = []
    print(f"Inspecting {len(schools)} locations, {len(jobs)} weekly menu sources, {start} to {end}; offline={args.offline}", flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(inspect_week, s, m, a, start, end, cache, args.refresh, args.offline) for s, m, a in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if len(results) % 10 == 0 or result["status"] == "error":
                print(f"{len(results)}/{len(jobs)} {result['location']} {result['meal']}: {result['status']}", flush=True)
    # Preserve all food rows, including repeated offerings and non-matches.
    # Notification deduplication belongs downstream, not in source collection.
    all_items = sorted((item for r in results for item in r.pop("items")), key=lambda m: (m["date"], m["location"], m["meal"], m["name"]))
    out.mkdir(parents=True, exist_ok=True)
    (out / "all_menu_items.json").write_text(json.dumps({"start": str(start), "end": str(end), "data_mode": "saved_sources" if args.offline else "refresh" if args.refresh else "cache_or_download", "items": all_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    classified = filter_records(all_items)
    counts = write_review(classified, out)
    matches = [r for r in classified if r["kind"] != "not_selected"]
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "date_basis": "MSU local calendar dates (US/Eastern); Monday-Sunday if --start is Monday",
        "start": str(start), "end": str(end), "locations": [{"name": s["name"], "slug": s["slug"]} for s in schools],
        "requests": len(jobs), "errors": sum(r["status"] == "error" for r in results),
        "filter_counts": counts, "all_food_rows": len(all_items),
        "data_mode": "saved_sources" if args.offline else "refresh" if args.refresh else "cache_or_download",
        "matches": matches, "coverage": results,
        "limitations": ["Menu listings are planned offerings, not real-time stock.", "Empty or unpublished menus are not evidence of no cheesecake.", "Name matching is a candidate filter; verify against the rendered menu before enabling notifications."],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# MSU menu probe: {start} to {end}", "", f"Locations: {len(schools)}; weekly API sources: {len(jobs)}; errors: {report['errors']}", "", "Dates use US/Eastern. Listings describe planned menus, not remaining stock.", "", f"All food rows retained: {len(all_items)}. Classification counts: {counts}.", "", "Broad review candidates are saved in review_candidates.json. The table below shows explicit cheesecake names, including related desserts; no class is a guarantee of availability.", "", "| Date | Location | Meal | Item | Station | Classification |", "|---|---|---|---|---|---|"]
    for m in (r for r in matches if r["kind"] != "broad_review"):
        lines.append(f"| {m['date']} | [{m['location']}]({m['menu_url']}) | {m['meal']} | {m['name']} | {m['station'] or ''} | {m['kind']} |")
    lines += ["", "Empty/unpublished days and request failures remain unknown. See results.json and raw/ for evidence.", ""]
    (out / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"weekly_sources": len(jobs), "errors": report["errors"], "all_food_rows": len(all_items), "filter_counts": counts}, ensure_ascii=False, indent=2), flush=True)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
