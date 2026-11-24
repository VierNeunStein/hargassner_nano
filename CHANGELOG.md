# Changelog

## 2.0.0 (2026-11-16)

The integration now works with other firmware versions than the author's and is ready
for HACS.

### Added

- 15 built-in layouts for Nano.2, Nano-PK, Classic and HSV firmware versions. Version
  1.1.0 only accepted lines with 125 fields.
- Setup detects the layout of the boiler and shows decoded values to compare with the
  display before the entry is created.
- Any other firmware can be used by pasting the `DAQPRJ` block from a log file the
  boiler writes to its SD card.
- Reconfigure: change the address or detect the layout again after a firmware update.
- Repair notice when the boiler starts sending a different format.
- Entities for heating circuits A, 2 to 6 and B, room temperatures, hot water charging
  pump and pellet energy (kWh, for the energy dashboard).
- Option to create a disabled diagnostic entity for every other channel of the boiler.
- Diagnostics download without the boiler's address.
- English translation. Entity names and boiler states follow the language of the user.
- About 70 fault numbers are shown as text (German or English, depending on the
  language of the server).
- `tools/capture.py` shows what a boiler sends, without Home Assistant.
- Tests, GitHub workflows and HACS metadata.

### Changed

- **Breaking:** the state of *Boiler state* is a key such as `full_firing` that Home
  Assistant translates. It used to be German text.
- **Breaking:** the attributes `stoerungsnummer` and `beschreibung` are now `code` and
  `description`.
- Entities of parts that are not installed are created disabled instead of showing
  "unknown".
- The update interval is set in the options only. The value of existing entries is
  kept.
- New entries are named by the user instead of "Hargassner Nano (address)".
- Home Assistant 2025.10 or newer is required.

Existing entries keep working. All 25 entities of version 1.1.0 keep their unique ids.

## 1.1.0 (2026-11-15)

- Values are read from the correct fields. Version 1.0.0 read almost every value from
  the wrong position.
- Lines with an unexpected number of fields are rejected instead of shown.
- The stream is read line by line instead of in blocks of 1024 bytes.
- The fault sensor works.
- New entities: output, residual oxygen, boiler target temperature, return, combustion
  chamber, buffer charge level, hot water tank, fault text, heating circuit pump 1,
  return / buffer pump.
- A changed update interval takes effect.
- Probes that are not installed are reported as unknown.

## 1.0.0

- First version.
