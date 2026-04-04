import logging
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiocryptopay import CryptoPay

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
START_ADMINS = [8137882829, 6332767725, 6848243673]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
crypto = CryptoPay(CRYPTO_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class Form(StatesGroup):
    promo_code = State(); promo_type = State(); promo_value = State()
    key_name = State(); key_days = State(); key_uses = State()
    edit_key_name = State(); edit_key_val = State() # Для смены лимита

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, username TEXT, active_until TEXT, 
                    is_frozen INTEGER DEFAULT 0, current_key TEXT, access_blocked INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, type TEXT, value TEXT)''')
    conn.commit()
    conn.close()

init_db()

def is_admin(uid): return uid in START_ADMINS

# --- КЛАВИАТУРЫ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🔑 Активация", "🎁 Промо", "🛒 Товары")
    markup.add("📢 Канал", "💬 Отзывы", "🆘 Поддержка")
    return markup

# --- АДМИН КОМАНДЫ ЗАМОРОЗКИ ---
@dp.message_handler(commands=['freeze'])
async def admin_freeze(message: types.Message):
    if not is_admin(message.from_user.id): return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.get_args()
        if args.isdigit(): target_id = int(args)
    
    if target_id:
        conn = sqlite3.connect("database.db")
        conn.execute("UPDATE users SET is_frozen = 1 WHERE id = ?", (target_id,))
        conn.commit(); conn.close()
        await message.answer(f"❄️ Пользователь `{target_id}` успешно заморожен.", parse_mode="Markdown")
    else:
        await message.answer("⚠️ Ответь на сообщение пользователя или введи его ID: `/freeze 12345`")

@dp.message_handler(commands=['unfreeze'])
async def admin_unfreeze(message: types.Message):
    if not is_admin(message.from_user.id): return
    args = message.get_args()
    if args.isdigit():
        conn = sqlite3.connect("database.db")
        conn.execute("UPDATE users SET is_frozen = 0 WHERE id = ?", (int(args),))
        conn.commit(); conn.close()
        await message.answer(f"🔥 Пользователь `{args}` разморожен.")

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'])
async def admin_main(message: types.Message):
    if not is_admin(message.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_key"),
        types.InlineKeyboardButton("⚙️ Изменить лимит", callback_data="adm_edit_limit"),
        types.InlineKeyboardButton("📊 Статистика ключей", callback_data="adm_check"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mail")
    )
    await message.answer("🛠 **Админ-меню**", reply_markup=markup, parse_mode="Markdown")

# Логика изменения лимита активаций
@dp.callback_query_handler(lambda c: c.data == "adm_edit_limit")
async def edit_limit_1(call: types.CallbackQuery):
    await Form.edit_key_name.set()
    await call.message.answer("⌨️ Введите название ключа, лимит которого хотите изменить:")

@dp.message_handler(state=Form.edit_key_name)
async def edit_limit_2(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await Form.edit_key_val.set()
    await message.answer("🔢 Введите новое кол-во активаций (число):")

@dp.message_handler(state=Form.edit_key_val)
async def edit_limit_3(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE keys SET max_uses = ? WHERE key = ?", (int(message.text), data['name']))
    conn.commit(); conn.close()
    await message.answer(f"✅ Лимит ключа `{data['name']}` изменен на {message.text}")
    await state.finish()

# --- ОБРАБОТКА АКТИВАЦИИ ---
@dp.message_handler()
async def global_handler(message: types.Message):
    text = message.text.strip()
    uid = message.from_user.id
    
    # Кнопки меню
    if text == "👤 Профиль":
        conn = sqlite3.connect("database.db")
        u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        conn.close()
        status = "❄️ ЗАМОРОЖЕН" if u and u[3] else (f"✅ До `{u[2]}`" if u and u[2] else "❌ Не активирован")
        await message.answer(f"👤 **Профиль**\nID: `{uid}`\nКлюч: `{u[4] if u else 'нет'}`\nСтатус: {status}", parse_mode="Markdown")
        return

    if text == "🛒 Товары":
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤖 Android", callback_data="buy_and"), types.InlineKeyboardButton("🍎 iOS", callback_data="buy_ios"))
        await message.answer("🛒 Выберите платформу:", reply_markup=markup); return

    if text == "🆘 Поддержка":
        await message.answer("🆘 Поддержка: @WareSupport"); return

    # Логика ключей
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM keys WHERE key=?", (text,))
    k = cur.fetchone()
    
    if k:
        # Проверка: не использовал ли уже КТО-ТО ДРУГОЙ этот ключ (если лимит 1)
        if k[3] >= k[2]:
            await message.answer("❌ Лимит активаций этого ключа исчерпан или он уже привязан к другому аккаунту.")
        else:
            # Активируем
            end = (datetime.now() + timedelta(days=k[1])).strftime("%Y-%m-%d")
            cur.execute("INSERT OR REPLACE INTO users (id, username, active_until, current_key, is_frozen) VALUES (?, ?, ?, ?, 0)", 
                        (uid, message.from_user.username, end, text))
            cur.execute("UPDATE keys SET used_count = used_count + 1 WHERE key = ?", (text,))
            conn.commit()
            await message.answer(f"🚀 **Успешно!**\nКлюч активирован до: `{end}`", parse_mode="Markdown")
    else:
        # Если это не команда и не ключ - молчим или даем подсказку
        if not text.startswith('/'):
            await message.answer("⚠️ Код не найден. Используйте кнопки меню.")
    
    conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
