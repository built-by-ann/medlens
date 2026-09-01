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


def atomic_write_json(path: Path, data: Any) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise
