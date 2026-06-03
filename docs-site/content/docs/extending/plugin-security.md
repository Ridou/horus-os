---
title: "Plugin security"
description: "How horus-os gates plugins with capability grants, manifest-hash pinning, and a closed API surface, plus what the model does and does not defend against."
---

## Overview

horus-os plugins are ordinary Python packages that run inside the horus-os process. They are powerful by design, so the plugin system is built around an explicit trust contract: every plugin starts with zero permissions, and you grant capabilities one at a time at install time.

This page is the canonical statement of the security model. Read it before you grant any capability to a plugin you did not write yourself. It covers four mechanisms (the capability grant, manifest-hash pinning, the closed API surface, and the audit log) and, just as importantly, the threats the model does NOT defend against.

For how plugins are built and installed, see [Plugins](/extending/plugins/). For the manifest fields referenced below, see [Manifest reference](/extending/manifest-reference/).

> [!IMPORTANT]
> The capability grant prompt tells you what the plugin AUTHOR declares they need. It is not a technical sandbox. A malicious plugin can reach further into the process than its grant prompt advertises. If you do not trust the author, do not install the plugin.

## Threat model

In horus-os, plugins execute in the same Python interpreter as horus-os itself. They share the process file descriptors, the environment variables (including your `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`), the loaded modules, and the same disk access horus-os holds. There is no OS-level sandbox between a plugin and the rest of the interpreter.

Capability grants reduce the surface a plugin's helper shims expose, but they do not stop a determined plugin from importing the standard library directly. The in-process reality has three concrete consequences:

- A plugin granted `filesystem.read` is meant to use the `ctx.filesystem.read(path)` shim, which checks the capability before returning file content. A malicious plugin can ignore the shim and call the stdlib `open()` directly. Python imposes no restriction on which modules a plugin imports.
- A plugin granted `secrets.read` is meant to use the `ctx.secrets.read(key)` shim. A malicious plugin can read every environment variable by reaching `os.environ` directly, not just the key it asked for.
- A plugin granted `net.outbound` is meant to use the `ctx.net.outbound(url)` shim. A malicious plugin can import `socket` or `urllib` directly and bypass any per-host intent the manifest implied.

The takeaway: the capability prompt is a statement of declared intent, not an enforcement boundary against hostile code. Trust the author first; treat the grant prompt as a second, finer-grained filter.

## The capability grant

The plugin system has a default-deny posture. Every capability is denied until you explicitly grant it. Capabilities come from a closed catalog: a plugin can only request strings that horus-os recognizes, and any other value fails manifest validation at load time.

The catalog members are:

| Capability | What the grant covers |
| --- | --- |
| `filesystem.read` | Read files from disk paths the plugin declares. Does NOT include writing, deleting, or modifying files. |
| `filesystem.write` | Create, modify, and delete files at declared paths. Implies read access to the same paths. |
| `net.outbound` | Open outbound network connections to hosts the plugin declares. Does NOT permit inbound listeners. |
| `secrets.read` | Read secret values by key name. Does NOT permit listing all secrets or writing new ones. |
| `skill.exec` | Run the embedded steps of a code-bearing skill. Prompt-template skills never need this. |
| `shell.exec` | Run shell commands as a structured argument list inside the configured safe working directory. |
| `code.exec` | Run code snippets through the same gated subprocess path as shell commands. |

Each catalog member carries a one-line, plain-English description that the installer prints verbatim at the grant prompt. That description is what you see when you are asked to authorize a plugin.

> [!NOTE]
> The catalog is closed on purpose. Plugin authors cannot invent new capability strings; adding a capability is a horus-os change, not a plugin change. This keeps the set of things you can ever be asked to grant small and reviewable.

### Granting and revoking from the CLI

Grants are normally made at install time, but you can also manage them afterward:

```bash
# Grant a single capability to an already-installed plugin.
horus-os plugins grant your-plugin-name filesystem.read

# Grant every capability declared in the plugin manifest at once.
horus-os plugins grant your-plugin-name --all

# Revoke a single capability without uninstalling.
horus-os plugins revoke your-plugin-name filesystem.read
```

Revoking flips the capability row to a revoked state and appends to the audit log. The plugin keeps running, but its shim refuses the revoked capability on the next call.

## Manifest-hash pinning and re-prompt-on-change

A grant is not pinned to a plugin name alone. It is pinned to the triple `(plugin_name, plugin_version, manifest_hash)`.

