from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.questions.models import Question
from src.questions.schemas import QuestionBulkCreate, QuestionCreate, QuestionUpdate


async def create_question(
    session: AsyncSession,
    question_create: QuestionCreate,
    project_id: UUID,
    user_id: UUID,
) -> Question:
    """문항 단건 생성"""
    db_question = Question(
        project_id=project_id,
        user_id=user_id,
        question=question_create.question,
        max_length=question_create.max_length,
        order=question_create.order,
    )
    session.add(db_question)
    await session.commit()
    await session.refresh(db_question)
    return db_question


async def bulk_create_questions(
    session: AsyncSession,
    bulk_create: QuestionBulkCreate,
    project_id: UUID,
    user_id: UUID,
) -> List[Question]:
    """문항 일괄 생성"""
    db_questions = []

    for item in bulk_create.questions:
        db_question = Question(
            project_id=project_id,
            user_id=user_id,
            question=item.question,
            max_length=item.max_length,
            order=item.order,
        )
        session.add(db_question)
        db_questions.append(db_question)

    await session.commit()

    # refresh all
    for q in db_questions:
        await session.refresh(q)

    return db_questions


async def get_questions(
    session: AsyncSession, project_id: UUID, user_id: UUID
) -> List[Question]:
    """프로젝트의 문항 목록 조회 (order 순)"""
    statement = (
        select(Question)
        .where(Question.project_id == project_id)
        .where(Question.user_id == user_id)
        .order_by(Question.order)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_question(
    session: AsyncSession, question_id: UUID, project_id: UUID, user_id: UUID
) -> Optional[Question]:
    """문항 단건 조회"""
    statement = (
        select(Question)
        .where(Question.id == question_id)
        .where(Question.project_id == project_id)
        .where(Question.user_id == user_id)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_question(
    session: AsyncSession, db_question: Question, question_update: QuestionUpdate
) -> Question:
    """문항 수정"""
    question_data = question_update.model_dump(exclude_unset=True)
    for key, value in question_data.items():
        setattr(db_question, key, value)

    db_question.updated_at = datetime.now(timezone.utc)

    session.add(db_question)
    await session.commit()
    await session.refresh(db_question)
    return db_question


async def delete_question(
    session: AsyncSession, db_question: Question, project_id: UUID, user_id: UUID
) -> None:
    """문항 삭제 및 order 재정렬"""
    deleted_order = db_question.order

    # 문항 삭제
    await session.delete(db_question)

    # 삭제된 문항보다 뒤에 있는 문항들의 order를 -1 (user_id 필터 포함)
    statement = (
        select(Question)
        .where(Question.project_id == project_id)
        .where(Question.user_id == user_id)
        .where(Question.order > deleted_order)
    )
    result = await session.execute(statement)
    questions_to_update = result.scalars().all()

    for q in questions_to_update:
        q.order -= 1
        session.add(q)

    await session.commit()
