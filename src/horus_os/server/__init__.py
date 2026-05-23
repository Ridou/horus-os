"""Local HTTP server for the horus-os dashboard and JSON API."""

from horus_os.server.api import create_app

__all__ = ["create_app"]
