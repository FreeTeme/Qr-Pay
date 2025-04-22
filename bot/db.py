# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from base import Base  # единый Base для моделей

# Импортируем модели, чтобы они были зарегистрированы в Base
from models import User, Business, LoyaltyLevel, UserBusiness, Promotion, Purchase

DATABASE_URL = "sqlite:///loyalty.db"  # Используем SQLite

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_session():
    return SessionLocal()

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы")

def get_user(tg_id: int):
    session = get_session()
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    session.close()
    return user

def create_user(user_data: dict):
    session = get_session()
    user = User(
        telegram_id=user_data['id'],
        full_name=user_data.get('full_name'),
        username=user_data.get('username'),
        gender=user_data.get('gender'),
        email=user_data.get('email'),
        birth_date=user_data.get('birth_date')
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user

def get_business(business_id: int):
    session = get_session()
    business = session.query(Business).get(business_id)
    session.close()
    return business


# Если запустить этот файл напрямую, создадим таблицы:
if __name__ == '__main__':
    init_db()
