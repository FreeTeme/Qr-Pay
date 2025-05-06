import logging
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile, FSInputFile
from config import BOT_TOKEN, ADMINS, BOT_USERNAME
from db import get_business, get_session, get_user
from models import User, Business, UserBusiness, Purchase
from qr_utils import generate_qr
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class BusinessCreation(StatesGroup):
    AWAITING_NAME = State()
    AWAITING_CONVERSION_RATE = State()

class PaymentStates(StatesGroup):
    AWAITING_AMOUNT = State()
    AWAITING_POINTS = State()

class PurchaseStates(StatesGroup):
    AWAITING_AMOUNT = State()
    AWAITING_POINTS = State()

class MenuStates(StatesGroup):
    MAIN_MENU = State()
    HOW_IT_WORKS = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def get_payment_keyboard(user_id: int, business_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💳 Оформить покупку",
        callback_data=f"process_payment:{user_id}:{business_id}"
    )
    return builder.as_markup()

def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подключить свой бизнес",
        url='https://app.qrpay.tw1.su/bis/',
    )
    builder.button(
        text="О нас",
        url='https://andhanc.github.io/SaveX/',
    )
    builder.button(
        text="Как работает",
        callback_data="show_how_it_works"
    )
    builder.adjust(1, 2)
    return builder.as_markup()

