from app.models import MemberRole, Project, ProjectMember, ProjectStatus


def test_member_role_levels_ordered():
    assert MemberRole.viewer.level < MemberRole.editor.level
    assert MemberRole.editor.level < MemberRole.admin.level
    assert MemberRole.admin.level < MemberRole.owner.level


def test_project_status_values():
    assert ProjectStatus.active.value == "active"
    assert {s.value for s in ProjectStatus} == {"active", "archived", "deleting"}


def test_tablenames():
    assert Project.__tablename__ == "projects"
    assert ProjectMember.__tablename__ == "project_members"
