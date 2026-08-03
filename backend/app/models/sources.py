"""Source management database models for tenant and admin source CRUD."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class UserSource(Base):
    """User-specific custom sources (tenant system)."""
    __tablename__ = "user_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    source_type = Column(String(20), nullable=False)  # rss, twitter, telegram, reddit, onchain
    url_or_handle = Column(String(500), nullable=False)
    priority = Column(Integer, default=5)
    tags = Column(String(500), default="")  # JSON array stored as string
    description = Column(String(500), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="user_sources")

    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_profile_source_name"),
        UniqueConstraint("profile_id", "url_or_handle", name="uq_profile_source_url"),
    )


class AdminSource(Base):
    """Admin-managed baseline sources."""
    __tablename__ = "admin_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    source_type = Column(String(20), nullable=False)
    url_or_handle = Column(String(500), nullable=False)
    priority = Column(Integer, default=5)
    tags = Column(String(500), default="")
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=True)  # Whether this is a pre-configured default
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# Add relationship to Profile
from app.models import Profile
Profile.user_sources = relationship(
    "UserSource",
    back_populates="profile",
    cascade="all, delete-orphan"
)
