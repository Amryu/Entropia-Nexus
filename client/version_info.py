"""Generate a PyInstaller version info file from client/VERSION.

Called by build.sh to produce a temporary .txt file that PyInstaller's
--version-file flag embeds into the Windows exe resources.

Usage:  python client/version_info.py > client/build/version_info.txt
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VERSION_STR = open(os.path.join(_HERE, "VERSION")).read().strip()
_PARTS = (_VERSION_STR + ".0.0.0").split(".")[:4]
_VER_TUPLE = ", ".join(_PARTS)

print(f"""\
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({_VER_TUPLE}),
    prodvers=({_VER_TUPLE}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Entropia Nexus'),
         StringStruct(u'FileDescription', u'Entropia Nexus Client'),
         StringStruct(u'FileVersion', u'{_VERSION_STR}'),
         StringStruct(u'InternalName', u'entropia-nexus'),
         StringStruct(u'OriginalFilename', u'entropia-nexus.exe'),
         StringStruct(u'ProductName', u'Entropia Nexus Client'),
         StringStruct(u'ProductVersion', u'{_VERSION_STR}')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)""")
