"""Tests for app/streamlit_app.py imports and Report page safety."""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "streamlit_app.py"


def test_required_audit_functions_imported_or_defined():
    """Verify that key functions called from src.audit.* in streamlit_app.py are imported or defined."""
    assert APP_PATH.exists(), f"{APP_PATH} does not exist"
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))

    # Names of functions/utilities called in app/streamlit_app.py from src.audit.*
    audit_functions_called = [
        "apply_reviews_to_report",
        "render_player_component",
        "resolve_audio_path",
        "get_involved_clause_ids",
        "load_transcript_json",
        "find_transcripts",
    ]

    # Collect all imported names and defined names in the file
    available_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                available_names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                available_names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            available_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    available_names.add(target.id)

    missing = [fn for fn in audit_functions_called if fn not in available_names]
    assert not missing, f"Functions called in streamlit_app.py but not imported or defined: {missing}"
