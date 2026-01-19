from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.questions import service
from src.questions.schemas import (
    QuestionBulkCreate,
    QuestionCreate,
    QuestionListItem,
    QuestionRead,
    QuestionReorder,
    QuestionUpdate,
)
from src.users.dependencies import ActiveUser, SessionDep

router = APIRouter()


@router.post("/", response_model=QuestionListItem, status_code=status.HTTP_201_CREATED)
async def create_question(
    project_id: UUID,
    question_in: QuestionCreate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """문항 단건 생성"""
    return await service.create_question(
        session=session,
        question_create=question_in,
        project_id=project_id,
        user_id=current_user.id,
    )


@router.post("/bulk", response_model=List[QuestionListItem], status_code=status.HTTP_201_CREATED)
async def create_questions_bulk(
    project_id: UUID,
    bulk_in: QuestionBulkCreate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """문항 일괄 생성 (프로젝트 첫 생성 시)"""
    return await service.bulk_create_questions(
        session=session,
        bulk_create=bulk_in,
        project_id=project_id,
        user_id=current_user.id,
    )


@router.get("/", response_model=List[QuestionListItem])
async def read_questions(
    project_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """프로젝트의 문항 목록 조회"""
    return await service.get_questions(
        session=session, project_id=project_id, user_id=current_user.id
    )


@router.get("/{question_id}", response_model=QuestionRead)
async def read_question(
    project_id: UUID,
    question_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """문항 단건 조회"""
    question = await service.get_question(
        session=session,
        question_id=question_id,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )
    return question


@router.patch("/{question_id}", response_model=QuestionRead)
async def update_question(
    project_id: UUID,
    question_id: UUID,
    question_in: QuestionUpdate,
    session: SessionDep,
    current_user: ActiveUser,
):
    """문항 수정"""
    question = await service.get_question(
        session=session,
        question_id=question_id,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )
    return await service.update_question(
        session=session, db_question=question, question_update=question_in
    )


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    project_id: UUID,
    question_id: UUID,
    session: SessionDep,
    current_user: ActiveUser,
):
    """문항 삭제 (order 자동 재정렬)"""
    question = await service.get_question(
        session=session,
        question_id=question_id,
        project_id=project_id,
        user_id=current_user.id,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )
    await service.delete_question(
        session=session, db_question=question, project_id=project_id
    )


@router.patch("/reorder", response_model=List[QuestionListItem])
async def reorder_questions(
    project_id: UUID,
    reorder_in: QuestionReorder,
    session: SessionDep,
    current_user: ActiveUser,
):
    """문항 순서 재정렬"""
    return await service.reorder_questions(
        session=session,
        project_id=project_id,
        user_id=current_user.id,
        question_ids=reorder_in.question_ids,
    )
