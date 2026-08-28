"""
对话状态表 ORM 模型（客服库重建表：cs_dialogue_state）
"""
from sqlalchemy import TEXT, BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from financecs.repository.base import Base


class DialogueRecord(Base):
    __tablename__ = "cs_dialogue_state"

    sender_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    customer_no: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="")
    state_json: Mapped[str] = mapped_column(TEXT, nullable=False, default="{}")
    state_version: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
