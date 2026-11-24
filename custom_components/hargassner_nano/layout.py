"""Channel layouts: which value of a telegram means what.

This module does not depend on Home Assistant.

A telegram is one line of the boiler's telnet stream::

    pm <analog 0> <analog 1> ... <analog N-1> <word 0> ... <word M-1>

Analog values are decimal numbers, the trailing digital words are hexadecimal bit
fields. A layout names the analog values and the bits. Layouts are written in the
format the boiler itself uses in its SD card log files (the ``<DAQPRJ>`` header).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache, cached_property
from html import unescape
import re

# More than enough for a DAQPRJ block (the largest known one has about 20 kB).
MAX_DAQPRJ_LENGTH = 200_000
# A custom definition may be followed by this many status words it does not name.
MAX_UNNAMED_WORDS = 2

_SECTION = r"<{0}\b[^>]*>(.*?)</{0}\s*>"
_CHANNEL = re.compile(r"<CHANNEL\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_ATTRIBUTE = re.compile(r"([A-Za-z_][\w.-]*)\s*=\s*([\"'])(.*?)\2", re.DOTALL)
_NUMBER = re.compile(r"-?\d+(?:\.(\d+))?")
_HEX = re.compile(r"[0-9A-Fa-f]{1,16}")
_UMLAUT = re.compile(r"[äöüÄÖÜß]")
_TRANSLITERATE = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})
_PLACEHOLDER_PREFIXES = ("dummy", "reserved", "unused")


class LayoutError(ValueError):
    """A layout definition is invalid or does not fit a telegram.

    ``reason`` is a stable identifier that the config flow shows as a translated error.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def channel_key(name: str) -> str:
    """Return a spelling-independent identifier for a channel name.

    Firmware versions spell the same channel differently ("Störungs Nr", "Storungs Nr",
    "Stoerungs Nr"). All of them map to the same key, so entities keep their identity
    when the firmware changes.
    """
    text = name.strip().lower().translate(_TRANSLITERATE)
    text = text.replace("ae", "a").replace("oe", "o").replace("ue", "u")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _lookup_keys(name: str) -> tuple[str, ...]:
    """Keys under which a channel called ``name`` may be found in a layout."""
    key = channel_key(name)
    # A DAQ file opened with the wrong character set turns "ö" into one or two odd
    # characters. Those end up as "_" in the key.
    damaged = channel_key(_UMLAUT.sub("?", name))
    return (key,) if damaged == key else (key, damaged)


@dataclass(frozen=True, slots=True)
class AnalogChannel:
    """One analog value of a telegram."""

    index: int
    name: str
    key: str
    unit: str | None = None
    decimals: int | None = None

    @property
    def is_placeholder(self) -> bool:
        """Return True for channels that carry no information (dummy, reserved)."""
        return self.key.startswith(_PLACEHOLDER_PREFIXES)


@dataclass(frozen=True, slots=True)
class DigitalChannel:
    """One bit of a digital status word."""

    word: int
    bit: int
    name: str
    key: str

    @property
    def is_placeholder(self) -> bool:
        """Return True for bits that carry no information (dummy, reserved)."""
        return self.key.startswith(_PLACEHOLDER_PREFIXES)


@dataclass(frozen=True, slots=True)
class Telegram:
    """The decoded values of one line."""

    values: tuple[str, ...]
    analog: dict[str, float | int | None]
    digital: dict[str, bool | None]


