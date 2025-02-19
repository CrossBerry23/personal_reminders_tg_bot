from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
import re
from database_manager import DatabaseManager
from task_manager import TaskManager

class BotHandler:
    def __init__(self):
        self.db_manager = DatabaseManager()

    async def main_menu(self, update: Update, context: CallbackContext) -> None:
        """Главное меню бота"""
        keyboard = [
            [InlineKeyboardButton("📅 Просмотр задач на сегодня", callback_data="list_today")],
            [InlineKeyboardButton("📋 Просмотр всех задач", callback_data="list")],
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.message.edit_text("Выберите действие: ⚙️", reply_markup=reply_markup)
            await update.callback_query.answer()
        else:
            await update.message.reply_text("Выберите действие: ⚙️", reply_markup=reply_markup)

    async def button_handler(self, update: Update, context: CallbackContext) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        user_id = query.message.chat_id
        task_manager = TaskManager(user_id, self.db_manager)
        
        await query.answer()

        if query.data == 'list_today':
            tasks = task_manager.get_today_tasks()
            await self.show_tasks(update, tasks)

        elif query.data == 'list':
            tasks = task_manager.get_all_tasks()
            await self.show_tasks(update, tasks)

        elif query.data == 'add':
            await query.message.delete()
            await context.bot.send_message(chat_id=user_id, text="Введите название новой задачи:")
            context.user_data['adding_task'] = True

        elif query.data == 'main_menu':
            await self.main_menu(update, context)

    async def show_tasks(self, update: Update, tasks):
        """Выводит список задач в виде inline-кнопок"""
        if not tasks:
            await update.callback_query.message.reply_text("📭 Нет активных задач.")
            await self.main_menu(update, None)
            return

        keyboard = [[InlineKeyboardButton(f"{task.name} ({task.date} {task.time})", callback_data=f"task_{task.task_id}")] for task in tasks]
        keyboard.append([InlineKeyboardButton("🔙 Вернуться в меню", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text("📋 Ваши задачи:", reply_markup=reply_markup)

    async def handle_text_input(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает текстовый ввод (название задачи, время, произвольную периодичность)"""
        text = update.message.text.strip()

        if context.user_data.get('waiting_for_time'):
            if re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text):
                context.user_data["task_time"] = text
                context.user_data["waiting_for_time"] = False

                keyboard = [
                    [InlineKeyboardButton("Разовая", callback_data="once")],
                    [InlineKeyboardButton("Каждый день", callback_data="daily")],
                    [InlineKeyboardButton("Раз в неделю", callback_data="weekly")],
                    [InlineKeyboardButton("Раз в месяц", callback_data="monthly")],
                    [InlineKeyboardButton("Раз в год", callback_data="yearly")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Выберите периодичность задачи:", reply_markup=reply_markup)
            else:
                await update.message.reply_text("❌ Некорректный формат. Введите время в формате ЧЧ:ММ (например, 09:45):")
            return

        if context.user_data.get("editing_task"):
            task = context.user_data.get("selected_task")
            edit_type = context.user_data.get("edit_type")

            if not task:
                await update.message.reply_text("❌ Ошибка: Задача не выбрана.")
                await self.main_menu(update, context)
                return

            if edit_type == "name":
                task.name = text
            elif edit_type == "time":
                if re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text):
                    task.time = text
                else:
                    await update.message.reply_text("❌ Некорректный формат времени. Введите ЧЧ:ММ (например, 09:45).")
                    return
            else:
                await update.message.reply_text("❌ Некорректный ввод.")
                return
            
            self.db_manager.update_task(task)
            context.user_data["selected_task"] = task
            edit_labels = {"name": "Имя", "time": "Время"}
            edit_label = edit_labels.get(edit_type, edit_type.capitalize())
            await update.message.reply_text(f"✅ {edit_label} изменено.")

            context.user_data.pop("editing_task")
            context.user_data.pop("edit_type")
            await self.main_menu(update, context)
            return

        if context.user_data.get('adding_task'):
            context.user_data['task_name'] = text
            context.user_data['adding_task'] = False
            await update.message.reply_text(f"Название задачи '{text}' сохранено. Теперь выберите дату выполнения.")
            await self.ask_for_date(update, context)

    async def ask_for_date(self, update: Update, context: CallbackContext) -> None:
        """Запускает календарь для выбора даты"""
        query = update.callback_query 
        message = query.message if query else update.message

        if query:
            await query.answer()
            await query.message.delete()

        if message is None:
            return  # Защита от возможных ошибок

        calendar, step = DetailedTelegramCalendar(calendar_id="calendar").build()
        await message.reply_text(f"Выберите {LSTEP[step]}", reply_markup=calendar)

    async def handle_recurrence_change(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает изменение периодичности задачи"""
        query = update.callback_query
        recurrence_mapping = {
            "recurrence_once": "once",
            "recurrence_daily": "daily",
            "recurrence_weekly": "weekly",
            "recurrence_monthly": "monthly",
            "recurrence_yearly": "yearly",
        }

        new_recurrence = recurrence_mapping.get(query.data)
        task = context.user_data.get("selected_task")

        if task and new_recurrence:
            task.recurrence = new_recurrence
            self.db_manager.update_task(task)
            context.user_data["selected_task"] = task
            await query.message.reply_text(f"✅ Периодичность изменена на '{self.recurrence_name(new_recurrence)}'.")
        else:
            await query.message.reply_text("❌ Ошибка: Задача не найдена.")
        await self.main_menu(update, context)


    async def calendar_handler(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает выбор даты из календаря"""
        query = update.callback_query
        result, key, step = DetailedTelegramCalendar(calendar_id="calendar").process(query.data)

        if not result and key:
            await query.message.edit_text(f"Выберите {LSTEP[step]}", reply_markup=key)
            return

        if result:
            if context.user_data.get("editing_date"):
                task = context.user_data.get("selected_task")
                if task:
                    task.date = result
                    self.db_manager.update_task(task)
                    context.user_data["selected_task"] = task
                    context.user_data.pop("editing_date")
                    await query.message.reply_text(f"📅 Дата задачи изменена на {result}.")
                else:
                    await query.message.reply_text("❌ Ошибка: Задача не выбрана.")
                await self.main_menu(update, context)
            else:
                context.user_data["task_date"] = result
                context.user_data["waiting_for_time"] = True
                await query.message.edit_text(f"📅 Дата задачи установлена: {result}\n⌨ Теперь введите время в формате ЧЧ:ММ (например, 17:37):")
        await query.answer()

    async def period_choice_handler(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает выбор периодичности задачи"""
        query = update.callback_query
        recurrence = query.data if query.data != "custom" else None
        context.user_data["task_recurrence"] = recurrence

        if recurrence == "custom":
            await query.message.edit_text("✏ Введите произвольную периодичность (пример: `1y 2m 1w 3d`):")
            context.user_data["waiting_for_custom_recurrence"] = True
        else:
            await self.save_task(update, context)

    async def save_task(self, update: Update, context: CallbackContext) -> None:
        """Сохраняет задачу в базу данных"""
        user_id = update.effective_chat.id
        user_data = context.user_data
        task_name = user_data.get("task_name")
        task_date = user_data.get("task_date")
        task_time = user_data.get("task_time")
        task_recurrence = user_data.get("task_recurrence")

        if not all([task_name, task_date, task_time, task_recurrence]):
            error_message = "❌ Ошибка: не все данные заполнены."
            if update.callback_query:
                await update.callback_query.message.edit_text(error_message)
            else:
                await update.message.reply_text(error_message)
            return

        self.db_manager.add_task(user_id, task_name, task_date, task_time, task_recurrence)
        confirmation_text = "✅ Задача успешно сохранена!"

        if update.callback_query:
            await update.callback_query.message.reply_text(confirmation_text)
        else:
            await update.message.reply_text(confirmation_text)

        user_data.clear()
        await self.main_menu(update, context)

    @staticmethod
    def recurrence_name(recurrence: str) -> str:
        """Преобразует код периодичности в читаемое название"""
        recurrence_mapping = {
            "once": "Единожды",
            "daily": "Каждый день",
            "weekly": "Раз в неделю",
            "monthly": "Раз в месяц",
            "yearly": "Раз в год"
        }
        return recurrence_mapping.get(recurrence, "Неизвестный тип")

    async def handle_task_selection(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает выбор задачи и открывает меню task_edit"""
        query = update.callback_query
        task_id = query.data.replace("task_", "")
        user_id = query.message.chat_id
        task_manager = TaskManager(user_id, self.db_manager)
        task = task_manager.get_task_by_id(task_id)
        if not task:
            await query.message.reply_text("❌ Задача не найдена.")
            await self.main_menu(update, context)
            return

        context.user_data["selected_task"] = task
        keyboard = [
            [InlineKeyboardButton("✅ Завершить задачу", callback_data="complete_task")],
            [InlineKeyboardButton("✏ Редактировать", callback_data="edit_task")],
            [InlineKeyboardButton("🔙 Вернуться в меню", callback_data="back_to_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            f"📌 Задача: *{task.name}*\n📅 Дата: {task.date}\n⏰ Время: {task.time}\n🔁 Периодичность: {self.recurrence_name(task.recurrence)}",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def task_edit_handler(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает действия в меню task_edit"""
        query = update.callback_query
        task = context.user_data.get("selected_task")

        if not task:
            await query.message.reply_text("❌ Ошибка: Задача не выбрана.")
            await self.main_menu(update, context)
            return

        if query.data == "complete_task":
            keyboard = [
                [InlineKeyboardButton("✅ Да", callback_data="confirm_complete")],
                [InlineKeyboardButton("❌ Нет", callback_data="cancel")],
            ]
            await query.message.edit_text("Вы уверены, что хотите завершить задачу?", reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == "edit_task":
            keyboard = [
                [InlineKeyboardButton("✏ Изменить название", callback_data="edit_name")],
                [InlineKeyboardButton("📅 Изменить дату", callback_data="edit_date")],
                [InlineKeyboardButton("⏰ Изменить время", callback_data="edit_time")],
                [InlineKeyboardButton("🔁 Изменить периодичность", callback_data="edit_recurrence")],
                [InlineKeyboardButton("🔙 Вернуться в меню", callback_data="back_to_menu")],
            ]
            await query.message.edit_text("Что вы хотите изменить?", reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == "edit_date":
            context.user_data["editing_date"] = True
            await self.ask_for_date(update, context)
        elif query.data == "back_to_menu":
            await self.main_menu(update, context)
        await query.answer()

    async def confirm_task_completion(self, update: Update, context: CallbackContext) -> None:
        """Подтверждение завершения задачи"""
        query = update.callback_query
        task = context.user_data.get("selected_task")
        user_id = query.message.chat_id
        task_manager = TaskManager(user_id, self.db_manager)

        if task:
            if query.data == "confirm_complete":
                task_manager.delete_task(task.task_id)
                await query.message.edit_text(f"✅ Задача '{task.name}' завершена.")
                await self.main_menu(update, context)
            elif query.data == "cancel":
                await self.main_menu(update, context)
        else:
            await query.message.edit_text("❌ Ошибка: Задача не найдена.")
        await query.answer()

    async def edit_task(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает выбор параметра для редактирования"""
        query = update.callback_query
        task = context.user_data.get("selected_task")

        if not task:
            await query.message.edit_text("❌ Ошибка: Задача не выбрана.")
            return
        if query.data == "edit_name":
            await query.message.edit_text("Введите новое название:")
            context.user_data["editing_task"] = True
            context.user_data["edit_type"] = "name"
        elif query.data == "edit_date":
            context.user_data["editing_date"] = True
            await self.ask_for_date(update, context)
        elif query.data == "edit_time":
            await query.message.edit_text("Введите новое время в формате ЧЧ:ММ:")
            context.user_data["editing_task"] = True
            context.user_data["edit_type"] = "time"
        elif query.data == "edit_recurrence":
            await self.ask_for_recurrence(update, context)

    async def ask_for_recurrence(self, update: Update, context: CallbackContext) -> None:
        """Отправляет inline-кнопки для выбора новой периодичности"""
        query = update.callback_query
        keyboard = [
            [InlineKeyboardButton("Разовая", callback_data="recurrence_once")],
            [InlineKeyboardButton("Каждый день", callback_data="recurrence_daily")],
            [InlineKeyboardButton("Раз в неделю", callback_data="recurrence_weekly")],
            [InlineKeyboardButton("Раз в месяц", callback_data="recurrence_monthly")],
            [InlineKeyboardButton("Раз в год", callback_data="recurrence_yearly")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Выберите новую периодичность:", reply_markup=reply_markup)


    async def handle_edit_text(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает ввод нового названия, времени или периодичности"""
        task = context.user_data.get("selected_task")
        if not task:
            await update.message.reply_text("❌ Ошибка: Задача не выбрана.")
            return

        text = update.message.text.strip()
        edit_type = context.user_data.get("edit_type")

        if edit_type == "name":
            task.name = text
        elif edit_type == "time":
            if not re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text):
                await update.message.reply_text("❌ Некорректный формат. Введите время в формате ЧЧ:ММ (например, 09:45):")
                return
            task.time = text
        elif edit_type == "recurrence":
            task.recurrence = text
        else:
            await update.message.reply_text("❌ Некорректный тип редактирования.")
            return

        self.db_manager.update_task(task)
        context.user_data["selected_task"] = task
        await update.message.reply_text(f"✅ {edit_type.capitalize()} изменено на '{text}'.")

        context.user_data.pop("editing_task", None)
        context.user_data.pop("edit_type", None)

    async def back_to_task_edit(self, update: Update, context: CallbackContext) -> None:
        """Возвращает пользователя в меню task_edit"""
        task = context.user_data.get("selected_task")
        if task:
            await self.handle_task_selection(update, context)