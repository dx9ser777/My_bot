import io
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from PIL import Image, ImageDraw, ImageFont

# --- НАСТРОЙКИ ---
API_TOKEN = 'ТВОЙ_ТОКЕН_ИЗ_BOTFATHER' 
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)

# ID твоих эмодзи (уже проверенные)
EMOJI_USDT = "5311998535032409760"
EMOJI_DOLLAR = "5406841020769936275"

# Файлы в твоей папке
TEMPLATE_PATH = "image_2.png" 
FONT_PATH = "Inter-Bold.ttf" 

def create_check(amount):
    try:
        # Открываем твой шаблон image_2.png
        img = Image.open(TEMPLATE_PATH).convert("RGBA")
    except Exception as e:
        print(f"Ошибка загрузки шаблона: {e}")
        # Запасной вариант, если файл не найден
        img = Image.new('RGBA', (720, 1080), color='#1db995')

    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Загружаем шрифт Inter-Bold
    try:
        font_main = ImageFont.truetype(FONT_PATH, 160) 
        font_sub = ImageFont.truetype(FONT_PATH, 70)   
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Рисуем сумму. На image_2.png логотип в центре, 
    # поэтому текст смещаем чуть ниже центральной оси.
    # Координаты (width // 2, height // 2 + смещение)
    draw.text((width // 2, height // 2 + 80), f"{amount}", font=font_main, fill="white", anchor="mm")
    draw.text((width // 2, height // 2 + 190), f"${amount}", font=font_sub, fill="rgba(255,255,255,0.8)", anchor="mm")

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

@dp.inline_handler()
async def inline_handler(query: types.InlineQuery):
    text = query.query.strip()
    if not text.isdigit():
        return

    amount = int(text)
    image_bytes = create_check(amount)

    # Получаем file_id через отправку себе
    photo_file = io.BytesIO(image_bytes)
    msg = await bot.send_photo(chat_id=query.from_user.id, photo=types.InputFile(photo_file, "check.png"))
    file_id = msg.photo[-1].file_id
    await bot.delete_message(chat_id=query.from_user.id, message_id=msg.message_id)

    # Текст с твоими премиум эмодзи
    caption = (
        f"📤 <b>Чек на</b> <tg-emoji emoji-id='{EMOJI_USDT}'>₮</tg-emoji> <b>{amount} USDT "
        f"(<tg-emoji emoji-id='{EMOJI_DOLLAR}'>$</tg-emoji>{amount}).</b>\n\n"
        f"<i>Ожидаем подтверждение создания чека.</i>"
    )

    result = types.InlineQueryResultPhoto(
        id='1',
        photo_url=file_id,
        thumb_url=file_id,
        caption=caption,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("Подтвердить", callback_data="confirm_check")
        )
    )

    await query.answer([result], cache_time=1)

if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    executor.start_polling(dp, skip_updates=True)
    
