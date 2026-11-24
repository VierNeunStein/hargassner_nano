"""Tests for the telnet reader, run against a local TCP server that plays the boiler."""

from __future__ import annotations

import asyncio
import unittest

from custom_components.hargassner_nano.client import (
    CannotConnect,
    NoTelegram,
    UnexpectedLength,
    async_read_telegram,
    split_telegram,
)

from .telegrams import NANO2_LINES

LINE = NANO2_LINES[0]
VALUES = tuple(LINE.split()[1:])


class FakeBoiler:
    """Sends the given chunks to every client, then keeps the connection open or closes it."""

    def __init__(self, chunks: list[bytes], *, close: bool = False, delay: float = 0.0) -> None:
        self.chunks = chunks
        self.close = close
        self.delay = delay
        self.received = b""
        self.port = 0
        self._server: asyncio.Server | None = None

    async def __aenter__(self) -> "FakeBoiler":
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            for chunk in self.chunks:
                if self.delay:
                    await asyncio.sleep(self.delay)
                writer.write(chunk)
                await writer.drain()
            if not self.close:
                self.received += await reader.read()  # until the client disconnects
        except ConnectionError:
            pass
        finally:
            writer.close()


def encode(*lines: str) -> list[bytes]:
    return [f"{line}\r\n".encode() for line in lines]


class SplitTest(unittest.TestCase):
    def test_split(self) -> None:
        self.assertEqual(split_telegram("pm 1 2.5 ff\r\n"), ("1", "2.5", "ff"))
        self.assertIsNone(split_telegram(""))
        self.assertIsNone(split_telegram("pm"))
        self.assertIsNone(split_telegram("z 12:00 Kessel Start"))
        self.assertIsNone(split_telegram("5 63.9 pm 1"))


class ReadTest(unittest.IsolatedAsyncioTestCase):
    async def test_reads_expected_line(self) -> None:
        async with FakeBoiler(encode(LINE)) as boiler:
            values = await async_read_telegram("127.0.0.1", boiler.port, expected=124)
        self.assertEqual(values, VALUES)
        self.assertEqual(boiler.received, b"")  # nothing is ever sent to the boiler

    async def test_skips_cut_off_first_line_and_other_output(self) -> None:
        chunks = [b"3.9 0 61.8 33\r\n", b"z 12:00:01 Kessel Start\r\n", *encode(LINE)]
        async with FakeBoiler(chunks) as boiler:
            self.assertEqual(await async_read_telegram("127.0.0.1", boiler.port, expected=124), VALUES)

    async def test_line_arriving_in_pieces(self) -> None:
        raw = encode(LINE)[0]
        async with FakeBoiler([raw[:100], raw[100:300], raw[300:]], delay=0.01) as boiler:
            self.assertEqual(await async_read_telegram("127.0.0.1", boiler.port, expected=124), VALUES)

    async def test_without_expectation_two_equal_lines_are_required(self) -> None:
        cut_off = "pm " + " ".join(VALUES[40:])
        async with FakeBoiler(encode(cut_off, LINE, NANO2_LINES[1])) as boiler:
            values = await async_read_telegram("127.0.0.1", boiler.port)
        self.assertEqual(values, tuple(NANO2_LINES[1].split()[1:]))

    async def test_unexpected_length(self) -> None:
        async with FakeBoiler(encode(*["pm 1 2 3"] * 8)) as boiler:
            with self.assertRaises(UnexpectedLength) as caught:
                await async_read_telegram("127.0.0.1", boiler.port, expected=124)
        self.assertEqual((caught.exception.expected, caught.exception.received), (124, [3]))

    async def test_connection_closed_by_peer(self) -> None:
        async with FakeBoiler([], close=True) as boiler:
            with self.assertRaises(NoTelegram):
                await async_read_telegram("127.0.0.1", boiler.port, expected=124)

    async def test_incomplete_last_line_is_ignored(self) -> None:
        async with FakeBoiler([LINE.encode()[:200]], close=True) as boiler:
            with self.assertRaises(NoTelegram):
                await async_read_telegram("127.0.0.1", boiler.port)

    async def test_other_device(self) -> None:
        async with FakeBoiler(encode(*["login:"] * 8)) as boiler:
            with self.assertRaises(NoTelegram):
                await async_read_telegram("127.0.0.1", boiler.port)

    async def test_endless_data_without_line_breaks(self) -> None:
        async with FakeBoiler([b"x" * 70_000] * 3) as boiler:
            with self.assertRaises(NoTelegram):
                await async_read_telegram("127.0.0.1", boiler.port)

    async def test_silent_device_times_out(self) -> None:
        async with FakeBoiler([]) as boiler:
            with self.assertRaises(CannotConnect):
                await async_read_telegram("127.0.0.1", boiler.port, timeout=0.2)

    async def test_refused_connection(self) -> None:
        async with FakeBoiler([]) as boiler:
            port = boiler.port
        with self.assertRaises(CannotConnect):
            await async_read_telegram("127.0.0.1", port, timeout=5)


if __name__ == "__main__":
    unittest.main()
