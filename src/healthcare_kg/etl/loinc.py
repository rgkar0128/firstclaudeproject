"""
LOINC loader.

Source: LOINC.csv from the LOINC download package.
Free registration required at https://loinc.org/downloads/

Relevant columns extracted:
  LOINC_NUM, COMPONENT, PROPERTY, TIME_ASPCT, SYSTEM,
  SCALE_TYP, METHOD_TYP, CLASS, CLASSTYPE, LONG_COMMON_NAME, STATUS
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .base import BaseLoader

_ACTIVE_STATUS = {"ACTIVE", "TRIAL", "DISCOURAGED"}

_CLASSTYPE_MAP = {
    "1": "Laboratory",
    "2": "Clinical",
    "3": "Claims attachments",
    "4": "Survey",
}


class LOINCLoader(BaseLoader):

    def load(self, path: Path) -> dict[str, int]:
        path = Path(path)
        self._validate_path(path, ".csv")

        df = pd.read_csv(
            path,
            dtype=str,
            usecols=[
                "LOINC_NUM",
                "COMPONENT",
                "PROPERTY",
                "TIME_ASPCT",
                "SYSTEM",
                "SCALE_TYP",
                "METHOD_TYP",
                "CLASS",
                "CLASSTYPE",
                "LONG_COMMON_NAME",
                "STATUS",
            ],
            low_memory=False,
        )

        # Keep active/trial codes only
        df = df[df["STATUS"].str.upper().isin(_ACTIVE_STATUS)].copy()
        df.fillna("", inplace=True)

        nodes = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="LOINC"):
            nodes.append(
                {
                    "loinc_num": row["LOINC_NUM"].strip(),
                    "long_common_name": row["LONG_COMMON_NAME"].strip(),
                    "component": row["COMPONENT"].strip(),
                    "property": row["PROPERTY"].strip(),
                    "time_aspect": row["TIME_ASPCT"].strip(),
                    "system": row["SYSTEM"].strip(),
                    "scale": row["SCALE_TYP"].strip(),
                    "method": row["METHOD_TYP"].strip(),
                    "class": row["CLASS"].strip(),
                    "class_type": _CLASSTYPE_MAP.get(row["CLASSTYPE"].strip(), ""),
                }
            )

        n_nodes = self.client.batch_merge_nodes("LabTest", "loinc_num", nodes)

        # IS_A relationships based on CLASS hierarchy (class → parent class via dot notation)
        rels = []
        seen_classes: dict[str, str] = {}  # class_name → representative loinc_num

        for node in nodes:
            cls = node["class"]
            loinc = node["loinc_num"]
            if cls and cls not in seen_classes:
                seen_classes[cls] = loinc

        # Build class→parent edges from dot-separated class names (e.g. HEM/BC → HEM)
        class_rels = []
        for cls in seen_classes:
            parts = cls.split(".")
            if len(parts) > 1:
                parent_cls = ".".join(parts[:-1])
                if parent_cls in seen_classes:
                    class_rels.append(
                        {
                            "src_key": seen_classes[cls],
                            "tgt_key": seen_classes[parent_cls],
                        }
                    )

        n_rels = self.client.batch_merge_relationships(
            "LabTest", "loinc_num", "IS_A", "LabTest", "loinc_num", class_rels
        )
        return {"nodes": n_nodes, "relationships": n_rels}
