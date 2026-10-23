#!/usr/bin/env python3
"""Read-only Rails change-to-screenshot candidate planner. Python stdlib only."""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote, urlsplit

__version__ = "0.1.0"
TOKEN = re.compile(r"([:*])([A-Za-z_][A-Za-z0-9_]*)")


def parse_routes(text):
    """Parse `rails routes --expanded` output; never load Ruby/project code."""
    routes, fields, engine = [], {}, None
    def flush():
        if not fields:
            return
        required = {"Verb", "URI", "Controller#Action"}
        if not required.issubset(fields):
            raise ValueError("Incomplete expanded route block: " + ", ".join(sorted(required - fields.keys())))
        target = fields["Controller#Action"]
        match = re.fullmatch(r"([\w/]+)#(\w+)", target)
        routes.append({"name": fields.get("Prefix", ""), "verb": fields["Verb"],
                       "uri": fields["URI"], "target": target,
                       "controller": match[1] if match else None,
                       "action": match[2] if match else None})
        if engine:
            routes[-1]["engine"] = engine
        fields.clear()
    for line in text.splitlines():
        section = (re.fullmatch(r"\[ Routes for (.+) \]", line.strip()) or
                   re.fullmatch(r"Routes for (.+):", line.strip()))
        if section:
            flush()
            engine = None if section[1] == "application" else section[1]
        elif re.match(r"^--\[ Route \d+ \]", line.strip()):
            flush()
        elif re.search(r"\s+\|", line):
            key, value = re.split(r"\s+\|\s*", line, maxsplit=1)
            key = key.strip()
            if key in {"Prefix", "Verb", "URI", "Controller#Action"}:
                if key in fields:
                    raise ValueError("Repeated route field; use unmodified --expanded output")
                fields[key] = value.strip()
    flush()
    if not routes:
        raise ValueError("No routes found; expected `rails routes --expanded` text")
    return routes


def render_uri(uri, params):
    """Resolve ordinary dynamic/optional segments; refuse wildcard/complex URI."""
    if not uri.startswith(("/", "(")) or uri.startswith("//"):
        raise ValueError("Route URI must be a local absolute path")
    if "*" in uri:
        raise ValueError("Wildcard route needs an explicit path override")
    if any(c in uri for c in "?#[\\\r\n\t"):
        raise ValueError("Complex route URI needs an explicit path override")
    if any(not isinstance(v, (str, int)) or isinstance(v, bool) or str(v) == "" for v in params.values()):
        raise ValueError("Sample parameters must be non-empty strings or integers")
    if any(c in str(v) for v in params.values() for c in "\r\n"):
        raise ValueError("Parameter contains a newline")
    while "(" in uri or ")" in uri:
        match = re.search(r"\([^()]*\)", uri)
        if not match:
            raise ValueError("Unbalanced optional route group")
        group = match[0][1:-1]
        names = [m[2] for m in TOKEN.finditer(group)]
        # Omit an optional group unless every parameter has an explicit sample.
        replacement = group if names and all(n in params for n in names) else ""
        uri = uri[:match.start()] + replacement + uri[match.end():]
    missing = sorted({m[2] for m in TOKEN.finditer(uri) if m[2] not in params})
    if missing:
        raise ValueError("Missing sample parameter(s): " + ", ".join(missing))
    uri = TOKEN.sub(lambda m: quote(str(params[m[2]]), safe=""), uri)
    return validate_path(uri)


def route_pattern(uri):
    """Approximate exported segment syntax solely to flag possible earlier matches."""
    parts, i = [], 0
    while i < len(uri):
        token = TOKEN.match(uri, i)
        if token:
            parts.append(".*" if token[1] == "*" else "[^/.]+")
            i = token.end()
        else:
            char = uri[i]
            parts.append("(?:" if char == "(" else ")?" if char == ")" else re.escape(char))
            i += 1
    try:
        return re.compile("^" + "".join(parts) + "$" )
    except re.error:
        return None


