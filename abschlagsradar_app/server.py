"""Independent local web application behind authenticated Supervisor Ingress.

No HA token is sent to a browser. Ingress identity is checked against HA users.
Only specific budgeting operations are exposed; this is never an arbitrary API proxy.
"""

import asyncio
import json
import os
import secrets
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, ClientWSTimeout, web
from store import SnapshotStore

VERSION = "0.4.4"
WEB = Path(__file__).parent / "web"
TRUSTED_INGRESS = {"172.30.32.2"}
ERROR_MESSAGES = {
    "invalid_date": "Bitte ein gültiges Datum eingeben.",
    "invalid_number": "Bitte eine gültige, nicht negative Zahl eingeben.",
    "invalid_settings": "Bitte die Vertragsdaten prüfen.",
    "invalid_history": "Bitte die historischen Daten und ihre Felder prüfen.",
    "duplicate_date": "Für dieses Datum gibt es bereits einen Eintrag.",
    "decreasing_meter": "Der Zählerstand darf nicht kleiner als ein älterer Stand sein.",
    "overlapping_intervals": "Verbrauchsintervalle dürfen sich nicht überschneiden.",
    "future_reading": "Eine Ablesung darf nicht in der Zukunft liegen.",
    "future_payment": "Zukünftige Zahlungen bitte als vorgemerkt erfassen.",
    "history_too_long": "Der historische Zeitraum darf höchstens 100 Jahre umfassen.",
    "no_digits": "Keine eindeutigen Ziffern erkannt. Bitte die Anzeige scharf und nah fotografieren.",
    "invalid_image": "Bitte ein gültiges JPEG- oder PNG-Foto auswählen.",
    "invalid_crop": "Bitte gültige Bildgrenzen zwischen 0 und 100 Prozent eingeben.",
    "source_unit_mismatch": "Die Einheit des Zählersensors muss zur Zählereinheit des Vertrags passen.",
    "image_too_large": "Das Foto darf höchstens 12 MB und 20 Megapixel groß sein.",
}


def is_admin(user):
    return bool(user.get("is_admin") or user.get("is_owner") or "system-admin" in user.get("group_ids", []))


class HAClient:
    def __init__(self, session, token, base="http://supervisor/core"):
        self.session, self.token, self.base = session, token, base

    async def call(self, message):
        url = self.base.replace("http:", "ws:").replace("https:", "wss:") + "/websocket"
        async with self.session.ws_connect(
            url, max_msg_size=4 * 1024 * 1024, timeout=ClientWSTimeout(ws_receive=30, ws_close=10)
        ) as ws:
            hello = await ws.receive_json(timeout=10)
            if hello.get("type") != "auth_required":
                raise ConnectionError("HA authentication unavailable")
            await ws.send_json({"type": "auth", "access_token": self.token})
            auth = await ws.receive_json(timeout=10)
            if auth.get("type") != "auth_ok":
                raise ConnectionError("HA authentication failed")
            await ws.send_json({"id": 1, **message})
            while True:
                response = await ws.receive_json(timeout=30)
                if response.get("id") == 1:
                    if not response.get("success"):
                        raise ValueError(
                            response.get("error", {}).get("message", "Home Assistant hat die Eingabe abgelehnt.")
                        )
                    return response.get("result")

    async def rest(self, path, data=None, method=None):
        async with self.session.request(
            method or ("POST" if data is not None else "GET"),
            self.base + "/api/" + path,
            headers={"Authorization": "Bearer " + self.token},
            json=data,
        ) as response:
            if response.status >= 400:
                raise ConnectionError("Home Assistant API unavailable")
            return await response.json()


HA_KEY = web.AppKey("ha", object)
STORE_KEY = web.AppKey("store", object)
TRUSTED_KEY = web.AppKey("trusted_ingress", object)
PHOTOS_KEY = web.AppKey("photos", object)
USERS_KEY = web.AppKey("users", object)
OCR_KEY = web.AppKey("ocr_lock", object)
RESTORE_KEY = web.AppKey("restore_lock", object)


