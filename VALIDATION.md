# Validierung · v0.4.4

Stand: 03.10.2026. Keine öffentliche Veröffentlichung erfolgt.

## Wiederherstellung und Entitäten v0.4.4

- Serverprüfung: Strom/Gas gemeinsam in leere App importieren, automatische/manuelle
  Ablesungen erhalten, bestehende Ziele ersetzen, Energieart prüfen, Rechte und
  ungültige Auswahl vor Änderungen abweisen, neue Verträge bei Fehlern zurückrollen.
- Browserprüfung: leere App → Datei prüfen → beide Verträge neu anlegen; neuer Reiter
  zeigt registrierte/umbenannte IDs, fehlende und deaktivierte Werte, direkte Links
  und Kopieren ohne Clipboard-API; mobile Ansicht und bestehende Reiter ohne Layoutblitzen.
- 82 Python-Tests, 5 Browserprüfungen und die Formatierungs-/Paketprüfungen bestanden.
- Isoliertes echtes HA 2026.9.4: Sicherung mit zwei synthetischen Verträgen direkt
  in die noch nie eingerichtete App importiert; beide Historien und 48 Sensoren erhalten.
  Registry-Umbenennung und deaktivierter Sensor korrekt in der App abgebildet.
  Vorhandenen Vertrag ersetzt und kalte Datenvolume-Wiederherstellung bestanden.
  Alle temporären Testcontainer, Datenvolumes und das Testnetz anschließend entfernt.
- Update auf der privaten Installation: alle 36 App-Dateien stimmen mit dem Release
  überein; interne Sensoranbindung 0.4.4 und HA-Konfigurationsprüfung bestätigt.

## Oberfläche v0.4.3

Die Vormerkungsanzeige, Eingabe und Bestätigungsbuttons sind aus beiden
Vertragsansichten entfernt. Tatsächlich bezahlte Zahlungen und Empfehlungen bleiben.
Ältere Vormerkungen bleiben in Daten/Sicherungen und im Rechenmodell kompatibel;
vorhandene Sensor-IDs werden nicht geändert.

Das Stylesheet wird einmal eingesetzt und bleibt bei Reiterwechsel und Aktualisierung
verbunden. Die erste Ansicht bleibt verborgen, bis die Gestaltung geladen ist.
Ein Ladefehler zeigt eine Fehlermeldung statt unformatierter Vertragsdaten.

Browser-Regressionsprüfungen verwenden ausschließlich synthetische Verträge:
verzögertes Stylesheet, wiederholte Reiterwechsel in Strom und Gas bei 1440/390 px,
Aktualisierung/Verbindungsfehler und fehlgeschlagenes Stylesheet. Beobachtet werden
sichtbare Layouts über Animationsframes, unveränderte Stylesheet-Verbindung,
nur eine CSS-Anfrage und das Fehlen sämtlicher Vormerkungsanzeigen/-aktionen.

Reproduzierbar: `pnpm install --frozen-lockfile`,
`pnpm exec playwright install chromium`, `pnpm test:browser`.
Optional `PLAYWRIGHT_EXECUTABLE_PATH` auf einen vorhandenen Chromium-Browser setzen.
Die GitHub-Prüfung führt diese Browser-Tests zusätzlich aus. Runtime-Pakete der App
werden dadurch nicht erweitert.

## Automatisierte lokale Prüfungen

- 78 Python-Tests bestanden, keine übersprungenen Tests; echte RapidOCR-Inferenz auf einem synthetischen Ziffernbild enthalten.
- Datumsgenaue Zählerstände, Intervalle ohne Doppelzählung, Gasmodi und Umrechnung.
- Tarif-/Abschlagswechsel, bestätigte Zahlungen heute, abweichender Bankbuchungstag, vorgemerkte Zahlungen und verbleibende Termine.
- Persönliche Monatsverteilung bei lückenhafter Historie und Anpassung an anhaltende Verbrauchsänderungen.
- Fehlende Daten, Schaltjahre, Überzahlung, extreme/ungültige Eingaben und endliche Sensorwerte.
- Fotozugriff, Größenbegrenzung, Vorschlagsbestätigung und Administratorprüfung.
- Portable Sicherungen einschließlich automatischer Ablesungen, geprüfte Wiederherstellung und Snapshot-Begrenzung.
- Vollständige interne Installation, Rückfall nach Kopierfehler, Wiederaufnahme nach Unterbrechung und Ablehnung von Datei-Umleitungen.
- JavaScript-Prüfung: Vorzeichen/Farben, Eurobeträge, Zähler-Nachkommastellen und maskierte Texte.
- Ruff, Formatierung, Shellsyntax, JSON/Python-Syntax, Versionsabgleich und identische gebündelte Quelldateien bestanden.

Frische lokale Testumgebung: macOS ARM64, Python 3.12.14, Node 24,
gepinnte Entwicklungs- und App-Abhängigkeiten. Kein ARM-App-Build behauptet.

## Private Installation auf Home Assistant

