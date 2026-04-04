import logging
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
# --- ИСПРАВЛЕННЫЙ ИМПОРТ ---
from aiocryptopay import AioCryptoPay 

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
START_ADMINS = [8137882829, 6332767725, 6848243673]
SUPPORT_USER = "@WareSupport"
PAYMENT_USER = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
REVIEWS_URL = "https://t.me/cultDX9reviews"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
# --- ИСПРАВЛЕННАЯ ИНИЦИАЛИЗАЦИЯ ---
crypto = AioCryptoPay(token=CRYPTO_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- СОСТОЯНИЯ (FSM) ---
class Form(StatesGroup):
    key_name = State()
    key_days = State()
    key_uses = State()
    delete_key_name = State()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, username TEXT, active_until TEXT, 
                    is_frozen INTEGER DEFAULT 0, current_key TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

def is_admin(uid): return uid in START_ADMINS

def get_u(uid, username="N/A"):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, f"@{username}"))
    conn.commit()
    user = cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user

# --- КЛАВИАТУРЫ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🔑 Активация", "🛒 Товары")
    markup.add("📢 Канал", "💬 Отзывы", "🆘 Поддержка")
    return markup

# --- КОМАНДЫ ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    get_u(message.from_user.id, message.from_user.username)
    await message.answer("🚀 Привет! Я бот DX9 WARE.", reply_markup=main_menu())

@dp.message_handler(commands=['admin'])
async def admin_main(message: types.Message):
    if not is_admin(message.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_key"),
        types.InlineKeyboardButton("🗑 Удалить ключ", callback_data="adm_del_key")
    )
    await message.answer("🛠 **Админ-панель**", reply_markup=markup, parse_mode="Markdown")

# --- ЛОГИКА ОПЛАТЫ (ОБНОВЛЕНА) ---
@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def shop(message: types.Message):
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🤖 Android (4$)", callback_data="pay_4"),
        types.InlineKeyboardButton("🍎 iOS (6$)", callback_data="pay_6")
    )
    await message.answer("🛒 Выбери платформу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def pay_link(call: types.CallbackQuery):
    amount = int(call.data.split('_')[1])
    # Используем новый метод для создания счета
    inv = await crypto.create_invoice(asset='USDT', amount=amount)
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💎 Оплатить", url=inv.bot_invoice_url))
    await call.message.answer(f"Чек на {amount}$ создан. После оплаты напиши {PAYMENT_USER}", reply_markup=markup)

# --- АДМИН-ФУНКЦИИ (КЛЮЧИ) ---
@dp.callback_query_handler(lambda c: c.data == "adm_key")
async def adm_k1(call: types.CallbackQuery):
    await Form.key_name.set()
    await call.message.answer("Введите название ключа:")

@dp.message_handler(state=Form.key_name)
async def adm_k2(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await Form.key_days.set()
    await message.answer("Кол-во дней подписки:")

@dp.message_handler(state=Form.key_days)
async def adm_k3(message: types.Message, state: FSMContext):
    await state.update_data(days=int(message.text))
    await Form.key_uses.set()
    await message.answer("Кол-во активаций:")

@dp.message_handler(state=Form.key_uses)
async def adm_k4(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO keys (key, days, max_uses) VALUES (?, ?, ?)", 
                 (data['name'], data['days'], int(message.text)))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Ключ `{data['name']}` создан!")
    await state.finish()

# --- ПРОФИЛЬ И АКТИВАЦИЯ ---
@dp.message_handler(lambda m: m.text == "👤 Профиль")
async def user_profile(message: types.Message):
    u = get_u(message.from_user.id, message.from_user.username)
    status = f"✅ До `{u[2]}`" if u[2] else "❌ Нет подписки"
    await message.answer(f"👤 **Профиль**\n🆔 ID: `{u[0]}`\nСтатус: {status}", parse_mode="Markdown")

@dp.message_handler()
async def check_activation(message: types.Message):
    text = message.text.strip()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    k = cur.fetchone()
    if k:
        if k[3] < k[2]:
            end = (datetime.now() + timedelta(days=k[1])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=?, current_key=? WHERE id=?", (end, text, message.from_user.id))
            cur.execute("UPDATE keys SET used_count=used_count+1 WHERE key=?", (text,))
            conn.commit()
            await message.answer(f"🚀 Подписка активирована до {end}!")
        else:
            await message.answer("❌ Этот ключ уже закончился.")
    conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
