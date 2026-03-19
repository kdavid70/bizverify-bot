from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
SessionLocal = None  # Will be set by init_db()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    referral_code = Column(String(10), unique=True)
    search_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    phone_primary = Column(String(20), nullable=False, index=True)
    category = Column(String(100))
    address_text = Column(Text)
    google_place_id = Column(String(255), unique=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

class Search(Base):
    __tablename__ = "searches"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_text = Column(String(500))
    category = Column(String(100))
    location = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Verification(Base):
    __tablename__ = "verifications"
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    status = Column(String(20), nullable=False)
    call_duration_seconds = Column(Integer)
    verified_at = Column(DateTime, default=datetime.utcnow)

def init_db(database_url: str):
    global SessionLocal
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal