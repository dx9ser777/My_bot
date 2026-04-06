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
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0"
    ".6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ЦЕНЫ ---
PRICES_CRYPTO = {
    "apk_7": 4,
    "apk_30": 8,
    "ios_7": 6,
    "ios_30": 12,
}
PRICES_STARS = {
    "apk_7": 350,
    "apk_30": 700,
    "ios_7": 400,
    "ios_30": 800,
}


class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()
    waiting_delete_key = State()
    waiting_freeze_key = State()


def gen_str(prefix="DX9-", length=10):
    chars = string.ascii_uppercase + string.digits
    return prefix + ''.join(random.choices(chars, k=length))


def is_subscribed(user_data: dict) -> bool:
    if not user_data:
        return False
    sub = user_data.get('active_until')
    if not sub or sub == "Нет ❌":
        return False
    if sub == "Lifetime ♾":
        return True
    try:
        return datetime.strptime(sub, "%Y-%m-%d") > datetime.now()
    except Exception:
        return False


def get_main_menu(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if user_id:
        try:
            res = supabase.table("users").select("*").eq("id", user_id).execute()
            if res.data and is_subscribed(res.data[0]):
                markup.add("👤 Профиль")
                return markup
        except Exception:
            pass
    markup.add("👤 Профиль", "🔑 Активировать")
    return markup


# --- КРИПТО PAY ---
async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {
        'asset': 'USDT',
        'amount': str(amount),
        'description': 'DX9WARE Subscription',
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://pay.crypt.bot/api/createInvoice',
            json=data,
            headers=headers,
        ) as resp:
            return await resp.json()


async def check_invoice(invoice_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    params = {'invoice_ids': str(invoice_id)}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://pay.crypt.bot/api/getInvoices',
            params=params,
            headers=headers,
        ) as resp:
            res = await resp.json()
            if res.get('ok') and res['result']['items']:
                return res['result']['items'][0]['status'] == 'paid'
    return False


# --- АВТО СОЗДАНИЕ КЛЮЧА ---
def auto_create_key(days: int, platform: str = "apk") -> str:
    key = gen_str()
    supabase.table("keys").insert({
        "key": key,
        "days": days,
        "is_used": False,
        "platform": platform,
        "max_uses": 1,
        "use_count": 0,
        "frozen": False,
        "created_at": datetime.now().isoformat(),
    }).execute()
    return key


# ============================================================
# /start
# ============================================================
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({
        "id": message.from_user.id,
        "username": message.from_user.username,
        "joined_at": datetime.now().isoformat(),
    }).execute()

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛒 Купить ключ", callback_data="open_shop"),
        InlineKeyboardButton("🔑 Активировать ключ", callback_data="start_activate"),
    )
    await message.answer(
        "💜 Добро пожаловать в магазин *dx9ware*",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    await message.answer(
        "Выберите действие:",
        reply_markup=get_main_menu(message.from_user.id),
    )


# ============================================================
# МАГАЗИН
# ============================================================
@dp.callback_query_handler(lambda c: c.data == "open_shop", state='*')
async def open_shop(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios"),
    )
    await callback.message.edit_text(
        "🛒 *Выбери платформу:*",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@dp.callback_query_handler(lambda c: c.data in ['shop_apk', 'shop_ios'], state='*')
async def shop_platform(callback: types.CallbackQuery):
    plat = callback.data.split('_')[1]
    is_ios = plat == "ios"
    name = "iOS 🍎" if is_ios else "Android 🤖"
    p7_c = PRICES_CRYPTO[plat + "_7"]
    p30_c = PRICES_CRYPTO[plat + "_30"]
    p7_s = PRICES_STARS[plat + "_7"]
    p30_s = PRICES_STARS[plat + "_30"]

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "7 дней | {}$ USDT / {}⭐".format(p7_c, p7_s),
            callback_data="choose_{}_7".format(plat),
        ),
        InlineKeyboardButton(
            "30 дней | {}$ USDT / {}⭐".format(p30_c, p30_s),
            callback_data="choose_{}_30".format(plat),
        ),
        InlineKeyboardButton("⬅️ Назад", callback_data="open_shop"),
    )
    text = (
        "💎 *DX9WARE {}*\n\n"
        "📦 7 дней:\n  • Крипта: {} USDT\n  • Звёзды: {}⭐\n\n"
        "📦 30 дней:\n  • Крипта: {} USDT\n  • Звёзды: {}⭐\n\n"
        "_Оплата крипто — авто. Звёзды — через @ware4_"
    ).format(name, p7_c, p7_s, p30_c, p30_s)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data.startswith('choose_'), state='*')
