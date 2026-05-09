# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A healthcare knowledge graph that maps and relates major medical ontologies — SNOMED CT, ICD-10-CM, LOINC, and RxNorm — into a unified Neo4j graph. Cross-ontology relationships (e.g., a SNOMED disorder → its ICD-10 code, its associated lab tests, its treatments) surface connections that are invisible when each standard is used in isolation. A Claude-powered NL query layer translates natural language questions into Cypher and summarizes the results.

## Setup

```bash
# Install in editable mode (creates the `healthcare-kg` CLI)
pip install -e ".[dev]"

# Copy and fill in credentials
cp .env.example .env
```

`.env` requires `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `ANTHROPIC_API_KEY`.

## Commands

```bash
# Initialize Neo4j constraints and indexes (run once)
healthcare-kg init-schema

# Load ontologies (point at downloaded source files)
healthcare-kg ingest icd10 path/to/icd10cm_codes_2024.txt     # or .xml tabular
healthcare-kg ingest loinc path/to/LOINC.csv
healthcare-kg ingest rxnorm path/to/rrf/                       # directory with RXNCONSO.RRF + RXNREL.RRF
healthcare-kg ingest snomed path/to/SnomedCT_Release/          # directory containing Snapshot/

# Query
healthcare-kg query "What ICD-10 codes map to Type 2 diabetes?"
healthcare-kg query "Which LOINC codes measure glucose?" --show-cypher

# Show node counts per ontology
healthcare-kg stats

# Run tests
pytest
pytest tests/test_etl.py::TestICD10FlatParser   # single class
```

## Architecture

```
Ontology source files
        │
        ▼
src/healthcare_kg/etl/          ← one loader per ontology
  icd10.py   — CMS flat text or tabular XML → :Diagnosis nodes + IS_A hierarchy
  loinc.py   — LOINC.csv → :LabTest nodes
  rxnorm.py  — RXNCONSO.RRF + RXNREL.RRF → :Drug nodes + IS_A / HAS_INGREDIENT
  snomed.py  — RF2 Snapshot → :ClinicalConcept nodes + IS_A + MAPS_TO (ICD-10)
        │
        ▼  (batch MERGE via neo4j Python driver)
Neo4j graph database
        │
        ▼
src/healthcare_kg/query/nl_query.py
  NLQueryEngine.ask(question)
    1. Claude: NL → Cypher  (schema cached via prompt caching)
    2. Neo4j:  execute Cypher
    3. Claude: raw results → human-readable summary
        │
        ▼
src/healthcare_kg/cli.py        ← Click CLI, entry point: `healthcare-kg`
```

## Graph Schema

Node labels: `:Diagnosis` (ICD-10), `:LabTest` (LOINC), `:Drug` (RxNorm), `:ClinicalConcept` (SNOMED CT).

Key relationships:
- `IS_A` — within-ontology hierarchy for all four node types
- `HAS_INGREDIENT` — drug → active ingredient (RxNorm)
- `MAPS_TO {map_type}` — SNOMED concept → ICD-10/LOINC/RxNorm equivalent
- `RELATED_TO` — general cross-ontology association

Full property lists are in `src/healthcare_kg/graph/schema.py` (`SCHEMA_DESCRIPTION`), which is also injected into Claude's system prompt for Cypher generation.

## Ontology Source Files

| Ontology   | License                         | Download                                  |
|------------|----------------------------------|-------------------------------------------|
| ICD-10-CM  | Public domain (CMS)             | cms.gov → Medicare → Coding → ICD-10     |
| LOINC      | Free (registration required)    | loinc.org/downloads                       |
| RxNorm     | Public domain (NLM)             | nlm.nih.gov → RxNorm → Full Release      |
| SNOMED CT  | UMLS/SNOMED license required    | uts.nlm.nih.gov (UMLS) or snomed.org     |

## Key Design Decisions

- All ETL uses Neo4j `MERGE` (idempotent) so re-running a loader updates rather than duplicates.
- Batching is fixed at 500 rows per transaction — tunable in `Neo4jClient.batch_merge_nodes`.
- Claude prompt caching is applied to the schema system prompt in `nl_query.py` to reduce token costs on repeated queries.
- SNOMED→ICD-10 cross-ontology edges are loaded from the Extended Map refset if present in the RF2 release; other cross-ontology links must be added manually or via UMLS mappings.
