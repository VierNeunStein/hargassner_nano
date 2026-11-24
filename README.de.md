# Hargassner Nano für Home Assistant

Lokale, rein lesende Integration für Hargassner-Pelletheizungen mit Touch-Steuerung
(Nano.2, Nano-PK, Classic, HSV und Verwandte). Sie liest den Datenstrom, den die
Heizung an ihrem Netzwerkanschluss ausgibt. Cloud, Benutzerkonto und zusätzliche
Hardware sind nicht nötig.

[English version](README.md)

- Einrichtung in der Oberfläche. Die Integration erkennt das Datenformat deiner
  Firmware und zeigt dir einige entschlüsselte Werte zum Vergleich mit dem Display der
  Heizung, bevor etwas angelegt wird.
- 15 Firmware-Formate sind eingebaut. Für jede andere Firmware fügst du die
  Beschreibung ein, die die Heizung selbst schreibt (siehe
  [Meine Firmware ist nicht dabei](#meine-firmware-ist-nicht-dabei)).
- Sendet die Heizung ein unerwartetes Format (zum Beispiel nach einem Firmware-Update),
  werden die Entitäten „nicht verfügbar“ und es erscheint ein Reparaturhinweis. Falsche
  Werte werden nie angezeigt.
- Entitätsnamen und Betriebszustände gibt es auf Deutsch und Englisch.
- Die Integration hört nur zu. Sie sendet nichts an die Heizung und kann keine
  Einstellung verändern.

> Dies ist ein Community-Projekt, das nicht mit Hargassner verbunden ist und von
> Hargassner nicht unterstützt wird.

## Entitäten

Angelegt wird, was die Heizung liefert. Entitäten nicht vorhandener Anlagenteile
(zweiter Heizkreis, Puffer, Boiler) werden deaktiviert angelegt.

| Entität | Hinweis |
|---|---|
| Betriebszustand | Aus, Zündung, Leistungsbrand, Entaschung, ... |
| Störung, Fehlerstatus | Text der aktuellen Störung und ein Problem-Sensor |
| Kessel-, Rücklauf-, Abgas- und Brennraumtemperatur | |
| Kessel Solltemperatur, Leistung, Restsauerstoff, Saugzug | |
| Außentemperatur (aktuell und Mittel) | |
| Puffer Temperatur oben / Mitte / unten, Füllgrad, Solltemperatur | |
| Boilertemperatur, Boilerladepumpe | |
| Heizkreise A, 1 bis 6 und B: Vorlauftemperatur, Vorlauf-Soll, Pumpe, Raumtemperatur, Raum-Soll | Raumwerte brauchen ein Raumgerät |
| Silostand, Pelletverbrauch | Verbrauch ist ein Zähler in kg |
| Pelletenergie | kWh, für das Energie-Dashboard |
| Rücklauf-/Pufferpumpe | |

Mit der Option *Entitäten für alle übrigen Kanäle anlegen* kommt jeder weitere Wert und
jedes Statusbit der Heizung (oft mehr als 150) als deaktivierte Diagnose-Entität dazu,
benannt wie in der Heizung, zum Beispiel `Tplat` oder `ES Run`.

## Voraussetzungen

- Home Assistant 2025.10 oder neuer. Entwickelt und getestet mit 2026.11.
- Die Touch-Steuerung der Heizung hängt per Kabel im Netzwerk und ist von Home
  Assistant aus erreichbar. Die IP-Adresse steht am Display in den
  Netzwerkeinstellungen. Gib der Heizung im Router eine feste Adresse.
- Port 23 der Heizung ist erreichbar. Das Hargassner-Internet-Gateway und die App
  werden nicht gebraucht.

## Sicherheit

- Port 23 der Heizung hat weder Passwort noch Verschlüsselung. Wer ihn erreicht, kann
  die Werte der Heizung mitlesen. **Gib Port 23 niemals ins Internet frei** (keine
  Portweiterleitung). Lass die Heizung im lokalen Netz, am besten in einem eigenen
  Netz (VLAN) für solche Geräte.
- Die Integration braucht weder Internetzugang noch ein Konto. Sie liest nur von der
  Heizung und sendet nie etwas an sie.
- Diagnosedateien enthalten die letzte Datenzeile und die entschlüsselten Werte, aber
  nicht die Adresse der Heizung.

## Installation

### HACS

1. In HACS das Menü (drei Punkte) öffnen und *Benutzerdefinierte Repositories* wählen.
2. `https://github.com/VierNeunStein/hargassner_nano` mit dem Typ *Integration*
   hinzufügen.
3. Nach *Hargassner Nano* suchen, herunterladen und Home Assistant neu starten.

### Von Hand

Den Ordner `custom_components/hargassner_nano` in den Ordner `custom_components`
deiner Home-Assistant-Konfiguration kopieren und Home Assistant neu starten.

## Einrichtung

1. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Hargassner Nano*.
2. Einen Namen und die IP-Adresse der Heizung eingeben.
3. Die Integration liest eine Zeile von der Heizung und wählt das passende Format. Du
   siehst einige aktuelle Werte, zum Beispiel Kesseltemperatur, Außentemperatur und
   Pelletlagerstand. Vergleiche sie mit dem Display der Heizung und schließe ab.

Haben mehrere eingebaute Formate die Länge der Datenzeile deiner Heizung, wirst du
gefragt. Wähle das Format deiner Firmware-Version und prüfe die Werte.

Um später die Adresse zu ändern oder nach einem Firmware-Update das Format neu erkennen
zu lassen, im Menü des Eintrags *Neu konfigurieren* wählen.

## Unterstützte Heizungen und Firmware

Die Firmware bestimmt, wie viele Werte die Heizung sendet und was sie bedeuten. Die
Firmware-Version steht am Touch-Display.

| Format | Werte pro Zeile | Stand |
|---|---|---|
| Nano.2 | 124 | Mit dem Display der Nano.2 des Autors abgeglichen |
| Nano.2, V14.1HAR.q1 | 120 | Aus einer Aufzeichnung des Herstellers |
| Nano-PK Plus, V14.1HAR.q | 121 | Community |
| Nano.2 / Nano-PK, V14.1HAR.q1, Variante mit 9 Statusworten | 121 | Community |
| Nano.2, V14.1HAR.q mit Solar und 3 Heizkreisen | 140 | Community |
| Nano.2, V14.1HAR.q mit Zusatzpuffer und AUP | 155 | Community |
| Nano-PK / HSV, V14.0HAR.q | 120 | Community |
| Nano-PK, V14.0o3 | 113 | Community |
| Nano-PK, V14.0n2 | 135 | Community |
| Nano-PK, V14.0n | 112 | Community |
| Nano-PK / Classic Lambda, V14.0m | 154 | Community |
| Nano-PK, V14.0l | 149 | Community |
| Nano-PK, V14.0k | 190 | Community |
| HSV / Classic, V14.0d | 171 | Community |
| Nano, V40.0HAR.az15 | 157 | Community |

Die *Community*-Formate haben die unter [Dank](#dank) genannten Projekte gesammelt. Der
Autor kann nur das erste selbst testen. Nutze deshalb die Werteprüfung bei der
Einrichtung und melde Formate, die funktionieren oder nicht funktionieren.

## Meine Firmware ist nicht dabei

Jede Heizung kann ihr Datenformat selbst beschreiben:

1. Am Touch-Display die Aufzeichnung auf SD-Karte aktivieren und für einige Minuten
   eine SD-Karte einstecken.
2. Auf der Karte liegt eine Datei wie `DAQ00000.DAQ`. Öffne sie in einem Texteditor.
3. Weit oben steht ein Block, der mit `<DAQPRJ>` beginnt und mit `</DAQPRJ>` endet.
   Kopiere den ganzen Block.
4. Bei der Einrichtung *Beschreibung der Heizung verwenden (DAQPRJ)* wählen und den
   Block einfügen. Hat kein eingebautes Format die Länge der Datenzeile deiner
   Heizung, erscheint dieser Schritt von selbst.

Bitte eröffne zusätzlich ein Issue und hänge den Block an, damit das Format für alle
mit derselben Firmware eingebaut werden kann.

## Optionen

*Einstellungen → Geräte & Dienste → Hargassner Nano → Konfigurieren*

| Option | Standard | Bedeutung |
|---|---|---|
| Abfrageintervall | 60 s | Wie oft die Werte gelesen werden (10 bis 3600 s) |
| Heizwert der Pellets | 4,8 kWh/kg | Grundlage für den Sensor Pelletenergie |
| Entitäten für alle übrigen Kanäle anlegen | aus | Siehe [Entitäten](#entitäten) |

## Energie-Dashboard

Der Sensor *Pelletenergie* summiert die verbrannten Pellets mal Heizwert. Trage ihn
unter *Einstellungen → Dashboards → Energie → Gasverbrauch* ein, dann siehst du die
Heizenergie neben dem Strom. Es ist der Energieinhalt des Brennstoffs, nicht die
abgegebene Wärme. Wer lieber die Wärme sehen will, multipliziert den Heizwert mit dem
Wirkungsgrad des Kessels.

Die Heizung zählt ganze Kilogramm, der Sensor steigt also in Schritten von etwa 5 kWh.
Ein geänderter Heizwert wirkt nur auf Pellets, die danach verbrannt werden.

## Fehlersuche

- **Keine Verbindung:** Adresse prüfen, ob das Netzwerkkabel an der Touch-Steuerung
  steckt und ob Port 23 zwischen Home Assistant und Heizung nicht gesperrt ist.
- **Werte sind falsch:** Das gewählte Format gehört nicht zu deiner Firmware. *Neu
  konfigurieren* wählen und ein anderes Format nehmen oder die Beschreibung der Heizung
  verwenden.
- **Entitäten nach einem Firmware-Update nicht verfügbar, mit Reparaturhinweis:** *Neu
  konfigurieren* wählen, das Format wird neu erkannt.
- **Ein Problem melden:** Auf der Geräteseite *Diagnose herunterladen* wählen und die
  Datei an das Issue hängen. Sie enthält die letzte Datenzeile und die entschlüsselten
  Werte, aber nicht die Adresse deiner Heizung.
- **Debug-Protokoll:**

  ```yaml
  logger:
    logs:
      custom_components.hargassner_nano: debug
  ```

- **Ohne Home Assistant:** `python tools/capture.py 192.168.1.50 --all` (Python 3.12
  oder neuer, keine Pakete nötig) zeigt, was die Heizung sendet und wie jedes
  eingebaute Format es entschlüsselt.

## So funktioniert es

Die Touch-Steuerung sendet jede Sekunde eine Textzeile an jeden Client, der mit ihrem
Port 23 verbunden ist: das Wort `pm`, dann alle Analogwerte, dann mehrere Statusworte,
deren Bits Pumpen, Motoren und Schalter sind. Die Integration verbindet sich einmal pro
Abfrageintervall, liest eine vollständige Zeile und trennt wieder. So bleibt der Port
die meiste Zeit für andere Werkzeuge frei. Welche Position was bedeutet, steht im
Format, geschrieben im selben `DAQPRJ`-Aufbau, den die Heizung in ihren eigenen
Aufzeichnungen verwendet.

Die Heizung schreibt manche Werte immer ohne und manche immer mit zwei
Nachkommastellen. Daran unterscheidet die Integration Formate gleicher Länge und
erkennt Zeilen, die nicht zum eingestellten Format gehören.

## Umstieg von Version 1.x

Neue Version installieren und neu starten. Der vorhandene Eintrag läuft weiter: Das
Format wird beim ersten Start erkannt, alle Entitäten behalten ihre IDs und ihren
Verlauf. Was sich ändert:

- Der Zustand von *Betriebszustand* ist jetzt ein fester englischer Schlüssel wie
  `full_firing`, der übersetzt angezeigt wird (vorher deutscher Text). Automationen,
  die den Zustand vergleichen, müssen angepasst werden.
- Die Attribute `stoerungsnummer` und `beschreibung` heißen jetzt `code` und
  `description`.
- Es kommen neue Entitäten dazu, die meisten deaktiviert: weitere Heizkreise,
  Raumtemperaturen, Boilerladepumpe, Pelletenergie.

## Dank

- [nano_pk](https://github.com/TheRealKillaruna/nano_pk) von TheRealKillaruna und
  [IP-HargassnerIntegration](https://github.com/bauer-group/IP-HargassnerIntegration)
  der BAUER GROUP haben die Kanallisten vieler Firmware-Versionen gesammelt. Die
  eingebauten Formate und Störungstexte dieser Integration beruhen auf ihrer Arbeit.
  Beide sind einen Blick wert, etwa wenn du lieber eine dauerhafte Verbindung mit
  Aktualisierung im Sekundentakt möchtest.
- [Jahislove](https://github.com/Jahislove) hat die erste Analyse des Datenstroms
  veröffentlicht, auf der diese Projekte aufbauen.

## Lizenz

[MIT](LICENSE). Die eingebauten Formate und Störungstexte beruhen auf Daten aus
nano_pk (Apache-2.0) und IP-HargassnerIntegration (MIT); deren Lizenzhinweise stehen in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
