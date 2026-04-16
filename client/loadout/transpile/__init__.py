"""JS-to-Python transpiler for shared loadout calculation files.

Public entry points:
    ensure_transpiled(force=False) -> None
        Regenerate `client/loadout/generated/*.py` when any source .js has
        changed since the last run. Called at client startup and from the
        packaging build step.

The `runtime` submodule is importable on its own without dragging in the
parser/walker — unit tests exercise it directly.
"""


def ensure_transpiled(force: bool = False) -> None:
    from .pipeline import ensure_transpiled as _impl
    _impl(force=force)
