"""
handlers/constructor.py

Открывает WebApp конструктора мерча и принимает данные от него.
После получения web_app_data:
  1. Парсим JSON.
  2. Заказ УЖЕ создан в БД самим WebApp'ом — бот только показывает подтверждение.
  3. Если snapshot_url есть — отправляем превью фото.
  4. Уведомляем пользователя об успешном создании заявки.
"""
import json
import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import settings
from services import api

logger = logging.getLogger(__name__)
router = Router()


def constructor_kb() -> InlineKeyboardMarkup:
    """Кнопка открытия WebApp."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎨 Открыть конструктор",
            web_app=WebAppInfo(url=settings.WEBAPP_URL),
        )
    ]])


@router.message(F.text == "🎨 Свой дизайн")
async def open_constructor(message: Message):
    """Кнопка в главном меню → открываем WebApp."""
    # Проверяем, заполнены ли данные доставки
    user = await api.get_user(message.from_user.id)
    if user and not user.get("delivery_complete"):
        await message.answer(
            "⚠️ <b>Заполните данные доставки</b>\n\n"
            "Для оформления заказа из конструктора нужны имя, город, адрес и служба доставки.\n"
            "Перейдите в <b>Профиль → Данные доставки</b> и заполните их.",
        )
        return

    await message.answer(
        "🎨 <b>Конструктор мерча</b>\n\n"
        "Создайте изделие с вашим принтом:\n"
        "• Выберите тип и цвет изделия\n"
        "• Разместите готовый принт или загрузите своё изображение\n"
        "• Подтвердите заявку — мастер свяжется с вами\n\n"
        "Стоимость печати рассчитывается мастером индивидуально.",
        reply_markup=constructor_kb(),
    )


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    """
    Telegram вызывает этот хендлер когда WebApp вызывает tg.sendData().
    WebApp уже создал заказ в БД — здесь только показываем подтверждение.
    """
    try:
        data = json.loads(message.web_app_data.data)
    except json.JSONDecodeError:
        logger.error(f"Некорректные данные от WebApp: {message.web_app_data.data}")
        await message.answer("❌ Ошибка при получении данных. Попробуйте ещё раз.")
        return

    order_id     = data.get("order_id")
    product_type = data.get("product_type", "—")
    color        = data.get("color", "—")
    size         = data.get("size", "—")
    snapshot_url = data.get("snapshot_url")

    if not order_id:
        logger.warning(f"WebApp прислал данные без order_id: {data}")
        await message.answer(
            "⚠️ Не удалось определить номер заявки. "
            "Возможно, заказ всё равно создан — проверьте в разделе «Мои заказы»."
        )
        return

    caption = (
        f"✅ <b>Заявка #{order_id} принята!</b>\n\n"
        f"<b>Изделие:</b> {product_type}\n"
        f"<b>Цвет:</b> {color}\n"
        f"<b>Размер:</b> {size}\n\n"
        "Мастер рассмотрит вашу заявку и свяжется с вами для уточнения "
        "деталей и итоговой стоимости 🧵"
    )

    # Если WebApp отдал URL превью — отправляем фото
    if snapshot_url and snapshot_url.startswith("http"):
        try:
            await message.answer_photo(photo=snapshot_url, caption=caption)
            return
        except Exception as e:
            logger.warning(f"Не удалось отправить превью ({snapshot_url}): {e}")

    await message.answer(caption)

    logger.info(
        f"Заказ конструктора #{order_id} от {message.from_user.id}: "
        f"{product_type} {color} р.{size}"
    )
