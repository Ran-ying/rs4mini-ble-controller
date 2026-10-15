"""Shared error/value contract; independent of transport and motion layers."""
import math

class RS4MiniError(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.__dict__.update(details)


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be greater than 0')


def finite(value, name):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + ' must be finite')
    return number
