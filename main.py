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
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
START_ADMINS = [8137882829, 6332767725, 6848243673]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AdminStates(StatesGroup):
    # Промо
    p_code = State(); p_type = State(); p_value = State()
    # Рассылка
    broadcast = State()
    # Управление ключами
    remove_target = State()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # Таблица юзеров с поддержкой заморозки и скидок
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (id INTEGER PRIMARY KEY, username TEXT, active_until TEXT, 
                    current_key TEXT, is_blocked INTEGER DEFAULT 0, is_frozen INTEGER DEFAULT 0,
                    discount INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS keys 
                   (key TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0, status TEXT DEFAULT 'active')''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promos 
                   (code TEXT PRIMARY KEY, type TEXT, value INTEGER)''')
    conn.commit()
    conn.close()

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🔑 Активировать ключ", "🎁 Ввести промо", "🛒 Товары")
    return markup

def get_admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎁 Добавить промо", callback_data="adm_promo"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("❄️ Заморозка", callback_data="adm_freeze_list"),
        types.InlineKeyboardButton("📊 Проверить ключи", callback_data="adm_check_keys")
    )
    return markup

# --- ХЕНДЛЕРЫ ПОЛЬЗОВАТЕЛЯ ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(f"💜 **Welcome @{message.from_user.username} to Luci4DX9**", 
                         reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "👤 Профиль" or m.text == "/профиль")
async def view_profile(message: types.Message):
    conn = sqlite3.connect("database.db")
    u = conn.execute("SELECT * FROM users WHERE id=?", (message.from_user.id,)).fetchone()
    conn.close()
    
    uid = message.from_user.id
    if not u or not u[2]:
        text = f"👤 **Профиль**\n🆔 ID: `{uid}`\n🔑 Ключ: **не активирован**"
    else:
        text = f"👤 **Профиль**\n🆔 ID: `{uid}`\n🔑 Ключ: `{u[3]}`\n📅 Истекает: `{u[2]}`"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def show_shop(message: types.Message):
    shop_text = (
        "🛒 **Магазин DX9WARE**\n\n"
        "🤖 **APK (Android)**\n"
        "├ 7 days: 350⭐️ / 4 USDT\n"
        "└ Month: 700⭐️ / 8 USDT\n\n"
        "🍎 **IOS**\n"
        "├ 7 days: 400⭐️ / 6 USDT\n"
        "└ Month: 800⭐️ / 12 USDT\n\n"
        "⚠️ Комиссия на вас.\n"
        "📢 Канал: [Luci4DX9](https://t.me/Luci4DX9)\n"
        "💬 Отзывы: [cultDX9reviews](https://t.me/cultDX9reviews)\n\n"
        "Для оплаты звёздами пиши: @Luci4Ware\n"
        "Для крипты: @ware4"
    )
    await message.answer(shop_text, parse_mode="Markdown", disable_web_page_preview=True)

# --- АДМИН-КОМАНДЫ (ГРУППЫ И ОТВЕТЫ) ---
@dp.message_handler(commands=['Aprofile'])
async def admin_profile(message: types.Message):
    if not (message.from_user.id in START_ADMINS): return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    conn = sqlite3.connect("database.db")
    u = conn.execute("SELECT * FROM users WHERE id=?", (target.id,)).fetchone()
    conn.close()
    await message.answer(f"🛠 **Админ-инфо {target.mention}:**\nID: `{target.id}`\nКлюч: `{u[3] if u else 'N/A'}`", parse_mode="Markdown")

@dp.message_handler(commands=['remove_key'])
async def remove_key_cmd(message: types.Message):
    if not (message.from_user.id in START_ADMINS): return
    key_to_del = message.get_args()
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE users SET active_until=NULL, current_key=NULL WHERE current_key=?", (key_to_del,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Ключ `{key_to_del}` отвязан от всех пользователей.")

# --- ЛОГИКА ПРОМОКОДОВ ---
@dp.callback_query_handler(lambda c: c.data == "adm_promo")
async def adm_promo_start(call: types.CallbackQuery):
    await AdminStates.p_code.set()
    await call.message.answer("Введите текст промокода:")

@dp.message_handler(state=AdminStates.p_code)
async def adm_promo_type(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Скидка (%)", callback_data="pt_disc"),
        types.InlineKeyboardButton("Временный ключ", callback_data="pt_days")
    )
    await message.answer("На что будет промо?", reply_markup=markup)
    await AdminStates.p_type.set()

@dp.callback_query_handler(state=AdminStates.p_type)
async def adm_promo_val_step(call: types.CallbackQuery, state: FSMContext):
    p_type = 'discount' if call.data == "pt_disc" else 'days'
    await state.update_data(type=p_type)
    await call.message.answer("Введите значение (число):")
    await AdminStates.p_value.set()

@dp.message_handler(state=AdminStates.p_value)
async def adm_promo_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("database.db")
    conn.execute("INSERT INTO promos (code, type, value) VALUES (?, ?, ?)", 
                 (data['code'], data['type'], int(message.text)))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Промо `{data['code']}` создано!")
    await state.finish()

# --- РАССЫЛКА ---
@dp.callback_query_handler(lambda c: c.data == "adm_broadcast")
async def broadcast_start(call: types.CallbackQuery):
    await AdminStates.broadcast.set()
    await call.message.answer("Введите текст рассылки:")

@dp.message_handler(state=AdminStates.broadcast)
async def broadcast_exec(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("database.db")
    users = conn.execute("SELECT id FROM users").fetchall()
    conn.close()
    count = 0
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            count += 1
        except: continue
    await message.answer(f"📢 Рассылка завершена. Получили: {count} чел.")
    await state.finish()

# --- ПРОЧИЕ ФУНКЦИИ ---
@dp.message_handler(lambda m: m.text == "🎁 Ввести промо")
async def user_promo(message: types.Message):
    await message.answer("Введите ваш промокод:")

@dp.message_handler()
async def global_text_handler(message: types.Message):
    text = message.text.strip()
    uid = message.from_user.id
    
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    
    # Проверка на промокод
    cur.execute("SELECT * FROM promos WHERE code=?", (text,))
    p = cur.fetchone()
    if p:
        if p[1] == 'discount':
            cur.execute("UPDATE users SET discount=? WHERE id=?", (p[2], uid))
            await message.answer(f"✅ Активирована скидка {p[2]}% на следующую покупку!")
        else:
            end = (datetime.now() + timedelta(days=p[2])).strftime("%Y-%m-%d")
            cur.execute("UPDATE users SET active_until=? WHERE id=?", (end, uid))
            await message.answer(f"✅ Получен временный доступ до `{end}`")
        cur.execute("DELETE FROM promos WHERE code=?", (text,))
        conn.commit()
        conn.close()
        return

    # Логика активации ключа (как раньше)
    # ...
    conn.close()

async def on_startup(_):
    await bot.delete_webhook(drop_pending_updates=True)

if __name__ == '__main__':
    init_db()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
