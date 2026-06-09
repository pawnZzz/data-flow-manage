import pytest
from sqlglot.errors import ParseError

from app.services.sql_parser import parse_sql


def test_insert_select_direction():
    out = parse_sql("INSERT INTO dw.t SELECT * FROM src.a", dialect="mysql")
    assert "dw.t" in out["tables"]
    assert "src.a" in out["tables"]
    assert {"source": "dw.t", "target": "src.a", "edge_type": "data_flow"} in out["dependencies"]


def test_create_table_as_multi_source():
    out = parse_sql(
        "CREATE TABLE x AS SELECT * FROM a JOIN b ON a.id=b.id", dialect="mysql"
    )
    assert "x" in out["tables"]
    assert {"a", "b"} <= set(out["tables"])
    deps = {(d["source"], d["target"]) for d in out["dependencies"]}
    assert ("x", "a") in deps and ("x", "b") in deps


def test_cte_intermediate_excluded():
    out = parse_sql(
        "INSERT INTO dw.t WITH c AS (SELECT * FROM src.base) SELECT * FROM c",
        dialect="mysql",
    )
    assert "c" not in out["tables"]
    assert "src.base" in out["tables"]
    deps = {(d["source"], d["target"]) for d in out["dependencies"]}
    assert ("dw.t", "src.base") in deps
    assert all("c" not in pair for pair in deps)


def test_select_only_unrecognized():
    out = parse_sql("SELECT 1", dialect="mysql")
    assert out["tables"] == []
    assert out["dependencies"] == []
    assert len(out["unrecognized"]) == 1


def test_qualified_name_preserved():
    out = parse_sql("INSERT INTO dw.ods_user SELECT * FROM raw.log", dialect="mysql")
    assert "dw.ods_user" in out["tables"]
    assert "raw.log" in out["tables"]


def test_syntax_error_raises():
    with pytest.raises(ParseError):
        parse_sql("INSERT INTO", dialect="mysql")


def test_multi_statement_mixed():
    out = parse_sql("SELECT 1; INSERT INTO a SELECT * FROM b", dialect="mysql")
    assert {"a", "b"} <= set(out["tables"])
    assert len(out["unrecognized"]) == 1


def test_merge_and_update_lineage():
    # MERGE INTO tgt USING src → tgt 依赖 src
    m = parse_sql("MERGE INTO tgt USING src ON tgt.id=src.id "
                  "WHEN MATCHED THEN UPDATE SET a=1", dialect="postgres")
    assert {"source": "tgt", "target": "src", "edge_type": "data_flow"} in m["dependencies"]
    # UPDATE t SET ... FROM s → t 依赖 s
    u = parse_sql("UPDATE t SET x=1 FROM s WHERE t.id=s.id", dialect="postgres")
    assert {"source": "t", "target": "s", "edge_type": "data_flow"} in u["dependencies"]
