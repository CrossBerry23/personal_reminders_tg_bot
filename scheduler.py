import asyncio
import datetime
import logging
from database_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.notified_tasks_30min = set()  
        self.notified_missed_tasks = set()  
        self.has_active_tasks = False
        self.midnight_notified = False

    async def start(self):
        """Функция запуска планировщика"""
        logger.info("Запуск планировщика...")
        while True:
            await self.check_tasks()
            sleep_time = 60 if self.has_active_tasks else 600  
            await asyncio.sleep(sleep_time)

    async def check_tasks(self):
        """Функция проверок планировщика"""
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        logger.info(f"Проверка задач на {now.strftime('%Y-%m-%d %H:%M:%S')}")
        tasks = await self.db_manager.get_tasks_for_today()
        outdated_tasks = await self.db_manager.get_all_tasks_with_prefix("❌")
        self.has_active_tasks = len(tasks) > 0  
        users_with_tasks = set()

        for task in tasks:
            task_time = datetime.datetime.strptime(f"{task.date} {task.time}", "%Y-%m-%d %H:%M")
            time_diff = (task_time - now).total_seconds()

            if time_diff < 0 and not task.name.startswith("❌"):  
                task.name = f"❌ {task.name}"
                await self.db_manager.update_task_field(task.task_id, "name", task.name)

            if task.date == today_str or time_diff < 0:
                users_with_tasks.add(task.user_id)

            if 0 < time_diff < 60:
                await self.bot.send_message(chat_id=task.user_id, text=f"⏰ Задача '{task.name}', назначенная на {task.date} {task.time}, требует выполнения.")
            
            elif 1800 >= time_diff > 1740:
                await self.bot.send_message(chat_id=task.user_id, text=f"⏳ Через 30 минут необходимо выполнить задачу '{task.name}' в {task.time}.")

        for task in outdated_tasks:
            task_time = datetime.datetime.strptime(f"{task.date} {task.time}", "%Y-%m-%d %H:%M")
            time_diff = (task_time - now).total_seconds()

            if time_diff >= 0:
                new_name = task.name[2:]
                await self.db_manager.update_task_field(task.task_id, "name", new_name)
                logger.info(f"✅ Убрали ❌ у задачи: {new_name} (Обновлённая дата)")

        if now.hour == 0 and now.minute in {0, 1} and not self.midnight_notified:
            await self.send_midnight_notifications(users_with_tasks)
            self.midnight_notified = True

        if now.hour == 1:
            self.midnight_notified = False

    async def send_midnight_notifications(self, users_with_tasks):
        """Отправляет уведомления в 00:00: задачи на сегодня и пропущенные задачи"""
        all_users = await self.db_manager.get_all_users()
        all_tasks = await self.db_manager.get_tasks_for_today()

        user_today_tasks = {}
        user_missed_tasks = {}

        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        for task in all_tasks:
            task_time = datetime.datetime.strptime(f"{task.date} {task.time}", "%Y-%m-%d %H:%M")
            time_diff = (task_time - now).total_seconds()

            if time_diff < 0:
                user_missed_tasks.setdefault(task.user_id, []).append(f"⚠️ {task.name} ({task.date} {task.time})")
            elif task.date == today_str:
                user_today_tasks.setdefault(task.user_id, []).append(f"✅ {task.name} в {task.time}")

        for user_id in all_users:
            message_parts = []

            if user_id in user_today_tasks:
                message_parts.append("📅 Сегодняшние задачи:\n" + "\n".join(user_today_tasks[user_id]))

            if user_id in user_missed_tasks:
                message_parts.append("⚠️ Пропущенные задачи:\n" + "\n".join(user_missed_tasks[user_id]))

            if not message_parts:
                message_parts.append("✅ На сегодня у вас нет задач.")

            logger.info(f"Отправляем пользователю {user_id}: {message_parts}")
            await self.bot.send_message(user_id, "\n\n".join(message_parts))

    async def handle_recurrence(self, task):
        """Создаёт новую задачу для повторяющихся событий"""
        if task.recurrence == "once":
            return  

        current_date = datetime.datetime.strptime(task.date, "%Y-%m-%d")
        if task.recurrence == "daily":
            next_date = current_date + datetime.timedelta(days=1)
        elif task.recurrence == "weekly":
            next_date = current_date + datetime.timedelta(weeks=1)
        elif task.recurrence == "monthly":
            next_date = current_date.replace(month=current_date.month + 1) if current_date.month < 12 else current_date.replace(year=current_date.year + 1, month=1)
        elif task.recurrence == "yearly":
            next_date = current_date.replace(year=current_date.year + 1)
        else:
            return  

        next_date_str = next_date.strftime("%Y-%m-%d")
        existing_tasks = await self.db_manager.get_tasks_for_today()
        clean_task_name = task.name.lstrip("❌ ").strip()
        similar_tasks = [
            existing_task for existing_task in existing_tasks
            if existing_task.user_id == task.user_id and  
            existing_task.name.lstrip("❌ ").strip() == clean_task_name and
            existing_task.time == task.time and  
            existing_task.recurrence == task.recurrence
        ]

        if len(similar_tasks) >= 2:
            return  

        logger.info(f"Добавление повторяющейся задачи '{clean_task_name}' -> {next_date_str}")
        await self.db_manager.add_task(task.user_id, clean_task_name, next_date_str, task.time, task.recurrence)
