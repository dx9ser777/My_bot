import logging
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY'
ADMIN_ID = 6332767725 
SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class AdminStates(StatesGroup):
    gen_step = State() # Упростим для примера, но логика пошаговая осталась
    edit_key = State()

class UserStates(StatesGroup):
    waiting_key = State()

# --- ЛОГИКА МЕНЮ (ДИНАМИЧЕСКАЯ) ---
async def get_user_menu(user_id):
    res = supabase.table("users").select("is_verified").eq("id", user_id).execute()
    verified = False
    if res.data and res.data[0].get('is_verified'):
        verified = True
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btns = ["👤 Профиль", "🛒 Товары"]
    if not verified: # Кнопка появляется ТОЛЬКО если нет подписки
        btns.append("🔑 Активировать")
    
    markup.add(*btns)
    return markup

# --- КОМАНДЫ АДМИНА (FIXED) ---
@dp.message_handler(commands=['cmd'])
async def admin_cmds(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = (
        "🛠 **Админ-команды:**\n"
        "🔹 `/gen` — Создать ключи (диалог)\n"
        "🔹 `/editkey [ключ]` — Изменить параметры\n"
        "🔹 `/delkey [ключ]` — Удалить ключ\n"
        "🔹 `/akey` — Список всех ключей"
    )
    await message.answer(text, parse_mode="Markdown")

# --- ТОВАРЫ ---
@dp.message_handler(lambda m: m.text == "🛒 Товары")
async def show_products(message: types.Message):
    res = supabase.table("products").select("*").execute()
    if not res.data:
        return await message.answer("Магазин пуст.")
    
    markup = InlineKeyboardMarkup()
    for p in res.data:
        markup.add(InlineKeyboardButton(f"{p['name']} — ${p['price_usd']}", callback_data=f"buy_{p['id']}"))
    
    await message.answer("💳 **Выберите подписку для оплаты Crypto:**", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def process_buy(call: types.CallbackQuery):
    await call.answer("Оплата через CryptoPay временно в ручном режиме. Свяжитесь с админом.", show_alert=True)

# --- АКТИВАЦИЯ (С ВЫВОДОМ ДАННЫХ) ---
@dp.message_handler(lambda m: m.text == "🔑 Активировать")
async def act_start(message: types.Message):
    await UserStates.waiting_key.set()
    await message.answer("Введите ваш лицензионный ключ:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Отмена"))

@dp.message_handler(state=UserStates.waiting_key)
async def act_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        return await message.answer("Отменено.", reply_markup=await get_user_menu(message.from_user.id))

    key_input = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_input).eq("is_active", True).execute()

    if res.data:
        k = res.data[0]
        if k['current_uses'] < k['max_uses']:
            exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
            
            # Обновление базы
            supabase.table("keys").update({"current_uses": k['current_uses'] + 1}).eq("key", key_input).execute()
            supabase.table("users").update({"is_verified": True, "expiry_date": exp}).eq("id", message.from_user.id).execute()
            
            # ОБЯЗАТЕЛЬНЫЙ ВЫВОД ДАННЫХ
            report = (
                "✅ **ПОДПИСКА АКТИВИРОВАНА!**\n\n"
                f"👤 **Ваш ID:** `{message.from_user.id}`\n"
                f"🔑 **Ключ:** `{key_input}`\n"
                f"📅 **Истекает:** `{exp}`\n\n"
                "Перезапустите лоадер для входа."
            )
            await message.answer(report, parse_mode="Markdown", reply_markup=await get_user_menu(message.from_user.id))
            await state.finish()
        else:
            await message.answer("❌ Лимит этого ключа исчерпан.")
    else:
        await message.answer("❌ Неверный или неактивный ключ.")

# --- СТАРТ ---
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    # Регистрация юзера
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    
    welcome_text = "👋 Добро пожаловать в DX9WARE!\nИспользуйте меню ниже:"
    await message.answer(welcome_text, reply_markup=await get_user_menu(message.from_user.id))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
            
