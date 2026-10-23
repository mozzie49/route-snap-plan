# Mapping configuration

Use a JSON object with these optional fields:

```json
{
  "samples": {
    "event": {"params": {"slug": "known-fixture-slug"}},
    "admin_event": {"paths": ["/admin/events/known-fixture"]}
  },
  "rules": [
    {"glob": "app/views/shared/_header.html.erb", "paths": ["/", "/events"]}
  ],
  "ignore": ["test/*", "docs/*"]
}
```

- Sample key: Rails route **Prefix**, without `_path`; unnamed routes use `controller#action`.
- A sample uses `params` OR `paths`. Required missing params remain unresolved. Optional groups are omitted unless all their params have samples. Wildcards/complex routes require explicit paths.
- Rule paths start with one `/` and stay on the chosen origin. Matching rules override automatic inference and ignores; matching rules combine.
- Globs use Python `fnmatch`, whose `*` can cross `/`.
- Ignore only consciously reviewed files; all other unknowns remain unresolved.
- Direct HTML views support ERB, Haml, and Slim. Direct controllers select every explicit GET action, deliberately over-inclusive. The application controller, partials/layouts, components, JS/CSS, helpers/models, Turbo Stream templates and opaque engine routes need mapping.
- Possible earlier-route shadowing appears in `review_notes`; constraints are missing from the dump, so this is a review caution rather than a definitive routing failure.
- The planner does not check app state, route constraints, auth or sample existence. Verify those before capture. A sample path does not assert the URL works.
- Use `--base-url http://127.0.0.1:3000` (the default) or an explicitly chosen HTTP(S) origin. The script only emits URLs and never fetches them.

## Mounted engines

Expanded Rails output may append `[ Routes for Some::Engine ]` sections. Their paths are internal to the engine, not complete application URLs. The helper marks matching engine views/controllers unresolved. Use an explicit, source-verified glob-to-path rule including the mount prefix; do not automatically prepend a guessed mount or reuse the internal URI.

