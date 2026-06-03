# pip-audit fix-tracking directory

Per-CVE tracking documents for vulnerabilities ignored in
`.github/pip-audit-ignore.txt`.

## Convention

One Markdown file per ignored CVE / GHSA / PYSEC ID, named after the
ID: `CVE-YYYY-NNNNN.md`, `GHSA-xxxx-yyyy-zzzz.md`, or
`PYSEC-YYYY-NNNN.md`.

Each tracking file documents:

1. **Vulnerability summary**: what the CVE is, what it impacts.
2. **Why we cannot fix it**: typically a transitive dependency
   awaiting an upstream patch. Name the transitive dep and the
   direct parent.
3. **Upstream tracker**: URL to the upstream issue / PR / advisory
   that, when resolved, will let us remove the ignore.
4. **Birth date**: YYYY-MM-DD when we first added the ignore
   (mirrors the `# YYYY-MM-DD: <reason>` comment in
   pip-audit-ignore.txt).
5. **Expiry condition**: the upstream event that triggers a
   follow-up to remove the ignore (e.g., "urllib3 1.27 released
   with the patched code path").

## Lifecycle

1. pip-audit flags a CVE that we cannot fix immediately.
2. Maintainer creates `<ID>.md` here documenting items 1 to 5 above.
3. Maintainer adds the CVE ID to `.github/pip-audit-ignore.txt`
   with a `# YYYY-MM-DD: <reason>` comment line immediately above.
4. The release-gate `local-pip-audit-clean` check (Phase 57) parses
   the ignore-list and rejects entries lacking the dated comment.
5. When the upstream fix lands, maintainer removes both the
   ignore-list entry AND deletes the tracking file (or moves to a
   `resolved/` subdirectory if historical archival is wanted).

## At v0.6.0 launch

This directory contains only this README. The discipline is wired
so the next real CVE has the tooling.
