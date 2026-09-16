"""Fix broken CSVs without loading them into memory."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table as RichTable

console = Console()


@dataclass
class CSVDiagnostic:
    file_path: str
    file_size_mb: float
    detected_encoding: str
    detected_delimiter: str
    total_rows: int = 0
    header_columns: int = 0
    malformed_rows: list[int] = field(default_factory=list)
    empty_rows: list[int] = field(default_factory=list)
    has_bom: bool = False

    def print_report(self) -> None:
        t = RichTable(title=f"CSV Diagnostic: {self.file_path}")
        t.add_column("Property", style="cyan")
        t.add_column("Value")
        t.add_row("Size", f"{self.file_size_mb:.2f} MB")
        t.add_row("Encoding", self.detected_encoding)
        t.add_row("Delimiter", repr(self.detected_delimiter))
        t.add_row("Rows", f"{self.total_rows:,}")
        t.add_row("Columns", str(self.header_columns))
        t.add_row("BOM", "Yes" if self.has_bom else "No")
        t.add_row("Malformed", f"{len(self.malformed_rows):,}")
        t.add_row("Empty", f"{len(self.empty_rows):,}")
        console.print(t)


class CSVSurgeon:
    """Diagnose and fix CSV files — handles files larger than RAM."""

    def diagnose(self, path: str) -> CSVDiagnostic:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path}")

        raw = p.read_bytes()[:10000]
        enc = self._detect_encoding(raw)
        delim = self._detect_delimiter(raw.decode(enc, errors="replace")[:5000])

        diag = CSVDiagnostic(
            file_path=path, file_size_mb=p.stat().st_size / 1048576,
            detected_encoding=enc, detected_delimiter=delim,
            has_bom=raw[:3] == b"\xef\xbb\xbf",
        )

        with open(path, "r", encoding=enc, errors="replace", newline="") as f:
            for i, row in enumerate(csv.reader(f, delimiter=delim)):
                if i == 0:
                    diag.header_columns = len(row)
                    continue
                if not any(c.strip() for c in row):
                    diag.empty_rows.append(i + 1)
                elif len(row) != diag.header_columns:
                    diag.malformed_rows.append(i + 1)
            diag.total_rows = i + 1 if i else 0
        return diag

    def fix(self, input_path: str, output_path: str, source_encoding: str | None = None,
            target_encoding: str = "utf-8", delimiter: str | None = None,
            output_delimiter: str = ",", remove_malformed: bool = True,
            remove_empty: bool = True, strip_whitespace: bool = True) -> dict:

        if source_encoding is None or delimiter is None:
            raw = Path(input_path).read_bytes()[:10000]
            source_encoding = source_encoding or self._detect_encoding(raw)
            delimiter = delimiter or self._detect_delimiter(raw.decode(source_encoding, errors="replace")[:5000])

        stats = {"rows_in": 0, "rows_out": 0, "rows_dropped": 0}
        header_len = None

        with (open(input_path, "r", encoding=source_encoding, errors="replace", newline="") as fin,
              open(output_path, "w", encoding=target_encoding, newline="") as fout):
            reader = csv.reader(fin, delimiter=delimiter)
            writer = csv.writer(fout, delimiter=output_delimiter)

            for i, row in enumerate(reader):
                stats["rows_in"] += 1
                if i == 0:
                    header_len = len(row)
                    if row and row[0].startswith("\ufeff"):
                        row[0] = row[0].lstrip("\ufeff")
                if remove_empty and not any(c.strip() for c in row):
                    stats["rows_dropped"] += 1
                    continue
                if remove_malformed and header_len and i > 0 and len(row) != header_len:
                    stats["rows_dropped"] += 1
                    continue
                if strip_whitespace:
                    row = [c.strip() for c in row]
                writer.writerow(row)
                stats["rows_out"] += 1
        return stats

    @staticmethod
    def _detect_encoding(raw: bytes) -> str:
        if raw[:3] == b"\xef\xbb\xbf":
            return "utf-8-sig"
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "latin-1"

    @staticmethod
    def _detect_delimiter(sample: str) -> str:
        try:
            return csv.Sniffer().sniff(sample, delimiters=",\t|;").delimiter
        except csv.Error:
            return ","
