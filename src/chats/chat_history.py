"""PostgreSQL 기반 채팅 히스토리 관리"""

from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .models import Chat, ChatRole


class PostgresChatMessageHistory(BaseChatMessageHistory):
    """
    대화 기록을 PostgreSQL DB에서 로드하는 클래스
    (LangChain RunnableWithMessageHistory 연동용)
    """

    def __init__(self, db: AsyncSession, question_id: UUID):
        self.db = db
        self.question_id = question_id
        self._messages: list[BaseMessage] = []

    @property
    def messages(self) -> list[BaseMessage]:
        """동기 접근 시 캐시된 메시지 반환"""
        return self._messages

    async def aget_messages(self) -> list[BaseMessage]:
        """DB에서 메시지를 비동기로 로드"""
        stmt = (
            select(Chat)
            .where(Chat.question_id == self.question_id)
            .order_by(Chat.created_at)
        )
        result = await self.db.execute(stmt)
        db_messages = result.scalars().all()

        self._messages = []
        for msg in db_messages:
            if msg.role == ChatRole.USER:
                self._messages.append(HumanMessage(content=msg.content))
            elif msg.role == ChatRole.ASSISTANT:
                self._messages.append(AIMessage(content=msg.content))

        return self._messages

    def add_message(self, message: BaseMessage) -> None:
        """메시지 추가 (DB 저장은 service.py에서 처리)"""
        self._messages.append(message)

    async def aadd_messages(self, messages: list[BaseMessage]) -> None:
        """비동기로 메시지 추가"""
        self._messages.extend(messages)

    def clear(self) -> None:
        """캐시된 메시지 초기화"""
        self._messages = []
