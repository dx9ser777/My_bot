import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ (ПРЯМЫЕ ТОКЕНЫ) ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'

SUPPORT_URL = "https://t.me/WareSupport"
PAYMENT_ADMIN = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip" 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

active_users = set()

# Цены в USDT для Crypto Bot
PRICES_CRYPTO = {
    "apk_7": 4, "apk_30": 8,
    "ios_7": 6, "ios_30": 12
}

# --- ЛОГИКА КЛЮЧЕЙ ---
def extract_one_key():
    if os.path.exists("keys.txt"):
        with open("keys.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            key_to_give = lines[0].strip()
            with open("keys.txt", "w", encoding="utf-8") as f:
                f.writelines(lines[1:])
            return key_to_give
    return None

# --- API CRYPTO PAY ---
async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': 'DX9WARE Subscription'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

async def check_invoice(invoice_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        params = {'invoice_ids': str(invoice_id)}
        async with session.get('https://pay.crypt.bot/api/getInvoices', params=params, headers=headers) as resp:
            res = await resp.json()
            if res['ok'] and res['result']['items']:
                return res['result']['items'][0]['status'] == 'paid'
    return False

# --- ИНТЕРФЕЙС ---
def get_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🛒 Товары и Цены", callback_data="shop")
    )
    if user_id not in active_users:
        markup.add(types.InlineKeyboardButton("🔑 Активировать ключ", callback_data="activate"))
    else:
        markup.add(types.InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    markup.add(types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL))
    return markup

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("👋 Добро пожаловать в DX9WARE!", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    
    if callback_query.data == 'shop':
        markup = types.InlineKeyboardMarkup(row_width=2).add(
            types.InlineKeyboardButton("Android (APK) 😀", callback_data="shop_apk"),
            types.InlineKeyboardButton("iOS 😔", callback_data="shop_ios"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")
        )
        await bot.edit_message_text("Выберите платформу:", uid, callback_query.message.message_id, reply_markup=markup)

    elif callback_query.data == 'shop_apk':
        text = (
            "🍏 **APK DX9WARE**\n\n"
            "🌟 **Цены в Stars:**\n"
            "├ 7 дней — 350 ⭐\n"
            "└ Месяц — 700 ⭐\n\n"
            "🌐 **Цены в Crypto:**\n"
            "├ 7 дней — 4 USDT\n"
            "└ Месяц — 8 USDT\n\n"
            f"📩 По вопросам оплаты звёздами: {PAYMENT_ADMIN}"
        )
        markup = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("💳 Купить 7 дней (4 USDT)", callback_data="buy_apk_7"),
            types.InlineKeyboardButton("💳 Купить Месяц (8 USDT)", callback_data="buy_apk_30"),
            types.InlineKeyboardButton("🌟 Купить за Stars (Админ)", url=f"https://t.me/{PAYMENT_ADMIN.replace('@', '')}"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="shop")
        )
        await bot.edit_message_text(text, uid, callback_query.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif callback_query.data == 'shop_ios':
        text = (
            "🍎 **IOS DX9WARE**\n\n"
            "🌟 **Цены в Stars:**\n"
            "├ 7 дней — 400 ⭐\n"
            "└ Месяц — 800 ⭐\n\n"
            "🌐 **Цены в Crypto:**\n"
            "├ 7 дней — 6 USDT\n"
            "└ Месяц — 12 USDT\n\n"
            f"📩 По вопросам оплаты звёздами: {PAYMENT_ADMIN}"
        )
        markup = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("💳 Купить 7 дней (6 USDT)", callback_data="buy_ios_7"),
            types.InlineKeyboardButton("💳 Купить Месяц (12 USDT)", callback_data="buy_ios_30"),
            types.InlineKeyboardButton("🌟 Купить за Stars (Админ)", url=f"https://t.me/{PAYMENT_ADMIN.replace('@', '')}"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="shop")
        )
        await bot.edit_message_text(text, uid, callback_query.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif callback_query.data.startswith('buy_'):
        plan = callback_query.data.replace('buy_', '')
        res = await create_invoice(PRICES_CRYPTO[plan])
        if res['ok']:
            markup = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔗 Перейти к оплате", url=res['result']['pay_url']),
                types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{res['result']['invoice_id']}")
            )
            await bot.send_message(uid, f"💰 Счет на {PRICES_CRYPTO[plan]} USDT создан:", reply_markup=markup)

    elif callback_query.data.startswith('check_'):
        inv_id = callback_query.data.replace('check_', '')
        if await check_invoice(inv_id):
            key = extract_one_key()
            if key:
                active_users.add(uid)
                await bot.send_message(uid, f"✅ Оплачено! Твой ключ: `{key}`", parse_mode="Markdown")
            else:
                await bot.send_message(uid, f"❌ Ключи закончились! Напиши: {PAYMENT_ADMIN}")
        else:
            await bot.answer_callback_query(callback_query.id, "❌ Оплата не найдена", show_alert=True)

    elif callback_query.data == 'activate':
        await bot.send_message(uid, "🔑 Отправь ключ доступа одним сообщением:")

    elif callback_query.data == 'profile':
        status = "Активен ✅" if uid in active_users else "Нет подписки ❌"
        await bot.send_message(uid, f"👤 **Профиль**\n\nID: `{uid}`\nСтатус: {status}", parse_mode="Markdown")

    elif callback_query.data == 'get_files':
        if uid in active_users and os.path.exists(FILE_NAME):
            with open(FILE_NAME, 'rb') as f:
                await bot.send_document(uid, f, caption="🚀 Твой файл DX9WARE!")
    
    elif callback_query.data == 'back_main':
        await bot.edit_message_text("Главное меню:", uid, callback_query.message.message_id, reply_markup=get_main_menu(uid))

    await bot.answer_callback_query(callback_query.id)

@dp.message_handler()
async def handle_msg(message: types.Message):
    key = message.text.strip()
    if os.path.exists("keys.txt"):
        with open("keys.txt", "r") as f:
            valid_keys = [l.strip() for l in f.readlines()]
            if key in valid_keys:
                active_users.add(message.from_user.id)
                await message.answer("✅ Доступ активирован!", reply_markup=get_main_menu(message.from_user.id))
                return
    await message.answer("❌ Неверный ключ.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
