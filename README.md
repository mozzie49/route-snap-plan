# route-snap-plan

**Independent alpha — planning only, not screenshot verification.**

**Turn a Rails changed-file list into a reviewable screenshot plan.**

A tiny, offline, dependency-free Python CLI. It answers **which URLs should I inspect?**, not “did my UI pass?”

```text
app/views/events/index.html.erb  → /events
app/views/events/show.html.erb   → unresolved: needs a sample slug
app/views/shared/_header.html.erb → unresolved: map its consumers explicitly
```

Agent-generated PRs need actual visual evidence. Guessing `/events/1`, silently ignoring shared components, or attaching a dead `tmp/shot.png` link is not evidence. This tool makes the planning gaps visible before you run Playwright or Capybara.

## Try it without Rails

Python 3.10+. No install, network, credentials, or project execution:

```sh
python3 route_snap_plan.py \
  --routes examples/routes.txt \
  --changed examples/changed.txt \
  --config examples/config.json --strict
```

The example emits `/`, `/events`, and `/events/sample-conference-2026`, each with the source files and reasons that selected it. The fixture is synthetic, **not** a capture from RubyEvents or another running app.

Omit `--config` to see the missing slug and shared-partial mapping reported explicitly. With `--strict`, those gaps exit `1` instead of silently producing a partial green result.

## For coding agents

The self-contained repository skill source is [`skills/rails-screenshot-plan/SKILL.md`](skills/rails-screenshot-plan/SKILL.md). It bundles the tested helper and sample inputs, anchors helper paths to the skill directory, and keeps **planned**, **captured**, and **published/link-verified** evidence separate. Review the files before installing; this repository does not install itself or grant any permissions.

### Install the skill

