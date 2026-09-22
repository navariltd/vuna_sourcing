# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any


class ResponseStatus(str, Enum):
	SUCCESS = "success"
	ERROR = "error"


@dataclass
class ApiResponse[T]:
	ok: bool
	status: ResponseStatus
	message: str | None = None
	data: T | None = None

	@classmethod
	def success(cls, message: str | None = None, data: T | None = None) -> "ApiResponse[T]":
		return cls(ok=True, status=ResponseStatus.SUCCESS, message=message, data=data)

	@classmethod
	def error(cls, message: str, data: T | None = None) -> "ApiResponse[T]":
		return cls(ok=False, status=ResponseStatus.ERROR, message=message, data=data)

	def as_dict(self) -> dict[str, Any]:
		return {
			"ok": self.ok,
			"status": self.status.value,
			"message": self.message,
			"data": _unwrap(self.data),
		}

	def __json__(self) -> dict[str, Any]:
		return self.as_dict()


def _unwrap(value: Any) -> Any:
	if value is None:
		return None
	if is_dataclass(value) and not isinstance(value, type):
		return asdict(value)
	return value
