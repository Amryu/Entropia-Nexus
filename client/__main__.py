import sys
import traceback

from .app import main

try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    input("Press Enter to exit...")
    sys.exit(1)
