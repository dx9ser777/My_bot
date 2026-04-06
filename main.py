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
API_TOKEN = '8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY'
ADMIN_ID = 6332767725
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
FILE_NAME = "cheat_file.zip"

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ЦЕНЫ ---
PRICES_CRYPTO = {"apk_7": 4, "apk_30": 8, "ios_7": 6, "ios_30": 12}
PRICES_STARS = {"apk_7": 350, "apk_30": 700, "ios_7": 400, "ios_30": 800}

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()
    admin_menu = State()
    waiting_key_uses = State()
    waiting_delete_key = State()
    waiting_freeze_key = State()

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_subscribed(user_data: dict) -> bool:
    """Проверяет, есть ли активная подписка"""
    if not user_data:
        return False
    sub = user_data.get('active_until')
    if not sub or sub == "Нет ❌":
        return False
    if sub == "Lifetime ♾":
        return True
    try:
        return datetime.strptime(sub, "%Y-%m-%d") > datetime.now()
    except:
        return False

def get_main_menu(user_id=None):
    """Динамическое меню в зависимости от подписки"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if user_id:
        res = supabase.table("users").select("*").eq("id", user_id).execute()
        if res.data and is_subscribed(res.data[0]):
            markup.add("👤 Профиль")
            return markup
    markup.add("👤 Профиль", "🔑 Активировать")
    return markup

# --- КРИПТО PAY ---
async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': 'DX9WARE Subscription'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

async def check_invoice(invoice_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        params = {'invoice_ids': str(invoice_id)}
        async with session.get('https://pay.crypt.bot/api/getInvoices', params=params, headers=headers) as resp:
            res = await resp.json()
            if res['ok'] and res['result']['items']:
                return res['result']['items'][0]['status'] == 'paid'
    return False

# --- АВТО СОЗДАНИЕ КЛЮЧА ---
def auto_create_key(days: int, platform: str = "apk") -> str:
    """Создаёт ключ автоматически и сохраняет в Supabase"""
    key = gen_str()
    supabase.table("keys").insert({
        "key": key,
        "days": days,
        "is_used": False,
        "platform": platform,
        "max_uses": 1,
        "use_count": 0,
        "frozen": False,
        "created_at": datetime.now().isoformat()
    }).execute()
    return key

# --- /start ---
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({
        "id": message.from_user.id,
        "username": message.from_user.username,
        "joined_at": datetime.now().isoformat()
    }).execute()

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛒 Купить ключ", callback_data="open_shop"),
        InlineKeyboardButton("🔑 Активировать ключ", callback_data="start_activate")
    )
    await message.answer(
        "💜 Добро пожаловать в магазин *dx9ware*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await message.answer("Выберите действие:", reply_markup=get_main_menu(message.from_user.id))

# --- МАГАЗИН ---
@dp.callback_query_handler(lambda c: c.data == "open_shop", state='*')
async def open_shop(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios")
    )
    await callback.message.edit_text("🛒 *Выбери платформу:*", reply_markup=markup, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🛒 Купить", state='*')
async def shop_btn(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios")
    )
    await message.answer("🛒 *Выбери платформу:*", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data in ['shop_apk', 'shop_ios'], state='*')
async def shop_platform(callback: types.CallbackQuery):
    plat = callback.data.split('_')[1]
    is_ios = plat == "ios"
    name = "iOS 🍎" if is_ios else "Android 🤖"
    p7_c = PRICES_CRYPTO[f"{plat}_7"]
    p30_c = PRICES_CRYPTO[f"{plat}_30"]
    p7_s = PRICES_STARS[f"{plat}_7"]
    p30_s = PRICES_STARS[f"{plat}_30"]

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(f"7 дней | {p7_c}$ USDT / {p7_s}⭐", callback_data=f"choose_{plat}_7"),
        InlineKeyboardButton(f"30 дней | {p30_c}$ USDT / {p30_s}⭐", callback_data=f"choose_{plat}_30"),
        InlineKeyboardButton("⬅️ Назад", callback_data="open_shop")
    )
    text = (
        f"💎 *DX9WARE {name}*\n\n"
        f"📦 7 дней:\n  • Крипта: {p7_c} USDT\n  • Звёзды: {p7_s}⭐\n\n"
        f"📦 30 дней:\n  • Крипта: {p30_c} USDT\n  • Звёзды: {p30_s}⭐\n\n"
        f"_Оплата крипто — авто. Звёзды — через @ware4_"
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('choose_'), state='*')
async def choose_payment(callback: types.CallbackQuery):
    _, plat, days = callback.data.split('_')
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💎 Оплатить криптой (авто)", callback_data=f"buy_crypto_{plat}_{days}"),
        InlineKeyboardButton("⭐ Оплатить звёздами (через @ware4)", url="https://t.me/ware4"),
        InlineKeyboardButton("⬅️ Назад", callback_data=f"shop_{plat}")
    )
    await callback.message.edit_text(
        "💳 *Выбери способ оплаты:*\n\n"
        "• Крипта — автоматическая выдача ключа\n"
        "• Звёзды — обратитесь к @ware4",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- ОПЛАТА КРИПТО ---
@dp.callback_query_handler(lambda c: c.data.startswith('buy_crypto_'), state='*')
async def process_buy_crypto(callback: types.CallbackQuery):
    parts = callback.data.split('_')
    plat, days = parts[2], parts[3]
    plan_key = f"{plat}_{days}"
    amount = PRICES_CRYPTO.get(plan_key, 8)

    res = await create_invoice(amount)
    if res.get('ok'):
        inv_id = res['result']['invoice_id']
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🔗 Оплатить", url=res['result']['pay_url']),
            InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{inv_id}_{plat}_{days}")
        )
        await callback.message.answer(
            f"💰 Счёт на *{amount} USDT* создан.\n\nПосле оплаты нажми «Проверить».",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Ошибка создания счёта.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('check_'), state='*')
async def process_check(callback: types.CallbackQuery):
    parts = callback.data.split('_')
    inv_id, plat, days = parts[1], parts[2], parts[3]

    if await check_invoice(inv_id):
        # Авто создание ключа
        new_key = auto_create_key(int(days), plat)
        # Сразу активируем
        exp = "Lifetime ♾" if int(days) >= 90000 else (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")
        supabase.table("users").update({
            "active_until": exp,
            "current_key": new_key
        }).eq("id", callback.from_user.id).execute()
        supabase.table("keys").update({
            "is_used": True,
            "use_count": 1,
            "used_by": callback.from_user.id
        }).eq("key", new_key).execute()

        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📁 Получить файлы", callback_data="download_file")
        )
        await callback.message.answer(
            f"🎉 *Оплата прошла!*\n\n🔑 Ключ: `{new_key}`\n📅 Действует до: `{exp}`",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        await callback.message.answer("Меню обновлено:", reply_markup=get_main_menu(callback.from_user.id))
    else:
        await callback.answer("❌ Оплата не найдена. Попробуй позже.", show_alert=True)

# --- АКТИВАЦИЯ КЛЮЧА ---
@dp.callback_query_handler(lambda c: c.data == "start_activate", state='*')
async def start_activate_inline(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await callback.message.answer("🔑 *Введи свой ключ:*", reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 *Введи свой ключ:*", reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message_handler(state=Form.waiting_activation)
async def act_logic(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.finish()
        await message.answer("⚠️ Отмена.", reply_markup=get_main_menu(message.from_user.id))
        return

    key_in = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_in).execute()

    if not res.data:
        await message.answer("❌ Неверный ключ!", reply_markup=get_main_menu(message.from_user.id))
        await state.finish()
        return

    k = res.data[0]

    if k.get('frozen'):
        await message.answer("❄️ Этот ключ заморожен.", reply_markup=get_main_menu(message.from_user.id))
        await state.finish()
        return

    max_uses = k.get('max_uses', 1)
    use_count = k.get('use_count', 0)

    if use_count >= max_uses:
        await message.answer("❌ Ключ уже использован.", reply_markup=get_main_menu(message.from_user.id))
        await state.finish()
        return

    exp = "Lifetime ♾" if k['days'] >= 90000 else (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
    supabase.table("users").update({
        "active_until": exp,
        "current_key": key_in
    }).eq("id", message.from_user.id).execute()
    supabase.table("keys").update({
        "is_used": True,
        "use_count": use_count + 1,
        "used_by": message.from_user.id
    }).eq("key", key_in).execute()

    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📁 Получить файлы", callback_data="download_file")
    )
    await message.answer(f"✅ *Активировано до:* `{exp}`", parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))
    await message.answer("🚀 Скачать файлы:", reply_markup=markup)
    await state.finish()

# --- ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until', 'Нет ❌')
        key = u.get('current_key', 'Нет')
        text = (
            f"👤 *Профиль*\n\n"
            f"🆔 ID: `{u['id']}`\n"
            f"🔑 Ключ: `{key}`\n"
            f"📅 Подписка до: `{sub}`"
        )
        markup = None
        if is_subscribed(u):
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("📁 Получить файлы", callback_data="download_file")
            )
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer("Профиль не найден. Напиши /start")

# --- ФАЙЛ ---
@dp.callback_query_handler(lambda c: c.data == "download_file", state='*')
async def send_cheat_file(callback: types.CallbackQuery):
    res = supabase.table("users").select("*").eq("id", callback.from_user.id).execute()
    if not res.data or not is_subscribed(res.data[0]):
        await callback.answer("❌ У тебя нет активной подписки.", show_alert=True)
        return
    if os.path.exists(FILE_NAME):
        await callback.message.answer_document(InputFile(FILE_NAME), caption="🚀 *Твой файл DX9WARE готов!*", parse_mode="Markdown")
    else:
        await callback.answer("⚠️ Файл не найден. Обратитесь к @ware4", show_alert=True)

# ============================================================
# АДМИН КОМАНДЫ
# ============================================================

def admin_only(func):
    async def wrapper(message: types.Message, state: FSMContext, *args, **kwargs):
        if message.from_user.id != ADMIN_ID:
            return
        return await func(message, state, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# /admin — полная панель
@dp.message_handler(commands=['admin'], state='*')
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔑 Создать ключ", callback_data="adm_create_key"),
        InlineKeyboardButton("📋 Все ключи", callback_data="adm_all_keys"),
        InlineKeyboardButton("👥 Все пользователи", callback_data="adm_all_users"),
        InlineKeyboardButton("❄️ Заморозить ключ", callback_data="adm_freeze"),
        InlineKeyboardButton("♻️ Разморозить ключ", callback_data="adm_unfreeze"),
        InlineKeyboardButton("🗑 Удалить ключ", callback_data="adm_delete"),
    )
    await message.answer("⚙️ *Панель администратора DX9WARE*", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "adm_create_key")
async def adm_create_key_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await Form.waiting_days.set()
    await callback.message.answer("На сколько дней создать ключ? (0 = Lifetime)\nОтправь число:")

@dp.message_handler(state=Form.waiting_days)
async def adm_gen_key(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    if message.text.startswith('/') or not message.text.isdigit():
        await state.finish()
        await message.answer("⚠️ Отменено.", reply_markup=get_main_menu(message.from_user.id))
        return
    days = 99999 if message.text == "0" else int(message.text)
    key = auto_create_key(days)
    await message.answer(f"✅ Ключ создан:\n`{key}`\nДней: {days if days < 90000 else 'Lifetime'}", parse_mode="Markdown")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "adm_all_keys")
async def adm_all_keys(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    res = supabase.table("keys").select("*").execute()
    if not res.data:
        await callback.message.answer("База ключей пуста.")
        return
    text = "🔑 *Все ключи:*\n\n"
    for k in res.data:
        status = "✅" if k['is_used'] else "🆕"
        frozen = "❄️" if k.get('frozen') else ""
        text += f"`{k['key']}` | {k['days']}д | {status} {frozen} | uses: {k.get('use_count',0)}/{k.get('max_uses',1)}\n"
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "adm_all_users")
async def adm_all_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    res = supabase.table("users").select("*").execute()
    if not res.data:
        await callback.message.answer("Пользователей нет.")
        return
    text = "👥 *Все пользователи:*\n\n"
    for u in res.data:
        sub = u.get('active_until', 'Нет')
        text += f"🆔 `{u['id']}` | @{u.get('username','?')} | до: {sub}\n"
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "adm_freeze")
async def adm_freeze_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await Form.waiting_freeze_key.set()
    await callback.message.answer("Введи ключ для заморозки:")

@dp.callback_query_handler(lambda c: c.data == "adm_unfreeze")
async def adm_unfreeze_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.update_data(freeze_action="unfreeze")
    await Form.waiting_freeze_key.set()
    await callback.message.answer("Введи ключ для разморозки:")

@dp.message_handler(state=Form.waiting_freeze_key)
async def adm_freeze_logic(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    data = await state.get_data()
    action = data.get('freeze_action', 'freeze')
    key = message.text.strip()
    frozen_val = action != "unfreeze"
    res = supabase.table("keys").update({"frozen": frozen_val}).eq("key", key).execute()
    word = "заморожен ❄️" if frozen_val else "разморожен ♻️"
    await message.answer(f"Ключ `{key}` {word}.", parse_mode="Markdown")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "adm_delete")
async def adm_delete_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await Form.waiting_delete_key.set()
    await callback.message.answer("Введи ключ для удаления:")

@dp.message_handler(state=Form.waiting_delete_key)
async def adm_delete_logic(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    key = message.text.strip()
    supabase.table("keys").delete().eq("key", key).execute()
    await message.answer(f"🗑 Ключ `{key}` удалён.", parse_mode="Markdown")
    await state.finish()

# --- ТЕКСТОВЫЕ КОМАНДЫ АДМИНА ---
@dp.message_handler(commands=['akey'], state='*')
async def cmd_akey(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.finish()
    res = supabase.table("keys").select("*").execute()
    if not res.data:
        return await message.answer("База пуста.")
    text = "🔑 *Все ключи (без цензуры):*\n\n"
    for k in res.data:
        status = "✅ Исп." if k['is_used'] else "🆕 Нов."
        frozen = " ❄️" if k.get('frozen') else ""
        text += f"`{k['key']}` | {k['days']}д | {status}{frozen} | {k.get('use_count',0)}/{k.get('max_uses',1)} uses\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['allkey'], sta