def validate_path(path):
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        raise ValueError("Sample path must begin with one slash, not a remote URL")
    if any(c in path for c in "\\\r\n\t") or any(ord(c) < 32 for c in path):
        raise ValueError("Sample path contains a control character or backslash")
    if any(p in {".", ".."} for p in path.split("?", 1)[0].split("/")):
        raise ValueError("Dot path segments are not allowed")
    return path


def validate_base(base):
    bits = urlsplit(base)
    if bits.scheme not in {"http", "https"} or not bits.netloc or bits.username or bits.password:
        raise ValueError("Base URL must be http(s) without embedded credentials")
    if bits.path not in {"", "/"} or bits.query or bits.fragment or any(c in base for c in "\r\n\t\\"):
        raise ValueError("Base URL must be an origin without path/query/fragment")
    return base.rstrip("/")


def normalize_file(path):
    if not isinstance(path, str) or any(c in path for c in "\r\n\x00"):
        raise ValueError("Invalid changed filename")
    while path.startswith("./"):
        path = path[2:]
    if "\\" in path or path.startswith("/") or ".." in PurePosixPath(path).parts:
        raise ValueError("Changed files must be repository-relative POSIX paths")
    return path


def plan(routes, changed, config=None, base="http://127.0.0.1:3000"):
    config = {} if config is None else config
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object")
    base = validate_base(base)
    changed = sorted(set(normalize_file(p) for p in changed if p))
    unknown_keys = set(config) - {"samples", "rules", "ignore"}
    if unknown_keys:
        raise ValueError("Unknown config keys: " + ", ".join(sorted(unknown_keys)))
    samples = config.get("samples", {})
    if not isinstance(samples, dict) or not isinstance(config.get("rules", []), list):
        raise ValueError("samples must be an object; rules must be an array")
    if not isinstance(config.get("ignore", []), list) or not all(isinstance(p, str) for p in config.get("ignore", [])):
        raise ValueError("ignore must be an array of glob strings")
    candidates, unresolved, ignored = {}, [], []
    def issue(source, reason, route=None):
        value = {"source": source, "reason": reason}
        if route:
            value["route"] = route["target"]
            value["uri"] = route["uri"]
        if value not in unresolved:
            unresolved.append(value)
    def add(path, source, reason, route=None):
        path = validate_path(path)
        target = candidates.setdefault(path, {"path": path, "url": base + path,
                    "screenshot": "shot-" + hashlib.sha256(path.encode()).hexdigest()[:12] + ".png",
                    "reasons": []})
        evidence = {"source": source, "basis": reason}
        if route:
            evidence["route"] = route["target"]
            evidence["route_name"] = route["name"]
        if evidence not in target["reasons"]:
            target["reasons"].append(evidence)
    for source in changed:
        matched_rule = False
        for rule in config.get("rules", []):
            if not isinstance(rule, dict) or set(rule) != {"glob", "paths"} or not isinstance(rule["glob"], str) or not isinstance(rule["paths"], list) or not rule["paths"]:
                raise ValueError("Every rule requires only glob and non-empty paths")
            if fnmatch.fnmatchcase(source, rule["glob"]):
                matched_rule = True
                for path in rule["paths"]:
                    add(path, source, "explicit configured mapping")
        if matched_rule:
            continue
        if any(fnmatch.fnmatchcase(source, glob) for glob in config.get("ignore", [])):
            ignored.append(source)
            continue
        view = re.fullmatch(r"app/views/(.+)/([^/]+)\.html(?:\+[^.]*)?\.(erb|haml|slim)", source)
        controller = re.fullmatch(r"app/controllers/(.+)_controller\.rb", source)
        if view and (view[2].startswith("_") or view[1] == "layouts"):
            issue(source, "Shared partial/layout: add explicit glob-to-path mapping; consumers are not inferred")
            continue
        if view:
            matched = [r for r in routes if r["controller"] == view[1] and r["action"] == view[2]]
            basis = "HTML view convention + supplied route table (candidate, not proven rendering)"
        elif controller and controller[1] != "application":
            matched = [r for r in routes if r["controller"] == controller[1]]
            basis = "changed controller + supplied route table (all GET actions; over-approximation)"
        else:
            issue(source, "No safe automatic mapping: add explicit mapping or consciously ignore this file")
            continue
        engine_matches = [r for r in matched if r.get("engine")]
        for route in engine_matches:
            issue(source, "Mounted-engine route: internal URI omits mount prefix; add explicit glob-to-path mapping", route)
        matched = [r for r in matched if not r.get("engine") and "GET" in r["verb"].split("|")]
        if not matched and not engine_matches:
            issue(source, "No matching GET route in supplied table; no URL guessed")
        for route in matched:
            key = route["name"] or route["target"]
            sample = samples.get(key, {})
            if not isinstance(sample, dict) or set(sample) - {"params", "paths"}:
                raise ValueError("Route sample must contain only params or paths: " + key)
            if "params" in sample and "paths" in sample:
                raise ValueError("Choose params or paths, not both: " + key)
            if "paths" in sample:
                if not isinstance(sample["paths"], list) or not sample["paths"]:
                    raise ValueError("paths must be a non-empty array: " + key)
                for path in sample["paths"]:
                    add(path, source, "explicit sample override; " + basis, route)
            else:
                params = sample.get("params", {})
                if not isinstance(params, dict):
                    raise ValueError("params must be an object: " + key)
                try:
                    add(render_uri(route["uri"], params), source, basis, route)
                except ValueError as error:
                    issue(source, str(error), route)
    review_notes = []
    for candidate in candidates.values():
        expected = {reason["route"] for reason in candidate["reasons"] if "route" in reason}
        if not expected:
            continue
        if len(expected) > 1:
            review_notes.append({"path": candidate["path"], "expected_targets": sorted(expected),
                "reason": "Merged candidate has multiple expected action targets; one URL may not exercise every change. Verify dispatch for each source or choose distinct reviewed samples."})
        for route in routes:
            if route.get("engine"):
                continue
            pattern = route_pattern(route["uri"])
            # Rails exports via: :all with a blank verb. Never infer a capture
            # candidate from it, but it can intercept a later explicit GET.
            may_match_get = not route["verb"] or "GET" in route["verb"].split("|")
            if not may_match_get or not pattern or not pattern.fullmatch(candidate["path"].split("?", 1)[0]):
                continue
            if route["target"] not in expected:
                review_notes.append({"path": candidate["path"], "expected_targets": sorted(expected),
                    "earlier_target": route["target"], "earlier_uri": route["uri"],
                    "reason": "Possible earlier-route shadowing; export omits request constraints. Verify dispatch or use an explicit reviewed mapping."})
            break
    return {"schema_version": 1, "status": "needs_mapping" if unresolved else "needs_review" if review_notes else "candidate_plan",
            "notice": "Candidates only, not coverage proof. Check auth, data, routing, constraints, rendering and final screenshot links.",
            "changed_files": changed, "candidates": [candidates[k] for k in sorted(candidates)],
            "unresolved": unresolved, "review_notes": review_notes, "ignored": ignored}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", required=True, type=Path, help="Saved rails routes --expanded output")
    parser.add_argument("--changed", required=True, type=Path, help="Changed paths, newline separated; use --null for git -z output")
    parser.add_argument("--null", action="store_true", help="Changed paths are NUL-delimited")
    parser.add_argument("--config", type=Path, help="Optional JSON samples, rules and ignores")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when unresolved mappings or routing review notes remain")
    args = parser.parse_args(argv)
    try:
        changed = args.changed.read_text().split("\0" if args.null else "\n")
        config = json.loads(args.config.read_text()) if args.config else {}
        result = plan(parse_routes(args.routes.read_text()), changed, config, args.base_url)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("route-snap-plan: " + str(error), file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 1 if args.strict and (result["unresolved"] or result["review_notes"]) else 0


if __name__ == "__main__":
    sys.exit(main())
