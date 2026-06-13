"""프로젝트 API 엔드포인트"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.common.responses import RESPONSES_CREATE_WITH_AUTH, RESPONSES_CRUD_WITH_AUTH
from src.projects import service
from src.projects.schemas import (
    ProjectCreate,
    ProjectCreateResponse,
    ProjectListItem,
    ProjectRead,
    ProjectUpdate,
)
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.post(
    "/",
    response_model=ProjectCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES_CREATE_WITH_AUTH,
    summary="프로젝트 생성",
)
async def create_project(
    project_in: ProjectCreate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    새로운 프로젝트를 생성합니다.

    - **company**: 기업명
    - **job_position**: 직무
    - **recruit_notice**: 채용 공고 내용
    - **due_date**: 마감일 (선택)
    - **questions**: 문항 목록 (선택)

    프로젝트 정보와 함께 생성된 문항 ID 목록을 반환합니다.
    """
    return await service.create_project(
        session=session, project_create=project_in, user_id=current_user.id
    )


@router.get(
    "/",
    response_model=list[ProjectListItem],
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 목록 조회",
)
async def read_projects(
    session: SessionDep,
    current_user: ActiveUser,
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(100, ge=1, le=200, description="페이지당 최대 항목 수"),
):
    """
    현재 사용자의 프로젝트 목록을 조회합니다.

    - **skip**: 건너뛸 항목 수 (페이지네이션)
    - **limit**: 최대 반환 항목 수 (페이지네이션)
    """
    return await service.get_projects(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 상세 조회",
)
async def read_project(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    특정 프로젝트의 상세 정보를 조회합니다.

    - **project_id**: 조회할 프로젝트의 UUID
    - 프로젝트를 찾을 수 없거나 소유권이 없는 경우 404 에러를 반환합니다.
    """
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 수정",
)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    기존 프로젝트의 정보를 수정합니다.

    - **project_id**: 수정할 프로젝트의 UUID
    - **project_in**: 수정할 필드 (부분 업데이트 지원)
    """
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return await service.update_project(
        session=session, db_project=project, project_update=project_in
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="프로젝트 삭제",
)
async def delete_project(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    프로젝트를 삭제합니다.

    - **project_id**: 삭제할 프로젝트의 UUID
    - soft delete 방식으로 처리됩니다.
    """
    project = await service.get_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    await service.delete_project(session=session, db_project=project)
    return None
