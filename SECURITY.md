# Security and privacy model

## Trust boundary

Run against a **stable local checkout you control**, under an unprivileged account. Do not run as administrator/root. This is not a sandbox for an adversary who can concurrently replace directories while the scanner runs. It skips symlink files/directories, does not follow them during normal traversal and uses O_NOFOLLOW where available, but parent-directory replacement races are not fully prevented. If inspecting hostile repos, copy them into a sandbox first and remove write access from other processes.

No network, telemetry, subprocess execution, provider SDK or AI call is used at runtime. It does not execute repository code. Tests assert no networking imports; inspect source yourself for stronger assurance.

## Input controls

- Only documented source/config extensions, UTF-8, up to 512 KiB/file, 10,000 read files and 32 MiB total bytes.
- Hidden paths, dependency/build folders, lockfiles and filenames containing common credential words are excluded. This is a convenience filter, **not** a secret scanner.
- Non-regular files, binaries and symlinks are skipped. Coverage counts and incomplete statuses are exposed.
- Profile is an allowlisted JSON object under 16 KiB; contains only feature choices. Baseline is a bounded prior JSON report. It must be trusted and refer to the same repository-relative scan root. Matching scope IDs are operator assertions, not repository authentication. Rule/filter/limit fingerprints must match; labels alone cannot prove a trustworthy baseline.
- On a huge directory tree, directory enumeration itself can still consume resources. Do not scan a filesystem root or concurrently changing hostile checkout.

## Outputs

No raw source excerpt or matched value is exported. Relative filenames and line numbers **are** exported by default and filenames may contain personal data. `--private-paths` replaces paths with stable hash prefixes, useful for comparison but **not cryptographic anonymization**: guessed filenames can be matched. Review reports manually before publication.

HTML escapes user-controlled strings, has no script/resources and includes a restrictive CSP. JSON escapes control/non-ASCII characters. Output files are created exclusively (no overwrite) with owner-only mode on POSIX; on Windows ACLs control access. An output parent directory must be trusted. A two-output run may leave the first file if the second fails; this is reported with exit 2, not success.

## Reporting vulnerabilities

Do not publish secrets, real customer samples or exploit details in a public issue. Until private reporting is configured on the published repository, open an issue containing only a request for a private reporting channel. Use synthetic evidence for public bug reports. Never send card data, credentials or merchant exports to maintainers.

## Rescan comparison

Baseline reading uses an opened regular-file descriptor, an identity check and a
16 MiB plus one-byte bounded read; final symlinks are refused where O_NOFOLLOW is
available. Duplicate JSON, malformed used fields and duplicate findings fail
closed. Only allowlisted finding fields are re-exported; arbitrary baseline labels
or extra excerpts are not copied. Private-path baselines must use the scanner's
pseudonym syntax. These checks do not authenticate a baseline or eliminate
concurrent in-place changes, parent-directory races, or user-supplied private
filenames. Scope labels and hashes are not signatures. Keep inputs stable.
