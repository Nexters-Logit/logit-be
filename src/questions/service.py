from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from src.projects.models import Project
from src.questions.models import Question
from src.questions.schemas import QuestionCreate, QuestionUpdate


async def get_next_order(session: AsyncSession, project_id: UUID, user_id: UUID) -> int:
    """프로젝트의 다음 order 값 계산 (max + 1)"""
    statement = (
        select(func.max(Question.order))
        .where(Question.project_id == project_id)
        .where(Question.user_id == user_id)
        .where(Question.deleted_at.is_(None))
    )
    result = await session.execute(statement)
    max_order = result.scalar()
    return (max_order or 0) + 1


async def create_question(
    session: AsyncSession,
    question_create: QuestionCreate,
    project_id: UUID,
    user_id: UUID,
) -> Question:
    """문항 단건 생성"""

    statement = select(Project.id).where(                                                                                                                                                          
        Project.id == project_id,                                                                                                                                                                  
        Project.user_id == user_id,                                                                                                                                                                
        Project.deleted_at.is_(None)                                                                                                                                                               
    )                                                                                                                                                                                              
    result = await session.execute(statement)                                                                                                                                                      
    if not result.scalar():                                                                                                                                                                        
        raise HTTPException(status_code=404, detail="Project not found")

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


async def get_questions(
    session: AsyncSession, project_id: UUID, user_id: UUID
) -> List[Question]:
    """프로젝트의 문항 목록 조회 (삭제되지 않은 것만, order 순)"""
    statement = (
        select(Question)
        .where(Question.project_id == project_id)
        .where(Question.user_id == user_id)
        .where(Question.deleted_at.is_(None))
        .order_by(Question.order)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_question(
    session: AsyncSession, question_id: UUID, project_id: UUID, user_id: UUID
) -> Optional[Question]:
    """문항 단건 조회 (삭제되지 않은 것만)"""
    statement = (
        select(Question)
        .where(Question.id == question_id)
        .where(Question.project_id == project_id)
        .where(Question.user_id == user_id)
        .where(Question.deleted_at.is_(None))
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
    session: AsyncSession, db_question: Question
) -> Question:
    """문항 삭제 (Soft Delete)"""
    db_question.deleted_at = datetime.now(timezone.utc)

    session.add(db_question)
    await session.commit()
    await session.refresh(db_question)
    return db_question
