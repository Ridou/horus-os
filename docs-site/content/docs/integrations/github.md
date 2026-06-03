---
title: "GitHub"
description: "Give your agents a read-only GitHub tool that fetches repository metadata, file contents, and directory listings over the GitHub REST API."
---

## What this integration does

horus-os ships an optional, read-only GitHub tool named `github_read`. When you enable it, your agents can fetch:

- **Repository metadata** (the response GitHub returns for a repo, such as description, default branch, and counts)
- **File contents** at a path within a repository
- **Directory listings** for a path within a repository

That is the full scope. The tool is read-only. It does not write, open issues, create pull requests, push commits, or change anything on GitHub. It calls the GitHub REST API (`api.github.com`) over the Python standard library, so it adds no compiled HTTP dependency.

> [!NOTE]
> The tool always queries the live GitHub REST API. There is no local mirror or cache.

## What the agent sees

The tool is registered with the agent runtime under the name `github_read`. It takes three parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `owner` | Yes | Repository owner (a user or organization login) |
| `repo` | Yes | Repository name |
| `path` | No | File or directory path within the repository. An empty path returns repository metadata |

When `path` is empty, the tool returns repository metadata. When `path` points at a file, it returns that file's contents payload. When `path` points at a directory, it returns the directory listing.

## Install the extra

The GitHub tool lives behind the `github` pip extra:

```bash
pip install 'horus-os[github]'
```

If you installed with `pip install 'horus-os[all]'`, the `github` extra is already included.

## Authentication

The tool reads a single server-side environment variable, `GITHUB_TOKEN`.

### Unauthenticated public reads (no token)

You do not need a token to read public repositories. When `GITHUB_TOKEN` is not set, the tool issues an unauthenticated public read. GitHub rate limits unauthenticated requests to roughly 60 per hour.

### Authenticated reads (with a token)

Set `GITHUB_TOKEN` to raise the rate limit and to read private repositories the token is authorized for. Create a token at [github.com/settings/tokens](https://github.com/settings/tokens), then export it in the environment of the machine running `horus-os serve` (or `horus-os run`):

```bash
export GITHUB_TOKEN="your-github-token"
```

> [!IMPORTANT]
> `GITHUB_TOKEN` is a server-side secret. Set it only in the environment of the process running horus-os. Never set it as a `NEXT_PUBLIC_*` variable. Next.js inlines every `NEXT_PUBLIC_*` value into the browser bundle at build time, which would publish your token to anyone who loads the dashboard. See [Deploy to Vercel](/operations/deploy-to-vercel/) for the full list of tokens that must stay server-side.

The token is never echoed back to the agent. On any failure the tool returns only an error class name (and an HTTP status code when one is available), never the underlying exception text and never the token value.

## Verify your setup

horus-os can probe GitHub to confirm your token works. The probe makes a single minimal authenticated API call (to `api.github.com/user`) and reports success or a short failure reason, such as `GITHUB_TOKEN not set` or an error class name, without echoing token material.

This probe is exposed by the running server, not by the `horus-os doctor` CLI command. The `doctor` command has no GitHub check. To run the probe:

1. Export `GITHUB_TOKEN` in the environment of the process running `horus-os serve`.
2. Start the dashboard with `horus-os serve` and open it in your browser (default `http://127.0.0.1:8765`).
3. Go to the Settings page, find the GitHub credential row, and select **Verify now**.

That button calls the server endpoint `POST /api/integrations/github/verify`, which runs the probe and records the verified state. If `GITHUB_TOKEN` is unset, the probe reports `GITHUB_TOKEN not set`. Public reads still work without a token; only the authenticated probe requires one.

> [!NOTE]
> The verify endpoint is loopback-only and is disabled in demo mode. Run it from the machine hosting `horus-os serve`. See [Dashboard](/guides/dashboard/) for how to open the Settings page.

## Behavior and limits

The tool enforces a few guardrails so a large response cannot blow the model context window or run up cost:

- **Response size cap.** Responses larger than about 1 MB are rejected with a `ResponseTooLarge` error rather than returned to the agent.
- **Request timeout.** Each request times out after 10 seconds.
- **Distinct error statuses.** HTTP errors surface the numeric status code (for example 404 not found, 403 rate limited, 401 unauthorized) so the agent can tell apart a missing repository from a rate limit or a forbidden read.
- **Path safety.** The `owner`, `repo`, and `path` values are URL-encoded so an agent-supplied value cannot break out of the fixed `api.github.com` path.

## Example

With the extra installed and (optionally) a token exported, ask an agent something like:

```text
Read the README and list the top-level files of Ridou/horus-os on GitHub.
```

The agent calls `github_read` once with an empty `path` to fetch repository metadata, again with a directory path to list files, and again with a file path to read the README, then summarizes what it found.

## See also

- [Integrations overview](/integrations/overview/) for the full list of integrations and how they are enabled
- [Deploy to Vercel](/operations/deploy-to-vercel/) for why `GITHUB_TOKEN` must never be a `NEXT_PUBLIC_*` variable
- [Environment variables](/reference/environment-variables/) for the complete env-var reference