def get_back_to_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Назад",
        callback_data="back_to_main_menu"
    )
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: Command, state: FSMContext):
    args = command.args
    session = get_session()
    
    try:
        if args and args.startswith("business_"):
            try:
                _, business_id_str = args.split("_")
                business_id = int(business_id_str)
            except (ValueError, IndexError):
                await message.answer("⚠️ Некорректный формат ссылки")
                return

            business = session.get(Business, business_id)
            if not business:
                await message.answer("❌ Бизнес не найден")
                return

            user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
            if not user:
                user = User(
                    telegram_id=message.from_user.id,
                    full_name=message.from_user.full_name,
                    username=message.from_user.username,
                )
                session.add(user)
                session.commit()

            user_business = session.query(UserBusiness).filter_by(
                user_id=user.id,
                business_id=business.id
            ).first()
            if not user_business:
                user_business = UserBusiness(
                    user_id=user.id,
                    business_id=business.id,
                    points=0,
                )
                session.add(user_business)
                session.commit()

            try:
                await bot.send_message(
                    chat_id=business.admin_id,
                    text=(
                        "🔔 Новый клиент!\n"
                        f"👤 Имя: {user.full_name}\n"
                        f"📱 Логин: @{user.username}\n"
                        f"⭐ Баллов: {user_business.points}"
                    ),
                    reply_markup=get_payment_keyboard(user.id, business.id)
                )
            except TelegramAPIError as e:
                logger.error(f"Ошибка отправки уведомления: {str(e)}")

            web_app_url = f"https://ваш-сайт.ru/app?user_id={user.id}&business_id={business.admin_id}"
            
            builder = InlineKeyboardBuilder()
            builder.button(
                text="Назад",
                callback_data="back_to_main_menu"
            )
            
            await message.answer(
                f"🔗 Вы привязаны к бизнесу: {business.name}\n"
                f"💰 Ваши баллы: {user_business.points}\n\n"
                "👇 Нажмите кнопку ниже, чтобы открыть приложение:",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[
                        [types.KeyboardButton(
                            text="Открыть приложение 🚀",
                            web_app=types.WebAppInfo(url=web_app_url))
                        ]
                    ],
                    resize_keyboard=True,
                )
            )
            await message.answer(
                "↩️ Вернуться в главное меню:",
                reply_markup=builder.as_markup()
            )
        else:
            await state.set_state(MenuStates.MAIN_MENU)
            await message.answer_photo(
                photo=types.FSInputFile("./static/Все магазины в одном приложении.png"),
                caption=(
                    "👋 Добро пожаловать в SaveX!\n\n"
                    "*Лояльность*\n"
                    "QR-код вместо физ. карт лояльностей - клиенты копят баллы, даже не замечая этого!\n\n"
                    "*Для бизнеса*\n"
                    "Подключение за 20 минут - никаких сложных настроек и дорогих разработок"
                ),
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {str(e)}")
        await message.answer("❌ Ошибка базы данных")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка")
    finally:
        session.close()

@dp.callback_query(F.data == "show_how_it_works")
async def show_how_it_works(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.bot.delete_message(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")
    
    await state.set_state(MenuStates.HOW_IT_WORKS)
    await callback.message.answer_photo(
        photo=types.FSInputFile("./static/Black White Halftone Creative Portfolio Presentation.png"),
        caption=(
            "📖 Как работает SaveX?\n\n"
            "1. Клиенты сканируют QR-код\n"
            "2. Автоматически регистрируются в системе\n"
            "3. Копят баллы за покупки\n"
            "4. Используют баллы для скидок\n\n"
            "Простое подключение и управление всеми баллами в любимых магазинов"
        ),
        reply_markup=get_back_to_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer_photo(
            photo=types.FSInputFile("./static/Все магазины в одном приложении.png"),
            caption=(
                "👋 Добро пожаловать в SaveX!\n\n"
                "*Лояльность*\n"
                "QR-код вместо физ. карт лояльностей - клиенты копят баллы, даже не замечая этого!\n\n"
                "*Для бизнеса*\n"
                "Подключение за 20 минут - никаких сложных настроек и дорогих разработок"
            ),
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.set_state(MenuStates.MAIN_MENU)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        await callback.answer()


@dp.callback_query(F.data == "add_business")
async def add_business_callback(callback: CallbackQuery, state: FSMContext):
    await add_business_start(callback.message, state)
    await callback.answer()

@dp.message(Command("add_business"))
async def add_business_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("🚫 У вас нет прав администратора")
    
    await message.answer("📝 Введите название бизнеса:")
    await state.set_state(BusinessCreation.AWAITING_NAME)

@dp.callback_query(F.data.startswith("process_payment:"))
async def start_payment_process(callback: CallbackQuery, state: FSMContext):
    try:
        _, user_id_str, business_id_str = callback.data.split(":")
        user_id = int(user_id_str)
        business_id = int(business_id_str)
        
        await state.update_data(
            user_id=user_id,
            business_id=business_id
        )
        
        await callback.message.answer("💵 Введите сумму покупки:")
        await state.set_state(PurchaseStates.AWAITING_AMOUNT)
        
    except Exception as e:
        logger.error(f"Error starting payment: {str(e)}")
        await callback.answer("❌ Ошибка запуска оплаты")

@dp.message(PurchaseStates.AWAITING_AMOUNT)
async def process_purchase_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        
        await state.update_data(amount=amount)
        await message.answer("🎫 Введите количество баллов для списания:")
        await state.set_state(PurchaseStates.AWAITING_POINTS)
        
    except ValueError:
        await message.answer("❌ Некорректная сумма. Введите положительное число.")

@dp.message(PurchaseStates.AWAITING_POINTS)
async def process_purchase_points(message: Message, state: FSMContext):
    session = get_session()
    try:
        data = await state.get_data()
        user_id = data["user_id"]
        business_id = data["business_id"]
        amount = data["amount"]
        points = int(message.text)
        
        user_business = session.query(UserBusiness).filter_by(
            user_id=user_id,
            business_id=business_id
        ).first()
        
        business = session.get(Business, business_id)

        if points < 0:
            await message.answer("❌ Количество баллов не может быть отрицательным")
            return
            
        if points > user_business.points:
            await message.answer("❌ Недостаточно баллов")
            return

        max_allowed_points = int(amount * 0.5)
        if points > max_allowed_points:
            await message.answer(f"❌ Можно списать не более {max_allowed_points} баллов")
            return

        user_business.points -= points

        if points == 0:
            bonus = round(amount * (business.conversion_rate / 100))
            user_business.points += bonus

        session.add(Purchase(
            user_id=user_id,
            business_id=business_id,
            amount=amount,
            points_used=points
        ))
        session.commit()

        await message.answer(
            "✅ Покупка оформлена!\n"
            f"💵 Сумма: {amount:.2f}\n"
            f"🎫 Списано баллов: {points}\n"
            f"⭐ Новый баланс: {user_business.points}"
        )

    except ValueError:
        await message.answer("❌ Введите целое число баллов")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await message.answer("⚠️ Произошла ошибка")
        session.rollback()
    finally:
        await state.clear()
        session.close()

@dp.message(BusinessCreation.AWAITING_NAME)
async def process_business_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🔢 Введите процент конвертации (например 10):")
    await state.set_state(BusinessCreation.AWAITING_CONVERSION_RATE)

@dp.message(BusinessCreation.AWAITING_CONVERSION_RATE)
async def process_conversion_rate(message: Message, state: FSMContext):
    session = get_session()
    try:
        rate = float(message.text)
        if rate <= 0:
            await message.answer("❌ Процент должен быть положительным")
            return
            
        data = await state.get_data()
        
        new_business = Business(
            name=data['name'],
            conversion_rate=rate,
            admin_id=message.from_user.id
        )
        session.add(new_business)
        session.commit()
        
        qr_buffer = generate_qr(new_business.id)
        await message.answer_photo(
            BufferedInputFile(
                file=qr_buffer.getvalue(),
                filename="qr_code.png"
            ),
            caption="Ваш QR-код"
        )
        
    except ValueError:
        await message.answer("❌ Некорректный формат. Введите число.")
    except Exception as e:
        logger.error(f"Ошибка создания бизнеса: {str(e)}")
        await message.answer("⚠️ Ошибка при создании бизнеса")
        session.rollback()
    finally:
        await state.clear()
        session.close()

async def handle_qr_scan(message: types.Message, business_id: int):
    session = get_session()
    try:
        business = session.get(Business, business_id)
        if not business:
            return await message.answer("❌ Бизнес не найден")
        
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )
            session.add(user)
            session.commit()
            
        user_business = session.query(UserBusiness).filter_by(
            user_id=user.id,
            business_id=business.id
        ).first()
        
        if not user_business:
            user_business = UserBusiness(
                user_id=user.id,
                business_id=business.id,
                points=0
            )
            session.add(user_business)
            session.commit()
        
        await message.answer(
            f"🏪 Магазин: {business.name}\n"
            f"⭐ Ваши баллы: {user_business.points}"
        )
        
        await bot.send_message(
            business.admin_id,
            f"🔔 Новый клиент!\n"
            f"👤 {user.full_name}\n"
            f"📱 @{user.username}\n"
            f"💰 Баллов: {user_business.points}",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text="💳 Обработать покупку",
                        callback_data=f"process_payment:{user.id}:{business.id}"
                    )
                ]]
            )
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки QR: {str(e)}")
        session.rollback()
    finally:
        session.close()

@dp.callback_query(F.data.startswith("process_payment_"))
async def start_payment(callback: CallbackQuery, state: FSMContext):
    try:
        _, user_id, business_id = callback.data.split('_')
        await state.update_data(
            user_id=int(user_id),
            business_id=int(business_id)
        )
        await callback.message.answer("💵 Введите сумму покупки:")
        await state.set_state(PaymentStates.AWAITING_AMOUNT)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error starting payment: {str(e)}")
        await callback.answer("❌ Ошибка запуска оплаты")

@dp.message(PaymentStates.AWAITING_AMOUNT)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await message.answer("🎫 Введите количество баллов для списания (0 если не нужно):")
        await state.set_state(PaymentStates.AWAITING_POINTS)
    except:
        await message.answer("❌ Некорректная сумма")

@dp.message(PaymentStates.AWAITING_POINTS)
async def process_points(message: Message, state: FSMContext):
    session = get_session()
    try:
        data = await state.get_data()
        points = int(message.text)
        
        user_business = session.query(UserBusiness).filter_by(
            user_id=data['user_id'],
            business_id=data['business_id']
        ).first()
        
        business = session.query(Business).get(data['business_id'])
        
        if points < 0:
            return await message.answer("❌ Количество баллов не может быть отрицательным")
            
        if points > user_business.points:
            return await message.answer("❌ Недостаточно баллов")
        
        user_business.points -= points
        
        if points == 0:
            bonus = data['amount'] * (business.conversion_rate / 100)
            user_business.points += bonus
        
        purchase = Purchase(
            user_id=data['user_id'],
            business_id=data['business_id'],
            amount=data['amount'],
            points_used=points
        )
        session.add(purchase)
        session.commit()
        
        await message.answer(
            f"✅ Операция успешна!\n"
            f"💵 Сумма: {data['amount']}\n"
            f"🎫 Списано баллов: {points}\n"
            f"⭐ Новый баланс: {user_business.points}"
        )
        
    except ValueError:
        await message.answer("❌ Введите целое число баллов")
    except Exception as e:
        logger.error(f"Ошибка платежа: {str(e)}")
        await message.answer("⚠️ Произошла ошибка")
        session.rollback()
    finally:
        await state.clear()
        session.close()

if __name__ == "__main__":
    logger.info("Бот запущен")
    dp.run_polling(bot)