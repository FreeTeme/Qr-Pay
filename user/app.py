from flask import Flask, render_template, jsonify, request, session
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, extract
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import sys
import os
from datetime import datetime

# Настраиваем путь к директории бота
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
from models import User, Business, UserBusiness, Purchase, Base

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# Путь к базе данных
DATABASE_URL = "sqlite:///../bot/loyalty.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Модель BusinessProfile
class BusinessProfile(Base):
    __tablename__ = 'business_profiles'
    business_id = Column(Integer, ForeignKey('businesses.id'), primary_key=True)
    logo_path = Column(String)
    address = Column(String)

# Модель CashbackLevel
class CashbackLevel(Base):
    __tablename__ = 'cashback_levels'
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey('businesses.id'))
    level_name = Column(String, nullable=False)
    cashback_percentage = Column(Float, nullable=False)
    min_purchase_amount = Column(Float, nullable=False)

# Инициализация базы данных
def init_db():
    Base.metadata.create_all(bind=engine)

@app.route('/')
def index():
    telegram_id = request.args.get('user_id', type=int)
    business_id= request.args.get('business_id',type=int)
    if not telegram_id:
        telegram_id=session['user_id']
        business_id=session['business_id']

        # return "user_id не указан", 400
    else:
        session['user_id'] = telegram_id  # ✅ Сохраняем user_id в сессию
        session['business_id']=business_id

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return "Пользователь не найден", 404

        # Получаем бизнес Vobraz
        vobraz = db.query(Business).filter_by(admin_id=business_id).first()
        if not vobraz:
            return "Бизнес Vobraz не найден", 404

        # Получаем баллы пользователя для бизнеса Vobraz
        user_business = db.query(UserBusiness).filter_by(user_id=user.id, business_id=vobraz.id).first()
        points = user_business.points if user_business else 0

        # Получаем профиль Vobraz (для адреса и логотипа)
        vobraz_profile = db.query(BusinessProfile).filter_by(business_id=vobraz.id).first()
        address = vobraz_profile.address if vobraz_profile and vobraz_profile.address else "Адрес не указан"

        # Получаем уровни кэшбэка для Vobraz
        levels = db.query(CashbackLevel).filter_by(business_id=vobraz.id).order_by(CashbackLevel.min_purchase_amount).all()
        if not levels:
            levels = [
                CashbackLevel(level_name="Bronze", cashback_percentage=5.0, min_purchase_amount=0.0),
                CashbackLevel(level_name="Silver", cashback_percentage=10.0, min_purchase_amount=10000.0),
                CashbackLevel(level_name="Gold", cashback_percentage=15.0, min_purchase_amount=50000.0)
            ]

        # Находим текущий уровень и следующий уровень
        current_level = None
        next_level = None
        total_purchases = points * vobraz.conversion_rate
        for i, level in enumerate(levels):
            if total_purchases >= level.min_purchase_amount:
                current_level = level
            else:
                if i > 0:
                    next_level = level
                break
        if not next_level and current_level != levels[-1]:
            next_level = levels[levels.index(current_level) + 1]

        # Вычисляем прогресс
        progress = {}
        if next_level:
            points_needed = (next_level.min_purchase_amount - current_level.min_purchase_amount) / vobraz.conversion_rate
            points_earned = (total_purchases - current_level.min_purchase_amount) / vobraz.conversion_rate
            progress_percent = (points_earned / points_needed) * 100 if points_needed > 0 else 100
            progress = {
                'current_points': points,
                'points_to_next': next_level.min_purchase_amount / vobraz.conversion_rate,
                'progress_percent': round(progress_percent, 1),
                'current_level_name': current_level.level_name,
                'current_cashback': current_level.cashback_percentage,
                'next_level_name': next_level.level_name if next_level else None,
                'next_cashback': next_level.cashback_percentage if next_level else None
            }
        else:
            progress = {
                'current_points': points,
                'points_to_next': current_level.min_purchase_amount / vobraz.conversion_rate,
                'progress_percent': 100,
                'current_level_name': current_level.level_name,
                'current_cashback': current_level.cashback_percentage,
                'next_level_name': None,
                'next_cashback': None
            }

        # Получаем данные о всех бизнесах пользователя для модального окна
        user_businesses = db.query(UserBusiness).filter_by(user_id=user.id).all()
        businesses_info = []
        for ub in user_businesses:
            business = db.query(Business).get(ub.business_id)
            profile = db.query(BusinessProfile).filter_by(business_id=ub.business_id).first()
            logo_path = profile.logo_path if profile else 'default_logo.png'
            businesses_info.append({
                'name': business.name,
                'logo_path': logo_path
            })

        # Получаем последние 7 покупок
        recent_purchases = db.query(Purchase).filter_by(
            user_id=user.id, business_id=vobraz.id
        ).order_by(Purchase.created_at.desc()).limit(7).all()

        # Получаем все покупки
        all_purchases = db.query(Purchase).filter_by(
            user_id=user.id, business_id=vobraz.id
        ).order_by(Purchase.created_at.desc()).all()

        # Аналитика
        # Общее количество посещений
        total_visits = db.query(Purchase).filter_by(
            user_id=user.id, business_id=vobraz.id
        ).count()

        # Посещения в текущем месяце (апрель 2025)
        current_month_visits = db.query(Purchase).filter(
            Purchase.user_id == user.id,
            Purchase.business_id == vobraz.id,
            extract('year', Purchase.created_at) == 2025,
            extract('month', Purchase.created_at) == 4
        ).count()

        # Самое частое время посещений (час)
        most_frequent_hour_result = db.query(
            func.strftime('%H', Purchase.created_at).label('hour'),
            func.count().label('count')
        ).filter(
            Purchase.user_id == user.id,
            Purchase.business_id == vobraz.id
        ).group_by(
            func.strftime('%H', Purchase.created_at)
        ).order_by(
            func.count().desc()
        ).first()

        most_frequent_hour = most_frequent_hour_result.hour + ':00' if most_frequent_hour_result else 'Нет данных'

        # Посещения по часам
        hourly_visits_result = db.query(
            func.strftime('%H', Purchase.created_at).label('hour'),
            func.count().label('count')
        ).filter(
            Purchase.user_id == user.id,
            Purchase.business_id == vobraz.id
        ).group_by(
            func.strftime('%H', Purchase.created_at)
        ).all()

        hourly_visits = {f"{h:02d}": 0 for h in range(24)}  # Инициализация всех часов
        for hour, count in hourly_visits_result:
            hourly_visits[hour] = count

        # Посещения по дням недели (0=понедельник, 6=воскресенье)
        weekday_visits_result = db.query(
            func.strftime('%w', Purchase.created_at).label('weekday'),
            func.count().label('count')
        ).filter(
            Purchase.user_id == user.id,
            Purchase.business_id == vobraz.id
        ).group_by(
            func.strftime('%w', Purchase.created_at)
        ).all()

        weekday_visits = {str(i): 0 for i in range(7)}  # Инициализация всех дней
        for weekday, count in weekday_visits_result:
            # SQLite: 0=воскресенье, 1=понедельник, ..., 6=суббота
            # Преобразуем в 0=понедельник, ..., 6=воскресенье
            adjusted_weekday = (int(weekday) + 6) % 7
            weekday_visits[str(adjusted_weekday)] = count

        # Передаем данные в шаблон
        return render_template(
            'index.html',
            points=points,
            businesses=businesses_info,
            progress=progress,
            address=address,
            recent_purchases=recent_purchases,
            all_purchases=all_purchases,
            total_visits=total_visits,
            current_month_visits=current_month_visits,
            most_frequent_hour=most_frequent_hour,
            hourly_visits=hourly_visits,
            weekday_visits=weekday_visits
        )
    
    finally:
        db.close()

