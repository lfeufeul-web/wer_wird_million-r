import flet as ft
import asyncio
import copy
import inspect
import json
import os
import random
import re
import urllib.request
import time
from datetime import datetime, date, timezone
import uuid
import smtplib
import ssl
import base64
import io
from email.message import EmailMessage

import requests

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from gtts import gTTS
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None

# ---------- Persistent Database ----------
DB_FILE = "user_data.json"
ENV_FILE = ".env"
CODE_REQUEST_COOLDOWN_SECONDS = 10
FIREBASE_SERVICE_ACCOUNT_FILE = "firebase-service-account.json"
FIREBASE_WEB_API_KEY_ENV = "FIREBASE_WEB_API_KEY"
FIREBASE_APP_COLLECTION = "_app"
FIREBASE_GLOBAL_STATS_DOC = "global_stats"
AUTH_STORAGE_PREFIX = "wer_wird_millionaer.auth."
AUTH_EMAIL_KEY = AUTH_STORAGE_PREFIX + "email"
AUTH_UID_KEY = AUTH_STORAGE_PREFIX + "uid"
AUTH_REFRESH_TOKEN_KEY = AUTH_STORAGE_PREFIX + "refresh_token"


DEFAULT_GLOBAL_STATS = {
    "games_played": 0,
    "correct_answers": 0,
    "questions_answered": 0,
    "highest_money": "0 €",
    "highest_money_level": -1,
}

DEFAULT_USER_STATS = {
    "games_played": 0,
    "correct_answers": 0,
    "questions_answered": 0,
    "highest_money": "0 €",
    "highest_money_level": -1,
}
EXTRA_STATS_DEFAULTS = {
    "games_won": 0,
    "games_lost": 0,
    "wrong_answers": 0,
    "total_money_level": 0,
    "perfect_games": 0,
    "jokers_used": 0,
    "best_streak": 0,
    "current_streak": 0,
    "wallet_balance": 0,
    "daily_current_streak": 0,
    "daily_best_streak": 0,
    "daily_best_result": "0 €",
    "daily_avg_correct": 0.0,
    "daily_games_played": 0,
    "last_daily_played": "",
}


def load_env_file():
    if not os.path.exists(ENV_FILE):
        return

    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"Error loading .env: {e}")


load_env_file()


def get_smtp_config():
    host = os.getenv("SMTP_HOST", "").strip()
    port_raw = os.getenv("SMTP_PORT", "587").strip() or "587"
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    username = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
    sender = os.getenv("SMTP_FROM", username).strip()
    use_ssl = os.getenv("SMTP_SSL", "false").strip().lower() in ("1", "true", "yes", "on")
    use_tls = os.getenv("SMTP_TLS", "true").strip().lower() in ("1", "true", "yes", "on")
    app_name = os.getenv("APP_NAME", "Wer wird Millionär").strip() or "Wer wird Millionär"

    missing = []
    if not host:
        missing.append("SMTP_HOST")
    if not username:
        missing.append("SMTP_USER")
    if not password:
        missing.append("SMTP_PASSWORD")
    if not sender:
        missing.append("SMTP_FROM")

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "use_ssl": use_ssl,
        "use_tls": use_tls,
        "app_name": app_name,
        "missing": missing,
    }


