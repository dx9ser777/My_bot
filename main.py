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
from aiocryptopay import CryptoPay

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
crypto = CryptoPay(CRYPTO_TOKEN)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    return markup

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ТОВАРЫ И АВТО-ОПЛАТА ---

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_start(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="buy_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="buy_ios")
    )
    await message.answer("Выберите платформу для покупки DX9WARE:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'), state='*')
async def choose_type(callback: types.CallbackQuery):
    platform = callback.data.split('_')[1].upper()
    is_ios = platform == "IOS"
    
    # Цены
    stars_7 = "400⭐️" if is_ios else "350⭐️"
    stars_month = "800⭐️" if is_ios else "700⭐️"
    usdt_month = 12 if is_ios else 8

    # Создаем инвойс через CryptoPay
    invoice = await crypto.create_invoice(asset='USDT', amount=usdt_month)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Оплатить Crypto (Авто)", url=invoice.pay_url),
        InlineKeyboardButton("Оплатить Stars (Админ)", url="https://t.me/ware4")
    )
    
    text = (
        f"💎 **ЦЕНЫ DX9WARE [{platform}]**\n\n"
        f"**Stars:**\n7 days — {stars_7}\nMonth — {stars_month}\n\n"
        f"**Crypto:**\n7 days — {'6$' if is_ios else '4$'}\nMonth — {usdt_month}$\n\n"
        f"📩 Покупка через Stars: @ware4"
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

# --- ПРОФИЛЬ ---

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until') or "Нет подписки"
        await message.answer(f"👤 **ПРОФИЛЬ**\n\n🆔 ID: `{u['id']}`\n📅 Подписка: `{sub}`", parse_mode="Markdown", reply_markup=get_main_menu())
    else:
        await message.answer("Вы не зарегистрированы. Напишите /start", reply_markup=get_main_menu())

# --- АКТИВАЦИЯ ---

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def activate_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("Введите ваш лицензионный ключ:", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_activation)
async def activate_logic(message: types.Message, state: FSMContext):
    key_input = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_input).execute()
    
    if res.data:
        k = res.data[0]
        if k.get('is_frozen'):
            await message.answer("❄️ Этот ключ заморожен админом.", reply_markup=get_main_menu())
        else:
            days = k['days']
            exp = "Lifetime" if days >= 90000 else (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            
            supabase.table("users").update({"active_until": exp, "current_key": key_input}).eq("id", message.from_user.id).execute()
            supabase.table("keys").delete().eq("key", key_input).execute()
            
            await message.answer(
                f"Ваш ключ \n`{key_input}`\nАктивирован!\nВаш айди: `{message.from_user.id}`", 
                parse_mode="Markdown", reply_markup=get_main_menu()
            )
    else:
        await message.answer("❌ Ключ не найден или уже использован.", reply_markup=get_main_menu())
    await state.finish()

# --- АДМИН-ПАНЕЛЬ ---

@dp.message_handler(commands=['admin'], state='*')
async def admin_gen(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.finish()
    await Form.waiting_days.set()
    await message.answer("На сколько дней создать ключ? (0 - Lifetime)")

@dp.message_handler(state=Form.waiting_days)
async def admin_gen_logic(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    days = 99999 if message.text == "0" else int(message.text)
    new_key = gen_str()
    supabase.table("keys").insert({"key": new_key, "days": days}).execute()
    try: supabase.table("username").insert({"password": new_key}).execute()
    except: pass
    await message.answer(f"🔑 Ключ создан: `{new_key}`", parse_mode="Markdown", reply_markup=get_main_menu())
    await state.finish()

# --- АДМИН-ИНСТРУМЕНТЫ (allkey, delkey, aprofile, freeze) ---

@dp.message_handler(commands=['aprofile', 'allkey', 'clearkey', 'freeze', 'unfreeze', 'delkey'], state='*')
async def admin_tools(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.get_command()
    args = message.get_args()

    if cmd == '/allkey':
        res = supabase.table("keys").select("*").execute()
        if res.data:
            text = "🔑 **СПИСОК:**\n" + "\n".join([f"`{k['key'][:5]}***` | {k['days']}д | {'❄️' if k.get('is_frozen') else '✅'}" for k in res.data])
            await message.answer(text, parse_mode="Markdown")
        else: await message.answer("База пуста.")

    elif cmd == '/delkey':
        if args:
            supabase.table("keys").delete().eq("key", args).execute()
            supabase.table("username").delete().eq("password", args).execute()
            await message.answer(f"🗑 Удален: `{args}`")

    elif cmd == '/clearkey':
        supabase.table("keys").delete().neq("key", "0").execute()
        await message.answer("🗑 Все ключи очищены.")

    elif cmd == '/freeze':
        if args:
            supabase.table("keys").update({"is_frozen": True}).eq("key", args).execute()
            await message.answer(f"❄️ Заморожен: `{args}`")

    elif cmd == '/unfreeze':
        if args:
            supabase.table("keys").update({"is_frozen": False}).eq("key", args).execute()
            await message.answer(f"🔥 Разморожен: `{args}`")

    elif cmd == '/aprofile':
        uid = message.reply_to_message.from_user.id if message.reply_to_message else args
        if uid:
            res = supabase.table("users").select("*").eq("id", uid).execute()
            if res.data:
                u = res.data[0]
                await message.answer(f"👤 Юзер `{uid}`:\nПодписка: {u.get('active_until')}\nКлюч: {u.get('current_key')}")

# --- СТАРТ ---

@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 DX9WARE активирован. Используйте меню ниже:", reply_markup=get_main_menu())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
            
