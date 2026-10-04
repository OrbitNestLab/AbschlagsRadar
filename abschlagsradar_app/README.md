# AbschlagsRadar

**Passt dein Abschlag zu deinem Verbrauch?** Strom und Gas übersichtlich in einer
lokalen Home-Assistant-App: Jahresverbrauch, Kosten, erwartete Nachzahlung/Guthaben,
empfohlene Abschläge und persönlicher Vorjahresvergleich.

- Getrennte Strom- und Gasansichten; keine Dashboard-Konfiguration erforderlich.
- Datumsgenaue Zählerstände, Tarife, Abschlagsänderungen und tatsächliche Zahlungen.
- Ruhiger Wechsel zwischen Ansichten; keine manuelle Zahlungsvormerkung.
- Lokaler Fotoscan als Beta-Funktion mit Prüfung vor dem Speichern und optionalem Bildausschnitt.
- Jahresdurchschnitt der Zahlungen und Abschlagsempfehlung für nächstes Jahr.
- Native HA-Sensoren für Diagramme und Automationen.
- JSON-Sicherung und Wiederherstellung inklusive automatischer Messwerte.
- Alle Berechnungen ohne Boni; keine Cloud-Übertragung deiner Fotos oder Verträge.

Installieren, starten und **In Seitenleiste anzeigen** aktivieren. Der erste Start
installiert die interne HA-Anbindung. Danach Home Assistant einmal manuell neu starten
und Strom und Gas in der App einrichten. Die App führt weder nach der Installation noch
nach einem Update selbst einen Home-Assistant-Neustart aus. Ändert ein Update die interne
Anbindung, ist erneut ein manueller Neustart nötig. Zum Herunterladen des Images wird
Internet benötigt; die spätere Nutzung läuft lokal.

Zielsystem **Home Assistant OS / AMD64**. App-Funktionen und HA-Anbindung sind mit HA 2026.9.4 in einer getrennten Container-Testumgebung geprüft. Experimentelles Release; vollständige App-Store-Installation, Supervisor-Update und HA-OS-Backup-Wiederherstellung noch nicht separat nachgewiesen.
Andere Architekturen werden erst nach eigener Prüfung angeboten. Die Prognose ist
eine Schätzung; aktuelle Ablesungen und der richtige Gas-Umrechnungsfaktor sind
entscheidend. Zahlungsaufträge beim Anbieter bleiben in deiner Hand.

Siehe **Dokumentation** für Einrichtung, Berechnungsannahmen und Sicherungen.


Die App übernimmt die Sprache des angemeldeten Home-Assistant-Nutzers. Deutsch und Englisch werden unterstützt; andere Sprachen verwenden englische App-Texte. Ohne zugänglichen HA-Sprachkontext gilt die Browsersprache. Vertragsnamen, Entity-IDs und gespeicherte Zahlen werden nicht übersetzt.
