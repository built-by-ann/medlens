"""Entry point for `python -m benchmark.report` (Issue #91).

See benchmark/runner/__main__.py's and benchmark/metrics/__main__.py's
own docstrings for why this exact sys.path insertion exists; identical
reasoning, for a third top-level CLI entry point. benchmark.loader's own
optional, lazy `from app.ai.schemas import ClinicalSummary` validation
only actually runs when backend/ is reachable; this ensures it is.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from benchmark.report.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
