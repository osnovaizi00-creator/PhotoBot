from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    date = State()
    time = State()
    name = State()
    cost = State()
    studio = State()
    phone = State()
    shoot_name = State()
    move_date = State()
    move_time = State()


class AdminStates(StatesGroup):
    reminder_hours = State()
    timezone = State()
    broadcast_message = State()
