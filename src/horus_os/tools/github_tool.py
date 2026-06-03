"""Optional read-only GitHub agent tool (GH-02).

`make_github_read_tool` returns a `Tool` that reads public or authorized
GitHub repository data (repository metadata, file and directory contents)
via the GitHub REST API. The HTTP client is the stdlib `urllib.request`,
lazy-imported inside the handler so this module imports cleanly even when
the optional `[github]` extra is not installed and so no compiled
dependency (the kind a third-party GitHub SDK pulls via pynacl) is added,
keeping the three-OS install gate safe (D-08).

The server-side `GITHUB_TOKEN` (the name in the committed integration
registry) is read from `os.environ`. When it is absent the tool still
issues an unauthenticated public read, which GitHub rate limits to about
60 requests per hour. The token is never returned to the caller: on any
failure the handler returns only `{"error": type(exc).__name__}`, never
`str(exc)` and never the token value (T-67-07).
"""

from __future__ import annotations

import json
import os
from typing import Any

from horus_os.types import Tool

_GITHUB_READ_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "owner": {
            "type": "string",
            "description": "Repository owner (user or organization login).",
        },
        "repo": {
            "type": "string",
            "description": "Repository name.",
        },
        "path": {
            "type": "string",
            "description": (
                "File or directory path within the repository. Empty = repository root metadata."
            ),
        },
    },
    "required": ["owner", "repo"],
}

_GITHUB_API_VERSION = "2022-11-28"
# Cap the response body fed back to the agent so a very large file or listing
# cannot blow the model context window or run up cost (WR-03). The bytes are
# returned verbatim to the model, so bound them.
_GITHUB_MAX_BYTES = 1_000_000


def make_github_read_tool() -> Tool:
    """Return a `Tool` that reads GitHub repository data over the REST API.

    The handler reads the server-side `GITHUB_TOKEN` when present (raising
    the rate limit and enabling private-repository reads); when absent it
    performs an unauthenticated public read. The HTTP client is imported
    lazily inside the handler so importing this module requires no extra.
    """

    def handler(owner: str, repo: str, path: str = "") -> dict[str, Any]:
        # Lazy imports so this module loads without the [github] extra and
        # never pulls a compiled HTTP dependency at import time.
        import urllib.error
        import urllib.parse
        import urllib.request

        token = os.environ.get("GITHUB_TOKEN")
        headers = {
            "User-Agent": "horus-os",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # URL-encode the model-supplied segments so a crafted value cannot
        # break out of the fixed api.github.com path (WR-02). owner and repo
        # carry no slashes; a path may carry directory slashes, so quote each
        # segment individually and preserve the separators.
        owner_q = urllib.parse.quote(owner, safe="")
        repo_q = urllib.parse.quote(repo, safe="")
        clean_path = path.strip("/")
        if clean_path:
            path_q = "/".join(urllib.parse.quote(seg, safe="") for seg in clean_path.split("/"))
            url = f"https://api.github.com/repos/{owner_q}/{repo_q}/contents/{path_q}"
        else:
            url = f"https://api.github.com/repos/{owner_q}/{repo_q}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read(_GITHUB_MAX_BYTES + 1)
            if len(raw) > _GITHUB_MAX_BYTES:
                return {"error": "ResponseTooLarge"}
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Surface the HTTP status code (404 vs 403 vs 401) so the agent can
            # distinguish not-found from rate-limited from forbidden (WR-04).
            # Only the class name and numeric code are returned: never str(exc),
            # never the token.
            return {"error": type(exc).__name__, "status": exc.code}
        except Exception as exc:
            # Any other failure (URLError, timeout, JSON decode) maps to a clean
            # class-name-only error: no token material can reach the model.
            return {"error": type(exc).__name__}

    return Tool(
        name="github_read",
        description=(
            "Read public or authorized GitHub repository data: repository "
            "metadata, file contents, and directory listings. Provide owner "
            "and repo, plus an optional path within the repository (empty "
            "path returns repository metadata). Set the server-side "
            "GITHUB_TOKEN to raise the rate limit and read private "
            "repositories; unauthenticated public reads work without it."
        ),
        parameters=_GITHUB_READ_PARAMETERS,
        handler=handler,
    )
