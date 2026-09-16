"""Profile PostgreSQL tables — column stats, nulls, distributions, HTML reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime

from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine

from toolkit.db import connect


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    total_rows: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    distinct_count: int = 0
    distinct_pct: float = 0.0
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    median_value: float | None = None
    stddev_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    avg_length: float | None = None
    top_values: list[dict] = field(default_factory=list)
    sample_values: list[str] = field(default_factory=list)


@dataclass
class TableProfile:
    table_name: str
    schema_name: str
    row_count: int
    column_count: int
    profiled_at: str
    columns: list[ColumnProfile] = field(default_factory=list)

    def to_json(self, path: str | None = None) -> str:
        s = json.dumps(asdict(self), indent=2, default=str)
        if path:
            with open(path, "w") as f:
                f.write(s)
        return s

    def to_html(self, path: str) -> None:
        from jinja2 import Template
        html = Template(HTML_TEMPLATE).render(p=self)
        with open(path, "w") as f:
            f.write(html)


NUMERIC_TYPES = ("integer", "bigint", "smallint", "numeric", "decimal", "real", "double", "float", "serial")
TEXT_TYPES = ("varchar", "character varying", "text", "char", "name")


class Profiler:
    """Profile a PostgreSQL table and produce stats for every column."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def profile(self, table: str, schema: str = "public", top_n: int = 10, samples: int = 5) -> TableProfile:
        inspector = inspect(self.engine)
        columns_meta = inspector.get_columns(table, schema=schema)
        fqt = f'"{schema}"."{table}"'

        with connect(self.engine) as conn:
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {fqt}")).scalar_one()

            profiles = []
            for col_meta in columns_meta:
                name, dtype = col_meta["name"], str(col_meta["type"]).lower()
                qcol = f'"{name}"'

                # Base stats
                base = conn.execute(text(
                    f"SELECT COUNT(*) AS total, COUNT(*) - COUNT({qcol}) AS nulls, "
                    f"COUNT(DISTINCT {qcol}) AS dist FROM {fqt}"
                )).mappings().one()

                total = base["total"]
                cp = ColumnProfile(
                    name=name, dtype=dtype, total_rows=total,
                    null_count=base["nulls"],
                    null_pct=round(base["nulls"] / total * 100, 2) if total else 0,
                    distinct_count=base["dist"],
                    distinct_pct=round(base["dist"] / total * 100, 2) if total else 0,
                )

                # Numeric stats
                if any(t in dtype for t in NUMERIC_TYPES):
                    ns = conn.execute(text(
                        f"SELECT MIN({qcol})::text AS mi, MAX({qcol})::text AS ma, "
                        f"AVG({qcol})::float AS av, STDDEV({qcol})::float AS sd, "
                        f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {qcol})::float AS md "
                        f"FROM {fqt} WHERE {qcol} IS NOT NULL"
                    )).mappings().one()
                    cp.min_value, cp.max_value = ns["mi"], ns["ma"]
                    cp.mean_value = round(ns["av"], 4) if ns["av"] else None
                    cp.stddev_value = round(ns["sd"], 4) if ns["sd"] else None
                    cp.median_value = ns["md"]

                # Text length stats
                if any(t in dtype for t in TEXT_TYPES):
                    ls = conn.execute(text(
                        f"SELECT MIN(LENGTH({qcol})) AS mi, MAX(LENGTH({qcol})) AS ma, "
                        f"AVG(LENGTH({qcol}))::float AS av FROM {fqt} WHERE {qcol} IS NOT NULL"
                    )).mappings().one()
                    cp.min_length, cp.max_length = ls["mi"], ls["ma"]
                    cp.avg_length = round(ls["av"], 2) if ls["av"] else None

                # Top values
                tvs = conn.execute(text(
                    f"SELECT {qcol}::text AS value, COUNT(*) AS freq, "
                    f"ROUND(COUNT(*)*100.0/:total,2) AS pct FROM {fqt} "
                    f"WHERE {qcol} IS NOT NULL GROUP BY {qcol} ORDER BY COUNT(*) DESC LIMIT :n"
                ), {"total": total, "n": top_n}).mappings().all()
                cp.top_values = [dict(r) for r in tvs]

                # Samples
                if samples:
                    ss = conn.execute(text(
                        f"SELECT DISTINCT {qcol}::text AS v FROM {fqt} "
                        f"WHERE {qcol} IS NOT NULL ORDER BY RANDOM() LIMIT :n"
                    ), {"n": samples}).scalars().all()
                    cp.sample_values = ss

                profiles.append(cp)

        return TableProfile(
            table_name=table, schema_name=schema, row_count=row_count,
            column_count=len(columns_meta), profiled_at=datetime.now(UTC).isoformat(),
            columns=profiles,
        )


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Profile: {{ p.schema_name }}.{{ p.table_name }}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#c9d1d9;padding:2rem;line-height:1.6}
.hdr{background:linear-gradient(135deg,#161b22,#0d1117);border:1px solid #30363d;padding:2rem;border-radius:12px;margin-bottom:2rem}
.hdr h1{font-size:1.6rem;color:#58a6ff}.hdr .meta{color:#8b949e;margin-top:.3rem;font-size:.85rem}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem}
.sc{background:#161b22;border:1px solid #30363d;padding:1.2rem;border-radius:10px}
.sc .lab{font-size:.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:.04em}
.sc .val{font-size:1.8rem;font-weight:700;color:#58a6ff}
.cc{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1.2rem;margin-bottom:.8rem}
.cc h3{font-size:1rem;color:#c9d1d9;margin-bottom:.3rem}
.cc .tp{display:inline-block;background:#1f2937;color:#7ee787;padding:.15rem .5rem;border-radius:4px;font-size:.75rem;font-family:monospace}
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.5rem;margin-top:.75rem}
.ms{padding:.4rem;background:#0d1117;border-radius:6px}.ms .lab{font-size:.7rem;color:#8b949e}.ms .val{font-weight:600;font-size:.85rem}
.bar{height:5px;background:#21262d;border-radius:3px;margin-top:.2rem}.bf{height:100%;border-radius:3px;background:#58a6ff}
.nh{background:#f85149}
table.fq{width:100%;margin-top:.6rem;border-collapse:collapse;font-size:.8rem}
table.fq th{text-align:left;padding:.3rem;border-bottom:1px solid #30363d;color:#8b949e}
table.fq td{padding:.3rem;border-bottom:1px solid #21262d;color:#c9d1d9}
</style></head><body>
<div class="hdr"><h1>{{ p.schema_name }}.{{ p.table_name }}</h1>
<div class="meta">Profiled {{ p.profiled_at }} UTC</div></div>
<div class="summary">
<div class="sc"><div class="lab">Rows</div><div class="val">{{ "{:,}".format(p.row_count) }}</div></div>
<div class="sc"><div class="lab">Columns</div><div class="val">{{ p.column_count }}</div></div>
</div>
{% for c in p.columns %}
<div class="cc"><h3>{{ c.name }} <span class="tp">{{ c.dtype }}</span></h3>
<div class="sg">
<div class="ms"><div class="lab">Null %</div><div class="val">{{ c.null_pct }}%</div>
<div class="bar"><div class="bf {% if c.null_pct > 50 %}nh{% endif %}" style="width:{{ c.null_pct }}%"></div></div></div>
<div class="ms"><div class="lab">Distinct</div><div class="val">{{ "{:,}".format(c.distinct_count) }} ({{ c.distinct_pct }}%)</div></div>
{% if c.min_value is not none %}<div class="ms"><div class="lab">Min</div><div class="val">{{ c.min_value }}</div></div>
<div class="ms"><div class="lab">Max</div><div class="val">{{ c.max_value }}</div></div>
<div class="ms"><div class="lab">Mean</div><div class="val">{{ c.mean_value }}</div></div>
<div class="ms"><div class="lab">Median</div><div class="val">{{ c.median_value }}</div></div>{% endif %}
{% if c.min_length is not none %}<div class="ms"><div class="lab">Len (min/avg/max)</div><div class="val">{{ c.min_length }}/{{ c.avg_length }}/{{ c.max_length }}</div></div>{% endif %}
</div>
{% if c.top_values %}<table class="fq"><thead><tr><th>Value</th><th>Count</th><th>%</th></tr></thead><tbody>
{% for tv in c.top_values[:5] %}<tr><td>{{ tv.value[:50] }}{% if tv.value|length > 50 %}…{% endif %}</td><td>{{ "{:,}".format(tv.freq) }}</td><td>{{ tv.pct }}%</td></tr>{% endfor %}
</tbody></table>{% endif %}</div>
{% endfor %}</body></html>"""
