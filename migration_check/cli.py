from __future__ import annotations
import argparse
import html
import json
import os
from pathlib import Path
import sys
from . import __version__
from .core import build_report, load_profile, scan
from .comparison import compare, incomplete
from .coverage_state import Ledger, load as load_coverage


def render_html(report: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    tasks = []
    for task in report["tasks"]:
        links = " · ".join(esc(f'{item["file"]}:{item["line"]}') for item in task["evidence"])
        tasks.append(f'<article><div class="tag">{esc(task["priority"])} · {esc(task["status"])}</div><h3>{esc(task["title"])}</h3><p>{esc(task["action"])}</p><small>{esc(task["basis"])}</small><pre>{links}</pre></article>')
    rows = "".join(f'<tr><td>{esc(f["label"])}</td><td><code>{esc(f["file"])}</code></td><td>{f["line"]}</td><td>Candidate</td></tr>' for f in report["findings"])
    rows = rows or '<tr><td colspan="4">No candidate identifiers found. This is not proof of no integration.</td></tr>'
    warnings = "".join(f'<li>{esc(w)}</li>' for w in report["warnings"])
    coverage = " · ".join(f'{esc(k.replace("_", " "))}: {v}' for k, v in report["coverage"].items())
    comparison = report.get("baseline_comparison")
    changes = ""
    if comparison:
        sections = []
        for key, title in (("new", "New candidates"), ("retained", "Still observed"), ("not_observed_now", "Not observed now (not resolved)")):
            items = "".join(f'<li>{esc(f["label"])} · {esc(f["file"])}:{esc(f["line"])}</li>' for f in comparison[key])
            sections.append(f'<h3>{title}: {len(comparison[key])}</h3><ul>{items}</ul>')
        coverage_rows = "".join(f'<li>{esc(k)}: {v["before"]} → {v["after"]} (delta {v["delta"]:+d})</li>' for k, v in comparison["coverage_changes"].items())
        changes = f'<h2>Rescan review</h2><div class="notice">{esc(comparison["note"])}<br>Baseline incomplete: {comparison["baseline_incomplete"]}; current incomplete: {comparison["current_incomplete"]}</div>{"".join(sections)}<h3>Coverage changes</h3><ul>{coverage_rows}</ul>'
    coverage_summary = report.get('scan_coverage_comparison')
    if coverage_summary:
        changes += '<h2>Assessed-file coverage</h2><pre>' + esc(json.dumps(coverage_summary, sort_keys=True, indent=2)) + '</pre>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Payment Migration Check</title><style>
:root{color-scheme:dark}body{font:16px/1.65 system-ui,sans-serif;background:#101923;color:#dce7ef;max-width:1080px;margin:48px auto;padding:0 24px}h1{font-size:clamp(2rem,6vw,3.2rem);line-height:1.1;color:#fff}h2{margin-top:40px}a{color:#77dec5}header p{max-width:750px}.eyebrow,.tag{color:#77dec5;font:12px/1.6 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.08em}.notice{border-left:4px solid #edbe6a;padding:16px 22px;background:#252a2f;border-radius:4px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(290px,100%),1fr));gap:16px}article{background:#192531;border:1px solid #33424f;padding:24px;border-radius:12px}h3{margin:10px 0}small{color:#aebfcb}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#9ed5c9}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:10px;border-bottom:1px solid #33424f;overflow-wrap:anywhere}code{font-size:12px}.table{overflow:auto}footer{margin-top:40px;color:#aebfcb}@media print{body{background:white;color:black}article{break-inside:avoid;background:white;color:black}h1,h2,h3{color:black}}
</style><header><div class="eyebrow">walker512 / offline readiness evidence</div><h1>Know what still needs moving.</h1><p>Local integration discovery and a human-review checklist for leaving Lemon Squeezy. No credentials. No provider writes. No automatic eligibility verdict.</p></header>''' + f'<div class="notice"><strong>Manual review required.</strong> No scan result certifies migration readiness. Policy snapshot: {esc(report["policy"]["verified_on"])}. {"RECHECK REQUIRED: snapshot is outside its 14-day freshness window." if report["policy"]["needs_recheck"] else "Recheck the official guide before acting."}<br><a href="{esc(report["policy"]["source"])}" rel="noreferrer">Official migration guide</a></div><h2>Evidence coverage</h2><p>{coverage}</p><ul>{warnings}</ul><div class="table"><table><thead><tr><th>Integration</th><th>File</th><th>Line</th><th>Meaning</th></tr></thead><tbody>{rows}</tbody></table></div>{changes}<h2>Migration work queue</h2><div class="grid">{"".join(tasks)}</div><footer>{esc(report["privacy"]["note"])}<br>Generated {esc(report["generated_at"])} · v{esc(report["tool_version"])}</footer></html>'


def write_new(path: Path, text: str) -> None:
    # Exclusive creation refuses existing files AND symlinks; no implicit overwrite.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)


def identity(finding: dict) -> tuple:
    # Line movement doesn't invent a new integration.
    return finding["rule"], finding["file"]


def compare_baseline(report: dict, path: Path) -> list:
    # Keep the original helper's new-findings return contract.
    return compare(report, path)["new"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline Lemon Squeezy integration discovery; never a go-live approval.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("scan", help="Read local source and write a readiness report")
    run.add_argument("source", type=Path)
    run.add_argument("--profile", type=Path, help="Optional documented yes/no/unknown feature JSON")
    run.add_argument("--json", type=Path, help="New JSON output path; stdout if omitted")
    run.add_argument("--html", type=Path, help="New self-contained HTML output path")
    run.add_argument("--private-paths", action="store_true", help="Replace relative filenames with stable pseudonyms before export")
    run.add_argument("--scope-id", help="Public non-sensitive label for this repository and relative scan root, e.g. shop/src; required for baseline comparison")
    run.add_argument("--coverage-state", type=Path, help="New PRIVATE local keyed scan inventory; never share this file")
    run.add_argument("--coverage-baseline", type=Path, help="Previous PRIVATE coverage inventory, not a legacy report; requires --coverage-state")
    run.add_argument("--baseline", type=Path, help="Compare findings against a previous JSON report")
    run.add_argument("--fail-on-new", action="store_true", help="With --baseline: exit 3 if a new (rule,file) candidate appears")
    args = parser.parse_args(argv)
    if args.baseline is not None and not args.scope_id:
        parser.error("--baseline requires --scope-id; use the same label and same relative scan root as the baseline")
    if args.fail_on_new and args.baseline is None:
        parser.error("--fail-on-new requires --baseline")
    if args.coverage_baseline is not None and args.coverage_state is None:
        parser.error("--coverage-baseline requires --coverage-state")
    if args.coverage_state is not None and not args.scope_id:
        parser.error("--coverage-state requires --scope-id")
    try:
        if args.scope_id is not None:
            import re
            if not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", args.scope_id):
                raise ValueError("Scope ID must be 1-100 ASCII letters, numbers, dots, slashes, underscores or hyphens")
        outputs = [path for path in (args.json, args.html, args.coverage_state) if path is not None]
        if len({p.absolute() for p in outputs}) != len(outputs):
            raise ValueError("JSON and HTML output paths must differ")
        if any(path.exists() or path.is_symlink() for path in outputs):
            raise ValueError("Output already exists; choose a new path (overwrites are intentionally disabled)")
        ledger = None
        if args.coverage_state is not None:
            # Never let inventory files become source inputs on a later scan.
            source_root = args.source.resolve()
            for path in (args.coverage_state, args.coverage_baseline):
                if path is not None and path.resolve().is_relative_to(source_root):
                    raise ValueError("Keep private coverage states outside the scan root")
            ledger = Ledger(args.scope_id, load_coverage(args.coverage_baseline) if args.coverage_baseline else None)
        profile = load_profile(args.profile)
        report = build_report(scan(args.source, observed=ledger.observe if ledger else None), profile, args.private_paths)
        if ledger is not None:
            ledger.state['incomplete'] = bool(incomplete(report))
        report['scan_coverage_comparison'] = ledger.summary() if ledger else {
            'status':'not_comparable', 'reason':'No local coverage inventory requested; counts and legacy baseline findings do not establish same-file coverage.'}
        state_text = ledger.serialized() if ledger else None
        report["scope_id"] = args.scope_id
        if args.baseline is not None:
            report["baseline_comparison"] = compare(report, args.baseline)
            report["new_findings"] = report["baseline_comparison"]["new"]
        serialized = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
        if args.coverage_state is not None:
            write_new(args.coverage_state, state_text)
        if args.json:
            write_new(args.json, serialized)
        else:
            print(serialized, end="")
        if args.html:
            write_new(args.html, render_html(report))
        print(f'Scanned {report["coverage"]["files_read"]} files; {len(report["findings"])} candidates. Manual review required.', file=sys.stderr)
        if incomplete(report):
            return 4
        if args.fail_on_new and report.get("new_findings"):
            return 3
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        # Do not echo parser contents or user-supplied paths/secrets in exception text.
        if isinstance(exc, (json.JSONDecodeError, UnicodeError, OSError, TypeError, KeyError, RecursionError)):
            print("Error: input/output could not be processed safely; check file type, JSON schema and permissions.", file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2
