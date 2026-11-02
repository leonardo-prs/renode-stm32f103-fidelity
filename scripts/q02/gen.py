"""Gera build/q02/gen/q02_spec.h a partir de spec.py (chamado pelo CMake)."""
from __future__ import annotations

from pathlib import Path

from . import spec


def write(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "q02_spec.h"
    text = spec.header()
    if not p.is_file() or p.read_text() != text:
        p.write_text(text)
