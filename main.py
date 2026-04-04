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
                   (code TEXT PRIMARY KEY, type TEXT, value INTEGER)''') # type: 'days' или 'discount'
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY)''')
    for adm_id in START_ADMINS:
        cur.execute("INSERT OR IGNORE INTO admins (id) VALUES (?)", (adm_id,))
    conn.commit()
    conn.close()

init_db()

class Form(StatesGroup):
    k_name = State(); k_days = State(); k_uses = State() # Ключи
    p_name = State(); p_type = State(); p_val = State() # Промо
    mail = State() # Рассылка

# --- ПРОВЕРКА ПРАВ ---
def is_admin(uid):
    conn = sqlite3.connect("database.db")
    res = conn.execute("SELECT id FROM admins WHERE id=?", (uid,)).fetchone()
    conn.close()
    return res is not None

def update_user(uid, username):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, f"@{username}" if username else "N/A"))
    cur.execute("UPDATE users SET username=? WHERE id=?", (f"@{username}" if username else "N/A", uid))
    conn.commit()
    user = cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user

# --- КЛАВИАТУРЫ ---
def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Создать ключ", callback_data="adm_add_key"),
        types.InlineKeyboardButton("🎁 Создать промо", callback_data="adm_add_promo"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mail"),
        types.InlineKeyboardButton("🔍 Проверить ключи", callback_data="adm_check_keys")
    )
    return markup

# --- АДМИНКА: СОЗДАНИЕ ПРОМО ---
@dp.callback_query_handler(lambda c: c.data == "adm_add_promo")
async def p1(call: types.CallbackQuery):
    await Form.p_name.set()
    await call.message.answer("🎁 Введите текст промокода:")

@dp.message_handler(state=Form.p_name)
async def p2(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("📉 Скидка (%)", callback_data="type_discount"),
        types.InlineKeyboardButton("⏳ Временный ключ (дни)", callback_data="type_days")
    )
    await Form.p_type.set()
    await message.answer("На что будет промо?", reply_markup=markup)

@dp.callback_query_handler(state=Form.p_type)
async def p3(call: types.CallbackQuery, state: FSMContext):
    p_type = "discount" if "discount" in call.data else "days"
    await state.update_data(ptype=p_type)
    await Form.p_val.set()
    txt = "Введите % скидки (число):" if p_type == "discount" else "Введите кол-во дней ключа:"
    await call.message.answer(txt)

