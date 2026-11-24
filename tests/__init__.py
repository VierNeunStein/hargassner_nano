"""Tests for the parts of the integration that do not need Home Assistant.

Run them from the repository root with either of::

    python -m unittest discover -s tests -t .
    pytest

The integration's ``__init__`` imports Home Assistant. To test the protocol code on a
machine without it, the package is registered here without running ``__init__``.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "custom_components" / "hargassner_nano"
PACKAGE = "custom_components.hargassner_nano"


def _register_package() -> None:
    if PACKAGE in sys.modules:
        return
    parent = sys.modules.get("custom_components")
    if parent is None:
        parent = types.ModuleType("custom_components")
        parent.__path__ = [str(ROOT / "custom_components")]
        sys.modules["custom_components"] = parent
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(COMPONENT_DIR)]
    sys.modules[PACKAGE] = package


_register_package()
