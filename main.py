import logging
import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
SUPPORT_URL = "https://t.me/WareSupport"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip" 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

active_users = set()

PRICES = {
    "apk_7": 4, "apk_30": 8,
    "ios_7": 6, "ios_30": 12
}

# --- ЛОГИКА ВЫДАЧИ КЛЮЧА ---
def extract_one_key():
    paths = ["keys.txt", "/data/keys.txt", "data/keys.txt"]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            if not lines:
                return None
            
            # Берем первый ключ и убираем его из списка
            key_to_give = lines[0].strip()
            remaining_keys = lines[1:]
            
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(remaining_keys)
            
            return key_to_give
    return None

async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {
        'asset': 'USDT', 'amount': str(amount),
        'description': 'Оплата DX9WARE (Standoff 2)', 'allow_comments': False
    }
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
    await message.answer("Добро пожаловать в DX9WARE!", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    
    if callback_query.data == 'shop':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Android (APK)", callback_data="shop_apk"),
            types.InlineKeyboardButton("iOS", callback_data="shop_ios"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")
        )
        await bot.edit_message_text("Выберите платформу:", uid, callback_query.message.message_id, reply_markup=markup)

    elif callback_query.data.startswith('buy_'):
        plan = callback_query.data.replace('buy_', '')
        res = await create_invoice(PRICES[plan])
        if res['ok']:
            pay_url = res['result']['pay_url']
            inv_id = res['result']['invoice_id']
            markup = types.InlineKeyboardMarkup(row_width=1).add(
                types.InlineKeyboardButton("💳 Оплатить в Crypto Bot", url=pay_url),
                types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{inv_id}")
            )
            await bot.send_message(uid, f"Счет создан. После оплаты нажмите «Проверить»:", reply_markup=markup)

    elif callback_query.data.startswith('check_'):
        inv_id = callback_query.data.replace('check_', '')
        if await check_invoice(inv_id):
            new_key = extract_one_key()
            if new_key:
                active_users.add(uid)
                await bot.send_message(uid, f"✅ Оплата подтверждена!\n\nТвой ключ активации: `{new_key}`\n\nСкопируй его и нажми «Активировать ключ» в меню.", parse_mode="Markdown", reply_markup=get_main_menu(uid))
            else:
                await bot.send_message(uid, "❌ Оплата прошла, но ключи в базе закончились! Напиши админу: " + SUPPORT_URL)
        else:
            await bot.answer_callback_query(callback_query.id, "Оплата не найдена!", show_alert=True)

    elif callback_query.data == 'shop_apk':
        markup = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("Купить 7 дней (4$)", callback_data="buy_apk_7"),
            types.InlineKeyboardButton("Купить Месяц (8$)", callback_data="buy_apk_30"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="shop")
        )
        await bot.edit_message_text("Цены на APK:", uid, callback_query.message.message_id, reply_markup=markup)

    elif callback_query.data == 'shop_ios':
        markup = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("Купить 7 дней (6$)", callback_data="buy_ios_7"),
            types.InlineKeyboardButton("Купить Месяц (12$)", callback_data="buy_ios_30"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="shop")
        )
        await bot.edit_message_text("Цены на iOS:", uid, callback_query.message.message_id, reply_markup=markup)

    elif callback_query.data == 'back_main':
        await bot.edit_message_text("Выбери действие:", uid, callback_query.message.message_id, reply_markup=get_main_menu(uid))

    elif callback_query.data == 'activate':
        await bot.send_message(uid, "Отправь ключ активации:")
        
    elif callback_query.data == 'profile':
        has_key = "Активен ✅" if uid in active_users else "нет ключа ❌"
        await bot.send_message(uid, f"👤 ID: `{uid}`\n🔑 Ключ: {has_key}", parse_mode="Markdown")
        
    elif callback_query.data == 'get_files':
        if uid in active_users:
            if os.path.exists(FILE_NAME
    
