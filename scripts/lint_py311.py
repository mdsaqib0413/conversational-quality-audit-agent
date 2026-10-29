"""Catch Python 3.12-only f-string syntax that breaks on Python 3.11 (backslash or same-quote reuse inside {...}).

  python scripts/lint_py311.py          # exits 1 and lists problems
"""
import ast
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def problems(path: Path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.FormattedValue):
                    seg = ast.get_source_segment(src, v.value) or ""
                    if "\\" in seg:
                        out.append((v.lineno, "backslash inside an f-string expression", seg[:60]))
            # same quote type reused inside the braces: look at the raw f-string text
            raw = ast.get_source_segment(src, node) or ""
            if raw[:1] in "fF" or raw[:2].lower() in ("rf", "fr"):
                body = raw.lstrip("rRfF")
                q = body[:3] if body[:3] in ('"""', "'''") else body[:1]
                inner = body[len(q):-len(q)] if len(q) else body
                depth, i, cur = 0, 0, ""
                while i < len(inner):
                    ch = inner[i]
                    if inner[i:i + 2] in ("{{", "}}") and depth == 0:
                        i += 2
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}" and depth:
                        depth -= 1
                    elif depth and len(q) == 1 and ch == q:
                        out.append((node.lineno, f"same quote ({q}) used inside an f-string expression", inner[max(0, i - 25):i + 25]))
                        break
                    i += 1
    return out


def main() -> int:
    bad = 0
    for p in sorted(list(ROOT.glob("src/**/*.py")) + list(ROOT.glob("app/**/*.py")) + list(ROOT.glob("scripts/*.py")) + list(ROOT.glob("eval/*.py")) + list(ROOT.glob("tests/*.py"))):
        for line, msg, ctx in problems(p):
            print(f"{p.relative_to(ROOT)}:{line}: {msg}: {ctx!r}")
            bad += 1
    print("OK: no Python 3.11 f-string problems" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
