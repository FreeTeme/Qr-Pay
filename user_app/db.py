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

# Если запустить этот файл напрямую, создадим таблицы:
if __name__ == '__main__':
    init_db()
