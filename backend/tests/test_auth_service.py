import pytest

from app.exceptions import AuthError, ConflictError
from app.models import User
from app.security import verify_password
from app.services import auth_service


def test_register_creates_user(db_session):
    user = auth_service.register(db_session, "alice", "alice@x.com", "secret", "Alice")
    assert user.id is not None
    assert user.username == "alice"
    assert verify_password("secret", user.password_hash)


def test_register_duplicate_username_conflicts(db_session):
    auth_service.register(db_session, "bob", "bob@x.com", "secret", None)
    with pytest.raises(ConflictError):
        auth_service.register(db_session, "bob", "bob2@x.com", "secret", None)


def test_authenticate_success(db_session):
    auth_service.register(db_session, "carol", "carol@x.com", "secret", None)
    user = auth_service.authenticate(db_session, "carol", "secret")
    assert user.username == "carol"


def test_authenticate_wrong_password_raises(db_session):
    auth_service.register(db_session, "dave", "dave@x.com", "secret", None)
    with pytest.raises(AuthError):
        auth_service.authenticate(db_session, "dave", "wrong")


def test_change_password(db_session):
    user = auth_service.register(db_session, "eve", "eve@x.com", "secret", None)
    auth_service.change_password(db_session, user, "secret", "newpass")
    assert auth_service.authenticate(db_session, "eve", "newpass").id == user.id
