# Decision: keyless OIDC signing via sigstore

**Status:** IN for v0.6 (Phase 52 substrate); reviewed at v0.7 if sigstore project changes its trust model.

## Context

Artifact signing protects against tampering between build and consumption. Two broad models:

1. **Long-lived key signing** (GPG, PGP): the project owns a private key, signs releases with it, distributes the public key. Compromise of the private key compromises every artifact ever signed by it. Key rotation requires re-establishing trust with every downstream consumer.
2. **Keyless OIDC signing** (sigstore): each signing event mints a short-lived (10-minute) certificate bound to the OIDC identity that triggered the build (GitHub Actions workflow URL plus ref). The certificate plus signature plus the transparency log entry are the signed artifact; no long-lived secret exists.

For a solo-maintained project, the operational burden of long-lived key management (HSM, rotation, escrow, revocation) is disproportionate to the project's threat model. Keyless OIDC removes that burden entirely.

## Decision (final, until revisited)

horus-os v0.6 wheels and sdists are signed via sigstore-python in a single GitHub Actions job whose identity is the workflow file path plus the release tag. Verification uses workflow-scoped EXACT-match identity (no wildcards, no regex, mandatory --cert-oidc-issuer).

The `scripts/verify_release.py` user-facing verifier hardcodes EXPECTED_IDENTITY_TEMPLATE and EXPECTED_ISSUER as module-level constants with a module-import-time assert. This is the Phase 52 substrate.

SBOMs (Phase 53) sign the same way in the same job.

## Trade-offs

- Pro: zero long-lived signing key management.
- Pro: every signature is auditable in the public Rekor transparency log; tampering is detectable.
- Pro: matches industry direction (PyPI Trusted Publishing PEP 807, npm, Homebrew, container registries).
- Con: requires GitHub Actions; signing from a maintainer workstation is possible but uncommon. For tag signing we use gitsign separately.
- Con: identity contract is brittle. Renaming `.github/workflows/release.yml` or restructuring the repo path invalidates every prior signature's identity match. Mitigated by the workflow-scoped EXACT-match identity contract and the module-import-time assert that defends EXPECTED_IDENTITY_TEMPLATE shape.

## When to revisit

- If sigstore upstream changes its trust root (the Fulcio CA) in a way that breaks backwards-verification of past releases.
- If GitHub Actions OIDC issuer URL changes (`https://token.actions.githubusercontent.com`).
- If horus-os moves to a self-hosted runner where the OIDC issuer is not GitHub's.

Revisit on upstream signal, not on schedule.

## See also

- `scripts/verify_release.py` (the user-facing verifier).
- `.github/workflows/release.yml` (Phase 52 + 53 signing pipeline).
- `.planning/decisions/sbom-cyclonedx.md` (SBOMs sign the same way).
- `.planning/decisions/no-pypi-in-v0.6.md` (PyPI Trusted Publishing is the same OIDC flow; deferred to v0.7).
