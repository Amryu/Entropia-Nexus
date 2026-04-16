# Import onnxruntime before any PyQt6 / Qt import. PyQt6 ships MSVC
# runtime DLLs that shadow onnxruntime_pybind11_state's dependencies;
# once Qt is loaded first, onnxruntime's C extension fails to init
# with "DLL initialization routine failed". Forcing ort to load first
# binds the correct DLLs into the process.
try:
    import onnxruntime  # noqa: F401
except Exception:
    pass

from .app import main

main()
