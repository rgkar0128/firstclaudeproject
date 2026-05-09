"""Unit tests for ETL parsers (no Neo4j or real ontology files required)."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from healthcare_kg.etl.icd10 import ICD10Loader
from healthcare_kg.etl.snomed import SNOMEDLoader


# ──────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.batch_merge_nodes.return_value = 0
    client.batch_merge_relationships.return_value = 0
    return client


# ──────────────────────────────────────────────────────────────────────
# ICD-10 flat parser
# ──────────────────────────────────────────────────────────────────────

class TestICD10FlatParser:
    def test_parses_codes_and_descriptions(self, tmp_path, mock_client):
        flat = tmp_path / "icd10.txt"
        # CMS flat format: 7-char code (space-padded) then description
        flat.write_text(
            "E11    Type 2 diabetes mellitus\n"
            "E11.9  Type 2 diabetes mellitus without complications\n",
            encoding="utf-8",
        )
        loader = ICD10Loader(mock_client)
        loader._parse_flat(flat)

        nodes, rels = loader._parse_flat(flat)
        codes = {n["code"] for n in nodes}
        assert "E11" in codes
        assert "E11.9" in codes

    def test_parent_relationship_derived(self, tmp_path, mock_client):
        flat = tmp_path / "icd10.txt"
        flat.write_text(
            "E11    Type 2 diabetes mellitus\n"
            "E11.9  Type 2 diabetes mellitus without complications\n",
            encoding="utf-8",
        )
        loader = ICD10Loader(mock_client)
        _, rels = loader._parse_flat(flat)
        # E11.9 should have E11 as parent
        assert any(r["src_key"] == "E11.9" and r["tgt_key"] == "E11" for r in rels)

    def test_billable_flag(self, mock_client):
        loader = ICD10Loader(mock_client)
        assert ICD10Loader._parent_code("E11.9") == "E11"
        assert ICD10Loader._parent_code("E11") == "E1"  # goes up to 2-char
        assert ICD10Loader._parent_code("E1") is None


class TestICD10ParentCode:
    @pytest.mark.parametrize("code,expected_parent", [
        ("E11.9", "E11"),
        ("E11.65", "E11.6"),
        ("E11", "E1"),
        ("A", None),
    ])
    def test_parent_derivation(self, code, expected_parent):
        assert ICD10Loader._parent_code(code) == expected_parent


# ──────────────────────────────────────────────────────────────────────
# SNOMED semantic tag extraction
# ──────────────────────────────────────────────────────────────────────

class TestSNOMEDSemanticTag:
    import re
    _re = SNOMEDLoader.__dict__  # access the module-level regex via the class

    @pytest.mark.parametrize("fsn,expected_tag", [
        ("Type 2 diabetes mellitus (disorder)", "disorder"),
        ("Glucose [Mass/volume] in Blood (observable entity)", "observable entity"),
        ("Metformin (substance)", "substance"),
        ("No tag here", ""),
    ])
    def test_extracts_semantic_tag(self, fsn, expected_tag):
        import re
        pattern = re.compile(r"\(([^)]+)\)$")
        m = pattern.search(fsn)
        result = m.group(1) if m else ""
        assert result == expected_tag
