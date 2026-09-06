"""Result<T, E> — loi la GIA TRI, khong phai exception.

Dung o ranh gioi giua agents/ va ha tang: mot loi upstream la ket qua binh thuong
cua duong ong (co cau fallback, co quyet dinh retry), khong phai su co bat thuong.
Exception van dung cho loi lap trinh that su.
"""

from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeGuard, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E


Result: TypeAlias = Ok[T] | Err[E]


def is_ok(result: Result[T, E]) -> TypeGuard[Ok[T]]:
    return isinstance(result, Ok)


def is_err(result: Result[T, E]) -> TypeGuard[Err[E]]:
    return isinstance(result, Err)
