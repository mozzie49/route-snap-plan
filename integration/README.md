# Live Rails integration evidence

Verified 2026-10-22 in an isolated cloud workspace using **Ruby 3.3.8 / Rails 8.1.0**. This is a small self-authored Rails application, not RubyEvents source and not a hand-authored imitation of CLI output.

## What actually ran

1. Booted `rails_fixture` and ran `ruby bin/rails routes --expanded`.
2. Passed that command's unmodified output (the published fixture redacts only absolute source locations) into the Python planner.
3. Sent all selected GET paths through the initialized Rails application using `Rack::MockRequest` and checked the rendered fixture HTML.
4. Compared Rails' actual recognized controller/action to the planner's provenance or explicit warning.

Results: **11 exported routes; 6 candidates; 2 unresolved mappings; 1 routing review note**. All six candidate requests returned HTTP 200 and fixture HTML. `/venues/new` deliberately dispatches to `venues#show`, not `venues#new`, because an earlier dynamic route shadows it; the planner's structured warning correctly catches this uncertainty before a browser session.

The live run caught a genuine parser bug that synthetic fixtures had missed: Rails appends a separate mounted-engine route table. The old helper treated its `/entries` URI as a complete URL. The fixed helper preserves engine context and leaves that view unresolved instead of emitting a bogus URL. A verified explicit mount-prefix mapping is required. The other unresolved file is a shared partial whose consumers are not inferred.

## Reproduce

The normal planner and offline tests do **not** require Ruby or any gems. This integration check is opt-in and boots only the fixture shipped here. In a trusted development environment with Ruby 3.2 or newer:

```sh
gem install railties -v 8.1.0 --no-document
python3 integration/run_rails_smoke.py
```

The command asserts candidate paths, uncertainty counts, successful rendered responses, and that the only dispatch mismatch is covered by a review note. Transitive dependency versions can vary; the verified environment's activated gem versions are in `runtime-gems.json`.

The original run used signed Debian repository packages for Ruby, extracted into `/tmp`, and official RubyGems packages installed into a separate `/tmp` GEM_HOME. No system packages, user desktop, upstream app, credentials, database, or external app service were used. The initial environment package mirror returned HTTP 502; the signed official Debian repository succeeded. Ruby's temporary relocation bootstrap is environment-specific and is not required by the product.

## Artifacts and limits

- `rails-expanded-8.1.0.txt`: captured CLI output with only the absolute fixture root replaced by `<FIXTURE_ROOT>`; route data and engine section are unchanged.
- `planner-result.json`: resulting machine-readable plan.
- `rack-verification.json`: actual HTTP statuses and recognized action targets.
- `rails_fixture/`: complete self-authored fixture source.
- `run_rails_smoke.py`: repeatable live integration assertions.
- `../tests/test_real_rails_export.py`: offline regression tests replaying the captured output.

No browser was launched and no screenshot was created, uploaded, or link-verified. A 200 response is not visual approval; the intentionally shadowed route demonstrates why. This validates the Rails-output-to-plan boundary and concrete routing behavior, not all Rails versions, engine configurations, authentication flows, RubyEvents compatibility, or real-user efficiency.

Framework reference: [Rails route inspection](https://guides.rubyonrails.org/routing.html#listing-existing-routes). Rails and its gem dependencies remain third-party software; only our fixture code and captured test outputs are included here.