The `manifest_hash` is a sha256 over the sorted, deduplicated capability set declared in the manifest. Because the hash is computed from the sorted set, reordering capabilities in the manifest does not change it, but adding or removing a capability does.

This pinning drives the re-prompt behavior:

- A version upgrade re-prompts for grants.
- A manifest edit that shifts the capability set changes the hash, so it re-prompts.
- A manifest edit that touches anything else (the description, unrelated metadata) does not change the capability hash and does not re-prompt.

The effect is that you are asked to re-confirm exactly when the set of things a plugin can request changes, and never just because the author shipped a cosmetic update. When you run `horus-os plugins update`, the upgrade-diff classifier compares the new capability set against your approved set and prompts only for what is newly requested.

> [!WARNING]
> Re-prompt-on-change protects you from silent capability creep, but only if you read the new prompt. An upgrade that adds `filesystem.write` to a plugin that previously only had `filesystem.read` will ask again. Do not reflexively type `y`.

## The API surface lock

Plugins are meant to reach the host through a fixed set of helper shims on the plugin context: `ctx.filesystem`, `ctx.secrets`, and `ctx.net`. Each shim consults the capability guard before every operation and raises a permission error when the capability is not granted.

The guard builds its set of allowed capabilities from the grant table, reading only rows whose state is granted. A missing row, a pending row, or a revoked row all mean denied. There is a single service that writes grant transitions; the storage schema is the only path to allow, and nothing else writes to the grant table. This narrow surface is what makes grants auditable: every allow decision traces back to one table and one writer.

The lock applies to the shims. As the threat model above states, it does not stop a plugin from bypassing the shims with direct standard-library calls. The API surface lock raises the cost and visibility of misbehavior; it is not an escape-proof boundary.

## The audit log

Every grant transition (issue, revoke, expire, re-grant under a new version) appends one row to the capability grant log. The log persists across plugin uninstall, so a post-incident review can reconstruct who granted what, even after the plugin is gone.

Inspect the current grant state and the audit-log tail for a plugin with:

```bash
horus-os plugins info your-plugin-name
```

This prints the granted capability set, the manifest hash, the version, and recent audit-log entries.

## Trust boundaries: what horus-os does NOT defend against

These are written down so the trust contract is honest. None of the following are inside the security boundary:

- **OS-level sandboxing.** Plugins run in the same Python process as horus-os. A plugin granted `filesystem.read` can read sensitive files even though its capability description scopes the grant to declared paths, because it can bypass the shim. If you cannot audit the plugin, you are trusting the author.
- **Supply-chain attacks.** Installing a plugin pulls whatever the package index serves at that moment. Index compromise, typosquatting, dependency confusion, and command-jacking are not defended by this system. The installer refuses wheels that ship `.pth` files and refuses source distributions by default (`--allow-sdist` overrides this and is not recommended), but neither defense rules out a malicious wheel whose payload is ordinary module-level code.
- **Social engineering of manifest text.** A plugin can describe itself as an innocent log viewer while requesting `filesystem.write`. The grant prompt surfaces the capability list, not the truth of the description. If the description and the capability list disagree, believe the capability list.
- **Network egress filtering.** The `net.outbound` grant is binary. Once granted, a plugin's shim can open outbound connections to any host. The manifest may list intended hosts in its description, but horus-os does not enforce a per-host allowlist. A plugin granted `net.outbound` can call any URL.

## Recommended practices

The grant prompt is your primary moment to evaluate trust. To use it well:

- **Install only from authors or organizations you trust.** A plugin you cannot audit rides entirely on the author's reputation. Treat unknown authors the way you would treat unsigned binaries.
- **Audit the capability list at install time.** A plugin that asks for `filesystem.write` while claiming to be a log viewer is asking for a justification.
- **Review installed plugins periodically.** Run `horus-os plugins info your-plugin-name` to see the granted set, the manifest hash, the version, and the audit-log tail.
- **Disable quickly when in doubt.** Run `horus-os plugins disable your-plugin-name` (or use the Enable / Disable toggle in the dashboard). A disabled plugin's adapter is stopped and its tools are unregistered; grants stay in place so re-enabling is one step.
- **Revoke a single capability** with `horus-os plugins revoke your-plugin-name <capability>` instead of uninstalling when you only want to narrow a plugin's reach.

## See also

- [Plugins](/extending/plugins/)
- [Manifest reference](/extending/manifest-reference/)
- [Writing an adapter](/extending/writing-an-adapter/)
- [Security](/operations/security/)
