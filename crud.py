from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database.models import User, Business, Search, Verification

def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_user(db: Session, telegram_id: int, username: str, first_name: str, last_name: str) -> User:
    import random, string
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    user = User(
        telegram_id=telegram_id,
        username=username or "",
        first_name=first_name or "",
        last_name=last_name or "",
        referral_code=referral_code
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_or_create_business(db: Session, **kwargs) -> Business:
    business = db.query(Business).filter(
        Business.google_place_id == kwargs.get('google_place_id')
    ).first()
    
    if not business:
        business = Business(**kwargs)
        db.add(business)
        db.commit()
        db.refresh(business)
    
    return business

def create_search(db: Session, user_id: int, query_text: str, category: str, location: str) -> Search:
    search = Search(
        user_id=user_id,
        query_text=query_text,
        category=category,
        location=location
    )
    db.add(search)
    
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.search_count += 1
    
    db.commit()
    db.refresh(search)
    return search

def create_verification(db: Session, **kwargs) -> Verification:
    verification = Verification(**kwargs)
    db.add(verification)
    db.commit()
    db.refresh(verification)
    return verification