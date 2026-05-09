"""
ICD-10-CM loader.

Supported source formats (auto-detected):
  1. CMS flat text file  — icd10cm_codes_YYYY.txt
     Format: <7-char code padded with spaces><description>
  2. CMS tabular XML     — icd10cm_tabular_YYYY.xml
     Preserves chapter/section hierarchy.

Download from: https://www.cms.gov/medicare/coding-billing/icd-10-codes
"""

from __future__ import annotations

import re
from pathlib import Path
from lxml import etree
from tqdm import tqdm

from .base import BaseLoader


class ICD10Loader(BaseLoader):

    def load(self, path: Path) -> dict[str, int]:
        path = Path(path)
        self._validate_path(path)

        if path.suffix.lower() == ".xml":
            nodes, rels = self._parse_xml(path)
        else:
            nodes, rels = self._parse_flat(path)

        n_nodes = self.client.batch_merge_nodes("Diagnosis", "code", nodes)
        n_rels = self.client.batch_merge_relationships(
            "Diagnosis", "code", "IS_A", "Diagnosis", "code", rels
        )
        return {"nodes": n_nodes, "relationships": n_rels}

    # ------------------------------------------------------------------
    # Flat text format
    # ------------------------------------------------------------------

    def _parse_flat(self, path: Path) -> tuple[list[dict], list[dict]]:
        nodes: list[dict] = []
        rels: list[dict] = []

        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in tqdm(fh, desc="ICD-10 flat"):
                line = line.rstrip("\n")
                if len(line) < 8:
                    continue
                code = line[:7].rstrip()
                description = line[7:].strip()
                if not code:
                    continue

                parent = self._parent_code(code)
                nodes.append(
                    {
                        "code": code,
                        "description": description,
                        "billable": len(code.replace(".", "")) >= 4,
                        "chapter": "",
                    }
                )
                if parent:
                    rels.append({"src_key": code, "tgt_key": parent})

        return nodes, rels

    # ------------------------------------------------------------------
    # Tabular XML format
    # ------------------------------------------------------------------

    def _parse_xml(self, path: Path) -> tuple[list[dict], list[dict]]:
        nodes: list[dict] = []
        rels: list[dict] = []

        tree = etree.parse(str(path))
        root = tree.getroot()

        for chapter in tqdm(root.findall(".//chapter"), desc="ICD-10 XML chapters"):
            chapter_name = (chapter.findtext("name") or "").strip()
            chapter_desc = (chapter.findtext("desc") or "").strip()
            chapter_label = f"{chapter_name}: {chapter_desc}"

            for diag in chapter.iter("diag"):
                code = (diag.findtext("name") or "").strip()
                description = (diag.findtext("desc") or "").strip()
                if not code:
                    continue

                parent = self._parent_code(code)
                nodes.append(
                    {
                        "code": code,
                        "description": description,
                        "chapter": chapter_label,
                        "billable": self._is_billable(diag),
                    }
                )
                if parent:
                    rels.append({"src_key": code, "tgt_key": parent})

        return nodes, rels

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parent_code(code: str) -> str | None:
        """Derive the parent code by one level of specificity."""
        code = code.strip()
        if "." in code:
            parts = code.split(".")
            if len(parts[1]) > 1:
                return parts[0] + "." + parts[1][:-1]
            return parts[0]
        if len(code) > 3:
            return code[:3]
        return None

    @staticmethod
    def _is_billable(diag_elem: etree._Element) -> bool:
        return len(diag_elem.findall("diag")) == 0
