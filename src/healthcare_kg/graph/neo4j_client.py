from __future__ import annotations

from typing import Any
from neo4j import GraphDatabase, Driver
from .schema import CONSTRAINTS, INDEXES


class Neo4jClient:
    def __init__(self, uri: str, username: str, password: str) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def apply_schema(self) -> None:
        with self._driver.session() as session:
            for stmt in CONSTRAINTS + INDEXES:
                session.run(stmt)

    def run(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def batch_merge_nodes(self, label: str, key: str, rows: list[dict]) -> int:
        """MERGE nodes in batches of 500, returns total merged count."""
        if not rows:
            return 0

        cypher = f"""
        UNWIND $rows AS row
        MERGE (n:{label} {{{key}: row.{key}}})
        SET n += row
        """
        total = 0
        for i in range(0, len(rows), 500):
            chunk = rows[i : i + 500]
            with self._driver.session() as session:
                session.run(cypher, {"rows": chunk})
            total += len(chunk)
        return total

    def batch_merge_relationships(
        self,
        src_label: str,
        src_key: str,
        rel_type: str,
        tgt_label: str,
        tgt_key: str,
        rows: list[dict],
        rel_props: list[str] | None = None,
    ) -> int:
        """MERGE relationships between existing nodes."""
        if not rows:
            return 0

        set_clause = ""
        if rel_props:
            assignments = ", ".join(f"r.{p} = row.{p}" for p in rel_props)
            set_clause = f"SET {assignments}"

        cypher = f"""
        UNWIND $rows AS row
        MATCH (src:{src_label} {{{src_key}: row.src_key}})
        MATCH (tgt:{tgt_label} {{{tgt_key}: row.tgt_key}})
        MERGE (src)-[r:{rel_type}]->(tgt)
        {set_clause}
        """
        total = 0
        for i in range(0, len(rows), 500):
            chunk = rows[i : i + 500]
            with self._driver.session() as session:
                session.run(cypher, {"rows": chunk})
            total += len(chunk)
        return total

    def node_count(self, label: str) -> int:
        result = self.run(f"MATCH (n:{label}) RETURN count(n) AS c")
        return result[0]["c"] if result else 0

    def stats(self) -> dict[str, int]:
        labels = ["Diagnosis", "LabTest", "Drug", "ClinicalConcept"]
        return {label: self.node_count(label) for label in labels}
