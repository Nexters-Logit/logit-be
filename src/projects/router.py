from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.projects import service
from src.projects.schemas import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """프로젝트 생성"""
    return await service.create_project(
        session=session, project_create=project_in, user_id=current_user.id
    )


@router.get("/", response_model=List[ProjectListItem])
async def read_projects(
    session: SessionDep,
    current_user: ActiveUser,
    skip: int = 0,
    limit: int = 100,
):
    """내 프로젝트 목록 조회"""
    return await service.get_projects(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get("/{project_id}", response_model=ProjectRead)
async def read_project(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """프로젝트 단건 조회"""
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """프로젝트 수정"""
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return await service.update_project(
        session=session, db_project=project, project_update=project_in
    )


@router.delete("/{project_id}", response_model=ProjectRead)
async def delete_project(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """프로젝트 삭제 (Soft Delete)"""
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return await service.delete_project(session=session, db_project=project)
