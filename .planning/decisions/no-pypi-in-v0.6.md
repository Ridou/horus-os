# Decision: no PyPI publishing in v0.6

**Status:** OUT for v0.6 (revisited no earlier than v0.7).

## Context

horus-os v0.6 ships the contribution-gate substrate: keyless OIDC artifact
signing (Phase 52), SBOM generation (Phase 53), and a user-facing
trust-chain verifier. The signing substrate makes PyPI Trusted Publishing
(PEP 807) technically feasible since both flows rely on the same GitHub
Actions OIDC issuer. The open question for v0.6 is whether to also wire
`pypa/gh-action-pypi-publish` into `.github/workflows/release.yml`.

The v0.6 milestone goal is contribution-gate readiness, not distribution
expansion. Phase 52 signs the wheel and sdist, attaches `.sigstore` bundles
to the published GitHub Release, and writes SLSA Build L2 attestations to
the GitHub attestation API. Users install with `pip install -e .` from a
clone or download the signed artifacts from the Release page.

## Decision criteria

1. horus-os does not currently publish to PyPI. No `your-project-name`
   PyPI project exists for this codebase; the name is not reserved.
2. There is no `PYPI_API_TOKEN` secret configured on the repository. PEP
   807 Trusted Publishing removes the need for that token, but reserving
   the project name and configuring the trusted publisher on the PyPI
   project page is a separate operational step that has not been done.
3. The v0.6 milestone goal is the contribution gate, not a distribution
   channel. Adding PyPI publishing widens the surface without serving the
   v0.6 goal.
4. Adding PEP 807 wiring in v0.6 would introduce a release-time failure
   mode (PyPI Trusted Publishing flow misconfiguration) that is unrelated
   to the contribution gate.

## Decision (final, until revisited)

**Decision (final, until revisited):** PyPI Trusted Publishing (PEP 807)
is OUT OF SCOPE for v0.6. The v0.6 distribution path is the signed
GitHub Release page only.

v0.7 (or a later milestone) may revisit when (a) the maintainer reserves
the PyPI project name, (b) configures Trusted Publishing on the PyPI
project page, and (c) decides to commit to PyPI as a distribution
channel. At that point the wiring is a single appended step in
`.github/workflows/release.yml` of the form:

```yaml
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@<sha>  # vN.M.P
```

with the existing per-job `id-token: write` permission on the
`sign-and-attest` job already in place per Phase 52 D-02.

## References

- PEP 807: https://peps.python.org/pep-0807/
- `pypa/gh-action-pypi-publish`: https://github.com/pypa/gh-action-pypi-publish
- Phase 52 CONTEXT.md D-09: couples this decision file with the
  `.planning/PROJECT.md` key-decisions table append (single commit).
- Phase 52 RESEARCH.md Standard Stack: the OIDC issuer that v0.7+ would
  reuse if PEP 807 is wired.
- `.planning/research/PITFALLS.md` Pitfall 9: PyPI Trusted Publishing
  sequencing rationale (the absence of `PYPI_API_TOKEN` IS the v0.6
  posture; a leaked token would invalidate the trust story).
