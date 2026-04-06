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

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    return markup

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message_handler(commands=['start', 'admin', 'akey', 'delkey', 'clear_keys'], state='*')
async def global_commands(message: types.Message, state: FSMContext):
    await state.finish()
    cmd = message.get_command()

    if cmd == '/start':
        # Сохраняем ID и Username
        u_name = message.from_user.username or "NoUser"
        supabase.table("users").upsert({"id": message.from_user.id, "username": u_name}).execute()
        await message.answer(f"👋 Привет, @{u_name}! DX9WARE готов.", reply_markup=get_main_menu())

    elif cmd == '/admin':
        if message.from_user.id != ADMIN_ID: return
        await Form.waiting_days.set()
        await message.answer("Введите число дней для ключа (только цифры):", reply_markup=types.ReplyKeyboardRemove())

    elif cmd == '/akey':
        if message.from_user.id != ADMIN_ID: return
        res = supabase.table("keys").select("*").execute()
        text = "🔑 **СПИСОК:**\n\n" + "\n".join([f"`{k['key']}` | {k['days']}д" for k in res.data]) if res.data else "Пусто"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu())

    elif cmd == '/delkey':
        if message.from_user.id != ADMIN_ID: return
        key = message.get_args().strip()
        if key:
            supabase.table("keys").delete().eq("key", key).execute()
            supabase.table("username").delete().eq("password", key).execute()
            await message.answer(f"🗑 Удален: `{key}`", reply_markup=get_main_menu())

# --- ЛОГИКА СОЗДАНИЯ ---

@dp.message_handler(state=Form.waiting_days)
async def process_days(message: types.Message, state: FSMContext):
    # Если нажал на кнопку меню вместо ввода числа
    if message.text in ["👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо"]:
        await state.finish()
        # Перенаправляем на нужную функцию вручную
        if message.text == "👤 Профиль": return await profile_view(message)
        if message.text == "🛒 Товары": return await shop(message)
        if message.text == "🔑 Активировать": return await act_press(message, state)
        return

    if not message.text.isdigit():
        return await message.answer("⚠️ Введи только ЧИСЛО или нажми /start для сброса.")
    
    days = int(message.text)
    new_key = gen_str()
    
    try:
        # Запись в базу
        supabase.table("keys").insert({"key": new_key, "days": days, "is_active": True, "used_count": 0, "max_uses": 1}).execute()
        supabase.table("username").insert({"password": new_key}).execute()
        await message.answer(f"✅ Ключ создан:\n`{new_key}`\nСрок: {days}д", parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка базы (Проверь RLS!): {e}", reply_markup=get_main_menu())
    
    await state.finish()

# --- АКТИВАЦИЯ ---

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_press(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("Введите ключ:", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_activation)
async def act_process(message: types.Message, state: FSMContext):
    key = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key).execute()
    
    if res.data:
        k = res.data[0]
        if k['used_count'] < k['max_uses']:
            exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
            supabase.table("users").update({
                "active_until": exp, 
                "current_key": key,
                "username": message.from_user.username or "NoUser"
            }).eq("id", message.from_user.id).execute()
            supabase.table("keys").update({"used_count": k['used_count'] + 1}).eq("key", key).execute()
            await message.answer(f"✅ Активировано до {exp}", reply_markup=get_main_menu())
        else:
            await message.answer("❌ Ключ использован.", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Ключ не найден.", reply_markup=get_main_menu())
    await state.finish()

# --- ПРОФИЛЬ И ТОВАРЫ ---

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message):
    r = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if r.data:
        u = r.data[0]
        await message.answer(f"👤 Юзер: @{u.get('username')}\n🆔 ID: `{u['id']}`\n📅 Срок: `{u.get('active_until') or 'Нет'}`", parse_mode="Markdown")
    else:
        await message.answer("Нажми /start для регистрации.")

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop(message: types.Message):
    await message.answer("🛒 Меню товаров доступно. Выбери подписку:")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                    
