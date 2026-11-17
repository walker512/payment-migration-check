# Validation evidence — 0.1.0

## Executed locally

Environment: Linux, Python 3.12. Synthetic data only.

1. `python -m unittest discover -s tests -v`: **33 tests pass**.
2. Source-run CLI on `examples/store` and `examples/profile.json`: exit 0, **2 files / 6 rule candidates**, 15 review tasks, no unknown silently converted to ready.
3. A clean virtual environment, `python -m pip install .`: built and installed wheel successfully. This installation fetched the build dependency, not a runtime dependency.
4. Installed `migration-check scan ...` invoked from `/tmp`, outside the source checkout: exit 0, same 6 candidates. This guards against accidentally depending on working-directory imports.
5. CI baseline unit tests: unchanged report exits 0, new webhook file exits 3, shifted lines do not invent a new integration.
6. Privacy/safety checks: sentinel source secret absent from reports; filenames pseudonymized when selected; script-looking filenames escaped in HTML; existing files and symlink outputs not overwritten; symlink inputs/FIFOs skipped; budgets and bad input fail visibly.

## Not established

- No live merchant migration, sandbox provider API call or real billing test was run. Synthetic source only demonstrates discovery and report behavior, not provider interoperability.
- No measured precision/recall over real projects. Six demo categories are deliberate fixtures, **not** a general accuracy score. Generic identifiers such as `variant_id` and webhook names can yield false positives.
- A real ripgrep subprocess comparison now exists over 12 synthetic files (see benchmarks/). It is not a field accuracy or human usability study. Detection ties equally configured ripgrep; domain-specific reporting is the narrower improvement. dodo-migrate comparison remains a scope comparison.
- Windows/Python 3.10/3.13 jobs are configured but not run locally. A published CI result is still required before claiming those targets verified.
- Cloud Chromium visual review completed at a desktop viewport and embedded 390/320 CSS-pixel report viewports. Review found and fixed narrow-screen grid overflow. After repair, document scroll width equaled client width (378/378 and 308/308 with scrollbars), and no task card overflowed. This tests responsive layout, not physical mobile devices or Safari. Earlier standalone Playwright startup was blocked by sandbox socket restrictions; the existing authorized browser was used instead.
- Official Migration Hub was scheduled for December 2, 2026 and unavailable at the policy review date. No claim is made to have tested it.

## Independent review gate

Implementation self-tests are not independent review. Before release, a different reviewer should check behavior, scan boundaries, report leaks, input validation, packaging and README claims; rerun the suite; and examine the generated HTML in a browser. Any blockers must be fixed and retested. No automatic “audit passed” badge is provided.
