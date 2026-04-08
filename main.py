import logging
import random
import string
import aiohttp
import os
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- [ КОНФИГ ] ---
API_TOKEN = "8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY"
ADMIN_ID = 6332767725
CRYPTO_PAY_TOKEN = "560149:AA3ApiNO9LQSmc0EysRwSUldKUDUNEgX0cq"
GITHUB_ZIP_URL = "https://github.com/dx9ser777/My_bot/raw/refs/heads/main/cheat_file.zip"
FILE_NAME = "cheat_file.zip"

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Цены
PRICES = {"7": 4, "30": 8, "99999": 20}

class Form(StatesGroup):
    waiting_activation = State()
    admin_gen_days = State()
    admin_freeze_user = State()
    shop_step = State() # Для цепочки выбора

# --- [ ФУНКЦИИ ] ---
def download_cheat_file():
    try:
        r = requests.get(GITHUB_ZIP_URL, allow_redirects=True)
        with open(FILE_NAME, 'wb') as f: f.write(r.content)
    except: pass

async def check_sub(user_id):
    try:
        member = await bot.get_chat_member("@Luci4DX9", user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

def gen_str(): return "DX9-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

# --- [ ХЕНДЛЕРЫ МАГАЗИНА ] ---

@dp.message_handler(lambda m: m.text == "🛒 Купить подписку")
async def shop_start(message: types.Message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("⚡️ External", callback_data="type_ext"),
               InlineKeyboardButton("🔮 Internal", callback_data="type_int"))
    await message.answer("🛠 Выберите тип DX9:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("type_"))
async def select_os(call: types.CallbackQuery, state: FSMContext):
    ctype = "External" if call.data == "type_ext" else "Internal"
    await state.update_data(ctype=ctype)
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🤖 Android", callback_data="os_android"),
                                        InlineKeyboardButton("🍎 iOS", callback_data="os_ios"))
    await call.message.edit_text(f"Выбрано: {ctype}. Теперь выберите ОС:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("os_"))
async def select_days(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("7 дней - 4$", callback_data="pay_7"),
               InlineKeyboardButton("30 дней - 8$", callback_data="pay_30"),
               InlineKeyboardButton("Lifetime - 20$", callback_data="pay_99999"))
    await call.message.edit_text("Выберите тариф:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("pay_"))
async def pay_method(call: types.CallbackQuery):
    days = call.data.split("_")[1]
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💳 CryptoBot (USDT)", callback_data=f"crypto_{days}"),
        InlineKeyboardButton("🌟 Stars (Админ)", callback_data="stars_pay")
    )
    await call.message.edit_text("Выберите способ оплаты:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "stars_pay")
async def stars_msg(call: types.CallbackQuery):
    await call.message.answer("💎 Для оплаты через Stars напишите: @ware4")

# --- [ ЛОГИКА РЕФЕРАЛОВ И КЛЮЧЕЙ ] ---
@dp.message_handler(lambda m: m.text == "👥 Рефералы")
async def refs(message: types.Message):
    # Логика: если юзер пригласил друга, друг совершил покупку -> баланс +30
    res = supabase.table("users").select("balance").eq("id", message.from_user.id).execute()
    bal = res.data[0]["balance"] if res.data else 0
    link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(f"👥 Реферальная система\n💰 Баланс: {bal} руб.\n🔗 Ваша ссылка: {link}")

# (Остальные функции активации и профиля остаются из прошлого кода)
# ...

@dp.message_handler(lambda m: m.text == "🆘 Поддержка")
async def supp(message: types.Message):
    await message.answer("👨‍💻 По всем вопросам: @WareSupport")

if __name__ == '__main__':
    download_cheat_file()
    executor.start_polling(dp, skip_updates=True)
