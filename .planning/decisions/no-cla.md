# Decision: no Contributor License Agreement

**Status:** OUT for v0.6 and beyond unless a downstream change forces a revisit.

## Context

A Contributor License Agreement (CLA) is a separate document each contributor signs that grants the project owner additional rights over their contribution beyond what the project's open-source license already grants. Common shapes include the Apache CLA (asserts copyright ownership and grants a perpetual license to the project) and Developer Certificate of Origin DCO (contributor asserts they have the right to license the change).

Adding a CLA gate raises friction for first-time contributors and introduces a legal process the maintainer does not have capacity to enforce on a solo project.

## Decision (final, until revisited)

horus-os does NOT require a CLA. Contributions land under the project's outgoing license (Apache 2.0) on the strength of the contributor's PR action: opening a PR against this repo asserts that the contributor has the right to license the change under Apache 2.0. This is the "inbound equals outbound" pattern documented widely in open-source.

The PR template includes a checkbox that states "I have the right to license this change under Apache 2.0" as a reminder. No external signing tool, no automated CLA bot, no separate document.

## Trade-offs

- Pro: zero friction for first-time contributors; no third-party CLA service to integrate.
- Pro: Apache 2.0 already includes a patent grant in section 3.
- Pro: matches the practice of major projects like Linux kernel (DCO), Python (CLA-free since 2019), pip, and many GitHub Actions ecosystem projects.
- Con: in a hypothetical relicensing scenario, getting all contributors to sign-off on a new license would be harder. We do not plan to relicense; Apache 2.0 is intentional.
- Con: if a contributor later disputes a contribution, we rely on the PR action audit trail rather than a signed document. Acceptable risk for a project of this scale.

## When to revisit

- If horus-os is donated to a foundation (CNCF, ASF, Linux Foundation) that requires a CLA.
- If a contributor's change creates material risk that needs an extra grant-of-rights paper trail.
- If our outgoing license changes from Apache 2.0 to something more permissive (MIT, BSD) or more restrictive (AGPL).

None of these are on the roadmap. Revisit at the donation or relicensing trigger, not on a schedule.
