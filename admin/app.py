from flask import Flask, render_template, request, session, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
DATABASE = '../bot/loyalty.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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
            return render_template('index.html', error="ID должен быть числом")

        conn = get_db()
        try:
            business = conn.execute(
                'SELECT id, name FROM businesses WHERE admin_id = ?',
                (int(admin_id),)
            ).fetchone()

            if not business:
                return render_template('index.html', error="Бизнес не найден")

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

            session['business_info'] = {
                'name': business['name'],
                'stats': dict(stats),
                'clients': [dict(client) for client in clients]
            }

            return redirect('/dashboard')
        finally:
            conn.close()

    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    if 'business_info' not in session:
        return redirect('/')

    return render_template('base.html')


@app.route('/lk')
def lk():
    return render_template('lk.html')


@app.route('/business_name')
def show_business_name():
    if 'business_info' not in session:
        return redirect('/')

   

if __name__ == '__main__':
    app.run(debug=True)