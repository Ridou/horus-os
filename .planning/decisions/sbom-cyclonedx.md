# Decision: CycloneDX 1.6 JSON for SBOMs

**Status:** IN for v0.6 (Phase 53 substrate); reviewed if CycloneDX or SPDX ecosystem maturity shifts.

## Context

A Software Bill of Materials (SBOM) is a machine-readable list of every component in a released artifact. Two major formats compete:

1. **CycloneDX** (OWASP project; XML, JSON, Protocol Buffers): tooling maturity is high for Python via `cyclonedx-bom` (the `cyclonedx-py environment <venv>` command introspects an installed venv and emits a CycloneDX document directly).
2. **SPDX** (Linux Foundation; tag-value, RDF, JSON): broader adoption in enterprise compliance contexts but the Python tooling lags CycloneDX for the "introspect a fresh venv" use case.

For a Python project shipping wheels and sdists, the cyclonedx-bom toolchain is the lower-friction path to a verifiable, FRESH-venv-aligned SBOM.

## Decision (final, until revisited)

horus-os v0.6 generates two SBOMs per release in CycloneDX 1.6 JSON format:
- `dist/horus_os-clean.cdx.json`: built against a FRESH `pip install <wheel>` venv (no extras).
- `dist/horus_os-dev-otel.cdx.json`: built against a FRESH `pip install <wheel>[dev,otel]` venv.

The FRESH-venv rule is load-bearing: SBOMs generated from `pip freeze` of the maintainer's dev environment would reflect editor extras and stale pins that do not match what users actually install. The release.yml pipeline creates throwaway venvs via `python -m venv` then runs `cyclonedx-py environment` against the throwaway venv's Python interpreter.

Schema version 1.6 is explicit (`--schema-version 1.6`) so a future cyclonedx-bom 8.x default change does not silently shift the SBOM contract.

Both SBOMs are signed via sigstore in the same release job that signs the wheel and sdist (see `.planning/decisions/sigstore-keyless.md`). Each SBOM is attested via `actions/attest-sbom` so the GitHub attestations binding shows the SBOM-to-wheel relationship.

## Trade-offs

- Pro: cyclonedx-py environment is well-maintained and natively understands Python venv internals (entry points, package metadata).
- Pro: JSON output is line-diffable and grep-friendly for the release-gate's eventual stale-SBOM check (deferred to Phase 57).
- Pro: schema 1.6 is the current stable; 1.5 lacks the lifecycle metadata 1.6 adds.
- Con: SPDX has wider enterprise adoption; downstream consumers who only accept SPDX must convert via a tool like `cyclonedx-cli convert`.
- Con: cyclonedx-bom is itself a Python dep; we install it inside release.yml (CI-only) and never add it to pyproject.toml runtime or dev extras.

## When to revisit

- If a downstream consumer (PyPI, GitHub Advanced Security, enterprise integrator) requires SPDX and the conversion path is insufficient.
- If CycloneDX 2.0 introduces breaking changes that warrant moving away from the 1.x line.
- If a competing Python-native SBOM tool ships with materially better venv introspection.

Revisit on consumer or upstream signal, not on schedule.

## See also

- `.github/workflows/release.yml` (Phase 53 SBOM generation + sigstore signing + attest-sbom).
- `scripts/verify_release.py` `check_sbom_signature` (Phase 53 user-facing verifier).
- `.planning/decisions/sigstore-keyless.md` (the signing layer underneath).
