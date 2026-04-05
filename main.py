import logging
import sqlite3
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 # Твой ID со скриншота

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- РАБОТА С БАЗОЙ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, active_until TEXT, current_key TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER, used_count INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def gen_key(length=12):
    return "DX9-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары")
    markup.add("🔑 Активировать")
    
    if message.from_user.id == ADMIN_ID:
        markup.add("⚙️ Админ-панель")
        
    await message.answer("🚀 **DX9WARE запущен!**\nИспользуйте меню ниже для навигации.", 
                         reply_markup=markup, parse_mode="Markdown")

# --- ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text == "👤 Профиль")
async def profile_handler(message: types.Message):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT active_until FROM users WHERE id=?", (message.from_user.id,))
    res = cur.fetchone()
    conn.close()
    
    status = res[0] if res else "Нет подписки ❌"
    await message.answer(f"👤 **Твой ID:** `{message.from_user.id}`\n**Статус:** {status}", parse_mode="Markdown")

# --- ТОВАРЫ ---
@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def shop_handler(message: types.Message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔥 30 дней — 5 USDT", callback_data="buy_30"))
    markup.add(types.InlineKeyboardButton("💎 Навсегда — 15 USDT", callback_data="buy_life"))
    await message.answer("Выберите тарифный план:", reply_markup=markup)

# --- АДМИН-ПАНЕЛЬ ---
@dp.message_handler(lambda m: m.text == "⚙️ Админ-панель")
async def admin_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Создать ключ (30 дней)", callback_data="admin_gen_30"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    )
    await message.answer("🛠 Панель администратора:", reply_markup=markup)

# --- ОБРАБОТКА CALLBACK (КНОПОК) ---
@dp.callback_query_handler(lambda c: c.data.startswith('admin_gen_'))
async def process_gen_key(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    
    new_key = gen_key()
    days = 30 if "30" in call.data else 9999
    
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO keys VALUES (?, ?, ?, ?)", (new_key, days, 1, 0))
    conn.commit()
    conn.close()
    
    await call.message.answer(f"✅ Сгенерирован ключ на {days} дн:\n`{new_key}`", parse_mode="Markdown")
    await call.answer()

# --- АКТИВАЦИЯ КЛЮЧЕЙ (В САМОМ КОНЦЕ) ---
@dp.message_handler(lambda m: m.text == "🔑 Активировать")
async def ask_key(message: types.Message):
    await message.answer("Отправьте ваш ключ ответным сообщением.")

@dp.message_handler()
async def check_key(message: types.Message):
    # Игнорируем кнопки меню
    if message.text in ["👤 Профиль", "🛒 Товары", "🔑 Активировать", "⚙️ Админ-панель"]:
        return

    key_text = message.text.strip()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    
    cur.execute("SELECT days, max_uses, used_count FROM keys WHERE key=?", (key_text,))
    res = cur.fetchone()
    
    if res and res[2] < res[1]:
        days = res[0]
        expire_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        cur.execute("INSERT OR REPLACE INTO users (id, active_until, current_key) VALUES (?, ?, ?)", 
                    (message.from_user.id, expire_date, key_text))
        cur.execute("UPDATE keys SET used_count = used_count + 1 WHERE key=?", (key_text,))
        conn.commit()
        await message.answer(f"✅ Подписка активирована до: {expire_date}")
    else:
        await message.answer("❌ Неверный ключ или он уже использован.")
    
    conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
