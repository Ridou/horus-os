"""horus-os-example-plugin: reference plugin demonstrating the v0.5 contract.

Four scenarios in one package:
  (a) ``tools.echo_text_tool`` — capability-gated filesystem read.
  (b) ``tools.lookup_secret_tool`` — capability-gated secret lookup.
  (c) ``adapter.ExampleAdapter`` — bounded-lifecycle adapter.
  (d) one ``horus-plugin.toml`` registering both tools + the adapter.

The public surface is the entry-point group ``horus_os.plugins``, not
bare attribute imports. ``__all__`` is empty by design.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
