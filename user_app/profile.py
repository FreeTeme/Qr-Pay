from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from models import User  # твоя модель User
from db import get_session, init_db  # твоя сессия и инициализация базы
from datetime import datetime
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # для работы сессий

# Создаем scoped_session для безопасной работы с сессиями в Flask
db_session = scoped_session(get_session)

# Добавляем обработчик для закрытия сессии после каждого запроса
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# ==================== Маршруты ====================

@app.route('/')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        telegram_id = request.form.get('telegram_id')
        if telegram_id:
            try:
                user = db_session.query(User).filter_by(telegram_id=int(telegram_id)).first()
                if not user:
                    return "Пользователь не найден", 404
                session['user_id'] = user.telegram_id
                return redirect(url_for('profile'))
            except ValueError:
                return "Некорректный Telegram ID", 400
            except Exception as e:
                db_session.rollback()
                return f"Ошибка сервера: {str(e)}", 500
        return "Нет telegram_id", 400
    return '''
    <form method="post">
        Telegram ID: <input type="text" name="telegram_id">
        <button type="submit">Войти</button>
    </form>
    '''

@app.route('/api/profile', methods=['GET'])
def get_profile():
    telegram_id = session.get('user_id')
    if not telegram_id:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        user = db_session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        return jsonify({
            'fullName': user.full_name,
            'phone': user.username,
            'birthDate': user.registration_date.strftime('%Y-%m-%d') if user.registration_date else None,
            'businesses': user.business_info  # Добавляем информацию о бизнесах пользователя
        })
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    telegram_id = session.get('user_id')
    if not telegram_id:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400

        user = db_session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        if 'fullName' in data:
            user.full_name = data['fullName']
        if 'phone' in data:
            user.username = data['phone']
        if 'birthDate' in data:
            try:
                user.registration_date = datetime.strptime(data['birthDate'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Неверный формат даты. Используйте YYYY-MM-DD'}), 400

        db_session.commit()
        return jsonify({'message': 'Профиль успешно обновлен'}), 200
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/profile/delete', methods=['DELETE'])
def delete_profile():
    telegram_id = session.get('user_id')
    if not telegram_id:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        user = db_session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        db_session.delete(user)
        db_session.commit()
        session.pop('user_id', None)
        return jsonify({'message': 'Профиль успешно удален'}), 200
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

# ==================== Конец ====================

if __name__ == '__main__':
    init_db()  # если нужно явно инициализировать, можно убрать
    app.run(host='0.0.0.0', port=8000, debug=True)  # debug=True для отладки