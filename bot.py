import json
import os

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

with open('dump.json', 'r') as f:
    DICTIONRY = json.loads(f.read())


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
    await update.callback_query.edit_message_text(
        f'{context.user_data['word']} - {context.user_data['translation']}'
        '\nСохранено. Добавить еще? /add',
    )
    DICTIONRY[context.user_data['word']] = context.user_data['translation']
    context.user_data.pop('word')
    context.user_data.pop('translation')
    with open(f'dump.json', 'w') as f:
        f.write(json.dumps(DICTIONRY, indent=4))
    await update.callback_query.answer('👍')
    return ConversationHandler.END


async def no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.edit_message_text(
        'Добавить другое слово? /add',
    )
    context.user_data.pop('word')
    context.user_data.pop('translation')
    await update.callback_query.answer('👍')
    return ConversationHandler.END


ITEMS_PER_PAGE = 5


def get_words(start_index: int, end_index: int) -> list:
    words_list = list(DICTIONRY)
    words_list.reverse()
    return words_list[start_index:end_index]


def words_keyboard(words):
    keyboard = []
    for word in words:
        keyboard.append([
            InlineKeyboardButton(
                word,
                callback_data=f'word@{word}'
            )
        ])
    return keyboard


next_page_button = InlineKeyboardButton(
    'next >>',
    callback_data='next_page'
)


previous_page_button = InlineKeyboardButton(
    '<< previous',
    callback_data='previous_page'
)


async def send_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    page = context.user_data.get("page", 1)
    start_index = (page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    current_page_words = get_words(start_index, end_index)

    keyboard = words_keyboard(current_page_words)
    pagination_keys = []
    if page > 1:
        pagination_keys.append(previous_page_button)
    if end_index < len(DICTIONRY):
        pagination_keys.append(next_page_button)
    keyboard.append(pagination_keys)

    message = 'Слова'
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=message, reply_markup=reply_markup)


async def words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['page'] = 1
    await send_page(update, context)


async def next_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['page'] += 1
    await send_page(update, context)


async def previous_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['page'] -= 1
    await send_page(update, context)


async def word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    word = update.callback_query.data.split('@').pop()
    await update.callback_query.answer(DICTIONRY[word])


app = ApplicationBuilder().token(os.getenv('TOKEN')).build()

app.add_handler(CommandHandler('hello', hello))
app.add_handler(ConversationHandler(
    [CommandHandler('add', add)],
    {
        TRANSLATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, translation)],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        SAVE: [CallbackQueryHandler(yes, 'yes'), CallbackQueryHandler(no, 'no')]
    },
    []
))
app.add_handler(CommandHandler("words", words))
app.add_handler(CallbackQueryHandler(word, 'word'))
app.add_handler(CallbackQueryHandler(next_page, 'next_page'))
app.add_handler(CallbackQueryHandler(previous_page, 'previous_page'))

app.run_polling()
