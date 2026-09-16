"""CLI entry points — three subcommands: profile, diff, csv."""

import sys
import click
from rich.console import Console

console = Console()


@click.group()
def cli():
    """dataeng-toolkit — PostgreSQL profiling, schema diffing, CSV fixing."""
    pass


@cli.command()
@click.option("--db", required=True, envvar="TOOLKIT_DB", help="PostgreSQL connection string")
@click.option("--table", required=True, help="Table to profile")
@click.option("--schema", default="public")
@click.option("-o", "--output", default=None, help="Output path (.html or .json)")
@click.option("--top-n", default=10, type=int)
def profile(db, table, schema, output, top_n):
    """Profile a PostgreSQL table — column stats, nulls, distributions."""
    from toolkit.db import get_engine, test_connection
    from toolkit.profiler import Profiler

    try:
        engine = get_engine(db)
        info = test_connection(engine)
        console.print(f"[green]Connected to {info['db']}[/green]")
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        sys.exit(1)

    report = Profiler(engine).profile(table, schema=schema, top_n=top_n)
    console.print(f"[green]Profiled {report.row_count:,} rows, {report.column_count} columns[/green]")

    if output:
        if output.endswith(".html"):
            report.to_html(output)
        else:
            report.to_json(output)
        console.print(f"[green]Saved to {output}[/green]")
    else:
        console.print(report.to_json())


@cli.command()
@click.option("--source", required=True, envvar="TOOLKIT_SOURCE", help="Source DB URL")
@click.option("--target", required=True, envvar="TOOLKIT_TARGET", help="Target DB URL")
@click.option("--schema", default="public")
@click.option("--sql", is_flag=True, help="Output migration SQL")
def diff(source, target, schema, sql):
    """Compare two PostgreSQL schemas and show differences."""
    from toolkit.db import get_engine
    from toolkit.schema_diff import SchemaDiffer

    result = SchemaDiffer(get_engine(source), get_engine(target)).compare(schema)
    console.print(result.migration_sql() if sql else result.summary())


@cli.command()
@click.argument("action", type=click.Choice(["diagnose", "fix"]))
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None)
@click.option("--keep-malformed", is_flag=True)
def csv(action, input_file, output, keep_malformed):
    """Diagnose or fix CSV files."""
    from toolkit.csv_surgeon import CSVSurgeon

    surgeon = CSVSurgeon()
    if action == "diagnose":
        surgeon.diagnose(input_file).print_report()
    elif action == "fix":
        if not output:
            console.print("[red]--output required for fix[/red]")
            sys.exit(2)
        stats = surgeon.fix(input_file, output, remove_malformed=not keep_malformed)
        console.print(f"[green]Done: {stats['rows_in']:,} in → {stats['rows_out']:,} out, {stats['rows_dropped']:,} dropped[/green]")
