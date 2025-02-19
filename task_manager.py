from database_manager import DatabaseManager
from task import Task
from datetime import date

class TaskManager:
    def __init__(self, user_id: int, db_manager: DatabaseManager):
        """
        Менеджер задач для конкретного пользователя.
        :param user_id: ID пользователя
        :param db_manager: Экземпляр DatabaseManager
        """
        self.user_id = user_id
        self.db_manager = db_manager

    def get_task_by_id(self, task_id):
        """Получает задачу по ID из базы данных"""
        task_data = self.db_manager.get_task_by_id(task_id)
        if task_data:
            return Task(*task_data)
        return None

    def add_task(self, task: Task):
        """ Добавляет задачу в БД """
        self.db_manager.add_task(self.user_id, task.name, task.date, task.time, task.recurrence)

    def delete_task(self, task_id: int):
        """ Удаляет задачу из БД """
        self.db_manager.delete_task(task_id)

    def get_all_tasks(self):
        """ Возвращает все задачи пользователя """
        tasks_data = self.db_manager.get_tasks(self.user_id)
        return [Task(task_id, user_id, name, date, time, recurrence) for task_id, user_id, name, date, time, recurrence in tasks_data]

    def get_today_tasks(self):
        """Возвращает задачи пользователя на сегодня и просроченные"""
        today = date.today().strftime("%Y-%m-%d")
        tasks_data = self.db_manager.get_tasks(self.user_id, max_date=today)
        return [Task(*task) for task in tasks_data]

    def update_task(self, task_id: int, new_date: str = None, new_time: str = None, new_recurrence: str = None, completed: bool = None):
        """ Обновляет параметры задачи """
        self.db_manager.update_task(task_id, new_date, new_time, new_recurrence, completed)
