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
- `4`: incomplete assessment due to budget, unreadable/oversize or non-UTF-8 source; this takes precedence over `3`

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
