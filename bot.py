"""
bot.py — bot Telegram pentru curs valutar la bănci din Moldova.

Rulare locală:
    export TELEGRAM_BOT_TOKEN="123456:ABC..."
    pip install -r requirements.txt
    python bot.py

Botul stă "ascultat" prin long polling — nu are nevoie de un URL public,
de HTTPS sau de webhook. Singura cerință e ca procesul să rămână pornit
(vezi README pentru găzduire gratuită 24/7).
"""

import logging
import os

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from rates import format_rate_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Butoanele afișate pe ecran (tastatura de jos din Telegram)
KEYBOARD = ReplyKeyboardMarkup(
    [
        ["EUR", "USD", "USDT"],
        ["RON", "GBP", "RUB"],
    ],
    resize_keyboard=True,
)

# valute acceptate ca text tastat, chiar dacă nu au buton dedicat
KNOWN_CODES = {
    "EUR", "USD", "USDT", "RON", "GBP", "RUB", "UAH", "CHF", "TRY",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salut! Apasă un buton sau scrie codul valutei (ex: EUR, USD, USDT) "
        "ca să vezi cursul de cumpărare/vânzare la MAIB, MICB, Victoriabank și FinComBank.",
        reply_markup=KEYBOARD,
    )


async def handle_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip().upper()

    if text not in KNOWN_CODES:
        await update.message.reply_text(
            "Nu recunosc această valută. Încearcă: " + ", ".join(sorted(KNOWN_CODES)),
            reply_markup=KEYBOARD,
        )
        return

    await update.message.chat.send_action("typing")
    try:
        message = format_rate_message(text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Eroare la preluarea cursului")
        message = f"A apărut o eroare la preluarea cursului: {exc}"

    await update.message.reply_text(message, reply_markup=KEYBOARD)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Setează variabila de mediu TELEGRAM_BOT_TOKEN cu token-ul de la @BotFather.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_currency))

    logger.info("Bot pornit — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
