import json
import logging
import asyncio
import os
from yookassa import Configuration, Payment
from aiogram import Bot, Dispatcher, types, executor
from settings import config
from functools import wraps

LOG_FILE = 'course_bot.log'
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'x').close()

# Создаем логгер
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Создаем обработчик для записи в файл
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Добавляем обработчики к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# YooKassa Configuration
Configuration.account_id = config.YOOKASSA_ACCOUNT_ID
Configuration.secret_key = config.YOOKASSA_SECRET_KEY

# Bot Initialization
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(bot)


# Tariffs Configuration
TARIFFS = {
    # 'Базовый': {
    #     'price': 1,
    #     'chat_id': -1001826989197,
    #     'channel_id': -1001847911388,
    # },
    # 'С добавками': {
    #     'price': 1,
    #     'chat_id': -1001869574555,
    #     'channel_id': -1001852442626,
    # },
    # 'Горячий способ': {
    #     'price': 1,
    #     'chat_id': -1001797777365,
    #     'channel_id': -1001775399351,
    "Марафон по мыловарению": {
        "price": 990,
        "chat_id": -1002485301769,
        "channel_id": -1002391181980,
    },
}
ids_list = []

for details in TARIFFS.values():
    chat_id = details.get("chat_id")
    channel_id = details.get("channel_id")
    ids_list.append((chat_id, channel_id))



def ignore_chats(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.chat.id in ids_list:
            return  # Ignore the message if the chat ID is in the ignore list
        return await func(message, *args, **kwargs)
    return wrapper



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

    final_message = f'Добро пожаловать!\n<a href="{course_link.invite_link}">Уроки</a>\n<a href="{support_link.invite_link}">Чат поддержки</a>'
    await bot.send_message(message.chat.id, 'Спасибо за покупку!😘')
    await bot.send_message(message.chat.id, f"Канал курса:\n{course_link.invite_link}")
    await bot.send_message(message.chat.id, f"Чат поддержки:\n{support_link.invite_link}")

# Handlers
@dp.message_handler(commands=['start'])
@ignore_chats
async def handle_start(message: types.Message):
    bot_message = f"Привет, {message.from_user.first_name}.\nБлагодарю за оказанное доверие. Я надеюсь вы получите от марафона максимум пользы и радости." + '<a href="{payment_link}">Ваша ссылка для оплаты курса - {price} руб.</a>'
    
    tariff = TARIFFS.get('Марафон по мыловарению')
    username = message.from_user.username
    name = f"{message.from_user.first_name} {message.from_user.last_name}"
    description = f'Покупка курса по мыловарению "{message.text}", пользователь - @{username}, {name}.'
    price = tariff['price']
    print('asdf')
    logging.error('before')
    payment_data = create_payment(price, description)
    logging.info('after')
    payment_id = payment_data['id']
    payment_link = payment_data['confirmation']['confirmation_url']

    await bot.send_message(message.chat.id, message, reply_markup=keyboard_for_client, parse_mode=types.ParseMode.HTML)
    await monitor_payment(payment_id, message, tariff)

@dp.message_handler()
@ignore_chats
async def handle_message(message: types.Message):
    tariff = TARIFFS.get(message.text)
    if tariff:
        username = message.from_user.username
        name = f"{message.from_user.first_name} {message.from_user.last_name}"
        description = f'Покупка курса по мыловарению "{message.text}", пользователь - @{username}, {name}.'
        price = tariff['price']
        payment_data = create_payment(price, description)
        payment_id = payment_data['id']
        payment_link = payment_data['confirmation']['confirmation_url']

        await bot.send_message(message.chat.id, f'<a href="{payment_link}">Ваша ссылка для оплаты курса - {price} руб.</a>', parse_mode=types.ParseMode.HTML)
        await monitor_payment(payment_id, message, tariff)
    else:
        await message.reply('Извините, но я не знаю как ответить на такое сообщение.')

# Entry Point
if __name__ == '__main__':
    logging.info("Bot started")
    executor.start_polling(dp, skip_updates=True)
