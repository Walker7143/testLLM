from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from probes.base import ProbeResult
from scoring import verdict


def print_report(
    base_url: str,
    claimed_model: str,
    results: list[ProbeResult],
    final_score: float,
    warning: str | None = None,
):
    console = Console()
    verdict_text, color = verdict(final_score)

    # Header
    header = Text()
    header.append("testLLM", style="bold cyan")
    header.append(" - Model Identity Detection Report")
    console.print(Panel(header, expand=False))

    console.print(f"  Target:  {base_url}")
    console.print(f"  Claimed: {claimed_model}")
    console.print()

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Probe", style="cyan", min_width=20)
    table.add_column("Score", justify="right", min_width=6)
    table.add_column("Confidence", justify="right", min_width=10)
    table.add_column("Evidence", min_width=40)

    for r in results:
        score_color = "green" if r.score >= 0.8 else "yellow" if r.score >= 0.5 else "red"
        table.add_row(
            r.probe_name,
            f"[{score_color}]{r.score:.2f}[/{score_color}]",
            f"{r.confidence:.2f}",
            " | ".join(r.evidence[:3]),
        )

    console.print(table)
    console.print()

    # Warning if too many probes failed
    if warning:
        console.print(Panel(f"[bold yellow]{warning}[/bold yellow]", title="Warning", expand=False))
        console.print()

    # Final verdict
    verdict_color = "green" if final_score >= 0.8 else "yellow" if final_score >= 0.5 else "red"
    console.print(
        Panel(
            f"[bold {verdict_color}]FINAL SCORE: {final_score:.2f} / 1.00[/bold {verdict_color}]\n"
            f"[bold {verdict_color}]VERDICT: {verdict_text}[/bold {verdict_color}]",
            title="Result",
            expand=False,
        )
    )
