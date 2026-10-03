# 0.4.5

- App übernimmt die Home-Assistant-Sprache; Deutsch und Englisch, Englisch als Rückfall für weitere Sprachen.
- Zahlen und Datum folgen der gewählten Sprache. Vertragsnamen und Eingaben bleiben unverändert.
- Öffentlicher AMD64-Image-Build, Installationslink, Icon und vertrauliche Sicherheitsmeldungen.

# 0.4.4

- JSON-Sicherungen können alle oder einzelne Verträge in einer leeren App neu anlegen.
- Vorhandene Verträge ersetzen bleibt eine getrennte Option mit erhaltenen Sensor-IDs.
- Import wartet auf HA-Setup/Neuladen; fehlgeschlagene Neuanlagen werden bereinigt.
- Neuer Reiter HA-Entitäten mit Werten, registrierten IDs, Kopieren und direkter Entitätsansicht.
- Anleitung und Browser-/Serverprüfungen für die neuen Abläufe erweitert; bestehende Optik erhalten.

# 0.4.3

- Vormerkungsanzeigen, Vormerkungsformular und Bestätigungsbuttons aus der App entfernt; manuelle Erfassung tatsächlicher Zahlungen bleibt.
- Das Stylesheet bleibt beim Wechsel zwischen Ansichten geladen; Inhalte erscheinen erst nach dem ersten Laden der Gestaltung.
- Anleitung und Veröffentlichungsunterlagen angepasst; ältere Sicherungen und native Sensoren bleiben kompatibel.

# 0.4.2

- Interne Installation schützt auch App-Datenpfade und Neustartmarkierungen vor Umleitungen.
- Optionale Zählersensoren und Vertragseinstellungen werden einheitlich geprüft.
- Ein Sensorwechsel erhält die Vertragsidentität; automatische Ablesungen bleiben begrenzt.
- Unberechenbare Prozentvergleiche bleiben offen statt unendliche Werte zu liefern.

# 0.4.1

- Leere optionale Zählersensoren werden beim Anlegen korrekt weggelassen.
- Extreme Zahlen und Wahrheitswerte werden als numerische Eingaben abgelehnt.

# 0.4.0

- Neue Verträge werden direkt über die getrennten App-Formulare zuverlässig angelegt.
- Zahlungen am heutigen Tag zählen bereits; vorgemerkte Bankbuchungen ersetzen den jeweiligen Monatsabschlag ohne Doppelzählung.
- Persönliche Saisonverteilung berücksichtigt unvollständige Vorjahre; ausreichend aktuelle Messdaten bestimmen das Verbrauchsniveau.
- Anzeige der verbleibenden Zahlungstermine, Messdatenstand und automatischen Ablesungen.
- Direkte kWh-Intervalle, vorgemerkte Zahlungen, Zählersensor und Gaszählereinheit über App-Formulare.
- Sicherungen enthalten automatische Messwerte und lassen sich in einen gewählten Vertrag zurückspielen.
- Lokaler Fotoscan mit optionalem Bildausschnitt, begrenzter paralleler Verarbeitung und verständlichen Fehlern.
- Vollständige, gesicherte Aktualisierung der internen Sensoranbindung; alter OCR-Hilfsdienst entfällt.
- Rechenarbeit außerhalb des HA-Ereignisloops, schnellere Tarifauswahl, begrenzte Datenspannen und lesbarer Quellcode.
- Installationsstarter, Tests und Veröffentlichungsvorbereitung ergänzt; Erstfreigabe auf geprüfte AMD64-Systeme begrenzt.

# 0.3.2

- Startansicht kennzeichnet Nachzahlungen rot mit Minus und Guthaben grün mit Plus.
- Abschlagsansicht zeigt den aktuell empfohlenen Monatsabschlag für den Rest des Jahres.

# 0.3.1

- Ein-Paket-Installation: Die App installiert ihre interne HA-Sensoranbindung selbst.
- Gültige, auf `/homeassistant` begrenzte Konfigurationsfreigabe für die Sensoranbindung.
- Alte Dashboard- und Custom-Panel-Wege entfernt; die Seitenleiste öffnet nur die App.
- Build-Metadaten und Tests für eine spätere App-Repository-Veröffentlichung ergänzt.

# 0.3.0

- Eigenständiger Home-Assistant-App-Dienst mit authentifiziertem Ingress.
- Eigene REST-Schnittstelle und Oberfläche, getrennte Strom-/Gas-Einrichtung.
- Bestehende Verträge und native Sensoren über die Integration angebunden.
- Lokaler Fotoscan im App-Container mit Bestätigung vor Übernahme.
- Datenexport und begrenzte SQLite-Sicherungen, keine Cloud-Übertragung.
- Administratorprüfung vor Änderungen, keine LAN-Portfreigabe.
