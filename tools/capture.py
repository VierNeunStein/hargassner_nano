"""Read telegrams from a Hargassner boiler and show how the integration understands them.

Usage::

    python tools/capture.py 192.168.1.50
    python tools/capture.py 192.168.1.50 --all
    python tools/capture.py 192.168.1.50 --daqprj DAQ00000.DAQ

Needs nothing but Python 3.12 or newer. The script only listens on the boiler's telnet
port; it never sends anything. Its output is what a GitHub issue about an unsupported
firmware should contain.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.hargassner_nano"


def _register_package() -> None:
    """Make the protocol modules importable without Home Assistant."""
    if PACKAGE in sys.modules:
        return
    parent = types.ModuleType("custom_components")
    parent.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", parent)
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "hargassner_nano")]
    sys.modules[PACKAGE] = package


_register_package()

from custom_components.hargassner_nano.client import HargassnerError, async_read_telegram  # noqa: E402
from custom_components.hargassner_nano.layout import (  # noqa: E402
    Layout,
    LayoutError,
    extract_daqprj,
    matching_layouts,
    parse_custom_daqprj,
)
from custom_components.hargassner_nano.texts import preview_lines  # noqa: E402


def _read_definition(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1252"):
        try:
            return extract_daqprj(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return extract_daqprj(raw.decode("latin-1"))


def _show(layout: Layout, values: tuple[str, ...], *, everything: bool) -> None:
    telegram = layout.decode(values)
    for line in preview_lines(layout, telegram, "en"):
        print(f"    {line}")
    if not everything:
        return
    print("    --- all analog channels ---")
    for channel in layout.analog:
        unit = f" {channel.unit}" if channel.unit else ""
        print(f"    {channel.index + 1:4}  {channel.name:<24} {values[channel.index]}{unit}")
    print("    --- status bits that are set ---")
    for bit in layout.digital:
        if telegram.digital[bit.key]:
            print(f"    word {bit.word} bit {bit.bit:<2}  {bit.name}")


async def _main(args: argparse.Namespace) -> int:
    lines: list[tuple[str, ...]] = []
    try:
        for _ in range(args.lines):
            lines.append(await async_read_telegram(args.host, args.port))
    except HargassnerError as err:
        print(f"Could not read from the boiler: {err}")
        return 1

    values = lines[-1]
    print(f"The boiler sends {len(values)} values per line (after the leading 'pm').\n")
    for index, line in enumerate(lines, start=1):
        print(f"line {index}: pm {' '.join(line)}")
    print()

    if args.daqprj:
        try:
            layout = parse_custom_daqprj(_read_definition(Path(args.daqprj)), values, title=Path(args.daqprj).name)
        except LayoutError as err:
            print(f"The definition in {args.daqprj} does not fit: {err}")
            return 1
        problems = [problem for line in lines for problem in layout.check(line)]
        print(f"Definition {args.daqprj}: {len(layout.analog)} analog values, {layout.digital_words} status words")
        for problem in problems[:10]:
            print(f"    format problem: {problem}")
        _show(layout, values, everything=args.all)
        return 0

    matches = matching_layouts(values)
    if not matches:
        print("No built-in layout has this number of values.")
        print("Please read the README section about unsupported firmware and open an issue with this output.")
        return 2
    for layout, _ in matches:
        problems = [problem for line in lines for problem in layout.check(line)]
        verdict = "fits" if not problems else f"does NOT fit ({len(problems)} format problems)"
        print(f"{layout.key}: {layout.title} - {verdict}")
        for problem in problems[:5]:
            print(f"    format problem: {problem}")
        if not problems:
            _show(layout, values, everything=args.all)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host", help="IP address or host name of the boiler")
    parser.add_argument("--port", type=int, default=23, help="telnet port (default: 23)")
    parser.add_argument("--lines", type=int, default=3, help="number of lines to record (default: 3)")
    parser.add_argument("--daqprj", help="file with a <DAQPRJ> definition, e.g. a DAQ file from the SD card")
    parser.add_argument("--all", action="store_true", help="print every channel, not only the summary")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
