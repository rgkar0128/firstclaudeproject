# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A healthcare knowledge graph that maps and relates major medical ontologies — including SNOMED CT, ICD-10, LOINC, and RxNorm — into a unified, queryable graph. The goal is to surface cross-ontology relationships (e.g., linking a diagnosis code to a lab test to a drug) that are not visible when each standard is used in isolation.

## Tech Stack

- **Python** — data ingestion, parsing, and ETL pipelines for ontology source files
- **Graph database** — Neo4j or Amazon Neptune to store nodes (concepts) and edges (relationships)
- **Claude API (Anthropic)** — LLM-assisted entity extraction, relationship inference, and natural language querying over the graph

## Architecture (planned)

```
Ontology Sources (SNOMED CT, ICD-10, LOINC, RxNorm)
        │
        ▼
   Python ETL Pipeline
   (parse → normalize → deduplicate)
        │
        ▼
   Graph Database (Neo4j / Neptune)
   Nodes: concepts  |  Edges: relationships
        │
        ▼
   Claude API Layer
   (NL queries → Cypher/SPARQL → graph results → summarized answers)
```

## Development Setup

> Fill in once tooling is established: virtual environment setup, dependency install command, graph DB connection config, API key env vars.

## Commands

> Fill in as the project grows: how to run ingestion pipelines, run tests, start a local Neo4j instance, etc.

## Key Ontology Notes

- **SNOMED CT** — clinical concepts and hierarchies (requires UMLS license)
- **ICD-10-CM** — diagnosis codes (freely available from CMS)
- **LOINC** — lab and clinical observation codes (free registration required)
- **RxNorm** — drug concepts and relationships (freely available via NLM)
