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

API_TOKEN = "8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY"
ADMIN_ID = 6332767725
CRYPTO_PAY_TOKEN = "560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1"
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
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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


def gen_str():
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=10))
    return "DX9-" + suffix


def is_subscribed(user_data):
    if not user_data:
        return False
    sub = user_data.get("active_until")
    if not sub or sub == "Net":
        return False
    if sub == "Lifetime":
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
                markup.add("Profil")
                return markup
        except Exception:
            pass
    markup.add("Profil", "Aktivirovat klyuch")
    return markup


def calc_exp(days):
    if days >= 90000:
        return "Lifetime"
    exp_date = datetime.now() + timedelta(days=days)
    return exp_date.strftime("%Y-%m-%d")


def auto_create_key(days, platform="apk"):
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


async def create_invoice(amount):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": "DX9WARE Subscription",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            json=data,
            headers=headers,
        ) as resp:
            return await resp.json()


async def check_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    params = {"invoice_ids": str(invoice_id)}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://pay.crypt.bot/api/getInvoices",
            params=params,
            headers=headers,
        ) as resp:
            res = await resp.json()
            if res.get("ok") and res["result"]["items"]:
                return res["result"]["items"][0]["status"] == "paid"
    return False


# /start
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({
        "id": message.from_user.id,
        "username": message.from_user.username,
        "joined_at": datetime.now().isoformat(),
    }).execute()
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "\U0001f6d2 Kupit klyuch",
            callback_data="open_shop",
        ),
        InlineKeyboardButton(
            "\U0001f511 Aktivirovat klyuch",
            callback_data="start_activate",
        ),
    )
    await message.answer(
        "\U0001f49c Dobro pozhalovat v magazin dx9ware",
        reply_markup=markup,
    )
    await message.answer(
        "Vyberi deystvie:",
        reply_markup=get_main_menu(message.from_user.id),
    )


# SHOP - platform select
@dp.callback_query_handler(lambda c: c.data == "open_shop", state="*")
async def open_shop(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android \U0001f916", callback_data="shop_apk"),
        InlineKeyboardButton("iOS \U0001f34e", callback_data="shop_ios"),
    )
    await callback.message.edit_text("Vyberi platformu:", reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data in ["shop_apk", "shop_ios"], state="*")
async def shop_platform(callback: types.CallbackQuery):
    plat = callback.data.split("_")[1]
    is_ios = plat == "ios"
    if is_ios:
        name = "iOS"
    else:
        name = "Android"
    p7_c = PRICES_CRYPTO[plat + "_7"]
    p30_c = PRICES_CRYPTO[plat + "_30"]
    p7_s = PRICES_STARS[plat + "_7"]
    p30_s = PRICES_STARS[plat + "_30"]

    btn1 = "7 dney - " + str(p7_c) + "$ / " + str(p7_s) + " zvezd"
    btn2 = "30 dney - " + str(p30_c) + "$ / " + str(p30_s) + " zvezd"

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(btn1, callback_data="choose_" + plat + "_7"),
        InlineKeyboardButton(btn2, callback_data="choose_" + plat + "_30"),
        InlineKeyboardButton("Nazad", callback_data="open_shop"),
    )
    text = (
        "DX9WARE " + name + "\n\n"
        "7 dney: " + str(p7_c) + " USDT / " + str(p7_s) + " zvezd\n"
        "30 dney: " + str(p30_c) + " USDT / " + str(p30_s) + " zvezd\n\n"
        "Oplata krypto - avto. Zvezdy - cherez @ware4"
    )
    await callback.message.edit_text(text, reply_markup=markup)


# SHOP - payment method
@dp.callback_query_handler(lambda c: c.data.startswith("choose_"), state="*")
async def choose_payment(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    plat = parts[1]
    days = parts[2]
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "Krypta (avto)",
            callback_data="buy_crypto_" + plat + "_" + days,
        ),
        InlineKeyboardButton(
            "Zvezdy (cherez @ware4)",
            url="https://t.me/ware4",
        ),
        InlineKeyboardButton("Nazad", callback_data="shop_" + plat),
    )
    await callback.message.edit_text(
        "Vyberi sposob oplaty:\n\nKrypta - avto vydacha\nZvezdy - obratites k @ware4",
        reply_markup=markup,
    )


