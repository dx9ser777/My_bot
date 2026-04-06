import logging
import random
import string
import aiohttp
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
FILE_NAME = "cheat_file.zip" 

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

PRICES_CRYPTO = {
    "apk_7": 4, "apk_30": 8, "ios_7": 6, "ios_30": 12
}

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    return markup

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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

# --- ФАЙЛЫ ---
@dp.callback_query_handler(lambda c: c.data == "download_file", state='*')
async def send_cheat_file(callback: types.CallbackQuery):
    if os.path.exists(FILE_NAME):
        await callback.message.answer_document(InputFile(FILE_NAME), caption="🚀 **Твой файл DX9WARE готов!**")
    else:
        await callback.answer("⚠️ Файл не найден в системе!", show_alert=True)

# --- МАГАЗИН (АВТО-ПЛАТА) ---
@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_start(message: types.Message, state: FSMContext):
    await state.finish() # Сбрасываем любые зависшие действия
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios")
    )
    await message.answer("🛒 **Выбери платформу для покупки:**", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'), state='*')
async def shop_platform(callback: types.CallbackQuery):
    plat = callback.data.split('_')[1]
    is_ios = plat == "ios"
    text = f"💎 **Подписка DX9WARE ({'iOS' if is_ios else 'Android'})**\n\nВыбери период:"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(f"💳 7 дней — {'6$' if is_ios else '4$'}", callback_data=f"buy_{plat}_7"),
        InlineKeyboardButton(f"💳 30 дней — {'12$' if is_ios else '8$'}", callback_data=f"buy_{plat}_30"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_shop")
    )
    await callback.message.edit_text(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'), state='*')
async def process_buy(callback: types.CallbackQuery):
    plan = callback.data.replace('buy_', '')
    amount = PRICES_CRYPTO.get(plan, 8)
    res = await create_invoice(amount)
    if res['ok']:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔗 Оплатить через Crypto Bot", url=res['result']['pay_url']),
            InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{res['result']['invoice_id']}_{plan}")
        )
        await callback.message.answer(f"💰 **Счет на {amount} USDT создан!**\nПосле оплаты ключ придет автоматически.", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('check_'), state='*')
async def process_check(callback: types.CallbackQuery):
    data = callback.data.split('_')
    if await check_invoice(data[1]):
        new_key = gen_str()
        # Автоматически создаем ключ в базе при успешной оплате
        supabase.table("keys").insert({"key": new_key, "days": int(data[3]), "is_used": False}).execute()
        await callback.message.answer(f"🎉 **Оплата подтверждена!**\n\n🔑 Твой ключ: `{new_key}`\n\nНажми 'Активировать' в меню, чтобы начать.")
    else:
        await callback.answer("❌ Оплата еще не прошла.", show_alert=True)

# --- АДМИНКА (БЕЗ ЦЕНЗУРЫ) ---
@dp.message_handler(commands=['admin'], state='*')
async def admin_init(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.finish()
    await Form.waiting_days.set()
    await message.answer("⚙️ На сколько дней создать ключ? (0 = Lifetime)")

@dp.message_handler(state=Form.waiting_days)
async def admin_gen_key(message: types.Message, state: FSMContext):
    # Если ввели не число (например, нажали кнопку меню), отменяем создание
    if not message.text.isdigit():
        await state.finish()
        await message.answer("⚠️ Действие отменено (введено не число).", reply_markup=get_main_menu())
        return

    days = 99999 if message.text == "0" else int(message.text)
    key = gen_str()
    supabase.table("keys").insert({"key": key, "days": days, "is_used": False}).execute()
    await message.answer(f"✅ Ключ создан: `{key}`", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(commands=['akey', 'allkey', 'delkey'], state='*')
async def admin_tools(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("keys").select("*").execute()
    if not res.data: return await message.answer("База пуста.")
    
    text = "🔑 **Список ключей:**\n\n"
    for k in res.data:
        status = "✅ Исп." if k['is_used'] else "🆕 Нов."
        text += f"`{k['key']}` | {k['days']}д | {status}\n"
    await message.answer(text, parse_mode="Markdown")

# --- ПРОФИЛЬ И АКТИВАЦИЯ ---
@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until')
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file")) if sub and sub != "Нет ❌" else None
        await message.answer(f"👤 **Твой ID:** `{u['id']}`\n📅 **Подписка до:** `{sub or 'Нет ❌'}`", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 **Пришли свой ключ:**", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_activation)
async def act_logic(message: types.Message, state: FSMContext):
    # Если вместо ключа нажали кнопку или прислали ерунду
    if len(message.text) < 5:
        await state.finish()
        await message.answer("⚠️ Действие отменено.", reply_markup=get_main_menu())
        return

    key_in = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_in).execute()
    
    if res.data:
        k = res.data[0]
        if k['is_used'] or k.get('is_frozen'):
            await message.answer("❌ Ключ недействителен.", reply_markup=get_main_menu())
        else:
            days = k['days']
            exp = "Lifetime ♾" if days >= 90000 else (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            supabase.table("users").update({"active_until": exp, "current_key": key_in}).eq("id", message.from_user.id).execute()
            supabase.table("keys").update({"is_used": True, "used_by": message.from_user.id}).eq("key", key_in).execute()
            
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
            await message.answer(f"✅ **Успешно!** Доступ до: `{exp}`", reply_markup=get_main_menu())
            await message.answer("🚀 Теперь можно скачать файлы:", reply_markup=markup)
    else:
        await message.answer("❌ Неверный ключ!", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 Привет! Используй меню для работы.", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "back_to_shop", state='*')
async def back_shop(callback: types.CallbackQuery, state: FSMContext):
    await shop_start(callback.message, state)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                    
