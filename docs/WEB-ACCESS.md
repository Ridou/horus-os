# Web access: search and browsing

horus-os web access ships in two halves, both opt-in and both off by default:

1. **Web search** (WEB-01): a bring-your-own-provider `web_search` tool that you
   enable by configuring `[tools.web_search]` in `config.toml`.
2. **Browsing and screenshots** (WEB-02): delivered with zero new horus-os
   browser code by adding the Playwright MCP server to `mcp.toml`. The phase-71
   MCP client registers its browser tools namespaced as `mcp:playwright:*`.

Neither is active in a default install. Web search has no tool entry until a
provider is configured; browsing has no tools until you add the Playwright MCP
server to `mcp.toml`.

## Web search

The `web_search` tool is absent from the agent registry unless a provider is
configured. Add a `[tools.web_search]` block to `<data_dir>/config.toml`:

```toml
[tools.web_search]
provider = "searxng"               # one of: searxng, brave, tavily
base_url = "http://localhost:8888" # required for searxng (your instance)
```

- `searxng` (default and recommended): a self-hosted SearXNG instance. Set
  `base_url` to your instance. No API key.
- `brave`: the Brave Search API. `base_url` is optional and defaults to the
  public endpoint. Provide the key via the `HORUS_OS_WEB_SEARCH_KEY` environment
  variable.
- `tavily`: the Tavily API. `base_url` is optional and defaults to the public
  endpoint. Provide the key via `HORUS_OS_WEB_SEARCH_KEY`.

The API key is read from `HORUS_OS_WEB_SEARCH_KEY` at runtime and is never
written to `config.toml`. With no `[tools.web_search]` block the registry has no
`web_search` entry at all (default-deny): the agent simply cannot search the web
until you opt in.

Each result is normalized to `{title, url, snippet}` regardless of provider.

## Browsing and screenshots (Playwright MCP)

WEB-02 browsing rides entirely on the phase-71 MCP client. horus-os adds no
Python browser dependency and no hand-rolled browser stack. You install the
Playwright MCP server (the `@playwright/mcp` package, run via `npx`) and list it
in `mcp.toml`. Once listed, its tools register automatically and namespaced as
`mcp:playwright:*`, traced like any builtin tool.

The tools the Playwright MCP server contributes include:

- `mcp:playwright:browser_navigate` (open a URL)
- `mcp:playwright:browser_take_screenshot` (capture the page)
- `mcp:playwright:browser_snapshot` (structured page snapshot)

### mcp.toml entry

Add a stdio server block to `<data_dir>/mcp.toml`:

```toml
[[mcp.servers]]
name = "playwright"
transport = "stdio"
command = ["npx", "@playwright/mcp@latest"]
```

Adding this `[[mcp.servers]]` block is the single conscious act that turns
browsing on. With no `mcp.toml`, or with the Playwright block absent, the agent
has no browser tools. See `docs/MCP.md` for the full `mcp.toml` schema and the
MCP trust model.

## Security posture

### SSRF guard on the search fetch path

Every outbound web-search request runs its URL through the SSRF guard before a
socket opens, and re-checks on every redirect hop. A provider URL (or a
redirect) that resolves to a loopback, private, link-local, or cloud-metadata
address is refused. In particular the cloud-metadata address `169.254.169.254`
and private ranges are refused on the search fetch path (cross-referenced by
TEST-35, the SSRF blocklist regression test). This same SSRF posture is the
model for any URL the agent fetches.

### Browsing trust gate

Browsing inherits the phase-71 MCP trust gate: the Playwright MCP server runs
only when it is explicitly listed in `mcp.toml`. A server you did not add cannot
contribute tools. Because a prompt-injected instruction can try to steer the
browser toward an internal or metadata URL, treat the Playwright MCP server as
you would any tool with network reach, and keep the SSRF posture above in mind
when reviewing what the agent fetched in a trace.

### robots.txt and Terms of Service

Automated browsing does not enforce `robots.txt`. You are responsible for
`robots.txt` and Terms of Service compliance for every site the agent visits.
Scraping a site that prohibits automation in its ToS can lead to rate limiting,
IP bans, or legal notices. Expect rate-limited responses (HTTP 429, `Retry-After`
headers, CAPTCHA walls) and back off rather than retrying in a tight loop
(Pitfall WA-3). Prefer fetching your own sites or sites that explicitly permit
automated access.

## Uploads (images and PDFs)

Clients upload an image or PDF as multipart form data to
`POST /api/uploads`, which stores it under `<data_dir>/uploads/` with a
uuid-based filename and returns the absolute path. Reference that path in a
chat message (or any agent prompt) so the agent can call the `analyze_file`
tool on it. The uploads
route enforces a content-type allowlist (PNG, JPEG, GIF, WebP, PDF), a size cap,
and a stored filename derived from the validated content type rather than the
client filename, so a crafted filename cannot escape the uploads directory. The
`analyze_file` tool is scoped to `<data_dir>/uploads/` so it cannot read
arbitrary local files.