@web.middleware
async def ingress_guard(request, handler):
    # No published LAN port. Still reject requests from other containers/peers.
    if request.remote not in request.app[TRUSTED_KEY]:
        raise web.HTTPForbidden(text="Use Home Assistant Ingress.")
    if request.method == "POST" and request.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
        raise web.HTTPForbidden(text="Cross-site request rejected.")
    try:
        response = await handler(request)
    except ValueError as err:
        response = web.json_response({"error": ERROR_MESSAGES.get(str(err), str(err))}, status=400)
    except web.HTTPException:
        raise
    except Exception:  # noqa: BLE001 - never expose token/photo/internal traces in HTTP errors.
        response = web.json_response(
            {"error": "Home Assistant ist vorübergehend nicht erreichbar. Bitte erneut versuchen."}, status=503
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
    )
    return response


async def identity(request, admin=False):
    uid = request.headers.get("X-Remote-User-Id")
    if not uid:
        raise web.HTTPForbidden(text="Home-Assistant-Benutzer fehlt. App bitte über die Seitenleiste öffnen.")
    now = time.monotonic()
    cache = request.app[USERS_KEY]
    if cache["until"] < now:
        cache["rows"] = await request.app[HA_KEY].call({"type": "config/auth/list"})
        cache["until"] = now + 30
    user = next((u for u in cache["rows"] if u["id"] == uid and u.get("is_active", True)), None)
    if not user or (admin and not is_admin(user)):
        raise web.HTTPForbidden(text="Nur Home-Assistant-Administratoren können Vertragsdaten ändern.")
    return user


async def json_object(request):
    """Validate JSON at the boundary before passing it into model/HA code."""
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType(text="Bitte JSON-Daten senden.")
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        raise ValueError("Die Eingabe enthält ungültiges JSON.") from err
    if not isinstance(data, dict):
        raise ValueError("Bitte ein JSON-Objekt senden.")  # noqa: TRY004 - public validation errors use ValueError
    return data


async def session_info(request):
    user = await identity(request)
    return web.json_response({"version": VERSION, "is_admin": is_admin(user)})


async def contract_rows(ha):
    """An empty installation has not registered the bridge commands yet."""
    try:
        return await ha.call({"type": "abschlagsradar/app"})
    except ValueError:
        entries = await ha.rest("config/config_entries/entry")
        if any(entry["domain"] == "abschlagsradar" for entry in entries):
            raise
        return []


async def contracts(request):
    await identity(request)
    rows = await contract_rows(request.app[HA_KEY])
    # A failure never masquerades as a current forecast from the snapshot.
    await asyncio.to_thread(request.app[STORE_KEY].save, rows)
    return web.json_response(rows)


async def message(request):
    uid = (await identity(request, admin=True))["id"]
    data = await json_object(request)
    if data.get("type") == "abschlagsradar/scan":
        if set(data) != {"type", "file_id"} or not isinstance(data["file_id"], str):
            raise ValueError("Ungültiger Foto-Vorschlag.")
        candidate = request.app[PHOTOS_KEY].get(data["file_id"])
        if not candidate or candidate["uid"] != uid or candidate["expires"] < time.monotonic():
            raise ValueError("Foto-Vorschlag abgelaufen. Bitte erneut hochladen.")
        request.app[PHOTOS_KEY].pop(data["file_id"])
        return web.json_response(candidate["candidates"])
    if data.get("type") != "abschlagsradar/edit" or set(data) != {"type", "entry_id", "action", "payload"}:
        raise ValueError("Unbekannte Aktion.")
    result = await request.app[HA_KEY].call(data)
    return web.json_response(result)


async def photo(request):
    uid = (await identity(request, admin=True))["id"]
    if request.content_type != "multipart/form-data":
        raise web.HTTPUnsupportedMediaType(text="Bitte ein JPEG- oder PNG-Foto hochladen.")
    lock = request.app[OCR_KEY]
    # Reject concurrent uploads before retaining another large image in memory.
    if lock.locked():
        raise web.HTTPTooManyRequests(text="Ein Foto wird gerade verarbeitet. Bitte gleich erneut versuchen.")
    async with lock:
        return await process_photo(request, uid)


