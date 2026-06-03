---
title: "Editing your vault"
description: "Your vault is plain markdown, so you can edit it in any editor. This guide shows how to use Obsidian as your vault editor, plus what to expect from horus-os when you do."
---

Because your [vault](/concepts/the-vault/) is just a folder of plain markdown
files, you can read and write it in whatever editor you already use. horus-os
never locks your notes into a proprietary format or database. This guide focuses
on **Obsidian**, a popular markdown knowledge-base editor, and then covers other
editors and a few things to know about how horus-os sees your edits.

## Use Obsidian as your vault editor

Obsidian opens any folder of markdown files as a "vault." Pointing it at your
horus-os notes folder gives you a polished editor, a file tree, graph view, and
live preview over the exact same files your agents read and write.

There are two ways to connect them.

### Option A: open your horus-os notes folder in Obsidian

Point Obsidian directly at the existing notes folder.

1. Find your vault path. It is the `notes/` folder in your [data
   directory](/getting-started/installation/#where-horus-os-stores-its-data),
   for example `~/Library/Application Support/horus-os/notes` on macOS.
2. In Obsidian, choose **Open folder as vault** and select that folder.
3. Obsidian now edits the same markdown files horus-os uses. Notes your agents
   write appear in Obsidian, and notes you write in Obsidian are visible to your
   agents.

### Option B: point horus-os at your existing Obsidian vault

If you already keep an Obsidian vault, tell horus-os to use it as the notes
folder. Edit `config.toml` in your data directory:

```toml
[notes]
notes_dir = "/Users/you/Documents/My Obsidian Vault"
```

Restart horus-os and your agents now read and write inside your existing vault.

> [!TIP]
> Keeping the two in sync is automatic because they are literally the same
> files. There is no import, export, or sync step.

## What horus-os understands (and what it does not)

This is the important part, so that Obsidian behaves the way you expect.
horus-os treats your vault as **plain markdown**. It does not currently parse
Obsidian-specific conventions, so a few Obsidian features are visible only inside
Obsidian and are not understood by your agents:

| Obsidian feature | Works in Obsidian | Understood by horus-os agents |
|------------------|-------------------|-------------------------------|
| Standard markdown (headings, lists, tables, code) | Yes | Yes |
| Full-text and semantic search of note bodies | Yes | Yes |
| Wikilinks `[[Note Name]]` | Yes | Stored as plain text, not resolved as links |
| Tags `#tag` | Yes | Stored as plain text, not indexed as metadata |
| YAML frontmatter properties | Yes | Stored as plain text, not parsed as metadata |
| Backlinks and graph view | Yes | Not built |

In practice this means you can absolutely use Obsidian to organize, link, and
tag your notes for your own benefit. Your agents will still find those notes by
their text content through keyword and (if enabled) vector search. They just will
not follow a `[[wikilink]]` or filter by a `#tag` the way Obsidian does.

> [!NOTE]
> Writing a wikilink or a tag in a note does no harm. horus-os stores it
> verbatim and shows it as written. It simply has no special meaning to the
> agents yet.

## Other editors

Anything that edits text files works just as well:

- **VS Code** with a markdown preview extension, opened on your notes folder.
- **Vim, Neovim, or Emacs** for terminal editing.
- **Any plain text editor**, since there is nothing but `.md` files.

## After editing notes outside horus-os

Keyword search always reads the current files on disk, so notes you add or edit
in another editor are searchable immediately, with no extra step.

If you have enabled [on-device vector memory](/concepts/the-vault/#optional-on-device-vector-search)
and you make a large batch of external edits, rebuild the semantic index so
those changes are reflected in vector search:

```bash
horus-os memory reindex
```

## Next steps

- [The vault](/concepts/the-vault/) explains how memory, audit logging, and
  vector search work under the hood.
- [Autonomous research](/guides/autonomous-research/) shows the Researcher
  writing cited reports straight into your vault.