@dataclass(frozen=True)
class Layout:
    """Describes the values of a telegram."""

    key: str
    title: str
    analog: tuple[AnalogChannel, ...]
    digital: tuple[DigitalChannel, ...]
    digital_words: int

    @property
    def value_count(self) -> int:
        """Number of values after the leading 'pm'."""
        return len(self.analog) + self.digital_words

    @cached_property
    def _analog_by_key(self) -> dict[str, AnalogChannel]:
        return {channel.key: channel for channel in self.analog}

    @cached_property
    def _digital_by_key(self) -> dict[str, DigitalChannel]:
        return {channel.key: channel for channel in self.digital}

    def find_analog(self, *names: str) -> AnalogChannel | None:
        """Return the first analog channel that has one of the given names."""
        for name in names:
            for key in _lookup_keys(name):
                if (channel := self._analog_by_key.get(key)) is not None:
                    return channel
        return None

    def find_digital(self, *names: str) -> DigitalChannel | None:
        """Return the first digital channel that has one of the given names."""
        for name in names:
            for key in _lookup_keys(name):
                if (channel := self._digital_by_key.get(key)) is not None:
                    return channel
        return None

    def decode(self, values: tuple[str, ...] | list[str]) -> Telegram:
        """Turn the values of one line into named values."""
        if len(values) != self.value_count:
            raise LayoutError("count_mismatch", f"{len(values)} values, layout has {self.value_count}")

        analog: dict[str, float | int | None] = {}
        for channel in self.analog:
            analog[channel.key] = _to_number(values[channel.index])

        words: list[int | None] = []
        for text in values[len(self.analog) :]:
            try:
                words.append(int(text, 16))
            except ValueError:
                words.append(None)

        digital: dict[str, bool | None] = {}
        for bit in self.digital:
            word = words[bit.word]
            digital[bit.key] = None if word is None else bool(word >> bit.bit & 1)

        return Telegram(values=tuple(values), analog=analog, digital=digital)

    def check(self, values: tuple[str, ...] | list[str]) -> list[str]:
        """Return the reasons why a line does not look like this layout (empty = fits).

        The boiler prints channels declared with ``dop="0"`` without a decimal point and
        channels with ``dop="2"`` with exactly two decimals. A line that breaks these
        rules was produced by a different firmware layout.
        """
        if len(values) != self.value_count:
            return [f"{len(values)} values instead of {self.value_count}"]

        problems: list[str] = []
        for channel in self.analog:
            text = values[channel.index]
            match = _NUMBER.fullmatch(text)
            if match is None:
                problems.append(f"{channel.name} (value {channel.index + 1}): '{text}' is not a number")
            elif channel.decimals is not None and len(match.group(1) or "") != channel.decimals:
                problems.append(
                    f"{channel.name} (value {channel.index + 1}): '{text}' does not have {channel.decimals} decimals"
                )
        for position in range(len(self.analog), len(values)):
            if _HEX.fullmatch(values[position]) is None:
                problems.append(f"status word (value {position + 1}): '{values[position]}' is not hexadecimal")
        return problems


def _to_number(text: str) -> float | int | None:
    """Convert a value of the telegram, keeping integers as integers."""
    match = _NUMBER.fullmatch(text)
    if match is None:
        return None
    return float(text) if match.group(1) else int(text)


def _attributes(tag_body: str) -> dict[str, str]:
    return {name.lower(): unescape(value).strip() for name, _, value in _ATTRIBUTE.findall(tag_body)}


