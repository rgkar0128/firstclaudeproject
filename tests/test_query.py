"""Unit tests for the NL query engine (mocked Claude and Neo4j)."""

from unittest.mock import MagicMock, patch

import pytest

from healthcare_kg.query.nl_query import NLQueryEngine


@pytest.fixture
def engine():
    neo4j_client = MagicMock()
    return NLQueryEngine(neo4j_client=neo4j_client, anthropic_api_key="test-key")


class TestNLQueryEngine:
    def test_ask_returns_expected_keys(self, engine):
        with (
            patch.object(engine, "_generate_cypher", return_value="MATCH (n:Diagnosis) RETURN n LIMIT 1"),
            patch.object(engine, "_summarize", return_value="One diagnosis found."),
        ):
            engine._neo4j.run.return_value = [{"n": {"code": "E11.9"}}]
            result = engine.ask("Find a diabetes code")

        assert set(result.keys()) >= {"question", "cypher", "raw_results", "answer"}
        assert result["answer"] == "One diagnosis found."

    def test_ask_handles_query_error_gracefully(self, engine):
        with patch.object(engine, "_generate_cypher", return_value="INVALID CYPHER"):
            engine._neo4j.run.side_effect = Exception("Cypher syntax error")
            result = engine.ask("bad question")

        assert "error" in result
        assert "failed" in result["answer"].lower()

    def test_ask_passes_question_through(self, engine):
        with (
            patch.object(engine, "_generate_cypher", return_value="MATCH (n) RETURN n LIMIT 1"),
            patch.object(engine, "_summarize", return_value="Summary."),
        ):
            engine._neo4j.run.return_value = []
            result = engine.ask("What drugs treat hypertension?")

        assert result["question"] == "What drugs treat hypertension?"
