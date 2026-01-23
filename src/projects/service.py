from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.projects.models import Project
from src.projects.schemas import ProjectCreate, ProjectUpdate
from src.questions.models import Question


async def create_project(
    session: AsyncSession, project_create: ProjectCreate, user_id: UUID
) -> Project:
    """프로젝트 생성 (문항 포함)"""
    # questions를 제외한 프로젝트 데이터
    project_data = project_create.model_dump(exclude={"questions"})

    db_project = Project(
        **project_data,
        user_id=user_id,
    )
    session.add(db_project)
    await session.flush()  # project.id 생성을 위해 flush

    # 문항 생성 (order는 리스트 순서 기반으로 자동 생성)
    for idx, question_data in enumerate(project_create.questions, start=1):
        db_question = Question(
            project_id=db_project.id,
            user_id=user_id,
            question=question_data.question,
            max_length=question_data.max_length,
            order=idx,
        )
        session.add(db_question)

    await session.commit()
    await session.refresh(db_project)
    return db_project


async def get_projects(
    session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100
) -> List[Project]:
    """사용자의 프로젝트 목록 조회 (삭제되지 않은 것만, 최근 활동순)"""
    statement = (
        select(Project)
        .where(Project.user_id == user_id)
        .where(Project.deleted_at.is_(None))
        .order_by(Project.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_project(
    session: AsyncSession, project_id: UUID, user_id: UUID
) -> Optional[Project]:
    """프로젝트 단건 조회 (삭제되지 않은 것만, 조회 시 updated_at 갱신)"""
    statement = (
        select(Project)
        .where(Project.id == project_id)
        .where(Project.user_id == user_id)
        .where(Project.deleted_at.is_(None))
    )
    result = await session.execute(statement)
    project = result.scalar_one_or_none()

    if project:
        project.updated_at = datetime.now(timezone.utc)
        session.add(project)
        await session.commit()
        await session.refresh(project)

    return project


async def update_project(
    session: AsyncSession, db_project: Project, project_update: ProjectUpdate
) -> Project:
    """프로젝트 수정"""
    project_data = project_update.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(db_project, key, value)

    db_project.updated_at = datetime.now(timezone.utc)

    session.add(db_project)
    await session.commit()
    await session.refresh(db_project)
    return db_project


async def delete_project(
    session: AsyncSession, db_project: Project
) -> Project:
    """프로젝트 삭제 (Soft Delete)"""
    db_project.deleted_at = datetime.now(timezone.utc)

    session.add(db_project)
    await session.commit()
    await session.refresh(db_project)
    return db_project
