from sqlalchemy import Column, String, Boolean, Float, Integer, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id = Column(String(255), unique=True, nullable=False, index=True)
    platform_source = Column(String(50), nullable=False)  # 'whatsapp' | 'instagram'
    full_name = Column(String(100))
    role = Column(String(20), default="customer")  # 'customer' | 'admin'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chat_sessions = relationship("ChatSession", back_populates="user")
    orders = relationship("Order", back_populates="user")
    safety_logs = relationship("SafetyLog", back_populates="user")


class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phppos_item_id = Column(Integer, unique=True, index=True)
    barcode = Column(String(100))
    sku = Column(String(50), index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    category = Column(String(100), index=True)
    image_url = Column(Text)
    metadata_ = Column("metadata", JSON)  # 'metadata' is reserved in some contexts, explicit name mapping
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), index=True)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True))
    status = Column(String(50), default="active", index=True)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id"), index=True)
    sender_type = Column(String(20), nullable=False)  # 'user' | 'agent' | 'admin'
    content = Column(Text)
    image_url = Column(Text)
    sentiment_score = Column(Float, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), index=True)
    paystack_reference = Column(String(100), index=True)
    phppos_sale_id = Column(Integer)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="orders")


class SafetyLog(Base):
    __tablename__ = "safety_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), index=True)
    prompt_text = Column(Text)
    violation_category = Column(String(100), index=True)
    action_taken = Column(String(50), default="blocked")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="safety_logs")
