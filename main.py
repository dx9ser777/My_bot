import logging
import random
import string
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiocryptopay import CryptoPay
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
crypto = CryptoPay(token=CRYPTO_TOKEN, network='main')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class AdminStates(StatesGroup):
    waiting_for_key = State()

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ГЛАВНОЕ МЕНЮ ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    supabase.table("users").upsert({"id": message.from_user.id}).execute()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    await message.answer("🚀 **DX9WARE Cloud запущен!**", reply_markup=markup, parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'])
async def admin_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Попытка кряка замечена\nВаша мать: шлюха ✅\nОтец: груз 200✅\nКряк: НЕ РАБОТАЕТ❌")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Создать ключ (Быстро)", callback_data="adm_fast_gen"),
        types.InlineKeyboardButton("⚙️ Управление ключом (Дни/Удаление)", callback_data="adm_manage_key")
    )
    await message.answer("🛠 **Панель управления**", reply_markup=markup)

# Логика управления днями и удалением
@dp.callback_query_handler(lambda c: c.data == "adm_manage_key")
async def start_manage(call: types.CallbackQuery):
    await AdminStates.waiting_for_key.set()
    await call.message.answer("Введите ключ, который хотите изменить:")

@dp.message_handler(state=AdminStates.waiting_for_key)
async def process_key_manage(message: types.Message, state: FSMContext):
    key_text = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_text).execute()
    
    if not res.data:
        await message.answer("❌ Ключ не найден в базе.")
        await state.finish()
        return

    k = res.data[0]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Добавить 7 дней", callback_data=f"edit_time_{key_text}_7"),
        types.InlineKeyboardButton("➖ Убрать 7 дней", callback_data=f"edit_time_{key_text}_-7"),
        types.InlineKeyboardButton("❄️ Заморозить/Разморозить", callback_data=f"edit_freeze_{key_text}"),
        types.InlineKeyboardButton("🗑 ПОЛНОЕ УДАЛЕНИЕ", callback_data=f"edit_del_{key_text}")
    )
    await message.answer(f"🔑 Ключ: `{key_text}`\n⏳ Дней: {k['days']}\n👤 Использовано: {k['used_count']}/{k['max_uses']}", 
                         reply_markup=markup, parse_mode="Markdown")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('edit_'))
async def handle_edit(call: types.CallbackQuery):
    data = call.data.split('_')
    action, key_text = data[1], data[2]

    if action == "time":
        days_change = int(data[3])
        res = supabase.table("keys").select("days").eq("key", key_text).execute()
        new_days = max(0, res.data[0]['days'] + days_change)
        supabase.table("keys").update({"days": new_days}).eq("key", key_text).execute()
        await call.answer(f"Обновлено: {new_days} дн.")
    
    elif action == "del":
        supabase.table("keys").delete().eq("key", key_text).execute()
        supabase.table("users").update({"active_until": None}).eq("current_key", key_text).execute()
        await call.message.edit_text(f"💥 Ключ `{key_text}` и подписки удалены навсегда.")
        return

    elif action == "freeze":
        res = supabase.table("keys").select("is_active").eq("key", key_text).execute()
        new_state = not res.data[0]['is_active']
        supabase.table("keys").update({"is_active": new_state}).eq("key", key_text).execute()
        await call.answer(f"Статус изменен: {'Активен' if new_state else 'Заморожен'}")

    # Обновляем сообщение
    await process_key_manage(call.message, FSMContext(storage, call.message.chat.id, call.message.chat.id))

# --- ТОВАРЫ И ОПЛАТА ---
@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def shop(message: types.Message):
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🤖 Android (4$)", callback_data="buy_apk_7_4"),
        types.InlineKeyboardButton("🍎 iOS (6$)", callback_data="buy_ios_7_6")
    )
    await message.answer("Выберите товар для покупки через Crypto Pay:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def create_invoice(call: types.CallbackQuery):
    _, plt, days, price = call.data.split('_')
    inv = await crypto.create_invoice(asset='USDT', amount=float(price))
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔗 Оплатить", url=inv.pay_url),
        types.InlineKeyboardButton("✅ Проверить", callback_data=f"check_{inv.invoice_id}_{days}")
    )
    await call.message.answer(f"Оплата {plt.upper()} ({days} дн.) — {price} USDT", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('check_'))
async def check_invoice(call: types.CallbackQuery):
    _, inv_id, days = call.data.split('_')
    invoices = await crypto.get_invoices(invoice_ids=int(inv_id))
    if invoices and invoices.status == 'paid':
        new_key = gen_str()
        supabase.table("keys").insert({"key": new_key, "days": int(days)}).execute()
        await call.message.edit_text(f"✅ Оплачено! Ваш ключ:\n`{new_key}`", parse_mode="Markdown")
    else:
        await call.answer("Оплата не найдена.", show_alert=True)

# --- АКТИВАЦИЯ И ПРОФИЛЬ ---
@dp.message_handler()
async def global_handler(message: types.Message):
    if message.text == "👤 Профиль":
        res = supabase.table("users").select("active_until").eq("id", message.from_user.id).execute()
        date = res.data[0]['active_until'] if res.data and res.data[0]['active_until'] else "Нет подписки"
        await message.answer(f"👤 ID: `{message.from_user.id}`\nСтатус: {date}")
    elif message.text == "🔑 Активировать":
        await message.answer("Введите ваш ключ:")
    else:
        k_text = message.text.strip()
        res = supabase.table("keys").select("*").eq("key", k_text).execute()
        if res.data:
            k = res.data[0]
            if k['is_active'] and k['used_count'] < k['max_uses']:
                exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
                supabase.table("users").upsert({"id": message.from_user.id, "active_until": exp, "current_key": k_text}).execute()
                supabase.table("keys").update({"used_count": k['used_count'] + 1}).eq("key", k_text).execute()
                await message.answer(f"✅ Успешно! Подписка до: {exp}")
            else:
                await message.answer("❌ Ключ недействителен.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
