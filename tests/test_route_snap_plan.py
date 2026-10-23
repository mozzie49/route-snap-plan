import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import route_snap_plan as rsp

ROOT = Path(__file__).resolve().parents[1]


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.routes = rsp.parse_routes((ROOT / "examples/routes.txt").read_text())

    def test_route_parser(self):
        self.assertEqual(len(self.routes), 5)
        self.assertEqual(self.routes[3]["name"], "")

    def test_empty_route_dump_fails(self):
        with self.assertRaisesRegex(ValueError, "No routes"):
            rsp.parse_routes("not a route table")

    def test_incomplete_block_fails(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            rsp.parse_routes("Verb | GET\nURI | /\n")

    def test_repeated_field_fails(self):
        with self.assertRaisesRegex(ValueError, "Repeated"):
            rsp.parse_routes("Verb | GET\nVerb | POST\n")

    def test_index_view(self):
        result = rsp.plan(self.routes, ["app/views/events/index.html.erb"])
        self.assertEqual(result["candidates"][0]["path"], "/events")
        self.assertFalse(result["unresolved"])
        self.assertIn("candidate", result["candidates"][0]["reasons"][0]["basis"])

    def test_dynamic_route_is_unresolved_not_guessed(self):
        result = rsp.plan(self.routes, ["app/views/events/show.html.erb"])
        self.assertFalse(result["candidates"])
        self.assertIn("slug", result["unresolved"][0]["reason"])

    def test_sample_parameter(self):
        result = rsp.plan(self.routes, ["app/views/events/show.html.erb"],
                          {"samples": {"event": {"params": {"slug": "a/b c"}}}})
        self.assertEqual(result["candidates"][0]["path"], "/events/a%2Fb%20c")

    def test_controller_is_all_get_actions_not_post(self):
        result = rsp.plan(self.routes, ["app/controllers/events_controller.rb"])
        self.assertEqual([x["path"] for x in result["candidates"]], ["/events"])
        self.assertEqual(len(result["unresolved"]), 1)
        self.assertNotIn("events#create", json.dumps(result))

    def test_namespace(self):
        result = rsp.plan(self.routes, ["app/views/admin/events/index.html.erb"])
        self.assertEqual(result["candidates"][0]["path"], "/admin/events")

    def test_partial_not_assumed_parent_controller(self):
        result = rsp.plan(self.routes, ["app/views/events/_row.html.erb"])
        self.assertFalse(result["candidates"])
        self.assertIn("Shared", result["unresolved"][0]["reason"])

    def test_layout_not_assumed(self):
        self.assertTrue(rsp.plan(self.routes, ["app/views/layouts/application.html.erb"])["unresolved"])

    def test_rule_dedupes_and_keeps_evidence(self):
        result = rsp.plan(self.routes, ["app/views/events/index.html.erb", "app/views/shared/_header.html.erb"],
                          {"rules": [{"glob": "app/views/shared/*", "paths": ["/", "/events"]}]})
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(len(result["candidates"][1]["reasons"]), 2)
        self.assertFalse(result["unresolved"])

    def test_unknown_file_not_silent(self):
        self.assertTrue(rsp.plan(self.routes, ["app/models/event.rb"])["unresolved"])

    def test_explicit_ignore(self):
        result = rsp.plan(self.routes, ["docs/a.md"], {"ignore": ["docs/*"]})
        self.assertEqual(result["ignored"], ["docs/a.md"])
        self.assertFalse(result["unresolved"])

    def test_no_matching_action(self):
        self.assertIn("No matching GET", rsp.plan(self.routes, ["app/views/events/other.html.erb"])["unresolved"][0]["reason"])

    def test_turbo_stream_needs_mapping(self):
        self.assertTrue(rsp.plan(self.routes, ["app/views/events/index.turbo_stream.erb"])["unresolved"])

    def test_escaped_path_override(self):
        result = rsp.plan(self.routes, ["app/views/events/show.html.erb"],
                          {"samples": {"event": {"paths": ["/events/known?tab=schedule"]}}})
        self.assertEqual(result["candidates"][0]["path"], "/events/known?tab=schedule")

    def test_rules_cannot_inject_remote_url(self):
        for path in ["https://evil.invalid/x", "//evil.invalid/x", "/\\evil", "/bad\nline", "/../x"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                rsp.plan(self.routes, ["x"], {"rules": [{"glob": "*", "paths": [path]}]})

    def test_base_restrictions(self):
        for base in ["file:///x", "https://user:pass@x", "https://x/sub", "https://x?q=1"]:
            with self.subTest(base=base), self.assertRaises(ValueError):
                rsp.plan(self.routes, [], base=base)

    def test_changed_paths_cannot_escape(self):
        for path in ["../x", "/etc/passwd", "app\\x", "app/../x"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                rsp.plan(self.routes, [path])

    def test_optional_locale(self):
        self.assertEqual(rsp.render_uri("(/:locale)/events(.:format)", {}), "/events")
        self.assertEqual(rsp.render_uri("(/:locale)/events(.:format)", {"locale": "fr"}), "/fr/events")

    def test_wildcard_refused(self):
        with self.assertRaisesRegex(ValueError, "Wildcard"):
            rsp.render_uri("/files/*path(.:format)", {"path": "hello"})

    def test_invalid_json_config_shape(self):
        for config in [[], "x", {"ignore": "*"}, {"rules": ["*"]}, {"typo": []}]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                rsp.plan(self.routes, ["a"], config)

    def test_invalid_parameter_values(self):
        for value in [None, False, [], "", ".."]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                rsp.render_uri("/events/:slug", {"slug": value})

    def test_blank_verb_is_not_implicitly_get(self):
        routes = rsp.parse_routes("Prefix | all\nVerb |\nURI | /all\nController#Action | all#index\n")
        result = rsp.plan(routes, ["app/views/all/index.html.erb"])
        self.assertTrue(result["unresolved"])
        self.assertFalse(result["candidates"])

    def test_earlier_dynamic_route_gets_structured_review_note(self):
        routes = rsp.parse_routes("Prefix | item\nVerb | GET\nURI | /items/:id(.:format)\nController#Action | items#show\n--[ Route 2 ]---\nPrefix | new_item\nVerb | GET\nURI | /items/new(.:format)\nController#Action | items#new\n")
        result = rsp.plan(routes, ["app/views/items/new.html.erb"])
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["review_notes"][0]["earlier_target"], "items#show")
        self.assertEqual(result["candidates"][0]["path"], "/items/new")

    def test_earlier_all_method_route_can_shadow_explicit_get(self):
        routes = rsp.parse_routes("Prefix | all\nVerb |\nURI | /events\nController#Action | catch#all\n--[ Route 2 ]---\nPrefix | events\nVerb | GET\nURI | /events\nController#Action | events#index\n")
        result = rsp.plan(routes, ["app/views/events/index.html.erb"])
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["review_notes"][0]["earlier_target"], "catch#all")
        self.assertEqual(result["candidates"][0]["reasons"][0]["route"], "events#index")

    def test_deduped_url_with_conflicting_targets_needs_review(self):
        routes = rsp.parse_routes("Prefix | item\nVerb | GET\nURI | /items/:id(.:format)\nController#Action | items#show\n--[ Route 2 ]---\nPrefix | new_item\nVerb | GET\nURI | /items/new(.:format)\nController#Action | items#new\n")
        for ordered_routes in [routes, list(reversed(routes))]:
            with self.subTest(first_target=ordered_routes[0]["target"]):
                result = rsp.plan(ordered_routes, ["app/controllers/items_controller.rb"],
                                  {"samples": {"item": {"params": {"id": "new"}}}})
                self.assertEqual(len(result["candidates"]), 1)
                self.assertEqual(len(result["candidates"][0]["reasons"]), 2)
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["review_notes"][0]["expected_targets"], ["items#new", "items#show"])
                self.assertIn("multiple expected", result["review_notes"][0]["reason"])

    def test_strict_cli_checks_review_notes_without_unresolved_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "routes").write_text("Prefix | item\nVerb | GET\nURI | /items/:id\nController#Action | items#show\n--[ Route 2 ]---\nPrefix | new_item\nVerb | GET\nURI | /items/new\nController#Action | items#new\n")
            (root / "changed").write_text("app/views/items/new.html.erb\n")
            with contextlib.redirect_stdout(io.StringIO()):
                status = rsp.main(["--routes", str(root / "routes"), "--changed", str(root / "changed"), "--strict"])
            self.assertEqual(status, 1)

    def test_static_route_first_has_no_shadow_warning(self):
        routes = rsp.parse_routes("Prefix | new_item\nVerb | GET\nURI | /items/new(.:format)\nController#Action | items#new\n--[ Route 2 ]---\nPrefix | item\nVerb | GET\nURI | /items/:id(.:format)\nController#Action | items#show\n")
        result = rsp.plan(routes, ["app/views/items/new.html.erb"])
        self.assertFalse(result["review_notes"])

    def test_earlier_wildcard_gets_review_note(self):
        routes = rsp.parse_routes("Prefix | wildcard\nVerb | GET\nURI | /*all\nController#Action | catch#all\n--[ Route 2 ]---\nPrefix | events\nVerb | GET\nURI | /events\nController#Action | events#index\n")
        result = rsp.plan(routes, ["app/views/events/index.html.erb"])
        self.assertEqual(result["review_notes"][0]["earlier_target"], "catch#all")

    def test_determinism(self):
        a = rsp.plan(self.routes, ["app/views/events/index.html.erb", "x"])
        b = rsp.plan(self.routes, ["x", "./app/views/events/index.html.erb", "x"])
        self.assertEqual(a, b)

    def test_cli_strict_status_and_null_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "changed"
            changed.write_bytes(b"app/views/events/show.html.erb\0")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = rsp.main(["--routes", str(ROOT / "examples/routes.txt"), "--changed", str(changed), "--null", "--strict"])
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(out.getvalue())["status"], "needs_mapping")

    def test_cli_bad_input_status(self):
        with contextlib.redirect_stderr(io.StringIO()):
            status = rsp.main(["--routes", "/missing", "--changed", "/missing"])
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()
