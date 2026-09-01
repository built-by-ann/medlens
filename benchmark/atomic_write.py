"""Shared atomic JSON file writing for benchmark/ tooling.

Extracted out of runner/storage.py (Issue #89) when metrics/io.py (Issue
#90) needed the exact same behavior, rather than duplicating it; the
same reasoning app/ai/providers/text_cleanup.py was extracted for.
Behavior is unchanged from runner/storage.py's original inline version:
written to a temporary file in the destination's own directory, then
moved into place with os.replace(), so a reader (or a crash between the
write and the rename) never observes a half-written file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str) -> None:
    """Same crash-safety guarantee as atomic_write_json, for a plain text
    file (report.md, a .svg figure) rather than a JSON document. Added
    for benchmark/report/ (Issue #91), which writes both.
    """
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
