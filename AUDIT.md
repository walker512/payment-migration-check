# Independent engineering review

Reviewed on 2026-11-17 using synthetic data only. Public project identity: walker512.

## Verified behavior

A reviewer separate from the implementation author inspected the scanner, CLI,
packaging, security boundaries, baseline checks and published claims. The review
independently reran the unit suite and installed the package in a virtual
environment, then invoked the installed CLI outside the source checkout.

Additional CLI checks confirmed:

- Unknown eligibility remains manual review, never a go-live approval.
- Same-scope baselines work; missing/different scope labels and changed rule
  fingerprints are rejected. New integration candidates produce exit 3.
- Incomplete UTF-8 assessment takes precedence and produces exit 4.
- Deep malformed baseline input fails without a traceback or echoed contents.
- Synthetic source secrets are absent from exported JSON/HTML; private-path mode
  removes literal filenames. This is pseudonymization, not anonymization.
- New report files use mode 0600 on POSIX and existing files are not overwritten.

## Comparison review

The reviewer independently executed `benchmarks/compare.py`, including the real
scanner CLI subprocess and actual ripgrep commands. Corpus hashes, confusion
matrices and first-match parity agreed with the recorded evidence:

| Configuration | TP | FN | FP | TN |
|---|---:|---:|---:|---:|
| Provider-name ripgrep | 5 | 3 | 1 | 3 |
| Same-rule ripgrep | 7 | 1 | 2 | 2 |
| Payment Migration Check | 7 | 1 | 2 | 2 |

The actual CLI produced 15 review tasks and coverage for 12 files, without
exporting the synthetic private value. The benchmark initially recorded a CLI
command while calling the core API; review required a real CLI subprocess and
explicit report-contract checks. That correction was verified.

The corpus is author-labelled synthetic regression material, not a blind test or
real-world accuracy study. The Python import rule was improved after observing
this corpus; its performance is therefore in-sample, not evidence of generalization.
The dynamic-URL miss and two unrelated-identifier false positives remain visible.

**Supported advantage:** an integrated migration-specific review deliverable over
raw search output, with categorized locations, policy review tasks, coverage and
unknowns. **Not supported:** better detection than equally configured ripgrep,
measured time savings, better general source search, or better actual migration
than dodo-migrate or the official Migration Hub. Both this tool and configured
ripgrep avoid exporting the synthetic private value in the tested configuration.

## Remaining boundaries

No real merchant migration, provider sandbox transaction, payment credential or
customer record was used. Windows execution, broad real-project precision/recall
were not independently verified in this review. The
explicit scope label is a user assertion, not proof of repository identity.
Baseline files must be trusted. This is not a full security certification or a
blanket release approval; finish applicable CI before
claiming those checks complete.

## Frozen review snapshot

Final independent rerun: **33 tests pass**, including the documentation-only
negative control. The benchmark was rerun after command-path normalization;
recorded counts and same-rule location parity remained unchanged. Normalized
commands explicitly disclose execution through `sys.executable`.

SHA-256 identities of reviewed executable/test files:

- `migration_check/core.py`: `eafe376c7f955b747b8103299e9bd8eb06ad9ec99d62ce544d0ad4931f85a0a9`
- `migration_check/cli.py`: `8502851079d6bc9ba0a667262d36f7b9106b45b2f7a3db2ff1d6a70990815482`
- `benchmarks/compare.py`: `cdfc2c0cbe6c2afd20fc9b69282a57d4fd3bd8cda8ceaa433935d2429884b767`
- `tests/test_core.py`: `90fa4f3c6c7726c9a89fb37e8c1bed22a71c6748c51940bbe58381e6a87e53ca`

## Completed visual review

The existing cloud Chromium browser displayed the real generated HTML at desktop
width and inside 390/320 CSS-pixel viewport frames. The header, caution message
and multi-column/single-column task cards were visually inspected. At 320 pixels,
review found page overflow caused by the grid minimum; the minimum was bounded
by 100% of available width. After repair, the two narrow documents measured
378/378 and 308/308 client/scroll widths (scrollbars reduce layout viewport width),
and all 15 cards in both layouts had no internal horizontal overflow.
The original 33 tests passed after the CSS-only repair. This is responsive
Chromium validation, not a physical mobile-device, Safari or accessibility audit.
The final CLI hash above includes this reviewed CSS repair.
