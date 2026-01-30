CONST_COUNT_TASKS_PER_PAGE = 3
import asyncio
import json
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
import os
import time #Только для генерации idшников
from pathlib import Path
import re
import pytz
from aiogram.types import ReplyKeyboardRemove
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.exceptions import TelegramForbiddenError

from config import ttkl
TOKEN = ttkl

def add_user(user_id):
    try:
        with open("data/users.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        if user_id not in data:
            data.append(user_id) 
            os.mkdir(f"user_data/{user_id}")
            with open(f"user_data/{user_id}/preferences","w",encoding="utf-8") as f:
                #ТУТ ДОРАБАТЫВАТЬ ПРЕДПОЧТЕНИЯ ПРИ ИНИЦИАЛИЗАЦИИ
                tmp_preference={"permittions":"user","utc_loc":"Europe/London","time_call":"03:00","waytoinfo":"text","status":"OK"}
                json.dump(tmp_preference,f,ensure_ascii=False,indent=2)

            with open(f"user_data/{user_id}/problems.json", "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

            with open("data/users.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return "Initialised. Please, write /settings and configure your UTC. Program basicly will think that you are in London"
        else:
            return "already in"   
    except:
        return "smth gone wrong"       

    

bot = Bot(token=TOKEN)
dp = Dispatcher()



with open("data/Timezones.json", "r", encoding="utf-8") as f:
    TIMEZONES = json.load(f)

@dp.message(Command("status"))
async def is_working(message:Message):
    await message.answer("working")

@dp.message(Command("clearkb"))
async def clrkb(message:Message):
    await message.answer("tried",reply_markup=ReplyKeyboardRemove())

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    t=add_user(user_id)
    print(t)
    await message.answer(t)
    print(message.from_user.id)

router = Router()
dp.include_router(router)

class reportState(StatesGroup):
    report = State()

@router.message(Command("report"))
async def getrep(message: Message, state: FSMContext):
    await message.answer("Please describe the problem in detail, what you did, and what the bot returned to you.")
    await state.set_state(reportState.report)

@router.message(reportState.report)
async def getnewreport(message: Message,state: FSMContext,bot):
    id=message.from_user.id
    msg = message.text
    name = f"data/reports/{id}_{int(time.time())}"
    with open(name,"w",encoding="utf-8") as f:
        f.write(msg)
    await message.answer("written")
    await state.clear()

class GlobalInfoState(StatesGroup):
    waiting_for_text = State()

@router.message(Command("global_info"))
async def global_from_tg(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            prefs = json.load(f)
        if prefs.get("permittions") != "admin":
            await message.answer("You aren't admin")
            return
    except (FileNotFoundError, json.JSONDecodeError):
        await message.answer("Access denied or invalid preferences file.")
        return

    await message.answer("Enter global message")
    await state.set_state(GlobalInfoState.waiting_for_text)


@router.message(GlobalInfoState.waiting_for_text)
async def receive_global_text(message: Message, state: FSMContext, bot):
    msg = message.text
    if not msg:
        await message.answer("Empty message ignored.")
        await state.clear()
        return

    try:
        with open("data/users.json", "r", encoding="utf-8") as f:
            user_ids = json.load(f)
        if not isinstance(user_ids, list):
            await message.answer("Error: users.json must contain a JSON array of user IDs.")
            await state.clear()
            return
    except (FileNotFoundError, json.JSONDecodeError) as e:
        await message.answer(f"Failed to load user list: {e}")
        await state.clear()
        return

    sent_count = 0
    blocked_count = 0

    for uid in user_ids:
        try:
            await bot.send_message(chat_id=str(uid), text=msg)
            
        except TelegramForbiddenError:
            try:
                pref_path = f"user_data/{uid}/preferences"
                with open(pref_path, "r", encoding="utf-8") as pref_file:
                    data = json.load(pref_file)
                data["status"] = "blocked"
                with open(pref_path, "w", encoding="utf-8") as pref_file:
                    json.dump(data, pref_file, ensure_ascii=False, indent=2)
                
            except (FileNotFoundError, json.JSONDecodeError):
                await bot.send_message(chat_id=str(uid), text="smth wrong with your data. Please, send report about this problem")
                pass
        except Exception:
            #Telegram errors 
            pass

    await message.answer("sended")
    await state.clear()


def format_task(task, user_tz, index): 
    try:
        utc_dt = datetime.fromisoformat(task["deadline"].rstrip("Z"))
        local_dt = utc_dt.astimezone(user_tz)
        local_str = local_dt.strftime("%d.%m.%Y %H:%M")
        
        now_local = datetime.now(user_tz)
        if local_dt < now_local:
            status = "Overdue"
        else:
            status = "Relevant"
    except Exception:
        local_str = "Time error"
        status = "Is unknown. Write a report and enter the task ID. Most likely, it will not be possible to return the recorded time."

    categories = []
    i = 1
    while f"kat{i}" in task:
        categories.append(str(task[f"kat{i}"]))
        i += 1
    categories_str = ", ".join(categories) if categories else "нет"

    return (
        f"<b>№{index + 1}</b>\n"
        f"<b>ID:</b> {task['id']}\n"
        f"<b>Title:</b> {task['name']}\n"
        f"<b>Description:</b> {task['description']}\n"
        f"<b>Deadline:</b> {local_str}\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Lead time:</b> {task['time_to_do']}\n"
        f"<b>Importance:</b> {task['importance']}\n"
        f"<b>Сonsequence:</b> {task['consequence']}\n"
        f"<b>Categories:</b> {categories_str}"
    )


@router.message(Command("not_sorted_problems"))
async def list_problems(message: Message):
    user_id = str(message.from_user.id)
    try:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            prefs = json.load(f)
        tz_name = prefs.get("utc_loc")
        if not tz_name:
            await message.answer("Часовой пояс не установлен. Используйте /settings.")
            return
        user_tz = pytz.timezone(tz_name)
    except (json.JSONDecodeError, pytz.UnknownTimeZoneError):
        await message.answer("Ошибка в настройках. Обратитесь к разработчику.")
        return

    
    problems = load_problems(user_id)
    if not problems:
        await message.answer("У вас нет задач.")
        return

    
    total_pages = (len(problems) + CONST_COUNT_TASKS_PER_PAGE - 1) // CONST_COUNT_TASKS_PER_PAGE#высчет страниц
    await send_problems_page(
        chat_id=message.chat.id,
        problems=problems,
        user_tz=user_tz,
        page=1,
        total_pages=total_pages
    )


async def send_problems_page(chat_id, problems, user_tz, page, total_pages, message_id=None):
    start_idx = (page - 1) * CONST_COUNT_TASKS_PER_PAGE
    end_idx = start_idx + CONST_COUNT_TASKS_PER_PAGE
    page_tasks = problems[start_idx:end_idx]

    if not page_tasks:
        text = "Нет задач для отображения."
        kb = InlineKeyboardMarkup(inline_keyboard=[])
    else:
        task_texts = [
            format_task(task, user_tz, idx)
            for idx, task in enumerate(page_tasks)
        ]
        text = "\n\n".join(task_texts)
        text += f"\n\nСтраница {page}/{total_pages}"
        keyboard = []

        
        for task in page_tasks:
            task_id = task["id"]
            row = [
                InlineKeyboardButton(text=f"Удалить {task_id}", callback_data=f"del_task:{task_id}")#,
                #InlineKeyboardButton(text="В выполненные", callback_data=f"del_task:{task_id}"),
                #InlineKeyboardButton(text="В просроченные", callback_data=f"del_task:{task_id}")
            ]#задел на расширение
            keyboard.append(row)

        # навигация
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page:{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"page:{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        except Exception:
            pass
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )


@router.callback_query(F.data.startswith("del_task:"))
async def delete_task_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    try:
        task_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный ID задачи.", show_alert=True)
        return

    problems = load_problems(user_id)
    initial_count = len(problems)
    problems = [t for t in problems if t["id"] != task_id]
    save_problems(user_id, problems)

    if len(problems) == initial_count:
        await callback.answer("Задача уже удалена.", show_alert=True)
        return

    try:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            prefs = json.load(f)
        tz_name = prefs.get("utc_loc")
        user_tz = pytz.timezone(tz_name)
    except Exception:
        await callback.answer("Ошибка перезагрузки.", show_alert=True)
        return

    total_pages = (len(problems) + CONST_COUNT_TASKS_PER_PAGE - 1) // CONST_COUNT_TASKS_PER_PAGE
    current_page = 1
    for i, t in enumerate(load_problems(user_id)): 
        if t["id"] == task_id:
            current_page = (i // CONST_COUNT_TASKS_PER_PAGE) + 1
            break

    final_page = min(current_page, total_pages) if total_pages > 0 else 1

    await send_problems_page(
        chat_id=callback.message.chat.id,
        problems=problems,
        user_tz=user_tz,
        page=final_page,
        total_pages=total_pages if total_pages > 0 else 1,
        message_id=callback.message.message_id
    )
    await callback.answer("Задача удалена.", show_alert=False)


@router.callback_query(F.data.startswith("page:"))
async def paginate_problems(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    try:
        page = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return
    try:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            prefs = json.load(f)
        tz_name = prefs.get("utc_loc")
        user_tz = pytz.timezone(tz_name)
        problems = load_problems(user_id)
        
    except Exception:
        await callback.answer("Ошибка загрузки данных.", show_alert=True)
        return

    total_pages = (len(problems) + CONST_COUNT_TASKS_PER_PAGE - 1) // CONST_COUNT_TASKS_PER_PAGE

    if page < 1 or page > total_pages:
        await callback.answer("Попробуйте снова и отправьте репорт.", show_alert=True)
        return

    await send_problems_page(
        chat_id=callback.message.chat.id,
        problems=problems,
        user_tz=user_tz,
        page=page,
        total_pages=total_pages,
        message_id=callback.message.message_id
    )
    await callback.answer()



def get_next_problem_id():
    #100% unique id
    _2025start = 1735689600  
    return int((time.time() - _2025start))//4

def get_problems_path(user_id):
    return Path(f"user_data/{user_id}/problems.json")

def load_problems(user_id):
    path = get_problems_path(user_id)
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

def save_problems(user_id, problems):
    
    path = get_problems_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

def parse_duration(text):
    text = text.strip()
    if not re.fullmatch(r"\d+:\d+", text):
        return None
    try:
        hours, minutes = map(int, text.split(":"))
        if hours < 0 or minutes < 0 or minutes >= 60:
            return None
        return hours, minutes
    except:
        return None

class ProblemStates(StatesGroup):
    name = State()
    description = State()
    deadline = State()
    duration = State()
    importance = State()
    consequence = State()
    categories = State()

@router.message(Command("new_problem"))
async def cmd_new_problem(message, state):
    await state.set_state(ProblemStates.name)
    await message.answer("Enter the problem name:")

@router.message(ProblemStates.name)
async def process_name(message, state):
    await state.update_data(name=message.text.strip())
    await state.set_state(ProblemStates.description)
    await message.answer("Briefly describe the problem:")

@router.message(ProblemStates.description)
async def process_description(message, state):
    await state.update_data(description=message.text.strip())
    await state.set_state(ProblemStates.deadline)
    await message.answer("Enter the deadline in the format: DD.MM.YYYY HH:MM\nExample: 14.12.2025 15:30")

@router.message(ProblemStates.deadline)
async def process_deadline(message, state):
    user_id = str(message.from_user.id)
    
    try:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            prefs = json.load(f)
        tz_name = prefs.get("utc_loc")
        if not tz_name or tz_name.strip() == "":
            await message.answer(
                "First, set the time zone in /settings.\n"
                "Enter the deadline in the format: DD.MM.YYYY HH:MM"
            )
            return
        
        user_tz = pytz.timezone(tz_name)
        
    except FileNotFoundError:
        print(f"The settings file was not found: user_data/{user_id}/preferences")
        await message.answer("No settings file found. Run /start and report the problem.")
        return
        
    except pytz.UnknownTimeZoneError as e:
        print(f"Unknown time zone '{tz_name}': {e}")
        await message.answer(
            "Incorrect time zone. Set it again in /settings.\n"
            "Enter the deadline in the format: DD.MM.YYYY HH:MM"
        )
        return
        
    except Exception as e:
        print(f"Error loading settings: {type(e).__name__}: {e}")
        await message.answer("Data loading error. Please contact the developer /report.")
        return

    
    try:
        naive_dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("Incorrect format. Use: DD.MM.YYYY HH:MM (for example, 14.12.2025 15:30)")
        return

    #convert to UTC
    try:
        local_dt = user_tz.localize(naive_dt)
        utc_dt = local_dt.astimezone(pytz.utc)
        deadline_utc_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        print(f"Time conversion error: {e}")
        await message.answer("Date processing error. Try again.")
        return

   
    now_utc = datetime.now(pytz.utc)
    if utc_dt <= now_utc:
        await state.clear()  
        await message.answer(
            "Time has passed. Unable to create a task.\n\n"
            "You can add a debt (the feature will be available later). Creating a problem has been canceled"
        )
        return

    await state.update_data(deadline=deadline_utc_iso)
    await state.set_state(ProblemStates.duration)
    await message.answer("Enter the estimated execution time in the format hours:minutes (for example: 2:30):")


@router.message(ProblemStates.duration)
async def process_duration(message, state):
    duration = parse_duration(message.text)
    if duration is None:
        await message.answer("Incorrect time format. Example: 2:30 (2 hours and 30 minutes). Minutes are from 0 to 59.")
        return
    hours, minutes = duration
    time_parts = []
    if hours > 0:
        time_parts.append(f"{hours} ч")
    if minutes > 0:
        time_parts.append(f"{minutes} мин")
    time_to_do = " ".join(time_parts) if time_parts else "0 мин"
    await state.update_data(time_to_do=time_to_do)
    await state.set_state(ProblemStates.importance)
    await message.answer("Specify the importance as an integer")

@router.message(ProblemStates.importance)
async def process_importance(message, state):
    try:
        importance = int(message.text.strip())
        if importance < 0:
            raise ValueError
    except ValueError:
        await message.answer("The importance must be a non-negative integer. Try again:")
        return
    await state.update_data(importance=importance)
    await state.set_state(ProblemStates.consequence)
    await message.answer("What will happen if the problem is not solved?")

@router.message(ProblemStates.consequence)
async def process_consequence(message, state):
    await state.update_data(consequence=message.text.strip())
    await state.set_state(ProblemStates.categories)
    await state.update_data(categories=[])
    await message.answer("Now enter the categories one by one. Finish the input with the /end command.")

@router.message(ProblemStates.categories)
async def add_category(message, state):
    if message.text == "/end":
        await cmd_end(message, state)
        return
    
    data = await state.get_data()
    categories = data.get("categories", [])
    categories.append(message.text.strip())
    await state.update_data(categories=categories)
    await message.answer(f"Category added: '{message.text}'. Enter the next command or /end to end.")

@router.message(Command("end"))
async def cmd_end(message, state):
    data = await state.get_data()
    categories = data.get("categories", [])
    if not categories:
        categories = ["none"]

    problem_id = get_next_problem_id()

    problem = {
        "id": problem_id,
        "name": data["name"],
        "description": data["description"],
        "deadline": data["deadline"],
        "time_to_do": data["time_to_do"],
        "importance": data["importance"],
        "consequence": data["consequence"],
    }

    for i, cat in enumerate(categories, start=1):
        problem[f"kat{i}"] = cat

    user_id = str(message.from_user.id)
    problems = load_problems(user_id)
    problems.append(problem)
    save_problems(user_id, problems)

    kats_str = ", ".join(f"kat{i}={cat}" for i, cat in enumerate(categories, start=1))
    result = (
        "Problem saved:\n\n"
        f"id: {problem['id']}\n"
        f"name: {problem['name']}\n"
        f"description: {problem['description']}\n"
        f"deadline (IN UTC): {problem['deadline']}\n"
        f"time_to_do: {problem['time_to_do']}\n"
        f"importance: {problem['importance']}\n"
        f"Consequences: {problem['consequence']}\n"
        f"Categories: {kats_str}"
    )
    await message.answer(result)
    await state.clear()

@router.message(Command("cancel"))
async def cmd_cancel(message, state):
    await state.clear()
    await message.answer("The problem creation has been canceled.")                


class SettingsStates(StatesGroup):
    editing_timezone = State()
    editing_time_call = State()


def settings_keyboard():
    inline_kb_list = [
        [InlineKeyboardButton(text="Time zone", callback_data='edit_timezone')],
        [InlineKeyboardButton(text="Time before the deadline", callback_data='edit_time_call')],
        [InlineKeyboardButton(text="Task output method", callback_data='edit_output_method')],
        [InlineKeyboardButton(text="back", callback_data='back')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb_list)


@dp.message(Command("settings"))
async def settings_handler(message: Message):
    await message.answer("What should I change?", reply_markup=settings_keyboard())


#Часовой пояс
@dp.callback_query(F.data == "edit_timezone")
async def tz_start(callback: CallbackQuery, state: FSMContext):
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"tz:{name}")] for name in TIMEZONES]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Select a time zone:", reply_markup=kb)
    await state.set_state(SettingsStates.editing_timezone)
    await callback.answer()


@dp.callback_query(F.data.startswith("tz:"), SettingsStates.editing_timezone)
async def tz_save(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    name = callback.data[3:]
    if name in TIMEZONES:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            p = json.load(f)
        p["utc_loc"] = TIMEZONES[name]
        with open(f"user_data/{user_id}/preferences", "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        await callback.message.edit_text("The time zone is saved.")
    await state.clear()
    await callback.answer()


#Время уведомления
@dp.callback_query(F.data == "edit_time_call")
async def time_call_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Enter the time until the deadline when you receive the notification in HH:MM format (for example, 09:30):")
    await state.set_state(SettingsStates.editing_time_call)
    await callback.answer()


@dp.message(SettingsStates.editing_time_call)
async def time_call_save(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            p = json.load(f)
        p["time_call"] = message.text.strip()
        with open(f"user_data/{user_id}/preferences", "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        await message.answer("The call time is saved.")
    except ValueError:
        await message.answer("Incorrect format. Enter HH:MM (for example, 14:00).")
        return
    await state.clear()


#Способ вывода задач
@dp.callback_query(F.data == "edit_output_method")
async def way_start(callback: CallbackQuery):
    buttons = [
        [InlineKeyboardButton(text="Text", callback_data="way:text")],
        [InlineKeyboardButton(text="Images", callback_data="way:graphix")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Select the notification method:",reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("way:"))
async def way_save(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    method = callback.data[4:]

    if method not in ("text", "graphix"):
        await callback.answer("An unacceptable option.", show_alert=True)
        return

    try:
        with open(f"user_data/{user_id}/preferences", "r", encoding="utf-8") as f:
            prefs = json.load(f)
        prefs["waytoinfo"] = method
        with open(f"user_data/{user_id}/preferences", "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        await callback.message.edit_text(f"Notification method: {method}")
    except Exception:
        await callback.message.edit_text("Saving error.")
    await callback.answer()



@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("The settings are closed.",reply_markup=ReplyKeyboardRemove())
    await callback.answer()


def format_timedelta(td: timedelta):
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "просрочено"
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    
    return " ".join(parts) if parts else "менее минуты"

async def check_all_users_for_deadlines(bot: Bot):
    try:
        with open("data/users.json", "r", encoding="utf-8") as f:
            user_ids = json.load(f)
    except Exception:
        return

    now_utc = datetime.now(pytz.UTC)

    for user_id in user_ids:
        try:
            pref_path = f"user_data/{user_id}/preferences"
            if not os.path.exists(pref_path):
                continue

            with open(pref_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)

            if prefs.get("status") == "blocked":
                continue

            tz_name = prefs.get("utc_loc")
            time_call_str = prefs.get("time_call", "00:00")

            #00:00=skip
            if time_call_str == "00:00":
                continue
            try:
                h, m = map(int, time_call_str.split(":"))
                notify_before = timedelta(hours=h, minutes=m)
            except (ValueError, TypeError):
                continue  

            
            problems = load_problems(user_id)
            updated = False

            for task in problems:
                if task.get("notified"):
                    continue

                try:
                    deadline_str = task["deadline"].rstrip("Z")
                    deadline_utc = datetime.fromisoformat(deadline_str).replace(tzinfo=pytz.UTC)
                except Exception:
                    continue

                
                time_until_deadline = deadline_utc - now_utc

                
                if time_until_deadline.total_seconds() <= 0:
                    continue

                
                notify_threshold = deadline_utc - notify_before

                
                if now_utc >= notify_threshold:
                    try:
                    
                        if tz_name:
                            try:
                                user_tz = pytz.timezone(tz_name)
                                local_deadline = deadline_utc.astimezone(user_tz)
                                deadline_str_local = local_deadline.strftime("%d.%m %H:%M")
                            except:
                                deadline_str_local = deadline_utc.strftime("%d.%m %H:%M UTC")
                        else:
                            deadline_str_local = deadline_utc.strftime("%d.%m %H:%M UTC")

                        time_left_str = format_timedelta(time_until_deadline)
                        
                        msg = (
                            f"🔔 <b>Task Reminder!</b>\n\n"
                            f"<b>{task['name']}</b>\n"
                            f"Deadline: {deadline_str_local}\n"
                            f"Time remaining: {time_left_str}\n"
                            f"Description: {task['description']}"
                        )
                        await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                        task["notified"] = True
                        updated = True

                    except TelegramForbiddenError:
                        prefs["status"] = "blocked"
                        with open(pref_path, "w", encoding="utf-8") as f:
                            json.dump(prefs, f, ensure_ascii=False, indent=2)
                        break
                    except Exception:
                        pass  

            if updated:
                save_problems(user_id, problems)

        except Exception as e:
            print(f"Ошибка при обработке пользователя {user_id}: {e}")
            continue

async def regular_reminder_loop(bot: Bot, user_id: str, interval: int = 10800):
    """
    Периодически отправляет напоминания по списку задач из data/regular.json.
    """
    regular_file = Path("data/regular.json")
    
    print(f"[REGULAR] Запущен regular_reminder_loop для пользователя {user_id}")
    
    while True:
        try:
            # Проверяем, существует ли файл
            if not regular_file.exists():
                print(f"[REGULAR] Файл {regular_file} не найден! Создайте его.")
                await asyncio.sleep(interval)
                continue
            
            # Проверяем, не пуст ли файл
            if regular_file.stat().st_size == 0:
                print(f"[REGULAR] Файл {regular_file} пуст! Добавьте задачи.")
                await asyncio.sleep(interval)
                continue
            
            # Читаем файл
            try:
                with open(regular_file, "r", encoding="utf-8") as f:
                    regular_tasks = json.load(f)
            except json.JSONDecodeError:
                print(f"[REGULAR] Ошибка: {regular_file} содержит невалидный JSON")
                await asyncio.sleep(interval)
                continue
            
            if not isinstance(regular_tasks, list):
                print(f"[REGULAR] Ошибка: данные в {regular_file} не являются списком")
                await asyncio.sleep(interval)
                continue
            
            print(f"[REGULAR] Найдено {len(regular_tasks)} регулярных задач")
            
            # Отправляем напоминания для каждой задачи
            for task in regular_tasks:
                try:
                    # Собираем категории
                    categories = []
                    i = 1
                    while f"kat{i}" in task:
                        categories.append(str(task[f"kat{i}"]))
                        i += 1
                    cats_str = ", ".join(categories) if categories else "нет"

                    # Формируем сообщение
                    msg = (
                        f"🔄 <b>РЕГУЛЯРНОЕ НАПОМИНАНИЕ</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"<b>ID:</b> {task.get('id', 'N/A')}\n"
                        f"<b>Задача:</b> {task.get('name', 'Без названия')}\n"
                        f"<b>Описание:</b> {task.get('description', 'Без описания')}\n"
                        f"<b>Важность:</b> {task.get('importance', 'N/A')}\n"
                        f"<b>Категории:</b> {cats_str}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"<i>Не забудь выполнить эту задачу!</i>"
                    )
                    
                    # Отправляем сообщение
                    await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                    print(f"[REGULAR] Отправлено напоминание пользователю {user_id}")
                    
                    # Небольшая пауза между сообщениями
                    await asyncio.sleep(1)
                    
                except TelegramForbiddenError:
                    print(f"[REGULAR] Пользователь {user_id} заблокировал бота")
                    return  # Завершаем цикл
                except Exception as e:
                    print(f"[REGULAR] Ошибка при отправке задачи: {type(e).__name__}: {e}")
                    continue
            
            print(f"[REGULAR] Все напоминания отправлены. Ждем {interval} секунд...")
            
        except Exception as e:
            print(f"[REGULAR] Критическая ошибка: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Ожидание до следующего цикла
        await asyncio.sleep(interval)


async def deadline_notifier_loop(bot: Bot):
    while True:
        await check_all_users_for_deadlines(bot)
        await asyncio.sleep(60)  


async def main():
    reports_dir = "data/reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    await bot.send_message(chat_id="5130574101",text="Code is working")

    """notifier_task = asyncio.create_task(deadline_notifier_loop(bot))
    print("working")
    try:
        await dp.start_polling(bot)
    finally:
        notifier_task.cancel()
        try:
            await notifier_task
        except asyncio.CancelledError:
            pass"""

    
    MY_ID = "5130574101"
  
    notifier_task = asyncio.create_task(deadline_notifier_loop(bot))
    
    # Запускаем регулярные напоминания по твоему списку
    # interval=3600 — напоминать раз в час
    regular_task = asyncio.create_task(
        regular_reminder_loop(bot, user_id=MY_ID, interval=3600*12)
    )

    print("Бот запущен и готов к работе")
    try:
        await dp.start_polling(bot)
    finally:
        notifier_task.cancel()
        regular_task.cancel()
        await asyncio.gather(notifier_task, regular_task, return_exceptions=True)



if __name__ == "__main__":
    asyncio.run(main())