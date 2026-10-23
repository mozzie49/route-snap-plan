---
name: rails-screenshot-plan
description: Plan visual evidence for Rails UI changes or an agent-generated PR by mapping changed files to screenshot candidate URLs. Use before browser capture when choosing affected pages. Not for pixel-diff judging or general frontend design.
---

# Rails screenshot plan

Produce a compact, evidence-linked capture plan before spending browser time. Separate candidate URLs from unresolved coverage; never treat a proposed screenshot as a screenshot that exists.

1. Obtain a repository-relative changed-file list and a saved `bin/rails routes --expanded` dump for the reviewed revision. Prefer supplied inputs. Exporting routes boots the application: only do that in a trusted checkout when authorized; the bundled planner does not execute project code.
2. Resolve the absolute directory containing **this** `SKILL.md`; call it `SKILL_DIR`. Locate the helper under that directory, not the project's working directory:

   ```sh
   python3 "$SKILL_DIR/scripts/route_snap_plan.py" \
     --routes /path/to/routes.txt --changed /path/to/changed.txt \
     --config /path/to/screenshot-plan.json --strict
   ```

   Omit `--config` if no mappings exist. Add `--null` for `git diff --name-only -z` input. Example input files are under [samples/](samples/); these are synthetic, not real app state.

3. Use the JSON's candidate URLs, filenames, source reasons, and `review_notes` directly. Preserve those review notes in machine-readable handoffs; append new evidence-backed cautions there rather than only mentioning them in prose. For unresolved dynamic parameters, find an existing fixture/sample record or keep the route blocked; do not invent ID `1`. Map shared partials, layouts, components, styles, and controller-wide changes to representative pages only when source evidence or an established map supports the choice. See [mapping reference](references/mapping.md) when adding mappings.
4. Review auth, fixture data, request/host constraints, earlier-route shadowing, viewport, and alternate render paths. Automatic view/controller matches are candidates, not exhaustive dependency analysis. `--strict` exit `1` means a plan was emitted with unresolved mappings or routing review notes; exit `2` means input/config failure. Do not “fix” strict failure by ignoring an unexamined file.
5. When capture is within the user's task, use the existing Playwright/Capybara/browser workflow. Check the response and rendered page, not just that a PNG file was created. A login/error-page capture does not validate the intended change.
6. Report three distinct states: **planned**, **captured and inspected**, **published and link-verified**. Use only the states actually reached. Uploading images or editing a PR needs the task's authorization; this skill supplies none. Never put local `tmp/` or `file://` paths into a PR as working image links.

If the task is only to plan, stop after delivering candidate URLs and explicit unresolved reasons. If screenshot verification was requested, continue through the authorized capture/inspection steps or report the exact blocker.