def send_verification_email(recipient: str, code: str):
    config = get_smtp_config()
    if config["missing"]:
        raise RuntimeError("E-Mail-Versand ist noch nicht eingerichtet. Bitte SMTP-Daten in .env eintragen.")

    msg = EmailMessage()
    msg["Subject"] = f"Dein Login-Code für {config['app_name']}"
    msg["From"] = config["sender"]
    msg["To"] = recipient
    msg.set_content(
        f"Hallo,\n\n"
        f"dein 6-stelliger Bestätigungscode lautet: {code}\n\n"
        f"Der Code ist 10 Minuten gültig.\n\n"
        f"Wenn du dich nicht anmelden wolltest, kannst du diese E-Mail ignorieren.\n"
    )
    msg.add_alternative(
        f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #1f1f1f;">
            <h2>{config['app_name']}</h2>
            <p>Dein 6-stelliger Bestätigungscode lautet:</p>
            <p style="font-size: 28px; font-weight: bold; letter-spacing: 4px;">{code}</p>
            <p>Der Code ist 10 Minuten gültig.</p>
            <p style="color: #666;">Wenn du dich nicht anmelden wolltest, kannst du diese E-Mail ignorieren.</p>
          </body>
        </html>
        """,
        subtype="html",
    )

    context = ssl.create_default_context()
    if config["use_ssl"]:
        with smtplib.SMTP_SSL(config["host"], config["port"], context=context, timeout=20) as server:
            server.login(config["username"], config["password"])
            server.send_message(msg)
        return

    with smtplib.SMTP(config["host"], config["port"], timeout=20) as server:
        server.ehlo()
        if config["use_tls"]:
            server.starttls(context=context)
            server.ehlo()
        server.login(config["username"], config["password"])
        server.send_message(msg)

def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        default_db = {
            "current_user_email": None,
            "global_stats": {
                "games_played": 0,
                "correct_answers": 0,
                "questions_answered": 0,
                "highest_money": "0 €",
                "highest_money_level": -1
            },
            "users": {}
        }
        save_db(default_db)
        return default_db
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "current_user_email": None,
            "global_stats": {
                "games_played": 0,
                "correct_answers": 0,
                "questions_answered": 0,
                "highest_money": "0 €",
                "highest_money_level": -1
            },
            "users": {}
        }

def save_db(db: dict):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving db: {e}")


THEME_GAME_ZONES = {
    # Classic / gradient themes use flow layout — these zones are only
    # used by the neon_nexus image-based theme.
    "play_column": {"l": 0.032, "t": 0.09, "w": 0.648, "h": 0.65},
    "jokers": {"l": 0.032, "t": 0.75, "w": 0.648, "h": 0.10},
    "ladder": {"l": 0.695, "t": 0.09, "w": 0.205, "h": 0.76},
    "exit": {"l": 0.032, "t": 0.025, "w": 0.1146, "h": 0.050},
    "overlay": {"l": 0, "t": 0, "w": 1, "h": 1},
}

NEON_NEXUS_ZONES = {
    "exit": {"l": 0.0198, "t": 0.0204, "w": 0.1146, "h": 0.0500},
    "timer": {"l": 0.18, "t": 0.0204, "w": 0.43, "h": 0.0500},
    "question": {"l": 0.0448, "t": 0.0704, "w": 0.5698, "h": 0.2102},
    "answers": {"l": 0.0448, "t": 0.3102, "w": 0.5698, "h": 0.3778},
    "footer": {"l": 0.0448, "t": 0.7102, "w": 0.5698, "h": 0.1667},
    "ladder": {"l": 0.6651, "t": 0.0704, "w": 0.2797, "h": 0.8593},
    "overlay": {"l": 0, "t": 0, "w": 1, "h": 1},
}


THEMES = {
    "classic": {
        "label": "Klassisch",
        "is_light": False,
        "text_primary": "#FFFFFF",
        "text_secondary": "#E0D0F0",
        "text_muted": "#CCCCCC",
        "gradient": ["#2C1654", "#6B2FA0", "#C2185B"],
        "panel": "#1A0A30",
        "border": "#9B59B6",
        "accent": "#9B59B6",
        "accent_2": "#F4A460",
        "success": "#2ECC71",
        "danger": "#C2185B",
        "gold": "#FFD700",
        "question_bg": "#FFFFFF",
        "question_text": "#2C1654",
        "answer_bg": "#FFFFFF",
        "answer_text": "#2C1654",
        "answer_colors": ["#F4A460", "#9B59B6", "#2ECC71", "#E91E8C"],
    },
    "neon_nexus": {
        "label": "Neon Nexus",
        "game_layout": "themed",
        "game_bg": "neon_nexus_bg_clean.png",
        "layout_zones": NEON_NEXUS_ZONES,
        "is_light": True,
        "text_primary": "#0F172A",
        "text_secondary": "#334155",
        "text_muted": "#64748B",
        "gradient": ["#000000", "#021208", "#042810"],
        "panel": "#00000000",
        "border": "#00000000",
        "accent": "#00000000",
        "accent_2": "#D946EF",
        "success": "#16A34A",
        "danger": "#DC2626",
        "gold": "#D946EF",
        "question_bg": "#00000000",
        "question_text": "#1E293B",
        "answer_bg": "#00000000",
        "answer_text": "#1E293B",
        "answer_colors": ["#0ea5e9", "#d946ef", "#10b981", "#f59e0b"],
    },
    "hacker": {
        "label": "Hacker Matrix",
        "is_light": False,
        "text_primary": "#00FF41",
        "text_secondary": "#008F11",
        "text_muted": "#003B00",
        "gradient": ["#000000", "#0B0C10", "#000000"],
        "panel": "#000000",
        "border": "#00FF41",
        "accent": "#00FF41",
        "accent_2": "#008F11",
        "success": "#00FF41",
        "danger": "#FF0000",
        "gold": "#FFFFFF",
        "question_bg": "#000000",
        "question_text": "#00FF41",
        "answer_bg": "#000000",
        "answer_text": "#00FF41",
        "answer_colors": ["#008F11", "#00FF41", "#008F11", "#00FF41"],
    },
    "royal": {
        "label": "Royal Gold",
        "is_light": False,
        "text_primary": "#FFFFFF",
        "text_secondary": "#F3E5AB",
        "text_muted": "#B5A642",
        "gradient": ["#2B0000", "#4A0E17", "#1A0000"],
        "panel": "#330000",
        "border": "#D4AF37",
        "accent": "#D4AF37",
        "accent_2": "#AA6C39",
        "success": "#32CD32",
        "danger": "#DC143C",
        "gold": "#FFD700",
        "question_bg": "#200000",
        "question_text": "#F3E5AB",
        "answer_bg": "#200000",
        "answer_text": "#FFD700",
        "answer_colors": ["#8B0000", "#4A0E17", "#8B0000", "#4A0E17"],
    },
    "cyberpunk": {
        "label": "Cyberpunk 2077",
        "is_light": False,
        "text_primary": "#00FFFF",
        "text_secondary": "#FF00FF",
        "text_muted": "#888888",
        "gradient": ["#090909", "#111133", "#330033"],
        "panel": "#111111",
        "border": "#FF00FF",
        "accent": "#00FFFF",
        "accent_2": "#FFFF00",
        "success": "#00FF00",
        "danger": "#FF0055",
        "gold": "#FFFF00",
        "question_bg": "#1A1A1A",
        "question_text": "#00FFFF",
        "answer_bg": "#1A1A1A",
        "answer_text": "#FF00FF",
        "answer_colors": ["#FF00FF", "#00FFFF", "#FFFF00", "#FF0055"],
    },
}
DEFAULT_USER_SETTINGS = {"theme": "classic", "play_audio": True}

SHOP_CATALOG = {
    "themes": [
        {"id": "hacker", "name": "Hacker Matrix", "price": 5000, "type": "theme"},
        {"id": "royal", "name": "Royal Gold", "price": 25000, "type": "theme"},
        {"id": "cyberpunk", "name": "Cyberpunk 2077", "price": 100000, "type": "theme"},
    ],
    "titles": [
        {"id": "Neuling", "name": "Neuling", "price": 0, "type": "title"},
        {"id": "Quiz-Lehrling", "name": "Quiz-Lehrling", "price": 2500, "type": "title"},
        {"id": "Alleswisser", "name": "Alleswisser", "price": 15000, "type": "title"},
        {"id": "Millionär-Club", "name": "Millionär-Club", "price": 150000, "type": "title"},
        {"id": "Quiz-Gott", "name": "Quiz-Gott", "price": 1000000, "type": "title"},
    ]
}


# ---------- Audio & TTS System ----------
AUDIO_DIR = os.path.join("assets", "audio")
try:
    os.makedirs(AUDIO_DIR, exist_ok=True)
except Exception:
    pass  # read-only filesystem on Render is fine, TTS just won't work
BG_MUSIC_FILE = "bg_music.mp3"

def play_tts(page: ft.Page, text: str):
    """Generates an MP3 via gTTS and plays it on the page."""
    if not HAS_TTS:
        return
    # check if user disabled audio
    # we don't have access to state directly here, but let's assume it's passed or global isn't used
    
    async def generate_and_play():
        try:
            os.makedirs(AUDIO_DIR, exist_ok=True)
            filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
            filepath = os.path.join(AUDIO_DIR, filename)
            tts = gTTS(text, lang="de")
            tts.save(filepath)
            
            # play via flet audio
            try:
                audio = ft.Audio(
                    src=f"audio/{filename}",
                    autoplay=True,
                    volume=1.0,
                    on_state_changed=lambda e: _cleanup_tts(e, filepath, audio, page)
                )
                page.overlay.append(audio)
                page.update()
            except AttributeError:
                print("ft.Audio not available - TTS audio playback disabled")
        except Exception as e:
            print(f"TTS Error: {e}")

    page.run_task(generate_and_play)

def _cleanup_tts(e, filepath, audio_ctrl, page):
    if e.data == "completed":
        try:
            if audio_ctrl in page.overlay:
                page.overlay.remove(audio_ctrl)
                page.update()
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

def init_bg_music(page: ft.Page):
    """Returns the background music audio control (placeholder for now)."""
    try:
        bg = ft.Audio(
            src=f"audio/{BG_MUSIC_FILE}",
            autoplay=True,
            volume=0.3,
        )
        # create dummy file if not exists so it doesn't crash on load
        try:
            dummy_path = os.path.join(AUDIO_DIR, BG_MUSIC_FILE)
            if not os.path.exists(dummy_path):
                os.makedirs(AUDIO_DIR, exist_ok=True)
                with open(dummy_path, "wb") as f:
                    pass  # empty placeholder
        except Exception:
            pass  # ignore on read-only filesystems
        return bg
    except AttributeError:
        print("ft.Audio not available in this Flet version - audio disabled")
        return None



def default_db() -> dict:
    return {
        "current_user_email": None,
        "global_stats": DEFAULT_GLOBAL_STATS.copy(),
        "users": {},
    }


def default_user(email: str, uid: str | None = None) -> dict:
    stats = DEFAULT_USER_STATS.copy()
    stats.update(EXTRA_STATS_DEFAULTS)
    user = {
        "email": email,
        "name": email.split("@")[0].capitalize(),
        "settings": DEFAULT_USER_SETTINGS.copy(),
        "stats": stats,
        "game_history": [],
        "friend_code": generate_friend_code(),
        "friends": [],
        "friend_requests_in": [],
        "friend_requests_out": [],
        "unlocked_themes": ["classic", "neon_nexus"],
        "unlocked_titles": ["Neuling"],
        "active_title": "Neuling",
        "unlocked_achievements": [],
    }
    if uid:
        user["uid"] = uid
    return user


def get_firestore_client():
    if firebase_admin is None:
        return None

    try:
        if not firebase_admin._apps:
            service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
            service_account_file = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", FIREBASE_SERVICE_ACCOUNT_FILE).strip()

            if service_account_json:
                cred = credentials.Certificate(json.loads(service_account_json))
            elif os.path.exists(service_account_file):
                cred = credentials.Certificate(service_account_file)
            else:
                return None

            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Firebase init error: {e}")
        return None


def load_local_db() -> dict:
    if not os.path.exists(DB_FILE):
        return default_db()

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
            db.setdefault("current_user_email", None)
            db.setdefault("global_stats", DEFAULT_GLOBAL_STATS.copy())
            db.setdefault("users", {})
            for key, value in DEFAULT_GLOBAL_STATS.items():
                db["global_stats"].setdefault(key, value)
            return db
    except Exception:
        return default_db()


def load_db() -> dict:
    client = get_firestore_client()
    if client is None:
        return load_local_db()

    db = default_db()
    try:
        global_doc = client.collection(FIREBASE_APP_COLLECTION).document(FIREBASE_GLOBAL_STATS_DOC).get()
        if global_doc.exists:
            db["global_stats"].update(global_doc.to_dict() or {})

        for user_doc in client.collection("users").stream():
            user_data = user_doc.to_dict() or {}
            email = user_data.get("email")
            if not email:
                continue
            user_data["uid"] = user_doc.id
            user_data.setdefault("settings", DEFAULT_USER_SETTINGS.copy())
            user_data.setdefault("stats", DEFAULT_USER_STATS.copy())
            user_data.setdefault("game_history", [])
            ensure_social_defaults(user_data)
            for key, value in DEFAULT_USER_SETTINGS.items():
                user_data["settings"].setdefault(key, value)
            ensure_stats_defaults(user_data["stats"])
            db["users"][email] = user_data
        return db
    except Exception as e:
        print(f"Firebase load error: {e}")
        return load_local_db()


def save_db(db: dict):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving db: {e}")

    client = get_firestore_client()
    if client is None:
        return

    try:
        client.collection(FIREBASE_APP_COLLECTION).document(FIREBASE_GLOBAL_STATS_DOC).set(
            db.get("global_stats", DEFAULT_GLOBAL_STATS.copy()),
            merge=True,
        )
        for email, user in db.get("users", {}).items():
            uid = user.get("uid")
            if not uid:
                continue
            payload = user.copy()
            payload["email"] = payload.get("email", email)
            client.collection("users").document(uid).set(payload, merge=True)
    except Exception as e:
        print(f"Firebase save error: {e}")


def get_firebase_web_api_key() -> str:
    return os.getenv(FIREBASE_WEB_API_KEY_ENV, "").strip()


def firebase_auth_request(action: str, email: str, password: str) -> dict:
    api_key = get_firebase_web_api_key()
    if not api_key:
        raise RuntimeError("FIREBASE_WEB_API_KEY fehlt in .env oder bei Render.")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{action}?key={api_key}"
    response = requests.post(
        url,
        json={
            "email": email,
            "password": password,
            "returnSecureToken": True,
        },
        timeout=20,
    )
    data = response.json()
    if response.status_code >= 400:
        error_code = data.get("error", {}).get("message", "UNKNOWN_ERROR")
        raise RuntimeError(firebase_auth_error_message(error_code))
    return data


def firebase_refresh_auth(refresh_token: str) -> dict:
    api_key = get_firebase_web_api_key()
    if not api_key:
        raise RuntimeError("FIREBASE_WEB_API_KEY fehlt in .env oder bei Render.")

    response = requests.post(
        f"https://securetoken.googleapis.com/v1/token?key={api_key}",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=20,
    )
    data = response.json()
    if response.status_code >= 400:
        error_code = data.get("error", {}).get("message", "UNKNOWN_ERROR")
        raise RuntimeError(firebase_auth_error_message(error_code))
    return data


def firebase_auth_error_message(error_code: str) -> str:
    messages = {
        "EMAIL_EXISTS": "Diese E-Mail ist bereits registriert.",
        "EMAIL_NOT_FOUND": "Kein Konto mit dieser E-Mail gefunden.",
        "INVALID_PASSWORD": "Das Passwort ist falsch.",
        "INVALID_LOGIN_CREDENTIALS": "E-Mail oder Passwort ist falsch.",
        "WEAK_PASSWORD : Password should be at least 6 characters": "Das Passwort muss mindestens 6 Zeichen haben.",
        "MISSING_PASSWORD": "Bitte gib ein Passwort ein.",
        "INVALID_EMAIL": "Bitte gib eine gueltige E-Mail-Adresse ein.",
    }
    return messages.get(error_code, f"Firebase Login-Fehler: {error_code}")


def ensure_firebase_user(uid: str, email: str) -> dict:
    user = default_user(email, uid)
    client = get_firestore_client()
    if client is None:
        return user

    ref = client.collection("users").document(uid)
    doc = ref.get()
    if doc.exists:
        stored = doc.to_dict() or {}
        user.update(stored)
        user["uid"] = uid
        user["email"] = stored.get("email", email)

    user.setdefault("settings", DEFAULT_USER_SETTINGS.copy())
    user.setdefault("stats", DEFAULT_USER_STATS.copy())
    user.setdefault("game_history", [])
    ensure_social_defaults(user)
    for key, value in DEFAULT_USER_SETTINGS.items():
        user["settings"].setdefault(key, value)
    ensure_stats_defaults(user["stats"])

    ref.set(user, merge=True)
    return user


def get_page_storage(page: ft.Page):
    return getattr(page, "shared_preferences", None) or getattr(page, "client_storage", None)


async def call_storage_method(method, *args):
    result = method(*args)
    if inspect.isawaitable(result):
        return await result
    return result


async def storage_get(page: ft.Page, key: str):
    storage = get_page_storage(page)
    if storage is None:
        return None
    return await call_storage_method(storage.get, key)


async def storage_set(page: ft.Page, key: str, value):
    storage = get_page_storage(page)
    if storage is None:
        return
    await call_storage_method(storage.set, key, value)


async def storage_remove(page: ft.Page, key: str):
    storage = get_page_storage(page)
    if storage is None:
        return
    await call_storage_method(storage.remove, key)


async def save_remembered_login(page: ft.Page, auth_data: dict, remember: bool):
    if not remember:
        await clear_remembered_login(page)
        return

    refresh_token = auth_data.get("refreshToken")
    uid = auth_data.get("localId")
    email = auth_data.get("email")
    if not refresh_token or not uid or not email:
        return

    await storage_set(page, AUTH_EMAIL_KEY, email)
    await storage_set(page, AUTH_UID_KEY, uid)
    await storage_set(page, AUTH_REFRESH_TOKEN_KEY, refresh_token)


async def clear_remembered_login(page: ft.Page):
    await storage_remove(page, AUTH_EMAIL_KEY)
    await storage_remove(page, AUTH_UID_KEY)
    await storage_remove(page, AUTH_REFRESH_TOKEN_KEY)


async def restore_remembered_login(page: ft.Page, state: dict):
    import asyncio
    # Give the WebSocket/client_storage time to sync after page load.
    # We try twice with increasing delays for slow connections.
    refresh_token = None
    for wait in (0.8, 1.2):
        await asyncio.sleep(wait)
        refresh_token = await storage_get(page, AUTH_REFRESH_TOKEN_KEY)
        if refresh_token:
            break

    email = await storage_get(page, AUTH_EMAIL_KEY)
    uid = await storage_get(page, AUTH_UID_KEY)

    print(f"[auto-login] token={'yes' if refresh_token else 'no'}, email={email}, uid={uid}")

    if not refresh_token or not email or not uid:
        print("[auto-login] No stored credentials – showing guest menu.")
        open_main_menu(page, state)
        return

    try:
        refreshed = firebase_refresh_auth(refresh_token)
        new_uid = refreshed.get("user_id") or refreshed.get("localId") or uid
        new_token = refreshed.get("refresh_token") or refresh_token
        user = ensure_firebase_user(new_uid, email)

        db = load_db()
        db["users"][email] = user
        update_last_active(db, email)
        save_db(db)

        state["current_user_email"] = email
        state["current_user_uid"] = new_uid
        # Persist updated tokens back to storage.
        await storage_set(page, AUTH_UID_KEY, new_uid)
        await storage_set(page, AUTH_REFRESH_TOKEN_KEY, new_token)
        print(f"[auto-login] Success – logged in as {email}")
        open_main_menu(page, state)
    except Exception as e:
        print(f"[auto-login] Token refresh failed: {e} – showing guest menu.")
        open_main_menu(page, state)


def ensure_user_settings(db: dict, email: str):
    user = db.get("users", {}).get(email)
    if not user:
        return
    settings = user.setdefault("settings", {})
    for key, value in DEFAULT_USER_SETTINGS.items():
        settings.setdefault(key, value)


def ensure_stats_defaults(stats: dict):
    for key, value in DEFAULT_USER_STATS.items():
        stats.setdefault(key, value)
    for key, value in EXTRA_STATS_DEFAULTS.items():
        stats.setdefault(key, value)


def generate_friend_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(8))


def normalize_friend_code(code: str) -> str:
    code = (code or "").strip().upper()
    if code.startswith("WWMFRIEND:"):
        code = code.split(":", 1)[1]
    return re.sub(r"[^A-Z0-9]", "", code)


def ensure_social_defaults(user: dict):
    user.setdefault("friend_code", generate_friend_code())
    user.setdefault("friends", [])
    user.setdefault("friend_requests_in", [])
    user.setdefault("friend_requests_out", [])
    user.setdefault("last_active", None)
    user.setdefault("weekly_stats", {"week": "", "money_level": 0, "games_won": 0})
    user.setdefault("custom_quizzes", [])


def get_current_week_key() -> str:
    """Returns ISO week key like '2025-W21'."""
    now = datetime.now(timezone.utc)
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


def update_last_active(db: dict, email: str):
    """Sets last_active to now for the given user in db."""
    user = db.get("users", {}).get(email)
    if user:
        user["last_active"] = datetime.now(timezone.utc).isoformat()


def format_last_active(iso_str: str | None) -> str:
    if not iso_str:
        return "Noch nie online"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        minutes = int(diff.total_seconds() // 60)
        if minutes < 2:
            return "Gerade eben online"
        if minutes < 60:
            return f"Vor {minutes} Min. online"
        hours = minutes // 60
        if hours < 24:
            return f"Vor {hours} Std. online"
        days = hours // 24
        return f"Vor {days} Tag(en) online"
    except Exception:
        return "Unbekannt"


def remove_friend(state: dict, friend_email: str):
    """Removes the friendship between the current user and friend_email."""
    db, email, user = current_user_entry(state)
    if not email or not user:
        return
    friend = db.get("users", {}).get(friend_email)
    ensure_social_defaults(user)
    if friend_email in user["friends"]:
        user["friends"].remove(friend_email)
    if friend:
        ensure_social_defaults(friend)
        if email in friend["friends"]:
            friend["friends"].remove(email)
    save_db(db)


def current_user_entry(state: dict) -> tuple[dict, str | None, dict | None]:
    db = load_db()
    email = state.get("current_user_email")
    user = db.get("users", {}).get(email) if email else None
    if user:
        ensure_social_defaults(user)
        save_db(db)
    return db, email, user


def find_user_by_friend_code(db: dict, code: str) -> tuple[str | None, dict | None]:
    normalized = normalize_friend_code(code)
    for email, user in db.get("users", {}).items():
        ensure_social_defaults(user)
        if normalize_friend_code(user.get("friend_code", "")) == normalized:
            return email, user
    return None, None


def save_friend_request(state: dict, target_code: str) -> str:
    db, email, user = current_user_entry(state)
    if not email or not user:
        return "Bitte melde dich zuerst an."
    target_email, target = find_user_by_friend_code(db, target_code)
    if not target_email or not target:
        return "Kein Nutzer mit diesem Freundescode gefunden."
    if target_email == email:
        return "Du kannst nicht mit dir selbst befreundet sein."
    if target_email in user.get("friends", []):
        return "Ihr seid bereits Freunde."

    ensure_social_defaults(target)
    if email not in target["friend_requests_in"]:
        target["friend_requests_in"].append(email)
    if target_email not in user["friend_requests_out"]:
        user["friend_requests_out"].append(target_email)
    save_db(db)
    return "Freundschaftsanfrage gesendet."


def respond_friend_request(state: dict, requester_email: str, accept: bool):
    db, email, user = current_user_entry(state)
    if not email or not user or requester_email not in db.get("users", {}):
        return
    requester = db["users"][requester_email]
    ensure_social_defaults(user)
    ensure_social_defaults(requester)
    if requester_email in user["friend_requests_in"]:
        user["friend_requests_in"].remove(requester_email)
    if email in requester["friend_requests_out"]:
        requester["friend_requests_out"].remove(email)
    if accept:
        if requester_email not in user["friends"]:
            user["friends"].append(requester_email)
        if email not in requester["friends"]:
            requester["friends"].append(email)
    save_db(db)


def friend_qr_base64(code: str) -> str | None:
    if qrcode is None:
        return None
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    url = f"https://wer-wird-million-r-eo5q.onrender.com/?add_friend={normalize_friend_code(code)}"
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def get_user_settings(state: dict) -> dict:
    db = load_db()
    email = state.get("current_user_email")
    if email and email in db.get("users", {}):
        ensure_user_settings(db, email)
        save_db(db)
        return db["users"][email]["settings"]
    return DEFAULT_USER_SETTINGS.copy()


def get_theme(state: dict) -> dict:
    theme_name = get_user_settings(state).get("theme", "classic")
    return THEMES.get(theme_name, THEMES["classic"])


def theme_value(theme: dict, key: str, fallback: str):
    return theme.get(key, THEMES["classic"].get(key, fallback))


def theme_txt(theme: dict, role: str = "primary") -> str:
    """Readable text color for menus and screens (light vs dark themes)."""
    light = theme.get("is_light", False)
    defaults = {
        "primary": "#1e293b" if light else "#FFFFFF",
        "secondary": "#334155" if light else "#E0D0F0",
        "muted": "#64748b" if light else "#AAAAAA",
    }
    return theme.get(f"text_{role}", defaults.get(role, "#FFFFFF"))


def uses_themed_game(theme: dict) -> bool:
    return theme.get("game_layout") == "themed" and bool(theme.get("game_bg"))


def _page_size(page: ft.Page) -> tuple[float, float]:
    """Viewport size for full-screen game layout (web + desktop)."""
    w = page.width
    h = page.height
    win = getattr(page, "window", None)
    if (not w or w <= 0) and win:
        w = win.width
    if (not h or h <= 0) and win:
        h = win.height
    return float(w or 1100), float(h or 720)


def _themed_game_background(bg_image: str, page_w: float, page_h: float, overlay_color: str) -> ft.Stack:
    """Background stretched to the full viewport (bottom layer in game Stack)."""
    w, h = max(1, int(page_w)), max(1, int(page_h))
    return ft.Stack(
        [
            ft.Image(src=bg_image, fit=ft.BoxFit.FILL, width=w, height=h),
            ft.Container(width=w, height=h, bgcolor=overlay_color),
        ],
        width=w,
        height=h,
    )


def _set_themed_game_resize(page: ft.Page, state: dict):
    state["_themed_game_active"] = True

    def on_resize(_e):
        if state.get("_themed_game_active") and uses_themed_game(get_theme(state)):
            render_game_screen(page, state)

    page.on_resize = on_resize


def _clear_themed_game_resize(state: dict):
    state["_themed_game_active"] = False
    stop_game_timer(state)
    state.pop("_timer_active_key", None)

def money_level_value(money_level_idx: int) -> int:
    if money_level_idx < 0:
        return 0
    return money_level_idx + 1


def update_stats_block(stats: dict, correct: int, answered: int, money: str, money_level_idx: int, won: bool, jokers_used: int):
    ensure_stats_defaults(stats)
    wrong = max(answered - correct, 0)
    stats["games_played"] += 1
    stats["correct_answers"] += correct
    stats["questions_answered"] += answered
    stats["wrong_answers"] += wrong
    stats["total_money_level"] += money_level_value(money_level_idx)
    stats["jokers_used"] += jokers_used
    
    # Parse money string to add to wallet
    try:
        money_amount = int(money.replace(" €", "").replace(".", "").replace(",", ""))
    except ValueError:
        money_amount = 0
    stats["wallet_balance"] = stats.get("wallet_balance", 0) + money_amount

    if won:
        stats["games_won"] += 1
        stats["perfect_games"] += 1 if wrong == 0 else 0
        stats["current_streak"] += 1
        stats["best_streak"] = max(stats.get("best_streak", 0), stats["current_streak"])
    else:
        stats["games_lost"] += 1
        stats["current_streak"] = 0
    if money_level_idx > stats.get("highest_money_level", -1):
        stats["highest_money"] = money
        stats["highest_money_level"] = money_level_idx


def build_game_history_entry(correct: int, answered: int, money: str, money_level_idx: int, won: bool, jokers_used: int) -> dict:
    return {
        "played_at": datetime.now(timezone.utc).isoformat(),
        "won": won,
        "money": money,
        "money_level": money_level_idx,
        "correct_answers": correct,
        "wrong_answers": max(answered - correct, 0),
        "questions_answered": answered,
        "jokers_used": jokers_used,
    }


def update_game_stats(correct: int, answered: int, money: str, money_level_idx: int, email: str | None = None, won: bool = False, jokers_used: int = 0):
    db = load_db()

    g = db["global_stats"]
    update_stats_block(g, correct, answered, money, money_level_idx, won, jokers_used)

    if email and email in db["users"]:
        u = db["users"][email]["stats"]
        update_stats_block(u, correct, answered, money, money_level_idx, won, jokers_used)
        history = db["users"][email].setdefault("game_history", [])
        history.append(build_game_history_entry(correct, answered, money, money_level_idx, won, jokers_used))
        db["users"][email]["game_history"] = history[-30:]
        # Update weekly stats
        ensure_social_defaults(db["users"][email])
        week_key = get_current_week_key()
        ws = db["users"][email]["weekly_stats"]
        if ws.get("week") != week_key:
            ws["week"] = week_key
            ws["money_level"] = 0
            ws["games_won"] = 0
        ws["money_level"] = max(ws["money_level"], money_level_idx + 1 if money_level_idx >= 0 else 0)
        if won:
            ws["games_won"] = ws.get("games_won", 0) + 1
        # Update last_active
        update_last_active(db, email)

    save_db(db)


def save_current_game(state: dict):
    email = state.get("current_user_email")
    if not email or state.get("game_finished") or state.get("is_daily_challenge"):
        return

    db = load_db()
    if email not in db.get("users", {}):
        return

    saved_game = {
        "money": state.get("money", "0 €"),
        "questions_answered": state.get("questions_answered", 0),
        "correct": state.get("correct", 0),
        "jokers_used": state.get("jokers_used", 0),
        "question_index": state.get("question_index", 0),
        "questions": state.get("questions", []),
        "is_custom_game": state.get("is_custom_game", False),
        "custom_quiz_id": state.get("custom_quiz_id"),
        "custom_quiz_title": state.get("custom_quiz_title"),
        "selected_jokers": state.get("selected_jokers", []),
        "jokers_used_ids": state.get("jokers_used_ids", []),
        "time_left": max(0, int(state.get("time_left", QUESTION_TIME_SEC))),
        "hidden_answers": state.get("hidden_answers", []),
        "time_pressure_enabled": bool(state.get("time_pressure_enabled", True)),
        "question_time_sec": int(state.get("question_time_sec", QUESTION_TIME_SEC)),
        "phone_until": state.get("phone_until"),
        "friend_until": state.get("friend_until"),
    }
    db["users"][email]["saved_game"] = saved_game
    state["saved_game"] = saved_game
    save_db(db)


def clear_saved_game(state: dict):
    email = state.get("current_user_email")
    if not email:
        return

    state.pop("saved_game", None)
    db = load_db()
    if email in db.get("users", {}) and "saved_game" in db["users"][email]:
        db["users"][email].pop("saved_game", None)
        save_db(db)

    uid = state.get("current_user_uid") or db.get("users", {}).get(email, {}).get("uid")
    client = get_firestore_client()
    if client is not None and uid and firestore is not None:
        try:
            client.collection("users").document(uid).update({"saved_game": firestore.DELETE_FIELD})
        except Exception as e:
            print(f"Firebase saved_game delete error: {e}")


def get_saved_game_for_state(state: dict) -> dict | None:
    email = state.get("current_user_email")
    if not email or state.get("game_finished"):
        return None

    saved = state.get("saved_game")
    if not saved:
        db = load_db()
        saved = db.get("users", {}).get(email, {}).get("saved_game")
        if saved:
            state["saved_game"] = saved
    if not saved or not saved.get("questions"):
        return None
    if saved.get("question_index", 0) >= len(saved.get("questions", [])):
        clear_saved_game(state)
        return None
    return saved


def saved_game_summary(saved: dict) -> str:
    total = len(saved.get("questions", []))
    question_index = saved.get("question_index", 0)
    current_question = min(question_index + 1, total) if total else 1
    money = saved.get("money", "0 €")
    correct = saved.get("correct", 0)
    prefix = ""
    if saved.get("is_custom_game"):
        title = saved.get("custom_quiz_title") or "Eigenes Quiz"
        prefix = f"{title} · "
    return f"{prefix}Frage {current_question} von {total} · {money} · {correct} richtig"


def resume_saved_game(page: ft.Page, state: dict, saved: dict | None = None):
    saved = saved or get_saved_game_for_state(state)
    if not saved:
        start_new_game(page, state, force_new=True)
        return

    state.update({
        "money": saved.get("money", "0 €"),
        "questions_answered": saved.get("questions_answered", 0),
        "correct": saved.get("correct", 0),
        "jokers_used": saved.get("jokers_used", 0),
        "question_index": saved.get("question_index", 0),
        "questions": saved.get("questions", []),
        "saved_game": saved,
        "game_finished": False,
        "is_custom_game": saved.get("is_custom_game", False),
        "custom_quiz_id": saved.get("custom_quiz_id"),
        "custom_quiz_title": saved.get("custom_quiz_title"),
        "selected_jokers": saved.get("selected_jokers", []),
        "jokers_used_ids": saved.get("jokers_used_ids", []),
        "time_left": max(0, int(saved.get("time_left", QUESTION_TIME_SEC))),
        "hidden_answers": list(saved.get("hidden_answers", [])),
        "time_pressure_enabled": bool(saved.get("time_pressure_enabled", True)),
        "question_time_sec": int(saved.get("question_time_sec", QUESTION_TIME_SEC)),
        "phone_until": saved.get("phone_until"),
        "friend_until": saved.get("friend_until"),
    })
    state.pop("_timer_active_key", None)
    state["_timer_question_key"] = f"q{state['question_index']}"
    if len(state.get("selected_jokers", [])) == JOKER_SELECT_COUNT:
        show_next_question(page, state)
    else:
        show_joker_selection(page, state, lambda: show_next_question(page, state))


# ---------- Custom quizzes ----------
MAX_CUSTOM_QUESTIONS = 15
MIN_CUSTOM_ANSWERS = 2
MAX_CUSTOM_ANSWERS = 4


def new_custom_quiz_id() -> str:
    return f"quiz_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"


def money_levels_for_state(state: dict) -> list[str]:
    """Prize ladder length matches the number of questions in the current game."""
    questions = state.get("questions") or []
    count = len(questions) if questions else len(MONEY_LEVELS)
    count = max(1, min(count, len(MONEY_LEVELS)))
    return MONEY_LEVELS[:count]


def get_user_custom_quizzes(state: dict) -> list[dict]:
    email = state.get("current_user_email")
    if not email:
        return []
    db = load_db()
    user = db.get("users", {}).get(email, {})
    return list(user.get("custom_quizzes", []) or [])


def persist_user_custom_quizzes(state: dict, quizzes: list[dict]):
    email = state.get("current_user_email")
    if not email:
        return
    db = load_db()
    if email not in db.get("users", {}):
        return
    db["users"][email]["custom_quizzes"] = quizzes
    save_db(db)


def find_custom_quiz(quizzes: list[dict], quiz_id: str) -> dict | None:
    for quiz in quizzes:
        if quiz.get("id") == quiz_id:
            return quiz
    return None


def custom_question_to_tuple(q: dict) -> tuple:
    answers = [str(a).strip() for a in (q.get("answers") or []) if str(a).strip()]
    if len(answers) < MIN_CUSTOM_ANSWERS:
        answers = (answers + ["Antwort A", "Antwort B"])[:MIN_CUSTOM_ANSWERS]
    while len(answers) < MAX_CUSTOM_ANSWERS:
        answers.append(f"Antwort {ANSWER_LETTERS[len(answers)]}")
    answers = answers[:MAX_CUSTOM_ANSWERS]
    correct_idx = int(q.get("correct_idx", 0))
    correct_idx = max(0, min(correct_idx, len(answers) - 1))
    return (str(q.get("question", "")).strip() or "Frage?", answers, correct_idx)


def custom_quiz_to_game_questions(quiz: dict) -> list[tuple]:
    raw = quiz.get("questions") or []
    tuples = [custom_question_to_tuple(q) for q in raw if str(q.get("question", "")).strip()]
    return tuples[:MAX_CUSTOM_QUESTIONS]


def new_empty_custom_quiz(title: str = "Mein Quiz") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": new_custom_quiz_id(),
        "title": title.strip() or "Mein Quiz",
        "created_at": now,
        "updated_at": now,
        "is_draft": True,
        "questions": [],
        "time_pressure_enabled": True,
        "question_time_sec": QUESTION_TIME_SEC,
    }


def upsert_custom_quiz(state: dict, quiz: dict, mark_finished: bool = False) -> dict:
    quiz = dict(quiz)
    quiz["updated_at"] = datetime.now(timezone.utc).isoformat()
    if mark_finished and quiz.get("questions"):
        quiz["is_draft"] = False
    quizzes = get_user_custom_quizzes(state)
    replaced = False
    for i, existing in enumerate(quizzes):
        if existing.get("id") == quiz.get("id"):
            quizzes[i] = quiz
            replaced = True
            break
    if not replaced:
        quizzes.append(quiz)
    persist_user_custom_quizzes(state, quizzes)
    return quiz


def delete_custom_quiz(state: dict, quiz_id: str):
    quizzes = [q for q in get_user_custom_quizzes(state) if q.get("id") != quiz_id]
    persist_user_custom_quizzes(state, quizzes)


def custom_quiz_prize_for_number(question_num: int, planned_total: int | None = None) -> str:
    """1-based question number -> prize money if answered correctly."""
    question_num = max(1, question_num)
    total = max(question_num, planned_total or question_num, 1)
    total = min(total, len(MONEY_LEVELS))
    return MONEY_LEVELS[:total][question_num - 1]


def auto_save_editing_quiz(
    state: dict,
    title: str | None = None,
    mark_finished: bool = False,
) -> dict | None:
    """Persist the quiz being edited (draft) without manual save button."""
    quiz = state.get("editing_quiz")
    if not quiz or not state.get("current_user_email"):
        return None
    if title is not None:
        quiz["title"] = title.strip() or quiz.get("title", "Mein Quiz")
    if not mark_finished:
        quiz["is_draft"] = True
    saved = upsert_custom_quiz(state, quiz, mark_finished=mark_finished)
    state["editing_quiz"] = saved
    return saved


def start_custom_quiz_play(page: ft.Page, state: dict, quiz: dict):
    questions = custom_quiz_to_game_questions(quiz)
    if not questions:
        page.snack_bar = ft.SnackBar(content=ft.Text("Bitte mindestens eine Frage mit Text anlegen."))
        page.snack_bar.open = True
        page.update()
        return
    clear_saved_game(state)
    reset_game_timer(state)
    state["time_pressure_enabled"] = bool(quiz.get("time_pressure_enabled", True))
    state["question_time_sec"] = int(quiz.get("question_time_sec", QUESTION_TIME_SEC)) or QUESTION_TIME_SEC
    state.update({
        "money": "0 €",
        "questions_answered": 0,
        "correct": 0,
        "jokers_used": 0,
        "question_index": 0,
        "questions": questions,
        "game_finished": False,
        "custom_quiz_id": quiz.get("id"),
        "custom_quiz_title": quiz.get("title", "Eigenes Quiz"),
        "is_custom_game": True,
    })
    state.pop("saved_game", None)
    state.pop("selected_jokers", None)
    state.pop("jokers_used_ids", None)
    reset_joker_pick_state(state)
    save_current_game(state)
    launch_game_after_jokers(page, state)


# ---------- Constants ----------
MONEY_LEVELS = [
    "50 €",
    "100 €",
    "200 €",
    "300 €",
    "500 €",
    "1.000 €",
    "2.000 €",
    "4.000 €",
    "8.000 €",
    "16.000 €",
    "32.000 €",
    "64.000 €",
    "125.000 €",
    "500.000 €",
    "1.000.000 €",
]

# Answer letter colors matching the design reference
ANSWER_COLORS = ["#F4A460", "#9B59B6", "#2ECC71", "#E91E8C"]  # A=orange, B=purple, C=green, D=pink
ANSWER_LETTERS = ["A", "B", "C", "D"]

# ---------- Jokers ----------
JOKER_SELECT_COUNT = 4

JOKER_CATALOG = [
    {"id": "half", "name": "50:50", "short": "50:50", "desc": "Zwei falsche Antworten verschwinden"},
    {"id": "friend", "name": "Freund", "short": "Freund", "desc": "Frag eine andere Person"},
    {"id": "swap", "name": "Tausch", "short": "Tausch", "desc": "Neue Frage mit neuen Antworten"},
    {"id": "moderator", "name": "Moderator", "short": "Tipp", "desc": "Kleiner Moderator-Hinweis"},
    {"id": "timestop", "name": "Zeit+", "short": "+30s", "desc": "30 Sekunden extra"},
    {"id": "truefalse", "name": "W/F", "short": "W/F", "desc": "Eine Antwort testen"},
    {"id": "emoji", "name": "Emoji", "short": "Emoji", "desc": "Richtige Antwort als Emojis"},
    {"id": "audience", "name": "Publikum", "short": "Chart", "desc": "Zuschauer-Diagramm"},
    {"id": "phone", "name": "Telefon", "short": "Tel", "desc": "1 Minute zum Anrufen"},
    {"id": "wikipedia", "name": "Wikipedia", "short": "Wiki", "desc": "Kurze Definition zum Begriff"},
    {"id": "wordtip", "name": "Wort-Tipp", "short": "Wort", "desc": "Ein einzelnes Hinweis-Wort"},
]

QUESTION_TIME_SEC = 30
PHONE_JOKER_SEC = 60
FRIEND_JOKER_SEC = 60

# UI options for the timer configuration (in joker select + custom quiz editor)
QUESTION_TIME_OPTIONS = [10, 20, 30, 45, 60]

JOKER_BY_ID = {j["id"]: j for j in JOKER_CATALOG}


def get_joker(joker_id: str) -> dict | None:
    return JOKER_BY_ID.get(joker_id)


def stop_game_timer(state: dict):
    state["_timer_cancel"] = True


def reset_game_timer(state: dict):
    """Full timer reset for a new game or after game over (not for pause/resume)."""
    stop_game_timer(state)
    state.pop("_timer_active_key", None)
    state.pop("_timer_question_key", None)
    state.pop("time_left", None)
    state.pop("phone_until", None)
    state.pop("friend_until", None)
    state.pop("truefalse_mode", None)


def reset_timer_for_new_question(state: dict):
    """30 seconds for the next question in the same run."""
    stop_game_timer(state)
    state.pop("_timer_active_key", None)
    state.pop("_timer_question_key", None)
    # Keep per-game timer configuration (used for custom quizzes).
    state["time_left"] = int(state.get("question_time_sec", QUESTION_TIME_SEC))


def sync_timer_display(page: ft.Page, state: dict):
    """Update timer bar/text without rebuilding the whole screen."""
    theme = get_theme(state)
    ui = state.get("_timer_ui")
    if not ui:
        return
    now = time.time()
    phone_end = float(state.get("phone_until") or 0)
    friend_end = float(state.get("friend_until") or 0)

    question_time_sec = int(state.get("question_time_sec", QUESTION_TIME_SEC)) or QUESTION_TIME_SEC
    time_pressure_enabled = bool(state.get("time_pressure_enabled", True))

    # Joker-spezifische Countdown-Anzeige
    if friend_end > now:
        sec = max(0, int(friend_end - now))
        ui["text"].value = f"👥 {sec}"
        ui["bar"].value = min(1.0, sec / FRIEND_JOKER_SEC)
        ui["text"].color = theme["gold"]
        ui["bar"].color = theme["accent"]
        try:
            page.update()
        except Exception:
            pass
        return

    if phone_end > now:
        sec = max(0, int(phone_end - now))
        ui["text"].value = f"📞 {sec}"
        ui["bar"].value = min(1.0, sec / PHONE_JOKER_SEC)
        ui["text"].color = theme["gold"]
        ui["bar"].color = theme["accent"]
        try:
            page.update()
        except Exception:
            pass
        return

    # Aufräumen abgelaufener Joker-Countdowns
    if phone_end:
        state.pop("phone_until", None)
    if friend_end:
        state.pop("friend_until", None)

    # Zeitdruck aus -> kein Countdown, Balken bleibt voll
    if not time_pressure_enabled:
        ui["text"].value = "∞"
        ui["bar"].value = 1.0
        ui["text"].color = theme_txt(theme, "primary")
        ui["bar"].color = theme["success"]
        try:
            page.update()
        except Exception:
            pass
        return

    sec = max(0, int(state.get("time_left", question_time_sec)))
    ui["text"].value = str(sec)
    ui["bar"].value = sec / max(1, question_time_sec)
    ui["text"].color = "#C62828" if sec <= 10 else theme_txt(theme, "primary")
    ui["bar"].color = "#C62828" if sec <= 10 else theme["success"]
    try:
        page.update()
    except Exception:
        pass


def mark_joker_used(state: dict, joker_id: str):
    used = list(state.get("jokers_used_ids", []))
    if joker_id not in used:
        used.append(joker_id)
        state["jokers_used_ids"] = used
        state["jokers_used"] = state.get("jokers_used", 0) + 1
        save_current_game(state)


def generate_audience_percents(correct_idx: int, count: int = 4) -> list[int]:
    """Returns integer % for A-D summing to 100; ~70% correct is highest."""
    if count != 4:
        count = 4
    if random.random() < 0.7:
        lead = random.randint(34, 52)
        rest = 100 - lead
        others = [random.randint(5, max(8, rest // 3)) for _ in range(3)]
        s = sum(others)
        others = [max(3, int(o * rest / s)) for o in others]
        diff = 100 - lead - sum(others)
        others[0] += diff
        percents = [0, 0, 0, 0]
        percents[correct_idx] = lead
        idxs = [i for i in range(4) if i != correct_idx]
        for i, p in zip(idxs, others):
            percents[i] = p
        if sum(percents) != 100:
            percents[correct_idx] += 100 - sum(percents)
        return percents
    weights = [random.randint(8, 40) for _ in range(4)]
    total = sum(weights)
    return [max(3, int(w * 100 / total)) for w in weights]


EMOJI_BY_WORD: dict[str, str] = {
    # Länder & Städte
    "berlin": "🏙️🇩🇪", "münchen": "🍺🏔️", "hamburg": "⚓🌊", "köln": "⛪🎉", "frankfurt": "🏦🌆",
    "deutschland": "🇩🇪", "österreich": "🇦🇹🏔️", "schweiz": "🇨🇭🧀", "frankreich": "🇫🇷",
    "eiffelturm": "🗼✨", "paris": "🗼❤️", "italien": "🇮🇹🍕", "pizza": "🍕",
    "spanien": "🇪🇸💃", "england": "🇬🇧☕", "griechenland": "🇬🇷🏛️", "japan": "🇯🇵🗻",
    "tokio": "🌆🗻", "australien": "🦘🌏", "kanada": "🍁🌲", "usa": "🗽🇺🇸",
    "china": "🇨🇳🐉", "indien": "🇮🇳🐘", "brasilien": "🇧🇷🌴", "mexiko": "🇲🇽🌮",
    "rom": "🏛️🍕", "london": "🎡🇬🇧", "new york": "🗽🌆", "moskau": "🏛️❄️",
    "amsterdam": "🚲🌷", "wien": "🎵🏰", "prag": "🏰🇨🇿", "dänemark": "🇩🇰🧊",
    "schweden": "🇸🇪❄️", "norwegen": "🇳🇴🌊", "finnland": "🇫🇮🎿", "portugal": "🇵🇹🐟",
    "türkei": "🇹🇷🕌", "ägypten": "🇪🇬🏜️🔺", "russland": "🇷🇺❄️",
    "hauptstadt": "🏛️🌆",

    # Tiere
    "elefant": "🐘", "giraffe": "🦒", "spinne": "🕷️", "kuh": "🐄🥛", "schwein": "🐷",
    "schaf": "🐑🧶", "pferd": "🐴", "biene": "🐝🍯", "frosch": "🐸", "hund": "🐕", "katze": "🐈",
    "vogel": "🐦", "fisch": "🐟", "nilpferd": "🦛", "nashorn": "🦏", "löwe": "🦁",
    "tiger": "🐯", "bär": "🐻", "panda": "🐼", "delfin": "🐬", "hai": "🦈",
    "oktopus": "🐙", "krebs": "🦀", "pinguin": "🐧", "eule": "🦉", "adler": "🦅",
    "schlange": "🐍", "krokodil": "🐊", "eidechse": "🦎", "dinosaurier": "🦕",
    "maus": "🐭", "ratte": "🐀", "kaninchen": "🐇", "igel": "🦔", "fuchs": "🦊",
    "wolf": "🐺", "affe": "🐒", "gorilla": "🦍", "zebra": "🦓", "känguru": "🦘",
    "koala": "🐨", "fledermaus": "🦇", "biber": "🦫", "otter": "🦦",

    # Pflanzen & Natur
    "baum": "🌲", "blume": "🌸", "rose": "🌹", "tulpe": "🌷", "sonnenblume": "🌻",
    "gras": "🌿", "pilz": "🍄", "kaktus": "🌵", "palme": "🌴", "bambus": "🎋",
    "wald": "🌲🌳", "dschungel": "🌿🦁", "wüste": "🏜️🐪", "strand": "🏖️", "berg": "⛰️",
    "ozean": "🌊", "see": "🏞️", "fluss": "🏞️", "gletscher": "🧊🏔️",

    # Weltraum & Astronomie
    "sonne": "☀️", "mond": "🌙", "mars": "🔴🪐", "venus": "🪐💛", "jupiter": "🪐🌀",
    "saturn": "🪐💫", "merkur": "🌑", "uranus": "🪐🌊", "neptun": "🔵🪐",
    "stern": "⭐", "galaxie": "🌌", "weltraum": "🚀🌌", "mondlandung": "🌕🚀",
    "asteroid": "☄️", "komet": "☄️", "schwarzes loch": "🕳️🌌",

    # Körper & Biologie
    "herz": "❤️", "lunge": "🫁", "gehirn": "🧠", "leber": "🫀", "niere": "🫘",
    "blut": "🩸", "blutplättchen": "🩹🩸", "blutkörperchen": "🩸🧬",
    "rote blutkörperchen": "🔴🩸", "weiße blutkörperchen": "🤍🧫",
    "sauerstoff": "💨🫁", "dna": "🧬", "zelle": "🔬🧬", "nervenzellen": "🧠⚡",
    "knochen": "🦴", "muskel": "💪", "haut": "🖐️", "auge": "👁️", "ohr": "👂",
    "mund": "👄", "nase": "👃", "hand": "✋", "fußb": "🦶",

    # Chemie & Physik
    "wasser": "💧", "h2o": "💧🧪", "feuer": "🔥", "eis": "🧊", "dampf": "💨",
    "stickstoff": "🫧", "helium": "🎈", "kohlenstoff": "⬛", "eisen": "⚙️",
    "gold": "🥇✨", "silber": "🥈", "kupfer": "🔶", "atom": "⚛️", "elektron": "⚡",
    "magnetismus": "🧲", "gravitation": "🍎⬇️", "licht": "💡", "laser": "🔴💡",
    "radioaktiv": "☢️", "explosion": "💥",

    # Mathematik
    "pi": "🟠π", "primzahl": "🔢", "quadrat": "🔲", "kreis": "⭕", "dreieck": "🔺",
    "gleichung": "⚖️", "integral": "∫", "algebra": "➗",

    # Geschichte & Personen
    "napoleon": "👑⚔️", "kaiser": "👑", "einstein": "🧑‍🔬E=mc²", "goethe": "✍️📜",
    "mozart": "🎵🎼", "beethoven": "🎹🎶", "shakespeare": "🎭", "aristoteles": "📖🏛️",
    "kleopatra": "👑🐍", "kolumbus": "⛵🗺️", "galilei": "🔭🌍", "newton": "🍎⬇️",
    "hitler": "⚠️", "stalin": "⚠️", "churchill": "🎩", "kennedy": "🗽",
    "martin luther king": "✊", "darwin": "🦎🔬",
    "mittelalter": "⚔️🏰", "renaissance": "🎨🏛️", "revolution": "🔥✊",
    "weltkrieg": "⚔️💣", "krieg": "⚔️",

    # Essen & Trinken
    "brot": "🍞", "käse": "🧀", "milch": "🥛", "butter": "🧈", "ei": "🥚",
    "fleisch": "🥩", "fisch": "🐟🍽️", "gemüse": "🥦", "obst": "🍎", "apfel": "🍎",
    "banane": "🍌", "erdbeere": "🍓", "orange": "🍊", "zitrone": "🍋",
    "tomate": "🍅", "kartoffel": "🥔", "zwiebel": "🧅", "knoblauch": "🧄",
    "nudeln": "🍝", "reis": "🍚", "suppe": "🍲", "kuchen": "🎂", "schokolade": "🍫",
    "kaffee": "☕", "tee": "🍵", "bier": "🍺", "wein": "🍷", "saft": "🧃",

    # Jahreszeiten & Wetter
    "herbst": "🍂🍁", "frühling": "🌸🌱", "sommer": "☀️🏖️", "winter": "❄️⛄",
    "regen": "🌧️", "schnee": "❄️", "gewitter": "⛈️", "regenbogen": "🌈",
    "wind": "💨", "tornado": "🌪️", "nebel": "🌫️", "hitze": "🥵",

    # Transport
    "flugzeug": "✈️", "auto": "🚗", "zug": "🚆", "fahrrad": "🚲", "schiff": "🚢",
    "rakete": "🚀", "hubschrauber": "🚁", "bus": "🚌", "u-bahn": "🚇", "taxi": "🚕",
    "motorrad": "🏍️", "boot": "⛵",

    # Technologie
    "computer": "💻", "handy": "📱", "telefon": "📞", "fernseher": "📺",
    "kamera": "📷", "roboter": "🤖", "internet": "🌐", "ki": "🤖🧠",
    "algorithmus": "⚙️💡", "datenbank": "🗄️",

    # Sport
    "fußball": "⚽", "basketball": "🏀", "tennis": "🎾", "schwimmen": "🏊",
    "laufen": "🏃", "boxen": "🥊", "radfahren": "🚴", "ski": "⛷️",
    "olympia": "🏅", "marathon": "🏃🏅",

    # Kunst & Kultur
    "musik": "🎵", "klavier": "🎹", "gitarre": "🎸", "geige": "🎻", "oper": "🎭",
    "theater": "🎭", "film": "🎬", "buch": "📚", "malen": "🎨", "skulptur": "🗿",
    "tanz": "💃", "gesang": "🎤",

    # Farben
    "gelb": "🟡", "grün": "🟢", "rot": "🔴", "blau": "🔵", "schwarz": "⬛",
    "weiß": "⬜", "lila": "🟣", "orange": "🟠", "rosa": "🩷", "braun": "🟫",

    # Zahlen & Zeit
    "zeit": "⏰", "stunde": "🕐", "tag": "📅", "woche": "📆", "jahr": "🗓️",
    "sekunde": "⏱️", "minute": "⏳",
    
    # Übergreifende Kategorien
    "instrument": "🥁🎻🎺", "werkzeug": "🔨🔧", "fahrzeug": "🚗🚀⛵", "beruf": "👷🧑‍⚕️",
    "planet": "🪐🌍", "kleidung": "👕👖👗", "möbel": "🛋️🛏️", "gebäude": "🏠🏢",
    "tier": "🐾", "pflanze": "🌿", "krankheit": "🤒🦠", "sprache": "🗣️",
    "religion": "⛪🕌🕍", "waffe": "⚔️🔫", "spiel": "🎲🎮", "süßigkeit": "🍬🍫",
}


def emoji_hint_for_answer(answer: str) -> str:
    text = answer.lower().strip()
    words = [w.strip(" ,.-!?") for w in text.split()]
    found: list[str] = []
    
    # First priority: direct exact word matches
    for w in words:
        if w in EMOJI_BY_WORD and EMOJI_BY_WORD[w] not in found:
            found.append(EMOJI_BY_WORD[w])
            
    # Second priority: partial matches for longer keys
    if not found:
        for word, em in sorted(EMOJI_BY_WORD.items(), key=lambda x: -len(x[0])):
            if len(word) >= 4 and word in text and em not in found:
                found.append(em)
            if len(found) >= 3:
                break

    # Third priority: Context from Wikipedia
    if not found:
        try:
            search_url = "https://de.wikipedia.org/w/api.php?action=opensearch&search=" + requests.utils.quote(answer.strip()) + "&limit=1&format=json"
            s_resp = requests.get(search_url, timeout=3)
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                if len(s_data) >= 2 and s_data[1]:
                    best_title = s_data[1][0]
                    url = "https://de.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(best_title)
                    resp = requests.get(url, timeout=4)
                    if resp.status_code == 200:
                        extract = resp.json().get("extract", "").lower()
                        for word, em in sorted(EMOJI_BY_WORD.items(), key=lambda x: -len(x[0])):
                            if len(word) >= 4 and re.search(r'\b' + re.escape(word) + r'\b', extract) and em not in found:
                                found.append(em)
                            if len(found) >= 3:
                                break
        except Exception:
            pass

    if found:
        return "  ".join(found[:3])

    # Fallback: derive emojis from word properties
    if re.search(r"\d{4}", text):
        return "📅 🗓️ 🔢"  # looks like a year
    if re.search(r"\d", text):
        return "🔢 🧮 ➕"
    if len(text) <= 3:
        return f"🔤 ❓"  # abbreviation / short code
    # Category guessing from common syllables
    if any(w in text for w in ("burg", "stadt", "dorf", "heim")):
        return "🏙️ 🗺️ 🏘️"
    if any(w in text for w in ("berg", "stein", "fels")):
        return "⛰️ 🪨"
    if any(w in text for w in ("meer", "see", "bach", "fluss")):
        return "🌊 💧"
    if any(w in text for w in ("tier", "vieh", "wild")):
        return "🐾 🦁"
    if any(w in text for w in ("pflanz", "baum", "gras", "blatt")):
        return "🌿 🌱"
    if any(w in text for w in ("krieg", "schlacht", "soldat")):
        return "⚔️ 🏳️"
    if any(w in text for w in ("musik", "lied", "ton", "klang")):
        return "🎵 🎶"
    if any(w in text for w in ("buch", "schreib", "lese", "text")):
        return "📖 ✍️"
    return "💡 🧩 🎯"


def moderator_hint_for(question: str, options: list, correct_idx: int) -> str:
    correct = options[correct_idx] if 0 <= correct_idx < len(options) else ""
    return (
        f"Moderator: Denke an etwas mit „{correct[:3]}…“ – "
        f"die Lösung hat {len(correct)} Buchstaben."
    )


WIKIPEDIA_HINTS = {
    "biene": "Ein Insekt, das Blüten bestäubt und Honig herstellt.",
    "frosch": "Ein springendes Amphib, das oft in Teichen und Feuchtgebieten lebt.",
    "elefant": "Das größte lebende Landtier mit einem langen Rüssel.",
    "berlin": "Großstadt in Mitteleuropa mit Regierungssitz und vielen Museen.",
    "wasser": "Flüssigkeit aus Wasserstoff und Sauerstoff, lebensnotwendig für Menschen.",
    "sonne": "Der Stern im Zentrum unseres Sonnensystems, liefert Licht und Wärme.",
    "buch": "Gedruckte oder digitale Seiten zum Lesen und Lernen.",
    "auto": "Kraftfahrzeug für den Straßenverkehr mit Motor.",
    "maus": "Kleines Nagetier oder ein Computer-Eingabegerät.",
    "hund": "Haus- und Heimtier, enger Begleiter des Menschen.",
    "herbst": "Jahreszeit mit fallendem Laub zwischen Sommer und Winter.",
    "frühling": "Jahreszeit, in der Natur erwacht und es wärmer wird.",
    "herz": "Muskelorgan, das Blut durch den Körper pumpt.",
    "jupiter": "Gasriese und größter Planet unseres Sonnensystems.",
    "h2o": "Chemische Verbindung aus zwei Wasserstoff- und einem Sauerstoffatom.",
    "sauerstoff": "Gas, das für Verbrennung und Atmung wichtig ist.",
    "stickstoff": "Häufigstes Gas in der Erdatmosphäre.",
    "frankreich": "Westeuropäisches Land, bekannt für Kultur und Küche.",
    "italien": "Südeuropäisches Land mit langer Geschichte und Küche.",
    "tokio": "Großstadt und wichtiges Zentrum auf einer ostasiatischen Insel.",
    "rom": "Historische Hauptstadt eines europäischen Landes mit Kolosseum.",
    "napoleon": "Französischer Kaiser und Feldherr des frühen 19. Jahrhunderts.",
    "mozart": "Österreichischer Komponist der klassischen Epoche.",
    "einstein": "Physiker, bekannt für Relativitätstheorie und E=mc².",
    "goethe": "Deutscher Dichter der Klassik, schrieb auch Faust.",
    "flugzeug": "Luftfahrzeug mit Tragflächen für Passagier- oder Frachtverkehr.",
    "pazifik": "Größtes Meer der Erde, erstreckt sich zwischen Asien und Amerika.",
}

WORD_TIP_HINTS = {
    "biene": "Bestäubung",
    "frosch": "Amphib",
    "elefant": "Rüssel",
    "berlin": "Regierung",
    "wasser": "Molekül",
    "sonne": "Fusion",
    "buch": "Literatur",
    "auto": "Motor",
    "maus": "Nagetier",
    "hund": "Haustier",
    "katze": "Schnurren",
    "vogel": "Gefieder",
    "fisch": "Kiemen",
    "herbst": "Laub",
    "frühling": "Knospung",
    "herz": "Puls",
    "jupiter": "Gasriese",
    "sauerstoff": "Atmung",
    "h2o": "Lösungsmittel",
    "frankreich": "Europa",
    "italien": "Mediterran",
    "tokio": "Metropole",
    "rom": "Antike",
    "mozart": "Komponist",
    "einstein": "Relativität",
    "goethe": "Dichtung",
    "flugzeug": "Aviation",
    "spinne": "Arachnid",
    "kuh": "Weidetier",
    "gelb": "Spektrum",
    "grün": "Chlorophyll",
    # Übergreifende Kategorien
    "instrument": "Musikgerät", "werkzeug": "Hilfsmittel", "fahrzeug": "Verkehrsmittel",
    "beruf": "Tätigkeit", "planet": "Himmelskörper", "kleidung": "Textil",
    "möbel": "Einrichtung", "gebäude": "Bauwerk", "tier": "Lebewesen",
    "pflanze": "Flora", "krankheit": "Symptom", "sprache": "Kommunikation",
}

QUESTION_WORD_TIPS = [
    (("hauptstadt", "stadt", "land"), "Stadt"),
    (("tier", "beine", "summt", "mensch"), "Tier"),
    (("farbe", "mischt"), "Farbe"),
    (("jahr", "monat", "tag", "stunde", "woche", "jahreszeit"), "Zeit"),
    (("zahl", "viele", "wie viel", "wurzel", "gleichung"), "Zahl"),
    (("organ", "körper", "zähne", "knochen"), "Körper"),
    (("planet", "mond", "sonne", "himmel"), "Planet"),
    (("chem", "element", "formel", "gas"), "Element"),
    (("schrieb", "malte", "oper", "drama"), "Autor"),
    (("krieg", "mauer", "kaiser", "jahr wurde"), "Geschichte"),
    (("transport", "transportieren", "fliegt", "fährt", "sauerstoff"), "Blut"),
    (("meer", "ozean", "graben"), "Ozean"),
]


def wikipedia_definition(term: str) -> str:
    """
    Fetches a short extract from the German Wikipedia using OpenSearch API to find the best title first.
    """
    key = term.strip().lower()

    # 1. Try Wikipedia API (German)
    try:
        # First, search for the best matching article title
        search_url = "https://de.wikipedia.org/w/api.php?action=opensearch&search=" + requests.utils.quote(term.strip()) + "&limit=1&format=json"
        s_resp = requests.get(search_url, timeout=3)
        if s_resp.status_code == 200:
            s_data = s_resp.json()
            if len(s_data) >= 2 and s_data[1]:
                best_title = s_data[1][0]
                base_title = best_title.split("(")[0].strip()
                
                # Get the summary for the exact title
                url = "https://de.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(best_title)
                resp = requests.get(url, timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    extract: str = data.get("extract", "")
                    if extract and len(extract) > 20:
                        # Replace occurrences of the answer to avoid spoiling
                        for w in [term.strip(), term.strip().capitalize(), best_title, best_title.capitalize(), base_title, base_title.capitalize()]:
                            if w and len(w) > 3 and w in extract:
                                extract = extract.replace(w, "___")
                        return extract[:300].rsplit(" ", 1)[0] + " …"
    except Exception:
        pass

    # 2. Local fallback
    for hint_key, text in WIKIPEDIA_HINTS.items():
        if hint_key in key:
            return text

    return (
        "Ein Begriff aus Allgemeinwissen – nähere Informationen findest du "
        "in Lexika und Enzyklopädien (z. B. Wikipedia)."
    )


def word_tip_for(term: str, question: str = "") -> str:
    key = term.strip().lower()
    for hint_key, word in WORD_TIP_HINTS.items():
        if hint_key in key:
            return word
    q = question.lower()
    for keys, tip in QUESTION_WORD_TIPS:
        if any(k in q for k in keys):
            return tip
    if "hauptstadt" in q or "stadt" in q:
        return "Hauptstadt"
    if "farbe" in q:
        return "Farbkombination"
    if re.search(r"\d", key):
        return "Zahl"

    # Wenn kein passender Hinweis greifbar ist, geben wir deterministisch
    # ein anderes "Hinweiswort" zurück (statt immer das gleiche).
    fallback_words = list(dict.fromkeys(list(WORD_TIP_HINTS.values()) + [t for _, t in QUESTION_WORD_TIPS]))
    if fallback_words:
        return fallback_words[abs(hash(key)) % len(fallback_words)]
    return "Hinweis"


def swap_question_at_index(state: dict) -> bool:
    idx = state["question_index"]
    used = {str(state["questions"][i][0]).strip().lower() for i in range(len(state["questions"]))}
    if state.get("is_custom_game"):
        pool = list(state["questions"])
        random.shuffle(pool)
        for cand in pool:
            if str(cand[0]).strip().lower() not in used or len(pool) <= 1:
                state["questions"][idx] = cand
                return True
        return False
    age = state.get("player_age", "mid")
    bank = build_level_question_bank(age)
    level_idx = min(idx, len(bank) - 1)
    candidates = list(bank[level_idx])
    random.shuffle(candidates)
    for cand in candidates:
        key = str(cand[0]).strip().lower()
        if key not in used:
            state["questions"][idx] = cand
            return True
    if candidates:
        state["questions"][idx] = candidates[0]
        return True
    return False


def set_game_modal(state: dict, panel: ft.Control):
    """Wrap panel in a draggable overlay that cannot leave the screen."""
    state["_modal_overlay"] = _DraggableModal(panel)


def clear_game_modal(state: dict):
    state.pop("_modal_overlay", None)


def _DraggableModal(panel: ft.Control) -> ft.Stack:
    """
    Full-screen darkened overlay whose inner panel can be dragged.
    The panel stays within the visible screen area and cannot be dragged off-screen.
    """
    PANEL_W = 400
    pos = {"left": -1.0, "top": -1.0}

    handle = ft.Container(
        content=ft.Text("⠿  verschieben", size=10, color="#AAAAAA", text_align="center"),
        height=22,
        bgcolor="#22222244",
        border_radius=ft.BorderRadius(12, 12, 0, 0),
        alignment=ft.Alignment(0, 0),
        width=PANEL_W,
    )

    card = ft.Column(
        [
            handle,
            ft.Container(content=panel, width=PANEL_W),
        ],
        spacing=0,
    )

    box = ft.Container(content=card, border_radius=16, width=PANEL_W)
    
    # We will wrap only the handle with the GestureDetector to move it!
    # Flet's drag works by tracking the drag on the handle.
    
    drag_container = ft.Container(content=box, left=0, top=0)

    def on_pan_update(e):
        try:
            page = e.control.page
            if page is None: return
            pw = float(getattr(page, "width", None) or 1100)
            ph = float(getattr(page, "height", None) or 720)
            
            if pos["left"] < 0:
                pos["left"] = drag_container.left
                pos["top"] = drag_container.top

            pos["left"] += e.delta_x
            pos["top"] += e.delta_y

            # Constrain to visible screen bounds
            pos["left"] = max(0, min(pw - PANEL_W, pos["left"]))
            pos["top"] = max(0, min(ph - 150, pos["top"]))

            drag_container.left = pos["left"]
            drag_container.top = pos["top"]
            drag_container.update()
        except Exception:
            pass

    gesture = ft.GestureDetector(
        content=drag_container,
        on_pan_update=on_pan_update,
        mouse_cursor=ft.MouseCursor.MOVE,
    )
    
    # We need to center the modal initially. We can do this in the build or via alignment.
    # Since we're using Stack with absolute positioning, we'll let it be centered initially via Stack properties? No, Stack left/top are absolute.
    # Let's initialize pos and center it initially via window size (assuming typical 1100x720 if not available)
    drag_container.left = (1100 - PANEL_W) / 2
    drag_container.top = (720 - 340) / 2

    backdrop = ft.Container(expand=True, bgcolor="#00000088")
    return ft.Stack([backdrop, gesture], expand=True)


async def _flash_joker_activation(page: ft.Page, theme: dict):
    """Brief gold flash when a joker is used."""
    flash = ft.Container(bgcolor="#55FFD700", expand=True)
    page.overlay.append(flash)
    try:
        page.update()
    except Exception:
        pass
    await asyncio.sleep(0.2)
    if flash in page.overlay:
        page.overlay.remove(flash)
    try:
        page.update()
    except Exception:
        pass


def show_game_message_with_body(page: ft.Page, state: dict, title: str, body_ctrl: ft.Control, theme: dict):
    """Like show_game_message but accepts a pre-built body control (allows async updating)."""
    def close(e=None):
        clear_game_modal(state)
        state.pop("truefalse_mode", None)
        render_game_screen(page, state)

    set_game_modal(
        state,
        ft.Container(
            content=ft.Column([
                ft.Text(title, size=20, weight="bold", color=theme_txt(theme, "primary"), text_align="center"),
                body_ctrl,
                ft.Container(height=8),
                _game_menu_button("OK", close, theme["accent"], width=160),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            bgcolor=theme["panel"],
            border_radius=16,
            padding=24,
            border=ft.border.Border.all(2, theme["gold"]),
            width=360,
        ),
    )
    render_game_screen(page, state)


def show_game_message(page: ft.Page, state: dict, title: str, body: str, theme: dict):
    body_ctrl = ft.Text(body, size=14, color=theme_txt(theme, "secondary"), text_align="center")
    show_game_message_with_body(page, state, title, body_ctrl, theme)


def _show_joker_countdown_dialog(
    page: ft.Page,
    state: dict,
    theme: dict,
    title: str,
    total_sec: int,
    until_key: str,
):
    """
    Shows a live countdown dialog in page.overlay.
    The user can close it early with a button.
    Automatically closes when time runs out.
    """
    countdown_text = ft.Text(
        str(total_sec),
        size=56,
        weight="bold",
        color=theme.get("gold", "#FFD700"),
        text_align="center",
    )
    subtitle = ft.Text(
        "Du kannst jetzt anrufen / fragen!",
        size=14,
        color="#CCCCCC",
        text_align="center",
    )

    dialog_container = ft.Container(
        content=ft.Column(
            [
                ft.Text(title, size=20, weight="bold", color="white", text_align="center"),
                subtitle,
                ft.Container(height=8),
                countdown_text,
                ft.Container(height=12),
                ft.ElevatedButton(
                    "Fertig – weiter spielen",
                    on_click=lambda e: close_dialog(),
                    bgcolor=theme.get("accent", "#C00"),
                    color="white",
                    width=220,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        bgcolor=theme.get("panel", "#1A1A1A"),
        border_radius=18,
        padding=28,
        border=ft.border.Border.all(2, theme.get("gold", "#FFD700")),
        width=340,
    )

    overlay_container = ft.Container(
        content=ft.Container(
            content=dialog_container,
            alignment=ft.Alignment(0, 0),
            expand=True,
            bgcolor="#00000088",
        ),
        expand=True,
    )

    overlay_ref = [overlay_container]

    def close_dialog():
        try:
            if overlay_ref[0] in page.overlay:
                page.overlay.remove(overlay_ref[0])
        except Exception:
            pass
        state.pop(until_key, None)
        sync_timer_display(page, state)
        render_game_screen(page, state)
        try:
            page.update()
        except Exception:
            pass

    async def _tick():
        while True:
            await asyncio.sleep(1)
            if overlay_ref[0] not in page.overlay:
                break
            remaining = int(state.get(until_key, 0) - time.time())
            if remaining <= 0:
                close_dialog()
                break
            countdown_text.value = str(remaining)
            color = "#C62828" if remaining <= 10 else theme.get("gold", "#FFD700")
            countdown_text.color = color
            try:
                countdown_text.update()
            except Exception:
                break

    page.overlay.append(overlay_container)
    page.update()
    asyncio.ensure_future(_tick())


def activate_joker(page: ft.Page, state: dict, joker_id: str, ctx: dict):
    if joker_id in state.get("jokers_used_ids", []):
        return
    # Joker sollen immer einen evtl. laufenden Testmodus "ausknipsen".
    state.pop("truefalse_mode", None)
    theme = ctx["theme"]
    correct_idx = ctx["correct_idx"]
    options = ctx["options"]
    question = ctx["question"]
    answer_buttons = ctx["answer_buttons"]
    hidden = set(state.get("hidden_answers", []))

    if joker_id == "half":
        wrong = [i for i in range(len(options)) if i != correct_idx]
        random.shuffle(wrong)
        for i in wrong[:2]:
            hidden.add(i)
            if i < len(answer_buttons):
                answer_buttons[i].visible = False
        state["hidden_answers"] = list(hidden)
        mark_joker_used(state, joker_id)
        render_game_screen(page, state)
        return

    if joker_id == "friend":
        mark_joker_used(state, joker_id)
        state["friend_until"] = time.time() + FRIEND_JOKER_SEC
        sync_timer_display(page, state)
        _show_joker_countdown_dialog(page, state, theme, "👥 Frag einen Freund", FRIEND_JOKER_SEC, "friend_until")
        return

    if joker_id == "swap":
        if swap_question_at_index(state):
            mark_joker_used(state, joker_id)
            reset_timer_for_new_question(state)   # treat new question like a fresh start
            render_game_screen(page, state)
        return

    if joker_id == "moderator":
        mark_joker_used(state, joker_id)
        show_game_message(page, state, "Moderator-Tipp", moderator_hint_for(question, options, correct_idx), theme)
        return

    if joker_id == "timestop":
        # Mark used first (prevents double-tap race) then add time
        mark_joker_used(state, joker_id)
        state["time_left"] = int(state.get("time_left", QUESTION_TIME_SEC)) + 30
        save_current_game(state)
        render_game_screen(page, state)   # rebuild joker bar so button greys out immediately
        return

    if joker_id == "wikipedia":
        mark_joker_used(state, joker_id)
        term = options[correct_idx]
        body_ref = ft.Text("⏳ Lade Wikipedia-Artikel …", size=14, color=theme_txt(theme, "secondary"), text_align="center")
        show_game_message_with_body(page, state, "Wikipedia", body_ref, theme)

        async def _load_wiki():
            loop = asyncio.get_event_loop()
            try:
                definition = await loop.run_in_executor(None, lambda: wikipedia_definition(term))
            except Exception:
                definition = "Kein Wikipedia-Eintrag gefunden."
            body_ref.value = definition
            try:
                body_ref.update()
            except Exception:
                pass

        asyncio.ensure_future(_load_wiki())
        return

    if joker_id == "wordtip":
        mark_joker_used(state, joker_id)
        word = word_tip_for(options[correct_idx], question)
        show_game_message(
            page, state,
            "Wort-Tipp",
            f"Denke an das Wort: „{word}“",
            theme,
        )
        return

    if joker_id == "truefalse":
        mark_joker_used(state, joker_id)
        state["truefalse_mode"] = True
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Tippe eine Antwort zum Testen – danach kannst du normal weiterwählen."),
            duration=3500,
        )
        page.snack_bar.open = True
        page.update()
        return

    if joker_id == "emoji":
        mark_joker_used(state, joker_id)
        term = options[correct_idx]
        body_ref = ft.Text("⏳ Suche Emojis …", size=24, color=theme_txt(theme, "secondary"), text_align="center")
        show_game_message_with_body(page, state, "Emoji-Joker", body_ref, theme)

        async def _load_emoji():
            loop = asyncio.get_event_loop()
            try:
                em = await loop.run_in_executor(None, lambda: emoji_hint_for_answer(term))
            except Exception:
                em = "💡 🧩 🎯"
            body_ref.value = f"Die richtige Antwort in Emojis:\n\n{em}"
            try:
                body_ref.update()
            except Exception:
                pass

        asyncio.ensure_future(_load_emoji())
        return

    if joker_id == "audience":
        mark_joker_used(state, joker_id)
        percents = generate_audience_percents(correct_idx)
        bars = []
        for i, letter in enumerate(ANSWER_LETTERS[: len(options)]):
            p = percents[i]
            bars.append(
                ft.Row([
                    ft.Text(letter, width=24, weight="bold", color=theme["gold"]),
                    ft.Container(
                        width=max(4, int(2.4 * p)),
                        height=18,
                        bgcolor=theme["success"] if i == correct_idx else theme["accent"],
                        border_radius=4,
                    ),
                    ft.Text(f"{p}%", size=12, color=theme_txt(theme, "secondary")),
                ], spacing=8)
            )

        def close_audience(e=None):
            clear_game_modal(state)
            state.pop("truefalse_mode", None)
            render_game_screen(page, state)

        set_game_modal(
            state,
            ft.Container(
                content=ft.Column([
                    ft.Text("Zuschauer-Joker", size=20, weight="bold", color="white"),
                    ft.Text(question[:100], size=13, color="#CCCCCC", text_align="center"),
                    *bars,
                    _game_menu_button("OK", close_audience, theme["accent"], width=140),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                bgcolor=theme["panel"],
                border_radius=16,
                padding=20,
                border=ft.border.Border.all(2, theme["border"]),
                width=400,
            ),
        )
        render_game_screen(page, state)
        return

    if joker_id == "phone":
        mark_joker_used(state, joker_id)
        state["phone_until"] = time.time() + PHONE_JOKER_SEC
        try:
            page.launch_url("tel:")
        except Exception:
            pass
        sync_timer_display(page, state)
        _show_joker_countdown_dialog(page, state, theme, "📞 Telefon-Joker", PHONE_JOKER_SEC, "phone_until")
        return


def reset_joker_pick_state(state: dict):
    state.pop("joker_pick_buffer", None)
    state.pop("jokers_confirmed", None)


def build_joker_tile(
    joker: dict,
    theme: dict,
    *,
    selected: bool = False,
    used: bool = False,
    size: int = 56,
    on_click=None,
    show_name: bool = True,
) -> ft.Container:
    is_nexus = theme.get("label") == "Neon Nexus"
    
    if is_nexus:
        border_w = 3 if selected and not used else 2
        border_color = "#D946EF" if selected and not used else "#0EA5E9"
        bgcolor = "#1E293B" if not used else "#47556944"
        if used:
            border_color = "#94A3B844"
            on_click = None
    else:
        border_w = 3 if selected and not used else 1
        border_color = theme["gold"] if selected and not used else theme["border"]
        bgcolor = theme["accent"] if selected and not used else (theme.get("question_bg", "#FFFFFF") if not used else "#55555588")
        if used:
            border_color = "#444444"
            on_click = None  # disable click entirely
        
    label = joker.get("short", joker.get("name", "?"))
    font_size = 8 if size <= 50 else (9 if size <= 58 else 10)
    
    if is_nexus:
        text_color = "#FFFFFF" if not used else "#94A3B8"
    else:
        text_color = theme["question_text"] if not used else "#777777"
        
    content = ft.Text(
        label,
        size=font_size,
        weight="bold" if selected else "normal",
        color=text_color,
        text_align=ft.TextAlign.CENTER,
        max_lines=2,
        no_wrap=False,
    ) if show_name else ft.Container()

    tile = ft.Container(
        content=content,
        width=size,
        height=size,
        border_radius=12,
        bgcolor=bgcolor,
        border=ft.border.Border.all(border_w, border_color),
        alignment=ft.Alignment(0, 0),
        opacity=0.35 if used else 1.0,
        shadow=ft.BoxShadow(blur_radius=14, color="#60FFD700") if selected and not used else None,
        tooltip=joker.get("desc", ""),
    )
    if on_click is None:
        return tile
    return ft.GestureDetector(
        on_tap=on_click,
        mouse_cursor=ft.MouseCursor.CLICK,
        content=tile,
    )


def build_joker_slot_row(
    picked_ids: list[str],
    theme: dict,
    *,
    slot_size: int = 58,
    empty_label: str = "?",
    on_joker_click=None,
) -> ft.Row:
    slots = []
    for i in range(JOKER_SELECT_COUNT):
        if i < len(picked_ids):
            jid = picked_ids[i]
            joker = get_joker(jid)
            if joker:
                slots.append(
                    build_joker_tile(
                        joker,
                        theme,
                        selected=True,
                        size=slot_size,
                        show_name=True,
                        on_click=(lambda e, j=jid: on_joker_click(j)) if on_joker_click else None,
                    )
                )
                continue
        slots.append(
            ft.Container(
                content=ft.Text(empty_label, size=18, color=theme_txt(theme, "muted"), weight="bold"),
                width=slot_size,
                height=slot_size,
                border_radius=12,
                bgcolor=theme.get("question_bg", "#FFFFFF"),
                border=ft.border.Border.all(2, theme["border"]),
                alignment=ft.Alignment(0, 0),
            )
        )
    return ft.Row(slots, spacing=10, alignment=ft.MainAxisAlignment.CENTER)


def build_game_joker_bar(page: ft.Page, state: dict, theme: dict, ctx: dict | None = None) -> ft.Control:
    """Separate white row with the 4 chosen jokers."""
    selected = state.get("selected_jokers", [])[:JOKER_SELECT_COUNT]
    used_ids = set(state.get("jokers_used_ids", []))

    def on_joker_tap(joker_id: str):
        if not ctx:
            return
        if joker_id in used_ids:
            return

        async def run_joker():
            await _flash_joker_activation(page, theme)
            activate_joker(page, state, joker_id, ctx)

        page.run_task(run_joker)

    chips = []
    for jid in selected:
        joker = get_joker(jid)
        if not joker:
            continue
        chips.append(
            build_joker_tile(
                joker,
                theme,
                selected=True,
                used=jid in used_ids,
                size=60,
                on_click=lambda e, j=jid: on_joker_tap(j),
                show_name=True,
            )
        )
    while len(chips) < JOKER_SELECT_COUNT:
        chips.append(
            ft.Container(
                width=60,
                height=60,
                border_radius=12,
                bgcolor=theme.get("question_bg", "#FFFFFF"),
                border=ft.border.Border.all(1, theme["border"]),
            )
        )

    return ft.Row(chips, spacing=8, alignment=ft.MainAxisAlignment.CENTER)


def _apply_joker_selection_and_start(state: dict, picked_ids: list[str], on_start):
    state["selected_jokers"] = list(picked_ids)
    state["jokers_used_ids"] = []
    state["jokers_confirmed"] = True
    state.pop("joker_pick_buffer", None)
    clear_game_modal(state)
    state.pop("_timer_active_key", None)
    save_current_game(state)
    on_start()


def show_joker_confirm_screen(page: ft.Page, state: dict, picked_ids: list[str], on_start):
    """Full-screen confirm (works on web where AlertDialog often fails)."""
    theme = get_theme(state)

    def yes(e):
        _apply_joker_selection_and_start(state, picked_ids, on_start)

    def no(e):
        show_joker_selection(page, state, on_start)

    chips = ft.Row(
        [
            build_joker_tile(get_joker(jid), theme, selected=True, size=64)
            for jid in picked_ids
            if get_joker(jid)
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=12,
        wrap=True,
    )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Joker bestätigen", size=28, weight="bold", color="white", text_align="center"),
                ft.Text(
                    "Möchtest du diese Joker auswählen?",
                    size=16,
                    text_align="center",
                    color=theme_txt(theme, "secondary"),
                ),
                ft.Container(height=12),
                ft.Container(
                    content=chips,
                    bgcolor=theme["panel"],
                    border_radius=16,
                    padding=20,
                    border=ft.border.Border.all(2, theme["border"]),
                ),
                ft.Container(height=16),
                ft.Row([
                    _game_menu_button("Nein", no, theme["danger"]),
                    _game_menu_button("Ja", yes, theme["success"]),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
            ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
            ),
        )
    )
    page.update()


def show_joker_selection(page: ft.Page, state: dict, on_start):
    """Pick 4 jokers from catalog, confirm, then start the game."""
    theme = get_theme(state)
    pick = list(state.get("joker_pick_buffer", []))
    state.setdefault("time_pressure_enabled", True)
    state.setdefault("question_time_sec", QUESTION_TIME_SEC)

    def on_time_pressure_change(e):
        state["time_pressure_enabled"] = bool(e.control.value)
        rebuild()

    def on_question_time_change(e):
        try:
            state["question_time_sec"] = int(e.control.value)
        except Exception:
            state["question_time_sec"] = QUESTION_TIME_SEC
        rebuild()

    state.setdefault("jokers_enabled", True)

    def on_jokers_enabled_change(e):
        state["jokers_enabled"] = bool(e.control.value)
        rebuild()

    def rebuild():
        show_joker_selection(page, state, on_start)

    def toggle_joker(joker_id: str):
        if joker_id in pick:
            pick.remove(joker_id)
        elif len(pick) < JOKER_SELECT_COUNT:
            pick.append(joker_id)
        state["joker_pick_buffer"] = pick
        rebuild()

    def on_check(e):
        if not state.get("jokers_enabled", True):
            _apply_joker_selection_and_start(state, [], on_start)
            return

        current = list(state.get("joker_pick_buffer", []))
        if len(current) == 0:
            _apply_joker_selection_and_start(state, [], on_start)
            return

        if len(current) != JOKER_SELECT_COUNT:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(
                    f"Bitte genau {JOKER_SELECT_COUNT} Joker auswählen ({len(current)}/{JOKER_SELECT_COUNT}), oder gar keinen."
                ),
            )
            page.snack_bar.open = True
            page.update()
            return
        show_joker_confirm_screen(page, state, current, on_start)

    def on_back(e):
        reset_joker_pick_state(state)
        if state.get("is_custom_game") or state.get("custom_quiz_id"):
            show_custom_quiz_hub(page, state)
        else:
            show_game_start_menu(page, state, get_saved_game_for_state(state))

    catalog_tiles = []
    for joker in JOKER_CATALOG:
        is_sel = joker["id"] in pick
        disabled = len(pick) >= JOKER_SELECT_COUNT and not is_sel
        catalog_tiles.append(
            build_joker_tile(
                joker,
                theme,
                selected=is_sel,
                size=62,
                on_click=None if disabled else (lambda e, jid=joker["id"]: toggle_joker(jid)),
                show_name=True,
            )
        )

    check_enabled = len(pick) == JOKER_SELECT_COUNT
    check_btn = ft.Container(
        content=ft.Text("✓", size=28, weight="bold", color="white" if check_enabled else "#888888"),
        width=58,
        height=58,
        border_radius=12,
        bgcolor=theme["success"] if check_enabled else "#555555",
        alignment=ft.Alignment(0, 0),
        on_click=on_check,
        ink=True,
        border=ft.border.Border.all(3, theme["gold"] if check_enabled else theme["border"]),
    )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Wähle deinen Joker", size=28, weight="bold", color="white", text_align="center"),
                ft.Text(
                    f"Tippe {JOKER_SELECT_COUNT} Joker an (oben oder unten) · erneut tippen zum Abwählen",
                    size=14,
                    color=theme_txt(theme, "secondary"),
                    text_align="center",
                ),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Checkbox(
                                        label="Timer aktivieren",
                                        value=bool(state.get("time_pressure_enabled", True)),
                                        on_change=on_time_pressure_change,
                                        fill_color=theme["accent"],
                                        check_color="white",
                                        label_style=ft.TextStyle(color=theme_txt(theme, "secondary"), size=13),
                                    ),
                                    ft.Container(width=20),
                                    ft.Checkbox(
                                        label="Joker aktivieren",
                                        value=bool(state.get("jokers_enabled", True)),
                                        on_change=on_jokers_enabled_change,
                                        fill_color=theme["accent"],
                                        check_color="white",
                                        label_style=ft.TextStyle(color=theme_txt(theme, "secondary"), size=13),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                            ft.Container(height=6),
                            ft.Row(
                                [
                                    ft.Text("Sekunden pro Frage:", size=13, color=theme_txt(theme, "secondary")),
                                    (lambda: (
                                        d := ft.Dropdown(
                                            options=[ft.dropdown.Option(str(v)) for v in QUESTION_TIME_OPTIONS],
                                            value=str(int(state.get("question_time_sec", QUESTION_TIME_SEC))),
                                            width=120,
                                        ),
                                        setattr(d, 'on_change', lambda e: on_question_time_change(e)),
                                        d
                                    )[-1])() if bool(state.get("time_pressure_enabled", True)) else ft.Text(
                                        "Timer aus – kein Countdown",
                                        size=13,
                                        color=theme_txt(theme, "secondary"),
                                        weight="bold",
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=10,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=theme["panel"],
                    border_radius=14,
                    padding=12,
                    border=ft.border.Border.all(2, theme["border"]),
                ),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Row([
                        build_joker_slot_row(
                            pick, theme, slot_size=58, on_joker_click=toggle_joker,
                        ),
                        check_btn,
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=14),
                    bgcolor=theme["panel"],
                    border_radius=14,
                    padding=16,
                    border=ft.border.Border.all(2, theme["border"]),
                    visible=state.get("jokers_enabled", True),
                ) if state.get("jokers_enabled", True) else ft.Container(
                    content=ft.ElevatedButton("Start ohne Joker", on_click=on_check, style=ft.ButtonStyle(bgcolor=theme["success"], color="white")),
                    padding=20,
                ),
                ft.Text("Deine Auswahl", size=13, color=theme["gold"], weight="bold", visible=state.get("jokers_enabled", True)),
                ft.Container(
                    content=ft.Row(
                        catalog_tiles,
                        wrap=True,
                        spacing=10,
                        run_spacing=10,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    width=520,
                    padding=10,
                    visible=state.get("jokers_enabled", True),
                ),
                ft.TextButton("← Zurück", on_click=on_back, style=ft.ButtonStyle(color="white")),
            ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
        )
    )
    page.update()


def launch_game_after_jokers(page: ft.Page, state: dict):
    """Show joker picker for new games; resume skips if already chosen."""
    valid_ids = set(JOKER_BY_ID.keys())
    state["selected_jokers"] = [j for j in state.get("selected_jokers", []) if j in valid_ids]
    if not state.get("questions"):
        page.snack_bar = ft.SnackBar(content=ft.Text("Keine Fragen geladen. Bitte Spiel neu starten."))
        page.snack_bar.open = True
        page.update()
        return
    if len(state.get("selected_jokers", [])) == JOKER_SELECT_COUNT:
        show_next_question(page, state)
        return
    reset_joker_pick_state(state)
    show_joker_selection(page, state, lambda: show_next_question(page, state))


# ---------- Question Data ----------
EASY_QUESTIONS = [
    ("Wie heißt die Hauptstadt von Deutschland?", ["Berlin", "München", "Hamburg", "Köln"], 0),
    ("Wie viele Beine hat eine Spinne?", ["6", "8", "10", "4"], 1),
    ("Welches Tier ist das größte Landtier der Welt?", ["Giraffe", "Nashorn", "Elefant", "Nilpferd"], 2),
    ("Welche Farbe hat eine reife Banane?", ["Grün", "Rot", "Blau", "Gelb"], 3),
    ("Wie viele Monate hat ein Jahr?", ["10", "11", "12", "13"], 2),
    ("Was ist 5 × 5?", ["20", "25", "30", "35"], 1),
    ("Welches Tier macht 'Muh'?", ["Schwein", "Schaf", "Kuh", "Pferd"], 2),
    ("Wie viele Tage hat eine Woche?", ["5", "6", "7", "8"], 2),
    ("In welchem Land liegt der Eiffelturm?", ["England", "Italien", "Spanien", "Frankreich"], 3),
    ("Welche Jahreszeit kommt nach dem Winter?", ["Sommer", "Herbst", "Frühling", "Winter"], 2),
    ("Welches Organ pumpt Blut durch den Körper?", ["Herz", "Lunge", "Magen", "Gehirn"], 0),
    ("Wie viele Zähne hat ein erwachsener Mensch normalerweise?", ["32", "28", "36", "24"], 0),
    ("Welcher Himmelskörper leuchtet tagsüber am Himmel?", ["Sonne", "Mond", "Mars", "Venus"], 0),
    ("Welcher Tag kommt nach dem Freitag?", ["Samstag", "Sonntag", "Montag", "Donnerstag"], 0),
    ("Was ist das Gegenteil von 'heiß'?", ["Kalt", "Warm", "Nass", "Trocken"], 0),
    ("Wie heißt die Flüssigkeit in Bäumen?", ["Harz", "Saft", "Wasser", "Milch"], 1),
    ("Welches Transportmittel fliegt in der Luft?", ["Flugzeug", "Auto", "Zug", "Fahrrad"], 0),
    ("Wie viele Stunden hat ein Tag?", ["24", "12", "48", "30"], 0),
    ("Welche Farbe erhält man, wenn man Blau und Gelb mischt?", ["Grün", "Rot", "Orange", "Lila"], 0),
    ("Aus welchem Land stammt die Pizza?", ["Italien", "Spanien", "Frankreich", "Griechenland"], 0),
]

MEDIUM_QUESTIONS = [
    ("Welches Element hat das chemische Symbol 'O'?", ["Gold", "Sauerstoff", "Silber", "Kohlenstoff"], 1),
    ("Wer schrieb 'Die Blechtrommel'?", ["Günter Grass", "Heinrich Heine", "Thomas Mann", "Bertolt Brecht"], 0),
    ("Wie viele Knochen hat ein erwachsener Mensch?", ["106", "156", "206", "256"], 2),
    ("Wann wurde die Berliner Mauer gebaut?", ["1951", "1961", "1971", "1981"], 1),
    ("Was ist die Hauptstadt von Japan?", ["Peking", "Seoul", "Tokio", "Bangkok"], 2),
    ("Welcher Planet ist der größte im Sonnensystem?", ["Saturn", "Jupiter", "Uranus", "Neptun"], 1),
    ("Wie lautet die chemische Formel für Wasser?", ["CO2", "NaCl", "H2O", "O2"], 2),
    ("In welchem Jahr begann der Erste Weltkrieg?", ["1912", "1914", "1916", "1918"], 1),
    ("Wer malte die Sixtinische Kapelle?", ["Leonardo da Vinci", "Raffael", "Michelangelo", "Botticelli"], 2),
    ("Was ist die Wurzel aus 144?", ["10", "11", "12", "13"], 2),
    ("Wie viele Bundesländer hat Deutschland?", ["16", "12", "14", "18"], 0),
    ("Wer schrieb das Drama 'Faust'?", ["Johann Wolfgang von Goethe", "Friedrich Schiller", "Gotthold Ephraim Lessing", "Heinrich Heine"], 0),
    ("Wie heißt das größte Meer der Erde?", ["Pazifischer Ozean", "Atlantischer Ozean", "Indischer Ozean", "Arktischer Ozean"], 0),
    ("Welches ist das leichteste chemische Element?", ["Wasserstoff", "Helium", "Lithium", "Sauerstoff"], 0),
    ("In welcher Stadt steht das Kolosseum?", ["Rom", "Athen", "Paris", "Mailand"], 0),
    ("Welches Land grenzt im Norden an Deutschland?", ["Dänemark", "Polen", "Tschechien", "Österreich"], 0),
    ("Wie viele Zähne hat ein Milchgebiss?", ["20", "24", "28", "32"], 0),
    ("Wer war der erste Mensch auf dem Mond?", ["Neil Armstrong", "Buzz Aldrin", "Yuri Gagarin", "Michael Collins"], 0),
    ("Welches Organ im menschlichen Körper entgiftet?", ["Leber", "Niere", "Milz", "Lunge"], 0),
    ("Aus welcher Pflanze wird Tequila hergestellt?", ["Agave", "Kaktus", "Zuckerrohr", "Mais"], 0),
]

HARD_QUESTIONS = [
    ("Was ist die Lösung der Gleichung x² - 4 = 0?", ["x=2", "x=-2", "x=±2", "x=4"], 2),
    ("Welches Land hat die meisten olympischen Goldmedaillen gewonnen?", ["USA", "Sowjetunion", "Deutschland", "Großbritannien"], 0),
    ("In welchem Jahr wurde das Relativitätsprinzip von Einstein veröffentlicht?", ["1900", "1905", "1910", "1915"], 1),
    ("Was ist das Lichtjahr?", ["Zeit", "Geschwindigkeit", "Masse", "Länge"], 3),
    ("Wie viele Primzahlen gibt es zwischen 1 und 100?", ["20", "25", "27", "30"], 1),
    ("Wer entwickelte die Quantenmechanik zusammen mit Bohr?", ["Einstein", "Newton", "Heisenberg", "Feynman"], 2),
    ("Was ist der Hauptbestandteil der Erdatmosphäre?", ["Sauerstoff", "Kohlendioxid", "Stickstoff", "Argon"], 2),
    ("Wie lautet Avogadros Zahl (gerundet)?", ["6,022 × 10²³", "3,14 × 10¹⁵", "9,81 × 10⁶", "1,38 × 10⁻²³"], 0),
    ("Welche Frequenz hat das menschliche Hörvermögen maximal?", ["10 kHz", "15 kHz", "20 kHz", "25 kHz"], 2),
    ("Was beschreibt das Pauli-Prinzip?", ["Gravitationskraft", "Elektronenbesetzung", "Lichtbrechung", "Wärmeausdehnung"], 1),
    ("Welcher physikalische Effekt beschreibt die Frequenzänderung bei Bewegung?", ["Doppler-Effekt", "Fotoelektrischer Effekt", "Meißner-Effekt", "Stark-Effekt"], 0),
    ("Wie heißt der tiefste Graben der Erde?", ["Marianengraben", "Tongagraben", "Kurilengraben", "Philippinengraben"], 0),
    ("Welcher Kaiser krönte sich 1804 selbst?", ["Napoleon Bonaparte", "Karl der Große", "Julius Caesar", "Franz II."], 0),
    ("Wie lautet die Hauptstadt von Australien?", ["Canberra", "Sydney", "Melbourne", "Brisbane"], 0),
    ("Welche Währung hatte Spanien vor dem Euro?", ["Peseta", "Lira", "Franc", "Escudo"], 0),
    ("In welchem Jahr sank die Titanic?", ["1912", "1905", "1918", "1920"], 0),
    ("Wie heißt das proteinhaltige Molekül, das Sauerstoff im Blut transportiert?", ["Hämoglobin", "Myoglobin", "Kollagen", "Insulin"], 0),
    ("Wer ist der Schöpfer der Oper 'Die Zauberflöte'?", ["Wolfgang Amadeus Mozart", "Ludwig van Beethoven", "Johann Sebastian Bach", "Richard Wagner"], 0),
    ("Welcher Planet unseres Sonnensystems hat die höchste Oberflächentemperatur?", ["Venus", "Merkur", "Mars", "Jupiter"], 0),
    ("Was ist die Hauptstadt von Kanada?", ["Ottawa", "Toronto", "Vancouver", "Montreal"], 0),
]

QUESTIONS_PER_LEVEL = 200


def _make_question(prompt: str, correct, wrongs) -> tuple:
    options = [str(correct), *[str(w) for w in wrongs]]
    deduped = []
    for option in options:
        if option not in deduped:
            deduped.append(option)
    while len(deduped) < 4:
        deduped.append(str(correct + len(deduped) + 1) if isinstance(correct, int) else f"Option {len(deduped) + 1}")
    choices = deduped[:4]
    random.shuffle(choices)
    return (prompt, choices, choices.index(str(correct)))


def _number_question(prompt: str, correct: int, spread: int = 3) -> tuple:
    wrongs = [correct + spread, correct - spread, correct + spread * 2]
    wrongs = [value if value != correct else value + 1 for value in wrongs]
    return _make_question(prompt, correct, wrongs)


EXTRA_TOPIC_QUESTIONS = [
    ("Welches Instrument hat Tasten, Saiten und Hämmer?", "Klavier", ["Geige", "Trompete", "Flöte"]),
    ("Welche Musikrichtung ist eng mit Jamaika verbunden?", "Reggae", ["Tango", "Polka", "Oper"]),
    ("Wer gilt als 'King of Pop'?", "Michael Jackson", ["Elvis Presley", "Freddie Mercury", "Prince"]),
    ("Welche Band veröffentlichte das Album 'Abbey Road'?", "The Beatles", ["Queen", "ABBA", "U2"]),
    ("Wie nennt man den Dirigentenstab?", "Taktstock", ["Bogen", "Plektrum", "Kapodaster"]),
    ("Welcher Vogel kann besonders gut Laute nachahmen?", "Papagei", ["Pinguin", "Adler", "Storch"]),
    ("Welcher Baum verliert im Herbst typischerweise seine Blätter?", "Ahorn", ["Tanne", "Kiefer", "Fichte"]),
    ("Was ist ein Biotop?", "Lebensraum", ["Gesteinsart", "Wetterlage", "Sternbild"]),
    ("Welches Tier baut Dämme in Flüssen?", "Biber", ["Fuchs", "Igel", "Reh"]),
    ("Welche Pflanze ist bekannt für ihre Sonnenblumenkerne?", "Sonnenblume", ["Rose", "Tulpe", "Orchidee"]),
    ("Welches Organ filtert Blut im menschlichen Körper?", "Niere", ["Lunge", "Magen", "Haut"]),
    ("Welche Blutkörperchen transportieren Sauerstoff?", "rote Blutkörperchen", ["weiße Blutkörperchen", "Blutplättchen", "Nervenzellen"]),
    ("Welche Sportart nutzt einen Puck?", "Eishockey", ["Basketball", "Tennis", "Rugby"]),
    ("Wie heißt der wichtigste Filmpreis in Hollywood?", "Oscar", ["Grammy", "Emmy", "Tony"]),
    ("Welches Land ist für Sushi bekannt?", "Japan", ["Mexiko", "Italien", "Norwegen"]),
    ("Welche Stadt nennt man auch 'Big Apple'?", "New York", ["London", "Berlin", "Madrid"]),
    ("Was ist ein Vulkan?", "Öffnung der Erdkruste", ["Wolkenart", "Meeresströmung", "Wüstenform"]),
    ("Welche Schicht schützt die Erde vor viel UV-Strahlung?", "Ozonschicht", ["Erdkern", "Troposphäre", "Magnetit"]),
    ("Was entsteht aus einer Raupe?", "Schmetterling", ["Frosch", "Libelle", "Biene"]),
    ("Welcher Planet ist für seine Ringe bekannt?", "Saturn", ["Mars", "Merkur", "Venus"]),
    ("Wie nennt man eine Gruppe von Sternen mit Muster?", "Sternbild", ["Krater", "Kontinent", "Molekül"]),
    ("Welche Farbe entsteht aus Gelb und Blau?", "Grün", ["Lila", "Orange", "Rot"]),
    ("Was ist ein Aquarell?", "Wasserfarbenbild", ["Steinskulptur", "Holzschnitt", "Fotofilm"]),
    ("Wer schrieb 'Harry Potter'?", "J. K. Rowling", ["Astrid Lindgren", "Cornelia Funke", "Enid Blyton"]),
    ("Wie heißt die Sprache der alten Römer?", "Latein", ["Griechisch", "Hebräisch", "Keltisch"]),
    ("Was ist ein Atlas?", "Kartensammlung", ["Messgerät", "Musikinstrument", "Sportart"]),
    ("Welches Gerät misst die Temperatur?", "Thermometer", ["Barometer", "Kompass", "Mikroskop"]),
    ("Was macht ein Kompass?", "Norden anzeigen", ["Temperatur messen", "Zeit stoppen", "Strom speichern"]),
    ("Welche Erfindung verbindet Computer weltweit?", "Internet", ["Mikrowelle", "Druckerpresse", "Taschenlampe"]),
    ("Was ist ein Passwort-Manager?", "Programm zum Speichern von Passwörtern", ["Musik-App", "Bildschirm", "Routerkabel"]),
    ("Welche Küche ist für Tacos bekannt?", "mexikanische Küche", ["japanische Küche", "schwedische Küche", "griechische Küche"]),
    ("Welches Gewürz färbt Speisen gelb?", "Kurkuma", ["Pfeffer", "Zimt", "Oregano"]),
    ("Welche Naturerscheinung erzeugt Donner?", "Gewitter", ["Nebel", "Frost", "Ebbe"]),
    ("Was ist Ebbe?", "niedriger Wasserstand", ["starker Wind", "Schneefall", "Vulkanausbruch"]),
    ("Welches Tier lebt sowohl im Wasser als auch an Land?", "Frosch", ["Hai", "Adler", "Kamel"]),
    ("Welche Pflanze liefert Kakaobohnen?", "Kakaobaum", ["Apfelbaum", "Olivenbaum", "Bambus"]),
    ("Welches Land gewann die Fußball-WM 2014?", "Deutschland", ["Brasilien", "Spanien", "Argentinien"]),
    ("Welche Stadt ist für den Karneval in Venedig berühmt?", "Venedig", ["Rom", "Mailand", "Neapel"]),
    ("Welches Tier ist das größte Säugetier?", "Blauwal", ["Elefant", "Giraffe", "Nashorn"]),
    ("Was sammelt ein Philatelist?", "Briefmarken", ["Münzen", "Bücher", "Schuhe"]),
    ("Welche Sprache spricht man überwiegend in Brasilien?", "Portugiesisch", ["Spanisch", "Französisch", "Italienisch"]),
    ("Welcher Kontinent ist der kleinste?", "Australien", ["Europa", "Antarktis", "Südamerika"]),
    ("Was ist ein Bonsai?", "Miniaturbaum", ["Teesorte", "Kampfsport", "Reisgericht"]),
    ("Welche Epoche kam nach dem Mittelalter?", "Renaissance", ["Steinzeit", "Barock", "Romantik"]),
    ("Welches Gerät vergrößert sehr kleine Dinge?", "Mikroskop", ["Teleskop", "Barometer", "Scanner"]),
    ("Was ist ein Podcast?", "Audiosendung", ["Suchmaschine", "Bildformat", "Kabeltyp"]),
    ("Welche Farbe hat Chlorophyll hauptsächlich?", "Grün", ["Rot", "Blau", "Gelb"]),
    ("Welcher Fluss fließt durch Paris?", "Seine", ["Themse", "Donau", "Elbe"]),
    ("Welche Insel gehört zu Italien?", "Sizilien", ["Kreta", "Mallorca", "Zypern"]),
    ("Was ist Origami?", "Papierfaltkunst", ["Tanzstil", "Suppengericht", "Holztechnik"]),
    ("Welches Metall ist bei Raumtemperatur flüssig?", "Quecksilber", ["Eisen", "Gold", "Kupfer"]),
    ("Welche Wolkenform kündigt oft Gewitter an?", "Cumulonimbus", ["Cirrus", "Stratus", "Nebel"]),
    ("Welches Land ist bekannt für Fjorde?", "Norwegen", ["Ungarn", "Ägypten", "Portugal"]),
    ("Wie heißt das größte Korallenriff der Erde?", "Great Barrier Reef", ["Rotes Riff", "Atlantikriff", "Nordseeriff"]),
    ("Was bedeutet Demokratie wörtlich ungefähr?", "Volksherrschaft", ["Königsherrschaft", "Geldherrschaft", "Stadtrecht"]),
    ("Welches Instrument spielt man mit einem Bogen?", "Geige", ["Trompete", "Klavier", "Schlagzeug"]),
]


def supplemental_question(level_idx: int, variant: int) -> tuple:
    prompt, correct, wrongs = EXTRA_TOPIC_QUESTIONS[(level_idx * 17 + variant) % len(EXTRA_TOPIC_QUESTIONS)]
    return _make_question(prompt, correct, wrongs)


def is_math_question(question: tuple) -> bool:
    prompt = question[0].lower()
    math_markers = [
        "was ist ",
        "wieviel",
        "wie viel",
        "löse",
        " x ",
        " + ",
        " - ",
        "%",
        "quadrat",
        "drittel",
        "hälfte",
        "größer",
        "primzahl",
    ]
    return any(marker in prompt for marker in math_markers)


def _young_question(level_idx: int, variant: int) -> tuple:
    level = level_idx + 1
    n = variant + 1
    kind = variant % 20
    base = level * 3 + n

    if kind == 0:
        a = base % 40 + 3
        b = (level + n) % 30 + 2
        return _number_question(f"Was ist {a} + {b}?", a + b)
    if kind == 1:
        a = base % 50 + 20
        b = (level + n) % 18 + 1
        return _number_question(f"Was ist {a} - {b}?", a - b)
    if kind == 2:
        a = level % 8 + 2
        b = n % 9 + 2
        return _number_question(f"Was ist {a} x {b}?", a * b, 2)
    if kind == 3:
        b = n % 8 + 2
        a = b * (level % 9 + 2)
        return _number_question(f"Was ist {a} : {b}?", a // b, 2)
    if kind == 4:
        colors = [("Blau und Gelb", "Grün", ["Rot", "Lila", "Braun"]),
                  ("Rot und Gelb", "Orange", ["Grün", "Blau", "Weiß"]),
                  ("Rot und Blau", "Lila", ["Gelb", "Orange", "Schwarz"])]
        mix, correct, wrongs = colors[(level + n) % len(colors)]
        return _make_question(f"Welche Farbe entsteht aus {mix}?", correct, wrongs)
    if kind == 5:
        animals = [("bellt", "Hund", ["Katze", "Kuh", "Pferd"]),
                   ("miaut", "Katze", ["Hund", "Ente", "Schaf"]),
                   ("wiehert", "Pferd", ["Kuh", "Huhn", "Fisch"]),
                   ("summt", "Biene", ["Maus", "Frosch", "Adler"])]
        sound, correct, wrongs = animals[(level + n) % len(animals)]
        return _make_question(f"Welches Tier {sound}?", correct, wrongs)
    if kind == 6:
        weekdays = [("Montag", "Dienstag"), ("Dienstag", "Mittwoch"), ("Mittwoch", "Donnerstag"),
                    ("Donnerstag", "Freitag"), ("Freitag", "Samstag"), ("Samstag", "Sonntag")]
        day, correct = weekdays[(level + n) % len(weekdays)]
        return _make_question(f"Welcher Tag kommt nach {day}?", correct, ["Montag", "Freitag", "Sonntag"])
    if kind == 7:
        facts = [("Wie viele Monate hat ein Jahr?", "12", ["10", "11", "13"]),
                 ("Wie viele Tage hat eine Woche?", "7", ["5", "6", "8"]),
                 ("Wie viele Beine hat eine Spinne?", "8", ["6", "4", "10"]),
                 ("Welche Form hat ein Ball meistens?", "rund", ["eckig", "flach", "spitz"])]
        return _make_question(*facts[(level + n) % len(facts)])
    if kind == 8:
        capitals = [("Deutschland", "Berlin", ["München", "Hamburg", "Köln"]),
                    ("Frankreich", "Paris", ["Lyon", "Rom", "Madrid"]),
                    ("Italien", "Rom", ["Mailand", "Paris", "Athen"]),
                    ("Spanien", "Madrid", ["Barcelona", "Lissabon", "Sevilla"])]
        country, correct, wrongs = capitals[(level + n) % len(capitals)]
        return _make_question(f"Wie heißt die Hauptstadt von {country}?", correct, wrongs)
    if kind == 9:
        nature = [("Was braucht eine Pflanze zum Wachsen?", "Licht", ["Steine", "Plastik", "Sand allein"]),
                  ("Welches Tier lebt im Wasser?", "Fisch", ["Hase", "Adler", "Schnecke"]),
                  ("Was fällt im Winter manchmal vom Himmel?", "Schnee", ["Sand", "Blätter", "Staub"]),
                  ("Welcher Stern scheint am Tag?", "Sonne", ["Mond", "Mars", "Venus"])]
        return _make_question(*nature[(level + n) % len(nature)])
    if kind == 10:
        body = [("Womit hört man?", "Ohren", ["Augen", "Nase", "Knie"]),
                ("Womit sieht man?", "Augen", ["Ohren", "Finger", "Zähne"]),
                ("Was schützt den Kopf?", "Helm", ["Schal", "Socke", "Handschuh"]),
                ("Womit riecht man?", "Nase", ["Mund", "Hand", "Fuß"])]
        return _make_question(*body[(level + n) % len(body)])
    if kind == 11:
        language = [("Was reimt sich auf Haus?", "Maus", ["Baum", "Sonne", "Tisch"]),
                    ("Was ist ein anderes Wort für schnell?", "flott", ["leise", "kalt", "rund"]),
                    ("Welches Wort ist ein Tier?", "Fuchs", ["Stuhl", "Lampe", "Wolke"]),
                    ("Was ist das Gegenteil von laut?", "leise", ["hell", "warm", "spitz"])]
        return _make_question(*language[(level + n) % len(language)])
    if kind == 12:
        safety = [("Bei welcher Farbe bleibt man an der Ampel stehen?", "Rot", ["Grün", "Blau", "Gelb"]),
                  ("Wo läuft man sicher über die Straße?", "Zebrastreifen", ["Wiese", "Parkplatz", "Bahnsteig"]),
                  ("Wen ruft man bei Feuer?", "Feuerwehr", ["Bäcker", "Bibliothek", "Kino"]),
                  ("Was trägt man im Auto zur Sicherheit?", "Gurt", ["Mütze", "Rucksack", "Schal"])]
        return _make_question(*safety[(level + n) % len(safety)])
    if kind == 13:
        food = [("Aus welcher Frucht macht man Apfelsaft?", "Apfel", ["Birne", "Banane", "Kirsche"]),
                ("Welche Mahlzeit isst man oft morgens?", "Frühstück", ["Abendbrot", "Mittagessen", "Nachtisch"]),
                ("Was ist meistens kalt und süß?", "Eis", ["Suppe", "Brot", "Reis"]),
                ("Aus welchem Getreide macht man oft Brot?", "Weizen", ["Kakao", "Kaffee", "Pfeffer"])]
        return _make_question(*food[(level + n) % len(food)])
    if kind == 14:
        music = [("Womit macht man Musik?", "Instrument", ["Lineal", "Teller", "Schlüssel"]),
                 ("Welches Instrument hat Tasten?", "Klavier", ["Trommel", "Flöte", "Gitarre"]),
                 ("Wie nennt man jemanden, der singt?", "Sänger", ["Maler", "Fahrer", "Bäcker"]),
                 ("Was hört man mit den Ohren?", "Musik", ["Farbe", "Duft", "Licht"])]
        return _make_question(*music[(level + n) % len(music)])
    if kind == 15:
        tech = [("Womit telefoniert man oft?", "Handy", ["Toaster", "Buch", "Stift"]),
                ("Was macht eine Kamera?", "Fotos", ["Kaffee", "Schuhe", "Wasser"]),
                ("Womit schreibt man am Computer?", "Tastatur", ["Gabel", "Kamm", "Ball"]),
                ("Was braucht eine Fernbedienung meistens?", "Batterien", ["Blätter", "Sand", "Milch"])]
        return _make_question(*tech[(level + n) % len(tech)])
    if kind == 16:
        seasons = [("Wann blühen viele Blumen?", "Frühling", ["Winter", "Nacht", "Herbst"]),
                   ("Wann ist es oft sehr warm?", "Sommer", ["Winter", "Montag", "Morgen"]),
                   ("Wann fallen viele Blätter?", "Herbst", ["Sommer", "Frühling", "Mittag"]),
                   ("Wann baut man oft einen Schneemann?", "Winter", ["Sommer", "Herbst", "Frühling"])]
        return _make_question(*seasons[(level + n) % len(seasons)])
    if kind == 17:
        logic = [("Was passt nicht dazu: Apfel, Banane, Auto, Birne?", "Auto", ["Apfel", "Banane", "Birne"]),
                 ("Was ist größer?", "Elefant", ["Maus", "Ameise", "Frosch"]),
                 ("Was ist leichter?", "Feder", ["Stein", "Auto", "Schrank"]),
                 ("Was kann fliegen?", "Flugzeug", ["Fahrrad", "Boot", "Zug"])]
        return _make_question(*logic[(level + n) % len(logic)])
    if kind == 18:
        space = [("Worauf leben wir?", "Erde", ["Mond", "Sonne", "Mars"]),
                 ("Was leuchtet nachts oft am Himmel?", "Mond", ["Baum", "Auto", "Buch"]),
                 ("Wie nennt man Menschen im Weltall?", "Astronauten", ["Piloten", "Taucher", "Maler"]),
                 ("Was ist die Sonne?", "Stern", ["Planet", "Wolke", "Insel"])]
        return _make_question(*space[(level + n) % len(space)])
    value = (level * 10) + (n % 10)
    return _number_question(f"Welche Zahl ist um 1 größer als {value}?", value + 1, 2)


def _mid_question(level_idx: int, variant: int) -> tuple:
    level = level_idx + 1
    n = variant + 1
    kind = variant % 20

    if kind == 0:
        a = level * 8 + n % 30
        b = level * 3 + n % 20
        return _number_question(f"Was ist {a} + {b}?", a + b, 4)
    if kind == 1:
        a = level * 12 + 80 + n
        b = level * 4 + n % 35
        return _number_question(f"Was ist {a} - {b}?", a - b, 5)
    if kind == 2:
        a = level + 5
        b = n % 12 + 3
        return _number_question(f"Was ist {a} x {b}?", a * b, 3)
    if kind == 3:
        percent = [10, 20, 25, 50][(level + n) % 4]
        amount = (n % 12 + 4) * 20
        correct = amount * percent // 100
        return _number_question(f"Wie viel sind {percent}% von {amount}?", correct, 5)
    if kind == 4:
        countries = [("Japan", "Tokio", ["Seoul", "Peking", "Bangkok"]),
                     ("Kanada", "Ottawa", ["Toronto", "Vancouver", "Montreal"]),
                     ("Australien", "Canberra", ["Sydney", "Melbourne", "Perth"]),
                     ("Österreich", "Wien", ["Graz", "Salzburg", "Linz"]),
                     ("Polen", "Warschau", ["Krakau", "Danzig", "Posen"])]
        country, correct, wrongs = countries[(level + n) % len(countries)]
        return _make_question(f"Was ist die Hauptstadt von {country}?", correct, wrongs)
    if kind == 5:
        science = [("Welches chemische Symbol hat Wasserstoff?", "H", ["O", "He", "N"]),
                   ("Welches chemische Symbol hat Sauerstoff?", "O", ["Au", "Ag", "C"]),
                   ("Wie nennt man den roten Blutfarbstoff?", "Hämoglobin", ["Insulin", "Kollagen", "Keratin"]),
                   ("Welches Organ pumpt Blut?", "Herz", ["Leber", "Lunge", "Niere"])]
        return _make_question(*science[(level + n) % len(science)])
    if kind == 6:
        history = [("In welchem Jahr begann der Erste Weltkrieg?", "1914", ["1912", "1918", "1939"]),
                   ("In welchem Jahr fiel die Berliner Mauer?", "1989", ["1961", "1991", "1975"]),
                   ("In welchem Jahr sank die Titanic?", "1912", ["1905", "1918", "1920"])]
        return _make_question(*history[(level + n) % len(history)])
    if kind == 7:
        geo = [("Welcher Fluss fließt durch Dresden?", "Elbe", ["Rhein", "Donau", "Main"]),
               ("Welches Meer liegt nördlich von Deutschland?", "Nordsee", ["Mittelmeer", "Schwarzes Meer", "Rotes Meer"]),
               ("Wie viele Bundesländer hat Deutschland?", "16", ["12", "14", "18"])]
        return _make_question(*geo[(level + n) % len(geo)])
    if kind == 8:
        a = n % 20 + 6
        correct = a * a
        return _number_question(f"Was ist {a} zum Quadrat?", correct, a)
    if kind == 9:
        fractions = [(1, 2, "die Hälfte"), (1, 4, "ein Viertel"), (3, 4, "drei Viertel")]
        numerator, denominator, label = fractions[(level + n) % len(fractions)]
        amount = denominator * (n % 20 + 5)
        correct = amount * numerator // denominator
        return _number_question(f"Wie viel ist {label} von {amount}?", correct, 4)
    if kind == 10:
        media = [("Was ist ein Podcast?", "Audiosendung", ["Suchmaschine", "Bildschirm", "Passwort"]),
                 ("Was ist ein Browser?", "Programm fürs Internet", ["Kabel", "Drucker", "Lautsprecher"]),
                 ("Was ist ein Screenshot?", "Bild vom Bildschirm", ["Tonaufnahme", "Textfehler", "Passwort"]),
                 ("Was bedeutet WLAN?", "drahtloses Netzwerk", ["Stromkabel", "Druckauftrag", "Lautsprecherbox"])]
        return _make_question(*media[(level + n) % len(media)])
    if kind == 11:
        environment = [("Was ist Recycling?", "Wiederverwertung", ["Verbrennen", "Wegwerfen", "Vergraben"]),
                       ("Welche Energiequelle ist erneuerbar?", "Sonne", ["Kohle", "Erdöl", "Benzin"]),
                       ("Was entsteht bei Photosynthese unter anderem?", "Sauerstoff", ["Plastik", "Salz", "Sand"]),
                       ("Was spart Wasser?", "kurz duschen", ["Hahn laufen lassen", "Badewanne überfüllen", "Auto täglich waschen"])]
        return _make_question(*environment[(level + n) % len(environment)])
    if kind == 12:
        language = [("Was ist ein Verb?", "Tunwort", ["Namenwort", "Eigenschaftswort", "Artikel"]),
                    ("Was ist ein Adjektiv?", "Eigenschaftswort", ["Tunwort", "Zahlwort", "Satzzeichen"]),
                    ("Welches Satzzeichen steht oft am Ende einer Frage?", "Fragezeichen", ["Komma", "Doppelpunkt", "Ausrufezeichen"]),
                    ("Was ist ein Synonym?", "ähnliches Wort", ["Gegenteil", "Reim", "Abkürzung"])]
        return _make_question(*language[(level + n) % len(language)])
    if kind == 13:
        sports = [("Wie viele Spieler hat eine Fußballmannschaft auf dem Feld?", "11", ["7", "9", "13"]),
                  ("Welche Sportart nutzt einen Schläger und Federball?", "Badminton", ["Handball", "Rudern", "Boxen"]),
                  ("Wie heißt der Start im Sprint?", "Startblock", ["Sprungbrett", "Torlinie", "Mittelkreis"]),
                  ("Welche Farbe hat die Tour-de-France-Spitzenwertung?", "gelb", ["rot", "blau", "grün"])]
        return _make_question(*sports[(level + n) % len(sports)])
    if kind == 14:
        art = [("Welche Farbe erhält man aus Rot und Blau?", "Lila", ["Grün", "Orange", "Braun"]),
               ("Was ist eine Skulptur?", "dreidimensionales Kunstwerk", ["Gedicht", "Melodie", "Landkarte"]),
               ("Wer schrieb viele Märchen mit seinem Bruder Wilhelm?", "Jacob Grimm", ["Goethe", "Einstein", "Mozart"]),
               ("Was ist ein Takt in der Musik?", "rhythmische Einheit", ["Farbe", "Bühnenbild", "Instrumentenkoffer"])]
        return _make_question(*art[(level + n) % len(art)])
    if kind == 15:
        health = [("Was stärkt die Ausdauer?", "regelmäßige Bewegung", ["nur Süßigkeiten", "wenig Schlaf", "kein Trinken"]),
                  ("Welcher Stoff ist wichtig für Knochen?", "Calcium", ["Helium", "Benzin", "Plastik"]),
                  ("Was transportiert Sauerstoff im Blut?", "rote Blutkörperchen", ["Haare", "Nägel", "Zähne"]),
                  ("Was sollte man vor dem Essen oft tun?", "Hände waschen", ["Schuhe binden", "Musik hören", "Fenster schließen"])]
        return _make_question(*health[(level + n) % len(health)])
    if kind == 16:
        economy = [("Was ist ein Budget?", "geplanter Geldrahmen", ["Wetterkarte", "Sportgerät", "Musikstück"]),
                   ("Was bedeutet sparen?", "Geld zurücklegen", ["alles ausgeben", "Geld zerreißen", "Preise erhöhen"]),
                   ("Was ist ein Rabatt?", "Preisnachlass", ["Steuer", "Zins", "Miete"]),
                   ("Wofür steht IBAN?", "Kontonummer", ["Passwort", "Schulnote", "WLAN-Name"])]
        return _make_question(*economy[(level + n) % len(economy)])
    if kind == 17:
        logic = [("Alle Blüten sind Pflanzen. Eine Rose ist eine Blüte. Was ist eine Rose?", "Pflanze", ["Tier", "Stein", "Maschine"]),
                 ("Was kommt in der Reihe 2, 4, 8, 16 als Nächstes?", "32", ["24", "30", "36"]),
                 ("Welches Wort passt nicht: Geige, Trommel, Gitarre, Fahrrad?", "Fahrrad", ["Geige", "Trommel", "Gitarre"]),
                 ("Was ist wahrscheinlicher: Münze Kopf oder Würfel 6?", "Kopf", ["Würfel 6", "gleich", "unmöglich"])]
        return _make_question(*logic[(level + n) % len(logic)])
    if kind == 18:
        astronomy = [("Welcher Planet ist der Sonne am nächsten?", "Merkur", ["Venus", "Mars", "Jupiter"]),
                     ("Wie heißt unsere Galaxie?", "Milchstraße", ["Andromeda", "Orion", "Polarstern"]),
                     ("Was ist ein Satellit?", "Begleiter im Orbit", ["Meeresströmung", "Vulkanart", "Wolkenform"]),
                     ("Warum gibt es Tag und Nacht?", "Erdrotation", ["Jahreszeiten", "Mondlicht", "Sonnenfinsternis"])]
        return _make_question(*astronomy[(level + n) % len(astronomy)])
    science_people = [("Wer entwickelte die Relativitätstheorie?", "Einstein", ["Newton", "Darwin", "Curie"]),
                      ("Wofür ist Marie Curie bekannt?", "Radioaktivität", ["Dampfmaschine", "Internet", "Buchdruck"]),
                      ("Wer formulierte Gesetze zur Bewegung?", "Newton", ["Mozart", "Kolumbus", "Kant"]),
                      ("Was erforschte Charles Darwin?", "Evolution", ["Elektrizität", "Oper", "Architektur"])]
    return _make_question(*science_people[(level + n) % len(science_people)])


def _hard_question(level_idx: int, variant: int) -> tuple:
    level = level_idx + 1
    n = variant + 1
    kind = variant % 20

    if kind == 0:
        a = level + 3
        b = n % 20 + 5
        c = level * 2 + n % 9
        return _number_question(f"Was ist {a} x {b} + {c}?", a * b + c, 7)
    if kind == 1:
        a = level + 4
        b = n % 13 + 3
        c = n % 8 + 2
        return _number_question(f"Was ist ({a} + {b}) x {c}?", (a + b) * c, 6)
    if kind == 2:
        x = level + n % 12
        result = 3 * x + 7
        return _number_question(f"Löse: 3x + 7 = {result}. Wie groß ist x?", x, 2)
    if kind == 3:
        speed = (level + 4) * 10
        time_hours = n % 5 + 1
        return _number_question(f"Ein Zug fährt {speed} km/h. Wie weit fährt er in {time_hours} h?", speed * time_hours, 20)
    if kind == 4:
        physics = [("Welche Einheit misst elektrische Spannung?", "Volt", ["Watt", "Ampere", "Newton"]),
                   ("Welche Einheit misst Kraft?", "Newton", ["Pascal", "Joule", "Volt"]),
                   ("Was beschreibt der Doppler-Effekt?", "Frequenzänderung", ["Massenverlust", "Ladungstrennung", "Wärmeleitung"]),
                   ("Was ist die Lichtgeschwindigkeit ungefähr?", "300.000 km/s", ["30.000 km/s", "3.000 km/s", "150.000 km/s"])]
        return _make_question(*physics[(level + n) % len(physics)])
    if kind == 5:
        chemistry = [("Welche Formel hat Wasser?", "H2O", ["CO2", "NaCl", "O2"]),
                     ("Welches Element hat das Symbol Au?", "Gold", ["Silber", "Argon", "Aluminium"]),
                     ("Welches Element hat die Ordnungszahl 6?", "Kohlenstoff", ["Sauerstoff", "Stickstoff", "Helium"]),
                     ("Welcher pH-Wert ist neutral?", "7", ["1", "5", "14"])]
        return _make_question(*chemistry[(level + n) % len(chemistry)])
    if kind == 6:
        culture = [("Wer schrieb 'Faust'?", "Goethe", ["Schiller", "Kafka", "Heine"]),
                   ("Wer komponierte 'Die Zauberflöte'?", "Mozart", ["Beethoven", "Bach", "Wagner"]),
                   ("Wer malte die Mona Lisa?", "Leonardo da Vinci", ["Michelangelo", "Raffael", "Picasso"])]
        return _make_question(*culture[(level + n) % len(culture)])
    if kind == 7:
        advanced = [("Wie heißt der tiefste bekannte Meeresgraben?", "Marianengraben", ["Tongagraben", "Kermadecgraben", "Atacamagraben"]),
                    ("Welche Währung hatte Spanien vor dem Euro?", "Peseta", ["Lira", "Franc", "Escudo"]),
                    ("Was ist ein Lichtjahr?", "Entfernung", ["Zeit", "Masse", "Temperatur"])]
        return _make_question(*advanced[(level + n) % len(advanced)])
    if kind == 8:
        a = n % 9 + 2
        b = level % 7 + 2
        correct = a ** 2 + b ** 2
        return _number_question(f"Was ist {a}² + {b}²?", correct, 5)
    if kind == 9:
        value = (level + n % 15) * 6
        correct = value // 3 + level
        return _number_question(f"Was ist ein Drittel von {value} plus {level}?", correct, 4)
    if kind == 10:
        computing = [("Was ist ein Algorithmus?", "Handlungsanweisung", ["Computerbauteil", "Bildschirmtyp", "Passwortliste"]),
                     ("Wofür steht HTML?", "HyperText Markup Language", ["High Tech Machine Logic", "Home Tool Mail Link", "Hyper Transfer Main Line"]),
                     ("Was ist Open Source?", "öffentlich einsehbarer Quellcode", ["verschlüsseltes WLAN", "kaputter Server", "privates Passwort"]),
                     ("Was beschreibt eine IP-Adresse?", "Netzwerkadresse", ["Bildauflösung", "Akkustand", "Dateigröße"])]
        return _make_question(*computing[(level + n) % len(computing)])
    if kind == 11:
        politics = [("Wie nennt man die Gewaltenteilung in drei Bereiche?", "Legislative, Exekutive, Judikative", ["Bund, Land, Stadt", "Import, Export, Zoll", "These, Antithese, Synthese"]),
                    ("Welches Organ beschließt in Deutschland Bundesgesetze maßgeblich?", "Bundestag", ["Bundesbank", "Bundeswehr", "Bundesliga"]),
                    ("Was ist eine Verfassung?", "Grundordnung eines Staates", ["Steuerbescheid", "Reisepass", "Wahlplakat"]),
                    ("Was bedeutet Föderalismus?", "Aufteilung zwischen Bund und Ländern", ["Herrschaft einer Stadt", "reine Direktwahl", "Abschaffung von Parlamenten"])]
        return _make_question(*politics[(level + n) % len(politics)])
    if kind == 12:
        literature = [("Welcher Roman beginnt mit Gregor Samsas Verwandlung?", "Die Verwandlung", ["Der Prozess", "Faust", "Effi Briest"]),
                      ("Wer schrieb 'Der Prozess'?", "Franz Kafka", ["Thomas Mann", "Bertolt Brecht", "Hermann Hesse"]),
                      ("Was ist ein Sonett?", "Gedichtform", ["Theaterbühne", "Romanfigur", "Musikinstrument"]),
                      ("Wer schrieb 'Der Steppenwolf'?", "Hermann Hesse", ["Günter Grass", "Goethe", "Schiller"])]
        return _make_question(*literature[(level + n) % len(literature)])
    if kind == 13:
        biology = [("Welche Zellbestandteile enthalten DNA bei Eukaryoten hauptsächlich?", "Zellkern", ["Ribosomen", "Zellwand", "Vakuole"]),
                   ("Was ist Osmose?", "Diffusion von Wasser", ["Zellteilung", "Photosynthese", "Proteinabbau"]),
                   ("Wie heißt die Erbinformation?", "DNA", ["ATP", "RNAse", "Insulin"]),
                   ("Was produzieren Chloroplasten mithilfe von Licht?", "Glucose", ["Harnstoff", "Eisen", "Kochsalz"])]
        return _make_question(*biology[(level + n) % len(biology)])
    if kind == 14:
        philosophy = [("Wer gilt als Autor der Ideenlehre?", "Platon", ["Aristoteles", "Kant", "Nietzsche"]),
                      ("Was fragt die Ethik?", "Was soll ich tun?", ["Wie schnell ist Licht?", "Wie malt man Öl?", "Wie kocht man Reis?"]),
                      ("Wer schrieb 'Kritik der reinen Vernunft'?", "Immanuel Kant", ["Hegel", "Descartes", "Sokrates"]),
                      ("Was bedeutet Empirie?", "Erkenntnis durch Erfahrung", ["Glaubenssatz", "Rechenfehler", "Sprachmelodie"])]
        return _make_question(*philosophy[(level + n) % len(philosophy)])
    if kind == 15:
        geography = [("Welche Meerenge trennt Europa und Afrika bei Gibraltar?", "Straße von Gibraltar", ["Bosporus", "Suezkanal", "Beringstraße"]),
                     ("Welcher Fluss ist der längste Afrikas?", "Nil", ["Kongo", "Niger", "Sambesi"]),
                     ("Welche Hauptstadt liegt am Tiber?", "Rom", ["Paris", "Prag", "Wien"]),
                     ("Welches Gebirge trennt Europa und Asien traditionell?", "Ural", ["Alpen", "Anden", "Atlas"])]
        return _make_question(*geography[(level + n) % len(geography)])
    if kind == 16:
        economics = [("Was misst das Bruttoinlandsprodukt?", "Wert aller produzierten Güter und Dienstleistungen", ["Staatsverschuldung allein", "Einwohnerzahl", "Inflation allein"]),
                     ("Was beschreibt Inflation?", "allgemeiner Preisanstieg", ["Lohnsenkung", "Exportverbot", "Zinsfreiheit"]),
                     ("Was ist Opportunitätskosten?", "Wert der besten Alternative", ["Mietvertrag", "Steuerart", "Bankkarte"]),
                     ("Was bedeutet Diversifikation?", "Risikostreuung", ["Monopolbildung", "Preisbindung", "Bargeldverbot"])]
        return _make_question(*economics[(level + n) % len(economics)])
    if kind == 17:
        language = [("Welche Sprache gehört zu den romanischen Sprachen?", "Spanisch", ["Deutsch", "Russisch", "Arabisch"]),
                    ("Was ist Etymologie?", "Wortherkunftslehre", ["Satzmelodie", "Drucktechnik", "Zahlenkunde"]),
                    ("Was ist ein Oxymoron?", "widersprüchliche Wortverbindung", ["Reimform", "Satzzeichen", "Dialekt"]),
                    ("Was bezeichnet Syntax?", "Satzbau", ["Lautstärke", "Wortherkunft", "Schriftfarbe"])]
        return _make_question(*language[(level + n) % len(language)])
    if kind == 18:
        logic = [("Wenn alle A B sind und alle B C sind, was gilt für A?", "Alle A sind C", ["Kein A ist C", "Einige C sind nie B", "Alle C sind A"]),
                 ("Was ist die Negation von 'alle' in der Logik?", "mindestens einer nicht", ["keiner immer", "alle nicht", "genau einer"]),
                 ("Welche Zahl folgt: 3, 6, 12, 24?", "48", ["36", "42", "54"]),
                 ("Was ist ein Trugschluss?", "scheinbar gültiges falsches Argument", ["korrekter Beweis", "Messgerät", "Wörterbuch"])]
        return _make_question(*logic[(level + n) % len(logic)])
    modern_history = [("Was markiert der 9. November 1989?", "Fall der Berliner Mauer", ["Beginn des Euro", "Ende des Ersten Weltkriegs", "Gründung der UNO"]),
                      ("Wann wurde die UNO gegründet?", "1945", ["1919", "1933", "1989"]),
                      ("Was war die Renaissance?", "kulturelle Wiederbelebung der Antike", ["Industriekrise", "Meeresströmung", "Programmiersprache"]),
                      ("Welche Revolution begann 1789?", "Französische Revolution", ["Russische Revolution", "Industrielle Revolution", "Digitale Revolution"])]
    return _make_question(*modern_history[(level + n) % len(modern_history)])


def build_level_question_bank(age: str) -> list[list[tuple]]:
    builders = {
        "young": _young_question,
        "mid": _mid_question,
        "old": _hard_question,
    }
    builder = builders.get(age, _mid_question)
    return [
        [
            *[builder(level_idx, variant) for variant in range(QUESTIONS_PER_LEVEL)],
            *[supplemental_question(level_idx, variant) for variant in range(40)],
        ]
        for level_idx in range(len(MONEY_LEVELS))
    ]


def create_game_questions(age: str) -> list[tuple]:
    bank = build_level_question_bank(age)
    questions = []
    used_prompts = set()
    for level_questions in bank:
        non_math = [question for question in level_questions if not is_math_question(question)]
        candidates = non_math if len(non_math) >= 8 else level_questions
        random.shuffle(candidates)
        chosen = None
        for question in candidates:
            prompt_key = question[0].strip().lower()
            if prompt_key not in used_prompts:
                chosen = question
                break
        if chosen is None:
            for question in level_questions:
                prompt_key = question[0].strip().lower()
                if prompt_key not in used_prompts:
                    chosen = question
                    break
        if chosen is None:
            raise RuntimeError("Nicht genug eindeutige Fragen fuer dieses Spiel.")
        used_prompts.add(chosen[0].strip().lower())
        questions.append(chosen)
    return questions


# ---------- Duel question helpers ----------
def duel_question_to_dict(q) -> dict:
    """Normalizes tuple/list/dict question formats for duel play."""
    if isinstance(q, dict):
        prompt = str(q.get("question", ""))
        answers = list(q.get("answers", []) or [])
        if q.get("correct"):
            return {"question": prompt, "answers": answers, "correct": str(q["correct"])}
        correct_idx = int(q.get("correct_idx", 0))
        if answers and 0 <= correct_idx < len(answers):
            return {"question": prompt, "answers": answers, "correct": str(answers[correct_idx])}
        return {"question": prompt or "?", "answers": answers or ["A", "B", "C", "D"], "correct": answers[0] if answers else "A"}
    if isinstance(q, (list, tuple)) and len(q) >= 3:
        prompt, answers, correct_idx = str(q[0]), list(q[1]), int(q[2])
        if answers and 0 <= correct_idx < len(answers):
            return {"question": prompt, "answers": [str(a) for a in answers], "correct": str(answers[correct_idx])}
    return {"question": "?", "answers": ["A", "B", "C", "D"], "correct": "A"}


def normalize_duel_questions(questions: list) -> list[dict]:
    return [duel_question_to_dict(q) for q in (questions or []) if q is not None]


def build_duel_questions(age: str = "mid", count: int = 15) -> list[dict]:
    bank = build_level_question_bank(age)
    pool = [q for level in bank for q in level]
    if len(pool) < count:
        picked = pool
    else:
        picked = random.sample(pool, count)
    return [duel_question_to_dict(q) for q in picked]


def _duel_document_id(duel: dict) -> str:
    return duel.get("id") or duel.get("_id") or ""


def refresh_duel_from_firestore(duel: dict) -> dict:
    duel_id = _duel_document_id(duel)
    client = get_firestore_client()
    if not client or not duel_id:
        return duel
    try:
        doc = client.collection("duels").document(duel_id).get()
        if doc.exists:
            fresh = doc.to_dict() or {}
            fresh["id"] = doc.id
            return fresh
    except Exception as ex:
        print(f"Duel refresh error: {ex}")
    return duel


# ---------- Build money ladder column ----------
def build_neon_nexus_money_ladder(state: dict, compact: bool = False) -> ft.Control:
    """Neon Nexus ladder with a glowing bar at the current prize level."""
    theme = get_theme(state)
    levels = money_levels_for_state(state)
    correct = min(state.get("correct", 0), len(levels) - 1)
    row_h = 21 if compact else 24
    header_h = 46 if compact else 52
    n = len(levels)
    i_current = n - 1 - correct
    rows = []
    is_nexus = theme.get("label") == "Neon Nexus"
    
    for i, level in enumerate(reversed(levels)):
        orig_idx = n - 1 - i
        is_current = orig_idx == correct
        is_reached = orig_idx < correct
        
        if is_nexus:
            dot_color = "#D946EF" if is_current else ("#0EA5E9" if is_reached else "#CBD5E1")
            text_color = "#D946EF" if is_current else ("#0F172A" if is_reached else "#94A3B8")
            bg_bar_color = "#D946EF33" if is_current else None
        else:
            dot_color = theme["gold"] if is_current else (theme["accent_2"] if is_reached else "#143d28")
            text_color = "#FFFFFF" if is_current else ("#B8FFD0" if is_reached else "#7AE8A8")
            bg_bar_color = "#0a140e" if is_current else None
            
        row_content = ft.Row([
            ft.Container(
                width=7, height=7, border_radius=4,
                bgcolor=dot_color,
                border=ft.border.Border.all(1, theme["border"]) if is_current and not is_nexus else None,
            ),
            ft.Text(
                level,
                size=12 if compact else 13,
                color=text_color,
                weight="bold" if is_current else "normal",
                expand=True,
                text_align=ft.TextAlign.RIGHT,
            ),
        ], spacing=6)

        if is_current:
            cell_content = ft.Stack([
                ft.Container(
                    left=4, right=4, top=(row_h - 8) / 2, height=8,
                    bgcolor="#D946EF" if is_nexus else theme["gold"],
                    border_radius=4,
                    shadow=ft.BoxShadow(blur_radius=18, color="#B000FF66", spread_radius=1) if not is_nexus else None,
                ),
                ft.Container(content=row_content, alignment=ft.Alignment(0, 0), height=row_h)
            ])
        else:
            cell_content = ft.Container(content=row_content, alignment=ft.Alignment(0, 0), height=row_h)

        rows.append(
            ft.Container(
                content=cell_content,
                height=row_h,
                bgcolor=bg_bar_color,
                border_radius=4,
            )
        )

    ladder_stack = ft.Column(
        [
            ft.Text(
                "PREISSTUFEN",
                size=12 if compact else 13,
                weight="bold",
                color=theme["gold"],
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Divider(color=theme["border"], height=1, thickness=1),
            *rows,
        ],
        spacing=0,
    )

    return ft.Container(
        content=ladder_stack,
        width=None if compact else 132,
        expand=compact,
        padding=ft.Padding(4, 4, 4, 4),
    )


def build_money_ladder(state: dict, compact: bool = False) -> ft.Control:
    """Build the right-side money ladder as a normal Column (no overlay)."""
    if uses_themed_game(get_theme(state)):
        return build_neon_nexus_money_ladder(state, compact)
    items = []
    correct = state.get("correct", 0)
    levels = money_levels_for_state(state)

    for i, level in enumerate(reversed(levels)):
        orig_idx = len(levels) - 1 - i
        is_current = orig_idx == correct  # current target level
        is_reached = orig_idx < correct   # already won

        if is_current:
            bg = "#F4A460"
            txt_color = "#2C1654"
            weight = "bold"
        elif is_reached:
            bg = "#9B59B6"
            txt_color = "white"
            weight = "normal"
        else:
            bg = "transparent"
            txt_color = "#CCCCCC"
            weight = "normal"

        row_num = ft.Text(
            str(len(levels) - i),
            size=11 if compact else 12,
            color=txt_color,
            weight=weight,
            width=18 if compact else 22,
            text_align="right",
        )
        row_money = ft.Text(
            level,
            size=12 if compact else 13,
            color=txt_color,
            weight=weight,
            expand=True,
            text_align="right",
        )
        item = ft.Container(
            content=ft.Row([row_num, row_money], spacing=6),
            padding=ft.Padding(8, 2 if compact else 3, 8, 2 if compact else 3),
            border_radius=8,
            bgcolor=bg,
        )
        items.append(item)

    return ft.Container(
        content=ft.Column(
            [
                ft.Row([
                    ft.Text("👑", size=18 if compact else 20),
                    ft.Text("PREISSTUFEN", size=13 if compact else 14, weight="bold", color="#FFD700"),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(color="#9B59B6", thickness=1),
                *items,
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=None if compact else 132,
        height=230 if compact else None,
        padding=10,
        bgcolor=theme_value(get_theme(state), "panel", "#1A0A30"),
        border_radius=16,
        border=ft.border.Border.all(2, theme_value(get_theme(state), "border", "#9B59B6")),
    )


# ---------- Welcome Screen ----------
def build_welcome_view(page: ft.Page, state: dict) -> ft.Control:
    """Styled welcome / main menu screen."""
    db = load_db()
    theme = get_theme(state)
    email = state.get("current_user_email")
    if email and email in db["users"]:
        username = db["users"][email].get("name", email)
        greeting = f"Hallo, {username}! 👋"
        logged_in = True
    else:
        greeting = "Hallo, Gast! 👋"
        username = "Gast"
        logged_in = False
    saved_game = get_saved_game_for_state(state) if logged_in else None

    def on_logout(e):
        state["current_user_email"] = None
        state["current_user_uid"] = None
        page.run_task(clear_remembered_login, e.page)
        open_main_menu(e.page, state)

    def resume_game(e):
        resume_saved_game(e.page, state)
        return

    def create_hover_card(
        title: str,
        desc: str,
        icon_name,
        color_hex: str,
        bg_hex: str,
        glow_hex: str,
        on_click,
        locked: bool = False,
        width: float = 280,
        height: float = 95,
        is_tall: bool = False,
        extra_content = None
    ):
        accent_color = color_hex
        border_color = f"#2A{glow_hex[1:]}" # subtle transparent border
        
        # Icon Circle
        icon_ctrl = ft.Container(
            content=ft.Text(
                "🔒" if locked else icon_name,
                color=accent_color,
                size=24 if is_tall else 20
            ),
            width=48 if is_tall else 42,
            height=48 if is_tall else 42,
            shape=ft.BoxShape.CIRCLE,
            bgcolor=f"#18{glow_hex[1:]}", # very transparent bg
            border=ft.border.Border.all(1, accent_color),
            alignment=ft.Alignment(0, 0)
        )
        
        if is_tall:
            card_content = ft.Column([
                icon_ctrl,
                ft.Container(expand=True),
                ft.Row([
                    ft.Column([
                        ft.Text(title, size=22, weight="bold", color="white"),
                        ft.Text(desc, size=13, color="#8B9A90")
                    ], spacing=2, tight=True),
                    ft.Container(expand=True),
                    ft.Text("▶", color="white", size=22)
                ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)
            
            if extra_content:
                card_content.controls.insert(2, extra_content)
        else:
            card_content = ft.Row([
                icon_ctrl,
                ft.Container(width=10),
                ft.Column([
                    ft.Text(title, size=16, weight="bold", color="white"),
                    ft.Text(desc, size=11, color="#8F949D" if not locked else "#E06B6B")
                ], spacing=2, tight=True, expand=True),
                ft.Text("▶" if not locked else "🔒", color="#4A505A" if locked else "white", size=18)
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
            
        # The main card Container
        card = ft.Container(
            content=card_content,
            bgcolor=bg_hex,
            width=width,
            height=height,
            border_radius=18 if is_tall else 16,
            padding=ft.Padding(24, 20, 24, 20) if is_tall else ft.Padding(18, 14, 18, 14),
            border=ft.border.Border.all(1.2, border_color),
            shadow=ft.BoxShadow(
                blur_radius=15,
                color=f"#15{glow_hex[1:]}", # soft glow
                spread_radius=-8
            ),
            on_click=on_click,
            scale=1.0,
            animate_scale=ft.Animation(200, ft.AnimationCurve.DECELERATE),
        )
        
        # Micro-animations on hover
        def on_hover(e):
            if e.data == "true":
                e.control.scale = 1.03
                e.control.border = ft.border.Border.all(1.2, accent_color)
                e.control.shadow = ft.BoxShadow(
                    blur_radius=25,
                    color=f"#25{glow_hex[1:]}",
                    spread_radius=-4
                )
                e.control.update()
            else:
                e.control.scale = 1.0
                e.control.border = ft.border.Border.all(1.2, border_color)
                e.control.shadow = ft.BoxShadow(
                    blur_radius=15,
                    color=f"#15{glow_hex[1:]}",
                    spread_radius=-8
                )
                e.control.update()
                
        card.on_hover = on_hover
        return card

    # Ambient glows (simplified without gradients)
    glow_left = ft.Container(
        width=500,
        height=500,
        bgcolor="#0A1D13",
        opacity=0.2
    )
    glow_right = ft.Container(
        width=500,
        height=500,
        bgcolor="#1D0D26",
        opacity=0.15
    )

    # Dot grid
    def create_dot_grid():
        dots = []
        for _ in range(4):
            dots.append(
                ft.Row([
                    ft.Container(width=4, height=4, bgcolor="#10B981", border_radius=2, opacity=0.15)
                    for _ in range(4)
                ], spacing=6)
            )
        return ft.Column(dots, spacing=6)

    # Profile actions at top right
    header_actions = ft.Row([
        ft.IconButton(
            icon=ft.Icon("👤"),
            icon_color="white",
            tooltip="Profil bearbeiten",
            on_click=lambda e: show_edit_profile_view(e.page, state)
        ) if logged_in else ft.Container(),
        ft.IconButton(
            icon=ft.Icon("🚪"),
            icon_color="#FF6B6B",
            tooltip="Abmelden",
            on_click=on_logout
        ) if logged_in else ft.Container()
    ], alignment=ft.MainAxisAlignment.END)

    # Top Central Banner Card
    top_card = ft.Container(
        content=ft.Column([
            # Circle with Question Mark
            ft.Container(
                content=ft.Text("?", size=32, weight="bold", color="white"),
                width=64,
                height=64,
                shape=ft.BoxShape.CIRCLE,
                bgcolor="#08100C",
                border=ft.border.Border.all(2, "#10B981"),
                alignment=ft.Alignment(0, 0),
                shadow=ft.BoxShadow(
                    blur_radius=15,
                    color="#10B981",
                    spread_radius=-4
                )
            ),
            ft.Container(height=8),
            # Title
            ft.Text("WER WIRD", size=24, weight="bold", color="white"),
            ft.Text("MILLIONÄR?", size=38, weight="w900", color="#10B981"),
            ft.Container(height=4),
            # Subtitle
            ft.Text("Teste dein Wissen. Werde Millionär.", size=13, color="#8B9A90")
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        width=600,
        padding=ft.Padding(32, 28, 32, 28),
        border_radius=24,
        bgcolor="#070A08",
        border=ft.border.Border.all(1.5, "#0E2919"),
        shadow=ft.BoxShadow(
            blur_radius=40,
            color="#081E12",
            spread_radius=-10
        ),
        alignment=ft.Alignment(0, 0)
    )

    # Greeting badge in center
    greeting_badge = ft.Container(
        content=ft.Row([
            ft.Text("👋", size=15),
            ft.Text("Hallo, ", color="white", size=13, weight="w500"),
            ft.Text(username, color="#10B981", size=13, weight="bold")
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=4, tight=True),
        bgcolor="#060C09",
        border=ft.border.Border.all(1, "#142D1E"),
        border_radius=30,
        padding=ft.Padding(18, 8, 18, 8),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color="#000000",
            spread_radius=-2
        )
    )

    # Standard cards setup
    card_start = create_hover_card(
        title="Spiel starten",
        desc="Dein Wissen. Dein Spiel.",
        icon_name="▶",
        color_hex="#10B981",
        bg_hex="#0A150F",
        glow_hex="#10B981",
        on_click=(lambda e: show_game_start_menu(e.page, state, saved_game)) if saved_game else (lambda e: start_new_game(e.page, state)),
        width=265,
        height=205,
        is_tall=True
    )

    card_settings = create_hover_card(
        title="Einstellungen",
        desc="Anpassen & konfigurieren",
        icon_name="⚙️",
        color_hex="#A78BFA",
        bg_hex="#130D22",
        glow_hex="#8B5CF6",
        on_click=lambda e: show_settings_view(e.page, state),
        width=265,
        height=95
    )
    
    if logged_in:
        card_shop = create_hover_card(
            title="Shop",
            desc="Power-Ups & Extras",
            icon_name="🛒",
            color_hex="#60A5FA",
            bg_hex="#0D1527",
            glow_hex="#3B82F6",
            on_click=lambda e: e.page.go("/shop"),
            width=265,
            height=95
        )
    else:
        card_shop = create_hover_card(
            title="Anmelden",
            desc="Profil verbinden",
            icon_name="🔑",
            color_hex="#60A5FA",
            bg_hex="#0D1527",
            glow_hex="#3B82F6",
            on_click=lambda e: show_login_view(e.page, state),
            width=265,
            height=95
        )
        
    card_daily = create_hover_card(
        title="Daily Challenge",
        desc="Jeden Tag neu" if logged_in else "Anmelden zum Spielen",
        icon_name="📅",
        color_hex="#FDBA74",
        bg_hex="#1E110A",
        glow_hex="#F97316",
        on_click=lambda e: e.page.go("/daily") if logged_in else show_login_view(e.page, state),
        locked=not logged_in,
        width=265,
        height=95
    )
    
    card_achievements = create_hover_card(
        title="Erfolge",
        desc="Deine Meilensteine" if logged_in else "Anmelden zum Freischalten",
        icon_name="🏆",
        color_hex="#FDE047",
        bg_hex="#1A180B",
        glow_hex="#FBBF24",
        on_click=lambda e: e.page.go("/achievements") if logged_in else show_login_view(e.page, state),
        locked=not logged_in,
        width=265,
        height=95
    )

    grid_row = ft.Row([
        card_start,
        ft.Column([
            card_settings,
            card_shop
        ], spacing=15, tight=True),
        ft.Column([
            card_daily,
            card_achievements
        ], spacing=15, tight=True)
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=15, tight=True)

    # Footer Bar
    footer_bar = ft.Container(
        content=ft.Row([
            ft.Text("🏆", color="#10B981", size=18),
            ft.VerticalDivider(width=1, color="#1F2A22", thickness=1),
            ft.Text("Wissen ist Macht.", color="white", size=12, weight="w500"),
            ft.Text("Bist du bereit?", color="#10B981", size=12, weight="bold"),
            ft.VerticalDivider(width=1, color="#1F2A22", thickness=1),
            ft.Container(width=40, height=2, bgcolor="#10B981", opacity=0.3)
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=12, tight=True),
        border_radius=20,
        border=ft.border.Border.all(1, "#14261B"),
        bgcolor="#060C08",
        padding=ft.Padding(24, 8, 24, 8)
    )

    main_column = ft.Column([
        top_card,
        ft.Container(height=5),
        greeting_badge,
        ft.Container(height=10),
        grid_row,
        ft.Container(height=10),
        footer_bar
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
    
    stack = ft.Stack([
        # Ambient glows behind
        ft.Container(
            content=glow_left,
            left=-100,
            top=-100
        ),
        ft.Container(
            content=glow_right,
            right=-100,
            bottom=-100
        ),
        # Dot grids in corners
        ft.Container(
            content=create_dot_grid(),
            left=40,
            top=40
        ),
        ft.Container(
            content=create_dot_grid(),
            right=40,
            bottom=40
        ),
        # Header action buttons
        ft.Container(
            content=header_actions,
            top=20,
            right=20
        ),
        # Centered main content
        ft.Container(
            content=main_column,
            alignment=ft.Alignment(0, 0),
            expand=True
        )
    ], expand=True)
    
    return ft.Container(
        expand=True,
        bgcolor="#030504",
        content=stack,
        alignment=ft.Alignment(0, 0)
    )


def _menu_button(label: str, on_click, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(label, size=18, weight="bold", color="white"),
        on_click=on_click,
        bgcolor=color,
        border_radius=50,
        padding=ft.Padding(40, 14, 40, 14),
        shadow=ft.BoxShadow(blur_radius=12, color="#40000000"),
    )


CUSTOM_QUIZ_BTN_WIDTH = 200
CUSTOM_QUIZ_BTN_HEIGHT = 44


def _game_menu_button(
    label: str,
    on_click,
    bgcolor: str,
    width: int = CUSTOM_QUIZ_BTN_WIDTH,
    height: int = CUSTOM_QUIZ_BTN_HEIGHT,
) -> ft.Container:
    return ft.Container(
        content=ft.Text(
            label, size=14, weight="bold", color="white",
            text_align=ft.TextAlign.CENTER, max_lines=2, no_wrap=False,
        ),
        on_click=on_click,
        bgcolor=bgcolor,
        border_radius=30,
        padding=ft.Padding(12, 8, 12, 8),
        alignment=ft.Alignment(0, 0),
        width=width,
        height=height,
    )


def show_game_start_menu(page: ft.Page, state: dict, saved: dict | None = None):
    """Spiel starten: fortsetzen, Standard-Quiz oder eigene Quizzes."""
    theme = get_theme(state)
    logged_in = bool(state.get("current_user_email"))
    buttons = []

    if saved:
        summary = saved_game_summary(saved)
        buttons.extend([
            ft.Text("Gespeichertes Spiel gefunden", size=16, weight="bold",
                    color=theme["gold"], text_align="center"),
            ft.Text(summary, size=13, color=theme_txt(theme, "secondary"), text_align="center"),
            ft.Container(height=4),
            _game_menu_button(
                "▶  Altes Spiel fortsetzen",
                lambda e: resume_saved_game(e.page, state, saved),
                theme["success"],
            ),
        ])

    buttons.append(
        _game_menu_button(
            "🎲  Neues Spiel starten",
            lambda e: show_age_selection(e.page, state),
            theme["accent"],
        )
    )
    if logged_in:
        buttons.append(
            _game_menu_button(
                "✏️  Eigene Spiele erstellen",
                lambda e: show_custom_quiz_hub(e.page, state),
                theme["accent_2"],
            )
        )
    else:
        buttons.append(
            ft.Text(
                "Eigene Spiele: bitte anmelden zum Speichern",
                size=12,
                color=theme_txt(theme, "muted"),
                text_align="center",
            )
        )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Spiel starten", size=30, weight="bold", color="white", text_align="center"),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Column(buttons, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=theme["panel"],
                    border_radius=16,
                    padding=24,
                    border=ft.border.Border.all(2, theme["border"]),
                    width=400,
                ),
                ft.TextButton(
                    "Zurück",
                    on_click=lambda e: open_main_menu(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14),
        )
    )
    page.update()


def show_custom_quiz_hub(page: ft.Page, state: dict):
    theme = get_theme(state)
    if not state.get("current_user_email"):
        show_login_view(page, state)
        return

    quizzes = get_user_custom_quizzes(state)
    quiz_rows = []
    for quiz in sorted(quizzes, key=lambda q: q.get("updated_at", ""), reverse=True):
        q_count = len(quiz.get("questions") or [])
        draft = quiz.get("is_draft", True)
        badge = "Entwurf" if draft else "Fertig"
        badge_color = theme["accent_2"] if draft else theme["success"]
        quiz_rows.append(
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(quiz.get("title", "Quiz"), size=16, weight="bold",
                                color=theme_txt(theme, "primary"), expand=True),
                        ft.Container(
                            content=ft.Text(badge, size=10, weight="bold", color="white"),
                            bgcolor=badge_color,
                            border_radius=8,
                            padding=ft.Padding(8, 3, 8, 3),
                        ),
                    ]),
                    ft.Text(f"{q_count} Frage(n)", size=12, color=theme_txt(theme, "secondary")),
                    ft.Row([
                        _game_menu_button(
                            "Bearbeiten",
                            lambda e, qid=quiz["id"]: show_custom_quiz_editor(e.page, state, qid),
                            theme["accent"],
                            width=120,
                            height=36,
                        ),
                        _game_menu_button(
                            "Spielen",
                            lambda e, q=quiz: start_custom_quiz_play(e.page, state, q),
                            theme["success"],
                            width=120,
                            height=36,
                        ),
                        _game_menu_button(
                            "Löschen",
                            lambda e, qid=quiz["id"]: confirm_delete_custom_quiz(e.page, state, qid),
                            theme["danger"],
                            width=120,
                            height=36,
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ], spacing=4),
                bgcolor=theme["panel"],
                border_radius=10,
                padding=12,
                border=ft.border.Border.all(1, theme["border"]),
            )
        )

    if not quiz_rows:
        quiz_rows.append(
            ft.Text("Noch keine eigenen Spiele. Lege jetzt eines an!", size=14,
                    color=theme_txt(theme, "secondary"), text_align="center")
        )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Eigene Spiele", size=28, weight="bold", color="white", text_align="center"),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Column(
                        quiz_rows,
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=420,
                    height=320,
                ),
                ft.Container(height=8),
                _game_menu_button(
                    "➕  Neues Spiel anlegen",
                    lambda e: show_custom_quiz_editor(e.page, state, None),
                    theme["success"],
                ),
                ft.TextButton(
                    "← Zurück",
                    on_click=lambda e: show_game_start_menu(e.page, state, get_saved_game_for_state(state)),
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=10),
        )
    )
    page.update()


def confirm_delete_custom_quiz(page: ft.Page, state: dict, quiz_id: str):
    theme = get_theme(state)
    quiz = find_custom_quiz(get_user_custom_quizzes(state), quiz_id)
    title = quiz.get("title", "Quiz") if quiz else "Quiz"

    def do_delete(e):
        close_page_dialog(page, dlg)
        delete_custom_quiz(state, quiz_id)
        show_custom_quiz_hub(page, state)

    dlg = ft.AlertDialog(
        title=ft.Text("Spiel löschen?"),
        content=ft.Text(f'"{title}" wirklich löschen?', color=theme_txt(theme, "secondary")),
        actions=[
            ft.TextButton("Abbrechen", on_click=lambda e: close_page_dialog(page, dlg)),
            ft.TextButton("Löschen", on_click=do_delete),
        ],
    )
    open_page_dialog(page, dlg)


def show_custom_quiz_editor(page: ft.Page, state: dict, quiz_id: str | None):
    theme = get_theme(state)
    if not state.get("current_user_email"):
        show_login_view(page, state)
        return

    if quiz_id:
        quiz = find_custom_quiz(get_user_custom_quizzes(state), quiz_id)
        if not quiz:
            quiz = new_empty_custom_quiz()
    else:
        quiz = new_empty_custom_quiz()

    state["editing_quiz"] = dict(quiz)
    auto_save_editing_quiz(state, title=quiz.get("title", "Mein Quiz"))

    save_status = ft.Text(
        "Automatisch gespeichert",
        size=12,
        color=theme["success"],
        text_align="center",
    )

    def on_title_change(e):
        auto_save_editing_quiz(state, title=title_field.value)
        save_status.value = "Automatisch gespeichert"
        save_status.update()

    title_field = ft.TextField(
        label="Titel des Spiels",
        value=quiz.get("title", ""),
        width=360,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
        on_change=on_title_change,
    )

    time_pressure_checkbox = ft.Checkbox(
        label="Timer aktivieren",
        value=bool(quiz.get("time_pressure_enabled", True)),
        fill_color=theme["accent"],
        check_color="white",
        label_style=ft.TextStyle(color=theme_txt(theme, "secondary"), size=13),
    )

    def on_time_pressure_change(e):
        state["editing_quiz"]["time_pressure_enabled"] = bool(e.control.value)
        auto_save_editing_quiz(state, title=title_field.value)

    time_pressure_checkbox.on_change = on_time_pressure_change

    time_sec_dropdown = ft.Dropdown(
        label="Sekunden pro Frage",
        value=str(int(quiz.get("question_time_sec", QUESTION_TIME_SEC))),
        options=[ft.dropdown.Option(str(v)) for v in QUESTION_TIME_OPTIONS],
        width=220,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )

    def on_time_sec_change(e):
        try:
            state["editing_quiz"]["question_time_sec"] = int(e.control.value)
        except Exception:
            state["editing_quiz"]["question_time_sec"] = QUESTION_TIME_SEC
        auto_save_editing_quiz(state, title=title_field.value)

    time_sec_dropdown.on_change = on_time_sec_change

    def save_finished(e):
        q = state["editing_quiz"]
        auto_save_editing_quiz(state, title=title_field.value)
        q = state["editing_quiz"]
        if not q.get("questions"):
            page.snack_bar = ft.SnackBar(content=ft.Text("Mindestens eine Frage erforderlich."))
            page.snack_bar.open = True
            page.update()
            return
        auto_save_editing_quiz(state, title=title_field.value, mark_finished=True)
        show_custom_quiz_hub(page, state)

    def add_question(e):
        auto_save_editing_quiz(state, title=title_field.value)
        if len(state["editing_quiz"].get("questions", [])) >= MAX_CUSTOM_QUESTIONS:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Maximal {MAX_CUSTOM_QUESTIONS} Fragen."))
            page.snack_bar.open = True
            page.update()
            return
        show_custom_question_editor(page, state, None)

    def play_now(e):
        auto_save_editing_quiz(state, title=title_field.value, mark_finished=bool(state["editing_quiz"].get("questions")))
        start_custom_quiz_play(page, state, state["editing_quiz"])

    def go_back_to_hub(e):
        auto_save_editing_quiz(state, title=title_field.value)
        show_custom_quiz_hub(e.page, state)

    questions_list = state["editing_quiz"].get("questions", [])
    planned_total = max(len(questions_list), 1)
    question_items = []
    for idx, q in enumerate(questions_list):
        preview = str(q.get("question", ""))[:50]
        if len(str(q.get("question", ""))) > 50:
            preview += "…"
        correct_letter = ANSWER_LETTERS[int(q.get("correct_idx", 0))]
        prize = custom_quiz_prize_for_number(idx + 1, planned_total)
        question_items.append(
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(
                            f"Frage {idx + 1} · {prize}",
                            size=12, weight="bold", color=theme["gold"],
                        ),
                        ft.Text(f"✓ {correct_letter}", size=12, color=theme["success"], weight="bold"),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(preview, size=13, color=theme_txt(theme, "primary")),
                    ft.Row([
                        _game_menu_button(
                            "Bearbeiten",
                            lambda e, i=idx: show_custom_question_editor(page, state, i),
                            theme["accent"],
                            width=175,
                            height=36,
                        ),
                        _game_menu_button(
                            "Entfernen",
                            lambda e, i=idx: delete_question_from_editor(page, state, i, title_field),
                            theme["danger"],
                            width=175,
                            height=36,
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                ], spacing=4),
                padding=ft.Padding(0, 4, 0, 8),
            )
        )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Quiz bearbeiten", size=26, weight="bold", color="white", text_align="center"),
                title_field,
                ft.Container(height=6),
                ft.Container(
                    content=ft.Column(
                        [
                            time_pressure_checkbox,
                            ft.Container(height=8),
                            time_sec_dropdown,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    width=420,
                    padding=12,
                    bgcolor=theme["panel"],
                    border_radius=12,
                    border=ft.border.Border.all(1, theme["border"]),
                ),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column(question_items or [
                        ft.Text("Noch keine Fragen", size=13, color=theme_txt(theme, "muted"))
                    ], spacing=4, scroll=ft.ScrollMode.AUTO),
                    width=400,
                    height=200,
                    bgcolor=theme["panel"],
                    border_radius=12,
                    padding=10,
                    border=ft.border.Border.all(1, theme["border"]),
                ),
                save_status,
                ft.Row([
                    _game_menu_button("➕ Frage", add_question, theme["accent"]),
                    _game_menu_button("✅ Fertig", save_finished, theme["success"]),
                    _game_menu_button("▶ Spielen", play_now, theme["gold"]),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=12, wrap=True),
                ft.TextButton(
                    "← Zurück zur Liste",
                    on_click=go_back_to_hub,
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=10, scroll=ft.ScrollMode.AUTO),
        )
    )
    page.update()


def delete_question_from_editor(page: ft.Page, state: dict, index: int, title_field: ft.TextField):
    q = state.get("editing_quiz")
    if not q:
        return
    questions = list(q.get("questions", []))
    if 0 <= index < len(questions):
        questions.pop(index)
        q["questions"] = questions
        auto_save_editing_quiz(state, title=title_field.value)
    show_custom_quiz_editor(page, state, q.get("id"))


def show_custom_question_editor(page: ft.Page, state: dict, question_index: int | None):
    theme = get_theme(state)
    quiz = state.get("editing_quiz")
    if not quiz:
        show_custom_quiz_hub(page, state)
        return

    existing = None
    questions = quiz.get("questions", [])
    if question_index is not None and 0 <= question_index < len(questions):
        existing = dict(questions[question_index])

    if question_index is not None:
        q_num = question_index + 1
        planned_total = max(len(questions), 1)
    else:
        q_num = len(questions) + 1
        planned_total = q_num
    prize = custom_quiz_prize_for_number(q_num, planned_total)

    question_field = ft.TextField(
        label="Frage",
        value=existing.get("question", "") if existing else "",
        multiline=True,
        min_lines=2,
        max_lines=4,
        width=360,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )
    answer_fields = []
    old_answers = (existing or {}).get("answers", ["", "", "", ""])
    while len(old_answers) < MAX_CUSTOM_ANSWERS:
        old_answers.append("")
    for i in range(MAX_CUSTOM_ANSWERS):
        answer_fields.append(ft.TextField(
            label=f"Antwort {ANSWER_LETTERS[i]}",
            value=old_answers[i] if i < len(old_answers) else "",
            width=360,
            bgcolor=theme["question_bg"],
            color=theme["question_text"],
            border_color=theme["border"],
        ))

    correct_dropdown = ft.Dropdown(
        label="Richtige Antwort",
        width=200,
        value=ANSWER_LETTERS[int((existing or {}).get("correct_idx", 0))],
        options=[ft.dropdown.Option(letter) for letter in ANSWER_LETTERS],
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )

    def save_question(e):
        answers = [(f.value or "").strip() for f in answer_fields]
        filled = [a for a in answers if a]
        if not (question_field.value or "").strip():
            page.snack_bar = ft.SnackBar(content=ft.Text("Bitte eine Frage eingeben."))
            page.snack_bar.open = True
            page.update()
            return
        if len(filled) < MIN_CUSTOM_ANSWERS:
            page.snack_bar = ft.SnackBar(content=ft.Text("Mindestens zwei Antworten ausfüllen."))
            page.snack_bar.open = True
            page.update()
            return
        correct_idx = ANSWER_LETTERS.index(correct_dropdown.value or "A")
        entry = {
            "question": question_field.value.strip(),
            "answers": answers,
            "correct_idx": correct_idx,
        }
        questions = list(quiz.get("questions", []))
        if question_index is not None and 0 <= question_index < len(questions):
            questions[question_index] = entry
        else:
            questions.append(entry)
        quiz["questions"] = questions
        state["editing_quiz"] = quiz
        auto_save_editing_quiz(state, title=quiz.get("title"))
        show_custom_quiz_editor(page, state, quiz.get("id"))

    def back_to_editor(e):
        auto_save_editing_quiz(state, title=quiz.get("title"))
        show_custom_quiz_editor(page, state, quiz.get("id"))

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text(
                    "Frage bearbeiten" if question_index is not None else "Neue Frage",
                    size=24, weight="bold", color="white", text_align="center",
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            f"Frage {q_num} von {planned_total}",
                            size=16, weight="bold", color=theme_txt(theme, "primary"),
                            text_align="center",
                        ),
                        ft.Text(
                            f"Preisstufe bei richtiger Antwort: {prize}",
                            size=15, weight="bold", color=theme["gold"],
                            text_align="center",
                        ),
                    ], spacing=4),
                    bgcolor=theme["panel"],
                    border_radius=12,
                    padding=14,
                    border=ft.border.Border.all(2, theme["border"]),
                    width=360,
                ),
                question_field,
                *answer_fields,
                correct_dropdown,
                ft.Container(height=8),
                ft.Row([
                    _game_menu_button("💾 Frage speichern", save_question, theme["success"]),
                    _game_menu_button("← Zurück", back_to_editor, theme["accent"]),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=12),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=8, scroll=ft.ScrollMode.AUTO),
        )
    )
    page.update()


# ---------- Age Selection ----------
def start_new_game(page: ft.Page, state: dict, force_new: bool = False):
    """Entry: menu with continue / standard / custom quizzes."""
    if not force_new:
        saved = get_saved_game_for_state(state)
        if saved or state.get("current_user_email"):
            show_game_start_menu(page, state, saved)
            return
    show_age_selection(page, state)


def show_age_selection(page: ft.Page, state: dict):
    """Reset state and ask for age group (standard quiz)."""
    reset_game_timer(state)
    theme = get_theme(state)
    state["time_pressure_enabled"] = True
    state["question_time_sec"] = QUESTION_TIME_SEC
    state.update({
        "money": "0 €",
        "questions_answered": 0,
        "correct": 0,
        "jokers_used": 0,
        "question_index": 0,
        "questions": [],
        "game_finished": False,
    })
    state.pop("saved_game", None)
    state.pop("is_custom_game", None)
    state.pop("custom_quiz_id", None)
    state.pop("custom_quiz_title", None)
    state.pop("selected_jokers", None)
    state.pop("jokers_used_ids", None)
    reset_joker_pick_state(state)

    def choose_age(e: ft.ControlEvent):
        age = e.control.data
        state["player_age"] = age
        state["questions"] = create_game_questions(age)
        state.pop("selected_jokers", None)
        state.pop("jokers_used_ids", None)
        reset_joker_pick_state(state)
        save_current_game(state)
        launch_game_after_jokers(page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Wähle deine Altersgruppe", size=26, weight="bold",
                        color="white", text_align="center"),
                ft.Container(height=10),
                _age_button("🌟  6 – 10 Jahre", "young", "#2ECC71", choose_age),
                _age_button("🔥  11 – 16 Jahre", "mid", "#F4A460", choose_age),
                _age_button("⚡  Ab 16 Jahre", "old", "#E91E8C", choose_age),
                ft.Container(height=10),
                ft.TextButton(
                    "← Zurück",
                    on_click=lambda e: show_game_start_menu(
                        e.page, state, get_saved_game_for_state(state)
                    ),
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14),
        )
    )
    page.update()


def _age_button(label: str, data: str, color: str, on_click) -> ft.Control:
    return ft.Container(
        content=ft.Text(label, size=20, weight="bold", color="white"),
        data=data,
        on_click=on_click,
        bgcolor=color,
        border_radius=50,
        padding=ft.Padding(50, 16, 50, 16),
        shadow=ft.BoxShadow(blur_radius=12, color="#40000000"),
    )


# ---------- Open main menu ----------
def open_main_menu(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    page.controls.clear()
    page.add(build_welcome_view(page, state))
    page.update()


# ---------- Game Screen ----------
def _neon_panel_border(theme: dict, width: int = 2) -> ft.Border:
    return ft.border.Border.all(width, theme["border"])


def _neon_solid_panel(content: ft.Control, theme: dict, expand: bool = True, compact: bool = False) -> ft.Container:
    """Opaque panel so text stays readable on any background."""
    is_nexus = theme.get("label") == "Neon Nexus"
    pad = 6 if compact else 10
    return ft.Container(
        content=content,
        bgcolor="#00000000" if is_nexus else theme.get("panel", "#0c1814"),
        border_radius=6,
        padding=ft.Padding(pad, pad - 2, pad, pad - 2),
        border=None if is_nexus else _neon_panel_border(theme),
        expand=expand,
        alignment=ft.Alignment(0, 0),
    )


def _duel_open_card(content: ft.Control, theme: dict, border_color: str | None = None) -> ft.Container:
    """Compact duel card — never uses expand (avoids empty gray blocks in web)."""
    return ft.Container(
        content=content,
        bgcolor=theme["panel"],
        border_radius=10,
        padding=ft.Padding(12, 10, 12, 10),
        border=ft.border.Border.all(1, border_color or theme["border"]),
        margin=ft.Margin(0, 0, 0, 6),
    )


def _neon_zone_box(zone: dict, page_w: float, page_h: float, content: ft.Control) -> ft.Container:
    """Places content in a relative zone (0..1) on the game canvas."""
    return ft.Container(
        left=max(0, int(page_w * zone["l"])),
        top=max(0, int(page_h * zone["t"])),
        width=max(80, int(page_w * zone["w"])),
        height=max(36, int(page_h * zone["h"])),
        content=content,
    )


def _duel_cancel_button(page: ft.Page, state: dict, theme: dict, duel: dict) -> ft.Container:
    return ft.Container(
        content=ft.Text("Abbrechen", size=12, color="white", weight="bold"),
        on_click=lambda e, d=duel: cancel_duel_challenge(page, state, d),
        bgcolor=theme["danger"],
        border_radius=16,
        padding=ft.Padding(12, 6, 12, 6),
    )


def _game_panel(
    content: ft.Control,
    theme: dict,
    *,
    height: int | None = None,
    width: int | None = None,
) -> ft.Container:
    """White/game panel with consistent width styling."""
    is_nexus = theme.get("label") == "Neon Nexus"
    return ft.Container(
        content=content,
        width=width,
        bgcolor="#00000000" if is_nexus else theme.get("question_bg", "#FFFFFF"),
        border_radius=10,
        padding=ft.Padding(12, 10, 12, 10),
        border=None if is_nexus else ft.border.Border.all(2, theme["border"]),
        height=height,
    )


async def _flash_red_screen(page: ft.Page, state: dict):
    """Brief red flash without rebuilding the game UI (keeps timer + clicks working)."""
    flash = ft.Container(bgcolor="#55FF1744", expand=True)
    page.overlay.append(flash)
    try:
        page.update()
    except Exception:
        pass
    await asyncio.sleep(0.12)
    if flash in page.overlay:
        page.overlay.remove(flash)
    try:
        page.update()
    except Exception:
        pass


def _start_question_timer(page: ft.Page, state: dict):
    timer_key = f"q{state['question_index']}"
    question_time_sec = int(state.get("question_time_sec", QUESTION_TIME_SEC)) or QUESTION_TIME_SEC
    time_pressure_enabled = bool(state.get("time_pressure_enabled", True))

    if state.get("_timer_question_key") != timer_key:
        state["_timer_question_key"] = timer_key
        state["time_left"] = question_time_sec
    elif state.get("time_left") is None:
        state["time_left"] = question_time_sec

    if state.get("_timer_active_key") == timer_key and not state.get("_timer_cancel"):
        sync_timer_display(page, state)
        return

    stop_game_timer(state)
    state["_timer_cancel"] = False
    state["_timer_active_key"] = timer_key
    sync_timer_display(page, state)

    async def tick():
        while not state.get("_timer_cancel") and state.get("_timer_active_key") == timer_key:
            now = time.time()
            phone_until = float(state.get("phone_until") or 0)
            friend_until = float(state.get("friend_until") or 0)

            # Joker-Countdowns laufen unabhängig vom Frage-Timer
            if phone_until > now or friend_until > now:
                sync_timer_display(page, state)
                await asyncio.sleep(0.3)
                continue

            time_pressure_enabled_now = bool(state.get("time_pressure_enabled", True))
            if not time_pressure_enabled_now:
                # Zeitdruck aus: keine Auto-"FALSCH"-Auslösung.
                sync_timer_display(page, state)
                await asyncio.sleep(0.6)
                continue

            question_time_sec_now = int(state.get("question_time_sec", QUESTION_TIME_SEC)) or QUESTION_TIME_SEC
            left = int(state.get("time_left", question_time_sec_now))
            if left <= 0:
                stop_game_timer(state)
                state.pop("_timer_active_key", None)
                state["questions_answered"] += 1
                state["game_finished"] = True
                clear_saved_game(state)
                _show_wrong_screen(page, state)
                return

            await asyncio.sleep(1)
            if state.get("_timer_cancel") or state.get("_timer_active_key") != timer_key:
                return

            state["time_left"] = max(0, int(state.get("time_left", question_time_sec_now)) - 1)
            sync_timer_display(page, state)
            if state["time_left"] == 10:
                await _flash_red_screen(page, state)
            elif 1 <= state["time_left"] <= 5:
                await _flash_red_screen(page, state)

    page.run_task(tick)


def render_game_screen(page: ft.Page, state: dict):
    """Unified game UI: timer, question, answers, status, jokers; classic + neon_nexus."""
    if state["question_index"] >= len(state["questions"]):
        _show_win_screen(page, state)
        return

    theme = get_theme(state)
    themed = uses_themed_game(theme)
    zones = theme.get("layout_zones", NEON_NEXUS_ZONES)
    answer_palette = theme.get("answer_colors", ANSWER_COLORS)
    question_text_color = theme_value(theme, "question_text", "#2C1654")
    answer_text_color = theme_value(theme, "answer_text", "#2C1654")
    answer_bg = theme_value(theme, "answer_bg", "#FFFFFF")
    question, options, correct_idx = state["questions"][state["question_index"]]
    q_num = state["question_index"] + 1
    total_q = len(state["questions"])
    page_w, page_h = _page_size(page)
    is_mobile = page_w < 720
    is_nexus = theme.get("label") == "Neon Nexus"

    state.setdefault("hidden_answers", [])
    hidden = set(state.get("hidden_answers", []))

    answer_buttons: list[ft.Container] = []
    answers_disabled = [False]

    def finish_answer(chosen: int):
        stop_game_timer(state)
        state.pop("truefalse_mode", None)
        state.pop("hidden_answers", None)

        async def _next():
            await asyncio.sleep(1.5)
            if chosen == correct_idx:
                state["correct"] += 1
                levels = money_levels_for_state(state)
                state["money"] = levels[min(state["correct"] - 1, len(levels) - 1)]
                state["questions_answered"] += 1
                state["question_index"] += 1
                reset_timer_for_new_question(state)
                if state["question_index"] >= len(state["questions"]):
                    _show_win_screen(page, state)
                else:
                    save_current_game(state)
                    _show_correct_screen(page, state)
            else:
                state["questions_answered"] += 1
                state["game_finished"] = True
                clear_saved_game(state)
                _show_wrong_screen(page, state)

        page.run_task(_next)

    def reset_answer_styles():
        for btn in answer_buttons:
            btn.bgcolor = answer_bg
            btn.border = ft.border.Border.all(2, theme["border"])

    def handle_answer(e):
        if answers_disabled[0]:
            return
        chosen = e.control.data
        if state.get("truefalse_mode"):
            answers_disabled[0] = True
            is_correct = chosen == correct_idx
            for idx, btn in enumerate(answer_buttons):
                if idx == chosen:
                    btn.border = ft.border.Border.all(3, "#2ECC71" if is_correct else "#E74C3C")
                    btn.bgcolor = "#C8E6C9" if is_correct else "#FFCDD2"
                else:
                    btn.bgcolor = answer_bg
                    btn.border = ft.border.Border.all(2, theme["border"])
            page.update()

            async def clear_test_feedback():
                await asyncio.sleep(1.4)
                reset_answer_styles()
                state.pop("truefalse_mode", None)
                answers_disabled[0] = False
                page.update()

            page.run_task(clear_test_feedback)
            return
        answers_disabled[0] = True
        for idx, btn_container in enumerate(answer_buttons):
            if idx == correct_idx:
                btn_container.bgcolor = "#00C853" if themed else "#2ECC71"
                btn_container.border = ft.border.Border.all(3, "#76FF03" if themed else "#27AE60")
            elif idx == chosen and idx != correct_idx:
                btn_container.bgcolor = "#B71C1C" if themed else "#E74C3C"
                btn_container.border = ft.border.Border.all(3, "#FF1744" if themed else "#C0392B")
        page.update()
        finish_answer(chosen)

    def make_answer_box(idx: int, text: str) -> ft.Container:
        letter = ANSWER_LETTERS[idx]
        color = answer_palette[idx % len(answer_palette)]
        _is_nexus = theme.get("label") == "Neon Nexus"

        letter_ctrl = ft.Container(width=42) if _is_nexus else ft.Container(
            content=ft.Text(letter, size=13, weight="bold", color="white"),
            width=30, height=30,
            border_radius=15,
            bgcolor=color,
            alignment=ft.Alignment(0, 0),
        )

        inner = ft.Row([
            letter_ctrl,
            ft.Text(text, size=14 if is_mobile else 15,
                    color=answer_text_color, weight="bold", expand=True,
                    max_lines=2, no_wrap=False),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        box = ft.Container(
            content=inner,
            data=idx,
            on_click=handle_answer,
            bgcolor=answer_bg,
            border_radius=10,
            padding=ft.Padding(10, 10, 10, 10),
            border=None if _is_nexus else ft.border.Border.all(2, theme["border"]),
            expand=True,
            visible=idx not in hidden,
            height=None if _is_nexus else (56 if not is_mobile else 50),
        )
        answer_buttons.append(box)
        return box

    answer_boxes = [make_answer_box(i, option) for i, option in enumerate(options)]
    ctx = {
        "theme": theme,
        "question": question,
        "options": options,
        "correct_idx": correct_idx,
        "answer_buttons": answer_buttons,
    }

    question_time_sec = int(state.get("question_time_sec", QUESTION_TIME_SEC)) or QUESTION_TIME_SEC
    time_pressure_enabled = bool(state.get("time_pressure_enabled", True))
    sec = max(0, int(state.get("time_left", question_time_sec))) if time_pressure_enabled else question_time_sec

    timer_text = ft.Text(
        "∞" if not time_pressure_enabled else str(sec),
        size=16, weight="bold",
        color="#FFFFFF" if is_nexus else (
            theme_txt(theme, "primary") if not time_pressure_enabled
            else ("#C62828" if sec <= 10 else theme_txt(theme, "primary"))
        ),
    )
    timer_bar = ft.ProgressBar(
        value=1.0 if not time_pressure_enabled else sec / question_time_sec,
        expand=True,
        height=8 if is_nexus else 10,
        color="#00FF66" if is_nexus else (
            theme["success"] if not time_pressure_enabled
            else ("#C62828" if sec <= 10 else theme["success"])
        ),
        bgcolor="#333333" if is_nexus else "#E0E0E0",
    )
    state["_timer_ui"] = {"text": timer_text, "bar": timer_bar}

    # ── background ─────────────────────────────────────────────────────────────
    bg_image = theme.get("game_bg") if themed else None
    overlay_color = "#00000000" if is_nexus else (
        "#00000099" if not theme.get("is_light") else "#00000055"
    )
    if bg_image:
        bg_layer = _themed_game_background(bg_image, page_w, page_h, overlay_color)
    else:
        bg_layer = ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
        )

    modal = state.get("_modal_overlay")

    # ══════════════════════════════════════════════════════════════════════════
    #  NEON NEXUS — absolute zone layout on top of background image
    # ══════════════════════════════════════════════════════════════════════════
    if is_nexus:
        nq_w = int(page_w * zones["question"]["w"])
        na_w = int(page_w * zones["answers"]["w"])
        na_h = int(page_h * zones["answers"]["h"])
        nt_w = int(page_w * zones["timer"]["w"])
        nf_w = int(page_w * zones["footer"]["w"])

        timer_panel = _game_panel(
            ft.Row([timer_text, ft.Container(content=timer_bar, expand=True)],
                   spacing=12, alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                   width=nt_w - 24),
            theme, height=int(page_h * zones["timer"]["h"]), width=nt_w,
        )
        question_panel = _game_panel(
            ft.Column([
                ft.Container(
                    content=ft.Text(f"FRAGE {q_num}", size=11, weight="bold", color="white"),
                    bgcolor=theme["gold"], border_radius=4,
                    padding=ft.Padding(8, 3, 8, 3),
                ),
                ft.Text(question, size=18, weight="bold", color=question_text_color,
                        text_align=ft.TextAlign.CENTER, max_lines=4, no_wrap=False),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER, width=nq_w - 24),
            theme, height=int(page_h * zones["question"]["h"]), width=nq_w,
        )
        answers_panel = _game_panel(
            ft.Column([
                ft.Row([answer_boxes[0], answer_boxes[1]], spacing=10, expand=True),
                ft.Row([answer_boxes[2], answer_boxes[3]], spacing=10, expand=True),
            ], spacing=10, width=na_w - 24, expand=True),
            theme, width=na_w, height=na_h,
        )
        nexus_exit_btn = ft.Container(
            content=ft.Row([
                ft.Text("🚪", size=14),
                ft.Text("Pause", size=13, weight="bold", color=theme["danger"]),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: (stop_game_timer(state), save_current_game(state), show_exit_confirmation(page, state)),
            bgcolor="#00000000", border_radius=4,
            padding=ft.Padding(10, 6, 10, 6), alignment=ft.Alignment(0, 0),
        )
        footer_content = ft.Column([
            _game_panel(
                ft.Row([
                    ft.Text(f"Frage {q_num} von {total_q}", size=13,
                            color=theme_txt(theme, "secondary"), weight="bold"),
                    ft.Text(f"◆ {state.get('money', '0 €')}", size=14,
                            color="#D946EF", weight="bold"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=nf_w - 24),
                theme,
            ),
            _game_panel(build_game_joker_bar(page, state, theme, ctx), theme),
        ], spacing=8)
        
        has_jokers = len(state.get("selected_jokers", [])) > 0
        if not has_jokers:
            footer_content.controls.pop() # Remove the joker panel
            
        ladder_panel = _neon_solid_panel(
            build_neon_nexus_money_ladder(state, compact=is_mobile), theme, compact=True)

        pw, ph = max(1, int(page_w)), max(1, int(page_h))
        hud = [bg_layer,
               _neon_zone_box(zones["exit"], page_w, page_h, nexus_exit_btn),
               _neon_zone_box(zones["timer"], page_w, page_h, timer_panel),
               _neon_zone_box(zones["question"], page_w, page_h, question_panel),
               _neon_zone_box(zones["answers"], page_w, page_h, answers_panel),
               _neon_zone_box(zones["footer"], page_w, page_h, footer_content),
               _neon_zone_box(zones["ladder"], page_w, page_h, ladder_panel)]
        if modal:
            hud.append(_neon_zone_box(zones["overlay"], page_w, page_h, modal))

        page.controls.clear()
        page.add(ft.Container(
            expand=True, width=pw, height=ph, bgcolor="#000000",
            content=ft.Stack(hud, expand=True, width=pw, height=ph),
        ))
        _set_themed_game_resize(page, state)
        _start_question_timer(page, state)
        page.update()
        return

    # ══════════════════════════════════════════════════════════════════════════
    #  CLASSIC — clean flow layout (Column/Row), no absolute positioning
    # ══════════════════════════════════════════════════════════════════════════
    ladder_panel = build_money_ladder(state, compact=is_mobile)

    # Pause / exit button
    exit_btn = ft.Container(
        content=ft.Row([
            ft.Text("🚪", size=12),
            ft.Text("Pause", size=12, weight="bold", color="white"),
        ], spacing=5, tight=True),
        on_click=lambda e: (stop_game_timer(state), save_current_game(state), show_exit_confirmation(page, state)),
        bgcolor=theme["danger"],
        border_radius=6,
        padding=ft.Padding(12, 7, 12, 7),
    )

    # Top bar: [Pause btn] + [timer bar + countdown]
    top_bar = ft.Row([
        exit_btn,
        ft.Container(
            content=ft.Row([
                ft.Container(content=timer_bar, expand=True),
                ft.Container(content=timer_text, width=36, alignment=ft.Alignment(1, 0)),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            bgcolor=theme.get("question_bg", "#FFFFFF"),
            border_radius=6,
            padding=ft.Padding(10, 7, 10, 7),
            border=ft.border.Border.all(2, theme["border"]),
        ),
    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # Question panel
    question_panel = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text(f"FRAGE {q_num}", size=11, weight="bold", color="#001a0a"),
                bgcolor=theme["gold"], border_radius=4,
                padding=ft.Padding(8, 3, 8, 3), alignment=ft.Alignment(0, 0),
            ),
            ft.Text(question, size=16 if is_mobile else 18, weight="bold",
                    color=question_text_color, text_align=ft.TextAlign.CENTER,
                    max_lines=4, no_wrap=False),
        ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=theme.get("question_bg", "#FFFFFF"),
        border_radius=10,
        padding=ft.Padding(16, 12, 16, 12),
        border=ft.border.Border.all(2, theme["border"]),
    )

    # Answer grid (2x2 desktop, stacked on mobile)
    if is_mobile:
        answers_grid = ft.Column(answer_boxes, spacing=8)
    else:
        answers_grid = ft.Column([
            ft.Row([answer_boxes[0], answer_boxes[1]], spacing=10),
            ft.Row([answer_boxes[2], answer_boxes[3]], spacing=10),
        ], spacing=10)

    # Status bar (question number + money)
    status_bar = ft.Container(
        content=ft.Row([
            ft.Text(f"Frage {q_num} von {total_q}", size=13,
                    color=theme_txt(theme, "secondary"), weight="bold"),
            ft.Text(f"◆ {state.get('money', '0 €')}", size=14,
                    color=theme["gold"], weight="bold"),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=theme.get("question_bg", "#FFFFFF"),
        border_radius=8,
        padding=ft.Padding(14, 8, 14, 8),
        border=ft.border.Border.all(2, theme["border"]),
    )

    # Joker bar — always its own row, never overlaps timer or question
    has_jokers = len(state.get("selected_jokers", [])) > 0
    joker_bar = ft.Container(
        content=build_game_joker_bar(page, state, theme, ctx),
        bgcolor=theme.get("question_bg", "#FFFFFF"),
        border_radius=8,
        padding=ft.Padding(10, 10, 10, 10),
        border=ft.border.Border.all(2, theme["border"]),
        visible=has_jokers,
    )

    # Left column: stacked vertically with natural flow
    left_col = ft.Column(
        [top_bar, question_panel, answers_grid, status_bar],
        spacing=10,
        expand=True,
    )
    if has_jokers:
        left_col.controls.append(joker_bar)

    if is_mobile:
        main_content = ft.Container(
            content=ft.Column(
                [top_bar, question_panel, answers_grid, status_bar, joker_bar, ladder_panel] if has_jokers else [top_bar, question_panel, answers_grid, status_bar, ladder_panel],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.Padding(12, 12, 12, 12),
            expand=True,
        )
    else:
        main_content = ft.Container(
            content=ft.Row(
                [left_col, ft.Container(content=ladder_panel, width=200)],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding(16, 16, 16, 16),
            expand=True,
        )

    layers: list = [bg_layer, main_content]
    if modal:
        layers.append(ft.Container(content=modal, expand=True))

    page.controls.clear()
    page.add(ft.Container(expand=True, content=ft.Stack(layers, expand=True)))
    _start_question_timer(page, state)
    page.update()


def show_next_question_themed(page: ft.Page, state: dict):
    render_game_screen(page, state)


def show_next_question(page: ft.Page, state: dict):
    """Display active question with timer and jokers."""
    if state["question_index"] >= len(state["questions"]):
        _show_win_screen(page, state)
        return

    q_idx = state["question_index"]
    if state.get("_last_spoken_q_idx") != q_idx:
        state["_last_spoken_q_idx"] = q_idx
        question, _, _ = state["questions"][q_idx]
        money = state.get("money", "0 €")
        text = f"Frage {q_idx + 1} für {money}. {question}"
        play_tts(page, text)

    render_game_screen(page, state)


def show_exit_confirmation(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    logged_in = email and email in db["users"]

    if logged_in:
        info_text = "Möchtest du das aktuelle Spiel wirklich beenden? Dein Fortschritt wird gespeichert und du kannst das Spiel jederzeit im Hauptmenü fortsetzen."
    else:
        info_text = "Möchtest du das aktuelle Spiel wirklich beenden?\n\n⚠️ Da du als Gast spielst, wird dein Spielstand nicht gespeichert und dein Fortschritt geht verloren!"

    def on_confirm_exit(e):
        if logged_in:
            save_current_game(state)
            db_current = load_db()
            if email in db_current["users"]:
                db_current["users"][email]["saved_game"] = {
                    "money": state.get("money", "0 €"),
                    "questions_answered": state.get("questions_answered", 0),
                    "correct": state.get("correct", 0),
                    "jokers_used": state.get("jokers_used", 0),
                    "question_index": state.get("question_index", 0),
                    "questions": state.get("questions", []),
                    "is_custom_game": state.get("is_custom_game", False),
                    "custom_quiz_id": state.get("custom_quiz_id"),
                    "custom_quiz_title": state.get("custom_quiz_title"),
                    "selected_jokers": state.get("selected_jokers", []),
                    "jokers_used_ids": state.get("jokers_used_ids", []),
                    "time_left": max(0, int(state.get("time_left", QUESTION_TIME_SEC))),
                    "hidden_answers": state.get("hidden_answers", []),
                    "time_pressure_enabled": bool(state.get("time_pressure_enabled", True)),
                    "question_time_sec": int(state.get("question_time_sec", QUESTION_TIME_SEC)),
                    "phone_until": state.get("phone_until"),
                    "friend_until": state.get("friend_until"),
                }
                save_db(db_current)
        open_main_menu(e.page, state)

    def on_resume_game(e):
        show_next_question(e.page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#2C1654", "#6B2FA0", "#C2185B"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Spiel unterbrechen?", size=24, weight="bold", color="white", text_align="center"),
                        ft.Container(height=10),
                        ft.Text(info_text, size=16, color="#E0D0F0", text_align="center"),
                        ft.Container(height=20),
                        ft.Row([
                            ft.Container(
                                content=ft.Text("Ja, beenden", size=16, weight="bold", color="white"),
                                on_click=on_confirm_exit,
                                bgcolor="#C0392B",
                                border_radius=30,
                                padding=ft.Padding(24, 12, 24, 12),
                                alignment=ft.Alignment(0, 0),
                                width=160,
                            ),
                            ft.Container(
                                content=ft.Text("Nein, weiter", size=16, weight="bold", color="white"),
                                on_click=on_resume_game,
                                bgcolor="#2ECC71",
                                border_radius=30,
                                padding=ft.Padding(24, 12, 24, 12),
                                alignment=ft.Alignment(0, 0),
                                width=160,
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    bgcolor="#1A0A30",
                    border_radius=20,
                    padding=30,
                    border=ft.border.Border.all(2, "#9B59B6"),
                    width=420,
                )
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )
    page.update()


# ---------- Result Screens ----------
def _show_correct_screen(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)

    def next_q(e):
        show_next_question(e.page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#1A3A1A", "#2ECC71", "#27AE60"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("✅", size=80),
                ft.Text("RICHTIG!", size=48, weight="black", color="white"),
                ft.Text(f"Du gewinnst: {state.get('money', '?')}",
                        size=22, color="#FFD700", weight="bold"),
                ft.Container(height=20),
                ft.Container(
                    content=ft.Text("➡  Nächste Frage", size=18, weight="bold", color="white"),
                    on_click=next_q,
                    bgcolor="#27AE60",
                    border_radius=50,
                    padding=ft.Padding(40, 14, 40, 14),
                    border=ft.border.Border.all(3, "white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=12),
        )
    )
    page.update()


def _show_wrong_screen(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    reset_game_timer(state)
    state["game_finished"] = True
    clear_saved_game(state)
    # Update persistent stats
    correct = state.get("correct", 0)
    answered = state.get("questions_answered", 0)
    money = state.get("money", "0 €")
    money_idx = -1
    if money in MONEY_LEVELS:
        money_idx = MONEY_LEVELS.index(money)
    update_game_stats(
        correct,
        answered,
        money,
        money_idx,
        state.get("current_user_email"),
        won=False,
        jokers_used=state.get("jokers_used", 0),
    )

    # Check achievements
    _check_and_show_achievements(page, state, money, won=False)
    
    # Daily challenge updates
    if state.get("is_daily_challenge"):
        db = load_db()
        email = state.get("current_user_email")
        if email and email in db["users"]:
            stats = db["users"][email]["stats"]
            stats["last_daily_played"] = state.get("daily_date", "")
            stats["daily_games_played"] = stats.get("daily_games_played", 0) + 1
            stats["daily_current_streak"] = 0 # reset streak on loss
            
            prev_total = stats.get("daily_avg_correct", 0) * (stats["daily_games_played"] - 1)
            stats["daily_avg_correct"] = (prev_total + correct) / stats["daily_games_played"]
            
            best_res = stats.get("daily_best_result", "0 €")
            best_idx = MONEY_LEVELS.index(best_res) if best_res in MONEY_LEVELS else -1
            if money_idx > best_idx:
                stats["daily_best_result"] = money
            save_db(db)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#3A0A0A", "#E74C3C", "#C0392B"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("❌", size=80),
                ft.Text("FALSCH!", size=48, weight="black", color="white"),
                ft.Text(f"Dein Gewinn: {state.get('money', '0 €')}",
                        size=22, color="#FFD700", weight="bold"),
                ft.Container(height=20),
                ft.Container(
                    content=ft.Text("🏠  Zurück zum Menü", size=18, weight="bold", color="white"),
                    on_click=lambda e: open_main_menu(e.page, state),
                    bgcolor="#C0392B",
                    border_radius=50,
                    padding=ft.Padding(40, 14, 40, 14),
                    border=ft.border.Border.all(3, "white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=12),
        )
    )
    page.update()


def _check_and_show_achievements(page: ft.Page, state: dict, money: str, won: bool):
    db = load_db()
    email = state.get("current_user_email")
    if email and email in db["users"]:
        user = db["users"][email]
        stats = user["stats"]
        unlocked = user.setdefault("unlocked_achievements", [])
        newly_unlocked = []
        
        if won and "purist" not in unlocked and state.get("jokers_used", 0) == 0:
            unlocked.append("purist")
            newly_unlocked.append("Purist")
            
        if "millionaire" not in unlocked and money == "1.000.000 €":
            unlocked.append("millionaire")
            newly_unlocked.append("Millionär")
            
        if "marathon" not in unlocked and stats.get("games_played", 0) >= 10:
            unlocked.append("marathon")
            newly_unlocked.append("Marathon")
            
        if newly_unlocked:
            save_db(db)
            ach_text = ", ".join(newly_unlocked)
            page.snack_bar = ft.SnackBar(content=ft.Text(f"🏆 Neue Erfolge freigeschaltet: {ach_text}!", size=16), bgcolor="green")
            page.snack_bar.open = True

def _show_win_screen(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    reset_game_timer(state)
    state["game_finished"] = True
    clear_saved_game(state)
    # Update persistent stats
    correct = state.get("correct", 0)
    answered = state.get("questions_answered", 0)
    money = state.get("money", "0 €")
    money_idx = -1
    if money in MONEY_LEVELS:
        money_idx = MONEY_LEVELS.index(money)
    update_game_stats(
        correct,
        answered,
        money,
        money_idx,
        state.get("current_user_email"),
        won=True,
        jokers_used=state.get("jokers_used", 0),
    )
    
    # Check achievements
    _check_and_show_achievements(page, state, money, won=True)
    
    # Daily challenge updates
    if state.get("is_daily_challenge"):
        db_d = load_db()
        email_d = state.get("current_user_email")
        if email_d and email_d in db_d["users"]:
            stats_d = db_d["users"][email_d]["stats"]
            stats_d["last_daily_played"] = state.get("daily_date", "")
            stats_d["daily_games_played"] = stats_d.get("daily_games_played", 0) + 1
            stats_d["daily_current_streak"] = stats_d.get("daily_current_streak", 0) + 1
            if stats_d["daily_current_streak"] > stats_d.get("daily_best_streak", 0):
                stats_d["daily_best_streak"] = stats_d["daily_current_streak"]
            
            prev_total = stats_d.get("daily_avg_correct", 0) * (stats_d["daily_games_played"] - 1)
            stats_d["daily_avg_correct"] = (prev_total + correct) / stats_d["daily_games_played"]
            
            best_res = stats_d.get("daily_best_result", "0 €")
            best_idx = MONEY_LEVELS.index(best_res) if best_res in MONEY_LEVELS else -1
            if money_idx > best_idx:
                stats_d["daily_best_result"] = money
            save_db(db_d)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#1A1000", "#B8860B", "#FFD700"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("🎉", size=80),
                ft.Text("GLÜCKWUNSCH!", size=36, weight="black", color="#2C1654"),
                ft.Text("Du hast alle Fragen beantwortet!", size=20, color="#2C1654"),
                ft.Text(f"Gewinn: {state.get('money', '?')}",
                        size=28, weight="bold", color="#2C1654"),
                ft.Container(height=20),
                ft.Container(
                    content=ft.Text("🏠  Zurück zum Menü", size=18, weight="bold", color="white"),
                    on_click=lambda e: open_main_menu(e.page, state),
                    bgcolor="#2C1654",
                    border_radius=50,
                    padding=ft.Padding(40, 14, 40, 14),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=12),
        )
    )
    page.update()


# ---------- Authentication & Profile Views ----------
def show_legacy_email_code_login_view(page: ft.Page, state: dict):
    db = load_db()
    
    email_input = ft.TextField(
        label="E-Mail-Adresse",
        width=300,
        bgcolor="#1A0A30",
        border_color="#9B59B6",
        color="white",
    )
    
    code_input = ft.TextField(
        label="6-stelliger Bestätigungscode",
        width=300,
        bgcolor="#1A0A30",
        border_color="#9B59B6",
        color="white",
        visible=False,
    )
    
    cooldown_text = ft.Text("", color="#FF4D4D", size=13, text_align="center", visible=False)
    status_text = ft.Text("", color="red", size=14, text_align="center")
    code_display_box = ft.Container(visible=False)
    
    verification_data = {"email": "", "code": "", "time": 0.0}
    request_state = {"last_request_time": 0.0}

    def show_cooldown_message(seconds_left: int):
        message = f"Bitte warte noch {seconds_left} Sekunden."
        cooldown_text.value = message
        cooldown_text.visible = True
        page.update()

        async def hide_message():
            await asyncio.sleep(2.0)
            if cooldown_text.value == message:
                cooldown_text.value = ""
                cooldown_text.visible = False
                page.update()

        page.run_task(hide_message)
    
    def on_request_code(e):
        email = email_input.value.strip()
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            status_text.value = "⚠️ Bitte eine gültige E-Mail eingeben."
            status_text.color = "red"
            page.update()
            return

        elapsed = time.time() - request_state["last_request_time"]
        if elapsed < CODE_REQUEST_COOLDOWN_SECONDS:
            remaining = int(CODE_REQUEST_COOLDOWN_SECONDS - elapsed + 0.999)
            show_cooldown_message(remaining)
            return
            
        code = f"{random.randint(100000, 999999)}"
        request_state["last_request_time"] = time.time()
        request_btn.disabled = True
        status_text.value = "Code wird per E-Mail gesendet..."
        status_text.color = "#FFD700"
        cooldown_text.value = ""
        cooldown_text.visible = False
        code_display_box.visible = False
        page.update()

        try:
            send_verification_email(email, code)
        except Exception as ex:
            verification_data["email"] = ""
            verification_data["code"] = ""
            verification_data["time"] = 0.0
            code_input.visible = False
            submit_btn.visible = False
            code_display_box.visible = False
            request_btn.disabled = False
            status_text.value = f"E-Mail konnte nicht gesendet werden: {ex}"
            status_text.color = "red"
            page.update()
            return
        
        code_display_box.content = ft.Container(
            content=ft.Column([
                ft.Text("E-Mail gesendet!", weight="bold", color="#FFD700"),
                ft.Text("Bitte pruefe dein Postfach und gib den 6-stelligen Code ein.", size=14, color="white", text_align="center"),
                ft.Text("(Code ist 10 Minuten gültig)", size=12, color="#E0D0F0"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=16,
            bgcolor="#2C1654",
            border_radius=12,
            border=ft.border.Border.all(1, "#9B59B6"),
        )
        verification_data["email"] = email
        verification_data["code"] = code
        verification_data["time"] = time.time()
        code_display_box.visible = True
        code_input.visible = True
        submit_btn.visible = True
        request_btn.disabled = False
        request_btn.content.value = "Neuen Code anfordern"
        status_text.value = "✓ Code gesendet! Bitte unten eingeben."
        status_text.color = "#2ECC71"
        page.update()
        
    def on_login(e):
        entered_code = code_input.value.strip()
        if not entered_code:
            status_text.value = "⚠️ Bitte gib den Code ein."
            status_text.color = "red"
            page.update()
            return
            
        if time.time() - verification_data["time"] > 600:
            status_text.value = "❌ Code abgelaufen! Bitte neuen anfordern."
            status_text.color = "red"
            page.update()
            return
            
        if entered_code != verification_data["code"]:
            status_text.value = "❌ Falscher Code. Bitte erneut eingeben."
            status_text.color = "red"
            page.update()
            return
            
        email = verification_data["email"]
        db = load_db()
        state["current_user_email"] = email
        if email not in db["users"]:
            default_name = email.split("@")[0].capitalize()
            db["users"][email] = {
                "name": default_name,
                "settings": DEFAULT_USER_SETTINGS.copy(),
                "stats": {
                    "games_played": 0,
                    "correct_answers": 0,
                    "questions_answered": 0,
                    "highest_money": "0 €",
                    "highest_money_level": -1
                }
            }
        ensure_user_settings(db, email)
        save_db(db)
        show_stats(page, state)
        
    request_btn = ft.Container(
        content=ft.Text("Code anfordern", size=16, weight="bold", color="white"),
        on_click=on_request_code,
        bgcolor="#9B59B6",
        border_radius=30,
        padding=ft.Padding(30, 12, 30, 12),
        alignment=ft.Alignment(0, 0),
        width=220,
    )
    
    submit_btn = ft.Container(
        content=ft.Text("Einloggen", size=16, weight="bold", color="white"),
        on_click=on_login,
        visible=False,
        bgcolor="#2ECC71",
        border_radius=30,
        padding=ft.Padding(30, 12, 30, 12),
        alignment=ft.Alignment(0, 0),
        width=220,
    )
    
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#2C1654", "#6B2FA0", "#C2185B"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("🔑 Anmelden", size=30, weight="bold", color="white"),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([
                        email_input,
                        request_btn,
                        code_display_box,
                        code_input,
                        submit_btn,
                        cooldown_text,
                        status_text,
                    ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#1A0A30",
                    border_radius=16,
                    padding=24,
                    border=ft.border.Border.all(2, "#9B59B6"),
                    width=360,
                ),
                ft.Container(height=10),
                ft.TextButton(
                    "← Zurück",
                    on_click=lambda e: show_stats(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                )
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14)
        )
    )
    page.update()


def show_login_view(page: ft.Page, state: dict):
    theme = get_theme(state)

    email_input = ft.TextField(
        label="E-Mail-Adresse",
        width=300,
        bgcolor=theme["panel"],
        border_color=theme["border"],
        color="white",
    )

    password_input = ft.TextField(
        label="Passwort",
        width=300,
        password=True,
        can_reveal_password=True,
        bgcolor=theme["panel"],
        border_color=theme["border"],
        color="white",
    )

    remember_checkbox = ft.Checkbox(
        label="Angemeldet bleiben",
        value=True,
        fill_color=theme["accent"],
        check_color="white",
        label_style=ft.TextStyle(color="#E0D0F0", size=13),
    )

    status_text = ft.Text("", color="red", size=14, text_align="center")

    async def finish_login(auth_data: dict):
        uid = auth_data["localId"]
        email = auth_data["email"]
        user = ensure_firebase_user(uid, email)

        db = load_db()
        db["users"][email] = user
        update_last_active(db, email)
        save_db(db)

        state["current_user_email"] = email
        state["current_user_uid"] = uid

        # IMPORTANT: await the storage save so tokens are on disk BEFORE we navigate.
        await save_remembered_login(page, auth_data, bool(remember_checkbox.value))
        print(f"[login] Credentials saved for {email}, remember={bool(remember_checkbox.value)}")

        # Check if there is a pending friend request from scanning a QR code
        pending_friend = state.pop("pending_friend_add", None)
        if pending_friend:
            msg = save_friend_request(state, pending_friend)
            show_friends_view(page, state, status_message=msg)
        else:
            open_main_menu(page, state)

    def validate_inputs() -> tuple[str | None, str | None]:
        email = email_input.value.strip()
        password = password_input.value.strip()
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            status_text.value = "Bitte eine gueltige E-Mail eingeben."
            status_text.color = "red"
            page.update()
            return None, None
        if len(password) < 6:
            status_text.value = "Das Passwort muss mindestens 6 Zeichen haben."
            status_text.color = "red"
            page.update()
            return None, None
        return email, password

    async def run_auth(action: str):
        email, password = validate_inputs()
        if not email or not password:
            return

        status_text.value = "Verbindung mit Firebase..."
        status_text.color = theme["gold"]
        page.update()

        try:
            auth_data = firebase_auth_request(action, email, password)
            await finish_login(auth_data)
        except Exception as ex:
            status_text.value = str(ex)
            status_text.color = "red"
            page.update()

    def on_login(e):
        page.run_task(run_auth, "signInWithPassword")

    def on_register(e):
        page.run_task(run_auth, "signUp")

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Anmelden", size=30, weight="bold", color="white"),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([
                        email_input,
                        password_input,
                        remember_checkbox,
                        ft.Container(
                            content=ft.Text("Einloggen", size=16, weight="bold", color="white"),
                            on_click=on_login,
                            bgcolor=theme["success"],
                            border_radius=30,
                            padding=ft.Padding(30, 12, 30, 12),
                            alignment=ft.Alignment(0, 0),
                            width=220,
                        ),
                        ft.Container(
                            content=ft.Text("Registrieren", size=16, weight="bold", color="white"),
                            on_click=on_register,
                            bgcolor=theme["accent"],
                            border_radius=30,
                            padding=ft.Padding(30, 12, 30, 12),
                            alignment=ft.Alignment(0, 0),
                            width=220,
                        ),
                        status_text,
                    ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=theme["panel"],
                    border_radius=16,
                    padding=24,
                    border=ft.border.Border.all(2, theme["border"]),
                    width=360,
                ),
                ft.Container(height=10),
                ft.TextButton(
                    "Zurueck",
                    on_click=lambda e: show_stats(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                )
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14)
        )
    )
    page.update()


async def _do_logout(page: ft.Page, state: dict):
    """Clears saved credentials and returns the user to the guest main menu."""
    await clear_remembered_login(page)
    state["current_user_email"] = None
    state["current_user_uid"] = None
    print("[logout] User logged out, credentials cleared.")
    open_main_menu(page, state)


def show_settings_view(page: ft.Page, state: dict):
    theme = get_theme(state)
    email = state.get("current_user_email")
    logged_in = bool(email)

    menu_items = [
        ft.Text("Einstellungen", size=30, weight="bold", color=theme_txt(theme, "primary")),
        ft.Container(height=10),
        ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Text("Statistiken", size=16, weight="bold", color="white"),
                    on_click=lambda e: show_stats(e.page, state),
                    bgcolor=theme["accent"],
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=240,
                ),
                ft.Container(
                    content=ft.Text("Design", size=16, weight="bold", color="white"),
                    on_click=lambda e: show_design_view(e.page, state),
                    bgcolor=theme["success"] if logged_in else "#777777",
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=240,
                ),
                ft.Container(
                    content=ft.Text("Freunde", size=16, weight="bold", color="white"),
                    on_click=lambda e: show_friends_view(e.page, state) if logged_in else show_login_view(e.page, state),
                    bgcolor=theme["accent"],
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=240,
                ),
                ft.Container(
                    content=ft.Text("Profil bearbeiten", size=16, weight="bold", color="white"),
                    on_click=lambda e: show_edit_profile_view(e.page, state) if logged_in else show_login_view(e.page, state),
                    bgcolor=theme["accent_2"],
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=240,
                ),
                ft.Text(
                    "Melde dich an, um Designs pro Account zu speichern." if not logged_in else f"Konto: {email}",
                    size=12,
                    color=theme_txt(theme, "secondary"),
                    text_align="center",
                ),
            ] + ([
                ft.Container(height=4),
                ft.Container(
                    content=ft.Text("🚪 Abmelden", size=16, weight="bold", color="white"),
                    on_click=lambda e: page.run_task(_do_logout, page, state),
                    bgcolor=theme["danger"],
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=240,
                ),
            ] if logged_in else []),
            spacing=14, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=theme["panel"],
            border_radius=16,
            padding=24,
            border=ft.border.Border.all(2, theme["border"]),
            width=360,
        ),
        ft.TextButton(
            "Zurück",
            on_click=lambda e: open_main_menu(e.page, state),
            style=ft.ButtonStyle(color="white"),
        ),
    ]

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                menu_items,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
            ),
        )
    )
    page.update()


def show_design_view(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    if not email or email not in db.get("users", {}):
        show_login_view(page, state)
        return

    ensure_user_settings(db, email)
    save_db(db)
    current_theme = db["users"][email].get("settings", {}).get("theme", "classic")
    theme = get_theme(state)
    status_text = ft.Text("", size=13, text_align="center")

    def choose_theme(theme_key: str):
        def _handler(e):
            db_current = load_db()
            if email in db_current.get("users", {}) and theme_key in THEMES:
                ensure_user_settings(db_current, email)
                db_current["users"][email]["settings"]["theme"] = theme_key
                save_db(db_current)
                state["theme"] = theme_key
                status_text.value = "Design gespeichert."
                status_text.color = THEMES[theme_key]["success"]
                show_design_view(e.page, state)
        return _handler

    cards = []
    for key, value in THEMES.items():
        selected = key == current_theme
        cards.append(
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        height=48,
                        border_radius=12,
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, -1),
                            end=ft.Alignment(1, 1),
                            colors=value["gradient"],
                        ),
                    ),
                    ft.Text(value["label"], size=15, weight="bold", color="white" if value["panel"] != "#FFFFFF" else "#102030"),
                    ft.Text("Aktiv" if selected else "Auswählen", size=12, color=value["gold"] if selected else "#CCCCCC"),
                ], spacing=8),
                on_click=choose_theme(key),
                bgcolor=value["panel"],
                border_radius=12,
                padding=12,
                border=ft.border.Border.all(3 if selected else 1, value["gold"] if selected else value["border"]),
                width=170,
            )
        )

    rows = [
        ft.Row(cards[i:i + 2], spacing=12, alignment=ft.MainAxisAlignment.CENTER)
        for i in range(0, len(cards), 2)
    ]

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Design", size=30, weight="bold", color=theme_txt(theme, "primary")),
                ft.Container(height=6),
                ft.Container(
                    content=ft.Column([
                        *rows,
                        status_text,
                    ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=theme["panel"],
                    border_radius=16,
                    padding=20,
                    border=ft.border.Border.all(2, theme["border"]),
                    width=390,
                ),
                ft.TextButton(
                    "Zurück",
                    on_click=lambda e: show_settings_view(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14, scroll=ft.ScrollMode.AUTO),
            padding=20,
        )
    )
    page.update()

def _medal(rank: int) -> str:
    return ["🥇", "🥈", "🥉"][rank - 1] if rank <= 3 else f"{rank}."



ACTIVE_DUEL_STATUSES = ("pending_accept", "pending", "challenger_done")


def get_active_duel_with_friend(email: str, friend_email: str) -> dict | None:
    """Returns an open duel between two friends, if any."""
    client = get_firestore_client()
    if not client:
        return None
    try:
        for doc in client.collection("duels").where("challenger_email", "==", email).where(
            "opponent_email", "==", friend_email
        ).stream():
            duel = doc.to_dict() or {}
            if duel.get("status") in ACTIVE_DUEL_STATUSES:
                duel["id"] = doc.id
                return duel
        for doc in client.collection("duels").where("challenger_email", "==", friend_email).where(
            "opponent_email", "==", email
        ).stream():
            duel = doc.to_dict() or {}
            if duel.get("status") in ACTIVE_DUEL_STATUSES:
                duel["id"] = doc.id
                return duel
    except Exception as ex:
        print(f"Duel check error: {ex}")
    return None


def open_page_dialog(page: ft.Page, dlg: ft.AlertDialog):
    """Open AlertDialog (compatible with Flet versions without page.open)."""
    if hasattr(page, "open"):
        try:
            page.open(dlg)
            page.update()
            return
        except Exception:
            pass
    page.dialog = dlg
    dlg.open = True
    if dlg not in page.overlay:
        page.overlay.append(dlg)
    page.update()


def close_page_dialog(page: ft.Page, dlg: ft.AlertDialog):
    if hasattr(page, "close"):
        try:
            page.close(dlg)
            page.update()
            return
        except Exception:
            pass
    dlg.open = False
    page.dialog = None
    if dlg in page.overlay:
        page.overlay.remove(dlg)
    page.update()


def _close_overlay(page: ft.Page, overlay):
    if isinstance(overlay, ft.AlertDialog):
        close_page_dialog(page, overlay)
        return
    if hasattr(page, "close"):
        try:
            page.close(overlay)
            page.update()
            return
        except Exception:
            pass
    overlay.open = False
    page.update()


def show_friend_profile_popup(page: ft.Page, state: dict, friend_email: str):
    """Opens an action menu for a friend (stats, challenge, remove)."""
    theme = get_theme(state)
    db = load_db()
    email = state.get("current_user_email")
    friend = db.get("users", {}).get(friend_email)
    if not friend:
        show_friends_view(page, state)
        return

    ensure_social_defaults(friend)
    friend_theme_name = friend.get("settings", {}).get("theme", "classic")
    friend_theme = THEMES.get(friend_theme_name, THEMES["classic"])
    last_active_str = format_last_active(friend.get("last_active"))
    friend_name = friend.get("name", friend_email)
    avatar_letter = (friend_name or friend_email)[0].upper()

    active_duel = get_active_duel_with_friend(email, friend_email) if email else None
    duel_hint = ""
    can_resume = False
    can_play_opponent = False
    if active_duel:
        status = active_duel.get("status")
        if status == "pending_accept" and active_duel.get("opponent_email") == email:
            duel_hint = "Neue Herausforderung – annehmen oder ablehnen im Tab „Duelle“."
        elif active_duel.get("challenger_email") == email and status == "pending":
            duel_hint = "Duell fortsetzen – du hast die Herausforderung noch nicht beendet."
            can_resume = True
        elif active_duel.get("challenger_email") == email and status == "pending_accept":
            duel_hint = "Warte auf Annahme deiner Herausforderung."
        elif active_duel.get("challenger_email") == email:
            duel_hint = "Es läuft bereits ein Duell mit diesem Freund."
        elif status == "challenger_done" and active_duel.get("opponent_email") == email:
            duel_hint = "Deine Runde – jetzt antworten!"
            can_play_opponent = True
        else:
            duel_hint = "Offenes Duell – siehe Tab „Duelle“."

    dlg_ref = [None]  # mutable container so close_dlg can reference dlg before it's defined

    def close_dlg():
        if dlg_ref[0] is not None:
            _close_overlay(page, dlg_ref[0])

    def on_stats(e):
        close_dlg()
        show_friend_stats_view(page, state, friend_email)

    def on_challenge(e):
        close_dlg()
        if active_duel:
            if can_resume:
                start_duel_play(page, state, active_duel, role="challenger")
            elif can_play_opponent:
                start_duel_play(page, state, active_duel, role="opponent")
            else:
                state["friends_tab"] = 2
                show_friends_view(
                    page, state,
                    status_message=duel_hint or "Es läuft bereits ein Duell mit diesem Freund.",
                )
            return
        send_duel_challenge(page, state, friend_email)

    def on_remove(e):
        close_dlg()
        remove_friend(state, friend_email)
        show_friends_view(page, state, status_message=f"{friend_name} wurde entfernt.")

    def menu_button(label: str, color: str, handler, disabled: bool = False):
        return ft.Container(
            content=ft.Text(label, size=14, weight="bold", color="white" if not disabled else "#888888"),
            on_click=None if disabled else handler,
            ink=not disabled,
            bgcolor=color if not disabled else "#444444",
            border_radius=12,
            padding=ft.Padding(16, 12, 16, 12),
            alignment=ft.Alignment(0, 0),
            width=280,
        )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Container(
                width=44, height=44,
                border_radius=22,
                bgcolor=friend_theme["accent"],
                content=ft.Text(
                    avatar_letter,
                    size=22, weight="bold", color="white",
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment(0, 0),
            ),
            ft.Column([
                ft.Text(friend_name, size=18, weight="bold", color="white"),
                ft.Text(f"⏰ {last_active_str}", size=12, color="#AAAAAA"),
                ft.Text(f"🎨 {friend_theme.get('label', friend_theme_name)}", size=12, color=friend_theme["gold"]),
            ], spacing=2, expand=True),
        ], spacing=10),
        content=ft.Column([
            ft.Text("Was möchtest du tun?", size=13, color="#CCCCCC"),
            ft.Text(duel_hint, size=12, color=theme["gold"], visible=bool(duel_hint)),
            menu_button("📊 Statistik ansehen", theme["accent"], on_stats),
            menu_button(
                "⚔️ Deine Runde spielen" if can_play_opponent else (
                    "⚔️ Duell fortsetzen" if can_resume else "⚔️ Herausfordern"
                ),
                theme["gold"],
                on_challenge,
                disabled=bool(active_duel and not can_resume and not can_play_opponent),
            ),
            menu_button("❌ Freund entfernen", theme["danger"], on_remove),
        ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        actions=[
            ft.TextButton(
                "Schließen",
                on_click=lambda e: close_dlg(),
                style=ft.ButtonStyle(color="#CCCCCC"),
            ),
        ],
        bgcolor=theme["panel"],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref[0] = dlg
    open_page_dialog(page, dlg)


def accept_duel_challenge(page: ft.Page, state: dict, duel: dict):
    """Opponent accepts an incoming duel invite."""
    theme = get_theme(state)
    duel_id = _duel_document_id(duel)
    client = get_firestore_client()
    if not client or not duel_id:
        show_friends_view(page, state, status_message="Duell konnte nicht angenommen werden.")
        return
    try:
        client.collection("duels").document(duel_id).update({
            "status": "pending",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        })
        name = duel.get("challenger_name", duel.get("challenger_email", "Freund"))
        state["friends_tab"] = 2
        show_friends_view(
            page, state,
            status_message=f"Herausforderung von {name} angenommen! Dein Freund kann jetzt spielen.",
        )
    except Exception as ex:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Fehler: {ex}", color="white"),
            bgcolor=theme["danger"], open=True,
        )
        page.update()


def decline_duel_challenge(page: ft.Page, state: dict, duel: dict):
    """Opponent declines an incoming duel invite."""
    theme = get_theme(state)
    duel_id = _duel_document_id(duel)
    client = get_firestore_client()
    if not client or not duel_id:
        show_friends_view(page, state, status_message="Duell konnte nicht abgelehnt werden.")
        return
    try:
        client.collection("duels").document(duel_id).update({
            "status": "declined",
            "declined_at": datetime.now(timezone.utc).isoformat(),
        })
        name = duel.get("challenger_name", duel.get("challenger_email", "Freund"))
        state["friends_tab"] = 2
        show_friends_view(page, state, status_message=f"Herausforderung von {name} abgelehnt.")
    except Exception as ex:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Fehler: {ex}", color="white"),
            bgcolor=theme["danger"], open=True,
        )
        page.update()


def cancel_duel_challenge(page: ft.Page, state: dict, duel: dict):
    """Cancels an active duel (either player)."""
    theme = get_theme(state)
    _, email, _ = current_user_entry(state)
    duel_id = _duel_document_id(duel)
    if not email or email not in (duel.get("challenger_email"), duel.get("opponent_email")):
        show_friends_view(page, state, status_message="Duell konnte nicht abgebrochen werden.")
        return
    if duel.get("status") in ("completed", "declined", "cancelled"):
        state["friends_tab"] = 2
        show_friends_view(page, state, status_message="Dieses Duell ist bereits beendet.")
        return
    client = get_firestore_client()
    if not client or not duel_id:
        show_friends_view(page, state, status_message="Duell konnte nicht abgebrochen werden.")
        return
    try:
        client.collection("duels").document(duel_id).update({
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": email,
        })
        other = (
            duel.get("opponent_email")
            if duel.get("challenger_email") == email
            else duel.get("challenger_email")
        )
        db = load_db()
        other_name = db.get("users", {}).get(other or "", {}).get("name", other or "Gegner")
        state["friends_tab"] = 2
        show_friends_view(page, state, status_message=f"Duell gegen {other_name} abgebrochen.")
    except Exception as ex:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Fehler: {ex}", color="white"),
            bgcolor=theme["danger"], open=True,
        )
        page.update()


def send_duel_challenge(page: ft.Page, state: dict, opponent_email: str):
    """Creates a duel invite in Firestore; opponent must accept before challenger plays."""
    theme = get_theme(state)
    db, email, user = current_user_entry(state)
    if not email or not user:
        show_login_view(page, state)
        return

    client = get_firestore_client()
    if client is None:
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Duelle benötigen eine Firebase-Verbindung.", color="white"),
            bgcolor=theme["danger"], open=True,
        )
        page.update()
        return

    if get_active_duel_with_friend(email, opponent_email):
        show_friends_view(
            page, state,
            status_message="Mit diesem Freund läuft bereits ein Duell. Beende es zuerst.",
        )
        return

    age = state.get("player_age", "mid")
    duel_questions = build_duel_questions(age, 15)
    if not duel_questions:
        show_friends_view(page, state, status_message="Keine Duell-Fragen verfügbar.")
        return

    duel_id = f"duel_{int(time.time())}_{random.randint(1000,9999)}"
    duel_doc = {
        "id": duel_id,
        "challenger_email": email,
        "challenger_name": user.get("name", email),
        "opponent_email": opponent_email,
        "status": "pending_accept",  # pending_accept / pending / challenger_done / completed / declined
        "created_at": datetime.now(timezone.utc).isoformat(),
        "questions": duel_questions,
        "challenger_score": None,
        "challenger_money_level": -1,
        "opponent_score": None,
        "opponent_money_level": -1,
        "winner_email": None,
    }

    try:
        client.collection("duels").document(duel_id).set(duel_doc)
    except Exception as ex:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Fehler beim Erstellen des Duells: {ex}", color="white"),
            bgcolor=theme["danger"], open=True,
        )
        page.update()
        return

    opponent = db.get("users", {}).get(opponent_email, {})
    opponent_name = opponent.get("name", opponent_email)
    state["friends_tab"] = 2
    show_friends_view(
        page, state,
        status_message=f"Herausforderung an {opponent_name} gesendet! Warte auf Annahme.",
    )


def start_duel_play(page: ft.Page, state: dict, duel: dict, role: str):
    """Loads fresh duel data from Firestore and opens the quiz."""
    fresh = refresh_duel_from_firestore(duel)
    show_duel_play_view(page, state, fresh, role)


def show_duel_play_view(page: ft.Page, state: dict, duel: dict, role: str):
    """Shows a simplified quiz using the duel's questions. Role: 'challenger' or 'opponent'."""
    theme = get_theme(state)
    db, email, user = current_user_entry(state)
    duel = refresh_duel_from_firestore(duel)
    duel_status = duel.get("status", "")
    if role == "challenger" and duel_status not in ("pending",):
        show_friends_view(
            page, state,
            status_message="Das Duell wurde noch nicht angenommen oder ist bereits beendet.",
        )
        return
    if role == "opponent" and duel_status != "challenger_done":
        show_friends_view(
            page, state,
            status_message="Du kannst erst spielen, wenn dein Freund seine Runde beendet hat.",
        )
        return
    questions = normalize_duel_questions(duel.get("questions", []))
    if not questions:
        show_friends_view(
            page, state,
            status_message="Keine Fragen im Duell – bitte neue Herausforderung senden.",
        )
        return

    duel_state = {"idx": 0, "correct": 0, "done": False}
    if role == "opponent":
        opponent_name = duel.get("challenger_name", duel.get("challenger_email", "Herausforderer"))
    else:
        opp_email = duel.get("opponent_email", "?")
        opponent_name = db.get("users", {}).get(opp_email, {}).get("name", opp_email)

    page_width = page.width or 1100
    is_mobile = page_width < 720

    question_text = ft.Text("", size=16 if is_mobile else 18, weight="bold", color="white", text_align=ft.TextAlign.CENTER)
    feedback_text = ft.Text("", size=13, text_align=ft.TextAlign.CENTER)
    progress_text = ft.Text("", size=12, color="#AAAAAA")
    answer_buttons = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def load_question():
        idx = duel_state["idx"]
        if idx >= len(questions):
            finish_duel()
            return
        q = questions[idx]
        progress_text.value = f"Frage {idx + 1} / {len(questions)}"
        question_text.value = q["question"]
        feedback_text.value = ""
        answers = q["answers"]
        answer_buttons.controls.clear()
        for ans in answers:
            answer_buttons.controls.append(
                ft.Container(
                    content=ft.Text(ans, size=13 if is_mobile else 14, color="white", text_align=ft.TextAlign.CENTER),
                    on_click=lambda e, a=ans, qobj=q: check_answer(a, qobj),
                    bgcolor=theme["accent"],
                    border_radius=10,
                    padding=ft.Padding(14, 10, 14, 10),
                    alignment=ft.Alignment(0, 0),
                    width=None if is_mobile else 340,
                )
            )
        page.update()

    def check_answer(chosen: str, q: dict):
        correct_ans = q["correct"]
        if chosen == correct_ans:
            duel_state["correct"] += 1
            feedback_text.value = "✅ Richtig!"
            feedback_text.color = theme["success"]
        else:
            feedback_text.value = f"❌ Falsch! Richtig: {correct_ans}"
            feedback_text.color = theme["danger"]
        duel_state["idx"] += 1
        page.update()
        page.run_task(next_question_delayed)

    async def next_question_delayed():
        import asyncio
        await asyncio.sleep(1.2)
        load_question()

    def finish_duel():
        score = duel_state["correct"]
        total = len(questions)
        duel_id = _duel_document_id(duel)
        client = get_firestore_client()

        result_text = f"Du hast {score} von {total} Fragen richtig beantwortet!"

        if client and duel_id:
            try:
                doc_ref = client.collection("duels").document(duel_id)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    if role == "challenger":
                        doc_ref.update({
                            "challenger_score": score,
                            "challenger_money_level": score,
                            "status": "challenger_done",
                        })
                    else:
                        challenger_score = data.get("challenger_score", 0) or 0
                        winner = email if score >= challenger_score else data.get("challenger_email", "")
                        doc_ref.update({
                            "opponent_score": score,
                            "opponent_money_level": score,
                            "status": "completed",
                            "winner_email": winner,
                        })
                        if score > challenger_score:
                            result_text += f"\n🏆 Du gewinnst das Duell!"
                        elif score == challenger_score:
                            result_text += f"\n🤝 Unentschieden!"
                        else:
                            result_text += f"\n😔 Dein Gegner gewinnt mit {challenger_score} Punkten."
            except Exception as ex:
                print(f"Duel update error: {ex}")

        # Show result page
        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=theme["gradient"]),
                alignment=ft.Alignment(0, 0),
                content=ft.Column([
                    ft.Text("⚔️ Duell beendet!", size=30, weight="bold", color="white"),
                    ft.Text(result_text, size=16, color=theme["gold"], text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        content=ft.Text("Zurück zu Freunden", size=15, weight="bold", color="white"),
                        on_click=lambda e: show_friends_view(page, state),
                        bgcolor=theme["accent"],
                        border_radius=30,
                        padding=ft.Padding(24, 12, 24, 12),
                        alignment=ft.Alignment(0, 0),
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
                padding=30,
            )
        )
        page.update()

    content_w = min(int(page_width) - 32, 420)
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=theme["gradient"]),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Row([
                    ft.Text(f"⚔️ Duell vs. {opponent_name}", size=20 if is_mobile else 22, weight="bold", color="white", expand=True),
                    _duel_cancel_button(page, state, theme, duel),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                progress_text,
                ft.Container(
                    content=question_text,
                    bgcolor=theme["panel"],
                    border_radius=12,
                    padding=16 if is_mobile else 20,
                    width=content_w,
                    alignment=ft.Alignment(0, 0),
                    border=ft.border.Border.all(1, theme["border"]),
                ),
                ft.Container(content=answer_buttons, width=content_w),
                feedback_text,
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14, scroll=ft.ScrollMode.AUTO),
            padding=16 if is_mobile else 20,
        )
    )
    page.update()
    load_question()



