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
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
START_ADMINS = [8137882829, 6332767725, 6848243673] 
PAYMENT_ADMIN = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"

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

init_db()

class Form(StatesGroup):
    k_name = State(); k_days = State(); k_uses = State()
    p_name = State(); p_type = State(); p_val = State()
    mail = State()

# --- ФУНКЦИИ ПРАВ ---
def is_admin(uid):
    conn = sqlite3.connect("database.db")
    res = conn.execute("SELECT id FROM admins WHERE id=?", (uid,)).fetchone()
    conn.close()
    return res is not None

def get_u(uid, username=None):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, f"@{username}" if username else "N/A"))
    if username: cur.execute("UPDATE users SET username=? WHERE id=?", (f"@{username}", uid))
    conn.commit()
    user = cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user

# --- МАГАЗИН (С УЧЕТОМ СКИДКИ) ---
def get_price(base_price, discount_pct):
    if discount_pct <= 0: return base_price
    return round(base_price * (1 - discount_pct / 100), 2)

# --- АДМИН-КОМАНДЫ (БЛОКИРОВКА / ВОЗВРАТ) ---
@dp.message_handler(commands=['remove_key'])
async def cmd_remove(message: types.Message):
    """Блокирует ключ и обнуляет подписку юзера"""
    if not is_admin(message.from_user.id): return
    args = message.get_args()
    if not args: return await message.reply("Использование: `/remove_key КЛЮЧ`")
    
    conn = sqlite3.connect("database.db")
    # Находим юзера с этим ключом и блокируем его
    conn.execute("UPDATE users SET active_until=NULL, current_key=NULL, is_blocked=1 WHERE current_key=?", (args,))
    conn.commit()
    conn.close()
    await message.reply(f"🚫 Ключ `{args}` заблокирован, пользователь лишен доступа и отправлен в бан.")

@dp.message_handler(commands=['back_key'])
async def cmd_back(message: types.Message):
    """Возвращает возможность использовать бота (разбан)"""
    if not is_admin(message.from_user.id): return
    args = message.get_args()
    if not args or not args.isdigit(): return await message.reply("Использование: `/back_key ID_ПОЛЬЗОВАТЕЛЯ`")
    
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE users SET is_blocked=0 WHERE id=?", (int(args),))
    conn.commit()
    conn.close()
    await message.reply(f"✅ Доступ для ID `{args}` восстановлен. Теперь он снова может активировать ключи.")

@dp.message_handler(commands=['Aprofile'])
async def cmd_aprofile(message: types.Message):
    """Профиль в ответ на сообщение"""
    if not is_admin(message.from_user.id): return
    if not message.reply_to_message: return await message.reply("Ответь на сообщение юзера!")
    
    target = message.reply_to_message.from_user
    u = get_u(target.id, target.username)
    
    status = "🚫 ЗАБАНЕН" if u[6] else ("✅ Активен" if u[2] else "❌ Нет подписки")
    text = (f"📑 **Админ-отчет:**\n"
            f"ID: `{u[0]}` | Юзер: {u[1]}\n"
            f"Статус: {status}\n"
            f"Ключ: `{u[5]}` | Скидка: {u[4]}%")
    await message.reply(text, parse_mode="Markdown")

# --- ПРОМОКОДЫ (СКИДКА И ДНИ) ---
@dp.callback_query_handler(lambda c: c.data == "adm_add_promo")
async def promo_step1(call: types.CallbackQuery):
    await Form.p_name.set()
    await call.message.answer("🎁 Введите текст промокода (например `SUMMER2026`):")

@dp.message_handler(state=Form.p_name)
async def promo_step2(message: types.Message, state: FSMContext):
    await state.update_data(pname=message.text.strip())
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("📉 Скидка (%)", callback_data="p_discount"),
        types.InlineKeyboardButton("⏳ Временный ключ (дни)", callback_data="p_days")
    )
    await Form.p_type.set()
    await message.answer("Выберите тип промокода:", reply_markup=markup)

@dp.callback_query_handler(state=Form.p_type)
async def promo_step3(call: types.CallbackQuery, state: FSMContext):
    p_type = "discount" if "discount" in call.data else "days"
    await state.update_data(ptype=p_type)
    await Form.p_val.set()
    txt = "На сколько процентов скидка? (Число 1-99):" if p_type == "discount" else "На сколько дней доступ?"
    await call.message.answer(txt)

@dp.message_handler(state=Form.p_val)
async def promo_step4(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Ошибка! Введи число.")
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO promos VALUES (?, ?, ?)", (data['pname'], data['ptype'], int(message.text)))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Промокод `{data['pname']}` успешно создан!")
    await state.finish()

# --- ЛОГИКА АКТИВАЦИИ ---
@dp.message_handler()
async def universal_handler(message: types.Message):
    uid = message.from_user.id
    u = get_u(uid, message.from_user.username)
    
    if u[6] == 1: # Проверка блокировки
        return await message.answer("🚫 Ты заблокирован в системе. Обратись к @ware4.")
    
    text = message.text.strip()
    if text.startswith('/'): return # Пропуск команд

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Проверка на ключ
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    k = cur.fetchone()
    if k and k[3] < k[2]:
        end = (datetime.now() + timedelta(days=k[1])).strftime("%Y-%m-%d")
        cur.execute("UPDATE users SET active_until=?, current_key=? WHERE id=?", (end, text, uid))
        cur.execute("UPDATE keys SET used_count=used_count+1 WHERE key=?", (text,))
        conn.commit()
        await message.answer(f"✅ Ключ на {k[1]}д активирован! До: {end}")
        return

    # Проверка на промо
    cur.execute("SELECT * FROM promos WHERE code=?", (text,))
    p = cur.fetchone()
    if p:
        if p[1] == 'days':
            end = (datetime.now() + timedelta(days=p[2])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=? WHERE id=?", (end, uid))
            await message.answer(f"🎁 Промо на {p[2]}д активировано!")
        else:
            cur.execute("UPDATE users SET discount=? WHERE id=?", (p[2], uid))
            await message.answer(f"📉 Твоя скидка {p[2]}% применена к магазину!")
        cur.execute("DELETE FROM promos WHERE code=?", (text,))
        conn.commit()
        return

    await message.answer("❌ Код не распознан.")

# Остальные функции (start, admin, shop) аналогичны прошлой версии...
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
