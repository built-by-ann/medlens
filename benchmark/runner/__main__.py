"""Entry point for `python -m benchmark.runner` (Issue #89).

benchmark/ is a top-level directory, a sibling of backend/ (see
benchmark/README.md); the production application under backend/app is
not on sys.path merely by running this from the repository root the way
`python -m benchmark.runner` does. This mirrors backend/tests/
test_benchmark_dataset.py's own explicit sys.path.insert() for crossing
the same repo-root/backend boundary in the other direction: one narrow,
well-commented insertion at the single entry point that needs it, not a
project-wide packaging change.

Must run before importing anything from benchmark.runner.cli (or any
other benchmark.runner module), since all of them import from app.ai.*
at module level.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from benchmark.runner.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
