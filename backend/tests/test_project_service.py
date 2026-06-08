from sqlalchemy import select

from app.models import MemberRole, ProjectMember, ProjectStatus
from app.services import project_service


def test_create_project_makes_owner(db_session, seed):
    user = seed.user("alice")
    p = project_service.create_project(db_session, user, "数仓", None)
    assert p.id is not None
    assert p.status == ProjectStatus.active
    members = db_session.scalars(
        select(ProjectMember).where(ProjectMember.project_id == p.id)
    ).all()
    assert len(members) == 1
    assert members[0].role == MemberRole.owner
    assert members[0].user_id == user.id


def test_list_my_projects_excludes_archived_by_default(db_session, seed):
    user = seed.user("alice")
    active = project_service.create_project(db_session, user, "active-proj", None)
    archived = project_service.create_project(db_session, user, "archived-proj", None)
    project_service.archive_project(db_session, user, archived)
    rows = project_service.list_my_projects(db_session, user, include_archived=False)
    ids = {p.id for p, _role in rows}
    assert active.id in ids
    assert archived.id not in ids


def test_list_my_projects_includes_archived_when_asked(db_session, seed):
    user = seed.user("alice")
    archived = project_service.create_project(db_session, user, "a", None)
    project_service.archive_project(db_session, user, archived)
    rows = project_service.list_my_projects(db_session, user, include_archived=True)
    assert archived.id in {p.id for p, _ in rows}


def test_update_project_changes_name(db_session, seed):
    user = seed.user("alice")
    p = project_service.create_project(db_session, user, "old", None)
    project_service.update_project(db_session, user, p, name="new", description="d")
    assert p.name == "new"
    assert p.description == "d"