# SHOP - crypto buy
@dp.callback_query_handler(lambda c: c.data.startswith("buy_crypto_"), state="*")
async def process_buy_crypto(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    plat = parts[2]
    days = parts[3]
    plan_key = plat + "_" + days
    amount = PRICES_CRYPTO.get(plan_key, 8)
    res = await create_invoice(amount)
    if res.get("ok"):
        inv_id = res["result"]["invoice_id"]
        pay_url = res["result"]["pay_url"]
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Oplatit", url=pay_url),
            InlineKeyboardButton(
                "Proverit oplatu",
                callback_data="check_" + str(inv_id) + "_" + plat + "_" + days,
            ),
        )
        await callback.message.answer(
            "Schet na " + str(amount) + " USDT sozdan. Posle oplaty nazhmite Proverit.",
            reply_markup=markup,
        )
    else:
        await callback.answer("Oshibka sozdaniya scheta.", show_alert=True)


# SHOP - check payment
@dp.callback_query_handler(lambda c: c.data.startswith("check_"), state="*")
async def process_check(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    inv_id = parts[1]
    plat = parts[2]
    days = int(parts[3])
    paid = await check_invoice(inv_id)
    if paid:
        new_key = auto_create_key(days, plat)
        exp = calc_exp(days)
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
        markup.add(
            InlineKeyboardButton("Poluchit fayly", callback_data="download_file")
        )
        await callback.message.answer(
            "Oplata proshla!\n\nKlyuch: " + new_key + "\nDeystviyet do: " + exp,
            reply_markup=markup,
        )
        await callback.message.answer(
            "Menyu:",
            reply_markup=get_main_menu(callback.from_user.id),
        )
    else:
        await callback.answer("Oplata ne naydena. Poprobuy pozzhe.", show_alert=True)


# ACTIVATION - inline button
@dp.callback_query_handler(lambda c: c.data == "start_activate", state="*")
async def start_activate_inline(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await callback.message.answer(
        "Vvedi svoy klyuch:",
        reply_markup=types.ReplyKeyboardRemove(),
    )


# ACTIVATION - keyboard button
@dp.message_handler(lambda m: m.text == "Aktivirovat klyuch", state="*")
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer(
        "Vvedi svoy klyuch:",
        reply_markup=types.ReplyKeyboardRemove(),
    )


# ACTIVATION - logic
@dp.message_handler(state=Form.waiting_activation)
async def act_logic(message: types.Message, state: FSMContext):
    if message.text.startswith("/"):
        await state.finish()
        await message.answer("Otmena.", reply_markup=get_main_menu(message.from_user.id))
        return
    key_in = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_in).execute()
    if not res.data:
        await message.answer("Nevernyy klyuch!", reply_markup=get_main_menu(message.from_user.id))
        await state.finish()
        return
    k = res.data[0]
    if k.get("frozen"):
        await message.answer("Etot klyuch zamorozhen.", reply_markup=get_main_menu(message.from_user.id))
        await state.finish()
        return
    max_uses = k.get("max_uses", 1)
    use_count = k.get("use_count", 0)
    if use_count >= max_uses:
        await message.answer("Klyuch uzhe ispolzovan.", reply_markup=get_main_menu(message.from_user.id))
        await state.finish()
        return
    exp = calc_exp(k["days"])
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
    markup_dl.add(InlineKeyboardButton("Poluchit fayly", callback_data="download_file"))
    await message.answer(
        "Aktivirovano do: " + exp,
        reply_markup=get_main_menu(message.from_user.id),
    )
    await message.answer("Skachat fayly:", reply_markup=markup_dl)
    await state.finish()


# PROFILE
@dp.message_handler(lambda m: m.text == "Profil", state="*")
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get("active_until", "Net")
        key = u.get("current_key", "Net")
        text = (
            "Profil\n\n"
            "ID: " + str(u["id"]) + "\n"
            "Klyuch: " + str(key) + "\n"
            "Podpiska do: " + str(sub)
        )
        markup = None
        if is_subscribed(u):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Poluchit fayly", callback_data="download_file"))
        await message.answer(text, reply_markup=markup)
    else:
        await message.answer("Profil ne nayden. Napishi /start")


# FILE
@dp.callback_query_handler(lambda c: c.data == "download_file", state="*")
async def send_cheat_file(callback: types.CallbackQuery):
    res = supabase.table("users").select("*").eq("id", callback.from_user.id).execute()
    if not res.data or not is_subscribed(res.data[0]):
        await callback.answer("Net aktivnoy podpiski.", show_alert=True)
        return
    if os.path.exists(FILE_NAME):
        await callback.message.answer_document(
            InputFile(FILE_NAME),
            caption="Tvoy fayl DX9WARE gotov!",
        )
    else:
        await callback.answer("Fayl ne nayden. Obratites k @ware4", show_alert=True)


# BACK TO SHOP
@dp.callback_query_handler(lambda c: c.data == "back_to_shop", state="*")
async def back_to_shop(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android", callback_data="shop_apk"),
        InlineKeyboardButton("iOS", callback_data="shop_ios"),
    )
    await callback.message.edit_text("Vyberi platformu:", reply_markup=markup)


# ADMIN /admin
@dp.message_handler(commands=["admin"], state="*")
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Sozdat klyuch", callback_data="adm_create_key"),
        InlineKeyboardButton("Vse klyuchi", callback_data="adm_all_keys"),
        InlineKeyboardButton("Vse polzovateli", callback_data="adm_all_users"),
        InlineKeyboardButton("Zamorozit", callback_data="adm_freeze"),
        InlineKeyboardButton("Razmorozit", callback_data="adm_unfreeze"),
        InlineKeyboardButton("Udalit klyuch", callback_data="adm_delete"),
    )
    await message.answer("Panel administratora DX9WARE", reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data == "adm_create_key")
