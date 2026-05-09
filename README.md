# Healthcare Knowledge Graph

A unified knowledge graph that maps and connects four major healthcare ontologies — **SNOMED CT**, **ICD-10-CM**, **LOINC**, and **RxNorm** — stored in Neo4j and queryable in plain English via the Claude API.

The graph surfaces cross-ontology relationships that are invisible when each standard is used in isolation: e.g., a SNOMED disorder linked to its ICD-10 billing code, the lab tests that diagnose it, and the drugs used to treat it.

---

## Features

- **Ontology ETL pipelines** — parse and load all four ontologies from their standard release formats into Neo4j
- **Unified graph schema** — consistent node/edge model across ICD-10, LOINC, RxNorm, and SNOMED CT
- **Cross-ontology mapping** — SNOMED→ICD-10 edges via RF2 Extended Map refsets; IS_A hierarchies within each ontology
- **Natural language querying** — ask questions in plain English; Claude generates the Cypher, runs it, and summarizes the answer
- **CLI** — single `healthcare-kg` command for ingestion, querying, and graph stats

---

## Architecture

```
Ontology Source Files
(ICD-10 XML/TXT · LOINC CSV · RxNorm RRF · SNOMED CT RF2)
        │
        ▼
Python ETL Pipelines  (src/healthcare_kg/etl/)
  ├── icd10.py   →  :Diagnosis nodes + IS_A hierarchy
  ├── loinc.py   →  :LabTest nodes
  ├── rxnorm.py  →  :Drug nodes + IS_A / HAS_INGREDIENT edges
  └── snomed.py  →  :ClinicalConcept nodes + IS_A + MAPS_TO (ICD-10)
        │
        ▼  (batch MERGE — idempotent)
Neo4j Graph Database
  Nodes:  :Diagnosis  :LabTest  :Drug  :ClinicalConcept
  Edges:  IS_A  HAS_INGREDIENT  MAPS_TO  RELATED_TO
        │
        ▼
Claude API Query Layer  (src/healthcare_kg/query/nl_query.py)
  1. NL question → Claude generates Cypher (schema prompt cached)
  2. Cypher executes against Neo4j
  3. Claude summarizes raw results → human-readable answer
        │
        ▼
CLI  (healthcare-kg)
```

---

## Graph Schema

| Node Label | Ontology | Key Properties |
|---|---|---|
| `:Diagnosis` | ICD-10-CM | `code`, `description`, `chapter`, `billable` |
| `:LabTest` | LOINC | `loinc_num`, `long_common_name`, `component`, `class` |
| `:Drug` | RxNorm | `rxcui`, `name`, `tty` |
| `:ClinicalConcept` | SNOMED CT | `sctid`, `fsn`, `preferred_term`, `semantic_tag` |

| Relationship | Meaning |
|---|---|
| `IS_A` | Within-ontology parent-child hierarchy |
| `HAS_INGREDIENT` | Drug → active ingredient (RxNorm) |
| `MAPS_TO {map_type}` | SNOMED concept → equivalent ICD-10 / LOINC / RxNorm concept |
| `RELATED_TO` | General cross-ontology association |

---

## Requirements

- Python 3.10+
- Neo4j 5.x (local or cloud — [Neo4j Desktop](https://neo4j.com/download/) or [AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/))
- Anthropic API key

---

## Installation

```bash
git clone https://github.com/rgkar0128/firstclaudeproject.git
cd firstclaudeproject
pip install -e ".[dev]"
cp .env.example .env
# Fill in NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, ANTHROPIC_API_KEY
```

---

## Ontology Source Files

Download the source files from their respective providers before running ingestion.

| Ontology | License | Download |
|---|---|---|
| ICD-10-CM | Public domain (CMS) | [cms.gov → ICD-10](https://www.cms.gov/medicare/coding-billing/icd-10-codes) |
| LOINC | Free with registration | [loinc.org/downloads](https://loinc.org/downloads/) |
| RxNorm | Public domain (NLM) | [NLM RxNorm Full Release](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html) |
| SNOMED CT | UMLS / SNOMED license | [UMLS (NLM)](https://uts.nlm.nih.gov) or [SNOMED International](https://www.snomed.org) |

---

## Usage

### 1. Initialize the graph schema (run once)

```bash
healthcare-kg init-schema
```

### 2. Load ontologies

```bash
# ICD-10-CM — flat text or tabular XML from CMS
healthcare-kg ingest icd10 path/to/icd10cm_codes_2024.txt

# LOINC — LOINC.csv from the LOINC download package
healthcare-kg ingest loinc path/to/LOINC.csv

# RxNorm — the rrf/ directory from the Full Release zip
healthcare-kg ingest rxnorm path/to/rrf/

# SNOMED CT — root of the RF2 release (contains Snapshot/)
healthcare-kg ingest snomed path/to/SnomedCT_InternationalRF2_Release/
```

### 3. Query in natural language

```bash
healthcare-kg query "What ICD-10 codes map to Type 2 diabetes?"
healthcare-kg query "Which LOINC codes measure blood glucose?"
healthcare-kg query "What drugs contain metformin as an ingredient?" --show-cypher
```

### 4. Check graph statistics

```bash
healthcare-kg stats
```

---

## Development

```bash
# Run all tests
pytest

# Run a specific test class
pytest tests/test_etl.py::TestICD10FlatParser
```

---

## Project Structure

```
src/healthcare_kg/
├── config.py          # Environment variable loading
├── cli.py             # Click CLI entry point
├── etl/               # One loader module per ontology
│   ├── base.py
│   ├── icd10.py
│   ├── loinc.py
│   ├── rxnorm.py
│   └── snomed.py
├── graph/
│   ├── neo4j_client.py  # Neo4j driver wrapper, batch MERGE utilities
│   └── schema.py        # Constraints, indexes, schema description for Claude
└── query/
    └── nl_query.py      # NLQueryEngine — NL → Cypher → summary via Claude API
tests/
├── test_etl.py
└── test_query.py
```

---

## License

MIT — see [LICENSE](LICENSE).
