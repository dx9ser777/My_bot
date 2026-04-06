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

# --- ОБРАБОТКА ФАЙЛОВ ---
@dp.callback_query_handler(lambda c: c.data == "download_file", state='*')
async def send_cheat_file(callback: types.CallbackQuery):
    if os.path.exists(FILE_NAME):
        await callback.message.answer_document(InputFile(FILE_NAME), caption="🚀 **Ваш файл DX9WARE готов!**")
    else:
        await callback.answer("⚠️ Файл не найден на сервере!", show_alert=True)

# --- АДМИН-КОМАНДЫ (НОВАЯ ЛОГИКА /akey и /allkey) ---

@dp.message_handler(commands=['admin'], state='*')
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await Form.waiting_days.set()
    await message.answer("⚙️ **На сколько дней ключ?** (0 = Lifetime)")

@dp.message_handler(state=Form.waiting_days)
async def admin_gen(message: types.Message, state: FSMContext):
    days = 99999 if message.text == "0" else int(message.text)
    key = gen_str()
    supabase.table("keys").insert({"key": key, "days": days, "is_used": False}).execute()
    await message.answer(f"✅ **Ключ создан:** `{key}`", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(commands=['akey', 'allkey', 'delkey', 'clearkey', 'freeze', 'unfreeze', 'aprofile'], state='*')
async def admin_commands(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.get_command()
    args = message.get_args()
    res = supabase.table("keys").select("*").execute()
    keys_data = res.data or []

    # /akey — БЕЗ цензуры (полные ключи)
    if cmd == '/akey':
        if not keys_data: return await message.answer("📭 База пуста.")
        text = "🔓 **ПОЛНЫЙ СПИСОК КЛЮЧЕЙ (БЕЗ ЦЕНЗУРЫ):**\n\n"
        for k in keys_data:
            status = f"✅ Используется (`{k['used_by']}`)" if k['is_used'] else "🆕 Свободен"
            frozen = " ❄️ (ЗАМОРОЖЕН)" if k.get('is_frozen') else ""
            text += f"• `{k['key']}` | {k['days']}д | {status}{frozen}\n"
        await message.answer(text, parse_mode="Markdown")

    # /allkey — С цензурой (скрытые)
    elif cmd == '/allkey':
        if not keys_data: return await message.answer("📭 База пуста.")
        text = "🛡 **СПИСОК КЛЮЧЕЙ (С ЦЕНЗУРОЙ):**\n\n"
        for k in keys_data:
            censored = f"{k['key'][:5]}***{k['key'][-3:]}"
            status = "✅ АКТИВИРОВАН" if k['is_used'] else "🆕 НЕ ИСПОЛЬЗОВАН"
            text += f"• `{censored}` | {k['days']}д | {status}\n"
        await message.answer(text, parse_mode="Markdown")

    elif cmd == '/delkey' and args:
        supabase.table("keys").delete().eq("key", args).execute()
        await message.answer(f"🗑 **Ключ `{args}` удален из базы.**")

    elif cmd == '/freeze' and args:
        supabase.table("keys").update({"is_frozen": True}).eq("key", args).execute()
        await message.answer(f"❄️ **Ключ `{args}` заморожен.**")

    elif cmd == '/unfreeze' and args:
        supabase.table("keys").update({"is_frozen": False}).eq("key", args).execute()
        await message.answer(f"🔥 **Ключ `{args}` разморожен.**")

# --- АКТИВАЦИЯ (ОБНОВЛЕНО: НЕ УДАЛЯЕМ КЛЮЧ, А МЕНЯЕМ СТАТУС) ---

@dp.message_handler(state=Form.waiting_activation)
async def act_logic(message: types.Message, state: FSMContext):
    key_input = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_input).execute()
    
    if res.data:
        k = res.data[0]
        if k['is_used']:
            await message.answer("❌ **Этот ключ уже был активирован кем-то другим!**", reply_markup=get_main_menu())
        elif k.get('is_frozen'):
            await message.answer("❄️ **Этот ключ заморожен админом.**", reply_markup=get_main_menu())
        else:
            days = k['days']
            exp = "Lifetime ♾" if days >= 90000 else (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            
            # Обновляем юзера
            supabase.table("users").update({"active_until": exp, "current_key": key_input}).eq("id", message.from_user.id).execute()
            # Обновляем ключ (ставим метку использования)
            supabase.table("keys").update({
                "is_used": True, 
                "used_by": message.from_user.id, 
                "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }).eq("key", key_input).execute()
            
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
            await message.answer(f"✅ **Успешно активировано!**\nДоступ до: `{exp}`", reply_markup=get_main_menu())
            await message.answer("📦 Теперь вам доступны файлы:", reply_markup=markup)
    else:
        await message.answer("❌ **Ошибка:** Ключ не найден в базе.", reply_markup=get_main_menu())
    await state.finish()

# --- СТАНДАРТНЫЕ ФУНКЦИИ ---

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until')
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file")) if sub and sub != "Нет" else None
        await message.answer(f"👤 **ПРОФИЛЬ**\n🆔 ID: `{u['id']}`\n📅 До: `{sub or 'Нет ❌'}`", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 **Введите ваш лицензионный ключ:**", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 **Добро пожаловать в DX9WARE!**", reply_markup=get_main_menu())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
