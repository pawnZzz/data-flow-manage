import pytest
from pydantic import ValidationError

from app.schemas.project import AddMemberRequest, CreateProjectRequest


def test_create_project_rejects_empty_name():
    with pytest.raises(ValidationError):
        CreateProjectRequest(name="")


def test_create_project_ok():
    r = CreateProjectRequest(name="数仓血缘", description=None)
    assert r.name == "数仓血缘"


def test_add_member_requires_username_or_email():
    with pytest.raises(ValidationError):
        AddMemberRequest(role="viewer")


def test_add_member_with_username_ok():
    r = AddMemberRequest(username="bob", role="editor")
    assert r.username == "bob"
    assert r.role == "editor"


def test_add_member_rejects_invalid_role():
    with pytest.raises(ValidationError):
        AddMemberRequest(username="bob", role="superadmin")


def test_add_member_with_email_ok():
    r = AddMemberRequest(email="bob@example.com", role="viewer")
    assert r.email == "bob@example.com"
    assert r.role == "viewer"
