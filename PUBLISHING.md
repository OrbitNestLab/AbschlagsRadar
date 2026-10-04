# Veröffentlichung und Wartung

Repository: https://github.com/OrbitNestLab/AbschlagsRadar
Öffentliche Projektidentität: AbschlagsRadar. MIT-Lizenz.

Die Home-Assistant-App liegt in `abschlagsradar_app/`. Die Integration unter
`custom_components/abschlagsradar/` ist die Entwicklungsquelle der gebündelten
Sensoranbindung; Nutzer installieren ausschließlich die App.

## Release-Ablauf

1. Version in App, Bridge, Projekt-/Browserpaket und Änderungsprotokoll gemeinsam aktualisieren.
2. `python tools/sync_sources.py --check`, `python tools/validate_release.py --public`,
   Ruff, Python-, Frontend- und Browserprüfungen ausführen.
3. Workflow **Publish AMD64 App image** manuell starten. Er verlangt zuerst die
   vollständige Validierung einschließlich Image-Build und Abhängigkeitsprüfung.
   Der Upload nutzt ausschließlich den kurzlebigen GitHub-Actions-Token; keine privaten Zugangsdaten.
4. Image `ghcr.io/orbitnestlab/abschlagsradar:VERSION` öffentlich lesbar machen und
   anonymes Herunterladen prüfen. Die App-Metadaten verwenden dieselbe Registry.
5. Versioniertes experimentelles GitHub-Release mit Testgrenzen und Änderungen erstellen.
   Bereits veröffentlichte Versions-Tags nicht still mit anderem Inhalt überschreiben.

Die erste Veröffentlichung unterstützt AMD64. App-Funktionen, Entitäten und
Sicherungen wurden isoliert mit synthetischen Daten geprüft. Ein Container-Test
beweist keinen App-Store-Erstinstallationsweg, Supervisor-Update oder vollständige
HA-OS-Sicherungswiederherstellung. Reale Zählerfotos und weitere Hardware separat prüfen.

Für spätere Releases diese Installationsprüfungen unter HA OS ergänzen. ARM erst
anbieten, wenn Image und Betrieb geprüft wurden.

Keine persönlichen Daten, lokale Pfade, Testzugänge oder private Entwicklungshistorie
veröffentlichen. Sicherheitsmeldungen erfolgen vertraulich über GitHub Advisories.

Ab 0.4.6 erfolgt kein automatischer Home-Assistant-Neustart. In Installations- und Updatehinweisen den nötigen manuellen Neustart nennen. Den lokalen Fotoscan in Beschreibungen immer als Beta mit Kontrolle vor dem Speichern ausweisen.