def _section(text: str, name: str) -> str | None:
    match = re.search(_SECTION.format(name), text, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _unique_key(name: str, fallback: str, used: set[str]) -> str:
    base = channel_key(name) or fallback
    key = base
    counter = 1
    while key in used:
        counter += 1
        key = f"{base}_{counter}"
    used.add(key)
    return key


def parse_daqprj(text: str, *, key: str, title: str, digital_words: int | None = None) -> Layout:
    """Build a layout from a ``<DAQPRJ>`` definition.

    ``digital_words`` overrides the number of status words. It is needed when a boiler
    sends more words than its definition names.
    """
    if len(text) > MAX_DAQPRJ_LENGTH:
        raise LayoutError("too_long", f"{len(text)} characters")

    analog_section = _section(text, "ANALOG")
    if analog_section is None:
        raise LayoutError("no_analog_section")

    by_id: dict[int, dict[str, str]] = {}
    for body in _CHANNEL.findall(analog_section):
        attributes = _attributes(body)
        try:
            channel_id = int(attributes["id"])
        except (KeyError, ValueError):
            raise LayoutError("bad_channel", body.strip()[:80]) from None
        if channel_id in by_id or channel_id < 0:
            raise LayoutError("duplicate_channel", f"analog id {channel_id}")
        by_id[channel_id] = attributes
    if not by_id:
        raise LayoutError("no_analog_channels")
    if sorted(by_id) != list(range(len(by_id))):
        missing = sorted(set(range(max(by_id) + 1)) - set(by_id))
        raise LayoutError("channel_gap", f"missing analog ids {missing[:10]}")

    used: set[str] = set()
    analog: list[AnalogChannel] = []
    for index in range(len(by_id)):
        attributes = by_id[index]
        name = attributes.get("name", "") or f"Analog {index}"
        decimals: int | None = None
        if attributes.get("dop", "").isdigit():
            decimals = int(attributes["dop"])
        analog.append(
            AnalogChannel(
                index=index,
                name=name,
                key=_unique_key(name, f"analog_{index}", used),
                unit=attributes.get("unit") or None,
                decimals=decimals,
            )
        )

    used = set()
    digital: list[DigitalChannel] = []
    seen_bits: set[tuple[int, int]] = set()
    for body in _CHANNEL.findall(_section(text, "DIGITAL") or ""):
        attributes = _attributes(body)
        try:
            word, bit = int(attributes["id"]), int(attributes["bit"])
        except (KeyError, ValueError):
            raise LayoutError("bad_channel", body.strip()[:80]) from None
        if not 0 <= bit < 64 or not 0 <= word < 64 or (word, bit) in seen_bits:
            raise LayoutError("duplicate_channel", f"digital word {word} bit {bit}")
        seen_bits.add((word, bit))
        name = attributes.get("name", "") or f"Digital {word}.{bit}"
        key_ = _unique_key(name, f"digital_{word}_{bit}", used)
        digital.append(DigitalChannel(word=word, bit=bit, name=name, key=key_))

    named_words = max((channel.word for channel in digital), default=-1) + 1
    if digital_words is None:
        digital_words = named_words
    elif digital_words < named_words:
        raise LayoutError("count_mismatch", f"{digital_words} status words, definition names {named_words}")

    return Layout(key=key, title=title, analog=tuple(analog), digital=tuple(digital), digital_words=digital_words)


def parse_custom_daqprj(text: str, values: tuple[str, ...] | list[str], *, title: str = "DAQPRJ") -> Layout:
    """Build a layout from a pasted definition and fit it to a line of the boiler.

    Some boilers send one or two status words more than their definition names. Such a
    surplus is accepted, but only if the line otherwise follows the definition's number
    formats; a definition of another firmware does not get through that way.
    """
    layout = parse_daqprj(text, key="custom", title=title)
    surplus = len(values) - layout.value_count
    if surplus == 0:
        return layout
    if 0 < surplus <= MAX_UNNAMED_WORDS:
        widened = parse_daqprj(text, key="custom", title=title, digital_words=layout.digital_words + surplus)
        if not widened.check(values):
            return widened
    raise LayoutError(
        "count_mismatch",
        f"definition has {len(layout.analog)} analog values and {layout.digital_words} status words, "
        f"the boiler sends {len(values)} values",
    )


def extract_daqprj(text: str) -> str:
    """Cut the ``<DAQPRJ>...</DAQPRJ>`` block out of pasted text (e.g. a whole DAQ file)."""
    match = re.search(r"<DAQPRJ\b.*?</DAQPRJ\s*>", text, re.IGNORECASE | re.DOTALL)
    return match.group(0) if match else text.strip()


@cache
def builtin_layouts() -> dict[str, Layout]:
    """Return all layouts shipped with the integration, keyed by their identifier."""
    from .layout_data import BUILTIN_LAYOUTS  # noqa: PLC0415 - large module, loaded on demand

    return {key: parse_daqprj(definition, key=key, title=title) for key, (title, definition) in BUILTIN_LAYOUTS.items()}


def matching_layouts(values: tuple[str, ...] | list[str]) -> list[tuple[Layout, list[str]]]:
    """Return the built-in layouts with the line's value count, best match first.

    Each layout comes with the list of formatting problems found by ``Layout.check``.
    """
    matches = [
        (layout, layout.check(values)) for layout in builtin_layouts().values() if layout.value_count == len(values)
    ]
    matches.sort(key=lambda match: len(match[1]))
    return matches


def detect_layout(values: tuple[str, ...] | list[str]) -> Layout | None:
    """Return the built-in layout of a line if exactly one fits without problems."""
    fitting = [layout for layout, problems in matching_layouts(values) if not problems]
    return fitting[0] if len(fitting) == 1 else None
