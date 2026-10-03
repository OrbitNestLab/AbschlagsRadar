# AbschlagsRadar App

Die App läuft als eigener Dienst auf Home Assistant OS / Supervised. **Weboberfläche öffnen**
oder **In Seitenleiste anzeigen** führt direkt in die lokale Oberfläche. Anmeldung und
Zugriff laufen über Home Assistant Ingress; ein separates Passwort ist nicht erforderlich.

Die intern gebündelte Sensoranbindung ist Teil derselben Installation. Vorhandene
Verträge werden automatisch angezeigt, ohne Import oder doppelte Datenpflege. Neue Verträge
lassen sich in der App als Strom oder Gas anlegen. Tarife, Zählerstände, Zahlungen und
Abschlagsänderungen werden validiert in den Integrationseinträgen gespeichert.

Der Fotoscan läuft direkt im App-Container. Fotos werden nur im Arbeitsspeicher verarbeitet
und nach dem Scan verworfen. Erst nach Bestätigung wird der Zählerstand gespeichert.

Unter **Daten sichern** können Einstellungen, manuelle Historie und automatische
Ablesungen als JSON heruntergeladen werden. **Sicherung wiederherstellen** prüft die
Datei. **Neue Verträge anlegen** holt alle oder einzelne Verträge samt Historie zurück,
auch in eine leere App. Vorhandene Verträge bleiben erhalten; neue Verträge erhalten neue
Home-Assistant-Sensor-IDs. **Vorhandenen Vertrag ersetzen** überschreibt nur den ausgewählten
Zielvertrag derselben Energieart und bewahrt seine Sensor-IDs. Vor dem Ersetzen selbst exportieren.
Zusätzlich speichert die App höchstens 24 unveränderte/aktualisierte Datenstände in
`/data/radar.sqlite3`; diese lokale Datenbank wird mit dem App-Backup gesichert. Sie ersetzt
nicht die Integration als maßgeblichen Speicher und wird nicht als aktuelle Prognose
angezeigt, wenn Home Assistant unerreichbar ist. HA-Backups müssen App **und** Integration
enthalten. Die Snapshot-Datenbank ist eine zusätzliche Rückfallkopie; normale
Wiederherstellung erfolgt über die heruntergeladene JSON-Datei.

Boni sind grundsätzlich ausgeschlossen. Zahlungen werden erst nach tatsächlicher
Bezahlung erfasst; Vormerkungsfelder sind nicht Teil der App. Eine Bankanbindung
ist bisher nicht enthalten. Preise nach Ablauf einer
Preisgarantie bleiben unbekannt, bis eine datierte Preisänderung eingetragen wird.

Die App-Formulare verwenden Cent/kWh, intern und in historischen JSON-Daten gelten
Euro/kWh. Der monatliche Zahlungstag ist unabhängig vom Beginn der jährlichen
Abrechnungsperiode. Die App nennt die konkreten verbleibenden Zahlungstermine.
Heute bestätigte Zahlungen zählen bereits.
Ohne bestätigte Zahlungsdaten wird der Zahlungsplan als bezahlt angenommen.
Sobald eine tatsächliche Zahlung erfasst wird, alle bisherigen Zahlungen eintragen.

Gas kann als m³ oder kWh erfasst werden. Bei m³ den Faktor Brennwert × Zustandszahl
aus der Rechnung verwenden. Ein vorläufiger Faktor macht die Kosten unsicher.
Die Prognose lernt aus persönlicher Saisonverteilung und aktuellen Messdaten;
fehlende Tage/Monate gelten nicht als Nullverbrauch. Wetterdaten werden nicht verwendet.

AMD64 wurde auf der echten Instanz geprüft. Das angebotene Release ist auf AMD64
begrenzt. AArch64 benötigt noch eigene Hardwaretests. App-Status: experimentell.

Ältere Sicherungen bleiben kompatibel. Bereits vorhandene Vormerkungen bleiben als
feste geplante Beträge in der Berechnung erhalten, werden aber nicht als bezahlt
markiert. Die bisherige Sensoranbindung bleibt unverändert.

## Entitäten weiterverwenden

Im Reiter **HA-Entitäten** eines Vertrags findest du die erzeugten Sensoren mit aktuellen
Werten, tatsächlichen Entity-IDs und Kopierknöpfen. Ein Klick auf den Wert öffnet die
Entität in Home Assistant in einem neuen Fenster. Nutze die IDs für Automationen und
Diagrammkarten. Fehlende und deaktivierte Werte sind als solche gekennzeichnet.
Bei eingeschränktem Zwischenablagezugriff lässt sich die markierte ID manuell kopieren.
