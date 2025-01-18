import json
import logging
import asyncio
import os
from yookassa import Configuration, Payment
from aiogram import Bot, Dispatcher, types, executor
from settings import config

# Logging Setup
LOG_FILE = 'course_bot.log'
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'x').close()
logging.basicConfig(level=logging.INFO, filename=LOG_FILE, format='%(asctime)s - %(levelname)s - %(message)s')

# YooKassa Configuration
Configuration.account_id = config.account_id
Configuration.secret_key = config.secret_key

# Bot Initialization
bot = Bot(token=config.bot_token)
dp = Dispatcher(bot)

# Tariffs Configuration
TARIFFS = {
    'Базовый': {
        'price': 1,
        'chat_id': -1001826989197,
        'channel_id': -1001847911388,
    },
    'С добавками': {
        'price': 1,
        'chat_id': -1001869574555,
        'channel_id': -1001852442626,
    },
    'Горячий способ': {
        'price': 1,
        'chat_id': -1001797777365,
        'channel_id': -1001775399351,
    },
}

# Keyboards Setup
keyboard_for_client = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
keyboard_for_client.add(*[types.KeyboardButton(title) for title in TARIFFS.keys()])

# YooKassa Payment Handling
def create_payment(price: int, description: str):
    payment_data = Payment.create({
        "amount": {"value": f"{price}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/get_soap_course_bot"},
        "capture": True,
        "description": description,
    })
    return json.loads(payment_data.json())

async def monitor_payment(payment_id: str, message: types.Message, tariff: dict):
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

    await bot.send_message(
        message.chat.id,
        'Срок действия ссылки истек или произошла ошибка. Обратитесь к @Aizada_03.'
    )

async def handle_successful_payment(payment, message, tariff):
    logging.info(f"Payment succeeded: {payment['description']}")

    course_link = await bot.create_chat_invite_link(tariff['channel_id'], member_limit=1)
    support_link = await bot.create_chat_invite_link(tariff['chat_id'], member_limit=1)

    await bot.send_message(message.chat.id, 'Спасибо за покупку!😘')
    await bot.send_message(message.chat.id, f"Канал курса:\n{course_link.invite_link}")
    await bot.send_message(message.chat.id, f"Чат поддержки:\n{support_link.invite_link}")

# Handlers
@dp.message_handler(commands=['start'])
async def handle_start(message: types.Message):
    await message.reply("Выберите тариф и я отправлю вам ссылку для оплаты.", reply_markup=keyboard_for_client)

@dp.message_handler()
async def handle_message(message: types.Message):
    tariff = TARIFFS.get(message.text)
    if tariff:
        username = message.from_user.username
        description = f'Покупка курса по мыловарению "{message.text}", пользователь - {username}.'

        payment_data = create_payment(tariff['price'], description)
        payment_id = payment_data['id']
        payment_link = payment_data['confirmation']['confirmation_url']

        await bot.send_message(message.chat.id, f'Обработка платежа займет минуту.\n{payment_link}')
        await monitor_payment(payment_id, message, tariff)
    else:
        await message.reply('Извините, но я не знаю как ответить на такое сообщение.')

# Entry Point
if __name__ == '__main__':
    logging.info("Bot started")
    executor.start_polling(dp, skip_updates=True)
