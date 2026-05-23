"""horus-os adapter plugin interface.

Adapters are inbound channels that route external events into the
horus-os agent runtime. They are discovered at FastAPI app startup
via the `horus_os.adapters` entry point group and bind their own
routes onto the FastAPI instance.

Third-party packages declare an adapter in their `pyproject.toml`:

    [project.entry-points."horus_os.adapters"]
    my_adapter = "my_package.adapter:MyAdapter"

`MyAdapter` must be a callable (typically a class) that returns an
object satisfying the `Adapter` Protocol. Long-running adapters can
additionally implement the optional `LifecycleAdapter` Protocol to
get `start`/`stop` hooks tied to the FastAPI app lifespan.
"""

from horus_os.adapters.base import (
    ADAPTER_ENTRY_POINT_GROUP,
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    ADAPTER_STATUS_STOPPED,
    Adapter,
    AdapterContext,
    AdapterEntry,
    AdapterRegistry,
    LifecycleAdapter,
    discover_adapters,
)
from horus_os.adapters.discord_adapter import DiscordAdapter
from horus_os.adapters.email_adapter import EmailAdapter
from horus_os.adapters.slack_adapter import SlackAdapter
from horus_os.adapters.webhook import WebhookAdapter

__all__ = [
    "ADAPTER_ENTRY_POINT_GROUP",
    "ADAPTER_STATUS_ERROR",
    "ADAPTER_STATUS_RUNNING",
    "ADAPTER_STATUS_STOPPED",
    "Adapter",
    "AdapterContext",
    "AdapterEntry",
    "AdapterRegistry",
    "DiscordAdapter",
    "EmailAdapter",
    "LifecycleAdapter",
    "SlackAdapter",
    "WebhookAdapter",
    "discover_adapters",
]
