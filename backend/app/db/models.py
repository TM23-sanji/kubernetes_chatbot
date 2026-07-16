from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Boolean, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    title = Column(String, default="New conversation")
    starred = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON)
    thinking_steps = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(String, primary_key=True)
    data_version = Column(String)
    prompt_version = Column(String)
    dataset_name = Column(String)
    faithfulness = Column(Float)
    relevancy = Column(Float)
    context_recall = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(String, primary_key=True)
    data_version = Column(String)
    files_processed = Column(JSON)
    chunk_count = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