@app.route('/profile')
def profile_page():
    if 'user_id' not in session:
        return "Нет доступа. Пользователь не авторизован.", 401
    return render_template('profile.html')  # Файл profile.html должен быть в templates/


# ================== API: Получение, обновление и удаление профиля ==================

@app.route('/api/profile')
def get_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401

    session_db = SessionLocal()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(user_id)).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        return jsonify({
            'fullName': user.full_name,
            'phone': user.username,
            'birthDate': user.registration_date.strftime('%Y-%m-%d') if user.registration_date else None
        })
    finally:
        session_db.close()


@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401

    data = request.json
    session_db = SessionLocal()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(user_id)).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        user.full_name = data.get('fullName', user.full_name)
        user.username = data.get('phone', user.username)
        if data.get('birthDate'):
            user.registration_date = datetime.strptime(data['birthDate'], '%Y-%m-%d')

        session_db.commit()
        return '', 204
    finally:
        session_db.close()


@app.route('/api/profile/delete', methods=['DELETE'])
def delete_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401

    session_db = SessionLocal()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(user_id)).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        session_db.delete(user)
        session_db.commit()
        session.pop('user_id', None)
        return '', 204
    finally:
        session_db.close()

@app.route('/api/progress')
def get_progress():
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(telegram_id=765843635).first()
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        vobraz = session.query(Business).filter_by(name='Vobraz').first()
        if not vobraz:
            return jsonify({"error": "Бизнес Vobraz не найден"}), 404

        user_business = session.query(UserBusiness).filter_by(user_id=user.id, business_id=vobraz.id).first()
        points = user_business.points if user_business else 0

        levels = session.query(CashbackLevel).filter_by(business_id=vobraz.id).order_by(CashbackLevel.min_purchase_amount).all()
        if not levels:
            levels = [
                CashbackLevel(level_name="Bronze", cashback_percentage=5.0, min_purchase_amount=0.0),
                CashbackLevel(level_name="Silver", cashback_percentage=10.0, min_purchase_amount=10000.0),
                CashbackLevel(level_name="Gold", cashback_percentage=15.0, min_purchase_amount=50000.0)
            ]

        current_level = None
        next_level = None
        total_purchases = points * vobraz.conversion_rate
        for i, level in enumerate(levels):
            if total_purchases >= level.min_purchase_amount:
                current_level = level
            else:
                if i > 0:
                    next_level = level
                break
        if not next_level and current_level != levels[-1]:
            next_level = levels[levels.index(current_level) + 1]

        progress = {}
        if next_level:
            points_needed = (next_level.min_purchase_amount - current_level.min_purchase_amount) / vobraz.conversion_rate
            points_earned = (total_purchases - current_level.min_purchase_amount) / vobraz.conversion_rate
            progress_percent = (points_earned / points_needed) * 100 if points_needed > 0 else 100
            progress = {
                'current_points': points,
                'points_to_next': next_level.min_purchase_amount / vobraz.conversion_rate,
                'progress_percent': round(progress_percent, 1),
                'current_level_name': current_level.level_name,
                'current_cashback': current_level.cashback_percentage,
                'next_level_name': next_level.level_name if next_level else None,
                'next_cashback': next_level.cashback_percentage if next_level else None
            }
        else:
            progress = {
                'current_points': points,
                'points_to_next': current_level.min_purchase_amount / vobraz.conversion_rate,
                'progress_percent': 100,
                'current_level_name': current_level.level_name,
                'current_cashback': current_level.cashback_percentage,
                'next_level_name': None,
                'next_cashback': None
            }

        return jsonify(progress)
    finally:
        session.close()

# Фильтр для форматирования чисел
@app.template_filter('format_number')
def format_number(value):
    return "{:,}".format(int(value)).replace(',', ' ')

# Фильтр для форматирования даты
@app.template_filter('format_date')
def format_date(value):
    if value:
        return value.strftime('%d.%m.%Y %H:%M')
    return ''


@app.route('/qr')
def qr():
    return render_template('qr1.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)