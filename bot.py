"""
Insurance Law Consultation Bot for Telegram
Professional AI assistant for insurance company employees
Powered by Google Gemini and RAG architecture
"""

import os
import logging
import warnings
from typing import Optional

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ChatAction
from core import InsuranceLawChatbot


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global chatbot instance
chatbot: Optional[InsuranceLawChatbot] = None

# Conversation states
AWAITING_QUESTION = 1
AWAITING_FEEDBACK = 2


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start command - welcome message and brief instructions.
    """
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "сотрудник"
    
    logger.info(f"👤 User started: {user_name} (ID: {user_id})")
    
    welcome_message = f"""
╔══════════════════════════════════════════════════════════╗
║     📋 КОНСУЛЬТАЦИОННЫЙ АССИСТЕНТ                        ║
║     По страховому законодательству РК                    ║
╚══════════════════════════════════════════════════════════╝

Здравствуйте, {user_name}! 👋

Я помощник для сотрудников страховой компании. Помогу вам разобраться с нормативными требованиями страхового законодательства Республики Казахстан.

✨ Я могу помочь с:
  ✓ Видами страхования и их особенностями
  ✓ Правами и обязанностями участников
  ✓ Требованиями к страховым компаниям
  ✓ Процедурами страховых выплат
  ✓ Другими вопросами по страховому законодательству РК

💡 Как использовать:
  1️⃣ Просто напишите свой вопрос
  2️⃣ Я найду информацию в документах
  3️⃣ Получите ответ с ссылками на законы

📌 Помню контекст разговора - можете задавать уточняющие вопросы!

Пример:
  👤 "Какие виды ОСАГО существуют?"
  🤖 "Ответ с ссылками на статьи..."
  👤 "А что означает пункт 2.1?"
  🤖 "Ответ с учетом предыдущего контекста"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Нажмите /help для подробной справки или просто начните задавать вопросы! 😊
"""
    
    keyboard = [
        [InlineKeyboardButton("❓ Справка", callback_data="help"),
         InlineKeyboardButton("🗑️ Очистить", callback_data="clear")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Status command - show knowledge base information.
        """
        global chatbot
        user_id = update.effective_user.id

        logger.info(f"User requested status: {user_id}")

        if not chatbot:
            await update.message.reply_text("⚠️ Ассистент еще инициализируется. Попробуйте позже.")
            return

        try:
            # Try to get status from chatbot, fall back to KnowledgeManager
            try:
                status = chatbot.get_knowledge_base_status()
            except AttributeError:
                from manager import KnowledgeManager
                km = KnowledgeManager()
                status = km.get_knowledge_base_info()

            status_message = f"""
╔══════════════════════════════════════════════════════════╗
║     📊 СТАТУС БАЗЫ ЗНАНИЙ                                ║
╚══════════════════════════════════════════════════════════╝

📚 Загруженные документы: {status['total_documents']}
📖 Терминов в словаре: {status['terminology_count']}
🕐 Последнее обновление: {status['last_update'] or 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ДОКУМЕНТЫ:
"""

            if status['documents']:
                for doc_name, doc_info in status['documents'].items():
                    status_message += f"\n  • {doc_name}\n    Тип: {doc_info['type']}\n    Загружен: {doc_info['loaded_at']}\n"

            status_message += "\n✅ Система полностью готова к работе"

            await update.message.reply_text(status_message)

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            await update.message.reply_text(f"❌ Ошибка получения статуса: {str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Help command - detailed usage instructions.
    """
    logger.info(f"User requested help: {update.effective_user.id}")
    
    help_text = """
╔══════════════════════════════════════════════════════════╗
║     ❓ СПРАВКА ПО ИСПОЛЬЗОВАНИЮ АССИСТЕНТА              ║
╚══════════════════════════════════════════════════════════╝

📖 ОСНОВНЫЕ ВОЗМОЖНОСТИ:

1. 🔍 Поиск информации
   • Просто напишите вопрос о страховом законодательстве
   • Ассистент найдет релевантную информацию в документах
   • Получите точный ответ с ссылками на статьи

2. 💬 Контекст беседы
   • Я помню всю историю нашего разговора
   • Можете задавать уточняющие вопросы
   • Ответы учитывают предыдущий контекст

3. 📚 Точность информации
   • Все ответы основаны на загруженных документах
   • Указываются конкретные статьи и пункты
   • Используется правильная страховая терминология РК

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 ПРИМЕРЫ ВОПРОСОВ:

✓ "Что такое ОСАГО и кто его должен оформить?"
✓ "Какие требования предъявляются к страховщику?"
✓ "Какой порядок получения страховой выплаты?"
✓ "Какие виды страхования предусмотрены законом?"
✓ "Какие льготы предусмотрены для застрахованных лиц?"
✓ "Расскажи подробнее о требованиях капитала страховщика"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ ДОСТУПНЫЕ КОМАНДЫ:

/start     - Начать работу с ассистентом
/help      - Показать эту справку
/status    - Статус базы знаний
/clear     - Очистить историю консультации
/feedback  - Отправить обратную связь

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 СОВЕТЫ ДЛЯ ЛУЧШИХ РЕЗУЛЬТАТОВ:

1. Будьте конкретны - чем точнее вопрос, тем точнее ответ
2. Используйте правильные термины - это поможет найти нужную информацию
3. Задавайте уточняющие вопросы - контекст помогает
4. Для деталей просите уточнения - "расскажи подробнее"

⚠️ ОГРАНИЧЕНИЯ:

• Ассистент отвечает только на основе загруженных документов
• Для общей юридической консультации обратитесь к юридическому отделу
• При необходимости актуальной информации проверяйте adilet.zan.kz

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Готовы начать? Просто напишите ваш первый вопрос! 👇
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text)
    else:
        await update.message.reply_text(help_text)

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Status command - show knowledge base information.
        """
        global chatbot
        user_id = update.effective_user.id

        logger.info(f"User requested status: {user_id}")

        if not chatbot:
            await update.message.reply_text("⚠️ Ассистент еще инициализируется. Попробуйте позже.")
            return

        try:
            # Try to get status from chatbot, fall back to KnowledgeManager
            try:
                status = chatbot.get_knowledge_base_status()
            except AttributeError:
                from manager import KnowledgeManager
                km = KnowledgeManager()
                status = km.get_knowledge_base_info()

            status_message = f"""
