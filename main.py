import logging
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ОБРАБОТЧИКИ КОМАНД (СБРОС СОСТОЯНИЙ) ---

@dp.message_handler(commands=['start', 'admin', 'akey', 'delkey', 'clear_keys'], state='*')
async def global_commands(message: types.Message, state: FSMContext):
    # ПРИНУДИТЕЛЬНЫЙ СБРОС любого ожидания при вводе команды
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    cmd = message.get_command()

    if cmd == '/start':
        supabase.table("users").upsert({"id": message.from_user.id}).execute()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("👤 Профиль", "🔑 Активировать")
        await message.answer("👋 DX9WARE готов к работе.", reply_markup=markup)

    elif cmd == '/admin':
        if message.from_user.id != ADMIN_ID: return
        await Form.waiting_days.set()
        await message.answer("Введите количество дней для НОВОГО ключа (только цифру):")

    elif cmd == '/akey':
        if message.from_user.id != ADMIN_ID: return
        res = supabase.table("keys").select("*").execute()
        if not res.data: return await message.answer("Ключей нет.")
        text = "🔑 **КЛЮЧИ В БАЗЕ:**\n\n"
        for k in res.data:
            text += f"`{k['key']}` | {k['days']}д | Исп: {k['used_count']}\n"
        await message.answer(text, parse_mode="Markdown")

    elif cmd == '/delkey':
        if message.from_user.id != ADMIN_ID: return
        key = message.get_args().strip()
        if not key: return await message.answer("Пример: `/delkey DX9-123` ")
        supabase.table("keys").delete().eq("key", key).execute()
        supabase.table("username").delete().eq("password", key).execute()
        await message.answer(f"🗑 Удалено: `{key}`")

# --- ЛОГИКА СОЗДАНИЯ (ОЖИДАНИЕ ЧИСЛА) ---

@dp.message_handler(state=Form.waiting_days)
async def process_days(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Ошибка: Введи ЧИСЛО дней! Или /start для отмены.")
    
    days = int(message.text)
    new_key = gen_str()
    
    # Пишем в обе таблицы
    try:
        supabase.table("keys").insert({"key": new_key, "days": days, "is_active": True, "used_count": 0, "max_uses": 1}).execute()
        supabase.table("username").insert({"password": new_key}).execute()
        await message.answer(f"✅ Ключ создан и активен:\n`{new_key}`", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка базы: {e}")
    
    await state.finish()

# --- ЛОГИКА АКТИВАЦИИ ---

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_press(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("Введите ваш ключ:")

@dp.message_handler(state=Form.waiting_activation)
async def act_process(message: types.Message, state: FSMContext):
    key = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key).execute()
    
    if res.data:
        k = res.data[0]
        if k['used_count'] < k['max_uses']:
            exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
            supabase.table("users").update({"active_until": exp, "current_key": key}).eq("id", message.from_user.id).execute()
            supabase.table("keys").update({"used_count": k['used_count'] + 1}).eq("key", key).execute()
            await message.answer(f"✅ Активировано! До: `{exp}`", parse_mode="Markdown")
        else:
            await message.answer("❌ Ключ уже использован.")
    else:
        await message.answer("❌ Ключ не найден.")
    await state.finish()

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message):
    r = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    u = r.data[0] if r.data else {}
    await message.answer(f"👤 Твой ID: `{message.from_user.id}`\n📅 До: `{u.get('active_until') or 'Нет'}`", parse_mode="Markdown")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
