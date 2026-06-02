"""SSRF blocklist for the agent web access path (WEB-03, BLOCKING).

This module is the first guard rail of Phase 72 and is written BEFORE any
fetch logic (Pitfall WA-1). No web tool may open a socket without first
running its target host through `guard_url`. The guard resolves the host to
every IP it answers with and refuses the request if ANY resolved address is
loopback, private, link-local, reserved, multicast, or unspecified. The
169.254.169.254 cloud metadata endpoint is part of the link-local
169.254.0.0/16 range and is therefore refused; it is named explicitly below
so the source self-documents the WEB-03 constraint.

The module is pure stdlib (ipaddress, socket, urllib.parse). It deliberately
does NOT import httpx or any HTTP client: the guard is a validation primitive
that cannot itself perform a fetch, so it can never be bypassed by reusing it
as a request helper. DNS resolution is injected via the `resolver` parameter
(default socket.getaddrinfo) so callers and tests can pin or stub resolution
without touching the network.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

# WEB-03 BLOCKING: the AWS/GCP/Azure cloud metadata service lives at this
# link-local address. A prompt-injected URL pointing here would exfiltrate
# instance credentials, so it is refused before any socket is opened. It is
# covered by the 169.254.0.0/16 link-local check below; this constant keeps
# the constraint searchable and self-documenting.
CLOUD_METADATA_ADDRESS = "169.254.169.254"

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class BlockedURLError(ValueError):
    """Raised when a URL is refused by the SSRF guard before any fetch.

    Subclasses ValueError so existing tool error handling that catches
    ValueError keeps working, while callers that want to distinguish an SSRF
    refusal from a generic bad value can catch BlockedURLError specifically.
    """


def is_blocked_ip(ip_str: str) -> bool:
    """Return True when `ip_str` is an address a web fetch must never reach.

    A string that does not parse as an IP address is treated as blocked: if we
    cannot prove an address is safe, we refuse it. The checks cover loopback
    (127.0.0.0/8, ::1), private (RFC 1918 plus unique-local), link-local
    (169.254.0.0/16, fe80::/10, and thus the 169.254.169.254 metadata
    endpoint), reserved, multicast, and the unspecified 0.0.0.0 / :: address.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def guard_url(
    url: str,
    resolver: Callable[..., list] = socket.getaddrinfo,
) -> list[str]:
    """Validate `url` against the SSRF blocklist and return its resolved IPs.

    Refuses, by raising BlockedURLError, any URL that:
      - uses a scheme other than http or https (blocks file/ftp/data and
        friends, Pitfall WA-1);
      - has no hostname;
      - resolves (via `resolver`, default socket.getaddrinfo) to a host where
        ANY A or AAAA record is a blocked address. Checking every resolved
        record, not just the first, defeats DNS rebinding across multi-record
        hosts (T-72-04).

    On success it returns the list of resolved IP strings so the caller can
    pin the connection to a vetted address and re-run this guard on each
    redirect hop (the redirect target is a fresh URL and must be re-guarded).
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise BlockedURLError(
            f"refusing URL with scheme {scheme!r}; only http and https are allowed"
        )
    hostname = parts.hostname
    if not hostname:
        raise BlockedURLError(f"refusing URL with no hostname: {url!r}")

    resolved: list[str] = []
    seen: set[str] = set()
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = resolver(hostname, None, family)
        except socket.gaierror:
            # This family did not resolve; the other family may still answer.
            continue
        for info in infos:
            sockaddr = info[4]
            ip_str = sockaddr[0]
            if ip_str in seen:
                continue
            seen.add(ip_str)
            resolved.append(ip_str)

    if not resolved:
        raise BlockedURLError(f"refusing URL; host {hostname!r} did not resolve to any IP")

    for ip_str in resolved:
        if is_blocked_ip(ip_str):
            raise BlockedURLError(
                f"refusing URL {url!r}; host {hostname!r} resolves to blocked address {ip_str}"
            )
    return resolved
