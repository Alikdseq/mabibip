"""Исключения домена бронирования."""


class SlotNotBookableError(Exception):
    """Слот недоступен для новой заявки (логика slot_is_bookable)."""


class BookingSlotConflictError(Exception):
    """Гонка или нарушение уникальности: окно уже занято."""
