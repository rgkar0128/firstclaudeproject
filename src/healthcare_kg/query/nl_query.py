"""
Natural language query layer.

Flow:
  1. User asks a natural language question.
  2. Claude generates a Cypher query using the graph schema as context.
  3. The query runs against Neo4j.
  4. Claude summarizes the raw results into a readable answer.

Claude API usage:
  - First call: NL → Cypher  (uses prompt caching on the schema system prompt)
  - Second call: results → summary
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from healthcare_kg.graph.neo4j_client import Neo4jClient
from healthcare_kg.graph.schema import SCHEMA_DESCRIPTION

_MODEL = "claude-sonnet-4-6"

_CYPHER_SYSTEM = f"""You are an expert in Neo4j Cypher and healthcare ontologies.
Given a natural language question, generate a valid Cypher query for the following graph schema.

{SCHEMA_DESCRIPTION}

Rules:
- Return ONLY the raw Cypher query, no markdown, no explanation.
- Limit results to 25 rows unless the user asks for more.
- Use case-insensitive matching with toLower() for string comparisons.
- Prefer MATCH + WHERE over label-only scans for large graphs.
- Do not use deprecated Cypher syntax.
"""

_SUMMARY_SYSTEM = """You are a clinical knowledge assistant.
Given a user question and raw graph query results (as JSON), produce a clear, concise answer.
- Use plain language suitable for a healthcare professional.
- If the results are empty, say so explicitly.
- Do not fabricate information not present in the results.
"""


class NLQueryEngine:
    def __init__(self, neo4j_client: Neo4jClient, anthropic_api_key: str) -> None:
        self._neo4j = neo4j_client
        self._claude = anthropic.Anthropic(api_key=anthropic_api_key)

    def ask(self, question: str) -> dict[str, Any]:
        """
        Ask a natural language question about the knowledge graph.
        Returns {"question", "cypher", "raw_results", "answer"}.
        """
        cypher = self._generate_cypher(question)
        try:
            raw_results = self._neo4j.run(cypher)
        except Exception as exc:
            return {
                "question": question,
                "cypher": cypher,
                "raw_results": [],
                "answer": f"Query execution failed: {exc}",
                "error": str(exc),
            }

        answer = self._summarize(question, raw_results)
        return {
            "question": question,
            "cypher": cypher,
            "raw_results": raw_results,
            "answer": answer,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_cypher(self, question: str) -> str:
        response = self._claude.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": _CYPHER_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text.strip()

    def _summarize(self, question: str, results: list[dict]) -> str:
        results_json = json.dumps(results, indent=2, default=str)
        prompt = (
            f"Question: {question}\n\n"
            f"Graph query results:\n{results_json}"
        )
        response = self._claude.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SUMMARY_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
