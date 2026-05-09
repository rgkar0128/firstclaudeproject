"""
RxNorm loader.

Source: RxNorm Full Release (RRF format) from NLM.
Free download at https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html

Required files (inside the rrf/ subdirectory of the release):
  RXNCONSO.RRF  — concepts
  RXNREL.RRF    — relationships

Term types (tty) loaded:
  IN  — ingredient
  PIN — precise ingredient
  BN  — brand name
  SCD — semantic clinical drug
  SBD — semantic branded drug
  SCDF — semantic clinical drug form
  SBDF — semantic branded drug form
  SCDG — semantic clinical drug group
  SBDG — semantic branded drug group

Relationships loaded from RXNREL:
  isa           → IS_A
  has_ingredient → HAS_INGREDIENT
  tradename_of  → (skipped — BN edges are very dense; add if needed)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .base import BaseLoader

_WANTED_TTY = {
    "IN", "PIN", "BN", "SCD", "SBD",
    "SCDF", "SBDF", "SCDG", "SBDG",
}

_REL_MAP = {
    "isa": "IS_A",
    "has_ingredient": "HAS_INGREDIENT",
    "inverse_isa": None,
}

_RXNCONSO_COLS = ["RXCUI", "LAT", "TS", "LUI", "STT", "SUI", "ISPREF", "RXAUI",
                  "SAUI", "SCUI", "SDUI", "SAB", "TTY", "CODE", "STR", "SRL",
                  "SUPPRESS", "CVF"]

_RXNREL_COLS = ["RXCUI1", "RXAUI1", "STYPE1", "REL", "RXCUI2", "RXAUI2",
                "STYPE2", "RELA", "RUI", "SRUI", "SAB", "SL", "DIR",
                "RG", "SUPPRESS", "CVF"]


class RxNormLoader(BaseLoader):

    def load(self, path: Path) -> dict[str, int]:
        path = Path(path)
        self._validate_path(path)

        rrf_dir = path if path.is_dir() else path.parent
        conso_path = rrf_dir / "RXNCONSO.RRF"
        rel_path = rrf_dir / "RXNREL.RRF"

        for p in (conso_path, rel_path):
            if not p.exists():
                raise FileNotFoundError(f"Required RxNorm file not found: {p}")

        nodes = self._load_concepts(conso_path)
        n_nodes = self.client.batch_merge_nodes("Drug", "rxcui", nodes)

        valid_cuis = {n["rxcui"] for n in nodes}
        rels = self._load_relationships(rel_path, valid_cuis)

        n_isa = self.client.batch_merge_relationships(
            "Drug", "rxcui", "IS_A", "Drug", "rxcui",
            [r for r in rels if r["rel_type"] == "IS_A"],
        )
        n_ingr = self.client.batch_merge_relationships(
            "Drug", "rxcui", "HAS_INGREDIENT", "Drug", "rxcui",
            [r for r in rels if r["rel_type"] == "HAS_INGREDIENT"],
        )
        return {"nodes": n_nodes, "relationships": n_isa + n_ingr}

    def _load_concepts(self, path: Path) -> list[dict]:
        df = pd.read_csv(
            path, sep="|", header=None, names=_RXNCONSO_COLS,
            dtype=str, index_col=False, low_memory=False,
        )
        # Keep only RxNorm source atoms that are preferred English terms
        df = df[
            (df["SAB"] == "RXNORM") &
            (df["LAT"] == "ENG") &
            (df["TTY"].isin(_WANTED_TTY)) &
            (df["SUPPRESS"] == "N")
        ].copy()

        # One preferred name per RXCUI (ISPREF == 'Y' first, else first row)
        df = df.sort_values("ISPREF", ascending=False).drop_duplicates("RXCUI")

        nodes = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="RxNorm concepts"):
            nodes.append({
                "rxcui": row["RXCUI"].strip(),
                "name": row["STR"].strip(),
                "tty": row["TTY"].strip(),
            })
        return nodes

    def _load_relationships(self, path: Path, valid_cuis: set[str]) -> list[dict]:
        df = pd.read_csv(
            path, sep="|", header=None, names=_RXNREL_COLS,
            dtype=str, index_col=False, low_memory=False,
        )
        df = df[
            (df["SAB"] == "RXNORM") &
            (df["RELA"].isin(_REL_MAP)) &
            (df["SUPPRESS"] == "N")
        ].copy()

        rels = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="RxNorm relationships"):
            rel_type = _REL_MAP.get(row["RELA"])
            if rel_type is None:
                continue
            src = row["RXCUI1"].strip()
            tgt = row["RXCUI2"].strip()
            if src in valid_cuis and tgt in valid_cuis:
                rels.append({"src_key": src, "tgt_key": tgt, "rel_type": rel_type})
        return rels
