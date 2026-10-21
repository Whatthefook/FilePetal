# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FilePetal (legacy tangerine.spec alias)."""

import os
import sys

# Forward to filepetal.spec
spec_dir = os.path.dirname(os.path.abspath(SPEC_DIR if 'SPEC_DIR' in locals() else __file__))
filepetal_spec = os.path.join(spec_dir, "filepetal.spec")
with open(filepetal_spec, "r", encoding="utf-8") as f:
    code = f.read()
exec(code)
