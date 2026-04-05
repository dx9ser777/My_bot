import logging
import sqlite3
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # Таблица юзеров (+ заморозка и бан)
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, active_until TEXT, is_frozen INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0)''')
    # Таблица ключей (+ лимиты)
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0)''')
    # Таблица промокодов
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, days INTEGER, used_by TEXT DEFAULT '')''')
    conn.commit()
    conn.close()

init_db()

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ОБРАБОТЧИК /START ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары")
    markup.add("🔑 Активировать", "🎁 Промо")
    
    await message.answer("🚀 **DX9WARE запущен!**", reply_markup=markup, parse_mode="Markdown")

# --- ЛОГИКА ДЛЯ ЮЗЕРОВ ---
@dp.message_handler(lambda m: m.text == "👤 Профиль")
async def profile(message: types.Message):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT active_until, is_frozen, is_banned FROM users WHERE id=?", (message.from_user.id,))
    res = cur.fetchone()
    conn.close()

    if not res: status = "Нет подписки ❌"
    elif res[2]: status = "ЗАБАНЕН ⛔️"
    elif res[1]: status = "ЗАМОРОЖЕН ❄️"
    else: status = f"До {res[0]} ✅"

    await message.answer(f"👤 **ID:** `{message.from_user.id}`\n**Статус:** {status}", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🎁 Промо")
async def promo_btn(message: types.Message):
    await message.answer("Введите промокод:")

# --- АДМИН-ПАНЕЛЬ И ЗАЩИТА ---
@dp.message_handler(commands=['admin'])
async def admin_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(
            "Попытка кряка замечена\nВаша мать: шлюха ✅\nОтец: груз 200✅\nСемья: мертва✅\nКряк: НЕ РАБОТАЕТ❌"
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_gen_key"),
        types.InlineKeyboardButton("🎁 Создать промо", callback_data="adm_gen_promo"),
        types.InlineKeyboardButton("🗑 Удалить ключ", callback_data="adm_del_key"),
        types.InlineKeyboardButton("🔢 Изменить лимит", callback_data="adm_limit"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")
    )
    await message.answer("🛠 **Панель управления DX9WARE**", reply_markup=markup, parse_mode="Markdown")

# --- КОМАНДЫ УПРАВЛЕНИЯ (FREEZE, BAN ETC) ---

@dp.message_handler(commands=['freeze'])
async def freeze(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.get_args() or (message.reply_to_message.from_user.id if message.reply_to_message else None)
    if uid:
        conn = sqlite3.connect("database.db"); cur = conn.cursor()
        cur.execute("UPDATE users SET is_frozen = 1 WHERE id = ?", (uid,))
        conn.commit(); conn.close()
        await message.answer(f"❄️ Пользователь {uid} заморожен.")

@dp.message_handler(commands=['unfreeze'])
async def unfreeze(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.get_args()
    if uid:
        conn = sqlite3.connect("database.db"); cur = conn.cursor()
        cur.execute("UPDATE users SET is_frozen = 0 WHERE id = ?", (uid,))
        conn.commit(); conn.close()
        await message.answer(f"☀️ Пользователь {uid} разморожен.")

@dp.message_handler(commands=['remove_key', 'delkey'])
async def delete_key_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    key = message.get_args()
    conn = sqlite3.connect("database.db"); cur = conn.cursor()
    cur.execute("DELETE FROM keys WHERE key = ?", (key,))
    conn.commit(); conn.close()
    await message.answer(f"🗑 Ключ {key} удален из базы.")

@dp.message_handler(commands=['backKey'])
async def unban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.get_args()
    conn = sqlite3.connect("database.db"); cur = conn.cursor()
    cur.execute("UPDATE users SET is_banned = 0 WHERE id = ?", (uid,))
    conn.commit(); conn.close()
    await message.answer(f"✅ Доступ пользователю {uid} возвращен.")

# --- ОБРАБОТКА КНОПОК АДМИНКИ ---
@dp.callback_query_handler(lambda c: c.data.startswith('adm_'))
async def adm_callbacks(call: types.CallbackQuery):
    conn = sqlite3.connect("database.db"); cur = conn.cursor()
    
    if call.data == "adm_gen_key":
        key = gen_str()
        cur.execute("INSERT INTO keys (key, days) VALUES (?, ?)", (key, 30))
        await call.message.answer(f"🔑 Ключ (30д): `{key}`", parse_mode="Markdown")
    
    elif call.data == "adm_gen_promo":
        promo = gen_str("PR-", 6)
        cur.execute("INSERT INTO promos (code, days) VALUES (?, ?)", (promo, 7))
        await call.message.answer(f"🎁 Промокод (7д): `{promo}`", parse_mode="Markdown")

    elif call.data == "adm_stats":
        cur.execute("SELECT COUNT(*) FROM users")
        cnt = cur.fetchone()[0]
        await call.answer(f"Всего юзеров: {cnt}", show_alert=True)

    conn.commit(); conn.close()
    await call.answer()

# --- ОБРАБОТКА ТЕКСТА (АКТИВАЦИЯ) ---
@dp.message_handler()
async def global_text_handler(message: types.Message):
    if message.text in ["👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо"]:
        if message.text == "🔑 Активировать": await message.answer("Введите ваш ключ:")
        return

    txt = message.text.strip()
    conn = sqlite3.connect("database.db"); cur = conn.cursor()

    # 1. Проверка на промокод
    cur.execute("SELECT days, used_by FROM promos WHERE code = ?", (txt,))
    promo_data = cur.fetchone()
    if promo_data:
        if str(message.from_user.id) in promo_data[1]:
            await message.answer("❌ Вы уже использовали этот промокод.")
        else:
            new_until = (datetime.now() + timedelta(days=promo_data[0])).strftime("%Y-%m-%d")
            cur.execute("INSERT OR REPLACE INTO users (id, active_until) VALUES (?, ?)", (message.from_user.id, new_until))
            cur.execute("UPDATE promos SET used_by = used_by || ? WHERE code = ?", (f",{message.from_user.id}", txt))
            await message.answer(f"✅ Промокод активирован! Подписка до {new_until}")
        conn.commit(); conn.close(); return

    # 2. Проверка на ключ
    cur.execute("SELECT days, max_uses, used_count FROM keys WHERE key = ?", (txt,))
    key_data = cur.fetchone()
    if key_data and key_data[2] > key_data[1]:
        expire = (datetime.now() + timedelta(days=key_data[0])).strftime("%Y-%m-%d")
        cur.execute("INSERT OR REPLACE INTO users (id, active_until) VALUES (?, ?)", (message.from_user.id, expire))
        cur.execute("UPDATE keys SET used_count = used_count + 1 WHERE key = ?", (txt,))
        await message.answer(f"✅ Ключ активирован! Подписка до {expire}")
    else:
        # Если это не кнопка, не ключ и не промо — игнорим или пишем ошибку
        if not txt.startswith('/'):
            await message.answer("❌ Объект не найден или лимит исчерпан.")

    conn.commit(); conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
