import logging
import random
import string
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiocryptopay import CryptoPay
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_ID = 6332767725 # Твой ID

# Данные Supabase
SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
crypto = CryptoPay(token=CRYPTO_TOKEN, network='main')

logging.basicConfig(level=logging.INFO)

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ОСНОВНОЕ МЕНЮ ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары")
    markup.add("🔑 Активировать", "🎁 Промо")
    await message.answer("🚀 **DX9WARE Cloud запущен!**", reply_markup=markup, parse_mode="Markdown")

# --- ТОВАРЫ ---
@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def shop_platforms(message: types.Message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 Android", callback_data="shop_android"),
        types.InlineKeyboardButton("🍎 iOS", callback_data="shop_ios")
    )
    await message.answer("Выберите платформу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'))
async def process_shop(call: types.CallbackQuery):
    platform = call.data.split('_')[1]
    is_apk = (platform == "android")
    
    if is_apk:
        text = "Apk DX9WARE \n\nStars:\n7 days — 350⭐️\nMonth — 700⭐️\nКомиссия на вас\n\nPrice on Crypto:\n7 days — 4\nMonth — 8☺️"
    else:
        text = "IOS 🍏\n\nStars:\n7 days — 400⭐️\nMonth — 800⭐️\nКомиссия на вас\n\nPrice on Crypto:\n7 days — 6\nMonth — 12"
    
    text += "\n\nSend Crypto or Nft/Stats here: @ware4"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    p = 4 if is_apk else 6
    markup.add(types.InlineKeyboardButton(f"💳 Купить 7 дней ({p}$)", callback_data=f"pay_{platform}_7_{p}"))
    await call.message.edit_text(text, reply_markup=markup)

# --- ОПЛАТА ---
@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def create_pay(call: types.CallbackQuery):
    _, plt, days, price = call.data.split('_')
    inv = await crypto.create_invoice(asset='USDT', amount=float(price))
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔗 Оплатить", url=inv.pay_url),
        types.InlineKeyboardButton("✅ Проверить", callback_data=f"check_{inv.invoice_id}_{days}")
    )
    await call.message.answer(f"Счет на {price} USDT создан.", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('check_'))
async def verify_pay(call: types.CallbackQuery):
    _, inv_id, days = call.data.split('_')
    invoices = await crypto.get_invoices(invoice_ids=int(inv_id))
    
    if invoices and invoices.status == 'paid':
        new_key = gen_str()
        supabase.table("keys").insert({"key": new_key, "days": int(days)}).execute()
        await call.message.edit_text(f"✅ Оплачено! Ключ:\n`{new_key}`", parse_mode="Markdown")
    else:
        await call.answer("❌ Оплата не найдена.", show_alert=True)

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'])
async def admin_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Попытка кряка замечена\nВаша мать: шлюха ✅\nОтец: груз 200✅\nСемья: мертва✅\nКряк: НЕ РАБОТАЕТ❌")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_gen"),
        types.InlineKeyboardButton("⚙️ Изменить лимит", callback_data="adm_limits"),
        types.InlineKeyboardButton("🗑 Удалить ключ", callback_data="adm_del")
    )
    await message.answer("🛠 Панель управления", reply_markup=markup)

# --- КОМАНДЫ ДЛЯ ЧАТОВ ---
@dp.message_handler(commands=['Aprofile'])
async def aprofile(message: types.Message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.get_args()) if message.get_args().isdigit() else None)
    if not uid: return
    res = supabase.table("users").select("active_until").eq("id", uid).execute()
    status = res.data[0]['active_until'] if res.data else "Нет ключа"
    await message.answer(f"👤 ID: `{uid}`\nСтатус: {status}")

@dp.message_handler(commands=['Allkey'])
async def allkey(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("keys").select("key, is_active").execute()
    text = "🗝 Ключи:\n" + "\n".join([f"{'✅' if k['is_active'] else '❄️'} `{k['key'][:5]}***{k['key'][-3:]}`" for k in res.data])
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['freeze', 'unfreeze', 'remove', 'delkey', 'backkey'])
async def manage_keys(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.get_command(); key = message.get_args()
    if not key: return
    
    if 'freeze' in cmd: supabase.table("keys").update({"is_active": False}).eq("key", key).execute()
    elif 'unfreeze' in cmd or 'backkey' in cmd: supabase.table("keys").update({"is_active": True}).eq("key", key).execute()
    elif 'remove' in cmd or 'delkey' in cmd: supabase.table("keys").delete().eq("key", key).execute()
    await message.answer(f"✅ Выполнено для `{key}`", parse_mode="Markdown")

# --- АКТИВАЦИЯ И ПРОФИЛЬ ---
@dp.message_handler()
async def global_handler(message: types.Message):
    if message.text == "👤 Профиль":
        res = supabase.table("users").select("active_until").eq("id", message.from_user.id).execute()
        date = res.data[0]['active_until'] if res.data else "Нет подписки"
        await message.answer(f"👤 ID: `{message.from_user.id}`\nСтатус: {date}")
    elif message.text == "🔑 Активировать": await message.answer("Отправьте ключ:")
    else:
        k_text = message.text.strip()
        res = supabase.table("keys").select("*").eq("key", k_text).execute()
        if res.data:
            k = res.data[0]
            if k['is_active'] and k['used_count'] < k['max_uses']:
                exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
                supabase.table("users").upsert({"id": message.from_user.id, "active_until": exp}).execute()
                supabase.table("keys").update({"used_count": k['used_count'] + 1}).eq("key", k_text).execute()
                await message.answer(f"✅ Активировано до {exp}")
            else: await message.answer("❌ Ключ не активен или лимит исчерпан.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
