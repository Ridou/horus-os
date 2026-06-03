---
title: "Manifest reference"
description: "Every field of the horus-os plugin manifest (horus-plugin.toml) at manifest_version 1, its type, whether it is required, and what it means."
---

## Overview

Every horus-os plugin ships a `horus-plugin.toml` manifest at its wheel root (or inside the package directory as package data). The manifest declares the plugin's identity, the horus-os versions it supports, the capabilities it requests, and the tools and adapters it contributes.

This page documents the v1 manifest contract field by field. The contract is validated against `horus_os.plugins.manifest.MANIFEST_V1_SCHEMA`, and a JSON Schema mirror lives at `docs/manifest-v1.schema.json` in the repository.

> [!NOTE]
> Unknown top-level fields are silently dropped (the schema uses `extra="ignore"`). Validation emits a warning for each unknown field before parsing, so you get a forward-compatibility hint without your plugin failing to load.

## Complete example

```toml
manifest_version = 1
name = "horus-os-example"
version = "1.2.3"
description = "An example plugin exercising every documented field."
author = "your-name"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.7,!=0.5.1"
homepage = "https://github.com/your-org/horus-os-example"
issue_tracker = "https://github.com/your-org/horus-os-example/issues"
capabilities = [
    "filesystem.read",
    "filesystem.write",
    "net.outbound",
    "secrets.read",
]

[[contributions.tools]]
name = "alpha_tool"
entry_point = "example_plugin.tools:alpha"

[[contributions.tools]]
name = "beta_tool"
entry_point = "example_plugin.tools:beta"

[[contributions.adapters]]
name = "alpha_adapter"
entry_point = "example_plugin.adapters:AlphaAdapter"

[[contributions.adapters]]
name = "beta_adapter"
entry_point = "example_plugin.adapters:BetaAdapter"
```

## Top-level fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `manifest_version` | integer | Yes | The manifest contract version. Always `1` for v1. Older or newer values are refused at validation time. A future v2 manifest will be parsed by a separate schema, and the installer switches on this integer. |
| `name` | string | Yes | The plugin name. Lowercase ASCII letters, digits, and hyphens. Becomes the plugin's row key, the prefix on every contributed tool's qualified name, and the argument to the `horus-os plugins` subcommands. |
| `version` | string | Yes | The plugin version, in PEP 440 form. Stored on the plugin record and pinned into every capability grant, so a version bump invalidates prior grants automatically. |
| `description` | string | Yes | A one-line plain-English summary (at most 200 characters). Appears in the dashboard plugins tab and in `horus-os plugins info <name>` output. |
| `author` | string | Yes | The plugin author. Must be non-empty. Shown next to the description in the capability grant prompt. |
| `license` | string | Yes | The plugin license. An SPDX identifier such as `Apache-2.0` is preferred. Surfaced in dashboard listings. |
| `horus_os_compat` | string | Yes | A PEP 440 specifier set, for example `>=0.5,<0.7,!=0.5.1`. Parsed via `packaging.specifiers.SpecifierSet`. The installer refuses to load a plugin whose specifier excludes the running horus-os version. |
| `homepage` | URL | No | A project homepage URL. Defaults to `null`. Surfaced in the dashboard. |
| `issue_tracker` | URL | No | An issue tracker URL. Defaults to `null`. Surfaced in the dashboard. |
| `capabilities` | array of strings | No | The capabilities the plugin requests. A closed enum; unknown values are refused at validation time. Defaults to an empty list. See [Capabilities](#capabilities). |
| `contributions` | table | No | The plugin's tool and adapter contribution tables. See [Contributions](#contributions). |

### URL fields

`homepage` and `issue_tracker` accept either a valid URL string (with a maximum length of 2083 characters) or `null`. Both default to `null` when omitted.

## Capabilities

`capabilities` is a list drawn from a closed enum. Each value names a class of access the plugin needs, and each one is presented to you in the capability grant prompt when you install the plugin. If a capability is not granted, the matching shim raises `PermissionDenied` at runtime.

| Capability | Meaning |
| --- | --- |
| `filesystem.read` | Read files from disk paths the plugin declares. Does not include writing, deleting, or modifying files. |
| `filesystem.write` | Create, modify, and delete files at disk paths the plugin declares. Implies read access to the same paths. |
| `net.outbound` | Open outbound network connections to hosts the plugin declares. Does not permit inbound listeners or connections to hosts the manifest did not list. |
| `secrets.read` | Read secret values (API keys, tokens) the plugin declares by key name. Does not permit listing all secrets or writing new ones. |
| `skill.exec` | Run the embedded steps of a code-bearing skill. Only a skill marked as code is gated on this. |
| `shell.exec` | Run shell commands as a structured argument list inside the configured safe working directory. Commands may not use shell metacharacters and may not escape the working directory. |
| `code.exec` | Run code snippets through the same gated subprocess path as shell commands, with the same metacharacter and working-directory boundary checks. |

> [!IMPORTANT]
> Granting a capability gives a plugin real access to your machine. Read the trust contract on [Plugin security](/extending/plugin-security/) before you grant capabilities to a plugin you did not author yourself.

## Contributions

The `contributions` table holds two optional arrays: `contributions.tools` and `contributions.adapters`. Both are written as repeated tables in TOML (`[[contributions.tools]]`, `[[contributions.adapters]]`).

- **Tools** extend the agent's tool registry.
- **Adapters** extend the FastAPI app with new routes, background tasks, or external integrations.

The loader instantiates each declared entry at startup, and per-surface entry-point resolution is independent, so one wheel can contribute both tools and adapters in a single manifest.

### Contribution entry fields

Each entry in `contributions.tools` and `contributions.adapters` is an object with the same shape.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | A lowercase-ASCII identifier scoped within the plugin. Must match the pattern `^[a-z][a-z0-9_]*$` (lowercase letter first, then lowercase letters, digits, or underscores). |
| `entry_point` | string | Yes | A dotted-path import string with an optional `:Symbol` suffix, for example `example_plugin.tools:alpha`. Must match the dotted-path pattern with an optional trailing symbol. |

Both fields are required for every entry, and no other keys are allowed on a contribution entry.

```toml
[[contributions.tools]]
name = "search_notes"
entry_point = "example_plugin.tools:search_notes"

[[contributions.adapters]]
name = "webhook_listener"
entry_point = "example_plugin.adapters:WebhookAdapter"
```

## Validation rules at a glance

- `manifest_version`, `name`, `version`, `description`, `author`, `license`, and `horus_os_compat` are all required. A manifest missing any of them fails validation.
- `manifest_version` must be `1` for the v1 schema.
- `name` on a contribution entry must be lowercase ASCII matching `^[a-z][a-z0-9_]*$`.
- `entry_point` must be a dotted import path, optionally suffixed with `:Symbol`.
- `capabilities` values must come from the closed capability enum; unknown values are refused.
- `horus_os_compat` must be a valid PEP 440 specifier set, and the running horus-os version must satisfy it.
- Unknown top-level fields are dropped with a warning rather than failing the load.

## See also

- [Plugins](/extending/plugins/) for the full plugin authoring guide, lifecycle hooks, and distribution.
- [Plugin security](/extending/plugin-security/) for the capability trust model and threat surface.
- [Writing an adapter](/extending/writing-an-adapter/) for building adapter contributions.
