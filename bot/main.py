# main.py
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from config import BOT_TOKEN, ADMINS, BOT_USERNAME
from db import get_session  # используем функцию для получения сессии
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

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def get_payment_keyboard(user_id: int, business_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💳 Оформить покупку",
        callback_data=f"process_payment:{user_id}:{business_id}"
    )
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: Command):
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

            await message.answer(
                f"🔗 Вы привязаны к бизнесу: {business.name}\n"
                f"💰 Ваши баллы: {user_business.points}"
            )
        else:
            await message.answer("👋 Добро пожаловать!")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {str(e)}")
        await message.answer("❌ Ошибка базы данных")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка")
    finally:
        session.close()

# Остальные обработчики также используют get_session() аналогичным образом.

if __name__ == "__main__":
    logger.info("Бот запущен")
    dp.run_polling(bot)
