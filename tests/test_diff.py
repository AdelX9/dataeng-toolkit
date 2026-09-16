from toolkit.schema_diff import ColumnDiff, DiffType, SchemaDiffResult, TableDiff


def test_empty_diff():
    r = SchemaDiffResult("pg://a", "pg://b", "public")
    assert "identical" in r.summary()

def test_added_table():
    r = SchemaDiffResult("pg://a", "pg://b", "public",
        table_diffs=[TableDiff("users", DiffType.ADDED, 5)])
    assert "users" in r.summary()

def test_migration_sql():
    r = SchemaDiffResult("pg://a", "pg://b", "public",
        column_diffs=[ColumnDiff("users", "email", DiffType.ADDED,
            source_def={"data_type": "varchar", "is_nullable": "NO"})])
    assert "ADD COLUMN" in r.migration_sql()
