from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot_handler import BotHandler
import logging
import os
from dotenv import load_dotenv
import asyncio
from scheduler import Scheduler

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # Подгрузка переменной окружения
application = Application.builder().token(TOKEN).build()
bot_handler = BotHandler() # Обработчик

scheduler = Scheduler(application.bot, bot_handler.db_manager) # Планировщик

async def run_scheduler():
    """Фоновый запуск планировщика"""
    await scheduler.start()

def main():
    """Запуск бота"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_scheduler())

    # Обработчики команд
    application.add_handler(CommandHandler("start", bot_handler.main_menu))
    
    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(bot_handler.calendar_handler, pattern="^cbcal_.*"))
    application.add_handler(CallbackQueryHandler(bot_handler.period_choice_handler, pattern="^(once|daily|weekly|monthly|yearly|custom)$"))
    application.add_handler(CallbackQueryHandler(bot_handler.handle_task_selection, pattern=r"^task_\d+$"))
    application.add_handler(CallbackQueryHandler(bot_handler.task_edit_handler, pattern="^(complete_task|edit_task|back_to_menu)$"))
    application.add_handler(CallbackQueryHandler(bot_handler.confirm_task_completion, pattern="^(confirm_complete|cancel)$"))
    application.add_handler(CallbackQueryHandler(bot_handler.edit_task, pattern="^(edit_name|edit_date|edit_time|edit_recurrence)$"))
    application.add_handler(CallbackQueryHandler(bot_handler.handle_recurrence_change, pattern=r"^recurrence_"))
    application.add_handler(CallbackQueryHandler(bot_handler.button_handler, pattern="^(list_today|list|add|main_menu)$"))

    # Обработчик текстового ввода
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.handle_text_input))

    # Запускаем чат-бота
    application.run_polling()

if __name__ == "__main__":
    main()