def show_friends_view(page: ft.Page, state: dict, status_message: str = ""):
    theme = get_theme(state)
    db, email, user = current_user_entry(state)
    if not email or not user:
        show_login_view(page, state)
        return

    code_input = ft.TextField(
        label="Freundescode oder QR-Inhalt",
        width=300,
        bgcolor=theme["panel"],
        border_color=theme["border"],
        color="white",
    )
    status_text = ft.Text(
        status_message,
        size=13,
        text_align="center",
        color=theme["success"] if any(w in status_message for w in ["gesendet", "entfernt", "Freunde", "Annehm"]) else theme["danger"],
    )

    def send_request(e):
        message = save_friend_request(state, code_input.value)
        show_friends_view(e.page, state, message)

    friend_code = user.get("friend_code", "")
    qr_data = friend_qr_base64(friend_code)
    qr_control = (
        ft.Container(
            content=ft.Image(src=f"data:image/png;base64,{qr_data}", width=180, height=180),
            bgcolor="white",
            padding=10,
            border_radius=12,
        )
        if qr_data
        else ft.Text("QR-Code benötigt qrcode-Paket.", size=12, color="#CCCCCC", text_align="center")
    )

    # ---- Tab 1: Freunde & Anfragen ----
    incoming_controls = []
    for requester_email in user.get("friend_requests_in", []):
        requester = db.get("users", {}).get(requester_email, {})
        name = requester.get("name", requester_email)
        incoming_controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(f"👤 {name}", color="white", expand=True, size=14),
                    ft.TextButton(
                        "✅ Annehmen",
                        on_click=lambda e, req=requester_email: (respond_friend_request(state, req, True), show_friends_view(e.page, state)),
                        style=ft.ButtonStyle(color=theme["success"]),
                    ),
                    ft.TextButton(
                        "❌ Ablehnen",
                        on_click=lambda e, req=requester_email: (respond_friend_request(state, req, False), show_friends_view(e.page, state)),
                        style=ft.ButtonStyle(color=theme["danger"]),
                    ),
                ], alignment=ft.MainAxisAlignment.START),
                bgcolor=theme["panel"],
                border_radius=10,
                padding=ft.Padding(10, 8, 10, 8),
                border=ft.border.Border.all(1, theme["border"]),
            )
        )
    if not incoming_controls:
        incoming_controls.append(ft.Text("Keine offenen Anfragen.", size=12, color="#CCCCCC"))

    friend_controls = []
    for f_email in user.get("friends", []):
        friend = db.get("users", {}).get(f_email)
        if not friend:
            continue
        ensure_social_defaults(friend)
        last_active_str = format_last_active(friend.get("last_active"))
        la = friend.get("last_active")
        is_online = False
        if la:
            try:
                dt = datetime.fromisoformat(la)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                is_online = (datetime.now(timezone.utc) - dt).total_seconds() < 300
            except Exception:
                pass
        dot_color = theme["success"] if is_online else "#666666"

        friend_controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=dot_color, margin=ft.Margin(0, 0, 8, 0)),
                    ft.Column([
                        ft.Text(friend.get("name", f_email), size=15, color="white", weight="bold"),
                        ft.Text(last_active_str, size=11, color="#AAAAAA"),
                    ], spacing=2, expand=True),
                    ft.Text("👤 Profil", size=12, color=theme["gold"]),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=lambda e, fe=f_email: show_friend_profile_popup(page, state, fe),
                ink=True,
                bgcolor=theme["accent"],
                border_radius=12,
                padding=ft.Padding(12, 10, 12, 10),
                margin=ft.Margin(0, 0, 0, 4),
                border=ft.border.Border.all(1, theme["border"]),
            )
        )
    if not friend_controls:
        friend_controls.append(ft.Text("Noch keine Freunde. Scanne einen QR-Code!", size=12, color="#CCCCCC"))

    tab_friends = ft.Column([
        ft.Text("🔗 Dein Freundescode", size=15, weight="bold", color=theme["gold"]),
        ft.Row([ft.Text(friend_code, size=20, weight="bold", color="white", selectable=True)], alignment=ft.MainAxisAlignment.CENTER),
        qr_control,
        code_input,
        ft.Container(
            content=ft.Text("Anfrage senden", size=14, weight="bold", color="white"),
            on_click=send_request,
            ink=True,
            bgcolor=theme["success"],
            border_radius=30,
            padding=ft.Padding(20, 9, 20, 9),
            alignment=ft.Alignment(0, 0),
            width=200,
        ),
        status_text,
        ft.Divider(color=theme["border"]),
        ft.Text("📬 Offene Anfragen", size=15, weight="bold", color=theme["gold"]),
        *incoming_controls,
        ft.Divider(color=theme["border"]),
        ft.Text("👥 Deine Freunde", size=15, weight="bold", color=theme["gold"]),
        *friend_controls,
    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ---- Tab 2: Wochenranking ----
    week_key = get_current_week_key()
    all_participants = [email] + user.get("friends", [])
    ranking_data = []
    for p_email in all_participants:
        p_user = db.get("users", {}).get(p_email)
        if not p_user:
            continue
        ensure_social_defaults(p_user)
        ws = p_user.get("weekly_stats", {})
        if ws.get("week") != week_key:
            weekly_lvl = 0
            weekly_wins = 0
        else:
            weekly_lvl = ws.get("money_level", 0)
            weekly_wins = ws.get("games_won", 0)
        ranking_data.append({
            "email": p_email,
            "name": p_user.get("name", p_email),
            "level": weekly_lvl,
            "wins": weekly_wins,
            "is_me": p_email == email,
        })
    ranking_data.sort(key=lambda x: (x["level"], x["wins"]), reverse=True)

    ranking_rows = []
    for rank_i, entry in enumerate(ranking_data, 1):
        medal = _medal(rank_i)
        bg = theme["accent"] if entry["is_me"] else theme["panel"]
        border_col = theme["gold"] if entry["is_me"] else theme["border"]
        ranking_rows.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(medal, size=20, width=36),
                    ft.Text(
                        entry["name"] + (" (Du)" if entry["is_me"] else ""),
                        size=14, color="white", expand=True,
                        weight="bold" if entry["is_me"] else "normal",
                    ),
                    ft.Column([
                        ft.Text(f"Lvl {entry['level']}", size=13, color=theme["gold"], weight="bold"),
                        ft.Text(f"{entry['wins']} Siege", size=11, color="#AAAAAA"),
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=bg,
                border_radius=10,
                padding=ft.Padding(12, 8, 12, 8),
                border=ft.border.Border.all(1, border_col),
                margin=ft.Margin(0, 0, 0, 4),
            )
        )
    if not ranking_rows:
        ranking_rows.append(ft.Text("Noch keine Daten diese Woche.", size=13, color="#CCCCCC"))

    tab_ranking = ft.Column([
        ft.Text("🏆 Wochenranking", size=18, weight="bold", color=theme["gold"]),
        ft.Text(f"Woche: {week_key}", size=12, color="#AAAAAA"),
        ft.Divider(color=theme["border"]),
        *ranking_rows,
    ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ---- Tab 3: Duelle ----
    client = get_firestore_client()
    incoming_invites = []
    opponent_turn_duels = []
    opponent_waiting_duels = []
    my_turn_duels = []
    waiting_accept_duels = []
    finished_duels = []
    if client:
        try:
            for doc in client.collection("duels").where("opponent_email", "==", email).stream():
                d = doc.to_dict() or {}
                d["id"] = doc.id
                status = d.get("status")
                if status == "pending_accept":
                    incoming_invites.append(d)
                elif status == "challenger_done":
                    opponent_turn_duels.append(d)
                elif status == "pending":
                    opponent_waiting_duels.append(d)
                elif status == "completed":
                    finished_duels.append(d)
            for doc in client.collection("duels").where("challenger_email", "==", email).stream():
                d = doc.to_dict() or {}
                d["id"] = doc.id
                status = d.get("status")
                if status == "pending_accept":
                    waiting_accept_duels.append(d)
                elif status == "pending":
                    my_turn_duels.append(d)
                elif status == "completed":
                    if d not in finished_duels:
                        finished_duels.append(d)
        except Exception as ex:
            print(f"Duel load error: {ex}")

    open_duel_controls = []

    for d in incoming_invites:
        challenger_name = d.get("challenger_name", d.get("challenger_email", "?"))
        open_duel_controls.append(
            _duel_open_card(
                ft.Column([
                    ft.Text(f"📩 Herausforderung von {challenger_name}", size=13, color="white", weight="bold"),
                    ft.Text("15 Fragen – erst nach Annahme spielt dein Freund.", size=11, color="#AAAAAA"),
                    ft.Row([
                        ft.Container(
                            content=ft.Text("✅ Annehmen", size=13, color="white", weight="bold"),
                            on_click=lambda e, duel=d: accept_duel_challenge(page, state, duel),
                            bgcolor=theme["success"],
                            border_radius=20,
                            padding=ft.Padding(14, 6, 14, 6),
                        ),
                        ft.Container(
                            content=ft.Text("❌ Ablehnen", size=13, color="white", weight="bold"),
                            on_click=lambda e, duel=d: decline_duel_challenge(page, state, duel),
                            bgcolor=theme["danger"],
                            border_radius=20,
                            padding=ft.Padding(14, 6, 14, 6),
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=8, wrap=True),
                ], spacing=6, tight=True),
                theme,
                theme["gold"],
            )
        )

    for d in opponent_waiting_duels:
        challenger_name = d.get("challenger_name", d.get("challenger_email", "?"))
        wait_rows = [
            ft.Text(f"⏳ {challenger_name} spielt noch", size=13, color="white", weight="bold"),
            ft.Text("Warte, bis dein Freund die Runde beendet hat.", size=11, color="#AAAAAA"),
        ]
        if d.get("challenger_email") == email:
            wait_rows.append(ft.Row([_duel_cancel_button(page, state, theme, d)], spacing=8))
        open_duel_controls.append(
            _duel_open_card(ft.Column(wait_rows, spacing=6, tight=True), theme)
        )

    for d in opponent_turn_duels:
        challenger_name = d.get("challenger_name", d.get("challenger_email", "?"))
        open_duel_controls.append(
            _duel_open_card(
                ft.Column([
                    ft.Text(f"⚔️ Deine Runde vs. {challenger_name}", size=13, color="white", weight="bold"),
                    ft.Text(f"Gegner: {d.get('challenger_score', '?')} Punkte", size=11, color="#AAAAAA"),
                    ft.Row([
                        ft.Container(
                            content=ft.Text("Spielen", size=13, color="white", weight="bold"),
                            on_click=lambda e, duel=d: start_duel_play(page, state, duel, "opponent"),
                            bgcolor=theme["gold"],
                            border_radius=20,
                            padding=ft.Padding(14, 6, 14, 6),
                        ),
                        _duel_cancel_button(page, state, theme, d),
                    ], spacing=8, wrap=True),
                ], spacing=6, tight=True),
                theme,
                theme["gold"],
            )
        )

    for d in my_turn_duels:
        opp_email = d.get("opponent_email", "?")
        opp_name = db.get("users", {}).get(opp_email, {}).get("name", opp_email)
        open_duel_controls.append(
            _duel_open_card(
                ft.Column([
                    ft.Text(f"⚔️ Dein Duell vs. {opp_name}", size=13, color="white", weight="bold"),
                    ft.Text("Angenommen – tippe auf Spielen und starte deine 15 Fragen.", size=11, color="#AAAAAA"),
                    ft.Row([
                        ft.Container(
                            content=ft.Text("Spielen", size=13, color="white", weight="bold"),
                            on_click=lambda e, duel=d: start_duel_play(page, state, duel, "challenger"),
                            bgcolor=theme["gold"],
                            border_radius=20,
                            padding=ft.Padding(14, 6, 14, 6),
                        ),
                        _duel_cancel_button(page, state, theme, d),
                    ], spacing=8, wrap=True),
                ], spacing=6, tight=True),
                theme,
                theme["accent_2"],
            )
        )

    for d in waiting_accept_duels:
        opp_email = d.get("opponent_email", "?")
        opp_name = db.get("users", {}).get(opp_email, {}).get("name", opp_email)
        open_duel_controls.append(
            _duel_open_card(
                ft.Column([
                    ft.Text(f"⏳ Warte auf {opp_name}", size=13, color="white", weight="bold"),
                    ft.Text("Herausforderung gesendet – noch nicht angenommen.", size=11, color="#AAAAAA"),
                    ft.Row([_duel_cancel_button(page, state, theme, d)], spacing=8),
                ], spacing=6, tight=True),
                theme,
            )
        )

    if not open_duel_controls:
        open_duel_controls.append(ft.Text("Keine offenen Herausforderungen.", size=12, color="#CCCCCC"))

    finished_duel_controls = []
    for d in finished_duels[-5:]:
        winner_email = d.get("winner_email", "")
        i_won = winner_email == email
        draw = d.get("challenger_score") == d.get("opponent_score")
        result_icon = "🤝" if draw else ("🏆" if i_won else "😔")
        result_color = theme["gold"] if draw else (theme["success"] if i_won else theme["danger"])
        other = d.get("opponent_email") if d.get("challenger_email") == email else d.get("challenger_email")
        other_name = db.get("users", {}).get(other or "", {}).get("name", other or "?")
        my_score_key = "challenger_score" if d.get("challenger_email") == email else "opponent_score"
        opp_score_key = "opponent_score" if d.get("challenger_email") == email else "challenger_score"
        finished_duel_controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(result_icon, size=22, width=32),
                    ft.Column([
                        ft.Text(f"vs. {other_name}", size=13, color="white"),
                        ft.Text(f"Du: {d.get(my_score_key, '?')} · Gegner: {d.get(opp_score_key, '?')}", size=11, color="#AAAAAA"),
                    ], spacing=2, expand=True),
                ]),
                bgcolor=theme["panel"],
                border_radius=10,
                padding=ft.Padding(10, 8, 10, 8),
                border=ft.border.Border.all(1, result_color),
                margin=ft.Margin(0, 0, 0, 4),
            )
        )
    if not finished_duel_controls:
        finished_duel_controls.append(ft.Text("Noch keine abgeschlossenen Duelle.", size=12, color="#CCCCCC"))

    tab_duels = ft.Column([
        ft.Text("⚔️ Offene Herausforderungen", size=15, weight="bold", color=theme["gold"]),
        ft.Column(open_duel_controls, spacing=0, tight=True),
        ft.Divider(height=1, color=theme["border"]),
        ft.Text("📜 Letzte Duelle", size=15, weight="bold", color=theme["gold"]),
        ft.Column(finished_duel_controls, spacing=0, tight=True),
        ft.Divider(height=1, color=theme["border"]),
        ft.Text("ℹ️ Freund antippen → Herausfordern · Annahme im Tab oben", size=11, color="#888888", text_align=ft.TextAlign.CENTER),
    ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)

    # ---- Tab Bar ----
    tab_contents = [tab_friends, tab_ranking, tab_duels]
    tab_labels = ["👥 Freunde", "🏆 Ranking", "⚔️ Duelle"]
    selected_tab = state.get("friends_tab", 0)

    content_container = ft.Container(
        content=tab_contents[selected_tab],
        bgcolor=theme["panel"],
        border_radius=16,
        padding=20,
        border=ft.border.Border.all(2, theme["border"]),
        width=460,
    )

    def switch_tab(idx):
        state["friends_tab"] = idx
        content_container.content = tab_contents[idx]
        for i, btn in enumerate(tab_buttons):
            btn.bgcolor = theme["accent"] if i == idx else theme["panel"]
            btn.border = ft.border.Border.all(2, theme["gold"] if i == idx else theme["border"])
        page.update()

    tab_buttons = []
    for idx, label in enumerate(tab_labels):
        is_sel = idx == selected_tab
        btn = ft.Container(
            content=ft.Text(label, size=13, color="white", weight="bold" if is_sel else "normal"),
            on_click=lambda e, i=idx: switch_tab(i),
            bgcolor=theme["accent"] if is_sel else theme["panel"],
            border_radius=20,
            padding=ft.Padding(14, 7, 14, 7),
            border=ft.border.Border.all(2, theme["gold"] if is_sel else theme["border"]),
        )
        tab_buttons.append(btn)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, -0.05),
            content=ft.Column([
                ft.Text("Freunde", size=28, weight="bold", color=theme_txt(theme, "primary")),
                ft.Row(tab_buttons, alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                content_container,
                ft.TextButton(
                    "← Zurück",
                    on_click=lambda e: show_settings_view(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14,
               scroll=ft.ScrollMode.AUTO),
            padding=20,
        )
    )
    page.update()



def show_friend_stats_view(page: ft.Page, state: dict, friend_email: str):
    theme = get_theme(state)
    db = load_db()
    friend = db.get("users", {}).get(friend_email)
    if not friend:
        show_friends_view(page, state)
        return

    stats = friend.get("stats", {})
    ensure_stats_defaults(stats)
    games = stats.get("games_played", 0)
    card = _stats_card(
        f"Statistik: {friend.get('name', friend_email)}",
        [
            ("Spiele", str(games)),
            ("Siege / Niederlagen", f"{stats.get('games_won', 0)} / {stats.get('games_lost', 0)}"),
            ("Winrate", _pct(stats.get("games_won", 0), games)),
            ("Trefferquote", _pct(stats.get("correct_answers", 0), stats.get("questions_answered", 0))),
            ("Rekord", stats.get("highest_money", "0 €")),
            ("Höchste Frage", _level_label(stats.get("highest_money_level", -1))),
            ("Beste Siegesserie", str(stats.get("best_streak", 0))),
        ],
        theme,
        theme["success"],
        360,
    )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Freundesstatistik", size=30, weight="bold", color="white"),
                card,
                ft.TextButton(
                    "Zurück",
                    on_click=lambda e: show_friends_view(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14),
        )
    )
    page.update()


def show_edit_profile_view(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    if not email:
        open_main_menu(page, state)
        return
        
    ensure_user_settings(db, email)
    save_db(db)
    theme = get_theme(state)
    user_info = db["users"].get(email, {})
    current_name = user_info.get("name", "")
    current_theme = user_info.get("settings", {}).get("theme", "classic")
    
    name_input = ft.TextField(
        label="Dein Anzeigename",
        value=current_name,
        width=300,
        bgcolor=theme["panel"],
        border_color=theme["border"],
        color="white",
    )

    theme_dropdown = ft.Dropdown(
        label="Design",
        value=current_theme,
        width=300,
        bgcolor=theme["panel"],
        border_color=theme["border"],
        color="white",
        options=[
            ft.dropdown.Option(key=key, text=value["label"])
            for key, value in THEMES.items()
        ],
    )
    
    status_text = ft.Text("", size=14, text_align="center")
    
    def on_save(e):
        new_name = name_input.value.strip()
        if not new_name:
            status_text.value = "⚠️ Name darf nicht leer sein."
            status_text.color = "red"
            page.update()
            return
            
        db = load_db()
        if email in db["users"]:
            db["users"][email]["name"] = new_name
            ensure_user_settings(db, email)
            selected_theme = theme_dropdown.value if theme_dropdown.value in THEMES else "classic"
            db["users"][email]["settings"]["theme"] = selected_theme
            save_db(db)
            state["theme"] = selected_theme
            status_text.value = "✓ Erfolgreich gespeichert!"
            status_text.color = "#2ECC71"
            page.update()
            
            async def back_delay():
                await asyncio.sleep(1.0)
                open_main_menu(page, state)
            page.run_task(back_delay)
            
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("✏️ Profil bearbeiten", size=30, weight="bold", color="white"),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"Konto: {email}", size=13, color="#E0D0F0"),
                        name_input,
                        theme_dropdown,
                        ft.Container(
                            content=ft.Text("Speichern", size=16, weight="bold", color="white"),
                            on_click=on_save,
                            bgcolor=theme["success"],
                            border_radius=30,
                            padding=ft.Padding(30, 12, 30, 12),
                            alignment=ft.Alignment(0, 0),
                            width=150,
                        ),
                        status_text,
                    ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=theme["panel"],
                    border_radius=16,
                    padding=24,
                    border=ft.border.Border.all(2, theme["border"]),
                    width=360,
                ),
                ft.Container(height=10),
                ft.Row([
                    ft.TextButton(
                        "← Zurück",
                        on_click=lambda e: open_main_menu(e.page, state),
                        style=ft.ButtonStyle(color="white"),
                    ),
                    ft.TextButton(
                        "🚪 Abmelden",
                        on_click=lambda e: page.run_task(_do_logout, page, state),
                        style=ft.ButtonStyle(color="#FF6B6B"),
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14)
        )
    )
    page.update()


# ---------- Statistics Screen ----------
def show_stats_legacy(page: ft.Page, state: dict):
    db = load_db()
    theme = get_theme(state)
    page_width = page.width or page.window.width or 1100
    is_mobile = page_width < 720
    card_width = None if is_mobile else 320
    
    g_stats = db.get("global_stats", {})
    g_games = g_stats.get("games_played", 0)
    g_correct = g_stats.get("correct_answers", 0)
    g_answered = g_stats.get("questions_answered", 0)
    g_money = g_stats.get("highest_money", "0 €")
    g_rate = f"{int(g_correct / g_answered * 100)}%" if g_answered > 0 else "0%"
    
    global_card = ft.Container(
        content=ft.Column([
            ft.Text("🌍 Globale Statistik", size=18, weight="bold", color=theme["gold"]),
            ft.Divider(color=theme["border"], thickness=1),
            _stat_row("🎮 Spiele gesamt", str(g_games)),
            _stat_row("📝 Beantwortete Fragen", str(g_answered)),
            _stat_row("✅ Richtige Antworten", f"{g_correct} ({g_rate})"),
            _stat_row("🏆 Höchster Gewinn", g_money),
        ], spacing=12),
        bgcolor=theme["panel"],
        border_radius=16,
        padding=20,
        border=ft.border.Border.all(2, theme["border"]),
        width=card_width,
    )
    
    email = state.get("current_user_email")
    if email and email in db["users"]:
        u_info = db["users"][email]
        u_name = u_info.get("name", email)
        u_stats = u_info.get("stats", {})
        u_games = u_stats.get("games_played", 0)
        u_correct = u_stats.get("correct_answers", 0)
        u_answered = u_stats.get("questions_answered", 0)
        u_money = u_stats.get("highest_money", "0 €")
        u_rate = f"{int(u_correct / u_answered * 100)}%" if u_answered > 0 else "0%"
        
        personal_card = ft.Container(
            content=ft.Column([
                ft.Text(f"👤 Statistik: {u_name}", size=18, weight="bold", color="#2ECC71"),
                ft.Text(email, size=11, color="#E0D0F0"),
                ft.Divider(color="#2ECC71", thickness=1),
                _stat_row("🎮 Deine Spiele", str(u_games)),
                _stat_row("📝 Beantwortete Fragen", str(u_answered)),
                _stat_row("✅ Richtige Antworten", f"{u_correct} ({u_rate})"),
                _stat_row("🏆 Dein Rekord", u_money),
            ], spacing=12),
            bgcolor=theme["panel"],
            border_radius=16,
            padding=20,
            border=ft.border.Border.all(2, theme["success"]),
            width=card_width,
        )
    else:
        personal_card = ft.Container(
            content=ft.Column([
                ft.Text("👤 Persönliche Statistik", size=18, weight="bold", color="#CCCCCC"),
                ft.Divider(color="#CCCCCC", thickness=1),
                ft.Text(
                    "Melde dich im Hauptmenü an, um deine persönlichen Statistiken dauerhaft zu sichern!",
                    size=13,
                    color="#CCCCCC",
                    text_align="center",
                ),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Text("🔑 Anmelden", size=16, weight="bold", color="white"),
                    on_click=lambda e: show_login_view(e.page, state),
                    bgcolor=theme["accent"],
                    visible=False,
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=200,
                ),
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=theme["panel"],
            border_radius=16,
            padding=20,
            border=ft.border.Border.all(2, "#CCCCCC"),
            width=card_width,
        )
        
    stats_cards = ft.Column(
        [global_card, personal_card],
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    ) if is_mobile else ft.Row([
        global_card,
        ft.Container(width=16),
        personal_card,
    ], alignment=ft.MainAxisAlignment.CENTER)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("📊 Statistiken", size=28 if is_mobile else 32, weight="bold", color="white"),
                ft.Container(height=10),
                stats_cards,
                ft.Container(height=20),
                ft.Container(
                    content=ft.Text("← Zurück", size=16, weight="bold", color="white"),
                    on_click=lambda e: open_main_menu(e.page, state),
                    bgcolor=theme["accent"],
                    border_radius=50,
                    padding=ft.Padding(30, 12, 30, 12),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14,
               scroll=ft.ScrollMode.AUTO),
            padding=ft.Padding(12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20),
        )
    )
    page.update()


def _pct(part: int, total: int) -> str:
    return f"{int(part / total * 100)}%" if total else "0%"


def _avg_level_label(stats: dict) -> str:
    games = stats.get("games_played", 0)
    if not games:
        return "0"
    return f"Frage {stats.get('total_money_level', 0) / games:.1f}"


def _level_label(level_idx: int) -> str:
    return "Keine" if level_idx < 0 else f"Frage {level_idx + 1}"


def _format_history_date(value: str) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except Exception:
        return value[:10]


def _stats_card(title: str, rows: list[tuple[str, str]], theme: dict, accent: str, width=None) -> ft.Control:
    return ft.Container(
        content=ft.Column([
            ft.Text(title, size=18, weight="bold", color=accent),
            ft.Divider(color=theme["border"], thickness=1),
            *[_stat_row(label, value) for label, value in rows],
        ], spacing=10),
        bgcolor=theme["panel"],
        border_radius=16,
        padding=20,
        border=ft.border.Border.all(2, accent),
        width=width,
    )


def _recent_games_card(history: list[dict], theme: dict, width=None) -> ft.Control:
    recent = list(reversed(history[-8:]))
    if recent:
        rows = [
            _stat_row(
                f"{_format_history_date(game.get('played_at', ''))} - {'Sieg' if game.get('won') else 'Aus'}",
                f"{game.get('money', '0 €')} - {game.get('correct_answers', 0)}/{game.get('questions_answered', 0)}",
            )
            for game in recent
        ]
    else:
        rows = [ft.Text("Noch keine abgeschlossenen Spiele.", size=13, color="#CCCCCC", text_align="center")]

    return ft.Container(
        content=ft.Column([
            ft.Text("Letzte Spiele", size=18, weight="bold", color=theme["accent_2"]),
            ft.Divider(color=theme["border"], thickness=1),
            *rows,
        ], spacing=10),
        bgcolor=theme["panel"],
        border_radius=16,
        padding=20,
        border=ft.border.Border.all(2, theme["accent_2"]),
        width=width,
    )


def show_stats(page: ft.Page, state: dict):
    db = load_db()
    theme = get_theme(state)
    page_width = page.width or page.window.width or 1100
    is_mobile = page_width < 720
    card_width = None if is_mobile else 340

    g_stats = db.get("global_stats", {})
    ensure_stats_defaults(g_stats)
    global_card = _stats_card(
        "Globale Statistik",
        [
            ("Spiele gesamt", str(g_stats.get("games_played", 0))),
            ("Siege / Niederlagen", f"{g_stats.get('games_won', 0)} / {g_stats.get('games_lost', 0)}"),
            ("Trefferquote", _pct(g_stats.get("correct_answers", 0), g_stats.get("questions_answered", 0))),
            ("Höchster Gewinn", g_stats.get("highest_money", "0 €")),
            ("Höchste Frage", _level_label(g_stats.get("highest_money_level", -1))),
            ("Durchschnitt", _avg_level_label(g_stats)),
        ],
        theme,
        theme["gold"],
        card_width,
    )

    email = state.get("current_user_email")
    if email and email in db.get("users", {}):
        u_info = db["users"][email]
        u_name = u_info.get("name", email)
        u_stats = u_info.get("stats", {})
        ensure_stats_defaults(u_stats)
        history = u_info.get("game_history", [])
        games = u_stats.get("games_played", 0)

        cards = [
            global_card,
            _stats_card(
                f"Statistik: {u_name}",
                [
                    ("Konto", email),
                    ("Deine Spiele", str(games)),
                    ("Siege / Niederlagen", f"{u_stats.get('games_won', 0)} / {u_stats.get('games_lost', 0)}"),
                    ("Winrate", _pct(u_stats.get("games_won", 0), games)),
                    ("Dein Rekord", u_stats.get("highest_money", "0 €")),
                    ("Höchste Frage", _level_label(u_stats.get("highest_money_level", -1))),
                ],
                theme,
                theme["success"],
                card_width,
            ),
            _stats_card(
                "Antworten",
                [
                    ("Beantwortet", str(u_stats.get("questions_answered", 0))),
                    ("Richtig", str(u_stats.get("correct_answers", 0))),
                    ("Falsch", str(u_stats.get("wrong_answers", 0))),
                    ("Trefferquote", _pct(u_stats.get("correct_answers", 0), u_stats.get("questions_answered", 0))),
                    ("Durchschnitt richtig", f"{u_stats.get('correct_answers', 0) / games:.1f}" if games else "0"),
                    ("Durchschnitt Frage", _avg_level_label(u_stats)),
                ],
                theme,
                theme["accent"],
                card_width,
            ),
            _stats_card(
                "Rekorde",
                [
                    ("Beste Siegesserie", str(u_stats.get("best_streak", 0))),
                    ("Aktuelle Siegesserie", str(u_stats.get("current_streak", 0))),
                    ("Perfekte Spiele", str(u_stats.get("perfect_games", 0))),
                    ("Joker genutzt", str(u_stats.get("jokers_used", 0))),
                    ("Verlauf gespeichert", str(len(history))),
                ],
                theme,
                theme["accent_2"],
                card_width,
            ),
            _recent_games_card(history, theme, card_width),
        ]
    else:
        cards = [
            global_card,
            ft.Container(
                content=ft.Column([
                    ft.Text("Persönliche Statistik", size=18, weight="bold", color="#CCCCCC"),
                    ft.Divider(color="#CCCCCC", thickness=1),
                    ft.Text(
                        "Melde dich im Hauptmenü an, um deine persönlichen Statistiken dauerhaft zu sichern!",
                        size=13,
                        color="#CCCCCC",
                        text_align="center",
                    ),
                ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=theme["panel"],
                border_radius=16,
                padding=20,
                border=ft.border.Border.all(2, "#CCCCCC"),
                width=card_width,
            ),
        ]

    if is_mobile:
        stats_cards = ft.Column(cards, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    else:
        rows = [
            ft.Row(cards[i:i + 2], alignment=ft.MainAxisAlignment.CENTER, spacing=16)
            for i in range(0, len(cards), 2)
        ]
        stats_cards = ft.Column(rows, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("Statistiken", size=28 if is_mobile else 32, weight="bold", color="white"),
                ft.Container(height=10),
                stats_cards,
                ft.Container(height=20),
                ft.Container(
                    content=ft.Text("Zurück", size=16, weight="bold", color="white"),
                    on_click=lambda e: open_main_menu(e.page, state),
                    bgcolor=theme["accent"],
                    border_radius=50,
                    padding=ft.Padding(30, 12, 30, 12),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14,
               scroll=ft.ScrollMode.AUTO),
            padding=ft.Padding(12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20),
        )
    )
    page.update()


def _stat_row(label: str, value: str) -> ft.Control:
    return ft.Row([
        ft.Text(label, size=16, color="#CCCCCC", expand=True),
        ft.Text(value, size=16, weight="bold", color="#FFD700"),
    ])


# ---------- Entry Point ----------
# ---------- Mega-Update Screens ----------

def show_shop_screen(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    if not email or email not in db["users"]:
        open_main_menu(page, state)
        return
    user = db["users"][email]
    theme = get_theme(state)
    
    async def flash_insufficient_funds(btn):
        original_text = btn.text
        original_bgcolor = btn.bgcolor
        original_color = btn.color
        
        btn.text = "Nicht genügend Geld"
        btn.bgcolor = "red"
        btn.color = "white"
        btn.update()
        
        import asyncio
        await asyncio.sleep(1.5)
        
        btn.text = original_text
        btn.bgcolor = original_bgcolor
        btn.color = original_color
        try:
            btn.update()
        except Exception:
            pass

    async def on_buy_theme(e, item):
        price = item["price"]
        if user["stats"].get("wallet_balance", 0) >= price:
            user["stats"]["wallet_balance"] -= price
            user.setdefault("unlocked_themes", ["classic", "neon_nexus"]).append(item["id"])
            save_db(db)
            build_shop()
        else:
            await flash_insufficient_funds(e.control)

    async def on_buy_title(e, item):
        price = item["price"]
        if user["stats"].get("wallet_balance", 0) >= price:
            user["stats"]["wallet_balance"] -= price
            user.setdefault("unlocked_titles", ["Neuling"]).append(item["id"])
            save_db(db)
            build_shop()
        else:
            await flash_insufficient_funds(e.control)

    def on_equip_theme(e, theme_id):
        user["settings"]["theme"] = theme_id
        state["settings"]["theme"] = theme_id
        save_db(db)
        show_shop_screen(page, state)

    def on_equip_title(e, title_id):
        user["active_title"] = title_id
        save_db(db)
        build_shop()

    def build_shop():
        unlocked_themes = user.get("unlocked_themes", ["classic", "neon_nexus"])
        unlocked_titles = user.get("unlocked_titles", ["Neuling"])
        current_theme = user.get("settings", {}).get("theme", "classic")
        current_title = user.get("active_title", "Neuling")
        wallet = user["stats"].get("wallet_balance", 0)

        theme_cards = []
        for t in SHOP_CATALOG["themes"]:
            is_unlocked = t["id"] in unlocked_themes
            is_equipped = current_theme == t["id"]
            if is_equipped:
                btn = ft.ElevatedButton("Ausgerüstet", disabled=True, color="green")
            elif is_unlocked:
                btn = ft.ElevatedButton("Ausrüsten", on_click=lambda e, tid=t["id"]: on_equip_theme(e, tid))
            else:
                btn = ft.ElevatedButton(f"{t['price']} € Kaufen", on_click=lambda e, itm=t: page.run_task(on_buy_theme, e, itm))
            
            theme_cards.append(ft.Container(
                content=ft.Row([ft.Text(t["name"], size=16, weight="bold", color=theme_txt(theme, "primary")), btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10, border_radius=8, bgcolor=theme["panel"], border=ft.border.Border.all(1, theme["border"])
            ))

        title_cards = []
        for t in SHOP_CATALOG["titles"]:
            is_unlocked = t["id"] in unlocked_titles
            is_equipped = current_title == t["id"]
            if is_equipped:
                btn = ft.ElevatedButton("Ausgerüstet", disabled=True, color="green")
            elif is_unlocked:
                btn = ft.ElevatedButton("Ausrüsten", on_click=lambda e, tid=t["id"]: on_equip_title(e, tid))
            else:
                btn = ft.ElevatedButton(f"{t['price']} € Kaufen", on_click=lambda e, itm=t: page.run_task(on_buy_title, e, itm))
            
            title_cards.append(ft.Container(
                content=ft.Row([ft.Text(t["name"], size=16, weight="bold", color=theme_txt(theme, "primary")), btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10, border_radius=8, bgcolor=theme["panel"], border=ft.border.Border.all(1, theme["border"])
            ))

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, -1),
                    end=ft.Alignment(1, 1),
                    colors=theme["gradient"],
                ),
                content=ft.Container(
                    padding=20,
                    content=ft.Column([
                        ft.Row([
                            ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                            ft.Text("In-Game Shop", size=24, weight="bold", color="white"),
                        ]),
                        ft.Text(f"Kontostand: {wallet} €", size=20, weight="bold", color=theme["gold"]),
                        ft.Divider(color=theme["border"]),
                        ft.Text("🎨 Designs", size=20, weight="bold", color="white"),
                        ft.Column(theme_cards, scroll=ft.ScrollMode.AUTO, height=200),
                        ft.Divider(color=theme["border"]),
                        ft.Text("🏷️ Titel", size=20, weight="bold", color="white"),
                        ft.Column(title_cards, scroll=ft.ScrollMode.AUTO, height=200),
                    ])
                )
            )
        )
        page.update()
    
    build_shop()


def show_achievements_screen(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    if not email or email not in db["users"]:
        open_main_menu(page, state)
        return
    user = db["users"][email]
    theme = get_theme(state)

    # Hardcoded achievements for now (can be expanded)
    achievements = [
        {"id": "purist", "name": "Purist", "desc": "Ein Spiel gewinnen, ohne Joker zu nutzen."},
        {"id": "millionaire", "name": "Millionär", "desc": "Die Million gewinnen."},
        {"id": "marathon", "name": "Marathon", "desc": "10 Spiele insgesamt gespielt."},
    ]
    unlocked = user.get("unlocked_achievements", [])

    cards = []
    for a in achievements:
        is_unlocked = a["id"] in unlocked
        icon = "🏆" if is_unlocked else "🔒"
        color = theme["gold"] if is_unlocked else "gray"
        
        cards.append(ft.Container(
            content=ft.Row([
                ft.Text(icon, size=30),
                ft.Column([
                    ft.Text(a["name"], size=16, weight="bold", color=color),
                    ft.Text(a["desc"], size=12, color=theme_txt(theme, "muted")),
                ])
            ]),
            padding=10, border_radius=8, bgcolor=theme["panel"], border=ft.border.Border.all(1, color)
        ))

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            content=ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Row([
                        ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                        ft.Text("Erfolge", size=24, weight="bold", color="white"),
                    ]),
                    ft.Column(cards, scroll=ft.ScrollMode.AUTO, expand=True)
                ])
            )
        )
    )
    page.update()


