import logging
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiocryptopay import AioCryptoPay # Исправленный импорт

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
START_ADMINS = [8137882829, 6332767725, 6848243673] # Твой ID добавлен
SUPPORT_USER = "@WareSupport"
PAYMENT_USER = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
REVIEWS_URL = "https://t.me/cultDX9reviews"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
crypto = AioCryptoPay(token=CRYPTO_TOKEN) # Исправленная инициализация
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- СОСТОЯНИЯ (FSM) ---
class Form(StatesGroup):
    key_name = State(); key_days = State(); key_uses = State()
    edit_key_name = State(); edit_key_val = State()
    delete_key_name = State()
    promo_code = State(); promo_type = State(); promo_value = State()
    mail_text = State()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, username TEXT, active_until TEXT, 
                    is_frozen INTEGER DEFAULT 0, current_key TEXT, access_blocked INTEGER DEFAULT 0, 
                    discount INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, type TEXT, value TEXT)''')
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
    markup.add("👤 Профиль", "🔑 Активация", "🎁 Промо", "🛒 Товары")
    markup.add("📢 Канал", "💬 Отзывы", "🆘 Поддержка")
    return markup

# --- АДМИН-КОМАНДЫ ---
@dp.message_handler(commands=['freeze'])
async def cmd_freeze(message: types.Message):
    if not is_admin(message.from_user.id): return
    target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.get_args()
    if str(target_id).isdigit():
        conn = sqlite3.connect("database.db")
        conn.execute("UPDATE users SET is_frozen=1 WHERE id=?", (target_id,))
        conn.commit(); conn.close()
        await message.answer(f"❄️ Пользователь `{target_id}` заморожен.")

@dp.message_handler(commands=['unfreeze'])
async def cmd_unfreeze(message: types.Message):
    if not is_admin(message.from_user.id): return
    target_id = message.get_args()
    if target_id.isdigit():
        conn = sqlite3.connect("database.db")
        conn.execute("UPDATE users SET is_frozen=0 WHERE id=?", (target_id,))
        conn.commit(); conn.close()
        await message.answer(f"🔥 Пользователь `{target_id}` разморожен.")

@dp.message_handler(commands=['admin'])
async def admin_main(message: types.Message):
    if not is_admin(message.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_key"),
        types.InlineKeyboardButton("🗑 Удалить ключ", callback_data="adm_del_key"),
        types.InlineKeyboardButton("⚙️ Изменить лимит", callback_data="adm_limit"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="adm_check")
    )
    await message.answer("🛠 **Админ-панель**", reply_markup=markup, parse_mode="Markdown")

# --- ЛОГИКА КЛЮЧЕЙ ---
@dp.callback_query_handler(lambda c: c.data == "adm_key")
async def adm_k1(call: types.CallbackQuery):
    await Form.key_name.set(); await call.message.answer("Введите название ключа:")

@dp.message_handler(state=Form.key_name)
async def adm_k2(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip()); await Form.key_days.set()
    await message.answer("Кол-во дней подписки:")

@dp.message_handler(state=Form.key_days)
async def adm_k3(message: types.Message, state: FSMContext):
    await state.update_data(days=message.text); await Form.key_uses.set()
    await message.answer("Кол-во активаций (обычно 1):")

@dp.message_handler(state=Form.key_uses)
async def adm_k4(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO keys (key, days, max_uses) VALUES (?, ?, ?)", (data['name'], data['days'], message.text))
    conn.commit(); conn.close()
    await message.answer(f"✅ Ключ `{data['name']}` создан!"); await state.finish()

@dp.callback_query_handler(lambda c: c.data == "adm_del_key")
async def adm_d1(call: types.CallbackQuery):
    await Form.delete_key_name.set(); await call.message.answer("Какой ключ удалить?")

@dp.message_handler(state=Form.delete_key_name)
async def adm_d2(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM keys WHERE key=?", (message.text,))
    conn.execute("UPDATE users SET active_until=NULL, current_key=NULL WHERE current_key=?", (message.text,))
    conn.commit(); conn.close()
    await message.answer(f"🗑 Ключ `{message.text}` удален."); await state.finish()

# --- ОСНОВНЫЕ ФУНКЦИИ ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    get_u(message.from_user.id, message.from_user.username)
    await message.answer("🚀 Привет! Я бот DX9 WARE.", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль")
async def user_profile(message: types.Message):
    u = get_u(message.from_user.id, message.from_user.username)
    status = f"✅ До `{u[2]}`" if u[2] else "❌ Не активирован"
    if u[3]: status = "❄️ ЗАМОРОЖЕН"
    await message.answer(f"👤 **Профиль**\n🆔 ID: `{u[0]}`\n🔑 Ключ: `{u[4] if u[4] else 'нет'}`\nСтатус: {status}", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def shop(message: types.Message):
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🤖 Android (4$ / 8$)", callback_data="pay_4"),
        types.InlineKeyboardButton("🍎 iOS (6$ / 12$)", callback_data="pay_6")
    )
    await message.answer("🛒 Выбери платформу для покупки подписки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def pay_link(call: types.CallbackQuery):
    amount = int(call.data.split('_')[1])
    inv = await crypto.create_invoice(asset='USDT', amount=amount)
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💎 Оплатить", url=inv.pay_url))
    await call.message.answer(f"Чек на {amount}$ готов. После оплаты напиши {PAYMENT_USER}", reply_markup=markup)

@dp.message_handler()
async def activation_handler(message: types.Message):
    text = message.text.strip()
    uid = message.from_user.id
    conn = sqlite3.connect("database.db"); cur = conn.cursor()
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    k = cur.fetchone()
    if k:
        if k[3] < k[2]: # used_count < max_uses
            end = (datetime.now() + timedelta(days=k[1])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=?, current_key=? WHERE id=?", (end, text, uid))
            cur.execute("UPDATE keys SET used_count=used_count+1 WHERE key=?", (text,))
            conn.commit(); await message.answer(f"🚀 Активировано до {end}!")
        else:
            await message.answer("❌ Ключ уже использован.")
    conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
