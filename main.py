import logging
import random
import string
import aiohttp
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = "8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY"
ADMIN_ID = 6332767725
CRYPTO_PAY_TOKEN = "560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1"
FILE_NAME = "cheat_file.zip"

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Цены
PRICES_CRYPTO = {"apk_7": 4, "apk_30": 8, "ios_7": 6, "ios_30": 12}
PRICES_STARS = {"apk_7": 350, "apk_30": 700, "ios_7": 400, "ios_30": 800}

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()
    waiting_delete_key = State()
    waiting_freeze_key = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def gen_str():
    return "DX9-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def is_subscribed(user_data):
    if not user_data: return False
    sub = user_data.get("active_until")
    if not sub or sub == "Net": return False
    if sub == "Lifetime": return True
    try:
        return datetime.strptime(sub, "%Y-%m-%d") > datetime.now()
    except: return False

def get_main_menu(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Profil", "Aktivirovat klyuch")
    return markup

def calc_exp(days):
    if days >= 90000: return "Lifetime"
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

# --- КРИПТО И БАЗА ---

async def create_invoice(amount):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    data = {"asset": "USDT", "amount": str(amount), "description": "DX9WARE Subscription"}
    async with aiohttp.ClientSession() as session:
        async with session.post("https://pay.crypt.bot/api/createInvoice", json=data, headers=headers) as resp:
            return await resp.json()

async def check_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}", headers=headers) as resp:
            res = await resp.json()
            if res.get("ok") and res["result"]["items"]:
                return res["result"]["items"][0]["status"] == "paid"
    return False

# --- ХЕНДЛЕРЫ ---

@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛒 Kupit klyuch", callback_data="open_shop"),
        InlineKeyboardButton("🔑 Aktivirovat klyuch", callback_data="start_activate")
    )
    await message.answer("💜 **Dobro pozhalovat v DX9WARE**", reply_markup=markup, parse_mode="Markdown")
    await message.answer("Vyberi deystvie:", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "Profil", state="*")
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get("active_until", "Net")
        text = f"👤 **Profil**\n\nID: `{u['id']}`\nPodpiska do: `{sub}`"
        
        markup = InlineKeyboardMarkup()
        if is_subscribed(u):
            markup.add(InlineKeyboardButton("📥 Poluchit fayly", callback_data="download_file"))
        
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer("Napishi /start dlya registratsii.")

@dp.callback_query_handler(lambda c: c.data == "open_shop")
async def shop_platforms(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios")
    )
    await callback.message.edit_text("Vyberi platformu:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("shop_"))
async def shop_details(callback: types.CallbackQuery):
    plat = callback.data.split("_")[1]
    p7, p30 = PRICES_CRYPTO[f"{plat}_7"], PRICES_CRYPTO[f"{plat}_30"]
    
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(f"7 dney - {p7}$", callback_data=f"buy_crypto_{plat}_7"),
        InlineKeyboardButton(f"30 dney - {p30}$", callback_data=f"buy_crypto_{plat}_30"),
        InlineKeyboardButton("Back", callback_data="open_shop")
    )
    await callback.message.edit_text(f"Выбрано: {plat.upper()}\nВыберите тариф:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("buy_crypto_"))
async def create_pay(callback: types.CallbackQuery):
    _, _, plat, days = callback.data.split("_")
    amount = PRICES_CRYPTO[f"{plat}_{days}"]
    
    res = await create_invoice(amount)
    if res.get("ok"):
        inv_id, url = res["result"]["invoice_id"], res["result"]["pay_url"]
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔗 Oplatit", url=url),
            InlineKeyboardButton("✅ Proverit", callback_data=f"check_{inv_id}_{plat}_{days}")
        )
        await callback.message.answer(f"Schet na {amount} USDT sozdan.", reply_markup=markup)
    else:
        await callback.answer("Error creating invoice", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("check_"))
async def check_pay(callback: types.CallbackQuery):
    _, inv_id, plat, days = callback.data.split("_")
    if await check_invoice(inv_id):
        exp = calc_exp(int(days))
        # Генерируем ключ и сразу активируем его юзеру
        new_key = gen_str()
        supabase.table("keys").insert({"key": new_key, "days": int(days), "is_used": True, "used_by": callback.from_user.id}).execute()
        supabase.table("users").update({"active_until": exp, "current_key": new_key}).eq("id", callback.from_user.id).execute()
        
        await callback.message.answer(f"✅ Oplata poluchena!\nKlyuch: `{new_key}`\nDo: {exp}", parse_mode="Markdown")
    else:
        await callback.answer("Oplata ne naydena", show_alert=True)

# --- АДМИН КОМАНДЫ ---

@dp.message_handler(commands=["akey"])
async def cmd_akey(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("keys").select("*").execute()
    if not res.data: return await message.answer("Baza pusta.")
    
    lines = ["🔑 **Vse klyuchi:**"]
    for k in res.data:
        status = "✅" if not k['is_used'] else "❌"
        lines.append(f"`{k['key']}` | {k['days']}d | {status}")
    
    # Чтобы не упало от длинного сообщения, режем по 10 штук
    await message.answer("\n".join(lines[:20]), parse_mode="Markdown")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
