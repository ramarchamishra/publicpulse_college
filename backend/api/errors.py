class APIError(Exception):
    def __init__(self, message, status=400, code="invalid_request"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


class OperationError(Exception):
    """An explicitly safe, user-facing processing error."""
