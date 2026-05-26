# Plugin Security

This doc states the security model for the v0.5 plugin system. It exists because plugin authors and `horus-os` users both need a single canonical statement of what the capability grant prompt actually buys, and a single canonical statement of what it does NOT defend against. Pitfall 1 (closed-enum capability catalog) and requirement REL-12 (the literal threat-model sentence) drive the shape of this file.

Read this document before granting capabilities to a plugin you have not authored yourself. The capability prompt the installer prints at install time also points back here.

## Threat model

In `horus-os` v0.5, plugins execute in the horus-os Python process. They share the file descriptors, the environment variables, the loaded modules, and the same access to `~/.horus-os/secrets.json` that `horus-os` itself holds. There is no OS-level sandbox between a plugin and the rest of the interpreter; capability grants reduce the surface a plugin's helper shims can touch, but a malicious plugin granted any capability can reach further into the process than the grant prompt advertises.

The in-process loading reality has three concrete consequences:

- A plugin granted `filesystem.read` uses the `ctx.filesystem.read(path)` shim. The shim checks the capability before returning the file content. A malicious plugin can bypass the shim entirely and call the stdlib `open()` directly — Python imposes no restriction on which modules a plugin can import.
- A plugin granted `secrets.read` uses the `ctx.secrets.read(key)` shim that reads from `os.environ`. A malicious plugin can read every env var by calling `os.environ` directly, not just the key it asked for.
- A plugin granted `net.outbound` uses the `ctx.net.outbound(url)` shim backed by `httpx`. A malicious plugin can import `socket` or `urllib` directly and bypass the per-host gate the manifest implied.

The capability prompt is therefore a statement of what the plugin AUTHOR claims to need, not a technical enforcement of what the plugin CAN reach. The audit log persists every grant decision so post-incident forensics survive uninstall.

## Trust contract

The plugin system has a default-deny posture. Every capability is denied until the user explicitly grants it at install time. Grants are pinned to the `(plugin_name, plugin_version, manifest_hash)` triple, where `manifest_hash` is sha256 over the sorted-and-dedup'd capability set. A version upgrade re-prompts. A manifest edit that shifts the capability set re-prompts. A manifest edit that touches anything else does not.

The grant table, `plugin_capabilities`, is the only path to allow. The helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`) call `CapabilityGuard.check_capability` before every operation and raise `PermissionDenied` otherwise. The guard's `granted_capabilities` set is built from `plugin_capabilities` rows where `state = 'granted'`; a missing row, a `'pending'` row, or a `'revoked'` row all mean denied.

Every grant transition (issue, revoke, expire, re-grant under a new version) appends one row to `plugin_capability_grants_log`. The audit log persists across plugin uninstall — forensics survive cleanup so that a security review can reconstruct who granted what to whom.

Grant transitions land through `PermissionService` only. There is no other code path that writes to `plugin_capabilities`; the storage schema is the seam, the service is the verb.

## What v0.5 does NOT defend against

Out-of-scope, written down here so the trust contract is honest:

- **OS-level sandboxing.** Plugins run in the same Python process. A plugin granted `filesystem.read` can read your `~/.horus-os/secrets.json` even though the capability description says "files from disk paths the plugin declares" — the shim enforces the per-path gate, but the plugin can bypass the shim. If you do not trust the plugin author, do not install the plugin.
- **PyPI supply-chain attacks.** The `pip download --no-deps` step pulls whatever the package index serves at install time. Index compromise, typosquatting, dependency-confusion, and command-jacking (Checkmarx's wheel-pth research, Wiz's LiteLLM TeamPCP writeup) are not defended by this system. The installer refuses wheels that ship `.pth` files and refuses sdists by default, but neither defense rules out a malicious wheel that limits its payload to ordinary module-level code.
- **Social engineering of manifest text.** A plugin can describe itself as `"innocent log viewer"` in its `description` field while requesting `filesystem.read`. The capability prompt surfaces what the plugin asks for (the capability list), not what the plugin claims to do (the description). A user who skims the description and skims the capability list and types `y` has authorized the request even when the two halves disagree.
- **Network egress filtering.** The `net.outbound` grant is binary — once granted, the plugin's helper shim opens outbound HTTP/HTTPS connections to any host. The manifest may list intended hosts in its description, but `horus-os` does not enforce a per-host allowlist in v0.5. A plugin granted `net.outbound` can call any URL.

## Recommended user practices

The capability grant prompt is the primary UX moment for the user to evaluate trust. The recommendations below assume the user is taking that prompt seriously.

- **Install only from authors or organizations you trust.** A plugin you cannot audit yourself rides on the author's reputation. Treat unknown authors the same way you would treat unsigned binaries.
- **Audit the capability list at install time.** The capability prompt is plain English by design (the `DESCRIPTIONS` mapping in `capability_catalog.py` carries one-line summaries that print verbatim). A plugin that asks for `filesystem.write` but claims to be a log viewer is asking for a justification.
- **Review installed plugins after the fact.** `horus-os plugins info <name>` prints the granted capability set, the manifest hash, the version, and the audit-log tail. Run it periodically against the plugins you have granted capabilities to.
- **Disable plugins quickly when in doubt.** The `/plugins` dashboard tab has an Enable / Disable toggle. The CLI equivalent is `horus-os plugins disable <name>`. A disabled plugin's adapter is stopped and its tools are unregistered; the grants stay in `plugin_capabilities` so re-enabling is one click away.
- **Revoke single capabilities without uninstalling.** `horus-os plugins revoke <name> <capability>` flips the row's `state` to `'revoked'` and appends to the audit log. The plugin keeps running but the shim refuses the revoked capability on the next call.
