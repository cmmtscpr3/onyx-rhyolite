#!/usr/bin/env python3
"""Entry point: ``python Collectors/run.py <indicator>``.

A thin shim so the folder can keep its capitalised name while the importable
package stays lower-case.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
