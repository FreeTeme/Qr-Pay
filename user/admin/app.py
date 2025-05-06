from flask import Blueprint, render_template, request, session, redirect, jsonify
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename
  # Точка в начале означает текущую папку

# Создаём Blueprint

bisness = Blueprint('bis', __name__,
                  url_prefix='/bis',
                  template_folder='templates')

# Конфигурация
DATABASE = '../bot/loyalty.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Устанавливаем конфиг для Blueprint (если нужно)
bisness.config = {
    'UPLOAD_FOLDER': UPLOAD_FOLDER,
    'SECRET_KEY': 'your_secret_key_here'  # Лучше вынести в основной app.py
}

# Проверяем папку для загрузок
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS business_profiles (
            business_id INTEGER PRIMARY KEY,
            logo_path TEXT,
            category TEXT,
            description TEXT,
            address TEXT,
            phone TEXT,
            website TEXT,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cashback_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            level_name TEXT NOT NULL,
            cashback_percentage REAL NOT NULL,
            min_purchase_amount REAL NOT NULL,
            UNIQUE(business_id, level_name),
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
    ''')
    conn.commit()
    conn.close()

# Инициализация БД (можно вызвать в app.py)
init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Фильтры для шаблонов
@bisness.app_template_filter('format_date')
def format_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
    except:
        return value

@bisness.app_template_filter('format_currency')
def format_currency(value):
    return "{:,.2f}".format(value).replace(',', ' ')

# Роуты
@bisness.route('/', methods=['GET', 'POST'])
def business_auth():
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')
        if not admin_id.isdigit():
            return render_template('vhod.html', error="ID должен быть числом")
        
        conn = get_db()
        business = conn.execute(
            'SELECT id, name FROM businesses WHERE admin_id = ?',
            (int(admin_id),)
        ).fetchone()
        
        if not business:
            return render_template('vhod.html', error="Бизнес не найден")
        
        session['business_info'] = {
            'id': business['id'],
            'name': business['name']
        }
        return redirect('/bis/dashboard')
    
    return render_template('vhod.html')

@bisness.route('/dashboard')
def dashboard():
    if 'business_info' not in session:
        return redirect('/bis/')
    return render_template('base.html')

# ... остальные роуты (lk, business_profile, cashback_settings) ...

# Не нужно if __name__ == '__main__' для Blueprint!

@bisness.route('/lk')
def lk():
    if 'business_info' not in session:
        return redirect('/bis/')
    return render_template('lk.html')

@bisness.route('/business_profile', methods=['GET', 'POST'])
def business_profile():
    if 'business_info' not in session:
        return redirect('/bis/')

    business_id = session['business_info']['id']
    
    if request.method == 'POST':
        conn = get_db()
        try:
            logo_path = session['business_info']['profile'].get('logo_path', '')
            
            if 'logo' in request.files:
                file = request.files['logo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{business_id}_{file.filename}")
                    file.save(os.path.join(bisness.config['UPLOAD_FOLDER'], filename))
                    logo_path = f"/{UPLOAD_FOLDER}/{filename}"

            category = request.form.get('category')
            description = request.form.get('description')
            address = request.form.get('address')
            phone = request.form.get('phone')
            website = request.form.get('website')

            conn.execute('''
                INSERT OR REPLACE INTO business_profiles 
                (business_id, logo_path, category, description, address, phone, website)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (business_id, logo_path, category, description, address, phone, website))

            conn.commit()

            profile = conn.execute(
                'SELECT * FROM business_profiles WHERE business_id = ?',
                (business_id,)
            ).fetchone()
            
            session['business_info']['profile'] = dict(profile)

            return jsonify({'status': 'success', 'message': 'Профиль обновлен'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
        finally:
            conn.close()

    return jsonify(session['business_info']['profile'])

@bisness.route('/cashback_settings', methods=['GET', 'POST'])
def cashback_settings():
    if 'business_info' not in session:
        return redirect('/bis/')

    business_id = session['business_info']['id']
    
    if request.method == 'POST':
        conn = get_db()
        try:
            levels = [
                ('Bronze', request.form.get('bronze_percentage'), request.form.get('bronze_min_amount')),
                ('Silver', request.form.get('silver_percentage'), request.form.get('silver_min_amount')),
                ('Gold', request.form.get('gold_percentage'), request.form.get('gold_min_amount'))
            ]

            for level_name, percentage, min_amount in levels:
                try:
                    percentage = float(percentage)
                    min_amount = float(min_amount)
                    if percentage < 0 or percentage > 100 or min_amount < 0:
                        raise ValueError("Invalid values")
                except (ValueError, TypeError):
                    return jsonify({'status': 'error', 'message': f'Некорректные значения для уровня {level_name}'})

                conn.execute('''
                    INSERT OR REPLACE INTO cashback_levels 
                    (business_id, level_name, cashback_percentage, min_purchase_amount)
                    VALUES (?, ?, ?, ?)
                ''', (business_id, level_name, percentage, min_amount))

            conn.commit()

            cashback_levels = conn.execute(
                'SELECT * FROM cashback_levels WHERE business_id = ?',
                (business_id,)
            ).fetchall()
            
            session['business_info']['cashback_levels'] = [dict(level) for level in cashback_levels]

            return jsonify({'status': 'success', 'message': 'Настройки кэшбэка обновлены'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
        finally:
            conn.close()

    return jsonify(session['business_info']['cashback_levels'])

