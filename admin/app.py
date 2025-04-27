from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
DATABASE = '../bot/loyalty.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Existing business_profiles table
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
    # New cashback_levels table
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

# Initialize database on startup
init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.template_filter('format_date')
def format_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
    except:
        return value

@app.template_filter('format_currency')
def format_currency(value):
    return "{:,.2f}".format(value).replace(',', ' ')

@app.route('/', methods=['GET', 'POST'])
def business_auth():
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')

        if not admin_id.isdigit():
            return render_template('vhod.html', error="ID должен быть числом")

        conn = get_db()
        try:
            business = conn.execute(
                'SELECT id, name FROM businesses WHERE admin_id = ?',
                (int(admin_id),)
            ).fetchone()

            if not business:
                return render_template('vhod.html', error="Бизнес не найден")

            business_id = business['id']

            stats = conn.execute('''
                SELECT 
                    COUNT(DISTINCT ub.user_id) as clients_count,
                    COALESCE(SUM(ub.points), 0) as total_points,
                    COALESCE(SUM(p.amount), 0) as total_profit,
                    COALESCE(SUM(p.amount_paid), 0) as discount_profit,
                    COUNT(DISTINCT CASE WHEN purchase_count > 1 THEN rp.rp_user_id END) as active_users,
                    CASE 
                        WHEN COUNT(p.id) > 0 THEN ROUND(SUM(p.amount) / COUNT(p.id), 2)
                        ELSE 0 
                    END as average_check
                FROM user_business ub
                LEFT JOIN (
                    SELECT 
                        user_id as rp_user_id,
                        business_id as rp_business_id,
                        COUNT(id) as purchase_count
                    FROM purchases
                    WHERE created_at >= DATE('now', '-30 days')
                    GROUP BY user_id, business_id
                ) rp ON ub.user_id = rp.rp_user_id AND ub.business_id = rp.rp_business_id
                LEFT JOIN purchases p ON ub.business_id = p.business_id
                WHERE ub.business_id = ?
            ''', (business_id,)).fetchone()

            clients = conn.execute('''
                SELECT u.*, ub.points 
                FROM users u
                JOIN user_business ub ON u.id = ub.user_id
                WHERE ub.business_id = ?
            ''', (business_id,)).fetchall()

            profile = conn.execute(
                'SELECT * FROM business_profiles WHERE business_id = ?',
                (business_id,)
            ).fetchone()

            cashback_levels = conn.execute(
                'SELECT * FROM cashback_levels WHERE business_id = ?',
                (business_id,)
            ).fetchall()

            session['business_info'] = {
                'id': business_id,
                'name': business['name'],
                'stats': dict(stats),
                'clients': [dict(client) for client in clients],
                'profile': dict(profile) if profile else {},
                'cashback_levels': [dict(level) for level in cashback_levels]
            }

            # Initialize default cashback levels if none exist
            if not cashback_levels:
                default_levels = [
                    ('Bronze', 5.0, 0.0),
                    ('Silver', 10.0, 10000.0),
                    ('Gold', 15.0, 50000.0)
                ]
                for level_name, percentage, min_amount in default_levels:
                    conn.execute(
                        'INSERT INTO cashback_levels (business_id, level_name, cashback_percentage, min_purchase_amount) VALUES (?, ?, ?, ?)',
                        (business_id, level_name, percentage, min_amount)
                    )
                conn.commit()
                session['business_info']['cashback_levels'] = [
                    {'level_name': name, 'cashback_percentage': percentage, 'min_purchase_amount': min_amount}
                    for name, percentage, min_amount in default_levels
                ]

            return redirect('/dashboard')
        finally:
            conn.close()

    return render_template('vhod.html')

@app.route('/dashboard')
def dashboard():
    if 'business_info' not in session:
        return redirect('/')
    return render_template('base.html')

@app.route('/lk')
def lk():
    if 'business_info' not in session:
        return redirect('/')
    return render_template('lk.html')

@app.route('/business_profile', methods=['GET', 'POST'])
def business_profile():
    if 'business_info' not in session:
        return redirect('/')

    business_id = session['business_info']['id']
    
    if request.method == 'POST':
        conn = get_db()
        try:
            logo_path = session['business_info']['profile'].get('logo_path', '')
            
            if 'logo' in request.files:
                file = request.files['logo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{business_id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
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

@app.route('/cashback_settings', methods=['GET', 'POST'])
def cashback_settings():
    if 'business_info' not in session:
        return redirect('/')

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

if __name__ == '__main__':
    app.run(debug=True)