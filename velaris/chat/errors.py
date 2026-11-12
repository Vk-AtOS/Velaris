"""One error type for the chat package. `code` and `message` are written here and are safe to show;
they never carry exception text or anything the sender typed."""
from __future__ import annotations


class ChatError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
