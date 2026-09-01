"""Entry point for `python -m benchmark.metrics` (Issue #90).

See benchmark/runner/__main__.py's own docstring for why this exact
sys.path insertion exists - identical reasoning, for a second top-level
CLI entry point. Nothing in benchmark/metrics/ directly imports from
app.* (matching/scoring operate on the plain dicts predictions.jsonl
already contains), but benchmark.loader.load_cases()'s own optional,
lazy `from app.ai.schemas import ClinicalSummary` validation (see
loader.py) only actually runs when backend/ is reachable - this ensures
it is, the same way it already is under pytest (pytest.ini's
pythonpath = .) and under `python -m benchmark.runner`.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from benchmark.metrics.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
