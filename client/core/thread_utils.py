"""Thread-safe helper to invoke callables on the Qt main thread."""

from PyQt6.QtCore import QObject, pyqtSignal


class _MainThreadInvoker(QObject):
    _call = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._execute)

    def _execute(self, fn):
        fn()


_invoker = _MainThreadInvoker()


def invoke_on_main(fn):
    """Queue *fn* for execution on the main thread. Safe from any thread."""
    _invoker._call.emit(fn)
