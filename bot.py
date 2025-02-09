import json
import os
import time

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


load_dotenv()

TRANSLATION, CONFIRM, SAVE = range(3)

DICTIONRY = {}


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(f'Введите слово')
    return TRANSLATION


async def translation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(update.message.text)
    context.user_data['word'] = update.message.text
    await update.message.reply_text(f'Введите перевод')
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(update.message.text)
    context.user_data['translation'] = update.message.text
    await update.message.reply_text(
        f'{context.user_data['word']} - {context.user_data['translation']}\nСохранить?',
        reply_markup=InlineKeyboardMarkup.from_row(
            [
                InlineKeyboardButton('Да', callback_data='yes'),
                InlineKeyboardButton('Нет', callback_data='no'),
            ]
        )
    )
    return SAVE


async def yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    DICTIONRY[context.user_data['word']] = context.user_data['translation']
    context.user_data.pop('word')
    context.user_data.pop('translation')
    with open(f'dump{int(time.time())}.json', 'w') as f:
        f.write(json.dumps(DICTIONRY, indent=4))
    await update.callback_query.answer('👍')
    return ConversationHandler.END


async def no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop('word')
    context.user_data.pop('translation')
    await update.callback_query.answer('👍')
    return ConversationHandler.END


app = ApplicationBuilder().token(os.getenv("TOKEN")).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(ConversationHandler(
    [CommandHandler("add", add)],
    {
        TRANSLATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, translation)],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        SAVE: [CallbackQueryHandler(yes, 'yes'), CallbackQueryHandler(no, 'no')]
    },
    []
))

app.run_polling()
