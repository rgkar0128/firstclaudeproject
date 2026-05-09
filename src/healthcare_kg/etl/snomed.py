"""
SNOMED CT loader.

Source: SNOMED CT International Edition RF2 Snapshot release.
Requires a UMLS/SNOMED license. Download via NLM UMLS or SNOMED International.

Expected files (in the Snapshot/Terminology directory):
  sct2_Concept_Snapshot_INT_<date>.txt
  sct2_Description_Snapshot-en_INT_<date>.txt
  sct2_Relationship_Snapshot_INT_<date>.txt

Cross-ontology map refsets (in Snapshot/Refset/Map):
  der2_iisssccRefset_ExtendedMapSnapshot_INT_<date>.txt  — SNOMED→ICD-10

SNOMED concept identifiers used:
  116680003 — Is a (relationship type)
  900000000000003001 — Fully specified name (description type)
  900000000000013009 — Synonym (description type)
  900000000000548007 — Preferred (acceptability)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .base import BaseLoader

_IS_A_TYPE = "116680003"
_FSN_TYPE = "900000000000003001"

_SEMANTIC_TAG_RE = re.compile(r"\(([^)]+)\)$")


class SNOMEDLoader(BaseLoader):

    def load(self, path: Path) -> dict[str, int]:
        path = Path(path)
        self._validate_path(path)

        snap_dir = self._find_snapshot_dir(path)
        term_dir = snap_dir / "Terminology"

        concept_file = self._find_file(term_dir, "sct2_Concept_Snapshot")
        desc_file = self._find_file(term_dir, "sct2_Description_Snapshot")
        rel_file = self._find_file(term_dir, "sct2_Relationship_Snapshot")

        concepts_df = self._load_concepts(concept_file)
        descriptions = self._load_descriptions(desc_file, set(concepts_df["id"]))
        nodes = self._build_nodes(concepts_df, descriptions)

        n_nodes = self.client.batch_merge_nodes("ClinicalConcept", "sctid", nodes)

        rels = self._load_is_a_rels(rel_file, {n["sctid"] for n in nodes})
        n_rels = self.client.batch_merge_relationships(
            "ClinicalConcept", "sctid", "IS_A", "ClinicalConcept", "sctid", rels
        )

        # Optional: load cross-ontology ICD-10 map if present
        n_maps = 0
        map_dir = snap_dir / "Refset" / "Map"
        if map_dir.exists():
            n_maps = self._load_icd10_map(map_dir, {n["sctid"] for n in nodes})

        return {"nodes": n_nodes, "relationships": n_rels + n_maps}

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _load_concepts(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
        return df[df["active"] == "1"][["id", "definitionStatusId"]].copy()

    def _load_descriptions(self, path: Path, active_ids: set[str]) -> dict[str, dict]:
        """Returns {sctid: {fsn, preferred_term, semantic_tag}}."""
        df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
        df = df[(df["active"] == "1") & (df["conceptId"].isin(active_ids))].copy()

        result: dict[str, dict] = {}
        for _, row in df.iterrows():
            sctid = row["conceptId"]
            term = row["term"]
            type_id = row["typeId"]

            if sctid not in result:
                result[sctid] = {"fsn": "", "preferred_term": "", "semantic_tag": ""}

            if type_id == _FSN_TYPE:
                result[sctid]["fsn"] = term
                m = _SEMANTIC_TAG_RE.search(term)
                result[sctid]["semantic_tag"] = m.group(1) if m else ""
            elif not result[sctid]["preferred_term"]:
                result[sctid]["preferred_term"] = term

        return result

    def _build_nodes(self, concepts_df: pd.DataFrame, descriptions: dict) -> list[dict]:
        nodes = []
        for _, row in tqdm(concepts_df.iterrows(), total=len(concepts_df), desc="SNOMED concepts"):
            sctid = row["id"]
            desc = descriptions.get(sctid, {})
            fsn = desc.get("fsn", "")
            nodes.append({
                "sctid": sctid,
                "fsn": fsn,
                "preferred_term": desc.get("preferred_term", "") or fsn,
                "semantic_tag": desc.get("semantic_tag", ""),
            })
        return nodes

    def _load_is_a_rels(self, path: Path, valid_sctids: set[str]) -> list[dict]:
        df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
        df = df[
            (df["active"] == "1") &
            (df["typeId"] == _IS_A_TYPE)
        ].copy()

        rels = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="SNOMED IS_A"):
            src = row["sourceId"]
            tgt = row["destinationId"]
            if src in valid_sctids and tgt in valid_sctids:
                rels.append({"src_key": src, "tgt_key": tgt})
        return rels

    def _load_icd10_map(self, map_dir: Path, valid_sctids: set[str]) -> int:
        """Load SNOMED→ICD-10 extended map refset and create MAPS_TO edges."""
        map_file = self._find_file(map_dir, "ExtendedMap", required=False)
        if map_file is None:
            return 0

        df = pd.read_csv(map_file, sep="\t", dtype=str, low_memory=False)
        # Keep active, mapCategoryId indicates a valid 1:1 map (category 447637006 = map source properly classified)
        df = df[df["active"] == "1"].copy()

        rels = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="SNOMED→ICD-10 map"):
            sctid = row.get("referencedComponentId", "")
            icd_code = row.get("mapTarget", "")
            if sctid in valid_sctids and icd_code:
                rels.append({
                    "src_key": sctid,
                    "tgt_key": icd_code.strip(),
                    "map_type": "ICD-10-CM",
                })

        return self.client.batch_merge_relationships(
            "ClinicalConcept", "sctid", "MAPS_TO", "Diagnosis", "code",
            rels, rel_props=["map_type"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_snapshot_dir(self, path: Path) -> Path:
        if (path / "Snapshot").exists():
            return path / "Snapshot"
        if path.name == "Snapshot":
            return path
        # Walk up one level
        candidate = path.parent / "Snapshot"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Cannot locate Snapshot directory under {path}")

    def _find_file(self, directory: Path, prefix: str, required: bool = True) -> Path | None:
        matches = list(directory.glob(f"{prefix}*.txt"))
        if not matches:
            if required:
                raise FileNotFoundError(f"No file matching '{prefix}*.txt' in {directory}")
            return None
        return matches[0]
