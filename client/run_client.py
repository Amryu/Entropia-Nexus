"""PyInstaller entry point for the Entropia Nexus client."""

import os
import sys

# When frozen, set working directory to the executable's directory
# so config.json and data/ resolve next to the exe
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from client.app import main

main()
