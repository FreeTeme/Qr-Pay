from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить оплату", callback_data="confirm_payment")
    builder.button(text="❌ Отмена", callback_data="cancel_payment")
    return builder.as_markup()