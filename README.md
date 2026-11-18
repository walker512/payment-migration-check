# Payment Migration Check

**Find the payment code you still need to migrate, not just the records you need to copy.**

An offline Lemon Squeezy migration readiness scanner by **walker512**. Point it at a local source tree to get a file-and-line inventory, a source-linked migration checklist and a self-contained HTML report. No API keys, AI service, customer export or telemetry required.

> This is a migration **discovery and review** tool, not a payment migration engine. It never declares a store ready, determines legal eligibility, moves subscriptions or changes billing.

## Try it in one minute

Python 3.10+; no runtime dependencies. From this checkout:

```sh
python -m migration_check scan examples/store --profile examples/profile.json --json demo.json --html demo.html
```

Open `demo.html` locally. The bundled store is **synthetic source**, not a real merchant, integration or working checkout. Its expected result is **6 candidates across 2 files**, with eligibility still unknown.

For your own repository:

```sh
python -m migration_check scan /path/to/your/app --json review.json --html review.html
```

Windows PowerShell works too:

```powershell
py -m migration_check scan C:\projects\my-app --json review.json --html review.html
```

Or install a local CLI in a virtual environment:

```sh
python -m venv .venv
# Linux/macOS: . .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
python -m pip install .
migration-check --help
```

Installation may download setuptools from PyPI; **running the scanner is offline**. The source-run command needs no install or download.

## What it actually does

- Locates candidates for SDK setup, checkout links/overlays, webhook lifecycle, license APIs, product/variant mapping and affiliate integration.
- Records relative file, first matching line and rule. **Never exports source lines, matched values, customer identifiers or credentials.** Paths themselves may be private; use `--private-paths` before sharing.
- Separates observed source candidates, manual declarations, unknowns and excluded/unreadable source. “Not found” never means “not used.”
- Produces JSON for tooling and portable, script-free HTML for human review.
- Flags new `(rule, file)` candidates against a reviewed baseline, useful when old-provider code returns during a migration freeze.
- Refuses to overwrite existing files. Use a fresh report name on every run.

## Manual feature profile

Copy `examples/profile.json`. Only the documented keys are accepted; do not put customer records, API keys, countries, account IDs or email addresses in it.

| Key | Values |
|---|---|
| `managed_payments_eligibility` | `confirmed`, `ineligible`, `unknown` |
| `paypal_subscriptions`, `licenses`, `file_delivery`, `affiliates`, `storefront`, `india_issued_cards`, `cash_app_subscriptions` | `yes`, `no`, `unknown` |

Omitted keys are unknown. A confirmed eligibility declaration is **your assertion**, never this tool's finding. A `no` declaration does not erase matching source evidence. Checklist statuses are not task-completion states; check completion in your own tracker.

## CI guard against reintroducing old integration points

First review and save a baseline, ideally outside the scanned tree:

```sh
python -m migration_check scan src --scope-id shop/src --private-paths --json baseline.json
python -m migration_check scan src --scope-id shop/src --private-paths --baseline baseline.json --fail-on-new --json current.json
```

Exit codes:

- `0`: scan completed (still manual review required)
- `2`: invalid input or output error
- `3`: new integration candidates with `--fail-on-new`
- `4`: incomplete assessment due to budget, unreadable/oversize or non-UTF-8 or NUL-containing source; this takes precedence over `3`

Baselines must be trusted reports from the **same repository and same relative scan root**. Use a non-sensitive `--scope-id` label such as `shop/src` for both runs. The scanner rejects differing/missing scope labels and changed rule/filter/limit fingerprints. The label is your assertion; it cannot prove that two directories are the same repository. Do not reuse a label for unrelated roots. Moving between machines is allowed if scope and rules are unchanged. Old baselines without this metadata must be reviewed and regenerated.

Moving code between lines in the same file does not trip the baseline. Adding another call of the same rule to an already matched file **does not** trip it either. This is a file-level inventory gate, not an exhaustive call graph or security gate. Exclusions and symlinks are always disclosed as counts but do not trigger `4` by themselves.

## Official policy versus local evidence