async def process_photo(request, uid):
    from radarcore.model import number

    try:
        crop = json.loads(request.headers.get("X-Radar-Crop", "[0,0,100,100]"))
        if not isinstance(crop, list) or len(crop) != 4:
            raise ValueError("invalid_crop")
        crop = tuple(number(value) for value in crop)
        left, top, right, bottom = crop
        if not 0 <= left < right <= 100 or not 0 <= top < bottom <= 100:
            raise ValueError("invalid_crop")
    except (ValueError, TypeError) as err:
        raise ValueError("invalid_crop") from err
    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "file":
        raise ValueError("Bitte ein Foto auswählen.")
    image = bytearray()
    while chunk := await field.read_chunk():
        image.extend(chunk)
        if len(image) > 12 * 1024 * 1024:
            raise web.HTTPRequestEntityTooLarge(max_size=12 * 1024 * 1024, actual_size=len(image))
    from radarcore.ocr_core import scan_bytes

    try:
        candidates = await asyncio.to_thread(scan_bytes, bytes(image), crop)
    finally:
        image.clear()
    photos = request.app[PHOTOS_KEY]
    now = time.monotonic()
    for key in list(photos):
        if photos[key]["expires"] < now:
            photos.pop(key)
    if len(photos) >= 32:
        photos.pop(next(iter(photos)))
    file_id = secrets.token_urlsafe(24)
    photos[file_id] = {"uid": uid, "expires": now + 120, "candidates": candidates}
    return web.json_response({"file_id": file_id})


async def create_contract(request):
    await identity(request, admin=True)
    from radarcore.model import validate_settings
    from settings import create_settings

    data = await json_object(request)
    settings = validate_settings(create_settings(data))
    entry_id = await create_entry(request.app[HA_KEY], settings)
    return web.json_response({"created": True, "entry_id": entry_id})


async def create_entry(ha, settings):
    """Use HA's normal config flow so validation and stable sensor identities apply."""
    flow = await ha.rest("config/config_entries/flow", {"handler": "abschlagsradar"})
    path = "config/config_entries/flow/" + flow["flow_id"]
    try:
        if flow["type"] == "menu":
            flow = await ha.rest(path, {"next_step_id": settings["energy_type"]})
        fields = {field["name"] for field in flow.get("data_schema", [])}
        # An empty optional entity selector must be omitted, not sent as an entity ID.
        result = await ha.rest(
            path, {key: value for key, value in settings.items() if key in fields and (key != "source_sensor" or value)}
        )
        if result.get("type") != "create_entry":
            raise ValueError("Vertrag konnte nicht angelegt werden. Bitte Eingaben prüfen.")
    except Exception:
        try:
            await ha.rest(path, method="DELETE")
        except Exception:  # noqa: BLE001, S110 - the original setup error remains authoritative
            pass
        raise
    entry_id = result.get("result", {}).get("entry_id")
    if not entry_id:
        raise ConnectionError("Home Assistant did not return a contract identity")
    return entry_id


async def export_data(request):
    await identity(request, admin=True)
    rows = await contract_rows(request.app[HA_KEY])
    return web.json_response(
        {"format": "abschlagsradar-backup", "version": 1, "contracts": rows},
        headers={"Content-Disposition": 'attachment; filename="abschlagsradar-vertraege.json"'},
    )


async def restore_preview(request):
    await identity(request, admin=True)
    from backup import read_backup

    return web.json_response(read_backup(await json_object(request)))