╔══════════════════════════════════════════════════════════╗
║     📊 СТАТУС БАЗЫ ЗНАНИЙ                                ║
╚══════════════════════════════════════════════════════════╝

📚 Загруженные документы: {status['total_documents']}
📖 Терминов в словаре: {status['terminology_count']}
🕐 Последнее обновление: {status['last_update'] or 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ДОКУМЕНТЫ:
"""

            if status['documents']:
                for doc_name, doc_info in status['documents'].items():
                    status_message += f"\n  • {doc_name}\n    Тип: {doc_info['type']}\n    Загружен: {doc_info['loaded_at']}\n"

            status_message += "\n✅ Система полностью готова к работе"

            await update.message.reply_text(status_message)

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            await update.message.reply_text(f"❌ Ошибка получения статуса: {str(e)}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Clear command - clear user's chat history.
    """
    global chatbot
    user_id = str(update.effective_user.id)
    
    logger.info(f"User clearing history: {user_id}")
    
    if not chatbot:
        await update.message.reply_text("⚠️ Ассистент еще не готов.")
        return
    
    try:
        chatbot.clear_history(user_id)
        
        clear_message = """
✅ История консультации успешно очищена!

🔄 Можете начать новый сеанс вопросов и ответов.
Все предыдущие консультации забыты, начинаем заново.

Что вас интересует? 👇
"""
        
        await update.message.reply_text(clear_message)
        logger.info(f"Cleared history for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        await update.message.reply_text(f"❌ Ошибка очистки истории: {str(e)}")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Feedback command - collect user feedback.
    """
    feedback_message = """
📝 Спасибо за обратную связь!

Пожалуйста, напишите ваше мнение о работе ассистента:
  • Полезность ответов
  • Точность информации
  • Удобство использования
  • Предложения по улучшению

Ваш отзыв очень важен для нас! 💙
"""
    
    await update.message.reply_text(feedback_message)
    return AWAITING_FEEDBACK


# ============================================================================
# MESSAGE HANDLERS
# ============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main message handler - process user questions.
    """
    global chatbot
    
    if chatbot is None:
        await update.message.reply_text(
            "⚠️ Ассистент еще инициализируется. Попробуйте через несколько секунд."
        )
        return
    
    user_question = update.message.text
    user_name = update.effective_user.first_name or "сотрудник"
    user_id = str(update.effective_user.id)
    
    logger.info(f"Question from {user_name} (ID: {user_id}): {user_question}")
    
    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)
    
    try:
        # Get answer from chatbot
        result = chatbot.ask(user_question, user_id=user_id)
        
        answer = result['answer']
        has_sources = result.get('has_sources', False)
        sources = result.get('sources', [])
        
        # Format response
        if has_sources and sources:
            # Answer with sources
            sources_list = list(set(sources))
            response = f"{answer}\n\n📄 Нормативные источники:\n"
            
            for source in sources_list:
                response += f"  • {source}\n"
            
            # Check Telegram message limit
            MAX_LENGTH = 4096
            
            if len(response) <= MAX_LENGTH:
                await update.message.reply_text(response)
            else:
                # Send answer and sources separately
                await update.message.reply_text(answer)
                
                sources_text = "📄 Нормативные источники:\n"
                for source in sources_list:
                    sources_text += f"  • {source}\n"
                
                await update.message.reply_text(sources_text)
        else:
            # Answer without sources
            await update.message.reply_text(answer)
        
        logger.info(f"Answer sent to {user_name}")
    
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        
        error_message = """
❌ Ошибка при обработке вопроса.

Попробуйте:
  • Переформулировать вопрос более четко
  • Использовать /clear для начала новой консультации
  • Убедиться, что вопрос касается страхового законодательства РК

Если проблема повторяется, обратитесь к администратору.
"""
        
        await update.message.reply_text(error_message)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle user feedback.
    """
    user_feedback = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"Feedback from user {user_id}: {user_feedback}")
    
    # Save feedback to file
    try:
        with open('feedback.log', 'a', encoding='utf-8') as f:
            f.write(f"[{user_id}] {user_feedback}\n")
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
    
    feedback_thanks = """
✅ Спасибо за вашу обратную связь!

Ваше мнение очень помогает улучшению ассистента. 💙

Есть еще вопросы по страховому законодательству? 👇
"""
    
    await update.message.reply_text(feedback_thanks)
    
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors in the bot.
    """
    logger.error(f"Exception while handling an update: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла критическая ошибка. Обратитесь к администратору."
            )
    except Exception as e:
        logger.error(f"Error sending error message: {e}")


# ============================================================================
# INITIALIZATION
# ============================================================================
def initialize_chatbot(
        docx_path: str,
        google_api_key: str,
        redis_url: str,
        model_name: str = "gemini-1.5-flash",
        rebuild: bool = False
) -> None:
    """
    Initialize the RAG chatbot system.

    Args:
        docx_path: Path to DOCX documents folder
        google_api_key: Google Gemini API key
        redis_url: Redis connection URL
        model_name: LLM model to use
        rebuild: Force rebuild of vector store
    """
    global chatbot

    logger.info("=" * 60)
    logger.info("🚀 Инициализация консультационного ассистента...")
    logger.info("=" * 60)

    try:
        chatbot = InsuranceLawChatbot(
            docx_files_path=docx_path,
            api_key=google_api_key,
            redis_url=redis_url
        )

        if rebuild:
            logger.info("🔄 Построение новой системы знаний...")
            chatbot.build(model_name=model_name)
        else:
            logger.info("📚 Загрузка системы знаний...")
            try:
                chatbot.build(model_name=model_name)
            except Exception as e:
                logger.warning(f"Не удалось загрузить существующую систему: {e}")
                logger.info("Построение новой системы...")
                chatbot.build(model_name=model_name)

        # Display knowledge base status
        try:
            status = chatbot.get_knowledge_base_status()
            logger.info(f"📊 База знаний инициализирована:")
            logger.info(f"   • Документов: {status['total_documents']}")
            logger.info(f"   • Терминов: {status['terminology_count']}")
            logger.info(f"   • Последнее обновление: {status['last_update']}")
        except AttributeError:
            # Fall back if method doesn't exist
            from manager import KnowledgeManager
            km = KnowledgeManager()
            status = km.get_knowledge_base_info()
            logger.info(f"📊 База знаний инициализирована:")
            logger.info(f"   • Документов: {status['total_documents']}")
            logger.info(f"   • Терминов: {status['terminology_count']}")
            logger.info(f"   • Последнее обновление: {status['last_update']}")

        logger.info("=" * 60)
        logger.info("✅ АССИСТЕНТ ГОТОВ К РАБОТЕ!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации: {e}", exc_info=True)
        raise


async def post_init(application: Application) -> None:
    """
    Post-initialization setup.
    """
    logger.info("Bot application initialized successfully")


def main() -> None:
    """
    Start the Telegram bot.
    """
    # Get configuration from environment
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    DOCX_PATH = os.getenv("DOCX_PATH", "./insurance_laws")
    MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash")
    REBUILD_VECTORSTORE = os.getenv("REBUILD_VECTORSTORE", "False").lower() == "true"
    
    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in environment")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY not set in environment")
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    # Initialize chatbot
    initialize_chatbot(
        docx_path=DOCX_PATH,
        google_api_key=GOOGLE_API_KEY,
        redis_url=REDIS_URL,
        model_name=MODEL_NAME,
        rebuild=REBUILD_VECTORSTORE
    )
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add conversation handler for feedback
    feedback_handler = ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_command)],
        states={
            AWAITING_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)]
        },
        fallbacks=[CommandHandler("help", help_command)]
    )
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(feedback_handler)
    
    # Message handler for questions
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Post-initialization
    application.post_init = post_init
    
    # Start the bot
    logger.info("🌐 Запуск Telegram бота...")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop the bot")
    logger.info("=" * 60)
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
