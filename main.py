import logging
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    return markup

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- АДМИН КОМАНДЫ (НОВЫЕ) ---

@dp.message_handler(commands=['aprofile'], state='*')
async def admin_user_profile(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    target_id = None
    args = message.get_args()

    # 1. Если это ответ на сообщение
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    # 2. Если передан аргумент (ID или ник)
    elif args:
        if args.isdigit():
            target_id = int(args)
        else:
            # Поиск по username в базе
            clean_nick = args.replace("@", "")
            res = supabase.table("users").select("*").eq("username", clean_nick).execute()
            if res.data: target_id = res.data[0]['id']

    if not target_id:
        return await message.answer("⚠️ Укажите ID, ник или ответьте на сообщение пользователя.")

    res = supabase.table("users").select("*").eq("id", target_id).execute()
    if not res.data:
        return await message.answer(f"❌ Пользователь `{target_id}` не найден в базе.")

    u = res.data[0]
    sub = u.get('active_until', 'Нет')
    key = u.get('current_key', 'Не использовал')
    
    await message.answer(
        f"📋 **ДАННЫЕ ЮЗЕРА**\n\n"
        f"🆔 ID: `{u['id']}`\n"
        f"👤 Nick: @{u.get('username', 'N/A')}\n"
        f"🔑 Ключ: `{key}`\n"
        f"📅 До: `{sub}`", parse_mode="Markdown"
    )

@dp.message_handler(commands=['allkey'])
async def all_keys_censored(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("keys").select("*").execute()
    if not res.data: return await message.answer("Ключей нет.")

    text = "🔑 **ВСЕ КЛЮЧИ (ЦЕНЗУРА):**\n\n"
    for k in res.data:
        raw_key = k['key']
        # Показываем только начало и конец ключа для безопасности
        censored = f"{raw_key[:7]}...{raw_key[-2:]}"
        days = "Lifetime" if k['days'] >= 90000 else f"{k['days']}д"
        text += f"`{censored}` | {days}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['clearkey'])
async def clear_all_keys(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        # Удаляем всё из таблиц ключей и лоадера
        supabase.table("keys").delete().neq("key", "0").execute() 
        supabase.table("username").delete().neq("password", "0").execute()
        await message.answer("🗑 Все ключи успешно удалены из базы данных.")
    except Exception as e:
        await message.answer(f"❌ Ошибка очистки: {e}")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ (ТОВАРЫ, АДМИН, АКТИВАЦИЯ) ---

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_start(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="buy_android"),
        InlineKeyboardButton("iOS 🍎", callback_data="buy_ios")
    )
    await message.answer("Выберите вашу платформу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def platform_selected(callback: types.CallbackQuery):
    platform = "Android" if "android" in callback.data else "iOS"
    is_ios = "ios" in callback.data
    
    stars_7 = "400⭐️" if is_ios else "350⭐️"
    stars_month = "800⭐️" if is_ios else "700⭐️"
    crypto_7 = "6 USDT" if is_ios else "4 USDT"
    crypto_month = "12 USDT" if is_ios else "8 USDT"

    price_text = (
        f"💳 **DX9WARE for {platform}**\n\n"
        f"**Stars:**\n7 days — {stars_7}\nMonth — {stars_month}\n\n"
        f"**Crypto:**\n7 days — {crypto_7}\nMonth — {crypto_month}\n\n"
        f"📩 Покупка: @ware4"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Оплатить Crypto (Авто)", url="https://t.me/CryptoBot?start=pay"))
    await callback.message.edit_text(price_text, reply_markup=markup, parse_mode="Markdown")

@dp.message_handler(commands=['admin'], state='*')
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.finish()
    await Form.waiting_days.set()
    await message.answer("Срок ключа? (0 - Lifetime)", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_days)
async def create_key_logic(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    days = 99999 if message.text == "0" else int(message.text)
    new_key = gen_str()
    supabase.table("keys").insert({"key": new_key, "days": days}).execute()
    try: supabase.table("username").insert({"password": new_key}).execute()
    except: pass
    await message.answer(f"✅ Ключ: `{new_key}`", parse_mode="Markdown", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def activate_btn(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("Введите ключ:", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_activation)
async def act_logic(message: types.Message, state: FSMContext):
    key = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key).execute()
    if res.data:
        k = res.data[0]
        exp = "Lifetime" if k['days'] >= 90000 else (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
        supabase.table("users").update({"active_until": exp, "current_key": key}).eq("id", message.from_user.id).execute()
        supabase.table("keys").delete().eq("key", key).execute()
        await message.answer(f"Ваш ключ \n`{key}`\nАктивирован!\nВаш айди: `{message.from_user.id}`", parse_mode="Markdown", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Ключ не найден.", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    # Сохраняем и ID и ник для работы /aprofile
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 DX9WARE готов.", reply_markup=get_main_menu())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
