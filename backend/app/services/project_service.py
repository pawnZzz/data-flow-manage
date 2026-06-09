import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cypher import projects as pq
from app.exceptions import ConflictError
from app.models import MemberRole, Project, ProjectMember, ProjectStatus, User
from app.repositories.graph_repo import GraphRepo

logger = logging.getLogger("app.audit")


def create_project(db: Session, user: User, name: str, description: str | None) -> Project:
    project = Project(name=name, description=description, created_by=user.id)
    db.add(project)
    db.flush()  # 取自增 id
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=MemberRole.owner))
    db.commit()
    db.refresh(project)
    logger.info("project.create user=%s project=%s name=%s", user.id, project.id, name)
    return project


def list_my_projects(
    db: Session, user: User, include_archived: bool = False
) -> list[tuple[Project, MemberRole]]:
    stmt = (
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
    )
    if include_archived:
        stmt = stmt.where(Project.status != ProjectStatus.deleting)  # 归档可见，删除中永不列出
    else:
        stmt = stmt.where(Project.status == ProjectStatus.active)
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def update_project(
    db: Session,
    actor: User,
    project: Project,
    name: str | None = None,
    description: str | None = None,
) -> Project:
    changed: dict[str, list] = {}
    if name is not None and name != project.name:
        changed["name"] = [project.name, name]
        project.name = name
    if description is not None and description != project.description:
        changed["description"] = [project.description, description]
        project.description = description
    if not changed:
        return project
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project.update user=%s project=%s changed=%s", actor.id, project.id, changed)
    return project


def archive_project(db: Session, actor: User, project: Project) -> Project:
    project.status = ProjectStatus.archived
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project.archive user=%s project=%s", actor.id, project.id)
    return project


def unarchive_project(db: Session, actor: User, project: Project) -> Project:
    if project.status != ProjectStatus.archived:
        raise ConflictError("仅归档项目可恢复", {"code": "PROJECT_NOT_ARCHIVED"})
    project.status = ProjectStatus.active
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project.unarchive user=%s project=%s", actor.id, project.id)
    return project


def purge_project(db: Session, repo: GraphRepo, actor: User, project: Project) -> dict:
    if project.status == ProjectStatus.active:
        raise ConflictError("项目须先归档才能永久删除", {"code": "PROJECT_NOT_ARCHIVED"})
    project.status = ProjectStatus.deleting
    db.add(project)
    db.commit()  # 崩溃也停在 deleting，可重跑
    pid = project.id
    deleted_nodes = repo.run_write(pq.PURGE_NODES, pid=pid)[0]["deleted_nodes"]
    deleted_schemas = repo.run_write(pq.PURGE_SCHEMAS, pid=pid)[0]["deleted_schemas"]
    db.query(ProjectMember).filter(ProjectMember.project_id == pid).delete()
    db.delete(project)
    db.commit()
    logger.info("project.purge user=%s project=%s nodes=%s schemas=%s",
                actor.id, pid, deleted_nodes, deleted_schemas)
    return {"deleted_nodes": deleted_nodes, "deleted_schemas": deleted_schemas}
