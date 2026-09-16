import csv

import pytest

from toolkit.csv_surgeon import CSVSurgeon


@pytest.fixture
def surgeon():
    return CSVSurgeon()

@pytest.fixture
def clean_csv(tmp_path):
    p = tmp_path / "clean.csv"
    p.write_text("name,age,city\nAlice,30,Lagos\nBob,25,Abuja\n")
    return p

@pytest.fixture
def messy_csv(tmp_path):
    p = tmp_path / "messy.csv"
    p.write_text("name , age , city\nAlice , 30 , Lagos\n , , \nBob,25\nCharlie , 35 , Kano\n")
    return p

def test_diagnose_clean(surgeon, clean_csv):
    d = surgeon.diagnose(str(clean_csv))
    assert d.header_columns == 3 and len(d.malformed_rows) == 0

def test_fix_whitespace(surgeon, messy_csv, tmp_path):
    out = tmp_path / "fixed.csv"
    stats = surgeon.fix(str(messy_csv), str(out))
    with open(out) as f:
        assert next(csv.reader(f)) == ["name", "age", "city"]
    assert stats["rows_dropped"] > 0

def test_missing_file(surgeon):
    with pytest.raises(FileNotFoundError):
        surgeon.diagnose("/nonexistent.csv")
