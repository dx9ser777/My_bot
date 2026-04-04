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
# Твои доверенные админы
START_ADMINS = [8137882829, 6332767725, 6848243673] 

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
                    freezes_left INTEGER DEFAULT 2)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, days INTEGER)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY)''')
    
    # Добавляем начальных админов
    for adm_id in START_ADMINS:
        cur.execute("INSERT OR IGNORE INTO admins (id) VALUES (?)", (adm_id,))
    conn.commit()
    conn.close()

init_db()

# --- СОСТОЯНИЯ (FSM) ---
class Form(StatesGroup):
    # Ключи
    waiting_for_key_name = State()
    waiting_for_key_days = State()
    waiting_for_key_uses = State()
    # Промо
    waiting_for_promo_name = State()
    waiting_for_promo_days = State()
    # Админы
    waiting_for_new_admin = State()
    # Рассылка
    waiting_for_mail = State()

# --- ПРОВЕРКА ПРАВ ---
def is_admin(uid):
    conn = sqlite3.connect("database.db")
    res = conn.execute("SELECT id FROM admins WHERE id=?", (uid,)).fetchone()
    conn.close()
    return res is not None

def get_user(uid):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
    user = cur.fetchone()
    if not user:
        cur.execute("INSERT INTO users (id) VALUES (?)", (uid,))
        conn.commit()
        user = (uid, None, 0, 2)
    conn.close()
    return user

# --- КЛАВИАТУРЫ ---
def main_menu(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    user = get_user(uid)
    markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
               types.InlineKeyboardButton("🛒 Товары", callback_data="shop"))
    
    if user[1]: # Если есть подписка
        txt = "🔥 Разморозить" if user[2] else "❄️ Заморозить (2/нед)"
        markup.add(types.InlineKeyboardButton(txt, callback_data="toggle_freeze"))
        if not user[2]:
            markup.add(types.InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    else:
        markup.add(types.InlineKeyboardButton("🔑 Активировать ключ", callback_data="activate"))
        
    markup.add(types.InlineKeyboardButton("🎁 Ввести промо", callback_data="promo_input"),
               types.InlineKeyboardButton("📢 Канал", url=CHANNEL_URL))
    return markup

def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Создать ключ", callback_data="adm_add_key"),
        types.InlineKeyboardButton("🎁 Создать промо", callback_data="adm_add_promo"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mail"),
        types.InlineKeyboardButton("👤 Добавить админа", callback_data="adm_add_admin")
    )
    return markup

# --- ОБРАБОТКА КОМАНД ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать в **DX9WARE**!", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")

@dp.message_handler(commands=['admin'])
async def admin_cmd(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("🛠 **Панель управления**", reply_markup=admin_menu(), parse_mode="Markdown")
    else:
        await message.answer("❌ Доступ запрещен.")

# --- ПОШАГОВАЯ АДМИНКА (ДОБАВЛЕНИЕ КЛЮЧА) ---
@dp.callback_query_handler(lambda c: c.data == "adm_add_key")
async def adm_k1(call: types.CallbackQuery):
    await Form.waiting_for_key_name.set()
    await call.message.answer("⌨️ Напишите ключ (например `DX9-PREMIUM`):")

@dp.message_handler(state=Form.waiting_for_key_name)
async def adm_k2(message: types.Message, state: FSMContext):
    await state.update_data(k_name=message.text.strip())
    await Form.waiting_for_key_days.set()
    await message.answer("⏳ Срок действия (в днях):")

@dp.message_handler(state=Form.waiting_for_key_days)
async def adm_k3(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    await state.update_data(k_days=int(message.text))
    await Form.waiting_for_key_uses.set()
    await message.answer("👥 Сколько человек может активировать?")

@dp.message_handler(state=Form.waiting_for_key_uses)
async def adm_k4(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO keys VALUES (?, ?, ?, 0)", (data['k_name'], data['k_days'], int(message.text)))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Ключ `{data['k_name']}` на {data['k_days']}д успешно добавлен!")
    await state.finish()

# --- ЗАМОРОЗКА ---
@dp.callback_query_handler(lambda c: c.data == "toggle_freeze")
async def user_freeze(call: types.CallbackQuery):
    uid = call.from_user.id
    user = get_user(uid)
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    
    if user[2] == 0: # Замораживаем
        if user[3] > 0:
            cur.execute("UPDATE users SET is_frozen=1, freezes_left=freezes_left-1 WHERE id=?", (uid,))
            await call.message.answer("❄️ **Заморожено.** Использование ключа приостановлено.", parse_mode="Markdown")
        else:
            await call.message.answer("❌ Лимит заморозок (2 в неделю) исчерпан.")
    else: # Размораживаем
        cur.execute("UPDATE users SET is_frozen=0 WHERE id=?", (uid,))
        await call.message.answer("🔥 **Разморожено!** Можешь скачивать файлы.", parse_mode="Markdown")
    
    conn.commit()
    conn.close()
    await call.message.edit_reply_markup(reply_markup=main_menu(uid))

# --- ПРОФИЛЬ ---
@dp.callback_query_handler(lambda c: c.data == "profile")
async def profile_call(call: types.CallbackQuery):
    u = get_user(call.from_user.id)
    status = f"✅ До {u[1]}" if u[1] else "❌ Нет подписки"
    if u[2]: status = "❄️ ЗАМОРОЖЕН"
    text = (
        f"👤 **Твой профиль**\n"
        f"├ ID: `{u[0]}`\n"
        f"├ Статус: {status}\n"
        f"└ Заморозок осталось: {u[3]} ❄️"
    )
    await call.message.answer(text, parse_mode="Markdown")

# --- ЛОГИКА ВВОДА КЛЮЧА / ПРОМО ---
@dp.callback_query_handler(lambda c: c.data == "activate" or c.data == "promo_input")
async def ask_input(call: types.CallbackQuery):
    await call.message.answer("⌨️ Введи свой ключ или промокод:")

@dp.message_handler()
async def check_key_promo(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # 1. Проверка ключей
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    k = cur.fetchone()
    if k:
        if k[3] < k[2]:
            expire = (datetime.now() + timedelta(days=k[1])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=?, is_frozen=0 WHERE id=?", (expire, uid))
            cur.execute("UPDATE keys SET used_count = used_count + 1 WHERE key=?", (text,))
            conn.commit()
            await message.answer(f"🚀 **Успех!**\nКлюч активирован на {k[1]} дней.\nДоступ до: `{expire}`", parse_mode="Markdown")
            conn.close()
            return
        else:
            await message.answer("❌ Лимит активаций этого ключа исчерпан.")
            conn.close()
            return

    # 2. Проверка промокодов
    cur.execute("SELECT * FROM promos WHERE code=?", (text,))
    p = cur.fetchone()
    if p:
        expire = (datetime.now() + timedelta(days=p[1])).strftime("%Y-%m-%d")
        cur.execute("UPDATE users SET active_until=?, is_frozen=0 WHERE id=?", (expire, uid))
        cur.execute("DELETE FROM promos WHERE code=?", (text,)) # Промо разовое
        conn.commit()
        await message.answer(f"🎁 **Промокод активирован!**\nДобавлено {p[1]} дней подписки.", parse_mode="Markdown")
        conn.close()
        return

    await message.answer("❌ Ключ или промокод не найден.")
    conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                 
