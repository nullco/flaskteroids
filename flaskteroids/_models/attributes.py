"""Rails-directed scalar input casting, separate from database serialization."""

import json
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    DefaultClause,
    Float,
    Integer,
    Numeric,
    String,
    Time,
    TypeDecorator,
)
from sqlalchemy.orm.attributes import NO_VALUE

_INTEGER = re.compile(r"^\s*([+-]?\d(?:_?\d)*)")
_FLOAT = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")
_FALSE = (False, 0, "0", "f", "F", "false", "FALSE", "off", "OFF")


def schema_default(column):
    """Decode literal server defaults without executing SQL or server functions."""
    default = column.server_default
    if not isinstance(default, DefaultClause):
        return NO_VALUE
    expression = str(default.arg).strip()
    while expression.startswith("(") and expression.endswith(")"):
        expression = expression[1:-1].strip()
    # A PostgreSQL literal may carry a type cast; the literal itself is safe to
    # decode. Function calls and more complex SQL always remain server-owned.
    expression = re.sub(r'::[A-Za-z_][\w.\s\[\]"]*$', "", expression).strip()
    if re.fullmatch(r"'(?:[^']|'')*'", expression):
        value = expression[1:-1].replace("''", "'")
        if isinstance(column.type, JSON):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return NO_VALUE
    elif expression.upper() in {"TRUE", "FALSE", "NULL"}:
        value = {"TRUE": True, "FALSE": False, "NULL": None}[expression.upper()]
    elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", expression):
        value = expression
    else:
        return NO_VALUE
    return cast_input(column.type, value)


def cast_input(type_, value):
    if isinstance(type_, TypeDecorator):
        return cast_input(type_.impl, value)
    if value is None:
        return None
    if isinstance(type_, JSON):
        return value
    if isinstance(type_, Boolean):
        return None if value == "" else value not in _FALSE
    if isinstance(type_, Integer):
        if isinstance(value, str):
            if not value.strip():
                return None
            match = _INTEGER.match(value)
            return int(match[1].replace("_", "")) if match else 0
        try:
            return int(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if isinstance(type_, (Float, Numeric)):
        if isinstance(value, str):
            if not value.strip():
                return None
            if value not in {"NaN", "Infinity", "-Infinity"}:
                match = _FLOAT.match(value)
                value = match[1] if match else "0"
        try:
            if isinstance(value, bool):
                value = int(value)
            return float(value) if isinstance(type_, Float) else Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            return None
    if isinstance(type_, String):
        if isinstance(value, bool):
            return "t" if value else "f"
        return str(value)
    try:
        if isinstance(type_, DateTime):
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(value) if isinstance(value, str) else None
        if isinstance(type_, Date):
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return date.fromisoformat(value) if isinstance(value, str) else None
        if isinstance(type_, Time):
            if isinstance(value, time):
                return value
            return time.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return value


def database_value(type_, value, raw):
    # Ruby's Integer#to_i reads a nonnumeric string as zero, but Active Record
    # serializes that input as NULL. Numericality validation examines raw input.
    if isinstance(type_, Integer) and isinstance(raw, str) and not _INTEGER.match(raw):
        return None
    return value