Clone this repository, review `skills/rails-screenshot-plan/`, then copy that whole folder into a skills directory supported by your agent. For a [project-scoped Codex skill](https://developers.openai.com/blog/skills-agents-sdk), from the destination project root:

```sh
# First clone this repository into a separate directory and review its files.
mkdir -p .agents/skills
# Refuse to overwrite an existing local skill.
test ! -e .agents/skills/rails-screenshot-plan && \
  cp -R /path/to/route-snap-plan/skills/rails-screenshot-plan .agents/skills/
```

Ask your agent to use `rails-screenshot-plan` for a Rails UI change and provide the saved route dump and changed-file list. Other clients have different discovery paths; use their documented skill installation method. No claim of universal auto-discovery or personal-library installation is made.

## Use on your trusted Rails app

Prepare two inputs yourself:

```sh
# This command boots YOUR Rails app. Only run it in a trusted checkout.
bin/rails routes --expanded > /tmp/routes.txt

# Choose the correct review base for your project; this example uses origin/main.
git diff --name-only -z origin/main...HEAD > /tmp/changed.paths

python3 /path/to/route_snap_plan.py \
  --routes /tmp/routes.txt --changed /tmp/changed.paths --null \
  --config screenshot-plan.json --strict > /tmp/screenshot-plan.json
```

The planner itself only reads those text/JSON inputs. It does not execute Git, Ruby, Rails, a browser, hooks, or repository scripts. Export routes for the same revision being reviewed; stale exports cannot be detected automatically. For renames, include both old and new paths when their removal may affect rendering.

### Supply real examples, never invented IDs

```json
{
  "samples": {
    "event": {"params": {"slug": "sample-conference-2026"}},
    "admin_event": {"paths": ["/admin/events/known-fixture"]}
  },
  "rules": [
    {"glob": "app/views/shared/_header.html.erb", "paths": ["/", "/events"]},
    {"glob": "app/components/event_card/*", "paths": ["/events"]},
    {"glob": "app/assets/stylesheets/*", "paths": ["/", "/events"]}
  ],
  "ignore": ["test/*", "docs/*"]
}
```

- `samples` keys are the route's **Prefix** (without `_path`); unnamed routes use `controller#action`.
- Use either `params` or explicit `paths` for a sample. Parameter values are URL-encoded.
- `rules` are explicit file-glob → same-origin page mappings. Matching rules take precedence over conventions and ignore patterns; all matching rule paths are combined.
- Globs use Python `fnmatch` semantics: `*` **can cross `/`**, unlike some shell/glob libraries.
- Ignore only files you have intentionally reviewed as outside this screenshot plan.
- Samples and rules may refer to authenticated pages. They do not authenticate, verify fixture data, or guarantee access.

## What gets inferred

| Change | Candidate selection |
|---|---|
| `app/views/events/index.html.erb` | GET routes targeting `events#index` |
| `app/views/admin/events/index.html.haml` | GET routes targeting `admin/events#index` |
| `app/controllers/events_controller.rb` | All GET routes targeting that controller; deliberately over-inclusive |
| Dynamic `:slug`, `:id` | Requires an explicit sample value or path |
| Optional `(:locale)` / `(.:format)` | Omitted unless sample values are supplied |
| Partial, layout, ViewComponent, JS/CSS, model, helper, application controller | Explicit mapping or unresolved; no guessed dependency graph |
| Turbo Stream view, wildcard, mounted engine, complex/opaque route target | Explicit mapping or unresolved |
| No matching GET route | Unresolved; never guesses a URL |

Both Haml and Slim HTML templates are supported. Only explicitly listed `GET` verbs are selected, never POST/PUT/PATCH/DELETE or a blank/all-method verb. Every automatic URL is labeled a **candidate**, not proof that the file renders on that page. Inheritance, alternate render calls, earlier-route shadowing, request constraints, host constraints, authentication, data, routes returning JSON, and viewport coverage need review.

## Output and exit status

The JSON contains `candidates`, `unresolved`, `review_notes`, `ignored`, and the original `changed_files`. Candidates have a stable safe screenshot filename, URL, and provenance. Duplicate URLs retain all source reasons.

- `0`: valid plan output (without `--strict`, unresolved items may still exist).
- `1`: unresolved mappings or routing review notes remain under `--strict`.
- `2`: malformed input, unsupported config shape, or read failure.

Possible earlier-route shadowing is emitted as a structured `review_notes` item; it is a caution, not a claim that omitted route constraints definitely allow the earlier match. Other runtime constraints remain unverified.

No remote URLs are accepted as sample paths. The optional `--base-url` must be an HTTP(S) origin without credentials. The planner never fetches it.

## From plan to real screenshots

Review unresolved entries, make fixture/auth choices, then hand candidate URLs to your **existing** Playwright or Capybara workflow. Confirm successful responses and rendered UI rather than capturing an error/login page. Publish the resulting images using a supported host/upload path and verify the final PR's stored image URLs.

This planner does **not** take screenshots, host images, upload artifacts, modify PRs, or repair broken image links. Actions artifacts are downloadable build outputs with retention limits, not a substitute for a verified inline image URL.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile route_snap_plan.py
```

Coverage includes unresolved IDs, namespaces, partials/layouts, POST exclusion, explicit mapping, malformed routes/config, path validation, deterministic output, and strict/NUL-delimited CLI behavior. The 39 offline tests include an path-redacted export captured from a real, self-authored Rails 8.1.0 fixture.

The opt-in [live Rails smoke](integration/README.md) has also passed on Ruby 3.3.8 / Rails 8.1.0: 11 exported routes, 6 candidate URLs, 2 explicit unresolved mappings, and 1 routing warning. All 6 URLs returned fixture HTML with status 200 through Rack. One deliberately shadowed URL dispatched to a different action, exactly as the planner warned. This is framework integration validation, **not** a RubyEvents deployment test or a browser screenshot test.

## Background

Inspired by a concrete maintainer request for an “expected screenshots for changed files” script in [RubyEvents #2226](https://github.com/rubyevents/rubyevents/issues/2226#issuecomment-6219543919). This is an independent prototype, not an upstream-approved integration or a claim to fix that entire issue.

Native building blocks remain the right tools:

- [Rails route inspection](https://guides.rubyonrails.org/routing.html#listing-existing-routes) provides the route table.
- [Playwright screenshots](https://playwright.dev/docs/screenshots) captures actual pages.
- [GitHub workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data) stores files with explicit retention.

The narrow gap here is a **diff-to-URL candidate plan with visible uncertainty**.