@dp.message_handler(state=Form.p_val)
async def p4(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO promos VALUES (?, ?, ?)", (data['name'], data['ptype'], int(message.text)))
    conn.commit()
    await message.answer(f"✅ Промокод `{data['name']}` создан!")
    await state.finish()

# --- АДМИНКА: РАССЫЛКА ---
@dp.callback_query_handler(lambda c: c.data == "adm_mail")
async def m1(call: types.CallbackQuery):
    await Form.mail.set()
    await call.message.answer("📢 Введите текст рассылки (или перешлите пост):")

@dp.message_handler(state=Form.mail, content_types=types.ContentTypes.ANY)
async def m2(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("database.db")
    users = conn.execute("SELECT id FROM users").fetchall()
    conn.close()
    count = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            count += 1
        except: pass
    await message.answer(f"✅ Рассылка завершена! Получили: {count} чел.")
    await state.finish()

# --- АДМИНКА: ПРОВЕРКА КЛЮЧЕЙ ---
@dp.callback_query_handler(lambda c: c.data == "adm_check_keys")
async def check_keys(call: types.CallbackQuery):
    conn = sqlite3.connect("database.db")
    users = conn.execute("SELECT id, username, current_key, active_until FROM users WHERE current_key IS NOT NULL").fetchall()
    conn.close()
    if not users: return await call.message.answer("Активных ключей нет.")
    
    text = "🔍 **Активные ключи:**\n\n"
    for u in users:
        text += f"👤 {u[1]} (`{u[0]}`)\n🔑 Ключ: `{u[2]}` | До: {u[3]}\n\n"
    await call.message.answer(text, parse_mode="Markdown")

# --- КОМАНДЫ ДЛЯ ГРУПП И ЧАТОВ ---
@dp.message_handler(commands=['remove_key'])
async def rem_key(message: types.Message):
    if not is_admin(message.from_user.id): return
    try:
        key = message.get_args()
        conn = sqlite3.connect("database.db")
        conn.execute("UPDATE users SET current_key=NULL, active_until=NULL WHERE current_key=?", (key,))
        conn.commit()
        await message.reply(f"✂️ Ключ `{key}` отвязан от пользователя.")
    except: await message.reply("Используйте: `/remove_key КЛЮЧ`")

@dp.message_handler(commands=['back_key'])
async def block_user(message: types.Message):
    if not is_admin(message.from_user.id): return
    uid = message.get_args()
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE users SET is_blocked=1 WHERE id=?", (uid,))
    conn.commit()
    await message.reply(f"🚫 Доступ для ID `{uid}` заблокирован до команды /unblock.")

@dp.message_handler(commands=['Aprofile'])
async def admin_prof(message: types.Message):
    if not is_admin(message.from_user.id): return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target: return await message.reply("Ответьте на сообщение юзера этой командой.")
    
    u = update_user(target.id, target.username)
    status = f"✅ Ключ: `{u[5]}` (До {u[2]})" if u[5] else "❌ Нет ключа"
    await message.reply(f"📝 **Инфо о юзере:**\nID: `{u[0]}`\nЮзер: {u[1]}\nСтатус: {status}", parse_mode="Markdown")

# --- ПРОФИЛЬ ЮЗЕРА ---
@dp.message_handler(commands=['profile'])
async def user_profile(message: types.Message):
    u = update_user(message.from_user.id, message.from_user.username)
    status = f"✅ До {u[2]}" if u[2] else "❌ Подписка неактивна"
    key_info = f"\n🔑 Твой ключ: `{u[5]}`" if u[5] else ""
    await message.reply(f"👤 **Профиль**\nID: `{u[0]}`\nСтатус: {status}{key_info}\nСкидка: {u[4]}%", parse_mode="Markdown")

# --- ЛОГИКА АКТИВАЦИИ (КЛЮЧ / ПРОМО) ---
@dp.message_handler()
async def main_handler(message: types.Message):
    uid = message.from_user.id
    u = update_user(uid, message.from_user.username)
    if u[6]: return # Если заблокирован
    
    text = message.text.strip()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Проверка ключа
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    k = cur.fetchone()
    if k:
        if k[3] < k[2]:
            end = (datetime.now() + timedelta(days=k[1])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=?, current_key=? WHERE id=?", (end, text, uid))
            cur.execute("UPDATE keys SET used_count=used_count+1 WHERE key=?", (text,))
            conn.commit()
            await message.answer(f"✅ Ключ на {k[1]}д активирован!")
            return

    # Проверка промо
    cur.execute("SELECT * FROM promos WHERE code=?", (text,))
    p = cur.fetchone()
    if p:
        if p[1] == 'days':
            end = (datetime.now() + timedelta(days=p[2])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=? WHERE id=?", (end, uid))
            await message.answer(f"🎁 Промо на {p[2]}д активировано!")
        else:
            cur.execute("UPDATE users SET discount=? WHERE id=?", (p[2], uid))
            await message.answer(f"📉 Твоя персональная скидка {p[2]}% активирована!")
        cur.execute("DELETE FROM promos WHERE code=?", (text,))
        conn.commit()
        return

    if not message.text.startswith('/'):
        await message.answer("❌ Неверный код.")

@dp.message_handler(commands=['admin'])
async def adm_start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("⚙️ Админ-панель:", reply_markup=admin_menu())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
