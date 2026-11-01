"""Tests for app/streamlit_app.py imports and Report page safety."""

from __future__ import annotations

import ast
import builtins
import json
from pathlib import Path
import symtable
import sys
from typing import Dict, List, Set

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "streamlit_app.py"

BUILTIN_NAMES: Set[str] = set(dir(builtins)) | {
    "__file__",
    "__name__",
    "__doc__",
    "__package__",
    "__spec__",
    "__annotations__",
    "__path__",
    "__builtins__",
}


def find_undefined_names(path: Path) -> Dict[str, List[int]]:
    """Analyze a python file to find names loaded without being defined, imported, builtin, or local.

    Returns a dict mapping undefined name to a list of line numbers where it is loaded.
    """
    code = path.read_text(encoding="utf-8")
    st = symtable.symtable(code, str(path), "exec")

    top_defs: Set[str] = set()
    for sym in st.get_symbols():
        if sym.is_assigned() or sym.is_imported() or sym.is_namespace():
            top_defs.add(sym.get_name())

    def _walk_table(table: symtable.SymbolTable, globals_seen: Set[str]) -> Set[str]:
        undef: Set[str] = set()
        is_top = (table.get_type() == "module")
        for sym in table.get_symbols():
            name = sym.get_name()
            if is_top:
                if not (sym.is_assigned() or sym.is_imported() or sym.is_namespace()):
                    if name not in BUILTIN_NAMES:
                        undef.add(name)
            else:
                if sym.is_global():
                    if name not in globals_seen and name not in BUILTIN_NAMES:
                        undef.add(name)
        for child in table.get_children():
            undef.update(_walk_table(child, globals_seen))
        return undef

    undefined = _walk_table(st, top_defs)
    if not undefined:
        return {}

    tree = ast.parse(code, filename=str(path))
    result: Dict[str, List[int]] = {name: [] for name in sorted(undefined)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in result:
                result[node.id].append(node.lineno)
    return result


ALL_PY_FILES = sorted(
    list((ROOT / "app").rglob("*.py")) + list((ROOT / "src").rglob("*.py")),
    key=lambda p: str(p.relative_to(ROOT)),
)


def test_streamlit_app_has_no_undefined_names():
    """Verify that app/streamlit_app.py has no undefined names loaded."""
    assert APP_PATH.exists(), f"{APP_PATH} does not exist"
    undefined = find_undefined_names(APP_PATH)
    assert not undefined, f"Undefined names found in {APP_PATH.name}: {undefined}"


@pytest.mark.parametrize("py_file", ALL_PY_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_all_app_and_src_files_have_no_undefined_names(py_file: Path):
    """Check every .py file in app/ and src/ for undefined names."""
    undefined = find_undefined_names(py_file)
    assert not undefined, f"Undefined names found in {py_file.relative_to(ROOT)}: {undefined}"


@pytest.mark.slow
def test_apptest_report_click_accept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run the Report page on call_101 via AppTest and click Accept on a finding without exception."""
    from streamlit.testing.v1 import AppTest
    import src.audit.review as review_module

    reviews_tmp = tmp_path / "reviews"
    reviews_tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(review_module, "REVIEWS_DIR", reviews_tmp)

    if str((ROOT / "app").resolve()) not in sys.path:
        sys.path.insert(0, str((ROOT / "app").resolve()))
    from streamlit_app import get_report_by_id

    rep = get_report_by_id("call_101")
    assert rep is not None, "Sample audit call_101 could not be loaded from data/cache/audits"
    assert len(rep.findings) > 0, "call_101 has no findings to review"

    at = AppTest.from_file(str(APP_PATH))
    at.session_state["nav"] = "Report"
    at.session_state["report"] = rep
    at.run(timeout=30)
    assert len(at.exception) == 0, f"Exceptions on initial load: {at.exception}"

    accept_btns = [b for b in at.button if b.label == "Accept"]
    assert len(accept_btns) > 0, "No Accept button found on Report page"
    target_btn = accept_btns[0]

    target_btn.click()
    at.run(timeout=30)
    assert len(at.exception) == 0, f"Exceptions after clicking Accept: {at.exception}"

    review_file = reviews_tmp / f"{rep.call_id}.json"
    assert review_file.exists(), f"Expected review file was not written to {review_file}"
    review_data = json.loads(review_file.read_text(encoding="utf-8"))
    assert review_data.get("call_id") == rep.call_id
    assert len(review_data.get("reviews", {})) > 0
