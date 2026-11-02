class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    code = "not_found"


class DomainValidationError(DomainError):
    code = "validation_error"


class InvalidSlot(DomainError):
    code = "invalid_slot"


class SlotUnavailable(DomainError):
    code = "slot_unavailable"


class DailyCapReached(DomainError):
    code = "daily_cap_reached"


class DuplicateBooking(DomainError):
    code = "duplicate_booking"


class NotOwner(DomainError):
    code = "not_owner"


class NotCancellable(DomainError):
    code = "not_cancellable"


class Conflict(DomainError):
    code = "conflict"
