"""Basic smoke tests for project structure and imports."""

import os
import yaml
from pathlib import Path

def test_rubric_exists_and_valid():
    rubric_path = Path(__file__).resolve().parent.parent / "data" / "rubric.yaml"
    assert rubric_path.exists(), "data/rubric.yaml must exist"
    with open(rubric_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "categories" in data
    assert "scoring_formula" in data
    assert "grade_scale" in data
    assert "sop_steps" in data

def test_policies_exist():
    policies_dir = Path(__file__).resolve().parent.parent / "data" / "policies"
    assert policies_dir.exists()
    md_files = list(policies_dir.glob("*.md"))
    assert len(md_files) >= 6

def test_sops_exist():
    sops_dir = Path(__file__).resolve().parent.parent / "data" / "sops"
    assert sops_dir.exists()
    md_files = list(sops_dir.glob("*.md"))
    assert len(md_files) >= 4
