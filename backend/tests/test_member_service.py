import pytest

from app.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models import MemberRole
from app.services import member_service


def test_add_member_by_username(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    m = member_service.add_member(
        db_session, actor_role=MemberRole.owner, actor=owner,
        project=p, username="bob", email=None, role="editor",
    )
    assert m.user_id == bob.id
    assert m.role == MemberRole.editor


def test_add_member_unknown_user_404(db_session, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    with pytest.raises(NotFoundError):
        member_service.add_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, username="ghost", email=None, role="viewer",
        )


def test_add_member_duplicate_409(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    with pytest.raises(ConflictError):
        member_service.add_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, username="bob", email=None, role="editor",
        )


def test_admin_cannot_add_owner(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    with pytest.raises(PermissionDenied):
        member_service.add_member(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, username="bob", email=None, role="owner",
        )


def test_remove_owner_forbidden(db_session, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    with pytest.raises(PermissionDenied):
        member_service.remove_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, target_user_id=owner.id,
        )


def test_change_last_owner_conflict(db_session, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    with pytest.raises(ConflictError):
        member_service.change_role(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, target_user_id=owner.id, new_role="admin",
        )


def test_admin_cannot_change_to_owner(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "editor")
    with pytest.raises(PermissionDenied):
        member_service.change_role(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, target_user_id=bob.id, new_role="owner",
        )


def test_change_role_ok(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    m = member_service.change_role(
        db_session, actor_role=MemberRole.admin, actor=owner,
        project=p, target_user_id=bob.id, new_role="editor",
    )
    assert m.role == MemberRole.editor


def test_remove_member_ok(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    member_service.remove_member(
        db_session, actor_role=MemberRole.admin, actor=owner,
        project=p, target_user_id=bob.id,
    )
    remaining = {m.user_id for m in member_service.list_members(db_session, p.id)}
    assert bob.id not in remaining


def test_add_member_by_email(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob", email="bob@corp.com")
    p = seed.project(owner)
    m = member_service.add_member(
        db_session, actor_role=MemberRole.owner, actor=owner,
        project=p, username=None, email="bob@corp.com", role="viewer",
    )
    assert m.user_id == bob.id
    assert m.role == MemberRole.viewer


def test_add_member_invalid_role_raises(db_session, seed):
    from app.exceptions import ValidationError

    owner = seed.user("owner")
    seed.user("bob")
    p = seed.project(owner)
    with pytest.raises(ValidationError):
        member_service.add_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, username="bob", email=None, role="superadmin",
        )


def test_admin_cannot_add_admin(db_session, seed):
    owner = seed.user("owner")
    seed.user("bob")
    p = seed.project(owner)
    with pytest.raises(PermissionDenied):
        member_service.add_member(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, username="bob", email=None, role="admin",
        )


def test_admin_cannot_promote_editor_to_admin(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "editor")
    with pytest.raises(PermissionDenied):
        member_service.change_role(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, target_user_id=bob.id, new_role="admin",
        )


def test_admin_cannot_change_existing_admin(db_session, seed):
    owner = seed.user("owner")
    carol = seed.user("carol")
    p = seed.project(owner)
    seed.member(p, carol, "admin")
    with pytest.raises(PermissionDenied):
        member_service.change_role(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, target_user_id=carol.id, new_role="viewer",
        )


def test_owner_can_add_admin(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    m = member_service.add_member(
        db_session, actor_role=MemberRole.owner, actor=owner,
        project=p, username="bob", email=None, role="admin",
    )
    assert m.role == MemberRole.admin


def test_owner_can_promote_to_admin(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "editor")
    m = member_service.change_role(
        db_session, actor_role=MemberRole.owner, actor=owner,
        project=p, target_user_id=bob.id, new_role="admin",
    )
    assert m.role == MemberRole.admin
