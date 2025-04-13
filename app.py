from flask import Flask, request, jsonify, g, render_template, redirect, url_for
import sqlite3
import datetime
from functools import wraps

app = Flask(__name__, static_folder='static', template_folder='templates')
DATABASE = 'business_bot.db'
DEFAULT_USER_ID = 765843635 # Фиксированный ID пользователя


# Утилиты для работы с БД
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    try:
        cur = get_db().execute(query, args)
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return None


def table_exists(table_name):
    cursor = get_db().cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None


def commit_db():
    get_db().commit()


# Страница бизнеса
@app.route('/business/<int:business_id>')
def business_page(business_id):
    # Получаем данные бизнеса
    business = query_db('SELECT * FROM businesses WHERE id = ?', [business_id], one=True)
    if business is None:
        return "Business not found", 404

    # Получаем данные пользователя
    user = query_db('SELECT * FROM users WHERE user_id = ?', [DEFAULT_USER_ID], one=True)
    if user is None:
        return "User not found", 404

    # Получаем историю операций
    history = []
    if table_exists('scans'):
        history = query_db('''
            SELECT s.*, b.name as business_name 
            FROM scans s
            LEFT JOIN businesses b ON s.business_id = b.id
            WHERE user_id = ? AND business_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', [DEFAULT_USER_ID, business_id]) or []

    # Получаем акции (если таблица существует)
    promos = []
    if table_exists('promos'):
        promos = query_db('''
            SELECT * FROM promos 
            WHERE business_id = ? 
            AND (end_date >= date('now') OR end_date IS NULL)
        ''', [business_id]) or []

    # Получаем статистику
    stats = {
        'total_visits': query_db('SELECT COUNT(*) as count FROM scans WHERE user_id = ? AND business_id = ?',
                                 [DEFAULT_USER_ID, business_id], one=True)['count'] if table_exists('scans') else 0,
        'monthly_visits': query_db('''SELECT COUNT(*) as count 
                                    FROM scans 
                                    WHERE user_id = ? AND business_id = ? 
                                    AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')''',
                                   [DEFAULT_USER_ID, business_id], one=True)['count'] if table_exists('scans') else 0,
        'popular_time': query_db('''SELECT strftime('%H:00', timestamp) as hour, COUNT(*) as count
                                  FROM scans
                                  WHERE user_id = ? AND business_id = ?
                                  GROUP BY hour
                                  ORDER BY count DESC
                                  LIMIT 1''',
                                 [DEFAULT_USER_ID, business_id], one=True) if table_exists('scans') else None
    }

    # Получаем другие бизнесы
    other_businesses = query_db('SELECT * FROM businesses WHERE id != ? LIMIT 5', [business_id]) or []

    return render_template('index1.html',
                           business=dict(business),
                           user=dict(user),
                           history=[dict(item) for item in history],
                           promos=[dict(item) for item in promos],
                           stats=stats,
                           other_businesses=[dict(item) for item in other_businesses])


if __name__ == '__main__':
    app.run(debug=True)