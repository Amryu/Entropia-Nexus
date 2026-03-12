"""WidgetRegistry — discovers, loads, and hot-reloads GridWidget subclasses."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
import sys
from pathlib import Path
from types import ModuleType

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

    Hot-reload
    ----------
    ``reload_file(path)`` syntax-checks and re-imports a single source file,
    returning the list of updated widget IDs (or an error string).
    ``get_watched_paths()`` returns all source file paths for file-watching.
    """

    def __init__(self, user_widget_dir: Path):
        self._user_dir = user_widget_dir
        self._widgets: dict[str, type[GridWidget]] = {}  # id → class
        self._load_errors: dict[str, str] = {}           # filename → error
        # Hotswap tracking
        self._id_to_module: dict[str, ModuleType] = {}   # widget_id → module
        self._file_to_ids: dict[str, list[str]] = {}     # abs_path → [widget_ids]

    def discover(self) -> None:
        """Scan builtin/ package and user_widget_dir for GridWidget subclasses."""
        self._widgets.clear()
        self._load_errors.clear()
        self._id_to_module.clear()
        self._file_to_ids.clear()

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
            mod_name = f"_user_widget_{path.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create module spec from {path}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod  # enable importlib.reload later
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

    def _register_from_module(self, mod: ModuleType) -> list[type[GridWidget]]:
        """Inspect a module for GridWidget subclasses and register them."""
        found: list[type[GridWidget]] = []
        src = getattr(mod, "__file__", "") or ""
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
                self._id_to_module[obj.WIDGET_ID] = mod
                if src:
                    ids = self._file_to_ids.setdefault(src, [])
                    if obj.WIDGET_ID not in ids:
                        ids.append(obj.WIDGET_ID)
                found.append(obj)
        return found

    # --- Hot-reload ---

    def get_watched_paths(self) -> list[str]:
        """Return all source file paths that can be hot-reloaded."""
        return list(self._file_to_ids.keys())

    def reload_file(self, file_path: str) -> tuple[list[str], str]:
        """Syntax-check and reload widget(s) from a changed source file.

        Returns ``(updated_widget_ids, error_string)``.
        *error_string* is empty on success.  On failure the old classes remain
        registered so existing widget instances keep working.
        """
        abs_path = str(Path(file_path).resolve())

        # 1. Syntax check (fast-fail before touching modules)
        try:
            source = Path(abs_path).read_text(encoding="utf-8")
            compile(source, abs_path, "exec")
        except SyntaxError as e:
            return [], f"Line {e.lineno}: {e.msg}"
        except OSError as e:
            return [], str(e)

        # 2. Find old widget IDs and their module
        old_ids = list(self._file_to_ids.get(abs_path, []))
        old_mod: ModuleType | None = None
        for wid in old_ids:
            old_mod = self._id_to_module.get(wid)
            if old_mod:
                break

        # 3. Try reload FIRST — keep old classes if this fails
        try:
            if old_mod and old_mod.__name__ in sys.modules:
                new_mod = importlib.reload(old_mod)
            else:
                mod_name = f"_user_widget_{Path(abs_path).stem}"
                spec = importlib.util.spec_from_file_location(mod_name, abs_path)
                if spec is None or spec.loader is None:
                    return [], f"Cannot create module spec for {abs_path}"
                new_mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = new_mod
                spec.loader.exec_module(new_mod)  # type: ignore[union-attr]
        except Exception as e:
            return [], str(e)

        # 4. Success — swap registrations
        for wid in old_ids:
            self._widgets.pop(wid, None)
            self._id_to_module.pop(wid, None)
        self._file_to_ids.pop(abs_path, None)

        found = self._register_from_module(new_mod)
        new_ids = [cls.WIDGET_ID for cls in found]
        return new_ids, ""

    # --- Queries ---

    def get_all(self) -> list[type[GridWidget]]:
        """Return all registered widget classes sorted by display name."""
        return sorted(self._widgets.values(), key=lambda c: c.DISPLAY_NAME)

    def get_by_id(self, widget_id: str) -> type[GridWidget] | None:
        return self._widgets.get(widget_id)

    def get_load_errors(self) -> dict[str, str]:
        """Return {filename: error_message} for files that failed to load."""
        return dict(self._load_errors)
