from flask import Flask, render_template
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, Business, UserBusiness, Base
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
import os

app = Flask(__name__)

# Путь к базе данных
DATABASE_URL = "sqlite:///../bot/loyalty.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Определяем модель для business_profiles
class BusinessProfile(Base):
    __tablename__ = 'business_profiles'
    business_id = Column(Integer, ForeignKey('businesses.id'), primary_key=True)
    logo_path = Column(String)

# Инициализация базы данных
def init_db():
    Base.metadata.create_all(bind=engine)

@app.route('/')
def index():
    session = SessionLocal()
    try:
        # Получаем данные пользователя с telegram_id=765843635
        user = session.query(User).filter_by(telegram_id=765843635).first()
        if not user:
            return "Пользователь не найден", 404

        # Получаем данные о баллах и бизнесах из user_business
        user_businesses = session.query(UserBusiness).filter_by(user_id=user.id).all()
        
        # Собираем информацию о бизнесах и их логотипах
        businesses_info = []
        total_points = 0
        for ub in user_businesses:
            business = session.query(Business).get(ub.business_id)
            profile = session.query(BusinessProfile).filter_by(business_id=ub.business_id).first()
            logo_path = profile.logo_path if profile else 'default_logo.png'
            businesses_info.append({
                'name': business.name,
                'logo_path': logo_path
            })
            total_points += ub.points

        # Передаем данные в шаблон
        return render_template('index.html', points=total_points, businesses=businesses_info)
    
    finally:
        session.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)