def show_daily_challenge_hub(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    if not email or email not in db["users"]:
        open_main_menu(page, state)
        return
    user = db["users"][email]
    theme = get_theme(state)
    stats = user.get("stats", {})

    today_str = str(date.today())
    has_played_today = stats.get("last_daily_played") == today_str

    def start_daily(e):
        # 1. Mark as played today immediately in local DB and save
        db_local = load_db()
        user_local = db_local["users"][email]
        user_local.setdefault("stats", {})["last_daily_played"] = today_str
        save_db(db_local)

        # 2. Try to sync to FireStore if active
        client = get_firestore_client()
        if client:
            try:
                client.collection("users").document(user_local["uid"]).set({
                    "stats": {
                        "last_daily_played": today_str
                    }
                }, merge=True)
            except Exception as ex:
                print(f"Failed to sync daily play to FireStore: {ex}")

        # 3. Configure daily state directly
        state.update({
            "money": "0 €",
            "questions_answered": 0,
            "correct": 0,
            "jokers_used": 0,
            "question_index": 0,
            "game_finished": False,
            "current_user_email": email,
            "current_user_uid": user_local.get("uid"),
            "is_daily_challenge": True,
            "daily_date": today_str,
            "player_age": "old",
            "time_pressure_enabled": True,
            "question_time_sec": 30,
            "time_left": 30,
            "selected_jokers": [],
            "jokers_used_ids": [],
        })

        # 4. Generate seeded questions
        random.seed(today_str)
        state["questions"] = create_game_questions("old")
        random.seed() # Reset seed

        # 5. Launch the game immediately!
        show_next_question(page, state)

    btn = ft.ElevatedButton(
        "Bereits gespielt!" if has_played_today else "Daily Challenge starten",
        disabled=has_played_today,
        on_click=start_daily,
        bgcolor="gray" if has_played_today else theme["success"],
        color="white",
        width=300,
        height=50
    )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            content=ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Row([
                        ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                        ft.Text("Daily Challenge", size=24, weight="bold", color="white"),
                    ]),
                    ft.Text("Spiele jeden Tag die exakt gleichen 15 Fragen wie alle anderen Spieler!", color="white"),
                    ft.Container(height=20),
                    btn,
                    ft.Container(height=20),
                    ft.Text("Deine Daily Stats:", size=18, weight="bold", color=theme["gold"]),
                    ft.Text(f"🔥 Aktueller Streak: {stats.get('daily_current_streak', 0)} Tage", color="white"),
                    ft.Text(f"👑 Bester Streak: {stats.get('daily_best_streak', 0)} Tage", color="white"),
                    ft.Text(f"💰 Bestes Ergebnis: {stats.get('daily_best_result', '0 €')}", color="white"),
                ])
            )
        )
    )
    page.update()


