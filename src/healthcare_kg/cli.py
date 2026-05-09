"""CLI entry point: healthcare-kg"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from healthcare_kg.config import load_config
from healthcare_kg.graph.neo4j_client import Neo4jClient

console = Console()


def _get_client(ctx: click.Context) -> Neo4jClient:
    cfg = load_config()
    client = Neo4jClient(cfg.neo4j_uri, cfg.neo4j_username, cfg.neo4j_password)
    ctx.call_on_close(client.close)
    return client


@click.group()
def cli() -> None:
    """Healthcare Knowledge Graph — load ontologies and query the graph."""


# ──────────────────────────────────────────────────────────────────────
# Schema setup
# ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def init_schema(ctx: click.Context) -> None:
    """Create Neo4j constraints and indexes."""
    client = _get_client(ctx)
    client.apply_schema()
    console.print("[green]Schema applied.[/green]")


# ──────────────────────────────────────────────────────────────────────
# Ingest commands
# ──────────────────────────────────────────────────────────────────────

@cli.group()
def ingest() -> None:
    """Load ontology data into Neo4j."""


@ingest.command("icd10")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def ingest_icd10(ctx: click.Context, file: str) -> None:
    """
    Load ICD-10-CM data.

    FILE — CMS flat text (icd10cm_codes_YYYY.txt) or tabular XML
    (icd10cm_tabular_YYYY.xml).
    """
    from healthcare_kg.etl.icd10 import ICD10Loader

    client = _get_client(ctx)
    loader = ICD10Loader(client)
    with console.status("Loading ICD-10-CM…"):
        counts = loader.load(Path(file))
    console.print(f"[green]ICD-10-CM loaded:[/green] {counts}")


@ingest.command("loinc")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def ingest_loinc(ctx: click.Context, file: str) -> None:
    """
    Load LOINC data.

    FILE — path to LOINC.csv from the LOINC download package.
    """
    from healthcare_kg.etl.loinc import LOINCLoader

    client = _get_client(ctx)
    loader = LOINCLoader(client)
    with console.status("Loading LOINC…"):
        counts = loader.load(Path(file))
    console.print(f"[green]LOINC loaded:[/green] {counts}")


@ingest.command("rxnorm")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def ingest_rxnorm(ctx: click.Context, path: str) -> None:
    """
    Load RxNorm data.

    PATH — directory containing RXNCONSO.RRF and RXNREL.RRF (the rrf/ folder
    from the RxNorm Full Release).
    """
    from healthcare_kg.etl.rxnorm import RxNormLoader

    client = _get_client(ctx)
    loader = RxNormLoader(client)
    with console.status("Loading RxNorm…"):
        counts = loader.load(Path(path))
    console.print(f"[green]RxNorm loaded:[/green] {counts}")


@ingest.command("snomed")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def ingest_snomed(ctx: click.Context, path: str) -> None:
    """
    Load SNOMED CT data.

    PATH — root of the SNOMED CT RF2 release directory (contains the
    Snapshot/ subdirectory).
    """
    from healthcare_kg.etl.snomed import SNOMEDLoader

    client = _get_client(ctx)
    loader = SNOMEDLoader(client)
    with console.status("Loading SNOMED CT…"):
        counts = loader.load(Path(path))
    console.print(f"[green]SNOMED CT loaded:[/green] {counts}")


# ──────────────────────────────────────────────────────────────────────
# Query
# ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("question")
@click.option("--show-cypher", is_flag=True, help="Print the generated Cypher query.")
@click.option("--show-raw", is_flag=True, help="Print raw graph results as JSON.")
@click.pass_context
def query(ctx: click.Context, question: str, show_cypher: bool, show_raw: bool) -> None:
    """
    Ask a natural language question about the knowledge graph.

    Example:
      healthcare-kg query "What ICD-10 codes map to Type 2 diabetes?"
    """
    import json
    from healthcare_kg.config import load_config
    from healthcare_kg.query.nl_query import NLQueryEngine

    cfg = load_config()
    client = _get_client(ctx)
    engine = NLQueryEngine(client, cfg.anthropic_api_key)

    with console.status("Querying…"):
        result = engine.ask(question)

    if show_cypher:
        console.print("\n[bold]Generated Cypher:[/bold]")
        console.print(result["cypher"])

    if show_raw:
        console.print("\n[bold]Raw results:[/bold]")
        console.print(json.dumps(result["raw_results"], indent=2, default=str))

    console.print(f"\n[bold]Answer:[/bold]\n{result['answer']}")


# ──────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show node counts for each ontology in the graph."""
    client = _get_client(ctx)
    counts = client.stats()

    table = Table(title="Knowledge Graph Node Counts")
    table.add_column("Label", style="cyan")
    table.add_column("Count", justify="right")
    for label, count in counts.items():
        table.add_row(label, f"{count:,}")
    console.print(table)
