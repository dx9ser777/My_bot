import logging
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN', '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU')
START_ADMINS = [8137882829, 6332767725, 6848243673]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, username TEXT, active_until TEXT, is_frozen INTEGER DEFAULT 0, 
                    discount INTEGER DEFAULT 0, current_key TEXT, is_blocked INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, type TEXT, value INTEGER)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY)''')
    for adm_id in START_ADMINS:
        cur.execute("INSERT OR IGNORE INTO admins (id) VALUES (?)", (adm_id,))
    conn.commit()
    conn.close()

class Form(StatesGroup):
    k_name = State(); k_days = State(); k_uses = State()
    p_name = State(); p_type = State(); p_val = State()
    mail = State()

def is_admin(uid):
    conn = sqlite3.connect("database.db")
    res = conn.execute("SELECT id FROM admins WHERE id=?", (uid,)).fetchone()
    conn.close()
    return res is not None

def get_u(uid, username=None):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, f"@{username}" if username else "N/A"))
    conn.commit()
    user = cur.execute("SELECT * @username FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user

# --- ОБРАБОТКА КОМАНД ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("🚀 **DX9WARE запущен!**\nОтправь мне ключ или промокод для активации.", parse_mode="Markdown")

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if is_admin(message.from_user.id):
        markup = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("➕ Ключ", callback_data="adm_add_key"),
            types.InlineKeyboardButton("🎁 Промо", callback_data="adm_add_promo")
        )
        await message.answer("🛠 Админ-панель:", reply_markup=markup)

# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК (С ДЕБАГОМ) ---
@dp.message_handler()
async def global_handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    
    # Если бот видит это сообщение, он ответит в логи Amvera
    logging.info(f"Получено сообщение от {uid}: {text}")

    u = get_u(uid, message.from_user.username)
    if u and u[6] == 1: # Поле is_blocked
        return await message.answer("🚫 Доступ заблокирован администратором.")

    # Логика проверки ключа/промо (как в прошлых версиях)
    # ... (код активации здесь) ...
    await message.answer(f"🔎 Проверяю код: `{text}`...", parse_mode="Markdown")

# --- ЗАПУСК ---
async def on_startup(dp):
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот успешно авторизован и готов к работе!")

if __name__ == '__main__':
    init_db()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
        
