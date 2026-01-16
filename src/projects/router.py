from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_db
from src.projects import service
from src.projects.schemas import ProjectCreate, ProjectRead, ProjectUpdate, TestResponse

router = APIRouter()

@router.get("/test", response_model=TestResponse, status_code=status.HTTP_200_OK)
async def test():
    try:
        return TestResponse(message="Hello, World!", status="success", data=["test1", "test2"])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    session: AsyncSession = Depends(get_async_db),
):
    return await service.create_project(session=session, project_create=project_in)


@router.get("/", response_model=List[ProjectRead])
async def read_projects(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_db),
):
    return await service.get_projects(session=session, skip=skip, limit=limit)


@router.get("/{project_id}", response_model=ProjectRead)
async def read_project(
    project_id: int,
    session: AsyncSession = Depends(get_async_db),
):
    project = await service.get_project(session=session, project_id=project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    session: AsyncSession = Depends(get_async_db),
):
    project = await service.get_project(session=session, project_id=project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return await service.update_project(
        session=session, db_project=project, project_update=project_in
    )


@router.delete("/{project_id}", response_model=ProjectRead)
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(get_async_db),
):
    project = await service.get_project(session=session, project_id=project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return await service.delete_project(session=session, project_id=project_id)
