#!/usr/bin/env python3
"""Opt-in integration smoke: executes only this repository's authored Rails fixture."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import route_snap_plan as rsp


def run():
    fixture = ROOT / "integration/rails_fixture"
    # Ruby/Rails dependencies must be installed explicitly by the caller.
    dump = subprocess.run(["ruby", "bin/rails", "routes", "--expanded"], cwd=fixture,
                          text=True, check=True, capture_output=True).stdout
    routes = rsp.parse_routes(dump)
    result = rsp.plan(routes, (fixture / "changed.txt").read_text().splitlines(),
                      json.loads((fixture / "samples.json").read_text()))
    assert [c["path"] for c in result["candidates"]] == [
        "/", "/admin/events", "/en/talks/fixture-talk", "/events",
        "/events/fixture-conference", "/venues/new"]
    assert len(routes) == 11, routes
    assert len(result["unresolved"]) == 2, result["unresolved"]
    assert len(result["review_notes"]) == 1, result["review_notes"]
    with tempfile.TemporaryDirectory(prefix="route-snap-smoke-") as tmp:
        plan_path = Path(tmp) / "plan.json"
        plan_path.write_text(json.dumps(result))
        verify = subprocess.run(["ruby", "verify_plan.rb", str(plan_path)], cwd=fixture,
                                text=True, check=True, capture_output=True)
        report = json.loads(verify.stdout)
    assert len(report["results"]) == 6
    assert sum(not item["dispatch_matches_candidate"] for item in report["results"]) == 1
    assert next(item for item in report["results"] if item["path"] == "/venues/new")["mismatch_in_review_notes"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