async def choose_payment(callback: types.CallbackQuery):
    parts = callback.data.split('_')
    plat = parts[1]
    days = parts[2]
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "💎 Оплатить криптой (авто)",
            callback_data="buy_crypto_{}_{}".format(plat, days),
        ),
        InlineKeyboardButton(
            "⭐ Оплатить звёздами (через @ware4)",
            url="https://t.me/ware4",
        ),
        InlineKeyboardButton("⬅️ Назад", callback_data="shop_{}".format(plat)),
    )
    await callback.message.edit_text(
        "💳 *Выбери способ оплаты:*\n\n"
        "• Крипта — автоматическая выдача ключа\n"
        "• Звёзды — обратитесь к @ware4",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@dp.callback_query_handler(lambda c: c.data.startswith('buy_crypto_'), state='*')
async def process_buy_crypto(callback: types.CallbackQuery):
    parts = callback.data.split('_')
    plat = parts[2]
    days = parts[3]
    plan_key = "{}_{}".format(plat, days)
    amount = PRICES_CRYPTO.get(plan_key, 8)

    res = await create_invoice(amount)
    if res.get('ok'):
        inv_id = res['result']['invoice_id']
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🔗 Оплатить", url=res['result']['pay_url']),
            InlineKeyboardButton(
                "✅ Проверить оплату",
                callback_data="check_{}_{}_{}" .format(inv_id, plat, days),
            ),
        )
        await callback.message.answer(
            "💰 Счёт на *{} USDT* создан.\n\nПосле оплаты нажми «Проверить».".format(amount),
            reply_markup=markup,
            parse_mode="Markdown",
        )
    else:
        await callback.answer("❌ Ошибка создания счёта.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith('check_'), state='*')
async def process_check(callback: types.CallbackQuery):
    parts = callback.data.split('_')
    inv_id = parts[1]
    plat = parts[2]
    days = parts[3]

    if await check_invoice(inv_id):
        new_key = auto_create_key(int(days), plat)
        if int(days) >= 90000:
            exp = "Lifetime ♾"
        else:
            exp = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")

        supabase.table("users").update({
            "active_until": exp,
            "current_key": new_key,
        }).eq("id", callback.from_user.id).execute()
        supabase.table("keys").update({
            "is_used": True,
            "use_count": 1,
            "used_by": callback.from_user.id,
        }).eq("key", new_key).execute()

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
        await callback.message.answer(
            "🎉 *Оплата прошла!*\n\n🔑 Ключ: `{}`\n📅 Действует до: `{}`".format(new_key, exp),
            reply_markup=markup,
            parse_mode="Markdown",
        )
        await callback.message.answer(
            "Меню обновлено:",
            reply_markup=get_main_menu(callback.from_user.id),
        )
    else:
        await callback.answer("❌ Оплата не найдена. Попробуй позже.", show_alert=True)


# ============================================================
# АКТИВАЦИЯ КЛЮЧА
# ============================================================
@dp.callback_query_handler(lambda c: c.data == "start_activate", state='*')
async def start_activate_inline(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await callback.message.answer(
        "🔑 *Введи свой ключ:*",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )


@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer(
        "🔑 *Введи свой ключ:*",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )


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
        await message.answer(
            "❄️ Этот ключ заморожен.",
            reply_markup=get_main_menu(message.from_user.id),
        )
        await state.finish()
        return

    max_uses = k.get('max_uses', 1)
    use_count = k.get('use_count', 0)

    if use_count >= max_uses:
        await message.answer(
            "❌ Ключ уже использован.",
            reply_markup=get_main_menu(message.from_user.id),
        )
        await state.finish()
        return

    if k['days'] >= 90000:
        exp = "Lifetime ♾"
    else:
        exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")

    supabase.table("users").update({
        "active_until": exp,
        "current_key": key_in,
    }).eq("id", message.from_user.id).execute()
    supabase.table("keys").update({
        "is_used": True,
        "use_count": use_count + 1,
        "used_by": message.from_user.id,
    }).eq("key", key_in).execute()

    markup_dl = InlineKeyboardMarkup()
    markup_dl.add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))

    await message.answer(
        "✅ *Активировано до:* `{}`".format(exp),
        parse_mode="Markdown",
        reply_markup=get_main_menu(message.from_user.id),
    )
    await message.answer("🚀 Скачать файлы:", reply_markup=markup_dl)
    await state.finish()


