import json
from yookassa import Configuration, Payment
import config
from aiogram import Bot, Dispatcher, types, executor
import logging
import asyncio
import os

Configuration.account_id = config.account_id
Configuration.secret_key = config.secret_key

# logging

if not os.path.exists('course_bot.log'):
    open('course_bot.log', 'x')
logging.basicConfig(level=logging.INFO, filename='soap.log')

# INITIALIZATION
bot = Bot(config.bot_token)
dp = Dispatcher(bot)


# WORKING WITH YOOKASSA

def payment(price: int, description: str):
    payment = Payment.create({
        "amount": {
            "value": str(price) + '.00',
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/get_soap_course_bot"
        },
        "capture": True,
        "description": description
    })

    return json.loads(payment.json())


async def check_payment(payment_id, message, tarif):
    payment = json.loads((Payment.find_one(payment_id)).json())
    n = 0
    while payment['status'] == 'pending':
        logging.info(f"check payment {payment['description']}")
        payment = json.loads((Payment.find_one(payment_id)).json())
        if n < 1:
            time = 70
        if 0 < n > 20:
            time = 15
        else:
            time = 60
        await asyncio.sleep(time)
        n += 1

    if payment['status'] == 'succeeded':
        logging.info(f'Покупка, описание - {payment["description"]}')
        link_for_course = await bot.create_chat_invite_link(tarif['channel_id'], member_limit=1)
        link_for_support = await bot.create_chat_invite_link(tarif['chat_id'], member_limit=1)

        await bot.send_message(
            message.chat.id,
            'Спасибо за покупку!😘'
        )

        await bot.send_message(
            message.chat.id,
            'Канал курса:\n' + link_for_course.invite_link)

        await bot.send_message(
            message.chat.id, "Чат поддержки:\n" + link_for_support.invite_link
        )
    else:
        await bot.send_message(
            message.chat.id,
            'Срок действия ссылки истек (для получения новой нажмите на кнопку ещё раз) или произошла другая ошибка. Если оплата не прошла, то обратитесь к @Aizada_03.'
        )


# ----------------------------------------------------------------
# Тарифы и каналы

#Названия кнопок
base_title = 'Базовый'
with_adds_title = 'С добавками'
hot_title = 'Горячий способ'


#конфигурации тарифов курса
tarifs = {
    base_title: {
        'price': 1,  # 5900
        'chat_id': -1001826989197,  # id чата поддержки
        'channel_id': -1001847911388,  # id канала курса
    },
    with_adds_title: {
        'price': 1,  # 9500
        'chat_id': -1001869574555,
        'channel_id': -1001852442626,
    },
    hot_title: {
        'price': 1,  # 12500
        'chat_id': -1001797777365,
        'channel_id': -1001775399351,
    },
}

# ----------------------------------------------------------------
# BUTTONS AND KEYBOARDS
base_btn = types.KeyboardButton(base_title)
with_adds_btn = types.KeyboardButton(with_adds_title)
hot_meth_btn = types.KeyboardButton(hot_title)

keyboard_for_client = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(base_btn).add(
    with_adds_btn).add(hot_meth_btn)


# -----------------------------------------------
# MESSAGE HANDLERS


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Выберите тариф и я отправлю вам ссылку для оплаты.", reply_markup=keyboard_for_client)


@dp.message_handler()
async def some_message(message: types.Message):
    if message.text in tarifs:
        title = message.text
        tarif = tarifs[title]
        username = message.from_user.username

        payment_data = payment(tarif['price'], f'Покупка курса по мыловарению "{title}", пользователь - {username}.')
        link_for_pay = payment_data['confirmation']['confirmation_url']
        payment_id = payment_data['id']
        await bot.send_message(message.chat.id, f'Обработка платежа займет минуту.\n{link_for_pay}')
        await check_payment(payment_id, message, tarif)
    else:
        await bot.send_message(message.chat.id, 'Извините, но я не знаю как ответить на такое сообщение.')


# --------------------------------------------------------------

# START

if __name__ == '__main__':
    print('[+] start')
    executor.start_polling(dp, skip_updates=False)
