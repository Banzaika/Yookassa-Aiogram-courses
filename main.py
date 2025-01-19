import json
import logging
import asyncio
import os
from yookassa import Configuration, Payment
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.filters import Command
from aiogram.dispatcher.router import Router
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from settings import config
from functools import wraps
# Логирование
LOG_FILE = 'course_bot.log'
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'x').close()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Настройки YooKassa
Configuration.account_id = config.YOOKASSA_ACCOUNT_ID
Configuration.secret_key = config.YOOKASSA_SECRET_KEY

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Тарифы
TARIFFS = {
    "Марафон по мыловарению": {
        "price": 990,
        "chat_id": -1002485301769,
        "channel_id": -1002391181980,
    },
}
ids_list = [(details["chat_id"], details["channel_id"]) for details in TARIFFS.values()]

# Функция для создания платежа
def create_payment(price: int, description: str):
    payment_data = Payment.create({
        "amount": {"value": f"{price}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/get_soap_course_bot"},
        "capture": True,
        "description": description,
    })
    return json.loads(payment_data.json())

# Мониторинг платежа
async def monitor_payment(payment_id: str, message: Message, tariff: dict):
    retry_interval = 60
    max_retries = 20
    retries = 0

    while retries < max_retries:
        payment = json.loads(Payment.find_one(payment_id).json())
        logging.info(f"Checking payment status for: {payment['description']}")

        if payment['status'] == 'succeeded':
            await handle_successful_payment(payment, message, tariff)
            return

        await asyncio.sleep(retry_interval if retries < 1 else 15)
        retries += 1

    await message.answer('Срок действия ссылки истек или произошла ошибка. Обратитесь к @Aizada_03.')

# Обработка успешного платежа
async def handle_successful_payment(payment, message: Message, tariff):
    logging.info(f"Payment succeeded: {payment['description']}")

    course_link = await bot.create_chat_invite_link(tariff['channel_id'], member_limit=1)
    support_link = await bot.create_chat_invite_link(tariff['chat_id'], member_limit=1)

    final_message = (
        f'Добро пожаловать!\n'
        f'<a href="{course_link.invite_link}">Уроки</a>\n'
        f'<a href="{support_link.invite_link}">Чат поддержки</a>'
    )

    await message.answer(
        final_message,
        parse_mode='HTML',
    )

# Игнорирование сообщений из определенных чатов
def ignore_chats(func):
    @wraps(func)
    async def wrapper(message: Message):
        if message.chat.id in ids_list:
            return  # Пропустить обработку сообщения
        return await func(message)
    return wrapper


# Обработчик команды /start
@router.message(Command(commands=["start"]))
@ignore_chats
async def handle_start(message: Message):
    tariff = TARIFFS.get('Марафон по мыловарению')
    username = message.from_user.username
    name = f"{message.from_user.first_name} {message.from_user.last_name}"
    description = f'Покупка курса по мыловарению, пользователь - @{username}, {name}.'
    price = tariff['price']

    payment_data = create_payment(price, description)
    payment_id = payment_data['id']
    payment_link = payment_data['confirmation']['confirmation_url']

    bot_message = (
        f"Привет, {message.from_user.first_name}.\n"
        f"Благодарю за оказанное доверие. Надеюсь, вы получите максимум пользы и радости от марафона.\n"
        f'<a href="{payment_link}">Ваша ссылка для оплаты курса - {price} руб.</a>'
    )

    await message.answer(bot_message, parse_mode='HTML', reply_markup=create_keyboard(list(TARIFFS.keys())))
    await monitor_payment(payment_id, message, tariff)

# Обработчик текстовых сообщений
@router.message()
@ignore_chats
async def handle_message(message: Message):
    tariff = TARIFFS.get(message.text)
    if tariff:
        username = message.from_user.username
        name = f"{message.from_user.first_name} {message.from_user.last_name}"
        description = f'Покупка курса по мыловарению, пользователь - @{username}, {name}.'
        price = tariff['price']

        payment_data = create_payment(price, description)
        payment_id = payment_data['id']
        payment_link = payment_data['confirmation']['confirmation_url']

        await message.answer(
            f'<a href="{payment_link}">Ваша ссылка для оплаты курса - {price} руб.</a>',
            parse_mode='HTML',
        )
        await monitor_payment(payment_id, message, tariff)
    else:
        await message.reply('Извините, но я не знаю, как ответить на такое сообщение.')

# Создание клавиатуры
def create_keyboard(buttons: list):
    builder = ReplyKeyboardBuilder()
    for button in buttons:
        builder.add(KeyboardButton(text=button))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

# Главная точка входа
async def main():
    dp.include_router(router)
    logging.info("Bot started")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
