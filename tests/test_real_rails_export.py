"""Replay path-redacted output captured from the self-authored Rails 8.1.0 app."""
import json
from pathlib import Path
import unittest

import route_snap_plan as rsp

ROOT = Path(__file__).resolve().parents[1]


class RealRailsExportTests(unittest.TestCase):
    def setUp(self):
        self.routes = rsp.parse_routes((ROOT / 'integration/rails-expanded-8.1.0.txt').read_text())

    def test_live_export_sections_and_source_locations(self):
        self.assertEqual(len(self.routes), 11)
        self.assertNotIn('engine', self.routes[0])
        self.assertEqual(self.routes[-1]['engine'], 'Embedded::Engine')
        self.assertEqual(self.routes[-1]['uri'], '/entries(.:format)')
        self.assertEqual(self.routes[-1]['target'], 'embedded/entries#index')

    def test_engine_internal_path_is_not_full_candidate_url(self):
        result = rsp.plan(self.routes, ['app/views/embedded/entries/index.html.erb'])
        self.assertFalse(result['candidates'])
        self.assertIn('mount prefix', result['unresolved'][0]['reason'])

    def test_explicit_engine_mapping_is_allowed(self):
        result = rsp.plan(self.routes, ['app/views/embedded/entries/index.html.erb'],
                          {'rules': [{'glob': 'app/views/embedded/**', 'paths': ['/embedded/entries']}]})
        self.assertEqual(result['candidates'][0]['path'], '/embedded/entries')
        self.assertFalse(result['unresolved'])

    def test_captured_plan_matches_actual_export(self):
        fixture = ROOT / 'integration/rails_fixture'
        actual = rsp.plan(self.routes, (fixture / 'changed.txt').read_text().splitlines(),
                          json.loads((fixture / 'samples.json').read_text()))
        self.assertEqual(actual, json.loads((ROOT / 'integration/planner-result.json').read_text()))
        self.assertEqual(len(actual['candidates']), 6)
        self.assertEqual(len(actual['unresolved']), 2)
        self.assertEqual(len(actual['review_notes']), 1)

    def test_legacy_engine_heading_is_conservative(self):
        routes = rsp.parse_routes('Routes for Example::Engine:\nPrefix | entry\nVerb | GET\nURI | /entry\nController#Action | entries#show\n')
        self.assertEqual(routes[0]['engine'], 'Example::Engine')
        self.assertTrue(rsp.plan(routes, ['app/views/entries/show.html.erb'])['unresolved'])
