"""
DOCNEST CLI — command-line interface using Typer + Rich.

Commands:
    DOCNEST convert <source>          Convert file or folder to .udf
    DOCNEST query <udf> <question>    Query a .udf file
    DOCNEST inspect <udf>             Show catalogue summary
    DOCNEST stats <udf>               Show detailed statistics
    DOCNEST sync <connector> ...      Sync from a remote source (Phase 5)

Phase: 1 (basic convert), 4 (query), 5 (sync)
Spec: docs/SPEC_DOCNEST_PYPI.md — Section 12
"""

from __future__ import annotations
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="DOCNEST",
    help="The document normalisation engine RAG has always needed.",
    add_completion=False,
)
console = Console()


@app.command()
def convert(
    source: str = typer.Argument(..., help="File or folder to convert"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output .udf path"),
    embedding_model: str = typer.Option("nomic-embed-text", "--embedding-model", "-e"),
    quantization: str = typer.Option("float16", "--quantization", "-q",
                                      help="float32 | float16 | int8 | binary"),
    llm_provider: str = typer.Option("ollama", "--llm-provider"),
    llm_model: str = typer.Option("llama3.2", "--llm-model"),
    include_originals: bool = typer.Option(False, "--include-originals"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Convert a document or folder to a .udf knowledge base file."""
    # TODO (Phase 1): Instantiate DOCNESTPipeline and call convert()
    # Show Rich progress bar with on_stage_complete callback
    console.print("[yellow]Convert not yet implemented — see ROADMAP.md Phase 1[/yellow]")
    raise typer.Exit(1)


@app.command()
def query(
    udf_path: str = typer.Argument(..., help="Path to the .udf file"),
    question: str = typer.Argument(..., help="Question to ask"),
    llm_provider: str = typer.Option("ollama", "--llm-provider"),
    llm_model: str = typer.Option("llama3.2", "--llm-model"),
) -> None:
    """Query a .udf knowledge base with a natural language question."""
    # TODO (Phase 4): Load UDFIndex and call query()
    console.print("[yellow]Query not yet implemented — see ROADMAP.md Phase 4[/yellow]")
    raise typer.Exit(1)


@app.command()
def inspect(
    udf_path: str = typer.Argument(..., help="Path to the .udf file"),
) -> None:
    """Display the catalogue summary of a .udf file."""
    # TODO (Phase 4): Load catalogue and print with Rich table
    console.print("[yellow]Inspect not yet implemented — see ROADMAP.md Phase 4[/yellow]")
    raise typer.Exit(1)


@app.command()
def stats(
    udf_path: str = typer.Argument(..., help="Path to the .udf file"),
) -> None:
    """Display detailed statistics about a .udf file."""
    # TODO (Phase 4): Print section count, token count, embedding size, etc.
    console.print("[yellow]Stats not yet implemented — see ROADMAP.md Phase 4[/yellow]")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
