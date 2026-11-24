"""Reads telegrams from the boiler's telnet port.

This module does not depend on Home Assistant. It only listens: nothing is ever sent
to the boiler.
"""

from __future__ import annotations

import asyncio
import contextlib

TELEGRAM_PREFIX = "pm"
DEFAULT_TIMEOUT = 10.0
# The boiler sends one line per second. A few lines are always enough to get a complete one.
DEFAULT_MAX_LINES = 8


class HargassnerError(Exception):
    """Base class for all errors of this module."""


class CannotConnect(HargassnerError):
    """The boiler cannot be reached or does not answer in time."""


class NoTelegram(HargassnerError):
    """The device accepted the connection but did not send a usable 'pm' line."""


class UnexpectedLength(HargassnerError):
    """The boiler sends lines with a different number of values than expected."""

    def __init__(self, expected: int, received: list[int]) -> None:
        super().__init__(f"expected {expected} values per line, received {received}")
        self.expected = expected
        self.received = received


def split_telegram(line: str) -> tuple[str, ...] | None:
    """Return the values of a 'pm' line, or None if the line is something else."""
    parts = line.split()
    if len(parts) < 2 or parts[0] != TELEGRAM_PREFIX:
        return None
    return tuple(parts[1:])


async def async_read_telegram(
    host: str,
    port: int = 23,
    *,
    expected: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_lines: int = DEFAULT_MAX_LINES,
) -> tuple[str, ...]:
    """Connect, read one complete telegram and disconnect.

    With ``expected`` the first line with exactly that many values is returned. Without
    it the first line that has the same length as the line before it is returned, so a
    damaged line is never mistaken for the boiler's format.
    """
    try:
        async with asyncio.timeout(timeout):
            return await _read(host, port, expected, max_lines)
    except TimeoutError as err:
        raise CannotConnect(f"no answer from {host}:{port} within {timeout:g} s") from err
    except OSError as err:
        raise CannotConnect(f"{host}:{port}: {err or type(err).__name__}") from err


async def _read(host: str, port: int, expected: int | None, max_lines: int) -> tuple[str, ...]:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        lengths: list[int] = []
        previous: tuple[str, ...] | None = None
        for _ in range(max_lines):
            try:
                raw = await reader.readline()
            except ValueError as err:  # a "line" longer than the stream buffer
                raise NoTelegram("the device sends data that is not a Hargassner telegram") from err
            if not raw.endswith(b"\n"):
                break  # connection closed (possibly in the middle of a line)
            values = split_telegram(raw.decode("ascii", errors="replace"))
            if values is None:
                continue
            if expected is not None:
                if len(values) == expected:
                    return values
            elif previous is not None and len(previous) == len(values):
                return values
            previous = values
            if len(values) not in lengths:
                lengths.append(len(values))
        if expected is not None and lengths:
            raise UnexpectedLength(expected, sorted(lengths))
        if lengths:
            raise NoTelegram(f"lines of changing length received ({sorted(lengths)} values)")
        raise NoTelegram("no 'pm' line received")
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            async with asyncio.timeout(2):
                await writer.wait_closed()
