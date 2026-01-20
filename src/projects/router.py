from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.common.responses import RESPONSES_CREATE_WITH_AUTH, RESPONSES_CRUD_WITH_AUTH
from src.projects import service
from src.projects.schemas import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES_CREATE_WITH_AUTH,
    summary="프로젝트 생성",
    description="새로운 프로젝트를 생성합니다. 프로젝트는 경험을 그룹화하는 컨테이너 역할을 합니다.",
)
async def create_project(
    project_in: ProjectCreate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    Create a new project.

    - **name**: 프로젝트 이름
    - **description**: 프로젝트에 대한 설명 (선택 사항)
    """
    return await service.create_project(
        session=session, project_create=project_in, user_id=current_user.id
    )


@router.get(
    "/",
    response_model=List[ProjectListItem],
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 목록 조회",
    description="현재 사용자가 소유한 모든 프로젝트의 목록을 조회합니다. 페이지네이션을 지원합니다.",
)
async def read_projects(
    session: SessionDep,
    current_user: ActiveUser,
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(100, ge=1, le=200, description="페이지당 최대 항목 수"),
):
    """
    Get a list of all projects for the current user.

    - **skip**: Number of projects to skip (for pagination)
    - **limit**: Maximum number of projects to return (for pagination)
    """
    return await service.get_projects(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 상세 조회",
    description="특정 프로젝트의 상세 정보를 ID로 조회합니다. 소유권이 없는 경우 404 에러를 반환합니다.",
)
async def read_project(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    Get a single project by its ID.

    - **project_id**: The UUID of the project to retrieve.
    """
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 수정",
    description="기존 프로젝트의 이름 또는 설명을 수정합니다. 부분 업데이트를 지원합니다.",
)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    Update an existing project.

    - **project_id**: The UUID of the project to update.
    - **project_in**: The fields to update.
    """
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


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 삭제",
    description="프로젝트를 삭제합니다. 이 작업은 soft delete로 처리됩니다 (is_deleted 플래그 설정).",
)
async def delete_project(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    "Delete" a project by setting its is_deleted flag to True (soft delete).

    - **project_id**: The UUID of the project to delete.
    """
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    await service.delete_project(session=session, db_project=project)
    return None  # Return None for 204 No Content
