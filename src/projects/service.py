from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.projects.models import Project
from src.projects.schemas import ProjectCreate, ProjectUpdate


async def create_project(session: AsyncSession, project_create: ProjectCreate) -> Project:
    db_project = Project.model_validate(project_create)
    session.add(db_project)
    await session.commit()
    await session.refresh(db_project)
    return db_project


async def get_projects(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Project]:
    statement = select(Project).offset(skip).limit(limit)
    result = await session.execute(statement)
    return result.scalars().all()


async def get_project(session: AsyncSession, project_id: int) -> Optional[Project]:
    return await session.get(Project, project_id)


async def update_project(
    session: AsyncSession, db_project: Project, project_update: ProjectUpdate
) -> Project:
    project_data = project_update.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(db_project, key, value)
    
    session.add(db_project)
    await session.commit()
    await session.refresh(db_project)
    return db_project


async def delete_project(session: AsyncSession, project_id: int) -> Optional[Project]:
    db_project = await session.get(Project, project_id)
    if db_project:
        await session.delete(db_project)
        await session.commit()
    return db_project