Policy notes are a dated snapshot checked **2026-11-17**, not live provider queries. After 14 days, reports visibly request a source refresh. Always verify the current [official migration guide](https://docs.lemonsqueezy.com/migration), [feature comparison](https://docs.lemonsqueezy.com/migration/comparison) and your store's migration notice.

The guide describes payments ending March 31, 2027 and eligible-store migration tooling planned for December 2, 2026. That tooling was not available to test at snapshot time. Managed Payments does not include storefront, file/key delivery or affiliate tooling; PayPal subscriptions require another supported-payment arrangement. Location and product eligibility are provider decisions. Dates and feature coverage can change; no automatic destination recommendation is made here.

## Why not just dodo-migrate?

[dodo-migrate](https://github.com/dodopayments/dodo-migrate) is designed to copy supported records to Dodo, with test/live modes, confirmations and repeatable runs. **Use it when that is your job.** We keep the useful principles of local CLI operation, repeatable review and auditability, but make no claim to its provider coverage.

| Job | This project | dodo-migrate, documented scope reviewed 2026-11-17 |
|---|---|---|
| Copy products/customers/discounts/license keys | No | Yes, provider-dependent |
| Call provider test/live APIs | Never | Yes |
| Local code file-and-line discovery | Yes, heuristic rules | Not advertised in reviewed README |
| Unknown/coverage-aware offline review report | Yes | Not its stated purpose |
| Needs provider credentials | No | Yes |

This dodo-migrate comparison is based on documented scope, **not a head-to-head quality benchmark**. Our tests demonstrate narrower capabilities; they cannot establish that we are better overall. No code was copied from that GPL-3.0 project.

## Measured comparison with ripgrep

A reproducible 12-file synthetic corpus compares actual ripgrep execution and this scanner. Keyword grep: TP 5 / FN 3 / FP 1. Same-rule ripgrep and this tool: TP 7 / FN 1 / FP 2, with identical first-match locations. **No detection advantage over equally configured ripgrep is claimed.** The tested advantage is the integrated migration-specific report and review queue, not general search quality. We fixed a Python import miss found in the comparison and retained all remaining misses/false positives. See [commands, truth labels, evidence and caveats](benchmarks/README.md).

## Validation and limitations

```sh
python -m unittest discover -s tests -v
```

The suite covers all six rule categories in bundled source, CLI reports, new-candidate gating, secret-value non-export, unknown eligibility, bad profiles, HTML escaping, symlinks, FIFOs, size/budget limits and invalid encodings. See [VALIDATION.md](VALIDATION.md) for reproducible evidence and what was **not** tested.

Static identifiers can match comments or unrelated libraries. Generated links, remote configuration and unsupported languages can be missed. A scan is not a security audit, real payment test, legal/tax advice or migration guarantee. See [provider rehearsal boundaries and official test anchors](docs/PROVIDER-REHEARSAL.md). The next step remains provider-sandbox rehearsal with your own approved test credentials, then a reviewed operational cutover. This project deliberately does not collect them.

## Contributing and security

Contributions should add a minimal **synthetic** positive fixture, a negative fixture and regression tests. Do not submit raw merchant logs or customer data. Read [SECURITY.md](SECURITY.md) before sharing reports or scanning untrusted trees.

MIT licensed. Public project identity: walker512.

## Review a migration rescan (0.2.0)

Use the same `--baseline` command above after editing the local source. JSON keeps
schema version 1 and the existing `new_findings` array; an additive
`baseline_comparison` object (comparison version 1) now contains `new`, `retained`
(with `previous_line`), `not_observed_now`, the baseline bytes' SHA-256, both
incomplete flags, and before/after/delta coverage counts. HTML shows the same
review inventory. Lists are sorted by rule and file for repeatable comparison.

**Not observed now is not fixed, migrated, or ready.** Code might have been
renamed, deleted, excluded, made unreadable or changed beyond these heuristic
rules. A changed coverage count prompts inspection; unchanged counts do not prove
that the same files were examined. Source files are not hash-pinned and a rescan
is not an atomic checkout snapshot. Both source trees and baseline must be trusted
and stable. A baseline digest identifies bytes, not their author or truth.

The new comparison requires valid coverage metadata and unique known-rule
findings from the old schema-1 scanner; malformed or duplicate JSON is rejected
with exit 2. An incomplete baseline is allowed but explicitly marked: it cannot
establish a full pre-migration inventory. Only current incompleteness returns 4;
normal exclusions remain disclosed rather than producing a new exit code.

**Behavior change:** NUL-containing candidate source (including UTF-16 files) now
returns existing exit code **4**, not 0, because it was not assessed as UTF-8.
This takes precedence over new-candidate exit 3. There is no new exit code.
Use UTF-8 source or explicitly review the missing coverage; do not suppress the
warning to make a migration gate green. No provider API or payment test was run.

This incremental correction was validated with 47 local Linux/Python 3.12 tests.
Windows/macOS and real merchant migrations were not tested for this increment;
historical CI evidence does not certify the new version. The HTML changes were
checked as escaped, script-free markup, not through a real browser in this pass.

## Compare assessed-file coverage without exporting new fingerprints

Optional **local private inventories** distinguish changed/unchanged bytes among
successfully assessed UTF-8 files, newly observed files, and files not observed
again. This is separate from candidate-finding differences. A legacy baseline
report has no inventory and cannot establish same-file coverage.

```sh
python -m migration_check scan project --scope-id shop --private-paths --coverage-state local-state-1.json --json first.json
python -m migration_check scan project --scope-id shop --private-paths --coverage-state local-state-2.json --coverage-baseline local-state-1.json --baseline first.json --json second.json
```

Keep both local-state files **outside `project` and private**, not in Git, logs or
shared reports. Each first state creates a random 256-bit key stored only inside
that state; a later state reuses the supplied prior state's key. It stores keyed
path/content digests but no paths or source bytes. Possession of the state also
reveals its key and allows dictionary guesses and cross-scan correlation: it is
not encrypted or anonymized. New states are exclusive 0600 files on POSIX; parent
directories must be trusted. Windows ACLs have not been verified. No old file
permissions change. Loss of a state means starting a new, incomparable chain;
missing files, mismatched scope/policy, malformed states and legacy reports
supplied as inventories fail closed before output. Version 2 states include a
canonical SHA-256 consistency digest over version, key, scope, policy, files and
completeness. A changed key or other field without a matching digest is rejected
before comparison or output. Old version 1 states without this digest are rejected;
start a new incomparable chain instead. Ordinary legacy finding baselines remain
supported separately. This detects accidental damage, not malicious forgery:
anyone can edit a state and recompute the digest. States are not authenticated
and do not prove provenance; the digest is private and is not exported in reports.

Only aggregate counts and completeness flags from this feature enter JSON/HTML;
its keys, path identifiers and content fingerprints are never exported there.
Without an explicit state the report says `not_comparable`. Existing
`--private-paths` is still only a **stable, guessable path pseudonym**, not
anonymity; the pre-existing explicit `--baseline` comparison still exports that
report's SHA-256. Review all reports before sharing. This new feature does not
retroactively remove historical report fields or identifiers.

A missing file may have moved, become unreadable/unsupported, been excluded or
fallen outside a budget. `not_observed_again` is never a deletion or repair
verdict. Binary/non-UTF-8 bytes are not counted as assessed source, even when the
older `files_read` counter includes those reads. Renames are new + not observed;
whitespace edits count as changes. A scan is not a filesystem snapshot. Inventory
hashing uses the exact bytes already assessed, never a second read. Unchanged
bytes do not establish runtime behavior or a successful migration.

At most 10,000 assessed records, 4 MiB state JSON; input acquisition is bounded
by the existing 16 MiB reader before the tighter state limit. No automatic
cleanup or multi-output transaction: a later I/O failure can leave an earlier
private state/report, so check exit status and use fresh paths. The new Linux
suite passes 64 tests (zero skips); no new hosted CI, provider sandbox or Windows
run is claimed. Prior inaccessible CI queries are not part of this validation.
