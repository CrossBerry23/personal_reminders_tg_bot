import sqlite3
import aiosqlite
import datetime

class DatabaseManager:
    def __init__(self, db_path="tasks.db"):
        self.db_path = db_path
        self.initialize_database()

    def initialize_database(self):
        """Создает таблицу tasks, если она не существует"""
        query = """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            recurrence TEXT NOT NULL
        )
        """
        self.execute_query(query)

    def execute_query(self, query, params=(), fetchone=False, fetchall=False):
        """Выполняет запрос к БД"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)   
            result = None
            if fetchone:
                result = cursor.fetchone()
            elif fetchall:
                result = cursor.fetchall()
            return result

    def get_task_by_id(self, task_id):
        """Получает задачу по ID"""
        query = "SELECT id, user_id, name, date, time, recurrence FROM tasks WHERE id = ?"
        return self.execute_query(query, (task_id,), fetchone=True)

    def add_task(self, user_id, name, date, time, recurrence):
        """Добавляет новую задачу"""
        query = "INSERT INTO tasks (user_id, name, date, time, recurrence) VALUES (?, ?, ?, ?, ?)"
        self.execute_query(query, (user_id, name, date, time, recurrence))

    def get_tasks(self, user_id, max_date=None):
        """Получает все задачи пользователя. 
        Если передана max_date, то возвращает только задачи с этой датой или раньше (просроченные и сегодняшние).
        """
        query = "SELECT id, user_id, name, date, time, recurrence FROM tasks WHERE user_id = ?"
        params = [user_id]

        if max_date:
            query += " AND date <= ?"
            params.append(max_date)

        return self.execute_query(query, tuple(params), fetchall=True)

    def get_tasks_by_date(self, user_id, date):
        """Получает задачи пользователя на определённую дату"""
        query = "SELECT id, name, time, recurrence FROM tasks WHERE user_id = ? AND date = ?"
        return self.execute_query(query, (user_id, date), fetchall=True)

    def update_task(self, task):
        """Обновляет задачу в БД"""
        query = """
        UPDATE tasks 
        SET name = ?, date = ?, time = ?, recurrence = ? 
        WHERE id = ?
        """
        self.execute_query(query, (task.name, task.date, task.time, task.recurrence, task.task_id))

    def get_all_tasks(self):
        """Получает все задачи из базы данных"""
        query = "SELECT id, user_id, name, date, time, recurrence FROM tasks"
        return self.execute_query(query, fetchall=True)


    async def update_task_field(self, task_id, field, value):
        """Асинхронно обновляет одно поле задачи"""
        allowed_fields = ["name", "date", "time", "recurrence"]
        if field not in allowed_fields:
            raise ValueError(f"Недопустимое поле: {field}")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
            await db.commit()


    def delete_task(self, task_id):
        """Удаляет задачу"""
        query = "DELETE FROM tasks WHERE id = ?"
        self.execute_query(query, (task_id,))

    async def get_tasks_for_today(self):
        """Получаем задачи на сегодня"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        async with aiosqlite.connect("tasks.db") as db:
            async with db.execute("SELECT * FROM tasks WHERE date <= ? OR recurrence != 'once'", (today,)) as cursor:
                return await cursor.fetchall()