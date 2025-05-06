# main.py
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from config import BOT_TOKEN, ADMINS, BOT_USERNAME
from db import get_business, get_session, get_user  # используем функцию для получения сессии
from models import User, Business, UserBusiness, Purchase
from qr_utils import generate_qr
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.exc import SQLAlchemyError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

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

            # Уведомление админа (как у вас было)
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

            web_app_url = f"https://app.qrpay.tw1.su/?user_id={message.from_user.id}&business_id={business.admin_id}"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Перейти в приложение",
                    web_app=WebAppInfo(url=web_app_url)  # Используем WebApp вместо url
                )]
            ])

            await message.answer(
                f"🔗 Вы привязаны к бизнесу: {business.name}\n"
                f"💰 Ваши баллы: {user_business.points}\n\n"
                "👇 Нажмите кнопку ниже, чтобы открыть приложение:",
                reply_markup=keyboard
            )
        else:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Подключить свой бизнес",
                url='https://app.qrpay.tw1.su/bis/'
            ))
            
            await message.answer(
                "👋 Добро пожаловать в SaveX!\n\n"
                "*Лояльность*\n"
                "QR-код вместо физ. карт лояльностей - клиенты копят баллы, даже не замечая этого!\n\n"
                "*Для бизнеса*\n"
                "Подключение за 20 минут - никаких сложных настроек и дорогих разработок",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
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

@dp.message(Command("add_business"))
async def add_business_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("🚫 У вас нет прав администратора")
    
    await message.answer("📝 Введите название бизнеса:")
    await state.set_state(BusinessCreation.AWAITING_NAME)


# 2. Обработчик кнопки
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
        await callback.answer("❌ Ошибка запуска оплаты")
# --------------------------------------------
# Обработчики состояний
# --------------------------------------------

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
        points = int(message.text)  # Баллы всегда целые
        
        user_business = session.query(UserBusiness).filter_by(
            user_id=user_id,
            business_id=business_id
        ).first()
        
        business = session.get(Business, business_id)

        # 1. Проверка баллов
        if points > user_business.points:
            await message.answer("❌ Недостаточно баллов")
            return

        # 2. Проверка 50% лимита
        max_allowed_points = int(amount * 0.5)  # Округление в меньшую сторону
        if points > max_allowed_points:
            await message.answer(f"❌ Можно списать не более {max_allowed_points} баллов")
            return

        # 3. Списание баллов
        user_business.points -= points

        # 4. Начисление баллов (только если не списывали)
        if points == 0:
            # Округляем до ближайшего целого
            bonus = round(amount * (business.conversion_rate / 100))
            user_business.points += bonus

        # 5. Сохраняем покупку
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
        data = await state.get_data()
        
        # Создание бизнеса
        new_business = Business(
            name=data['name'],
            conversion_rate=rate,
            admin_id=message.from_user.id
        )
        session.add(new_business)
        session.commit()
        
        # Генерация QR
        qr_buffer = generate_qr(new_business.id)
        await message.answer_photo(
            BufferedInputFile(
                file=qr_buffer.getvalue(),  # Байты изображения
                filename="qr_code.png"      # Имя файла
            ),
            caption="Ваш QR-код"
        )
        
    except ValueError:
        await message.answer("❌ Некорректный формат. Введите число.")
    except Exception as e:
        logger.error(f"Ошибка создания бизнеса: {str(e)}")
        await message.answer("⚠️ Ошибка при создании бизнеса")
    finally:
        await state.clear()
        session.close()

# --------------------------------------------
# Обработка QR-кодов
# --------------------------------------------

async def handle_qr_scan(message: types.Message, business_id: int):
    session = get_session()
    try:
        business = get_business(business_id)
        if not business:
            return await message.answer("❌ Бизнес не найден")
        
        user = get_user(message.from_user.id)
        user_business = session.query(UserBusiness).filter_by(
            user_id=user.id,
            business_id=business.id
        ).first()
        
        # Создаем связь если не существует
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
        
        # Уведомление бизнесу
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
                        callback_data=f"process_payment_{user.id}_{business.id}"
                    )
                ]]
            )
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки QR: {str(e)}")
    finally:
        session.close()

# --------------------------------------------
# Обработка платежей
# --------------------------------------------

@dp.callback_query(F.data.startswith("process_payment_"))
async def start_payment(callback: CallbackQuery, state: FSMContext):
    _, user_id, business_id = callback.data.split('_')
    await state.update_data(
        user_id=int(user_id),
        business_id=int(business_id)
    )
    await callback.message.answer("💵 Введите сумму покупки:")
    await state.set_state(PaymentStates.AWAITING_AMOUNT)

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
        
        # Получаем данные
        user_business = session.query(UserBusiness).filter_by(
            user_id=data['user_id'],
            business_id=data['business_id']
        ).first()
        
        business = session.query(Business).get(data['business_id'])
        
        # Проверка баллов
        if points < 0 or points > user_business.points:
            return await message.answer("❌ Недостаточно баллов")
        
        # Списание баллов
        user_business.points -= points
        
        # Начисление новых баллов если не списывали
        if points == 0:
            bonus = data['amount'] * (business.conversion_rate / 100)
            user_business.points += bonus
        
        # Запись покупки
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
        
    except Exception as e:
        logger.error(f"Ошибка платежа: {str(e)}")
        await message.answer("⚠️ Произошла ошибка")
    finally:
        await state.clear()
        session.close()

# --------------------------------------------
# Запуск бота
# --------------------------------------------


if __name__ == "__main__":
    logger.info("Бот запущен")
    dp.run_polling(bot)
