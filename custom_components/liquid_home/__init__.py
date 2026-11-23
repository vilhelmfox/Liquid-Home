"""Local, temporary QR pairing relay for Liquid Home.

No Home Assistant authentication tokens or entity states are stored here.
Each pairing is isolated by two independently random secrets; an iPad must
select the target tile before the phone can submit changes.
"""
from __future__ import annotations

import io
from pathlib import Path
import secrets
import time
import re
import hmac
from homeassistant.helpers.storage import Store
from typing import Any

import qrcode
import qrcode.image.svg
from aiohttp import web
from homeassistant.components.http import HomeAssistantView, StaticPathConfig

DOMAIN = "liquid_home"
TTL = 15 * 60
MAX_SESSIONS = 20
MAX_UPDATES = 30
ALLOWED_DOMAINS = {"light", "cover", "switch", "fan", "input_boolean", "scene", "script", "media_player"}
ALLOWED_SERVICES = {
    "light": {"toggle", "turn_on", "turn_off"},
    "cover": {"open_cover", "close_cover", "stop_cover", "set_cover_position"},
    "switch": {"toggle", "turn_on", "turn_off"},
    "fan": {"toggle", "turn_on", "turn_off"},
    "input_boolean": {"toggle", "turn_on", "turn_off"},
    "scene": {"turn_on"},
    "script": {"turn_on"},
    "media_player": {"media_play_pause", "media_play", "media_pause", "media_next_track", "media_previous_track", "play_media", "volume_set"},
}


def permitted_entities(widgets, rules):
    out=set()
    for w in widgets:
        for field in ("entity", "actionTarget"):
            value=w.get(field, "")
            if isinstance(value, str) and re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", value):
                out.add(value)
    for rule in rules:
        value=rule.get("entity", "")
        if isinstance(value, str) and re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", value):
            out.add(value)
    return sorted(out)


def device_check(request, devices, did):
    item=devices.get(did)
    supplied=request.headers.get("X-Liquid-Key", "")
    if not item or not supplied or not secrets.compare_digest(supplied, item["key"]):
        return None
    return item


def as_json(request, data, status=200):
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store"})


def active(store, sid):
    item = store.get(sid)
    if not item or item["expiry"] < time.monotonic():
        store.pop(sid, None)
        return None
    return item


class PairNew(HomeAssistantView):
    url = "/api/liquid_home/new"
    name = "api:liquid_home:new"
    requires_auth = False

    def __init__(self, store):
        self.store = store

    async def post(self, request):
        for key in list(self.store):
            active(self.store, key)
        if len(self.store) >= MAX_SESSIONS:
            return as_json(request, {"error": "For mange aktive forbindelser. Prøv igen senere."}, 429)
        try:
            data = await request.json()
        except Exception:
            data = {}
        settings = data.get("settings", {}) if isinstance(data, dict) else {}
        widgets = data.get("widgets", []) if isinstance(data, dict) else []
        if not isinstance(settings, dict):
            settings = {}
        rules = settings.get("rules", [])
        if not isinstance(rules, list):
            rules = []
        rules = [r for r in rules[:20] if isinstance(r, dict) and all(isinstance(r.get(f, ""), str) and len(r.get(f, "")) <= 160 for f in ("entity", "state", "title", "body", "emoji"))]
        idle = settings.get("idle", 2)
        idle = idle if type(idle) is int and 0 <= idle <= 120 else 2
        tap = settings.get("tapAction", "dashboard")
        tap = tap if tap in ("dashboard", "qr", "none") else "dashboard"
        if not isinstance(widgets, list) or len(widgets) != 6:
            widgets = [{} for _ in range(6)]
        widgets = [w if isinstance(w, dict) and len(str(w)) <= 2000 else {} for w in widgets]
        sid = secrets.token_urlsafe(15)
        ipad_key = secrets.token_urlsafe(30)
        phone_key = secrets.token_urlsafe(30)
        self.store[sid] = {"ipad": ipad_key, "phone": phone_key, "expiry": time.monotonic()+TTL, "authorized": False,
                           "selected": -1, "revision": 0, "updates": [], "count": 0, "settings": {"idle": idle, "rules": rules, "tapAction": tap, "backgroundMode": settings.get("backgroundMode", "default") if settings.get("backgroundMode") in ("default", "nature", "custom") else "default", "setupComplete": settings.get("setupComplete") is True}, "widgets": widgets}
        return as_json(request, {"id": sid, "ipad_key": ipad_key,
                                 "qr": "/api/liquid_home/qr/"+sid, "expires_seconds": TTL})