# ============================================================
# ПРОФИЛЬ
# ============================================================
@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until', 'Нет ❌')
        key = u.get('current_key', 'Нет')
        text = (
            "👤 *Профиль*\n\n"
            "🆔 ID: `{}`\n"
            "🔑 Ключ: `{}`\n"
            "📅 Подписка до: `{}`"
        ).format(u['id'], key, sub)
        markup = None
        if is_subscribed(u):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer("Профиль не найден. Напиши /start")


# ============================================================
# ФАЙЛ
# ============================================================
@dp.callback_query_handler(lambda c: c.data == "download_file", state='*')
async def send_cheat_file(callback: types.CallbackQuery):
    res = supabase.table("users").select("*").eq("id", callback.from_user.id).execute()
    if not res.data or not is_subscribed(res.data[0]):
        await callback.answer("❌ У тебя нет активной подписки.", show_alert=True)
        return
    if os.path.exists(FILE_NAME):
        await callback.message.answer_document(
            InputFile(FILE_NAME),
            caption="🚀 *Твой файл DX9WARE готов!*",
            parse_mode="Markdown",
        )
    else:
        await callback.answer("⚠️ Файл не найден. Обратитесь к @ware4", show_alert=True)


# ============================================================
# НАЗАД В МАГАЗИН
# ============================================================
@dp.callback_query_handler(lambda c: c.data == "back_to_shop", state='*')
async def back_to_shop(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios"),
    )
    await callback.message.edit_text(
        "🛒 *Выбери платформу:*",
        reply_markup=markup,
        parse_mode="Markdown",
    )


# ============================================================
# АДМИН ПАНЕЛЬ — /admin
# ============================================================
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
    await message.answer(
        "⚙️ *Панель администратора DX9WARE*",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@dp.callback_query_handler(lambda c: c.data == "adm_create_key")
async def adm_create_key_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await Form.waiting_days.set()
    await callback.message.answer(
        "На сколько дней создать ключ? (0 = Lifetime)\nОтправь число:"
    )


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
    label = "Lifetime" if days >= 90000 else str(days)
    await message.answer(
        "✅ Ключ создан:\n`{}`\nДней: {}".format(key, label),
        parse_mode="Markdown",
    )
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "adm_all_keys")
async def adm_all_keys_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    res = supabase.table("keys").select("*").execute()
    if not res.data:
        await callback.message.answer("База ключей пуста.")
        return
    text = "🔑 *Все ключи:*\n\n"
    for k in res.data:
        status = "✅" if k['is_used'] else "🆕"
        frozen = " ❄️" if k.get('frozen') else ""
        text += "`{}` | {}д | {}{} | {}/{}\n".format(
            k['key'], k['days'], status, frozen,
            k.get('use_count', 0), k.get('max_uses', 1),
        )
    await callback.message.answer(text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "adm_all_users")
async def adm_all_users_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    res = supabase.table("users").select("*").execute()
    if not res.data:
        await callback.message.answer("Пользователей нет.")
        return
    text = "👥 *Все пользователи:*\n\n"
    for u in res.data:
        sub = u.get('active_until', 'Нет')
        text += "🆔 `{}` | @{} | до: {}\n".format(
            u['id'], u.get('username', '?'), sub
        )
    await callback.message.answer(text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "adm_freeze")
async def adm_freeze_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.update_data(freeze_action="freeze")
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
    supabase.table("keys").update({"frozen": frozen_val}).eq("key", key).execute()
    word = "заморожен ❄️" if frozen_val else "разморожен ♻️"
    await message.answer("`{}` {}".format(key, word), parse_mode="Markdown")
    await state.finish()


@dp.ca
