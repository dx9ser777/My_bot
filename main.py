import logging
import sqlite3
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_IDS = [8137882829, 6332767725, 6848243673]
PAYMENT_ADMIN = "@ware4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AdminStates(StatesGroup):
    wait_key_name = State()
    wait_key_days = State()
    wait_limit = State()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, username TEXT, active_until TEXT, 
                    is_frozen INTEGER DEFAULT 0, current_key TEXT, banned INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

def is_admin(uid): return uid in ADMIN_IDS

# --- API CRYPTO PAY (Твой рабочий метод) ---
async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': 'DX9WARE Sub'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

async def check_invoice(invoice_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        params = {'invoice_ids': str(invoice_id)}
        async with session.get('https://pay.crypt.bot/api/getInvoices', params=params, headers=headers) as resp:
            res = await resp.json()
            if res['ok'] and res['result']['items']:
                return res['result']['items'][0]['status'] == 'paid'
    return False

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_create"),
        types.InlineKeyboardButton("🗑 Удалить ключ", callback_data="adm_delete"),
        types.InlineKeyboardButton("⚙️ Изменить лимит", callback_data="adm_limit")
    )
    await message.answer("🛠 **Админ-панель**\n\nКоманды:\n/freeze [ID]\n/unfreeze [ID]\n/remove_key [Имя]\n/backKey [ID]", 
                         reply_markup=markup, parse_mode="Markdown")

# Логика создания ключа
@dp.callback_query_handler(lambda c: c.data == "adm_create")
async def adm_c1(call: types.CallbackQuery):
    await AdminStates.wait_key_name.set()
    await call.message.answer("Введите название нового ключа:")

@dp.message_handler(state=AdminStates.wait_key_name)
async def adm_c2(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await AdminStates.wait_key_days.set()
    await message.answer("На сколько дней ключ?")

@dp.message_handler(state=AdminStates.wait_key_days)
async def adm_c3(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO keys (key, days) VALUES (?, ?)", (data['name'], int(message.text)))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Ключ `{data['name']}` на {message.text} дн. создан!")
    await state.finish()

# --- КОМАНДЫ УПРАВЛЕНИЯ (FREEZE / REMOVE) ---
@dp.message_handler(commands=['freeze'])
async def cmd_freeze(message: types.Message):
    if not is_admin(message.from_user.id): return
    uid = message.get_args()
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE users SET is_frozen=1 WHERE id=?", (uid,))
    conn.commit(); conn.close()
    await message.answer(f"❄️ Пользователь {uid} заморожен.")

@dp.message_handler(commands=['unfreeze'])
async def cmd_unfreeze(message: types.Message):
    if not is_admin(message.from_user.id): return
    uid = message.get_args()
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE users SET is_frozen=0 WHERE id=?", (uid,))
    conn.commit(); conn.close()
    await message.answer(f"🔥 Пользователь {uid} разморожен.")

@dp.message_handler(commands=['remove_key', 'delkey'])
async def cmd_remove_key(message: types.Message):
    if not is_admin(message.from_user.id): return
    key_name = message.get_args()
    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM keys WHERE key=?", (key_name,))
    conn.execute("UPDATE users SET active_until=NULL, banned=1 WHERE current_key=?", (key_name,))
    conn.commit(); conn.close()
    await message.answer(f"🚫 Ключ `{key_name}` удален, связанные юзеры забанены.")

@dp.message_handler(commands=['backKey'])
async def cmd_back_key(message: types.Message):
    if not is_admin(message.from_user.id): return
    uid = message.get_args()
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE users SET banned=0 WHERE id=?", (uid,))
    conn.commit(); conn.close()
    await message.answer(f"✅ Доступ юзеру {uid} возвращен.")

# --- ПРОФИЛЬ И АКТИВАЦИЯ ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("👤 Профиль", "🛒 Товары")
    await message.answer("🚀 DX9WARE запущен!", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "👤 Профиль")
async def profile(message: types.Message):
    conn = sqlite3.connect("database.db")
    u = conn.execute("SELECT active_until, is_frozen, banned FROM users WHERE id=?", (message.from_user.id,)).fetchone()
    conn.close()
    if not u: status = "Нет подписки ❌"
    elif u[2]: status = "ЗАБАНЕН 🚫"
    elif u[1]: status = "ЗАМОРОЖЕН ❄️"
    else: status = f"Активен до {u[0]} ✅" if u[0] else "Нет подписки ❌"
    await message.answer(f"👤 Твой ID: `{message.from_user.id}`\nСтатус: {status}", parse_mode="Markdown")

@dp.message_handler()
async def handle_activation(message: types.Message):
    key_text = message.text.strip()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # Проверка ключа
    cur.execute("SELECT days, max_uses, used_count FROM keys WHERE key=?", (key_text,))
    k = cur.fetchone()
    if k and k[2] < k[1]:
        end_date = (datetime.now() + timedelta(days=k[0])).strftime("%Y-%m-%d")
        cur.execute("INSERT OR REPLACE INTO users (id, active_until, current_key) VALUES (?, ?, ?)", 
                    (message.from_user.id, end_date, key_text))
        cur.execute("UPDATE keys SET used_count=used_count+1 WHERE key=?", (key_text,))
        conn.commit()
        await message.answer(f"✅ Успешно! Подписка до: {end_date}")
    else:
        await message.answer("❌ Неверный ключ или лимит исчерпан.")
    conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
