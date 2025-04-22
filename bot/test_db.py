from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Business, User, UserBusiness, Purchase, LoyaltyLevel, DefaultLevel

# Создание движка и сессии
engine = create_engine('sqlite:///loyalty.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


def populate_data():
    # Создание бизнесов
    businesses = [
        Business(
            name="Coffee Shop",
            conversion_rate=10.0,
            point_value=0.1,
            admin_id=1
        ),
        Business(
            name="Book Store",
            conversion_rate=5.0,
            point_value=0.5,
            admin_id=1
        ),
        Business(
            name="Gym",
            conversion_rate=15.0,
            point_value=0.2,
            admin_id=1
        )
    ]
    session.add_all(businesses)
    session.flush()  # Получаем ID бизнесов

    # Создание уровней лояльности
    # Для Coffee Shop (кастомные уровни)
    coffee_levels = [
        LoyaltyLevel(
            business_id=businesses[0].id,
            name="Regular",
            min_points=0
        ),
        LoyaltyLevel(
            business_id=businesses[0].id,
            name="VIP",
            min_points=500
        ),
        LoyaltyLevel(
            business_id=businesses[0].id,
            name="Premium",
            min_points=1000
        )
    ]

    # Стандартные уровни (для остальных бизнесов)
    default_levels = [
        LoyaltyLevel(
            name=DefaultLevel.BRONZE.value,
            min_points=0,
            is_default=True
        ),
        LoyaltyLevel(
            name=DefaultLevel.SILVER.value,
            min_points=500,
            is_default=True
        ),
        LoyaltyLevel(
            name=DefaultLevel.GOLD.value,
            min_points=1000,
            is_default=True
        )
    ]

    session.add_all(coffee_levels + default_levels)
    session.flush()

    # Создание пользователей
    users = [
        User(
            telegram_id=12345,
            full_name="Иван Иванов",
            username="ivan_ivanov"
        ),
        User(
            telegram_id=23456,
            full_name="Петр Петров",
            username="petr_petrov"
        ),
        User(
            telegram_id=34567,
            full_name="Анна Сидорова",
            username="anna_sidorova"
        ),
        User(
            telegram_id=45678,
            full_name="Мария Кузнецова",
            username="maria_kuz"
        ),
        User(
            telegram_id=56789,
            full_name="Сергей Смирнов",
            username="sergey_smirnov"
        )
    ]
    session.add_all(users)
    session.flush()

    # Создание связей пользователь-бизнес
    user_businesses = [
        UserBusiness(user_id=users[0].id, business_id=businesses[0].id),
        UserBusiness(user_id=users[0].id, business_id=businesses[1].id),
        UserBusiness(user_id=users[1].id, business_id=businesses[2].id),
        UserBusiness(user_id=users[2].id, business_id=businesses[0].id),
        UserBusiness(user_id=users[3].id, business_id=businesses[1].id),
        UserBusiness(user_id=users[3].id, business_id=businesses[2].id)
    ]
    session.add_all(user_businesses)
    session.flush()

    # Создание покупок
    purchases = [
        # Покупки Ивана (Coffee Shop)
        Purchase(
            user_id=users[0].id,
            business_id=businesses[0].id,
            amount=50.0,
            points_used=0
        ),
        Purchase(
            user_id=users[0].id,
            business_id=businesses[0].id,
            amount=25.0,
            points_used=0
        ),
        # Покупка Ивана (Book Store)
        Purchase(
            user_id=users[0].id,
            business_id=businesses[1].id,
            amount=60.0,
            points_used=0
        ),
        # Покупка Петра (Gym)
        Purchase(
            user_id=users[1].id,
            business_id=businesses[2].id,
            amount=100.0,
            points_used=300
        ),
        # Покупка Анны (Coffee Shop)
        Purchase(
            user_id=users[2].id,
            business_id=businesses[0].id,
            amount=20.0,
            points_used=0
        ),
        # Покупки Марии (Book Store)
        Purchase(
            user_id=users[3].id,
            business_id=businesses[1].id,
            amount=80.0,
            points_used=0
        ),
        Purchase(
            user_id=users[3].id,
            business_id=businesses[1].id,
            amount=40.0,
            points_used=0
        ),
        # Покупка Марии (Gym)
        Purchase(
            user_id=users[3].id,
            business_id=businesses[2].id,
            amount=10.0,
            points_used=0
        )
    ]

    # Расчет итоговой суммы оплаты
    for purchase in purchases:
        purchase.calculate_payment()

    session.add_all(purchases)
    session.flush()

    # Обновление баллов и уровней
    for ub in user_businesses:
        # Расчет накопленных баллов
        related_purchases = [
            p for p in purchases
            if p.user_id == ub.user_id
               and p.business_id == ub.business_id
        ]

        total_earned = sum(
            p.amount * next(
                b.conversion_rate for b in businesses
                if b.id == ub.business_id
            )
            for p in related_purchases
        )

        total_used = sum(p.points_used for p in related_purchases)
        ub.points = total_earned - total_used

        # Обновление уровня
        ub.update_level()

    session.commit()
    print("Тестовые данные успешно добавлены!")


if __name__ == "__main__":
    populate_data()