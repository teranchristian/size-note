class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str, *, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ConflictError(DomainError):
    status_code = 409


class NotFoundError(DomainError):
    status_code = 404