Die umfassenden Prüfungen vom 02.10.2026 gelten für v0.4.2; v0.4.3 verändert
die Oberfläche und Versionsangaben. Die 78 Backend-Tests bestehen erneut; zusätzlich bestehen alle drei neuen Browser-Regressionsprüfungen.
Nach dem privaten Update sind die Einstellungen, Historien, automatischen Ablesungen
und sämtliche Prognosewerte gegenüber dem unmittelbar davor gesicherten Stand
unverändert. Alle 48 nativen Sensoren bleiben verfügbar; die installierten 36 App-Dateien
entsprechen dem Release-Quellstand. Flackerfreie Navigation ohne Vormerkungsfelder
ist zusätzlich gegen die echte Ingress-App geprüft.

Geprüft mit Home Assistant 2026.9.4 / Python 3.14.6 auf AMD64.
App-Python 3.12.15; tatsächlicher Web-/OCR-Prozess läuft mit UID 65534.

- Privates Supervisor-Update, Installation der internen Sensoranbindung und anschließender HA-Neustart.
- HA-Konfigurationsprüfung, authentifizierte Ingress-Oberfläche und Seitenleisteneintrag.
- Temporäre Strom-/Gas-Verträge über die wirkliche App angelegt; deutsche/ISO-Daten, Intervalle, Tarife, Abschlagsänderungen, Zahlungen, Vormerkung, Bestätigung und JSON-Wiederherstellung geprüft.
- Temporäre Verträge anschließend entfernt; ursprüngliche Vertragsdaten und Ablesungen erhalten.
- 24 native Sensoren je Energieart, insgesamt 48; keine nicht verfügbaren Entitäten.
- Desktop und 390-px-Mobilansicht im isolierten Browser, getrenntes Gasformular, rotes Minus/grünes Plus, Restperioden-Empfehlung und lokaler Fotoscan geprüft.
- Fotoscan mit synthetischen Ziffern einschließlich bestätigter Speicherung und einmaliger Vorschlagsnutzung im temporären Testvertrag geprüft. Kein Testwert wurde in produktive Verträge geschrieben.
- Der überflüssige frühere OCR-Hilfscontainer wurde entfernt.

## Leere Installation und Wiederherstellung

Eine getrennte HA-/App-Testumgebung mit eigenen leeren Datenvolumes, synthetischem
Benutzer und internem Docker-Netzwerk wurde auf dem AMD64-System geprüft.
Die App verwendet denselben gebauten Quellstand; ein Testproxy ersetzt ausschließlich
die Supervisor-Kommunikation. Produktive Konfiguration und Zugangsdaten werden
nicht in diese Testumgebung übernommen.

- Automatische Installation der Sensoranbindung und genau ein Neustart der leeren HA-Instanz.
- Leere Startseite, Anlage von Strom/Gas mit optional leerem Sensor und 48 nativen Entitäten.
- Automatische Sensorablesung, Erkennung eines zurückspringenden Zählers und anschließende Erholung.
- JSON-Export mit automatischen Ablesungen, Vorschau und Wiederherstellung.
- Kalt kopierte HA-/App-Datenvolumes erhalten Vertrags-/Entitätskennungen, Einstellungen, Historien und beschreibbare App-Snapshots.
- Alle ausschließlich für diesen Test angelegten Container, Volumes und Netzwerke wurden entfernt.

Dies ist keine vollständige Supervisor-Backup-Wiederherstellung auf einer neuen HA-OS-Maschine.
Der komplette macOS-Doppelklick-Starter auf einer fabrikneuen Instanz bleibt ebenfalls offen.

## Geschwindigkeit und Abhängigkeiten

Ein reproduzierbarer synthetischer Modellvergleich mit 100 Jahren Historie und
500 Tarifwechseln sank lokal von 0,5392 auf 0,0101 Sekunden. Mit 10.000
Tarifwechseln benötigte der neue Stand 0,0243 Sekunden. Die Zeiten betreffen
diesen Modelltest; sie sind keine pauschale Zusage für die App-Geschwindigkeit.

24 installierte Python-Pakete wurden gegen bekannte Sicherheitsmeldungen geprüft:
keine Treffer nach dem Paketupdate. Versionspins und Prüfung sind vorbereitet.
Dies ersetzt keine Prüfung des gesamten Betriebssystems oder unbekannter Schwachstellen.

## Grenzen vor der ersten öffentlichen Freigabe

- Reale Repository-Adresse, Maintainer und privater Sicherheitskontakt ergänzen; danach öffentlicher Metadatencheck, App-Lint/Builder und Hassfest.
- Vollständigen App-Store-Erstinstallationsweg und echte Supervisor-Backup-Wiederherstellung separat prüfen.
- Reale mechanische/digitale Zählerfotos mit Reflexionen und roten Nachkommastellen prüfen. Bestätigung vor Speicherung bleibt erforderlich.
- Weitere HA-Versionen, Mobilgeräte und Hardware: bislang nur AMD64-App validiert.
- Langfristige Recorder-Verläufe/Diagrammkarten benötigen Beobachtung im normalen Betrieb.
- Gasfaktor muss aus der tatsächlichen Rechnung stammen; persönliche Saisonverteilung ist noch nicht wetterbereinigt.

Die öffentliche CI ist vorbereitet, wurde aber ohne ein veröffentlichtes GitHub-Repository
nicht auf GitHub ausgeführt. Das Release-Paket enthält weder private Testdaten noch Zugangsdaten.
