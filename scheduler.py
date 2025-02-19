import asyncio
import datetime
import logging
from database_manager import DatabaseManager
from task import Task

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.notified_tasks_30min = set()  
        self.notified_missed_tasks = set()  
        self.has_active_tasks = False  

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
        self.has_active_tasks = len(tasks) > 0  

        today_tasks = []
        missed_tasks = []

        for task_data in tasks:
            task_id, user_id, name, date, time, recurrence = task_data
            task = Task(task_id, user_id, name, date, time, recurrence)
            task_time = datetime.datetime.strptime(f"{task.date} {task.time}", "%Y-%m-%d %H:%M")
            time_diff = (task_time - now).total_seconds()

            if time_diff < 0 and not task.name.startswith("❌"):  
                new_name = f"❌ {task.name}"
                await self.db_manager.update_task_field(task_id, "name", new_name)
                task.name = new_name  

            if task.recurrence != "once":
                await self.handle_recurrence(task)

            if time_diff < 0:
                if task_id not in self.notified_missed_tasks:
                    missed_tasks.append(task)
                    self.notified_missed_tasks.add(task_id)
                continue  

            if date == today_str:
                today_tasks.append(task)

            if time_diff < 60:  
                await self.bot.send_message(chat_id=user_id, text=f"⏰ Задача '{task.name}', назначенная на {task.date} {task.time}, требует выполнения.")
                self.notified_tasks_30min.discard(task_id)

            elif 1800 >= time_diff > 1740 and task_id not in self.notified_tasks_30min:  
                await self.bot.send_message(chat_id=user_id, text=f"⏳ Через 30 минут необходимо выполнить задачу '{task.name}' в {task.time}.")
                self.notified_tasks_30min.add(task_id)

        if now.hour == 0 and now.minute in {0, 1}:
            await self.send_midnight_notifications(today_tasks, missed_tasks)

    async def send_midnight_notifications(self, today_tasks, missed_tasks):
        """Отправляет уведомления в 00:00: задачи на сегодня и пропущенные задачи"""
        sent_users = set()

        for task in today_tasks:
            if task.user_id not in sent_users:
                await self.bot.send_message(task.user_id, "📅 Сегодняшние задачи:")
                sent_users.add(task.user_id)
            await self.bot.send_message(task.user_id, f"✅ '{task.name}' в {task.time}.")

        for task in missed_tasks:
            await self.bot.send_message(task.user_id, f"⚠️ Задача '{task.name}', назначенная на {task.date} {task.time}, была пропущена.")

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
        similar_tasks = [
            existing_task for existing_task in existing_tasks
            if existing_task[1] == task.user_id and  
            existing_task[2] == task.name and  
            existing_task[4] == task.time and  
            existing_task[5] == task.recurrence  
        ]

        if len(similar_tasks) >= 2:
            logger.info(f"Для задачи '{task.name}' уже есть две копии, создание не требуется.")
            return  

        logger.info(f"Добавление повторяющейся задачи '{task.name}' -> {next_date_str}")
        self.db_manager.add_task(task.user_id, task.name, next_date_str, task.time, task.recurrence)
