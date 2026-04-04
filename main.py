import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
SUPPORT_URL = "https://t.me/WareSupport"
CHANNEL_URL = "https://t.me/Luci4DX9"
# Ссылка на файл с читом, которую получит юзер после ввода ключа
CHEAT_LINK = "https://t.me/Luci4DX9" 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# Главное меню (появляется после кнопки Старт)
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 Купить ключ", url=SUPPORT_URL),
        types.InlineKeyboardButton("🔑 Активировать ключ", callback_data="activate"),
        types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL)
    )
    return markup

# 1. ПРИВЕТСТВИЕ
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    start_button = types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_button.add("🚀 СТАРТ")
    
    await message.answer(
        "Привет дорогой игрок здесь ты сможешь купить лучшее дополнение по низким ценам "
        "для standoff 2 и быть всегда наверху!", 
        reply_markup=start_button
    )

# 2. ПОЯВЛЕНИЕ КНОПОК ПОСЛЕ "СТАРТ"
@dp.message_handler(lambda message: message.text == "🚀 СТАРТ")
async def show_buttons(message: types.Message):
    await message.answer("Выбери нужное действие:", reply_markup=main_menu())

# 3. ОБРАБОТКА НАЖАТИЯ "АКТИВИРОВАТЬ КЛЮЧ"
@dp.callback_query_handler(lambda c: c.data == 'activate')
async def process_activate(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "⬇️ Отправь мне свой ключ активации:")

# 4. ПРОВЕРКА КЛЮЧА ИЗ ФАЙЛА KEYS.TXT
@dp.message_handler()
async def check_key(message: types.Message):
    # Если это не системная кнопка, проверяем как ключ
    if message.text == "🚀 СТАРТ": return

    user_key = message.text.strip()
    
    try:
        # Читаем ключи из файла keys.txt
        with open("keys.txt", "r") as f:
            valid_keys = [line.strip() for line in f.readlines()]
        
        if user_key in valid_keys:
            # Успех: выдаем ссылку
            await message.answer(
                f"✅ <b>Ключ верный!</b>\n\nТвоя ссылка на скачивание:\n{CHEAT_LINK}", 
                parse_mode="HTML"
            )
            # Опционально: здесь можно добавить код для удаления ключа из файла, 
            # но на бесплатном хостинге файлы после перезагрузки сбрасываются.
        else:
            await message.answer("❌ <b>Ошибка!</b> Неверный или использованный ключ.")
            
    except FileNotFoundError:
        await message.answer("⚠️ Ошибка: файл keys.txt не найден на сервере.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

