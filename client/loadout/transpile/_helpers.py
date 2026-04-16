"""Hand-written Python ports of helpers from JS files that are not
themselves transpiled (e.g. `nexus/src/lib/util.js`).

The pipeline copies this file into `client/loadout/generated/_helpers.py`.
Generated modules import from it via the `$lib/util.js` mapping in the
pipeline's import map.

Keep functions here minimal and mirror the JS semantics 1:1. When a JS
util function gets touched, update the Python port alongside it — the
parity tests in `test_transpile_parity.py` are the safety net.
"""

from __future__ import annotations

import re
from typing import Any

from ._runtime import is_nullish


def hasItemTag(currentName: Any, tag: Any) -> bool:
    """Return True if `currentName` ends with `(..., tag, ...)`.

    Mirrors `hasItemTag` in `nexus/src/lib/util.js`. Names look like
    "Mayhem Rifle (L)" or "Weapon (L,ARMATRIX)"; we pull the comma-
    separated tag list out of the trailing parenthesised block.
    """
    if is_nullish(currentName) or not currentName:
        return False
    match = re.match(r"^(.*) \((.*)\)$", str(currentName))
    existing_tags = match.group(2).split(",") if match else []
    return str(tag) in existing_tags
