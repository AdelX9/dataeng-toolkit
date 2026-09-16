# dataeng-toolkit

Profile any PostgreSQL table in one command — column stats, null rates, distributions, and an HTML report you can share with non-technical stakeholders.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## What's Inside

| Tool | What It Solves |
|------|---------------|
| **Data Profiler** | "What's in this table?" — types, nulls, distributions, top values → HTML report |
| **Schema Differ** | Compare two databases → get exact migration SQL |
| **CSV Surgeon** | Fix encoding, drop malformed rows, detect delimiters — without loading into memory |

## Quick Start

```bash
git clone https://github.com/AdelX9/dataeng-toolkit.git
cd dataeng-toolkit
pip install -e .

# Profile a table
toolkit profile --db postgresql://user:pass@localhost/mydb --table users -o report.html

# Compare two schemas
toolkit diff --source postgresql://localhost/prod --target postgresql://localhost/staging

# Fix a broken CSV
toolkit csv diagnose messy_data.csv
toolkit csv fix messy_data.csv -o clean.csv
```

## Data Profiler Output

For each column the profiler reports:
- Data type, null rate, distinct count
- Min / max / mean / median / stddev (numeric columns)
- String length stats (text columns)
- Top N most frequent values with percentages
- All rendered as a self-contained HTML report

## Architecture

```
toolkit/
├── profiler.py       ← Profiles tables via SQL aggregates, renders HTML
├── schema_diff.py    ← Compares schemas via information_schema, outputs DDL
├── csv_surgeon.py    ← Stream-processes CSVs (constant memory, handles GBs)
├── db.py             ← SQLAlchemy 2.0 connection helpers
└── cli.py            ← Click-based CLI with 3 subcommands
```

Each tool is standalone — import one without needing the others.

## Why Not pandas?

These tools are for **operations**, not analysis:
- Handle files larger than RAM (streaming, not loading)
- PostgreSQL-native features (pg_stat, COPY, information_schema)
- CLI-first — designed for cron jobs and CI pipelines
- Produce reports for non-technical people (HTML, not notebooks)

## Related Projects

- [`sql-agent`](https://github.com/AdelX9/sql-agent) — AI agent that writes SQL from natural language
- [`sql-cookbook`](https://github.com/AdelX9/sql-cookbook) — Advanced PostgreSQL query patterns

## License

MIT
