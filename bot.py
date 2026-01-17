import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from core import InsuranceLawChatbot  # Import your RAG module

# Load environment variables from .env file
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

Просто задайте свой вопрос, и я найду ответ в законодательных документах.

Команды:
/start - Показать это сообщение
/help - Помощь
"""
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
❓ Как использовать бота:

1. Просто напишите свой вопрос о страховом законодательстве
2. Бот найдет релевантную информацию в законодательных документах
3. Вы получите ответ с указанием источников

Примеры вопросов:
• Какие виды страхования существуют?
• Каковы права страхователя?
• Что такое обязательное страхование?
• Какие документы нужны для получения выплаты?

Если бот не может найти ответ, попробуйте переформулировать вопрос.
"""
    await update.message.reply_text(help_text)


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

    logger.info(f"Question from {user_name}: {user_question}")

    # Send typing action
    await update.message.chat.send_action(action="typing")

    try:
        # Get answer from RAG system
        result = chatbot.ask(user_question)

        # Format response
        answer = result['answer']
        sources = list(set(result['sources']))

        response = f"{answer}\n\n📚 Источники:\n"
        for source in sources:
            response += f"• {source}\n"

        # Telegram message limit is 4096 characters
        MAX_LENGTH = 4000  # Leave some margin

        if len(response) <= MAX_LENGTH:
            await update.message.reply_text(response)
        else:
            # Split into multiple messages
            # First send the answer
            if len(answer) <= MAX_LENGTH:
                await update.message.reply_text(answer)
                # Then send sources separately
                sources_text = "📚 Источники:\n" + "\n".join(f"• {s}" for s in sources)
                await update.message.reply_text(sources_text)
            else:
                # Answer is too long, split it
                parts = []
                current_part = ""

                # Split by sentences
                sentences = answer.split('. ')
                for sentence in sentences:
                    if len(current_part) + len(sentence) + 2 < MAX_LENGTH:
                        current_part += sentence + '. '
                    else:
                        if current_part:
                            parts.append(current_part)
                        current_part = sentence + '. '

                if current_part:
                    parts.append(current_part)

                # Send all parts
                for i, part in enumerate(parts):
                    if i == 0:
                        await update.message.reply_text(part)
                    else:
                        await update.message.reply_text(f"(продолжение)\n\n{part}")

                # Send sources
                sources_text = "📚 Источники:\n" + "\n".join(f"• {s}" for s in sources)
                await update.message.reply_text(sources_text)

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        await update.message.reply_text(
            "❌ Извините, произошла ошибка при обработке вашего вопроса. "
            "Попробуйте переформулировать или обратитесь позже."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")


def initialize_chatbot(docx_path, mistral_api_key, model_name="mistral-large-latest", rebuild=False):
    """
    Initialize the RAG chatbot system.

    Args:
        docx_path: Path to .docx files folder
        mistral_api_key: Mistral API key
        model_name: Mistral model to use
        rebuild: If True, rebuild vector store. If False, load existing.
    """
    global chatbot

    logger.info("Initializing RAG chatbot...")

    chatbot = InsuranceLawChatbot(
        docx_files_path=docx_path,
        api_key=mistral_api_key
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
    # Configuration - use environment variables or config file
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "your-mistral-api-key")
    DOCX_PATH = os.getenv("DOCX_PATH", "./insurance_laws")
    MODEL_NAME = os.getenv("MODEL_NAME", "mistral-large-latest")

    # Set to True for first run, False for subsequent runs
    REBUILD_VECTORSTORE = os.getenv("REBUILD_VECTORSTORE", "False").lower() == "true"

    # Initialize the RAG system
    initialize_chatbot(
        docx_path=DOCX_PATH,
        mistral_api_key=MISTRAL_API_KEY,
        model_name=MODEL_NAME,
        rebuild=REBUILD_VECTORSTORE
    )

    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()