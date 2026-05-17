"""
DocNest CLI — command-line interface using Typer + Rich.

Commands:
    docnest convert <source>          Convert file or folder to .udf
    docnest query   <udf> <question>  Query a .udf file (5-layer RAG)
    docnest inspect <udf>             Show catalogue summary
    docnest stats   <udf>             Show detailed statistics

Phase: 1 (convert), 4 (query / inspect / stats)
Spec: docs/SPEC_DOCNEST_PYPI.md — Section 12
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

app = typer.Typer(
    name="docnest",
    help="The document normalisation engine RAG has always needed.",
    add_completion=False,
    pretty_exceptions_enable=False,
)
console = Console()
err_console = Console(stderr=True, style="bold red")


# ------------------------------------------------------------------ #
#  convert                                                             #
# ------------------------------------------------------------------ #

@app.command()
def convert(
    source: str = typer.Argument(..., help="File or folder to convert (.pdf, .docx, .xlsx, .html, .md)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output .udf path"),
    quantization: str = typer.Option(
        "float16", "--quantization", "-q",
        help="Embedding compression: float32 | float16 | int8 | binary",
    ),
    llm_provider: str = typer.Option("ollama", "--llm-provider", help="LLM provider for intelligence"),
    llm_model: str = typer.Option("llama3.2", "--llm-model", help="Model name"),
    skip_intelligence: bool = typer.Option(
        False, "--fast", "-f",
        help="Skip LLM enrichment (faster, no Ollama required)",
    ),
    include_originals: bool = typer.Option(False, "--include-originals", help="Embed source file in .udf"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show stage-by-stage progress"),
) -> None:
    """Convert a document or folder to a .udf knowledge base file.

    Examples:
        docnest convert report.pdf
        docnest convert report.pdf --fast --output kb.udf
        docnest convert ./reports/ --quantization int8
    """
    from docnest.pipeline import DocNestPipeline
    from docnest.exceptions import DOCNESTError

    path = Path(source)
    if not path.exists():
        err_console.print(f"[red]Error:[/red] Source not found: {source}")
        raise typer.Exit(1)

    stages_done: list[str] = []

    def on_stage(stage: str, data: object) -> None:
        stages_done.append(stage)
        if verbose:
            console.print(f"  [green]✓[/green] {stage}")

    stage_names = {
        "parse": "Parsing document",
        "normalise": "Assigning §ids",
        "enrich_sections": "Enriching sections (LLM)",
        "enrich_document": "Document intelligence (LLM)",
        "embed": "Generating embeddings",
        "write": "Writing .udf archive",
    }

    console.print(f"\n[bold cyan]DocNest[/bold cyan] converting [yellow]{source}[/yellow]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=not verbose,
    ) as progress:
        task = progress.add_task("Starting…", total=None)

        def on_stage_progress(stage: str, data: object) -> None:
            label = stage_names.get(stage, stage)
            progress.update(task, description=label)
            on_stage(stage, data)

        try:
            pipeline = DocNestPipeline(
                quantization=quantization,
                llm_provider=llm_provider,
                llm_model=llm_model,
                on_stage_complete=on_stage_progress,
                skip_intelligence=skip_intelligence,
            )
            out = pipeline.convert(source, output=output, include_originals=include_originals)
            progress.update(task, description="Done!", completed=100, total=100)
        except DOCNESTError as exc:
            err_console.print(f"\n[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    size_kb = Path(out).stat().st_size // 1024
    console.print(
        Panel(
            f"[green bold]✓ Success![/green bold]\n\n"
            f"Output: [yellow]{out}[/yellow]\n"
            f"Size:   [cyan]{size_kb:,} KB[/cyan]\n"
            f"Stages: {', '.join(stages_done)}",
            title="DocNest Convert",
            border_style="green",
        )
    )


# ------------------------------------------------------------------ #
#  query                                                               #
# ------------------------------------------------------------------ #

@app.command()
def query(
    udf_path: str = typer.Argument(..., help="Path to the .udf file"),
    question: str = typer.Argument(..., help="Natural language question"),
    llm_provider: str = typer.Option("ollama", "--llm-provider"),
    llm_model: str = typer.Option("llama3.2", "--llm-model"),
    show_layer: bool = typer.Option(False, "--show-layer", help="Show which layer answered"),
) -> None:
    """Query a .udf knowledge base with a natural language question.

    The 5-layer engine escalates from pre-computed (0 tokens) up to
    full-document LLM only if cheaper layers can't answer.

    Examples:
        docnest query report.udf "What was the Q3 revenue?"
        docnest query report.udf "Summarise the document" --show-layer
    """
    from docnest.reader import UDFIndex
    from docnest.exceptions import UDFReadError

    if not Path(udf_path).exists():
        err_console.print(f"[red]Error:[/red] File not found: {udf_path}")
        raise typer.Exit(1)

    try:
        with console.status("[cyan]Loading .udf…[/cyan]"):
            index = UDFIndex.load(udf_path)
    except UDFReadError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    with console.status("[cyan]Thinking…[/cyan]"):
        result = index.query(question, llm_provider=llm_provider, llm_model=llm_model)

    # Print answer
    console.print(f"\n[bold]{result.answer}[/bold]\n")

    # Citations
    if result.citations:
        console.print(f"[dim]Source: {', '.join(result.citations)}[/dim]")
    if result.navigate_to:
        console.print(f"[dim]Navigate to: {result.navigate_to}[/dim]")
    if show_layer:
        layer_labels = {
            0: "Layer 0 (pre-computed, 0 tokens)",
            1: "Layer 1 (BM25+cosine, 0 tokens)",
            2: f"Layer 2 (section LLM, ~{result.tokens_used} tokens)",
            3: f"Layer 3 (multi-section, ~{result.tokens_used} tokens)",
            4: f"Layer 4 (full doc, ~{result.tokens_used} tokens)",
        }
        console.print(f"[dim]Answered by: {layer_labels.get(result.layer_used, f'Layer {result.layer_used}')}[/dim]")


# ------------------------------------------------------------------ #
#  inspect                                                             #
# ------------------------------------------------------------------ #

@app.command()
def inspect(
    udf_path: str = typer.Argument(..., help="Path to the .udf file"),
) -> None:
    """Display the catalogue summary of a .udf file.

    Shows title, summary, key numbers, and the full section tree.

    Example:
        docnest inspect report.udf
    """
    from docnest.reader import UDFIndex
    from docnest.exceptions import UDFReadError

    if not Path(udf_path).exists():
        err_console.print(f"[red]Error:[/red] File not found: {udf_path}")
        raise typer.Exit(1)

    try:
        index = UDFIndex.load(udf_path)
    except UDFReadError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    cat = index._catalogue

    # Header panel
    console.print(
        Panel(
            f"[bold]{cat.get('title', 'Untitled')}[/bold]\n\n"
            f"{cat.get('summary', '[no summary]')}",
            title=f"[cyan]{Path(udf_path).name}[/cyan]",
            border_style="cyan",
        )
    )

    # Key numbers
    key_numbers = cat.get("key_numbers", [])
    if key_numbers:
        tbl = Table(title="Key Numbers", box=box.SIMPLE, show_header=True, header_style="bold")
        tbl.add_column("Label", style="cyan")
        tbl.add_column("Value", style="yellow")
        tbl.add_column("Unit")
        tbl.add_column("Section", style="dim")
        for kn in key_numbers:
            tbl.add_row(
                kn.get("label", ""),
                kn.get("value", ""),
                kn.get("unit", "") or "",
                kn.get("section", ""),
            )
        console.print(tbl)

    # Insights
    insights = cat.get("insights", [])
    if insights:
        console.print("\n[bold]Insights:[/bold]")
        for insight in insights:
            console.print(f"  [green]•[/green] {insight}")

    # Section tree
    section_index = cat.get("section_index", [])
    if section_index:
        console.print("\n[bold]Sections:[/bold]")
        for entry in section_index:
            indent = "  " * (entry.get("level", 1) - 1)
            sid = entry.get("id", "")
            title = entry.get("title", "")
            console.print(f"  {indent}[dim]{sid}[/dim]  {title}")


# ------------------------------------------------------------------ #
#  stats                                                               #
# ------------------------------------------------------------------ #

@app.command()
def stats(
    udf_path: str = typer.Argument(..., help="Path to the .udf file"),
) -> None:
    """Display detailed statistics about a .udf file.

    Example:
        docnest stats report.udf
    """
    import zipfile
    import json
    from docnest.exceptions import UDFReadError

    path = Path(udf_path)
    if not path.exists():
        err_console.print(f"[red]Error:[/red] File not found: {udf_path}")
        raise typer.Exit(1)

    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
            catalogue = json.loads(zf.read("catalogue.json"))
            names = zf.namelist()
            sizes = {n: zf.getinfo(n).file_size for n in names}
    except Exception as exc:
        err_console.print(f"[red]Error reading .udf:[/red] {exc}")
        raise typer.Exit(1)

    section_index = catalogue.get("section_index", [])
    total_tokens = sum(e.get("token_count", 0) for e in section_index)
    total_size_kb = path.stat().st_size // 1024

    tbl = Table(title=f"Stats: {path.name}", box=box.SIMPLE, show_header=False)
    tbl.add_column("Field", style="cyan", width=24)
    tbl.add_column("Value", style="yellow")

    tbl.add_row("Format version", manifest.get("udf_version", "?"))
    tbl.add_row("Document ID", manifest.get("doc_id", "?"))
    tbl.add_row("Source format", manifest.get("source_format", "?"))
    tbl.add_row("Created at", manifest.get("created_at", "?"))
    tbl.add_row("Sections", str(manifest.get("section_count", len(section_index))))
    tbl.add_row("Total tokens (approx)", f"{total_tokens:,}")
    tbl.add_row("Key numbers", str(len(catalogue.get("key_numbers", []))))
    tbl.add_row("Insights", str(len(catalogue.get("insights", []))))
    tbl.add_row("Embedding model", manifest.get("embedding_model", "?"))
    tbl.add_row("Embedding dims", str(manifest.get("embedding_dims", "?")))
    tbl.add_row("Quantization", manifest.get("quantization", "?"))
    tbl.add_row("Total .udf size", f"{total_size_kb:,} KB")
    for name, size in sizes.items():
        tbl.add_row(f"  {name}", f"{size // 1024:,} KB")

    console.print(tbl)


if __name__ == "__main__":
    app()
