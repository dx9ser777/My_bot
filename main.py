import logging
import sqlite3
import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ (Используем переменную из Amvera) ---
# На скриншоте у тебя BOT_TOKEN, берем его из системы
API_TOKEN = os.getenv('BOT_TOKEN', '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is')
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

# --- ФУНКЦИЯ ДЛЯ ЧИСТКИ ПРИ ЗАПУСКЕ ---
async def on_startup(dp):
    # ПРИНУДИТЕЛЬНО УДАЛЯЕМ ВЕБХУК И СТАРЫЕ ОБНОВЛЕНИЯ
    # Это решает проблему ConflictError на серверах
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook deleted and updates cleared.")

# (Тут должен быть остальной твой код с хендлерами /admin, /start и т.д.)

if __name__ == '__main__':
    init_db()
    # Добавляем on_startup для очистки конфликтов
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
