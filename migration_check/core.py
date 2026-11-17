"""Bounded, read-only source discovery; evidence is identifiers, never source excerpts."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SOURCE = "https://docs.lemonsqueezy.com/migration"
VERIFIED = "2026-11-17"
MAX_FILE = 512 * 1024
MAX_FILES = 10000
MAX_BYTES = 32 * 1024 * 1024
EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rs", ".rb", ".php", ".java", ".cs", ".vue", ".svelte", ".html", ".json", ".yaml", ".yml", ".toml"}
EXCLUDED = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "vendor", "dist", "build", "coverage", "__pycache__", ".next", ".idea", ".vscode", "reports", "migration-reports"}
# Every returned token is a static rule label, not a user-controlled regex match.
RULES = (
    ("sdk", "SDK / API setup", r"\b(?:from|import)\s+lemonsqueezy\b|@lemonsqueezy/lemonsqueezy\.js|lemonSqueezySetup|api\.lemonsqueezy\.com/v1"),
    ("checkout", "Checkout integration", r"lemonsqueezy\.com/(?:checkout|buy)|LemonSqueezy\.(?:Setup|Url|Refresh)|createCheckout|lemon\.js"),
    ("webhook", "Webhook lifecycle", r"X-Signature|x-signature|order_created|subscription_(?:created|updated|cancelled|resumed|expired|payment_success|payment_failed|payment_recovered|payment_refunded|paused|unpaused)"),
    ("license", "License API / fulfillment", r"api\.lemonsqueezy\.com/v1/licenses|(?:activate|validate|deactivate)License|license_key_created|license_key_updated"),
    ("catalog", "Product / variant mapping", r"LEMON(?:SQUEEZY|_SQUEEZY)?_(?:PRODUCT|VARIANT|STORE)_ID|(?:get|list)(?:Products|Variants)|variant_id"),
    ("affiliate", "Affiliate integration candidate", r"lemonsqueezy\.com/affiliates|lemonSqueezyAffiliate|affiliate_tracking"),
)
COMPILED = [(key, label, re.compile(pattern, re.I)) for key, label, pattern in RULES]
RULESET_FINGERPRINT = hashlib.sha256(json.dumps({"rules": RULES, "extensions": sorted(EXTENSIONS), "excluded": sorted(EXCLUDED), "limits": [MAX_FILE, MAX_FILES, MAX_BYTES], "filter_version": 1}, sort_keys=True).encode()).hexdigest()
FEATURES = ("paypal_subscriptions", "licenses", "file_delivery", "affiliates", "storefront", "india_issued_cards", "cash_app_subscriptions")
PROFILE_KEYS = set(FEATURES) | {"managed_payments_eligibility"}


def load_profile(path: Path | None) -> dict:
    if path is None:
        return {key: "unknown" for key in PROFILE_KEYS}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("Profile must be a regular non-symlink JSON file under 16 KiB")
    with path.open(encoding="utf-8") as stream:
        profile = json.load(stream)
    if not isinstance(profile, dict) or set(profile) - PROFILE_KEYS:
        raise ValueError("Profile must contain only documented feature keys; no customer data")
    for key, value in profile.items():
        allowed = ("confirmed", "ineligible", "unknown") if key == "managed_payments_eligibility" else ("yes", "no", "unknown")
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"Invalid value for {key}; expected one of {', '.join(allowed)}")
    return {key: profile.get(key, "unknown") for key in sorted(PROFILE_KEYS)}


def is_excluded(name: str) -> bool:
    low = name.lower()
    return low.startswith(".") or low in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "composer.lock"} or any(word in low for word in ("secret", "credential", "password", "token", "private_key"))


def scan(root: Path, *, max_files: int = MAX_FILES, max_bytes: int = MAX_BYTES) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Source must be a directory, not a symlink")
    root = root.resolve()
    findings, warnings = [], []
    counts = {"files_read": 0, "bytes_read": 0, "excluded_entries": 0, "unsupported_files": 0, "symlinks_skipped": 0, "unreadable_files": 0, "oversize_files": 0, "binary_files": 0, "non_utf8_files": 0}
    truncated = False
    # Paths are kept local; --private-paths hides them for externally shareable reports.
    def onerror(error):
        counts["unreadable_files"] += 1
    for base, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        kept = []
        for name in sorted(dirs):
            path = Path(base) / name
            if path.is_symlink():
                counts["symlinks_skipped"] += 1
            elif name in EXCLUDED or name.startswith("."):
                counts["excluded_entries"] += 1
            else:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(files):
            path = Path(base) / name
            if path.is_symlink():
                counts["symlinks_skipped"] += 1
                continue
            if is_excluded(name):
                counts["excluded_entries"] += 1
                continue
            if path.suffix.lower() not in EXTENSIONS:
                counts["unsupported_files"] += 1
                continue
            try:
                # Do not open FIFOs, sockets or device files. O_NOFOLLOW closes the
                # ordinary final-component symlink race on platforms supporting it.
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    counts["excluded_entries"] += 1
                    continue
                if info.st_size > MAX_FILE:
                    counts["oversize_files"] += 1
                    continue
                if counts["files_read"] >= max_files or counts["bytes_read"] + info.st_size > max_bytes:
                    truncated = True
                    break
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                fd = os.open(path, flags)
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        counts["excluded_entries"] += 1
                        continue
                    raw = stream.read(MAX_FILE + 1)
                if len(raw) > MAX_FILE:
                    counts["oversize_files"] += 1
                    continue
                if counts["bytes_read"] + len(raw) > max_bytes:
                    truncated = True
                    break
                counts["files_read"] += 1
                counts["bytes_read"] += len(raw)
                if b"\x00" in raw:
                    counts["binary_files"] += 1
                    continue
                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    counts["non_utf8_files"] += 1
                    continue
            except OSError:
                counts["unreadable_files"] += 1
                continue
            relative = path.relative_to(root).as_posix()
            # One finding per rule per file, with first line, so a large generated
            # source cannot make report growth proportional to token repetitions.
            for key, label, pattern in COMPILED:
                match = pattern.search(content)
                if match:
                    findings.append({"rule": key, "label": label, "file": relative, "line": content.count("\n", 0, match.start()) + 1, "confidence": "candidate", "evidence": "static identifier match; inspect locally"})
        if truncated:
            break
    if truncated:
        warnings.append("Scan budget exhausted; unvisited source is not assessed")
    for key in ("unreadable_files", "oversize_files", "binary_files", "non_utf8_files", "symlinks_skipped"):
        if counts[key]:
            warnings.append(f"{key}: {counts[key]}")
    warnings.append("Static matches are candidates, not proof of active payment usage. Comments and unrelated identifiers may match. Dynamic imports, other languages, ignored files and remote settings may be missed.")
    return {"findings": findings, "coverage": counts, "truncated": truncated, "warnings": warnings}


TASKS = {
    "checkout": ("Replace checkout entry points", "Inventory overlays, payment links and return URLs. Test success, cancel and abandoned checkout against your chosen provider sandbox."),
    "sdk": ("Replace provider API setup", "Map SDK calls and environment variable names. Keep credentials outside source and use separate sandbox credentials. Do not remove the old integration until the cutover plan is approved."),
    "webhook": ("Rebuild and validate webhook handling", "Map event payloads and entitlement transitions. Verify signatures, reject tampering, deduplicate retries and reconcile out-of-order events. Provider-specific test events are still required."),
    "license": ("Preserve license validation and fulfillment", "Plan existing-key continuity, activation limits, revocation and offline behavior. Managed Payments does not issue or deliver license keys for you."),
    "catalog": ("Reconcile product, variant and subscription identifiers", "Create an explicit old-to-new mapping in a secure local workspace. Verify prices, currency, discounts, trial periods and existing subscription state."),
    "affiliate": ("Replace affiliate attribution", "Check attribution, commission rules, payout obligations and existing links. Managed Payments does not include an affiliate platform."),
}


def build_report(result: dict, profile: dict, private_paths: bool = False) -> dict:
    result = json.loads(json.dumps(result))
    if private_paths:
        for finding in result["findings"]:
            finding["file"] = "file-" + hashlib.sha256(finding["file"].encode()).hexdigest()[:12]
    by_rule = {}
    for finding in result["findings"]:
        by_rule.setdefault(finding["rule"], []).append({"file": finding["file"], "line": finding["line"]})
    tasks = []
    for rule, (title, action) in TASKS.items():
        tasks.append({"id": rule, "priority": "P1", "status": "review" if rule in by_rule else "unverified", "title": title, "action": action, "evidence": by_rule.get(rule, []), "basis": "local source candidates" if rule in by_rule else "not found in scanned source; not proof of absence"})
    eligibility = profile["managed_payments_eligibility"]
    tasks.insert(0, {"id": "eligibility", "priority": "P0", "status": "blocked" if eligibility == "ineligible" else "review" if eligibility == "confirmed" else "unverified", "title": "Confirm destination eligibility with provider", "action": "Use the official eligibility guidance and your store-specific migration notice. This tool cannot determine legal, country or product eligibility. 'confirmed' is your assertion, not independent verification.", "evidence": [], "basis": "manual input: " + eligibility})
    feature_actions = {
        "paypal_subscriptions": "PayPal subscriptions cannot directly transfer to Managed Payments. Plan customer opt-in to a new supported payment method; do not silently cancel or recreate billing.",
        "licenses": "Provide an independent license issuance and validation service, preserving existing customer entitlements.",
        "file_delivery": "Provide secure file/download delivery and confirm access for existing buyers.",
        "affiliates": "Arrange an independent affiliate platform and reconcile outstanding commissions.",
        "storefront": "Provide a separate storefront and update existing purchase links.",
        "india_issued_cards": "Plan customer reauthorization for subscriptions using India-issued cards with the provider.",
        "cash_app_subscriptions": "Check destination restrictions: the official guide describes Cash App Pay migration to Managed Payments, not other providers.",
    }
    for feature in FEATURES:
        answer = profile[feature]
        tasks.append({"id": feature, "priority": "P0" if feature == "paypal_subscriptions" else "P1", "status": "review" if answer == "yes" else "declared_not_used" if answer == "no" else "unverified", "title": feature.replace("_", " ").capitalize(), "action": feature_actions[feature], "evidence": [], "basis": "manual input: " + answer})
    tasks.append({"id": "cutover", "priority": "P0", "status": "unverified", "title": "Rehearse and reconcile before cutover", "action": "Export necessary business records securely. Test sandbox purchase, refund, failed renewal, cancellation, duplicate delivery and reconciliation. Plan customer notices, rollback and parallel observation. Do not treat a passing scanner as permission to go live.", "evidence": [], "basis": "manual operational verification required"})
    today = dt.date.today()
    age = (today - dt.date.fromisoformat(VERIFIED)).days
    return {"schema_version": 1, "tool_version": "0.1.0", "ruleset_fingerprint": RULESET_FINGERPRINT, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "verdict": "MANUAL_REVIEW_REQUIRED", "profile": profile, "policy": {"verified_on": VERIFIED, "source": SOURCE, "needs_recheck": age > 14 or age < 0, "note": "Dated documentation snapshot. Recheck official terms, eligibility and availability before action; no live provider query was made."}, "privacy": {"source_excerpts_exported": False, "paths_pseudonymized": private_paths, "note": "Paths may contain private information unless --private-paths is used. Review all reports before sharing. No network calls or provider mutations."}, **result, "tasks": tasks}
