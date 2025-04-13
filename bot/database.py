# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, LoyaltyLevel, DefaultLevel, User, Business, UserBusiness, Purchase, Promotion
from datetime import datetime

# Настройки подключения к БД (SQLite)
DATABASE_URL = "sqlite:///loyalty.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_db():
    """Создает все таблицы в базе данных."""
    Base.metadata.create_all(engine)
    print("✅ Таблицы успешно созданы.")

def add_default_levels():
    """Добавляет стандартные уровни лояльности (бронза, серебро, золото)."""
    session = Session()
    
    # Проверяем, существуют ли уровни
    existing_levels = session.query(LoyaltyLevel).filter_by(business_id=None).count()
    if existing_levels >= 3:
        print("⚡ Стандартные уровни уже добавлены.")
        return

    default_levels = [
        {"name": DefaultLevel.BRONZE.value, "min_points": 0, "is_default": True},
        {"name": DefaultLevel.SILVER.value, "min_points": 500, "is_default": True},
        {"name": DefaultLevel.GOLD.value, "min_points": 1000, "is_default": True}
    ]

    for level in default_levels:
        new_level = LoyaltyLevel(**level)
        session.add(new_level)
    
    session.commit()
    print("✅ Стандартные уровни добавлены.")
    session.close()

def add_test_data():
    """Добавляет тестовые данные для проверки (опционально)."""
    session = Session()

    # Тестовый пользователь
    user = User(
        telegram_id=123456789,
        full_name="Test User",
        username="test_user"
    )
    session.add(user)

    # Тестовый бизнес
    business = Business(
        name="Test Shop",
        conversion_rate=10.0,
        point_value=1.0,
        admin_id=987654321
    )
    session.add(business)
    session.commit()

    # Привязка пользователя к бизнесу
    user_business = UserBusiness(
        user_id=user.id,
        business_id=business.id,
        points=0
    )
    session.add(user_business)
    session.commit()

    print("✅ Тестовые данные добавлены.")
    session.close()

if __name__ == "__main__":
    init_db()          # Создать таблицы
    add_default_levels()  # Добавить стандартные уровни
    add_test_data()     # Добавить тестовые данные (опционально)