import json
import time
import os
import random
from collections import defaultdict

random.seed(4)

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
    PollHandler,
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


# Загрузка базы данных
with open('arm.json') as f:
    DATABASE = json.loads(f.read())

# Словарь для быстрого поиска индекса слова по армянскому слову
DICT = {word['armenian']: idx for idx, word in enumerate(DATABASE['words'])}
DICT.update({word['russian']: idx for idx, word in enumerate(DATABASE['words'])})

class WordPrioritySystem:
    def __init__(self, words):
        self.words = words
        self.stats = defaultdict(lambda: {'shown': 0, 'correct': 0})

        # Загружаем статистику из базы данных
        for idx, word in enumerate(self.words):
            if 'shown' in word:
                self.stats[idx]['shown'] = word['shown']
            if 'correct' in word:
                self.stats[idx]['correct'] = word['correct']

    def get_next_word_id(self):
        # Вычисляем приоритет для каждого слова
        priorities = []
        for idx, word in enumerate(self.words):
            shown = self.stats[idx]['shown']
            correct = self.stats[idx]['correct']

            if shown == 0:
                # Если слово еще не показывалось, оно имеет высокий приоритет
                priority = 1.0
            else:
                # Приоритет зависит от процента правильных ответов
                accuracy = correct / shown
                priority = 1.0 - accuracy

            priorities.append((idx, priority))

        # Нормализуем приоритеты
        total_priority = sum(priority for _, priority in priorities)
        normalized_priorities = [(idx, priority / total_priority) for idx, priority in priorities]

        # Выбираем слово на основе приоритетов
        ids, weights = zip(*normalized_priorities)
        return random.choices(ids, weights=weights, k=1)[0]

    def update_stats(self, word_id, is_correct):
        self.stats[word_id]['shown'] += 1
        if is_correct:
            self.stats[word_id]['correct'] += 1

# Инициализация системы приоритизации
word_system = WordPrioritySystem(DATABASE['words'])

def get_word(word_id):
    return DATABASE['words'][word_id]['armenian']

def get_russian_word(word_id):
    return DATABASE['words'][word_id]['russian']

def get_options(word_id):
    options_id = set({word_id})
    while len(options_id) < 4:
        options_id.add(random.randrange(len(DATABASE['words'])))
    return [get_russian_word(option_id) for option_id in options_id]

def get_armenian_options(word_id):
    options_id = set({word_id})
    while len(options_id) < 4:
        options_id.add(random.randrange(len(DATABASE['words'])))
    return [get_word(option_id) for option_id in options_id]

def get_correct_option_id(options, word_id):
    correct_word = get_russian_word(word_id)
    return options.index(correct_word)

def get_correct_armenian_option_id(options, word_id):
    correct_word = get_word(word_id)
    return options.index(correct_word)

MODE = 'armenian'

async def armenian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем следующее слово с учетом приоритетов
    word_id = word_system.get_next_word_id()
    word = get_word(word_id)
    options = get_options(word_id)

    global MODE
    MODE = 'armenian'

    # Отправляем опрос
    await context.bot.send_poll(
        7602306060,
        word,
        options,
        type='quiz',
        correct_option_id=get_correct_option_id(options, word_id),
    )

async def russian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем следующее слово с учетом приоритетов
    word_id = word_system.get_next_word_id()
    word = get_russian_word(word_id)
    options = get_armenian_options(word_id)

    global MODE
    MODE = 'russian'

    # Отправляем опрос
    await context.bot.send_poll(
        7602306060,
        word,
        options,
        type='quiz',
        correct_option_id=get_correct_armenian_option_id(options, word_id),
    )

async def receive_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем ID слова из вопроса
    word_id = DICT[update.poll.question]

    # Обновляем статистику
    is_correct = update.poll.options[update.poll.correct_option_id].voter_count > 0
    word_system.update_stats(word_id, is_correct)

    # Сохраняем обновленную статистику в базу данных
    DATABASE['words'][word_id]['shown'] = word_system.stats[word_id]['shown']
    DATABASE['words'][word_id]['correct'] = word_system.stats[word_id]['correct']

    # Сохраняем обновленную базу данных в файл
    with open('arm.json', 'w') as f:
        json.dump(DATABASE, f, indent=4)

    if not is_correct:
        time.sleep(1)

    if MODE == 'armenian':
        await armenian(update, context)
    elif MODE == 'russian':
        await russian(update, context)


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
app.add_handler(CommandHandler('words', words))
app.add_handler(CallbackQueryHandler(word, 'word'))
app.add_handler(CallbackQueryHandler(next_page, 'next_page'))
app.add_handler(CallbackQueryHandler(previous_page, 'previous_page'))
app.add_handler(CommandHandler('armenian', armenian))
app.add_handler(CommandHandler('russian', russian))
app.add_handler(PollHandler(receive_quiz_answer))

app.run_polling()
