#!/bin/bash
# Local guided installer for the tested HA OS SSH / Docker layout.
set -euo pipefail
cd "$(dirname "$0")"
printf '\nAbschlagsRadar installieren\n\n'
printf 'Home-Assistant-IP: '
read -r radar_host
printf 'SSH-Benutzer [hassio]: '
read -r radar_user
radar_user="${radar_user:-hassio}"
if [[ ! "$radar_host" =~ ^[a-zA-Z0-9.-]+$ || ! "$radar_user" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  printf 'Ungültige Adresse oder Benutzername.\n'; exit 1
fi
printf '\nDie Installation sichert die bisherige Integration und richtet die App ein. Home Assistant wird nicht automatisch neu gestartet.\nFortfahren? [j/N]: '
read -r radar_answer
[[ "$radar_answer" == j || "$radar_answer" == J ]] || exit 0
tar -czf - abschlagsradar_app | ssh "${radar_user}@${radar_host}" '
set -eu
stage=$(mktemp -d)
trap '\''rm -rf "$stage"'\'' EXIT
tar -xzf - -C "$stage"
test -d /homeassistant
test -d /addons
radar_stage=$(sudo -n mktemp -d /addons/.abschlagsradar-stage-XXXXXX)
sudo -n chmod 755 "$radar_stage"
sudo -n cp -a "$stage/abschlagsradar_app/." "$radar_stage/"
if test -e /addons/abschlagsradar; then
  test ! -L /addons/abschlagsradar
  test -f /addons/abschlagsradar/config.yaml
  grep -q "^slug: abschlagsradar$" /addons/abschlagsradar/config.yaml
  radar_previous=$(sudo -n mktemp -d /addons/.abschlagsradar-previous-XXXXXX)
  sudo -n rmdir "$radar_previous"
  sudo -n mv /addons/abschlagsradar "$radar_previous"
  if ! sudo -n mv "$radar_stage" /addons/abschlagsradar; then
    sudo -n mv "$radar_previous" /addons/abschlagsradar
    exit 1
  fi
else
  sudo -n mv "$radar_stage" /addons/abschlagsradar
fi
sudo -n docker exec -i homeassistant python - <<"PYAPP"
import os,json,time,urllib.request
headers={"Authorization":"Bearer "+os.environ["SUPERVISOR_TOKEN"],"Content-Type":"application/json"}
def api(path,data=None):
 request=urllib.request.Request("http://supervisor/"+path,headers=headers,data=json.dumps(data).encode() if data is not None else None)
 with urllib.request.urlopen(request,timeout=600) as response:return json.load(response)
api("store/reload",{})
apps=api("addons")["data"]["addons"]
installed=any(x["slug"]=="local_abschlagsradar" for x in apps)
if not installed:
 api("addons/local_abschlagsradar/install",{})
else:
 info=api("addons/local_abschlagsradar/info")["data"]
 if info.get("version_latest")!=info["version"]:
  api("addons/local_abschlagsradar/update",{})
api("addons/local_abschlagsradar/options",{"ingress_panel":True,"watchdog":True})
if api("addons/local_abschlagsradar/info")["data"]["state"]!="started":
 api("addons/local_abschlagsradar/start",{})
PYAPP
'
open "http://${radar_host}:8123/local_abschlagsradar"
printf '\nInstalliert. Bitte Home Assistant jetzt einmal selbst neu starten und danach AbschlagsRadar über die Seitenleiste öffnen.\nStrom und Gas öffnen jeweils ein eigenes Einrichtungsformular.\nDer Fotoscan ist eine Beta-Funktion und läuft direkt in der App; erkannte Werte immer prüfen.\n'
read -r -p 'Enter zum Schließen …' radar_done
