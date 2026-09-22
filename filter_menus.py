"""Reclassify saved full menus offline; broad matches are review candidates only."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata

PATTERN = re.compile(r"cheese[\s-]*cakes?|起司蛋糕|乳酪蛋糕|芝士蛋糕", re.I)
RELATED = re.compile(r"ice\s*cream|frozen\s*yogurt|milkshake|smoothie|cookie|muffin|pancake|waffle|冰淇淋", re.I)
BROAD = re.compile(r"cheese|cake|dessert|mascarpone|ricotta|gateau|gâteau|torte|\btart\b|\bpie\b|mousse|pudding|custard|起司|乳酪|芝士|蛋糕|甜點", re.I)
FIELDS = ("name", "description", "subtext", "ingredients", "food_category", "station", "section")
ORDER = {"cheesecake_candidate": 0, "related_dessert_review": 1, "broad_review": 2, "not_selected": 3}


def classify(record):
    evidence = []
    for field in FIELDS:
        text = unicodedata.normalize("NFKC", record.get(field) or "")
        terms = sorted({m.group().lower() for m in BROAD.finditer(text)})
        if terms:
            evidence.append({"field": field, "terms": terms})
    name = unicodedata.normalize("NFKC", record.get("name") or "")
    if PATTERN.search(name):
        kind = "related_dessert_review" if RELATED.search(name) else "cheesecake_candidate"
        evidence.insert(0, {"field": "name", "rule": "explicit_cheesecake_name"})
    else:
        kind = "broad_review" if evidence else "not_selected"
    return {**record, "kind": kind, "match_evidence": evidence}


def filter_records(records):
    return sorted((classify(r) for r in records), key=lambda r: (ORDER[r["kind"]], r["date"], r["location"], r["meal"], r["name"]))


def write_review(classified, output):
    output.mkdir(parents=True, exist_ok=True)
    counts = dict(Counter(r["kind"] for r in classified))
    (output / "classified_menu_items.json").write_text(json.dumps({"counts": counts, "items": classified}, ensure_ascii=False, indent=2), encoding="utf-8")
    candidates = [r for r in classified if r["kind"] != "not_selected"]
    (output / "review_candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("probe-output/all_menu_items.json"))
    parser.add_argument("--output", type=Path, default=Path("probe-output"))
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    counts = write_review(filter_records(source["items"]), args.output)
    print(json.dumps({"mode": "offline_filter", "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
