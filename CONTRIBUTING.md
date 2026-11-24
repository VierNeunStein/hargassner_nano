# Contributing

Reports about firmware versions are the most valuable contribution: a layout that
works, one that shows wrong values, or the `DAQPRJ` block of a firmware that is not
built in. Please use the *Firmware layout* issue form.

## Layout of the code

Everything in `custom_components/hargassner_nano`:

| File | Purpose |
|---|---|
| `client.py` | Reads a line from the boiler. Never sends anything. |
| `layout.py` | Parses `DAQPRJ` definitions, decodes lines, detects the layout of a line. |
| `layout_data.py` | The built-in `DAQPRJ` definitions. |
| `model.py` | Which entities exist for a layout and how their values are derived. |
| `texts.py` | Fault texts and the value preview of the setup dialog. |
| the rest | Home Assistant: config flow, coordinator, entities, diagnostics, translations. |

The first five files do not import Home Assistant, so they can be tested and used
without it.

## Adding a layout

1. Add an entry to `BUILTIN_LAYOUTS` in `layout_data.py`: a key, a title that ends
   with `(N values)` and the `DAQPRJ` block exactly as the boiler wrote it. `N` is the
   number of analog channels plus the number of status words.
2. Add the key and `N` to `VALUE_COUNTS` in `tests/test_layout.py`.
3. Add a row to the tables in `README.md` and `README.de.md`.

Never rename a key or change the channel order of an existing layout. Config entries
refer to layouts by key, and a changed order would move values between entities on
every installation that uses the layout. Add a new entry instead.

## Adding an entity

Add a `SensorSpec` or `BinarySpec` to `model.py`, naming the channel as it appears in
the `DAQPRJ` definitions, and its name to `translations/en.json` and
`translations/de.json`. Keys are part of the unique ids and must not be renamed.

## Tests

```bash
python -m unittest discover -s tests -t .
```

No packages are needed. `pytest` works as well. The GitHub workflow additionally runs
Home Assistant's `hassfest` and the HACS validation.

To see what a real boiler sends:

```bash
python tools/capture.py 192.168.1.50 --all
```