async def adm_create_key_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await Form.waiting_days.set()
    await callback.message.answer("Na skolko dney? (0 = Lifetime):")


@dp.message_handler(state=Form.waiting_days)
async def adm_gen_key(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    if message.text.startswith("/") or not message.text.isdigit():
        await state.finish()
        await message.answer("Otmeneno.")
        return
    days = 99999 if message.text == "0" else int(message.text)
    key = auto_create_key(days)
    if days >= 90000:
        label = "Lifetime"
    else:
        label = str(days)
    await message.answer("Klyuch sozdan: " + key + "  Dney: " + label)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "adm_all_keys")
async def adm_all_keys_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    res = supabase.table("keys").select("*").execute()
    if not res.data:
        await callback.message.answer("Baza klyuchey pusta.")
        return
    lines = ["Vse klyuchi:\n"]
    for k in res.data:
        if k["is_used"]:
            status = "Isp"
        else:
            status = "Nov"
        if k.get("frozen"):
            frozen = " FROZEN"
        else:
            frozen = ""
        line = (
            str(k["key"]) + " | "
            + str(k["days"]) + "d | "
            + status + frozen + " | "
            + str(k.get("use_count", 0)) + "/" + str(k.get("max_uses", 1))
        )
        lines.append(line)
    await callback.message.answer("\n".join(lines))


@dp.callback_query_handler(lambda c: c.data == "adm_all_users")
async def adm_all_users_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    res = supabase.table("users").select("*").execute()
    if not res.data:
        await callback.message.answer("Polzovateley net.")
        return
    lines = ["Vse polzovateli:\n"]
    for u in res.data:
        sub = u.get("active_until", "Net")
        uname = u.get("username") or "?"
        line = "ID: " + str(u["id"]) + " | @" + uname + " | do: " + str(sub)
        lines.append(line)
    await callback.message.answer("\n".join(lines))


@dp.callback_query_handler(lambda c: c.data == "adm_freeze")
async def adm_freeze_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.update_data(freeze_action="freeze")
    await Form.waiting_freeze_key.set()
    await callback.message.answer("Vvedi klyuch dlya zamorozki:")


@dp.callback_query_handler(lambda c: c.data == "adm_unfreeze")
async def adm_unfreeze_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.update_data(freeze_action="unfreeze")
    await Form.waiting_freeze_key.set()
    await callback.message.answer("Vvedi klyuch dlya razmorozki:")


@dp.message_handler(state=Form.waiting_freeze_key)
async def adm_freeze_logic(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    data = await state.get_data()
    action = data.get("freeze_action", "freeze")
    key = message.text.strip()
    frozen_val = action != "unfreeze"
    supabase.table("keys").update({"frozen": frozen_val}).eq("key", key).execute()
    if frozen_val:
        word = "zamorozhen"
    else:
        word = "razmorozhen"
    await message.answer("Klyuch " + key + " " + word + ".")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "adm_delete")
async def adm_delete_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await Form.waiting_delete_key.set()
    await callback.message.answer("Vvedi klyuch dlya udaleniya:")


@dp.message_handler(state=Form.waiting_delete_key)
async def adm_delete_logic(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    key = message.text.strip()
    supabase.table("keys").delete().eq("key", key).execute()
    await message.answer("Klyuch " + key + " udalyon.")
    await state.finish()


# TEXT ADMIN COMMANDS
@dp.message_handler(commands=["akey"], state="*")
async def cmd_akey(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.finish()
    res = supabase.table("keys").select("*").execute()
    if not res.data:
        await message.answer("Baza pusta.")
        return
    lines = ["Vse klyuchi (bez tsenzury):\n"]
    for k in res.data:
        if k["is_used"]:
            status = "Isp"
        else:
            status = "Nov"
        if k.get("frozen"):
            frozen = " FROZEN"
        else:
            frozen = ""
        line = (
            str(k["key"]) + " | "
            + str(k["days"]) + "d | "
            + status + frozen + " | "
            + str(k.get("use_count", 0)) + "/" + str(k.get("max_uses", 1))
        )
        lines.append(line)
    await m
