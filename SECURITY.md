# Lokaler Zugriff und Sicherheitsgrenzen

Die App veröffentlicht keinen LAN-Port. Zugriff erfolgt über Home Assistant
Ingress. Die App akzeptiert nur den Supervisor-Ingress-Peer und prüft dessen
Benutzerkennung gegen aktive HA-Benutzer. Änderungen, Fotos, Exporte und
Wiederherstellung verlangen Administratorrechte. Es wird kein HA-Token an den
Browser weitergegeben und kein beliebiger HA-API-Proxy angeboten.

Cross-Site-Browser-Schreibzugriffe werden abgelehnt. Vertragsnamen werden vor
HTML-Ausgabe maskiert. JSON-Felder, Zahlen, Datum, Einheiten und historische
Intervalle werden geprüft. Fotos sind auf 12 MB/20 Megapixel begrenzt;
es läuft höchstens eine Verarbeitung gleichzeitig. Vorschläge sind kurzlebig,
an den Nutzer gebunden und werden erst nach Bestätigung als Zahl gespeichert.
ONNX-Telemetrie ist deaktiviert. Fotos und erkannte Texte werden nicht protokolliert.

Die App benötigt beim Start Schreibzugriff auf die HA-Konfiguration, um ihre
gebündelte Sensoranbindung zu installieren. Das ist ein bewusstes Privileg dieser
Ein-Paket-Lösung. Symlinks oder fremde Integrationsmanifest-Domains werden
abgelehnt. Vorige Versionen werden gesichert; die vollständige Anbindung wird über
Verzeichniswechsel mit Rückfallpfad aktualisiert. Nach Einrichtung des Datenordners
gibt der Web-/OCR-Prozess Rootrechte ab und läuft mit UID/GID 65534.

Sicherungen enthalten private Vertragsdaten. Die maßgebliche Historie liegt in der
HA-Konfiguration, zusätzliche Snapshots in den App-Daten. Vollständige HA-Backups
müssen beide enthalten. Die portable JSON-Datei sollte privat aufbewahrt werden.
Eine Wiederherstellung ersetzt den ausdrücklich ausgewählten Vertrag; zuvor exportieren.

Die Paketversionen sind festgelegt und die CI prüft bekannte Sicherheitsmeldungen.
Eine Prüfung ohne Treffer ist keine Garantie gegen unbekannte Schwachstellen.
Zum Bauen werden Pakete vom öffentlichen Paketindex und das offizielle Python-Image
geladen; Bilder und Verträge werden dabei nicht hochgeladen.

## Sicherheitsproblem melden

Bitte Sicherheitslücken vertraulich über [Report a vulnerability](https://github.com/OrbitNestLab/AbschlagsRadar/security/advisories/new) melden. Normale Fehler gehören in die [Issues](https://github.com/OrbitNestLab/AbschlagsRadar/issues).
Keine Tokens, Passwörter, Fotos oder privaten Backups hochladen. Version 0.4.5 ist die erste experimentelle öffentliche Version; Korrekturen werden über neue App-Versionen bereitgestellt. Der Fotoscan ist eine Beta-Funktion: erkannte Zählerstände vor dem Speichern immer selbst kontrollieren.