class PairQR(HomeAssistantView):
    url = "/api/liquid_home/qr/{sid}"
    name = "api:liquid_home:qr"
    requires_auth = False

    def __init__(self, store):
        self.store = store

    async def get(self, request, sid):
        item = active(self.store, sid)
        if not item:
            return web.Response(status=404, text="QR-koden er udløbet")
        # Draw QR locally. No external QR provider ever receives the URL.
        url = "%s://%s/liquid_home/phone.html?sid=%s&key=%s" % (
            request.scheme, request.host, sid, item["phone"])
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                           border=3, box_size=7)
        qr.add_data(url)
        qr.make(fit=True)
        output = io.BytesIO()
        qr.make_image(image_factory=qrcode.image.svg.SvgImage).save(output)
        return web.Response(body=output.getvalue(), content_type="image/svg+xml",
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


class PairState(HomeAssistantView):
    url = "/api/liquid_home/state/{sid}"
    name = "api:liquid_home:state"
    requires_auth = False

    def __init__(self, store):
        self.store = store

    async def get(self, request, sid):
        item = active(self.store, sid)
        if not item:
            return as_json(request, {"error": "Forbindelsen er udløbet"}, 404)
        key = request.query.get("key", "")
        if not (secrets.compare_digest(key, item["ipad"]) or secrets.compare_digest(key, item["phone"])):
            return as_json(request, {"error": "Ugyldig forbindelse"}, 403)
        is_ipad = secrets.compare_digest(key, item["ipad"])
        since = request.query.get("since", "0")
        try:
            since = max(0, int(since))
        except ValueError:
            since = 0
        return as_json(request, {"selected": item["selected"], "revision": item["revision"],
                                 "updates": [u for u in item["updates"] if u["rev"] > since] if is_ipad else [],
                                 "expires_seconds": max(0, int(item["expiry"]-time.monotonic())),
                                 "settings": item["settings"] if not is_ipad else None,
                                 "authorized": item.get("authorized", False),
                                 "widget": item["widgets"][item["selected"]] if not is_ipad and item["selected"] >= 0 else None})


class PairEntities(HomeAssistantView):
    url = "/api/liquid_home/entities/{sid}"
    name = "api:liquid_home:entities"
    requires_auth = False

    def __init__(self, store, hass):
        self.store, self.hass = store, hass

    async def get(self, request, sid):
        item = active(self.store, sid)
        if not item or not secrets.compare_digest(request.query.get("key", ""), item["phone"]):
            return as_json(request, {"error": "Forbindelse udløbet"}, 403)
        if not item.get("authorized"):
            return as_json(request, {"error": "Godkend først med din Liquid Home kode"}, 403)
        domains = {"light", "cover", "switch", "fan", "media_player", "sensor", "binary_sensor", "scene", "script", "climate", "input_boolean"}
        entities = [{"id": st.entity_id, "name": str(st.attributes.get("friendly_name") or st.entity_id)[:100], "domain": st.domain}
                    for st in self.hass.states.async_all() if st.domain in domains]
        entities.sort(key=lambda x: (x["domain"], x["name"].casefold()))
        return as_json(request, {"entities": entities[:1000]})


class PairSelect(HomeAssistantView):
    url = "/api/liquid_home/select/{sid}"
    name = "api:liquid_home:select"
    requires_auth = False

    def __init__(self, store):
        self.store = store

    async def post(self, request, sid):
        item = active(self.store, sid)
        if not item:
            return as_json(request, {"error": "Udløbet"}, 404)
        try:
            data = await request.json()
        except Exception:
            return as_json(request, {"error": "Ugyldig data"}, 400)
        if not secrets.compare_digest(str(data.get("key", "")), item["ipad"]):
            return as_json(request, {"error": "Ikke tilladt"}, 403)
        slot = data.get("slot")
        if type(slot) is not int or slot not in range(6):
            return as_json(request, {"error": "Vælg et felt fra 1 til 6"}, 400)
        item["selected"] = slot
        item["revision"] += 1
        return as_json(request, {"ok": True, "selected": slot})




class PairAuthorize(HomeAssistantView):
    url = "/api/liquid_home/authorize/{sid}"
    name = "api:liquid_home:authorize"
    requires_auth = False

    def __init__(self, sessions, devices, storage, pin):
        self.sessions, self.devices, self.storage, self.pin = sessions, devices, storage, pin
        self.failures = {}

    async def post(self, request, sid):
        session = active(self.sessions, sid)
        if not session:
            return as_json(request, {"error": "QR koden er udløbet"}, 404)
        try:
            data = await request.json()
        except Exception:
            return as_json(request, {"error": "Ugyldig data"}, 400)
        if not secrets.compare_digest(str(data.get("key", "")), session["phone"]):
            return as_json(request, {"error": "Forkert parring"}, 403)
        failures=self.failures.get(sid, 0)
        if failures >= 5:
            return as_json(request, {"error": "For mange forsøg. Vis en ny QR kode på iPad."}, 429)
        if not secrets.compare_digest(str(data.get("pin", "")), self.pin):
            self.failures[sid] = failures+1
            return as_json(request, {"error": "Forkert adgangskode"}, 403)
        # A random device credential with ONLY configured entity access.
        did = secrets.token_urlsafe(16)
        key = secrets.token_urlsafe(32)
        self.devices[did] = {"key": key, "entities": permitted_entities(session["widgets"], session["settings"]["rules"])}
        await self.storage.async_save(self.devices)
        session["authorized"] = True
        session["device_id"] = did
        session["revision"] += 1
        session["updates"].append({"rev": session["revision"], "type": "device_authorization", "id": did, "key": key})
        return as_json(request, {"ok": True, "connected": True})


class DeviceProxy(HomeAssistantView):
    url = "/api/liquid_home/device/{did}/{operation}"
    name = "api:liquid_home:device"
    requires_auth = False

    def __init__(self, hass, devices):
        self.hass,self.devices=hass,devices

    async def get(self, request, did, operation):
        device=device_check(request,self.devices,did)
        if not device: return as_json(request, {"error": "Ikke godkendt"}, 403)
        if operation == "check": return as_json(request,{"ok":True})
        if operation != "states": return as_json(request,{"error":"Ugyldig handling"},404)
        data=[]
        for entity in device.get("entities",[]):
            state=self.hass.states.get(entity)
            if state:
                attrs={}
                if entity.startswith("media_player."):
                    for k in ("media_title","media_artist","source","entity_picture","volume_level"):
                        attrs[k]=state.attributes.get(k, "")
                data.append({"entity_id":entity,"state":state.state,"attributes":attrs})
        return as_json(request,data)

    async def post(self, request, did, operation):
        device=device_check(request,self.devices,did)
        if not device: return as_json(request,{"error":"Ikke godkendt"},403)
        if operation != "service": return as_json(request,{"error":"Ugyldig handling"},404)
        try: data=await request.json()
        except Exception: return as_json(request,{"error":"Ugyldig data"},400)
        domain=data.get("domain","");service=data.get("service","");payload=data.get("data",{})
        if domain not in ALLOWED_SERVICES or service not in ALLOWED_SERVICES[domain]:
            return as_json(request,{"error":"Handlingen er ikke tilladt"},403)
        if not isinstance(payload,dict) or set(payload)-{"entity_id","brightness","rgb_color","position","media_content_id","media_content_type","volume_level"}:
            return as_json(request,{"error":"Ugyldige parametre"},400)
        entity=payload.get("entity_id","")
        if not isinstance(entity,str) or entity not in device.get("entities",[]) or not entity.startswith(domain+"."):
            return as_json(request,{"error":"Denne enhed er ikke godkendt"},403)
        if "brightness" in payload and not (type(payload["brightness"]) is int and 0<=payload["brightness"]<=255):
            return as_json(request,{"error":"Ugyldig lysstyrke"},400)
        if "volume_level" in payload and not (type(payload["volume_level"]) in (int,float) and 0<=payload["volume_level"]<=1):
            return as_json(request,{"error":"Ugyldig lydstyrke"},400)
        if "position" in payload and not (type(payload["position"]) is int and 0<=payload["position"]<=100):
            return as_json(request,{"error":"Ugyldig position"},400)
        if "rgb_color" in payload and (not isinstance(payload["rgb_color"],list) or len(payload["rgb_color"])!=3 or any(type(n) is not int or n<0 or n>255 for n in payload["rgb_color"])):
            return as_json(request,{"error":"Ugyldig farve"},400)
        if "media_content_id" in payload and (not isinstance(payload["media_content_id"],str) or len(payload["media_content_id"])>180):
            return as_json(request,{"error":"Ugyldigt medie"},400)
        if "media_content_type" in payload and (not isinstance(payload["media_content_type"],str) or len(payload["media_content_type"])>40):
            return as_json(request,{"error":"Ugyldig medietype"},400)
        if not self.hass.services.has_service(domain, service):
            return as_json(request,{"error":"Service findes ikke"},404)
        try:
            await self.hass.services.async_call(domain,service,payload,blocking=True)
        except Exception:
            return as_json(request,{"error":"Home Assistant afviste handlingen"},400)
        return as_json(request,{"ok":True})


class PairUpdate(HomeAssistantView):
    url = "/api/liquid_home/update/{sid}"
    name = "api:liquid_home:update"
    requires_auth = False

    def __init__(self, store, devices, storage):
        self.store = store
        self.devices = devices
        self.storage = storage

    async def post(self, request, sid):
        item = active(self.store, sid)
        if not item:
            return as_json(request, {"error": "Udløbet"}, 404)
        if item["count"] >= MAX_UPDATES:
            return as_json(request, {"error": "Maksimalt antal ændringer nået"}, 429)
        try:
            data = await request.json()
        except Exception:
            return as_json(request, {"error": "Ugyldig data"}, 400)
        if not secrets.compare_digest(str(data.get("key", "")), item["phone"]):
            return as_json(request, {"error": "Ikke tilladt"}, 403)
        if data.get("reset_all") is True:
            if item.get("device_id") in self.devices:
                self.devices.pop(item["device_id"], None)
                await self.storage.async_save(self.devices)
            item["authorized"] = False
            item["widgets"] = [{"type": "empty"} for _ in range(6)]
            item["selected"] = -1
            item["settings"] = {"idle": 2, "rules": [], "tapAction": "dashboard", "backgroundMode": "default", "setupComplete": False}
            item["revision"] += 1
            item["count"] += 1
            item["updates"].append({"rev": item["revision"], "type": "reset_all"})
            item["updates"] = item["updates"][-MAX_UPDATES:]
            return as_json(request, {"ok": True})
        action = data.get("tap_action")
        if action is not None:
            if action not in ("dashboard", "qr", "none"):
                return as_json(request, {"error": "Ugyldig trykhandling"}, 400)
            item["settings"]["tapAction"] = action
            item["revision"] += 1
            item["count"] += 1
            item["updates"].append({"rev": item["revision"], "type": "tap_action", "value": action})
            item["updates"] = item["updates"][-MAX_UPDATES:]
            return as_json(request, {"ok": True, "tap_action": action})
        # Other settings are allowed only through the paired phone key.
        update = None
        if "background_mode" in data:
            mode = data["background_mode"]
            if mode not in ("default", "nature", "custom"):
                return as_json(request, {"error": "Ugyldig baggrund"}, 400)
            item["settings"]["backgroundMode"] = mode
            update = {"type": "background_mode", "value": mode}
        elif data.get("setup_complete") is True:
            item["settings"]["setupComplete"] = True
            update = {"type": "setup_complete"}
        elif "idle" in data:
            v = data["idle"]
            if type(v) is not int or not 0 <= v <= 120:
                return as_json(request, {"error": "Ugyldig tid"}, 400)
            item["settings"]["idle"] = v
            update = {"type": "idle", "value": v}
        elif "rules" in data:
            rules = data["rules"]
            if not isinstance(rules, list) or len(rules) > 20:
                return as_json(request, {"error": "Højst 20 regler"}, 400)
            cleaned = []
            for rule in rules:
                if not isinstance(rule, dict):
                    return as_json(request, {"error": "Ugyldig regel"}, 400)
                fields = ("entity", "state", "title", "body", "emoji")
                if any(not isinstance(rule.get(f, ""), str) or len(rule.get(f, "")) > 160 for f in fields):
                    return as_json(request, {"error": "Ugyldig regeltekst"}, 400)
                if not rule.get("entity") or not rule.get("state") or not rule.get("title"):
                    return as_json(request, {"error": "Ufuldstændig regel"}, 400)
                clean = {f: rule.get(f, "") for f in fields}
                if len(clean["emoji"]) > 12:
                    return as_json(request, {"error": "Emoji er for lang"}, 400)
                if not clean["emoji"]:
                    clean["emoji"] = "🔔"
                cleaned.append(clean)
            item["settings"]["rules"] = cleaned
            update = {"type": "rules", "value": cleaned}
        elif "background" in data:
            value = data["background"]
            if not isinstance(value, str) or len(value) > 650000 or (value and not value.startswith("data:image/jpeg;base64,")):
                return as_json(request, {"error": "Kun JPG under 450 KB er tilladt"}, 400)
            update = {"type": "background", "value": value}
        elif "test_notification" in data:
            note = data["test_notification"]
            if not isinstance(note, dict) or any(not isinstance(note.get(f, ""), str) or len(note.get(f, "")) > 160 for f in ("title", "body", "emoji")):
                return as_json(request, {"error": "Ugyldig notifikation"}, 400)
            update = {"type": "test_notification", "title": note.get("title", "Test"), "body": note.get("body", ""), "emoji": note.get("emoji", "🔔") or "🔔"}
        elif "ha_token" in data:
            if not request.secure:
                return as_json(request, {"error": "HTTPS påkrævet"}, 403)
            value = data["ha_token"]
            if not isinstance(value, str) or not 30 <= len(value) <= 2048:
                return as_json(request, {"error": "Ugyldigt token"}, 400)
            update = {"type": "ha_token", "value": value}
        elif data.get("ha_disconnect") is True:
            if item.get("device_id") in self.devices:
                self.devices.pop(item["device_id"], None)
                await self.storage.async_save(self.devices)
            item["authorized"] = False
            update = {"type": "ha_disconnect"}
        if update is not None:
            if update.get("type") == "rules" and item.get("authorized") and item.get("device_id") in self.devices:
                self.devices[item["device_id"]]["entities"] = permitted_entities(item["widgets"], item["settings"]["rules"])
                await self.storage.async_save(self.devices)
            item["revision"] += 1
            item["count"] += 1
            update["rev"] = item["revision"]
            item["updates"].append(update)
            item["updates"] = item["updates"][-MAX_UPDATES:]
            return as_json(request, {"ok": True})
        slot = item["selected"]
        if slot < 0:
            return as_json(request, {"error": "Tryk først på et felt på iPad'en"}, 409)
        widget = data.get("widget")
        if not isinstance(widget, dict):
            return as_json(request, {"error": "Der mangler et widget"}, 400)
        kind = widget.get("type")
        if kind not in ("empty", "clock", "text", "sensor", "button", "music", "light", "switch", "cover"):
            return as_json(request, {"error": "Ukendt widgettype"}, 400)
        clean = {"type": kind}
        for field in ("label", "value", "entity", "service", "actionTarget", "actionService", "mediaSource", "mediaType"):
            value = widget.get(field, "")
            if not isinstance(value, str) or len(value) > 180:
                return as_json(request, {"error": "Et tekstfelt er for langt"}, 400)
            clean[field] = value
        action_type = widget.get("actionType", "default")
        if action_type not in ("default", "none", "toggle", "service", "url", "saver", "settings", "qr"):
            return as_json(request, {"error": "Ukendt trykhandling"}, 400)
        clean["actionType"] = action_type
        # Fixed tile types always use server-defined commands; ignore stale advanced actions.
        if kind in ("light","switch","cover","music","clock","sensor","text","empty"):
            clean["actionType"] = "default"
            clean["actionTarget"] = ""
            clean["actionService"] = ""
            clean["service"] = ""
        # The phone cannot choose the target slot. The iPad does that.
        item["revision"] += 1
        item["count"] += 1
        item["updates"].append({"rev": item["revision"], "slot": slot, "widget": clean})
        item["widgets"][slot] = clean
        if item.get("authorized") and item.get("device_id") in self.devices:
            self.devices[item["device_id"]]["entities"] = permitted_entities(item["widgets"], item["settings"]["rules"])
            await self.storage.async_save(self.devices)
        item["updates"] = item["updates"][-MAX_UPDATES:]
        return as_json(request, {"ok": True, "slot": slot})


async def async_setup(hass, config) -> bool:
    """Integration is configured from the Home Assistant UI, not YAML."""
    return True


async def async_setup_entry(hass, entry) -> bool:
    """Start one local Liquid Home instance and serve its bundled frontend."""
    if hass.data.get(DOMAIN, {}).get("registered"):
        return True
    pin = entry.options.get("pairing_pin", entry.data.get("pairing_pin", ""))
    if not isinstance(pin, str) or len(pin) < 12:
        return False
    storage = Store(hass, 1, "liquid_home_devices")
    devices = await storage.async_load() or {}
    store = {}
    await hass.http.async_register_static_paths([
        StaticPathConfig("/liquid_home", str(Path(__file__).parent / "frontend"), False)
    ])
    hass.http.register_view(PairNew(store))
    hass.http.register_view(PairQR(store))
    hass.http.register_view(PairState(store))
    hass.http.register_view(PairEntities(store, hass))
    hass.http.register_view(PairSelect(store))
    hass.http.register_view(PairUpdate(store, devices, storage))
    authorize_view = PairAuthorize(store, devices, storage, pin)
    hass.http.register_view(authorize_view)

    async def _update_pairing_code(hass, updated_entry):
        candidate = updated_entry.options.get("pairing_pin", updated_entry.data.get("pairing_pin", ""))
        if isinstance(candidate, str) and len(candidate) >= 12:
            authorize_view.pin = candidate

    entry.async_on_unload(entry.add_update_listener(_update_pairing_code))
    hass.http.register_view(DeviceProxy(hass, devices))
    hass.data[DOMAIN] = {"registered": True}
    return True
