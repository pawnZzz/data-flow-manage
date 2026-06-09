import pytest
from pydantic import ValidationError

from app.schemas.sql_import import CommitRequest, CommitTable, PreviewRequest


def test_preview_request_defaults():
    r = PreviewRequest(sql="SELECT 1")
    assert r.dialect == "mysql"


def test_preview_request_rejects_empty_sql():
    with pytest.raises(ValidationError):
        PreviewRequest(sql="")


def test_commit_table_default_type():
    t = CommitTable(name="dw.t")
    assert t.type == "table"


def test_commit_request_defaults_empty_lists():
    r = CommitRequest()
    assert r.tables == [] and r.dependencies == []
