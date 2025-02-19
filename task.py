class Task:
    def __init__(self, task_id: int, user_id: int, name: str, date: str, time: str, recurrence: str = None):
        """
        Класс задачи.
        :param task_id: ID задачи в БД (если уже сохранена)
        :param user_id: ID пользователя
        :param name: Название задачи
        :param date: Дата выполнения (в формате YYYY-MM-DD)
        :param time: Время выполнения (в формате HH:MM)
        :param recurrence: Периодичность ("once", "daily", "weekly", "monthly", "yearly" None)
        
        """
        self.task_id = task_id
        self.user_id = user_id
        self.name = name
        self.date = date
        self.time = time
        self.recurrence = recurrence

    def update_time(self, new_date: str, new_time: str, new_recurrence: str = None):
        """ Обновляет дату, время и (если нужно) периодичность задачи """
        self.date = new_date
        self.time = new_time
        self.recurrence = new_recurrence