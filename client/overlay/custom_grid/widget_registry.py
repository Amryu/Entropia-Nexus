"""WidgetRegistry — discovers and loads GridWidget subclasses."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
from pathlib import Path

from ...core.logger import get_logger
from .grid_widget import GridWidget

log = get_logger("WidgetRegistry")


class WidgetRegistry:
    """Discovers and tracks GridWidget subclasses from builtin/ and user dir.

    Built-in widgets are scanned from the ``custom_grid.builtin`` package.
    User widgets are loaded from ``user_widget_dir/*.py`` via
    ``importlib.util.spec_from_file_location``.

    Errors during loading are isolated — a failing file never prevents other
    widgets from loading.  Check ``get_load_errors()`` after ``discover()``.
    """

    def __init__(self, user_widget_dir: Path):
        self._user_dir = user_widget_dir
        self._widgets: dict[str, type[GridWidget]] = {}  # id → class
        self._load_errors: dict[str, str] = {}           # filename → error

    def discover(self) -> None:
        """Scan builtin/ package and user_widget_dir for GridWidget subclasses."""
        self._widgets.clear()
        self._load_errors.clear()

        # Built-in widgets
        from . import builtin as _builtin_pkg
        builtin_path = Path(_builtin_pkg.__file__).parent
        for _finder, modname, _ispkg in pkgutil.iter_modules([str(builtin_path)]):
            full_name = f"client.overlay.custom_grid.builtin.{modname}"
            try:
                mod = importlib.import_module(full_name)
                self._register_from_module(mod)
            except Exception as e:
                log.error("Failed to load builtin widget module %s: %s", modname, e)

        # User widgets
        if self._user_dir.exists():
            for py_file in sorted(self._user_dir.glob("*.py")):
                self.load_user_file(py_file)

        log.info(
            "Widget discovery complete: %d widget(s), %d error(s)",
            len(self._widgets), len(self._load_errors),
        )

    def load_user_file(self, path: Path) -> list[type[GridWidget]]:
        """Load a user widget file and register any GridWidget subclasses found.

        Returns the list of successfully registered classes.
        """
        found: list[type[GridWidget]] = []
        try:
            spec = importlib.util.spec_from_file_location(
                f"_user_widget_{path.stem}", path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create module spec from {path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            found = self._register_from_module(mod)
            log.info(
                "Loaded user widget file: %s (%d class(es))", path.name, len(found)
            )
        except Exception as e:
            err = str(e)
            log.error("Failed to load user widget %s: %s", path.name, err)
            self._load_errors[path.name] = err
        return found

    def _register_from_module(self, mod) -> list[type[GridWidget]]:
        """Inspect a module for GridWidget subclasses and register them."""
        found: list[type[GridWidget]] = []
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, GridWidget)
                and obj is not GridWidget
                and obj.WIDGET_ID != GridWidget.WIDGET_ID
            ):
                if obj.WIDGET_ID in self._widgets:
                    log.warning(
                        "Duplicate widget ID '%s' — skipping %s",
                        obj.WIDGET_ID, obj.__name__,
                    )
                    continue
                self._widgets[obj.WIDGET_ID] = obj
                found.append(obj)
        return found

    def get_all(self) -> list[type[GridWidget]]:
        """Return all registered widget classes sorted by display name."""
        return sorted(self._widgets.values(), key=lambda c: c.DISPLAY_NAME)

    def get_by_id(self, widget_id: str) -> type[GridWidget] | None:
        return self._widgets.get(widget_id)

    def get_load_errors(self) -> dict[str, str]:
        """Return {filename: error_message} for files that failed to load."""
        return dict(self._load_errors)
