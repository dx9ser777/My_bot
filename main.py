import logging
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiocryptopay import AioCryptoPay
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_ID = 6332767725 

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
crypto = AioCryptoPay(token=CRYPTO_TOKEN, network='main')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class AdminStates(StatesGroup):
    waiting_days = State()

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ГЛАВНОЕ МЕНЮ ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    supabase.table("users").upsert({"id": message.from_user.id}).execute()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    await message.answer("🚀 **DX9WARE Cloud запущен!**", reply_markup=markup, parse_mode="Markdown")

# --- ТОВАРЫ ---
@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def shop_os(message: types.Message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🤖 Android", callback_data="shop_apk"),
               types.InlineKeyboardButton("🍎 iOS", callback_data="shop_ios"))
    await message.answer("Выбери платформу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'))
async def shop_prices(call: types.CallbackQuery):
    os = call.data.split('_')[1]
    is_apk = os == "apk"
    text = f"{'Apk DX9WARE 😀' if is_apk else 'IOS 😔'}\n\n" \
           f"Stars:\n7 days: {350 if is_apk else 400}⭐️\nMonth: {700 if is_apk else 800}⭐️\n" \
           f"Комиссия на вас\n\nCrypto:\n7 days: {4 if is_apk else 6}☺️\nMonth: {8 if is_apk else 12}☺️\n\n" \
           f"Send Crypto or Nft/Stats here: @ware4"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    p7, p30 = (4, 8) if is_apk else (6, 12)
    markup.add(types.InlineKeyboardButton(f"7 Days ({p7}$)", callback_data=f"buy_7_{p7}"),
               types.InlineKeyboardButton(f"Month ({p30}$)", callback_data=f"buy_30_{p30}"))
    await call.message.edit_text(text, reply_markup=markup)

# --- АДМИНКА И КОМАНДЫ ЧАТА ---
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Создать ключ", callback_data="adm_gen"))
    await message.answer("🛠 Админ-панель", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "adm_gen")
async def adm_gen_start(call: types.CallbackQuery):
    await AdminStates.waiting_days.set()
    await call.message.answer("На сколько дней создать ключ?")

@dp.message_handler(state=AdminStates.waiting_days)
async def adm_gen_final(message: types.Message, state: FSMContext):
    days = int(message.text) if message.text.isdigit() else 7
    new_key = gen_str()
    supabase.table("keys").insert({"key": new_key, "days": days, "max_uses": 1, "is_active": True}).execute()
    await message.answer(f"✅ Ключ создан на {days} дн.: `{new_key}`", parse_mode="Markdown")
    await state.finish()

@dp.message_handler(commands=['Aprofile'])
async def aprofile(message: types.Message):
    target_id = message.from_user.id
    if message.reply_to_message: target_id = message.reply_to_message.from_user.id
    elif message.get_args().isdigit(): target_id = int(message.get_args())
    
    res = supabase.table("users").select("*").eq("id", target_id).execute()
    if not res.data:
        await message.answer(f"ID: `{target_id}`\nКлюча нет", parse_mode="Markdown")
    else:
        u = res.data[0]
        await message.answer(f"👤 ID: `{target_id}`\nДо: {u.get('active_until')}\nКлюч: {u.get('current_key')}")

@dp.message_handler(commands=['freeze', 'unfreeze', 'Delkey', 'remove', 'backkey'])
async def admin_cmds(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.get_command()
    key = message.get_args()
    if not key: return await message.answer("Введите ключ!")

    if cmd in ['/freeze']:
        supabase.table("keys").update({"is_active": False}).eq("key", key).execute()
        await message.answer(f"❄️ Ключ `{key}` заморожен")
    elif cmd in ['/unfreeze', '/backkey']:
        supabase.table("keys").update({"is_active": True}).eq("key", key).execute()
        await message.answer(f"☀️ Ключ `{key}` активен")
    elif cmd in ['/Delkey', '/remove']:
        supabase.table("keys").delete().eq("key", key).execute()
        supabase.table("users").update({"active_until": None, "current_key": None}).eq("current_key", key).execute()
        await message.answer(f"🗑 Ключ `{key}` и подписки удалены")

@dp.message_handler(commands=['Allkey'])
async def all_keys(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("keys").select("*").execute()
    text = "🔑 Ключи:\n"
    for k in res.data:
        text += f"{'✅' if k['is_active'] else '❄️'} `{k['key'][:4]}***` | {k['days']}д | {k['used_count']}/{k['max_uses']}\n"
    await message.answer(text, parse_mode="Markdown")

# --- ОПЛАТА И АКТИВАЦИЯ ---
@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def buy_key(call: types.CallbackQuery):
    _, days, price = call.data.split('_')
    inv = await crypto.create_invoice(asset='USDT', amount=float(price))
    btn = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Оплата", url=inv.pay_url),
                                           types.InlineKeyboardButton("✅ Проверить", callback_data=f"chk_{inv.invoice_id}_{days}"))
    await call.message.answer(f"Оплата {days} дн.", reply_markup=btn)

@dp.callback_query_handler(lambda c: c.data.startswith('chk_'))
async def chk_key(call: types.CallbackQuery):
    _, inv_id, days = call.data.split('_')
    invs = await crypto.get_invoices(invoice_ids=int(inv_id))
    if invs and invs.status == 'paid':
        nk = gen_str()
        supabase.table("keys").insert({"key": nk, "days": int(days), "max_uses": 1, "is_active": True}).execute()
        await call.message.answer(f"✅ Твой ключ ({days} дн.): `{nk}`", parse_mode="Markdown")
    else: await call.answer("Не оплачено", show_alert=True)

@dp.message_handler()
async def main_h(message: types.Message):
    if message.text == "👤 Профиль":
        r = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
        sub = r.data[0]['active_until'] if r.data and r.data[0]['active_until'] else "Нет"
        await message.answer(f"ID: `{message.from_user.id}`\nДо: {sub}")
    elif message.text == "🔑 Активировать": await message.answer("Введи ключ:")
    else:
        key = message.text.strip()
        r = supabase.table("keys").select("*").eq("key", key).execute()
        if r.data and r.data[0]['is_active'] and r.data[0]['used_count'] < r.data[0]['max_uses']:
            exp = (datetime.now() + timedelta(days=r.data[0]['days'])).strftime("%Y-%m-%d")
            supabase.table("users").upsert({"id": message.from_user.id, "active_until": exp, "current_key": key}).execute()
            supabase.table("keys").update({"used_count": r.data[0]['used_count'] + 1}).eq("key", key).execute()
            await message.answer(f"✅ Готово до {exp}")
        else: await message.answer("❌ Ошибка ключа")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
