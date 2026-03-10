from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String(50),  unique=True, index=True, nullable=False)
    email      = Column(String(120), unique=True, index=True, nullable=False)
    hashed_pw  = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active  = Column(Boolean, default=True)
    checks     = relationship("NewsCheck", back_populates="user", cascade="all, delete")
    bookmarks  = relationship("Bookmark",  back_populates="user", cascade="all, delete")


class NewsCheck(Base):
    __tablename__ = "news_checks"
    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    news_text      = Column(Text,    nullable=False)

    # ML results
    ml_verdict     = Column(String(20))
    ml_confidence  = Column(Float)
    ml_fake_prob   = Column(Float)
    ml_real_prob   = Column(Float)
    ml_model_name  = Column(String(100))

    # Claude AI results
    ai_verdict     = Column(String(20))
    ai_confidence  = Column(Integer)
    ai_summary     = Column(Text)

    # Combined
    final_verdict  = Column(String(20))
    final_score    = Column(Float)

    checked_at     = Column(DateTime, default=datetime.utcnow)
    user           = relationship("User",     back_populates="checks")
    bookmarks      = relationship("Bookmark", back_populates="check", cascade="all, delete")


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id        = Column(Integer, primary_key=True, index=True)
    user_id   = Column(Integer, ForeignKey("users.id"),       nullable=False)
    check_id  = Column(Integer, ForeignKey("news_checks.id"), nullable=False)
    note      = Column(Text, default="")
    saved_at  = Column(DateTime, default=datetime.utcnow)
    user      = relationship("User",      back_populates="bookmarks")
    check     = relationship("NewsCheck", back_populates="bookmarks")
