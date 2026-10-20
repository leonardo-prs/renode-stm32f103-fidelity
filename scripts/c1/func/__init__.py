"""Catálogo funcional do C1 (preset c1-func): um módulo por grupo, como em src/c1/func/."""
from __future__ import annotations

from importlib import import_module

GROUPS = ("fa", "fl", "fs", "fm", "fd", "fq", "fb", "fc", "fmem", "fal", "fbb", "fex")

FORMS = []
DERIVED: dict = {}
for _g in GROUPS:
    _m = import_module(f".{_g}", __name__)
    FORMS += _m.FORMS
    DERIVED.update(getattr(_m, "DERIVED", {}))

_names = [f.name for f in FORMS]
if len(set(_names)) != len(_names):
    raise ValueError("nomes de forma repetidos no catálogo funcional")
for _f in FORMS:
    _f.check()
