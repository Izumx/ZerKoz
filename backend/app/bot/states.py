from aiogram.fsm.state import State, StatesGroup


class StatusQuery(StatesGroup):
    code = State()


class Report(StatesGroup):
    location = State()
    photo = State()
    description = State()
    confirm = State()