async def wait_for_contract(ha, entry_id, restored=None):
    """Wait for setup/reload before restoring or returning a successful response."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            rows = await contract_rows(ha)
        except ValueError:
            # First config-entry setup registers the bridge asynchronously.
            rows = []
        row = next((row for row in rows if row["id"] == entry_id), None)
        if row and (restored is None or row["history"] == restored["history"]):
            return
        await asyncio.sleep(0.25)
    raise ConnectionError("Home Assistant contract setup timed out")


async def restore_contract(request):
    await identity(request, admin=True)
    from backup import read_backup

    data = await json_object(request)
    creating = data.get("mode") == "create"
    expected = {"mode", "backup", "contract_indices"} if creating else {"entry_id", "backup", "contract_index"}
    if set(data) != expected:
        raise ValueError("Ungültige Wiederherstellungsanfrage.")
    saved = read_backup(data["backup"])
    indices = data["contract_indices"] if creating else [data["contract_index"]]
    if (
        not isinstance(indices, list)
        or not indices
        or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(saved) for i in indices)
        or len(set(indices)) != len(indices)
    ):
        raise ValueError("Bitte gültige Verträge aus der Sicherung auswählen.")
    lock = request.app[RESTORE_KEY]
    if lock.locked():
        raise web.HTTPTooManyRequests(text="Eine Sicherung wird gerade wiederhergestellt. Bitte warten.")
    async with lock:
        ha = request.app[HA_KEY]
        current = await contract_rows(ha)
        if not creating:
            target = next((row for row in current if row["id"] == data["entry_id"]), None)
            if target is None or target["settings"]["energy_type"] != saved[indices[0]]["settings"]["energy_type"]:
                raise ValueError("Bitte einen vorhandenen Vertrag derselben Energieart auswählen.")
        await asyncio.to_thread(request.app[STORE_KEY].save, current)
        created = []
        try:
            for index in indices:
                restored = saved[index]
                entry_id = await create_entry(ha, restored["settings"]) if creating else data["entry_id"]
                if creating:
                    created.append(entry_id)
                await wait_for_contract(ha, entry_id)
                await ha.call({"type": "abschlagsradar/restore", "entry_id": entry_id, "payload": restored})
                await wait_for_contract(ha, entry_id, restored)
        except Exception:
            # Roll back only entries created by this request. Existing contracts are never deleted.
            failed_cleanup = False
            for entry_id in reversed(created):
                try:
                    await ha.rest("config/config_entries/entry/" + entry_id, method="DELETE")
                except Exception:  # noqa: BLE001 - report partial cleanup explicitly
                    failed_cleanup = True
            if failed_cleanup:
                raise ValueError(
                    "Die Wiederherstellung wurde unterbrochen. Mindestens ein neuer Vertrag konnte nicht entfernt "
                    "werden. Bitte die Übersicht prüfen, bevor du erneut wiederherstellst."
                ) from None
            raise
        return web.json_response({"restored": True, "created": created, "count": len(indices)})


async def index(request):
    return web.FileResponse(WEB / "index.html")


async def health(request):
    return web.json_response({"status": "ready", "version": VERSION})


def create_app(ha=None, store=None, trusted=None):
    app = web.Application(middlewares=[ingress_guard], client_max_size=13 * 1024 * 1024)
    app[HA_KEY] = ha
    app[STORE_KEY] = store
    app[TRUSTED_KEY] = TRUSTED_INGRESS if trusted is None else trusted
    app[PHOTOS_KEY] = {}
    app[USERS_KEY] = {"rows": [], "until": 0}
    app[OCR_KEY] = asyncio.Lock()
    app[RESTORE_KEY] = asyncio.Lock()
    app.add_routes(
        [
            web.get("/", index),
            web.get("/health", health),
            web.get("/api/session", session_info),
            web.get("/api/contracts", contracts),
            web.post("/api/message", message),
            web.post("/api/photo", photo),
            web.post("/api/contracts", create_contract),
            web.get("/api/export", export_data),
            web.post("/api/restore/preview", restore_preview),
            web.post("/api/restore", restore_contract),
        ]
    )
    app.router.add_static("/assets/", WEB, show_index=False)
    return app


async def main():
    data = Path("/data")
    if os.getuid() == 0:
        data.mkdir(exist_ok=True)
        from bridge_installer import ensure_bridge

        ensure_bridge(Path(__file__).parent / "bridge", "/homeassistant", data)
        marker = data / "bridge-restart-needed"
        if marker.exists():
            os.chown(marker, 65534, 65534, follow_symlinks=False)
        os.chown(data, 65534, 65534)
        data.chmod(0o700)
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)
    store = SnapshotStore(data / "radar.sqlite3")
    async with ClientSession(timeout=ClientTimeout(total=50)) as session:
        ha = HAClient(session, os.environ["SUPERVISOR_TOKEN"])
        marker = data / "bridge-restart-needed"
        if marker.exists():
            try:
                await ha.rest("services/homeassistant/restart", {})
                marker.unlink()
                print("Bundled HA connection installed; Home Assistant restart requested.", flush=True)
            except Exception:  # noqa: BLE001 - keep restart marker for the next startup
                print("HA connection prepared. A Home Assistant restart is still required.", flush=True)
        app = create_app(ha, store)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", 8099).start()
        print("AbschlagsRadar local app ready.", flush=True)
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
