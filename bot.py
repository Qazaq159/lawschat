import os
import logging
import warnings

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from core import InsuranceLawChatbot

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global chatbot instance
chatbot = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    welcome_message = """
    🏛️ Добро пожаловать в бот по страховому законодательству Казахстана!

    Я могу ответить на ваши вопросы о:
    • Видах страхования
    • Правах и обязанностях страхователя
    • Требованиях к страховым компаниям
    • Процедурах получения страховых выплат
    • И многом другом

    💬 Я помню контекст разговора! Вы можете задавать уточняющие вопросы:
    - "Что такое ОСАГО?"
    - "А что означает п. 2.1?"
    - "Расскажи подробнее об этом"

    Команды:
    /start - Показать это сообщение
    /help - Помощь
    /clear - Очистить историю разговора
    """
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
    ❓ Как использовать бота:

    1. Просто напишите свой вопрос о страховом законодательстве
    2. Бот найдет релевантную информацию в законодательных документах
    3. Вы получите ответ с указанием источников

    💡 Бот помнит контекст разговора!
    Вы можете задавать уточняющие вопросы:

    Пример диалога:
    👤 "Что такое ОСАГО?"
    🤖 [Краткий ответ]
    👤 "А что означает пункт 2.1?"
    🤖 [Ответ с учетом предыдущего контекста]
    👤 "Расскажи подробнее об этом"
    🤖 [Подробный ответ]

    Команды:
    /clear - Очистить историю и начать новый разговор
    /help - Показать эту справку
    """
    await update.message.reply_text(help_text)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear chat history for the user."""
    global chatbot

    if chatbot:
        user_id = str(update.effective_user.id)
        chatbot.clear_history(user_id)
        await update.message.reply_text("✅ История разговора очищена. Можете начать новый разговор!")
    else:
        await update.message.reply_text("⚠️ Бот еще не готов.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with questions."""
    global chatbot

    if chatbot is None:
        await update.message.reply_text(
            "⚠️ Система еще загружается. Попробуйте через несколько секунд."
        )
        return

    user_question = update.message.text
    user_name = update.effective_user.first_name
    user_id = str(update.effective_user.id)

    logger.info(f"Question from {user_name} (ID: {user_id}): {user_question}")

    # Send typing action
    await update.message.chat.send_action(action="typing")

    try:
        result = chatbot.ask(user_question, user_id=user_id)

        # Format response
        answer = result['answer']
        
        # Only add sources if the answer was based on document retrieval
        if result.get('has_sources') and result.get('sources'):
            sources = list(set(result['sources']))
            response = f"{answer}\n\n📚 Источники:\n"
            for source in sources:
                response += f"• {source}\n"
            
            # Telegram message limit is 4096 characters
            MAX_LENGTH = 4000
            
            if len(response) <= MAX_LENGTH:
                await update.message.reply_text(response)
            else:
                # Send answer and sources separately
                await update.message.reply_text(answer)
                sources_text = "📚 Источники:\n" + "\n".join(f"• {s}" for s in sources)
                await update.message.reply_text(sources_text)
        else:
            # Just send the answer without sources
            await update.message.reply_text(answer)

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Извините, произошла техническая ошибка при обработке вашего вопроса.\n\n"
            "Попробуйте:\n"
            "• Переформулировать вопрос\n"
            "• Использовать /clear для начала нового разговора\n"
            "• Задать вопрос на русском языке"
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")


def initialize_chatbot(docx_path, google_api_key, redis_url, model_name="gemini-1.5-flash", rebuild=False):
    """Initialize the RAG chatbot system."""
    global chatbot

    logger.info("Initializing RAG chatbot with Google Gemini...")

    chatbot = InsuranceLawChatbot(
        docx_files_path=docx_path,
        api_key=google_api_key,
        redis_url=redis_url
    )

    if rebuild:
        logger.info("Building new vector store...")
        chatbot.build(model_name=model_name)
    else:
        logger.info("Loading existing vector store...")
        try:
            chatbot.load_existing_vectorstore()
            chatbot.setup_chain(model_name=model_name)
        except Exception as e:
            logger.warning(f"Could not load existing vectorstore: {e}")
            logger.info("Building new vector store...")
            chatbot.build(model_name=model_name)

    logger.info("RAG chatbot ready!")


def main():
    """Start the bot."""
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "your-google-api-key")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    DOCX_PATH = os.getenv("DOCX_PATH", "./insurance_laws")
    MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash")

    REBUILD_VECTORSTORE = os.getenv("REBUILD_VECTORSTORE", "False").lower() == "true"

    initialize_chatbot(
        docx_path=DOCX_PATH,
        google_api_key=GOOGLE_API_KEY,
        redis_url=REDIS_URL,
        model_name=MODEL_NAME,
        rebuild=REBUILD_VECTORSTORE
    )

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot with Google Gemini...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()