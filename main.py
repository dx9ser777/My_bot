import logging
import asyncio
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
ADMIN_ID = 6848243673 
PAYMENT_ADMIN = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, active_until TEXT, is_frozen INTEGER DEFAULT 0, 
                    freezes_left INTEGER DEFAULT 2, last_freeze_week TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, days INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- СОСТОЯНИЯ (FSM) ---
class Form(StatesGroup):
    # Для ключей
    waiting_for_key_name = State()
    waiting_for_key_days = State()
    waiting_for_key_uses = State()
    # Для промо
    waiting_for_promo_name = State()
    waiting_for_promo_days = State()
    # Для рассылки
    waiting_for_mail = State()
    # Для админ-заморозки
    waiting_for_user_id = State()

# --- ФУНКЦИИ БАЗЫ ---
def get_user(uid):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
    user = cur.fetchone()
    if not user:
        cur.execute("INSERT INTO users (id) VALUES (?)", (uid,))
        conn.commit()
        user = (uid, None, 0, 2, None)
    conn.close()
    return user

# --- КЛАВИАТУРЫ ---
def main_menu(uid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    user = get_user(uid)
    markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
               types.InlineKeyboardButton("🛒 Товары", callback_data="shop"))
    if user[1]: # Если есть подписка
        txt = "🔥 Разморозить" if user[2] else "❄️ Заморозить (2/нед)"
        markup.add(types.InlineKeyboardButton(txt, callback_data="toggle_freeze"))
        if not user[2]: markup.add(types.InlineKeyboardButton("📁 Файлы", callback_data="get_files"))
    else:
        markup.add(types.InlineKeyboardButton("🔑 Активация", callback_data="activate"))
    markup.add(types.InlineKeyboardButton("🎁 Промокод", callback_data="promo"),
               types.InlineKeyboardButton("📢 Канал", url=CHANNEL_URL))
    return markup

def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Создать ключ", callback_data="adm_add_key"),
        types.InlineKeyboardButton("🎁 Создать промо", callback_data="adm_add_promo"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mail"),
        types.InlineKeyboardButton("🥶 Заморозка (Админ)", callback_data="adm_freeze_user")
    )
    return markup

# --- ХЕНДЛЕРЫ ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 DX9WARE приветствует тебя!", reply_markup=main_menu(message.from_user.id))

@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Панель управления:", reply_markup=admin_menu())

# --- ПОШАГОВОЕ СОЗДАНИЕ КЛЮЧА ---
@dp.callback_query_handler(lambda c: c.data == "adm_add_key")
async def adm_k1(call: types.CallbackQuery):
    await Form.waiting_for_key_name.set()
    await call.message.answer("1️⃣ Введите название ключа (например, `DX9-ABC`):")

@dp.message_handler(state=Form.waiting_for_key_name)
async def adm_k2(message: types.Message, state: FSMContext):
    await state.update_data(k_name=message.text)
    await Form.waiting_for_key_days.set()
    await message.answer("2️⃣ На сколько дней ключ? (Введите число):")

@dp.message_handler(state=Form.waiting_for_key_days)
async def adm_k3(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    await state.update_data(k_days=int(message.text))
    await Form.waiting_for_key_uses.set()
    await message.answer("3️⃣ Сколько человек могут активировать? (Число):")

@dp.message_handler(state=Form.waiting_for_key_uses)
async def adm_k4(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO keys VALUES (?, ?, ?, 0)", (data['k_name'], data['k_days'], int(message.text)))
    conn.commit()
    await message.answer(f"✅ Ключ `{data['k_name']}` на {data['k_days']}д успешно создан!")
    await state.finish()

# --- ЛОГИКА ЗАМОРОЗКИ ЮЗЕРОМ ---
@dp.callback_query_handler(lambda c: c.data == "toggle_freeze")
async def user_freeze(call: types.CallbackQuery):
    uid = call.from_user.id
    user = get_user(uid)
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    
    if user[2] == 0: # Если не заморожен -> замораживаем
        if user[3] > 0:
            cur.execute("UPDATE users SET is_frozen=1, freezes_left=freezes_left-1 WHERE id=?", (uid,))
            await call.message.answer("❄️ Ключ заморожен. Доступ к файлам закрыт.")
        else:
            await call.message.answer("❌ Лимит заморозок на этой неделе исчерпан.")
    else: # Если заморожен -> размораживаем
        cur.execute("UPDATE users SET is_frozen=0 WHERE id=?", (uid,))
        await call.message.answer("🔥 Ключ разморожен! Приятной игры.")
    
    conn.commit()
    await call.message.edit_reply_markup(reply_markup=main_menu(uid))

# --- АКТИВАЦИЯ ---
@dp.callback_query_handler(lambda c: c.data == "activate")
async def act_btn(call: types.CallbackQuery):
    await call.message.answer("⌨️ Отправь ключ доступа:")

@dp.message_handler(lambda message: not message.text.startswith('/'))
async def handle_all(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    text = message.text.strip()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Проверка ключа
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    key_data = cur.fetchone()
    if key_data:
        if key_data[3] < key_data[2]: # uses < max_uses
            expire = (datetime.now() + timedelta(days=key_data[1])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=? WHERE id=?", (expire, uid))
            cur.execute("UPDATE keys SET used_count=used_count+1 WHERE key=?", (text,))
            conn.commit()
            await message.answer(f"✅ Ключ выдан на {key_data[1]} дней!\nПодписка до: {expire}")
            return
        else: await message.answer("❌ Лимит активаций ключа исчерпан.")

    # Проверка промо
    cur.execute("SELECT * FROM promos WHERE code=?", (text,))
    promo_data = cur.fetchone()
    if promo_data:
        expire = (datetime.now() + timedelta(days=promo_data[1])).strftime("%Y-%m-%d")
        cur.execute("UPDATE users SET active_until=? WHERE id=?", (expire, uid))
        cur.execute("DELETE FROM promos WHERE code=?", (text,))
        conn.commit()
        await message.answer(f"🎁 Промокод на {promo_data[1]}д активирован!")
        return

    await message.answer("❌ Ключ или промокод не найден.")

# --- ПРОФИЛЬ И МАГАЗИН ---
@dp.callback_query_handler(lambda c: c.data == "profile")
async def prof(call: types.CallbackQuery):
    u = get_user(call.from_user.id)
    status = f"✅ До {u[1]}" if u[1] else "❌ Нет подписки"
    if u[2]: status = "❄️ ЗАМОРОЖЕН"
    await call.message.answer(f"👤 ID: `{u[0]}`\nСтатус: {status}\nЗаморозок осталось: {u[3]}", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "shop")
async def shop(call: types.CallbackQuery):
    await call.message.answer(f"🍏 Android: 7д-350⭐ / 30д-700⭐\n🍎 iOS: 7д-400⭐ / 30д-800⭐\nПокупка: {PAYMENT_ADMIN}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
