from flask import Flask, render_template, request, jsonify
from db import get_session
from models import User, UserBusiness

app = Flask(__name__)

# Главная страница
@app.route("/")
def profile():
    return render_template("profile.html")

# Получение профиля пользователя
@app.route("/api/profile/<int:telegram_id>")
def get_profile(telegram_id):
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        businesses = [
            {
                "name": ub.business.name,
                "points": ub.points,
                "level": ub.level.name if ub.level else "Без уровня"
            }
            for ub in user.businesses
        ]

        profile = {
            "full_name": user.full_name,
            "username": user.username,
            "telegram_id": user.telegram_id,
            "businesses": businesses
        }

        return jsonify(profile)
    finally:
        session.close()

# Обновление данных профиля
@app.route("/api/profile/<int:telegram_id>", methods=["POST"])
def update_profile(telegram_id):
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        data = request.json
        user.full_name = data.get("full_name", user.full_name)
        user.username = data.get("username", user.username)
        session.commit()

        return jsonify({"message": "Профиль обновлен"})
    finally:
        session.close()

# Получение магазинов (бизнесов) пользователя
@app.route("/api/stores/<int:telegram_id>")
def get_stores(telegram_id):
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify([])

        stores = [
            {
                "name": ub.business.name,
                "points": ub.points
            }
            for ub in user.businesses
        ]
        return jsonify(stores)
    finally:
        session.close()

if __name__ == "__main__":
    app.run(debug=True)
