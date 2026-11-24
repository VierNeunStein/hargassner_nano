# Hargassner Nano for Home Assistant

Local, read-only integration for Hargassner pellet boilers with touch control
(Nano.2, Nano-PK, Classic, HSV and relatives). It reads the data stream the boiler
provides on its network port. No cloud, no account and no extra hardware are needed.

[Deutsche Anleitung](README.de.md)

- Set up in the user interface. The integration detects the data format of your
  firmware and shows you a few decoded values to compare with the boiler's display
  before anything is created.
- 15 firmware layouts are built in. For any other firmware you paste the description
  the boiler writes itself (see [My firmware is not listed](#my-firmware-is-not-listed)).
- If the boiler ever sends a format the integration does not expect (for example after
  a firmware update), the entities become unavailable and a repair notice appears. Wrong
  values are never shown.
- Entity names and boiler states are available in English and German.
- The integration only listens. It never sends anything to the boiler and cannot
  change any setting.

> This is a community project. It is not affiliated with or supported by Hargassner.

## Entities

Created when the boiler provides the value. Entities of parts that are not installed
(second heating circuit, buffer, hot water tank) are created disabled.

| Entity | Notes |
|---|---|
| Boiler state | Off, Ignition, Full firing, Ash removal, ... |
| Fault message, Fault | Text of the current fault and a problem sensor |
| Boiler, return, flue gas and combustion chamber temperature | |
| Boiler target temperature, output, residual oxygen, induced draft fan | |
| Outside temperature (current and average) | |
| Buffer temperature top / middle / bottom, charge level, target temperature | |
| Hot water tank temperature, hot water charging pump | |
| Heating circuits A, 1 to 6 and B: flow temperature, flow target, pump, room temperature, room target | Room values need a room unit |
| Pellet stock, pellet consumption | Consumption is a counter in kg |
| Pellet energy | kWh, for the energy dashboard |
| Return / buffer pump | |

With the option *Create entities for all other channels* every remaining value and
status bit of the boiler (often more than 150) is added as a disabled diagnostic
entity, named as the boiler names it, for example `Tplat` or `ES Run`.

## Requirements

- Home Assistant 2025.10 or newer. Developed and tested with 2026.11.
- The boiler's touch control is connected to your network by cable and reachable from
  Home Assistant. The display shows its IP address in the network settings. Give the
  boiler a fixed address in your router.
- Port 23 of the boiler is reachable. The Hargassner internet gateway and app are not
  required.

## Security

- The boiler's port 23 has no password and no encryption. Anyone who can reach it can
  read the boiler's values. **Never forward port 23 to the internet.** Keep the boiler
  in your local network, ideally in a separate network (VLAN) for devices like this.
- The integration needs no internet access and no account. It only reads from the
  boiler and never sends anything to it.
- Diagnostics files contain the last data line and the decoded values, but not the
  address of the boiler.

### HACS

1. In HACS open the menu (three dots) and choose *Custom repositories*.
2. Add `https://github.com/VierNeunStein/hargassner_nano` with the type
   *Integration*.
3. Search for *Hargassner Nano*, download it and restart Home Assistant.

### Manually

Copy the folder `custom_components/hargassner_nano` into the `custom_components`
folder of your Home Assistant configuration and restart Home Assistant.

## Setup

1. *Settings → Devices & services → Add integration → Hargassner Nano*.
2. Enter a name and the IP address of the boiler.
3. The integration reads a line from the boiler and selects the matching layout. You
   see a few current values, for example boiler temperature, outside temperature and
   pellet stock. Compare them with the display of the boiler and finish.

If several built-in layouts have the length of your boiler's data line, you are asked
to choose. Pick the one for your firmware version and check the values.

To change the address later, or to detect the layout again after a firmware update,
open the entry's menu and choose *Reconfigure*.

## Supported boilers and firmware

The firmware decides how many values the boiler sends and what they mean. The firmware
version is shown on the touch display.

| Layout | Values per line | Status |
|---|---|---|
| Nano.2 | 124 | Checked against the display of the author's Nano.2 |
| Nano.2, V14.1HAR.q1 | 120 | From a manufacturer log file |
| Nano-PK Plus, V14.1HAR.q | 121 | Community |
| Nano.2 / Nano-PK, V14.1HAR.q1, variant with 9 status words | 121 | Community |
| Nano.2, V14.1HAR.q with solar and 3 heating circuits | 140 | Community |
| Nano.2, V14.1HAR.q with auxiliary buffer and AUP | 155 | Community |
| Nano-PK / HSV, V14.0HAR.q | 120 | Community |
| Nano-PK, V14.0o3 | 113 | Community |
| Nano-PK, V14.0n2 | 135 | Community |
| Nano-PK, V14.0n | 112 | Community |
| Nano-PK / Classic Lambda, V14.0m | 154 | Community |
| Nano-PK, V14.0l | 149 | Community |
| Nano-PK, V14.0k | 190 | Community |
| HSV / Classic, V14.0d | 171 | Community |
| Nano, V40.0HAR.az15 | 157 | Community |

*Community* layouts were collected by the projects named under [Credits](#credits).
The author can only test the first one, so please use the value check during setup
and report layouts that work or do not work.

## My firmware is not listed

Every boiler can describe its own data format:

1. On the touch display, enable logging to the SD card and insert an SD card for a few
   minutes.
2. On the card you find a file such as `DAQ00000.DAQ`. Open it in a text editor.
3. Near the top is a block that starts with `<DAQPRJ>` and ends with `</DAQPRJ>`.
   Copy the whole block.
4. During setup choose *Use the boiler's own description (DAQPRJ)* and paste it. If no
   built-in layout has the length of your boiler's data line, this step appears
   automatically.

Please also open an issue and attach the block, so the layout can be built in for
everyone with the same firmware.

## Options

*Settings → Devices & services → Hargassner Nano → Configure*

| Option | Default | Meaning |
|---|---|---|
| Update interval | 60 s | How often the values are read (10 to 3600 s) |
| Energy content of the pellets | 4.8 kWh/kg | Used by the pellet energy sensor |
| Create entities for all other channels | off | See [Entities](#entities) |

## Energy dashboard

The sensor *Pellet energy* adds up the pellets burnt times their energy content. Add
it under *Settings → Dashboards → Energy → Gas consumption* to see the heating
energy next to your electricity. It is the energy content of the fuel, not the heat
delivered; multiply the energy content by your boiler's efficiency if you prefer that.

The boiler counts whole kilograms, so the sensor moves in steps of about 5 kWh.
Changing the energy content only affects pellets burnt from then on.

## Troubleshooting

- **Cannot connect:** check the address, that the network cable is plugged into the
  touch control and that port 23 is not blocked between Home Assistant and the boiler.
- **Values are wrong:** the selected layout does not belong to your firmware. Choose
  *Reconfigure* and select another layout or use the boiler's own description.
- **Entities unavailable with a repair notice after a firmware update:** choose
  *Reconfigure*; the layout is detected again.
- **Reporting a problem:** open the device page, choose *Download diagnostics* and
  attach the file to your issue. It contains the last data line and the decoded
  values, but not the address of your boiler.
- **Debug log:**

  ```yaml
  logger:
    logs:
      custom_components.hargassner_nano: debug
  ```

- **Without Home Assistant:** `python tools/capture.py 192.168.1.50 --all` (Python 3.12
  or newer, no packages needed) prints what the boiler sends and how each built-in
  layout decodes it.

## How it works

The touch control sends one line of text per second to every client connected to its
port 23: the word `pm`, then all analog values, then several status words whose bits
are pumps, motors and switches. The integration connects once per update interval,
reads a complete line and disconnects, so the port stays free for other tools most of
the time. Which position means what comes from the layout, written in the same
`DAQPRJ` format the boiler uses in its own log files.

The boiler prints some values always without decimals and some always with two. The
integration uses this to tell apart layouts of the same length and to reject lines
that do not belong to the configured layout.

## Upgrading from version 1.x

Install the new version and restart. The existing entry keeps working: the layout is
detected on the first start, and all entities keep their ids and history. What changes:

- The state of *Boiler state* is now a fixed English key such as `full_firing` that is
  shown translated (before: German text). Adjust automations that compare the state.
- The attributes `stoerungsnummer` and `beschreibung` are now `code` and `description`.
- New entities appear, most of them disabled: other heating circuits, room
  temperatures, hot water charging pump, pellet energy.

## Credits

- [nano_pk](https://github.com/TheRealKillaruna/nano_pk) by TheRealKillaruna and
  [IP-HargassnerIntegration](https://github.com/bauer-group/IP-HargassnerIntegration)
  by BAUER GROUP collected the channel lists of many firmware versions. The built-in
  layouts and fault texts of this integration are based on their work. Both are
  alternatives worth a look, for example if you prefer a permanent connection with
  updates every few seconds.
- [Jahislove](https://github.com/Jahislove) published the first analysis of the data
  stream that these projects build on.

## License

[MIT](LICENSE). The built-in layouts and fault texts are based on data from nano_pk
(Apache-2.0) and IP-HargassnerIntegration (MIT); their notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
