#!/usr/bin/env python3
"""Write the offline HTML: ``python Dashboard/export_html.py [--out PATH]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard import charts, export, paths  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the self-contained HTML version of the tracker.")
    parser.add_argument(
        "--out",
        type=Path,
        default=paths.DIST / "indonesia-indicators.html",
        help="where to write the file (default: Dashboard/dist/indonesia-indicators.html)",
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="omit the <html>/<head>/<body> skeleton (for hosts that add their own)",
    )
    args = parser.parse_args(argv)
    bundle = charts.load_bundle()
    payload = export.build_offline_html(bundle, standalone=not args.fragment)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(f"wrote {args.out} ({len(payload) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
