from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from filter_menus import classify
from notify_menus import LocalState, GitHubState, deliver, digest, render_email, select_updates, smtp_config, send_email


def record(**changes):
    row = {"date": "2026-09-26", "location": "Test Dining", "location_slug": "test",
           "meal": "Lunch", "meal_slug": "lunch", "food_id": 1, "station": "Desserts",
           "name": "Cheesecake", "kind": "cheesecake_candidate",
           "menu_url": "https://msu.nutrislice.com/menu/test/lunch/2026-09-26"}
    row.update(changes)
    return row


def report(rows=None):
    return {"start": "2026-09-21", "end": "2026-09-27", "errors": 0,
            "coverage": [{"status": "ok"}], "matches": rows if rows is not None else [record()]}


class Notifications(unittest.TestCase):
    def test_wide_capture_but_bounded_email(self):
        rows = [record(), record(food_id=2, kind="related_dessert_review", name="Cheesecake Ice Cream"),
                record(food_id=3, kind="broad_review", name="Cheese Pizza")]
        updates = select_updates(report(rows), {}, date(2026, 9, 22))
        self.assertEqual(len(updates), 2)
        self.assertEqual(classify({"name": "Cheese Pizza"})["kind"], "broad_review")

    def test_expired_dates_excluded_sunday_included(self):
        updates = select_updates(report([record(date="2026-09-21"), record(date="2026-09-27")]), {}, date(2026, 9, 22))
        self.assertEqual([v["date"] for v in updates.values()], ["2026-09-27"])

    def test_same_food_different_meals_preserved_duplicates_collapsed(self):
        rows = [record(), record(), record(meal_slug="dinner", meal="Dinner")]
        self.assertEqual(len(select_updates(report(rows), {}, date(2026, 9, 22))), 2)

    def test_success_deduplicates_and_changed_name_is_new(self):
        state = {"version": 1, "recipients": {}}
        store, sender = Mock(), Mock()
        updates = select_updates(report(), {}, date(2026, 9, 22))
        deliver(store, state, "recipient", updates, {}, ("subject", "body", "html"), date(2026, 9, 22), sender)
        sender.assert_called_once()
        self.assertEqual(store.save.call_count, 2)
        sent = state["recipients"]["recipient"]["sent"]
        self.assertEqual(select_updates(report(), sent, date(2026, 9, 22)), {})
        self.assertEqual(len(select_updates(report([record(name="Fruit Cheesecake")]), sent, date(2026, 9, 22))), 1)

    def test_incomplete_report_does_not_mean_no_matches(self):
        bad = report()
        bad["errors"] = 1
        with self.assertRaises(ValueError):
            select_updates(bad, {}, date(2026, 9, 22))
        bad["errors"] = 0
        bad["coverage"] = []
        with self.assertRaises(ValueError):
            select_updates(bad, {}, date(2026, 9, 22))

    def test_pending_saved_before_send_and_blocks_retry(self):
        saved = []
        store = Mock()
        store.save.side_effect = lambda value: saved.append(deepcopy(value))
        state = {"version": 1, "recipients": {}}
        sender = Mock(side_effect=TimeoutError("uncertain delivery"))
        with self.assertRaises(TimeoutError):
            deliver(store, state, "recipient", {}, {}, ("s", "t", "h"), date(2026, 9, 22), sender)
        self.assertIn("pending", saved[0]["recipients"]["recipient"])
        with self.assertRaises(RuntimeError):
            deliver(store, saved[0], "recipient", {}, {}, ("s", "t", "h"), date(2026, 9, 22), sender)
        sender.assert_called_once()

    def test_state_write_failure_prevents_smtp(self):
        store, sender = Mock(), Mock()
        store.save.side_effect = RuntimeError("state not writable")
        with self.assertRaises(RuntimeError):
            deliver(store, {"version": 1, "recipients": {}}, "r", {}, {}, ("s", "t", "h"), date(2026, 9, 22), sender)
        sender.assert_not_called()

    def test_html_escaped_and_unexpected_link_rejected(self):
        updates = select_updates(report([record(name="<script>alert(1)</script> Cheesecake")]), {}, date(2026, 9, 22))
        _, _, body = render_email(updates, report())
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>", body)
        self.assertIn("charset='utf-8'", body)
        updates = select_updates(report([record(menu_url="https://example.invalid/")]), {}, date(2026, 9, 22))
        with self.assertRaises(ValueError):
            render_email(updates, report())

    def test_email_settings_validate_recipients_and_tls(self):
        env = {"SMTP_HOST": "smtp.example.test", "SMTP_USERNAME": "from@example.test", "SMTP_PASSWORD": "fake-test-secret", "EMAIL_TO": "to@example.test"}
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(smtp_config()["security"], "starttls")
        with patch.dict("os.environ", {**env, "EMAIL_TO": "to@example.test\nBcc: bad@example.test"}, clear=True):
            with self.assertRaises(ValueError):
                smtp_config()

    def test_local_state_roundtrip(self):
        base = (Path.cwd() / "dist").resolve()
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            self.assertTrue(Path(directory).resolve().is_relative_to(base))
            store = LocalState(Path(directory) / "state.json")
            state = store.read()
            state["recipients"]["r"] = {"sent": {}}
            store.save(state)
            self.assertEqual(store.read(), state)

    def test_smtp_uses_tls_authentication_and_two_message_formats(self):
        config = {"host": "smtp.example.test", "port": 587, "username": "from@example.test", "password": "fake",
                  "sender": "from@example.test", "recipients": ["to@example.test"], "security": "starttls"}
        with patch("notify_menus.smtplib.SMTP") as factory:
            smtp = factory.return_value
            smtp.send_message.return_value = {}
            send_email(config, "測試", "plain text", "<p>HTML</p>")
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once_with("from@example.test", "fake")
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message["To"], "to@example.test")
            self.assertEqual(message.get_content_type(), "multipart/alternative")

    def test_failed_final_save_keeps_persisted_pending_for_manual_resolution(self):
        state = {"version": 1, "recipients": {}}
        snapshots = []
        def save(value):
            if snapshots:
                raise RuntimeError("state update unavailable after SMTP accepted")
            snapshots.append(deepcopy(value))
        store, sender = Mock(), Mock()
        store.save.side_effect = save
        updates = select_updates(report(), {}, date(2026, 9, 22))
        with self.assertRaises(RuntimeError):
            deliver(store, state, "r", updates, {}, ("s", "t", "h"), date(2026, 9, 22), sender)
        sender.assert_called_once()
        self.assertEqual(len(snapshots[0]["recipients"]["r"]["pending"]["items"]), 1)

    def test_github_state_initializes_branch_and_uses_blob_sha(self):
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "fake", "GITHUB_SHA": "a" * 40}):
            store = GitHubState()
            store.api = Mock(side_effect=[None, None, {"ref": "created"}, {"content": {"sha": "first"}}, {"content": {"sha": "second"}}])
            state = store.read()
            store.save(state)
            store.save(state)
            self.assertEqual(store.api.call_args_list[-1].args[1]["sha"], "first")
            self.assertEqual(store.sha, "second")


if __name__ == "__main__":
    unittest.main()
