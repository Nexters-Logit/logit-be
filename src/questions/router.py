"""문항 API 엔드포인트"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.common.responses import RESPONSES_CREATE_WITH_AUTH, RESPONSES_CRUD_WITH_AUTH
from src.questions import service
from src.questions.schemas import (
    QuestionCreate,
    QuestionListItem,
    QuestionRead,
    QuestionUpdate,
)
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.post(
    "/",
    response_model=QuestionListItem,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES_CREATE_WITH_AUTH,
    summary="문항 생성",
    description="특정 프로젝트에 새로운 자기소개서 문항을 생성합니다.",
)
async def create_question(
    project_id: UUID,
    question_in: QuestionCreate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    새로운 문항을 생성합니다.

    - **project_id**: 문항이 속할 프로젝트의 UUID
    - **question_in**: 문항 내용
    """
    return await service.create_question(
        session=session,
        question_create=question_in,
        project_id=project_id,
        user_id=current_user.id,
    )


@router.get(
    "/",
    response_model=List[QuestionListItem],
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="문항 목록 조회",
    description="특정 프로젝트에 속한 모든 자기소개서 문항 목록을 조회합니다.",
)
async def read_questions(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    프로젝트의 문항 목록을 조회합니다.

    - **project_id**: 문항을 조회할 프로젝트의 UUID
    """
    return await service.get_questions(
        session=session, project_id=project_id, user_id=current_user.id
    )


@router.get(
    "/{question_id}",
    response_model=QuestionRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="문항 상세 조회",
    description="특정 자기소개서 문항의 상세 정보를 조회합니다.",
)
async def read_question(
    project_id: UUID,
    question_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    특정 문항의 상세 정보를 조회합니다.

    - **project_id**: 프로젝트의 UUID
    - **question_id**: 조회할 문항의 UUID
    """
    question = await service.get_question(
        session=session,
        question_id=question_id,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )
    return question


@router.patch(
    "/{question_id}",
    response_model=QuestionRead,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="문항 수정",
    description="기존 자기소개서 문항의 내용을 수정합니다.",
)
async def update_question(
    project_id: UUID,
    question_id: UUID,
    question_in: QuestionUpdate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    기존 문항의 내용을 수정합니다.

    - **project_id**: 프로젝트의 UUID
    - **question_id**: 수정할 문항의 UUID
    - **question_in**: 수정할 필드 (부분 업데이트 지원)
    """
    question = await service.get_question(
        session=session,
        question_id=question_id,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )
    return await service.update_question(
        session=session, db_question=question, question_update=question_in
    )


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="문항 삭제",
    description="자기소개서 문항을 삭제합니다. 이 작업은 soft delete로 처리됩니다.",
)
async def delete_question(
    project_id: UUID,
    question_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    문항을 삭제합니다.

    - **project_id**: 프로젝트의 UUID
    - **question_id**: 삭제할 문항의 UUID
    - soft delete 방식으로 처리됩니다.
    """
    question = await service.get_question(
        session=session,
        question_id=question_id,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )
    await service.delete_question(session=session, db_question=question)
    return None
