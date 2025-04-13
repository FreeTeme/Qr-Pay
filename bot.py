import sqlite3
import qrcode
from io import BytesIO
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Настройки бота
API_TOKEN = '7614037945:AAFrWrjShd62i_QDfqN-5YnfKNcthUXkb4w'
BOT_USERNAME = 'histobit_chat_bot'  # Без @

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        name TEXT,
        description TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        balance REAL DEFAULT 0
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        business_id INTEGER,
        amount REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

init_db()

# Проверка админа
def is_admin(user_id):
    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Количество бизнесов админа
def count_admin_businesses(admin_id):
    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM businesses WHERE admin_id = ?', (admin_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Сохранить пользователя
def save_user(user: types.User):
    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)''',
                   (user.id, user.username, user.first_name, user.last_name))
    conn.commit()
    conn.close()

# Получить баланс
def get_balance(user_id):
    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0.0

# Состояния FSM
class AddBusiness(StatesGroup):
    name = State()
    description = State()

class Payment(StatesGroup):
    waiting_for_amount = State()

# Клавиатура админа
def admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton('/add_business'))
    kb.add(KeyboardButton('/my_businesses'))
    return kb

# Генерация QR-кода
def generate_qr(business_id):
    deep_link = f"https://t.me/{BOT_USERNAME}?start=business_{business_id}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(deep_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    bio = BytesIO()
    bio.name = 'qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)

    return bio, deep_link

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args()
    save_user(message.from_user)

    if args and args.startswith('business_'):
        try:
            business_id = int(args.split('_')[1])
            await handle_qr_scan(message, business_id)
            return
        except:
            pass

    if is_admin(message.from_user.id):
        await message.answer("Привет, админ!", reply_markup=admin_keyboard())
    else:
        await message.answer("Добро пожаловать!")

# Обработка сканирования QR
async def handle_qr_scan(message: types.Message, business_id: int):
    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id, name, admin_id FROM businesses WHERE id = ?', (business_id,))
    business = cursor.fetchone()

    if not business:
        await message.answer("Бизнес не найден")
        return

    await message.answer(
        f"Вы отсканировали QR-код бизнеса {business[1]}.\n"
        "Пожалуйста, подождите пока администратор введет сумму вашей покупки."
    )

    admin_id = business[2]
    user_info = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name

    # Устанавливаем состояние для админа
    admin_state = dp.current_state(chat=admin_id, user=admin_id)
    await admin_state.set_state(Payment.waiting_for_amount)
    async with admin_state.proxy() as data:
        data['user_id'] = message.from_user.id
        data['business_id'] = business_id
        data['business_name'] = business[1]

    await bot.send_message(
        admin_id,
        f"🔔 Новое сканирование QR-кода!\n\n"
        f"Бизнес: {business[1]}\n"
        f"Пользователь: {user_info}\n\n"
        "Введите сумму покупки для начисления бонуса (10%):"
    )

# Обработка ввода суммы админом
@dp.message_handler(state=Payment.waiting_for_amount)
async def process_payment_amount(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам")
        await state.finish()
        return

    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Сумма должна быть положительной. Попробуйте еще раз.")
            return

        async with state.proxy() as data:
            user_id = data['user_id']
            business_id = data['business_id']
            business_name = data['business_name']

        # Проверка принадлежности бизнеса
        conn = sqlite3.connect('business_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM businesses WHERE id = ? AND admin_id = ?',
                      (business_id, message.from_user.id))
        if not cursor.fetchone():
            await message.answer("Ошибка: этот бизнес не принадлежит вам")
            await state.finish()
            return

        # Начисление бонуса
        bonus = amount * 0.1
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                      (bonus, user_id))
        cursor.execute('''INSERT INTO scans 
            (user_id, business_id, amount) 
            VALUES (?, ?, ?)''',
            (user_id, business_id, amount))
        conn.commit()
        conn.close()

        # Уведомление пользователя
        try:
            await bot.send_message(
                user_id,
                f"🎉 Вам начислен бонус {bonus:.2f} !\n\n"
                f"🏢 Бизнес: {business_name}\n"
                f"💵 Сумма покупки: {amount:.2f} Byn\n"
                f"💰 Ваш бонус: {get_balance(user_id):.2f} руб"
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")

        await message.answer(
            f"✅ Пользователю начислено {bonus:.2f} бонусов",
            reply_markup=admin_keyboard()
        )
        await state.finish()

    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму (число):")

# Добавление бизнеса
@dp.message_handler(commands=['add_business'])
async def add_business_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    if count_admin_businesses(message.from_user.id) >= 5:
        await message.answer("Вы достигли лимита бизнесов (5)")
        return

    await AddBusiness.name.set()
    await message.answer("Введите название бизнеса:", reply_markup=ReplyKeyboardRemove())

@dp.message_handler(state=AddBusiness.name)
async def process_business_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text

    await AddBusiness.next()
    await message.answer("Теперь введите описание бизнеса:")

@dp.message_handler(state=AddBusiness.description)
async def process_business_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = message.text

        conn = sqlite3.connect('business_bot.db')
        cursor = conn.cursor()

        cursor.execute('''INSERT INTO businesses 
            (admin_id, name, description) 
            VALUES (?, ?, ?)''',
                       (message.from_user.id, data['name'], data['description']))

        business_id = cursor.lastrowid
        conn.commit()
        conn.close()

        qr_img, qr_link = generate_qr(business_id)

        await message.answer(
            "Бизнес успешно создан!\n"
            f"Ссылка: {qr_link}",
            reply_markup=admin_keyboard()
        )

        await bot.send_photo(
            message.from_user.id,
            photo=qr_img,
            caption=f"QR-код для бизнеса: {data['name']}"
        )

    await state.finish()

# Просмотр бизнесов
@dp.message_handler(commands=['my_businesses'])
async def list_businesses(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    conn = sqlite3.connect('business_bot.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id, name, description FROM businesses WHERE admin_id = ?',
                   (message.from_user.id,))

    businesses = cursor.fetchall()
    conn.close()

    if not businesses:
        await message.answer("У вас пока нет бизнесов")
        return

    response = "Ваши бизнесы:\n\n"
    for biz in businesses:
        response += f"🆔 ID: {biz[0]}\n🏢 Название: {biz[1]}\n📝 Описание: {biz[2]}\n\n"

    await message.answer(response)

if __name__ == '__main__':
    # Добавление админа
    def add_admin(user_id):
        conn = sqlite3.connect('business_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()

    # Укажите ваш Telegram ID
    add_admin(6850731097)

    executor.start_polling(dp, skip_updates=True)