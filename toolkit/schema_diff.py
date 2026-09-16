"""Compare two PostgreSQL schemas and generate migration SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text
from sqlalchemy.engine import Engine

from toolkit.db import connect


class DiffType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class ColumnDiff:
    table: str
    column: str
    diff_type: DiffType
    source_def: dict | None = None
    target_def: dict | None = None
    changes: list[str] = field(default_factory=list)


@dataclass
class TableDiff:
    table: str
    diff_type: DiffType
    column_count: int = 0


@dataclass
class SchemaDiffResult:
    source_url: str
    target_url: str
    schema: str
    table_diffs: list[TableDiff] = field(default_factory=list)
    column_diffs: list[ColumnDiff] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Schema Diff: {self.schema}",
                 f"Source: {_mask(self.source_url)}",
                 f"Target: {_mask(self.target_url)}", "=" * 60]
        if not self.table_diffs and not self.column_diffs:
            lines.append("Schemas are identical.")
            return "\n".join(lines)
        for td in self.table_diffs:
            sym = "+" if td.diff_type == DiffType.ADDED else "-"
            where = "missing in target" if td.diff_type == DiffType.ADDED else "only in target"
            lines.append(f"  {sym} TABLE {td.table} ({td.column_count} cols) — {where}")
        for cd in self.column_diffs:
            if cd.diff_type == DiffType.ADDED:
                lines.append(f"  + COLUMN {cd.table}.{cd.column}")
            elif cd.diff_type == DiffType.REMOVED:
                lines.append(f"  - COLUMN {cd.table}.{cd.column}")
            else:
                lines.append(f"  ~ COLUMN {cd.table}.{cd.column}: {', '.join(cd.changes)}")
        lines += ["=" * 60, f"{len(self.table_diffs)} table + {len(self.column_diffs)} column changes"]
        return "\n".join(lines)

    def migration_sql(self) -> str:
        stmts = []
        s = self.schema
        for td in self.table_diffs:
            if td.diff_type == DiffType.REMOVED:
                stmts.append(f'DROP TABLE IF EXISTS "{s}"."{td.table}" CASCADE;')
            elif td.diff_type == DiffType.ADDED:
                stmts.append(f'-- TODO: CREATE TABLE "{s}"."{td.table}" (...);')
        for cd in self.column_diffs:
            if cd.diff_type == DiffType.ADDED and cd.source_def:
                n = "" if cd.source_def.get("is_nullable") == "YES" else " NOT NULL"
                stmts.append(f'ALTER TABLE "{s}"."{cd.table}" ADD COLUMN "{cd.column}" {cd.source_def["data_type"]}{n};')
            elif cd.diff_type == DiffType.REMOVED:
                stmts.append(f'ALTER TABLE "{s}"."{cd.table}" DROP COLUMN IF EXISTS "{cd.column}";')
            elif cd.diff_type == DiffType.MODIFIED and cd.source_def:
                for ch in cd.changes:
                    if "type" in ch.lower():
                        stmts.append(f'ALTER TABLE "{s}"."{cd.table}" ALTER COLUMN "{cd.column}" TYPE {cd.source_def["data_type"]};')
                    if "nullable" in ch.lower():
                        act = "DROP NOT NULL" if cd.source_def["is_nullable"] == "YES" else "SET NOT NULL"
                        stmts.append(f'ALTER TABLE "{s}"."{cd.table}" ALTER COLUMN "{cd.column}" {act};')
        return "\n".join(stmts) if stmts else "-- No changes needed."


def _mask(url: str) -> str:
    return re.sub(r":([^@]+)@", ":***@", url)


class SchemaDiffer:
    def __init__(self, source: Engine, target: Engine):
        self.source, self.target = source, target

    def compare(self, schema: str = "public") -> SchemaDiffResult:
        src_tables = self._tables(self.source, schema)
        tgt_tables = self._tables(self.target, schema)
        src_cols = self._columns(self.source, schema)
        tgt_cols = self._columns(self.target, schema)

        result = SchemaDiffResult(str(self.source.url), str(self.target.url), schema)

        for t in set(src_tables) - set(tgt_tables):
            result.table_diffs.append(TableDiff(t, DiffType.ADDED, src_tables[t]))
        for t in set(tgt_tables) - set(src_tables):
            result.table_diffs.append(TableDiff(t, DiffType.REMOVED, tgt_tables[t]))

        for t in set(src_tables) & set(tgt_tables):
            sc = {c["column_name"]: c for c in src_cols.get(t, [])}
            tc = {c["column_name"]: c for c in tgt_cols.get(t, [])}
            for col in set(sc) - set(tc):
                result.column_diffs.append(ColumnDiff(t, col, DiffType.ADDED, sc[col]))
            for col in set(tc) - set(sc):
                result.column_diffs.append(ColumnDiff(t, col, DiffType.REMOVED, target_def=tc[col]))
            for col in set(sc) & set(tc):
                changes = []
                if sc[col].get("data_type") != tc[col].get("data_type"):
                    changes.append(f"type: {tc[col]['data_type']} → {sc[col]['data_type']}")
                if sc[col].get("is_nullable") != tc[col].get("is_nullable"):
                    changes.append(f"nullable: {tc[col]['is_nullable']} → {sc[col]['is_nullable']}")
                if changes:
                    result.column_diffs.append(ColumnDiff(t, col, DiffType.MODIFIED, sc[col], tc[col], changes))
        return result

    def _tables(self, engine: Engine, schema: str) -> dict[str, int]:
        with connect(engine) as conn:
            rows = conn.execute(text(
                "SELECT table_name, COUNT(column_name) AS cc "
                "FROM information_schema.columns WHERE table_schema = :s "
                "GROUP BY table_name"
            ), {"s": schema}).mappings().all()
            return {r["table_name"]: r["cc"] for r in rows}

    def _columns(self, engine: Engine, schema: str) -> dict[str, list[dict]]:
        with connect(engine) as conn:
            rows = conn.execute(text(
                "SELECT table_name, column_name, data_type, is_nullable, "
                "column_default, character_maximum_length "
                "FROM information_schema.columns WHERE table_schema = :s "
                "ORDER BY table_name, ordinal_position"
            ), {"s": schema}).mappings().all()
        grouped: dict[str, list[dict]] = {}
        for r in rows:
            grouped.setdefault(r["table_name"], []).append(dict(r))
        return grouped