def main(page: ft.Page):
    app_state = {
        "money": "0 €",
        "questions_answered": 0,
        "correct": 0,
        "jokers_used": 0,
        "current_user_email": None,
        "current_user_uid": None,
    }

    page.title = "Wer wird Millionär?"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#2C1654"
    page.padding = 0
    page.window.width = 1100
    page.window.height = 680

    def check_url_parameters():
        if page.route:
            match = re.search(r"add_friend=([A-Z0-9]+)", page.route, re.IGNORECASE)
            if match:
                friend_code = match.group(1).upper()
                email = app_state.get("current_user_email")
                if email:
                    msg = save_friend_request(app_state, friend_code)
                    show_friends_view(page, app_state, status_message=msg)
                else:
                    app_state["pending_friend_add"] = friend_code
                    show_login_view(page, app_state)
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Bitte logge dich ein, um die Freundschaftsanfrage abzusenden!"),
                        open=True
                    )
                    page.update()

    def on_route_change(e):
        check_url_parameters()
        route = page.route or "/"
        path = route.split("?")[0]
        if path == "/shop":
            show_shop_screen(page, app_state)
        elif path == "/achievements":
            show_achievements_screen(page, app_state)
        elif path == "/daily":
            show_daily_challenge_hub(page, app_state)
        else:
            open_main_menu(page, app_state)

    page.on_route_change = on_route_change

    # Show main menu immediately so the page is not blank while init runs.
    # We mark app_state so that restore_remembered_login can signal whether
    # it already handled navigation (logged-in) — in that case we skip the
    # second on_route_change that would overwrite the authenticated screen.
    app_state["_init_nav_done"] = False

    async def init_task():
        await restore_remembered_login(page, app_state)
        # restore_remembered_login always ends with open_main_menu, so mark done.
        app_state["_init_nav_done"] = True
        check_url_parameters()
        # Only re-run route logic for special deep-link paths.
        route = page.route or "/"
        path = route.split("?")[0]
        if path in ("/shop", "/achievements", "/daily"):
            on_route_change(None)

    page.run_task(init_task)
    # Render a blank/loading screen immediately; init_task will replace it.
    open_main_menu(page, app_state)
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
