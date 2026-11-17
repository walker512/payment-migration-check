# Real local comparison, deliberately modest claims

Run `python benchmarks/compare.py > /tmp/comparison.json` from the repository root with ripgrep installed. It invokes the actual `rg` executable and the scanner CLI as separate subprocesses (using `sys.executable -m migration_check`), then emits every command, first-match location, fixture hash and confusion matrix. The checked-in results were produced with **ripgrep 15.2.0**. Runtime dependency: Python; benchmark-only external dependency: ripgrep. No downloads or network requests.

The scanner CLI response is parsed and checked: exit code 0, 15 nonempty/actionable review tasks, 12 files in coverage, manual-review verdict, no exported source excerpts and no synthetic private sentinel in either stdout or stderr. A failed check stops the benchmark rather than recording success. These are programmatic deliverable checks, not human usability testing.

## Task and ground truth

Discover payment integration **files** in a 12-file, synthetic multi-language source tree. Eight files contain intended integration points, four do not. `ground-truth.json` contains the author-assigned labels and categories, independent of tool results. This is an adversarial regression corpus, **not representative merchant data or measured production accuracy**. Each file has one intended category; confusion metrics are file-level. Category-and-line parity is separately checked for the same-rule baseline.

| Executed configuration | TP | Missed (FN) | False positives | Correct negatives |
|---|---:|---:|---:|---:|
| Simple `rg -n -i lemonsqueezy` | 5 | 3 | 1 | 3 |
| `rg` with the scanner's six regexes and `--only-matching` | 7 | 1 | 2 | 2 |
| Payment Migration Check | 7 | 1 | 2 | 2 |
| Scanner's original regexes before Python import fix | 6 | 2 | 2 | 2 |

The original scanner missed `from lemonsqueezy import Client`; the keyword baseline exposed this shortcoming. We added that import branch and a regression test, then reran both the original and updated rule sets. The tool still misses a runtime-assembled URL and still flags two unrelated identifiers. We retain and disclose these counterexamples rather than remove them from the corpus.

## What this establishes, and what it does not

- Compared to a **single provider-name grep**, domain-aware rules locate two extra positive files but add one extra false positive. This is a recall/precision tradeoff, not unconditional superiority.
- Given exactly the same rules, **ripgrep and this scanner tie on detection**. The first matching file/line/category triples also match. There is no evidence our regex engine is better or faster.
- Plain grep prints a synthetic private value located on a matching line. This scanner does not. **Configured ripgrep `--only-matching` does not either**; it would be unfair to call ripgrep inherently unsafe.
- This tool's concrete advantage for this particular task is producing a migration-specific review deliverable: categorized locations, unknown/coverage metadata, 15 explanatory review tasks, and optional HTML from one invocation. Raw ripgrep output is not that deliverable. A programmer can build equivalent postprocessing and policy logic around it.
- The comparison script uses six rg invocations for category attribution. They are not six human clicks; a single combined expression plus classification could replace them. We made **no timing, saved-hours or user-effort experiment**. Human review remains necessary for all configurations.

## Competitor strengths kept visible

ripgrep is the stronger general-purpose source search tool: flexible queries, mature ignore handling, many encodings and broad file coverage. Our intentionally bounded extension/encoding rules and simplistic filename exclusions can miss relevant code. Use ripgrep for investigation outside the scanner's coverage and to verify ambiguous matches. Neither a local report nor grep validates actual billing behavior.

The official Migration Hub is a different category and was not available at the policy snapshot; this comparison does not simulate it. dodo-migrate transfers provider records; this experiment makes no claim about that workflow.
