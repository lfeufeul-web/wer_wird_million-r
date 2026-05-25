import flet as ft
import asyncio
import random
import json
import os
import time
import re
import inspect
import smtplib
import ssl
import base64
import io
from datetime import datetime, timezone
from email.message import EmailMessage

import requests

try:
    import qrcode
except ImportError:
    qrcode = None

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
    "question": {"l": 0.0448, "t": 0.0704, "w": 0.5698, "h": 0.135},
    "answer_a": {"l": 0.0448, "t": 0.218, "w": 0.2771, "h": 0.118},
    "answer_b": {"l": 0.3375, "t": 0.218, "w": 0.2771, "h": 0.118},
    "answer_c": {"l": 0.0448, "t": 0.348, "w": 0.2771, "h": 0.118},
    "answer_d": {"l": 0.3375, "t": 0.348, "w": 0.2771, "h": 0.118},
    "ladder": {"l": 0.6651, "t": 0.0704, "w": 0.2797, "h": 0.8593},
    "footer": {"l": 0.0448, "t": 0.478, "w": 0.5698, "h": 0.052},
    "exit": {"l": 0.0198, "t": 0.0204, "w": 0.1146, "h": 0.0500},
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
    "ocean": {
        "label": "Ocean",
        "game_layout": "themed",
        "game_bg": "bg_ocean.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#F0FDFF",
        "text_secondary": "#BAE6FD",
        "text_muted": "#7DD3FC",
        "gradient": ["#062A38", "#0E7490", "#14B8A6"],
        "panel": "#06202A",
        "border": "#38BDF8",
        "accent": "#0891B2",
        "accent_2": "#22C55E",
        "success": "#10B981",
        "danger": "#E11D48",
        "gold": "#FDE68A",
        "question_bg": "#06202A",
        "question_text": "#E0F7FA",
        "answer_bg": "#073540",
        "answer_text": "#CCFBF1",
        "answer_colors": ["#0891B2", "#14B8A6", "#22C55E", "#38BDF8"],
    },
    "neon": {
        "label": "Neon Night",
        "game_layout": "themed",
        "game_bg": "bg_neon.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#F8FAFC",
        "text_secondary": "#E0E7FF",
        "text_muted": "#A5B4FC",
        "gradient": ["#020617", "#11126B", "#E11D8E"],
        "panel": "#070A2D",
        "border": "#22D3EE",
        "accent": "#EC4899",
        "accent_2": "#F59E0B",
        "success": "#22C55E",
        "danger": "#F43F5E",
        "gold": "#FDE047",
        "question_bg": "#0B102F",
        "question_text": "#F8FAFC",
        "answer_bg": "#11143A",
        "answer_text": "#F8FAFC",
        "answer_colors": ["#EC4899", "#F59E0B", "#22D3EE", "#8B5CF6"],
    },
    "forest": {
        "label": "Forest",
        "game_layout": "themed",
        "game_bg": "bg_forest.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#F8FFF8",
        "text_secondary": "#D8F0D8",
        "text_muted": "#A8D4A8",
        "gradient": ["#1a3d2a", "#2d5a3d", "#4a7c59"],
        "panel": "#1e3d2a",
        "border": "#7DA88A",
        "accent": "#3D7A59",
        "accent_2": "#F2B84B",
        "success": "#2F855A",
        "danger": "#B45309",
        "gold": "#FFE08A",
        "question_bg": "#1e3d2a",
        "question_text": "#F0FFF0",
        "answer_bg": "#243d2a",
        "answer_text": "#E8F5E9",
        "answer_colors": ["#7DA88A", "#F2B84B", "#3D7A59", "#F59E0B"],
    },
    "arcade": {
        "label": "Arcade",
        "game_layout": "themed",
        "game_bg": "bg_arcade.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#F7FEE7",
        "text_secondary": "#D9F99D",
        "text_muted": "#BEF264",
        "gradient": ["#050807", "#0B1F12", "#4D7C0F"],
        "panel": "#06110B",
        "border": "#84CC16",
        "accent": "#65A30D",
        "accent_2": "#A3E635",
        "success": "#84CC16",
        "danger": "#DC2626",
        "gold": "#BEF264",
        "question_bg": "#020604",
        "question_text": "#D9F99D",
        "answer_bg": "#050807",
        "answer_text": "#F7FEE7",
        "answer_colors": ["#84CC16", "#65A30D", "#A3E635", "#22C55E"],
    },
    "candy": {
        "label": "Candy Pop",
        "game_layout": "themed",
        "game_bg": "bg_candy.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": True,
        "text_primary": "#1e1b4b",
        "text_secondary": "#312e81",
        "text_muted": "#4338ca",
        "gradient": ["#DFF6FF", "#BDEBFF", "#FFE66D"],
        "panel": "#FFFFFF",
        "border": "#60A5FA",
        "accent": "#3B82F6",
        "accent_2": "#F97316",
        "success": "#22C55E",
        "danger": "#FB7185",
        "gold": "#FACC15",
        "question_bg": "#FFFFFF",
        "question_text": "#172554",
        "answer_bg": "#FFFFFF",
        "answer_text": "#172554",
        "answer_colors": ["#3B82F6", "#F97316", "#22C55E", "#8B5CF6"],
    },
    "royal": {
        "label": "Royal Gold",
        "game_layout": "themed",
        "game_bg": "bg_royal.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#FFF7ED",
        "text_secondary": "#FDE68A",
        "text_muted": "#D8B4FE",
        "gradient": ["#1E1B4B", "#581C87", "#92400E"],
        "panel": "#17122F",
        "border": "#C084FC",
        "accent": "#7C3AED",
        "accent_2": "#D97706",
        "success": "#16A34A",
        "danger": "#DC2626",
        "gold": "#FBBF24",
        "question_bg": "#2B174F",
        "question_text": "#FFF7ED",
        "answer_bg": "#24123E",
        "answer_text": "#FFF7ED",
        "answer_colors": ["#D97706", "#7C3AED", "#16A34A", "#DB2777"],
    },
    "sunset": {
        "label": "Sunset",
        "game_layout": "themed",
        "game_bg": "bg_sunset.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#FFF7ED",
        "text_secondary": "#FECDD3",
        "text_muted": "#FDBA74",
        "gradient": ["#2D0B36", "#B91C1C", "#F59E0B"],
        "panel": "#2A1020",
        "border": "#FB7185",
        "accent": "#F97316",
        "accent_2": "#FBBF24",
        "success": "#22C55E",
        "danger": "#BE123C",
        "gold": "#FEF08A",
        "question_bg": "#FFF1F2",
        "question_text": "#4A102A",
        "answer_bg": "#FFF7ED",
        "answer_text": "#4A102A",
        "answer_colors": ["#F97316", "#FB7185", "#FBBF24", "#A855F7"],
    },
    "ice": {
        "label": "Ice Crystal",
        "game_layout": "themed",
        "game_bg": "bg_ice.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": True,
        "text_primary": "#0c4a6e",
        "text_secondary": "#075985",
        "text_muted": "#0369a1",
        "gradient": ["#E0F2FE", "#7DD3FC", "#1D4ED8"],
        "panel": "#F0F9FF",
        "border": "#38BDF8",
        "accent": "#2563EB",
        "accent_2": "#06B6D4",
        "success": "#059669",
        "danger": "#E11D48",
        "gold": "#0F766E",
        "question_bg": "#FFFFFF",
        "question_text": "#0F172A",
        "answer_bg": "#F8FAFC",
        "answer_text": "#0F172A",
        "answer_colors": ["#2563EB", "#06B6D4", "#0EA5E9", "#38BDF8"],
    },
    "neon_nexus": {
        "label": "Neon Nexus",
        "game_layout": "themed",
        "game_bg": "neon_nexus_bg_clean.png",
        "layout_zones": THEME_GAME_ZONES,
        "is_light": False,
        "text_primary": "#F5FFF5",
        "text_secondary": "#C8FFC8",
        "text_muted": "#9dffb8",
        "gradient": ["#000000", "#021208", "#042810"],
        "panel": "#0c1814",
        "border": "#00FF66",
        "accent": "#064d2a",
        "accent_2": "#00C853",
        "success": "#00FF66",
        "danger": "#FF1744",
        "gold": "#76FF03",
        "question_bg": "#0c1814",
        "question_text": "#F5FFF5",
        "answer_bg": "#08120e",
        "answer_text": "#F0FFF0",
        "answer_colors": ["#00E676", "#00C853", "#76FF03", "#1DE9B6"],
    },
}
DEFAULT_USER_SETTINGS = {"theme": "classic"}


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
    refresh_token = await storage_get(page, AUTH_REFRESH_TOKEN_KEY)
    email = await storage_get(page, AUTH_EMAIL_KEY)
    uid = await storage_get(page, AUTH_UID_KEY)
    if not refresh_token or not email or not uid:
        return

    try:
        refreshed = firebase_refresh_auth(refresh_token)
        uid = refreshed.get("user_id", uid)
        refresh_token = refreshed.get("refresh_token", refresh_token)
        user = ensure_firebase_user(uid, email)

        db = load_db()
        db["users"][email] = user
        update_last_active(db, email)
        save_db(db)

        state["current_user_email"] = email
        state["current_user_uid"] = uid
        await storage_set(page, AUTH_UID_KEY, uid)
        await storage_set(page, AUTH_REFRESH_TOKEN_KEY, refresh_token)
        open_main_menu(page, state)
    except Exception as e:
        print(f"Auto-login failed: {e}")
        await clear_remembered_login(page)


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
    """Background stretched to the full viewport (no letterboxing)."""
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
            show_next_question_themed(page, state)

    page.on_resize = on_resize


def _clear_themed_game_resize(state: dict):
    state["_themed_game_active"] = False

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
    if not email or state.get("game_finished"):
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
    })
    show_next_question(page, state)


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


def start_custom_quiz_play(page: ft.Page, state: dict, quiz: dict):
    questions = custom_quiz_to_game_questions(quiz)
    if not questions:
        page.snack_bar = ft.SnackBar(content=ft.Text("Bitte mindestens eine Frage mit Text anlegen."))
        page.snack_bar.open = True
        page.update()
        return
    clear_saved_game(state)
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
    save_current_game(state)
    show_next_question(page, state)


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
    bar_top = header_h + i_current * row_h + max(0, (row_h - 8) // 2)

    rows = []
    for i, level in enumerate(reversed(levels)):
        orig_idx = n - 1 - i
        is_current = orig_idx == correct
        is_reached = orig_idx < correct
        dot_color = theme["gold"] if is_current else (theme["accent_2"] if is_reached else "#143d28")
        text_color = "#FFFFFF" if is_current else ("#B8FFD0" if is_reached else "#7AE8A8")
        rows.append(
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=7, height=7, border_radius=4,
                        bgcolor=dot_color,
                        border=ft.border.Border.all(1, theme["border"]) if is_current else None,
                    ),
                    ft.Text(
                        level,
                        size=12 if compact else 13,
                        color=text_color,
                        weight="bold" if is_current else "normal",
                        expand=True,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ], spacing=6),
                height=row_h,
                alignment=ft.Alignment(0, 0),
                bgcolor="#0a140e" if is_current else None,
                border_radius=4,
            )
        )

    ladder_stack = ft.Stack(
        [
            ft.Column(
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
            ),
            ft.Container(
                top=bar_top,
                left=4,
                right=4,
                height=8,
                bgcolor=theme["gold"],
                border_radius=4,
                shadow=ft.BoxShadow(blur_radius=18, color="#B000FF66", spread_radius=1),
            ),
        ],
        height=header_h + n * row_h + 4,
    )

    return ft.Container(
        content=ladder_stack,
        width=None if compact else 200,
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
        width=None if compact else 180,
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
        """
        db_current = load_db()
        email_current = state.get("current_user_email")
        if email_current and email_current in db_current["users"]:
            saved = db_current["users"][email_current].get("saved_game")
            if saved:
                state.update({
                    "money": saved.get("money", "0 €"),
                    "questions_answered": saved.get("questions_answered", 0),
                    "correct": saved.get("correct", 0),
                    "jokers_used": saved.get("jokers_used", 0),
                    "question_index": saved.get("question_index", 0),
                    "questions": saved.get("questions", []),
                })
                show_next_question(e.page, state)
        """

    menu_buttons = []
    if logged_in and saved_game:
        menu_buttons.append(
            _menu_button("▶️  Spiel fortsetzen", resume_game, "#2ECC71")
        )
    menu_buttons.append(
        _menu_button("🎮  Spiel starten",
                     lambda e: start_new_game(e.page, state), "#F4A460")
    )
    menu_buttons.append(
        _menu_button("Einstellungen",
                     lambda e: show_settings_view(e.page, state), "#9B59B6")
    )
    if not logged_in:
        menu_buttons.append(
            _menu_button("Anmelden",
                         lambda e: show_login_view(e.page, state), "#2ECC71")
        )

    menu_items = [
        ft.Container(
            content=ft.Column([
                ft.Text("❓", size=60, text_align="center"),
                ft.Text("WER WIRD", size=28, weight="bold",
                        color=theme["gold"], text_align="center"),
                ft.Text("MILLIONÄR?", size=34, weight="black",
                        color=theme_txt(theme, "primary"), text_align="center"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            padding=30,
            border_radius=24,
            bgcolor=theme["panel"],
            shadow=ft.BoxShadow(blur_radius=40, color="#40000000"),
            border=ft.border.Border.all(3, theme["gold"]),
        ),
        ft.Container(height=10),
        ft.Container(
            content=ft.Text(greeting, size=18, weight="bold", color=theme_txt(theme, "primary"), text_align="center"),
            bgcolor=theme["panel"],
            border_radius=12,
            padding=ft.Padding(14, 8, 14, 8),
            border=ft.border.Border.all(1, theme["border"]),
        ),
        ft.Container(height=10),
        *menu_buttons,
    ]

    if logged_in:
        menu_items.extend([
            ft.Container(height=10),
            ft.Row([
                ft.TextButton(
                    "✏️ Profil bearbeiten",
                    on_click=lambda e: show_edit_profile_view(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                ),
                ft.TextButton(
                    "🚪 Abmelden",
                    on_click=on_logout,
                    style=ft.ButtonStyle(color="#FF6B6B"),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        ])

    return ft.Container(
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


def _menu_button(label: str, on_click, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(label, size=18, weight="bold", color="white"),
        on_click=on_click,
        bgcolor=color,
        border_radius=50,
        padding=ft.Padding(40, 14, 40, 14),
        shadow=ft.BoxShadow(blur_radius=12, color="#40000000"),
    )


def _game_menu_button(label: str, on_click, bgcolor: str, width: int = 280) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=16, weight="bold", color="white", text_align="center"),
        on_click=on_click,
        bgcolor=bgcolor,
        border_radius=30,
        padding=ft.Padding(24, 12, 24, 12),
        alignment=ft.Alignment(0, 0),
        width=width,
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
                        ft.TextButton("Bearbeiten", on_click=lambda e, qid=quiz["id"]: show_custom_quiz_editor(e.page, state, qid)),
                        ft.TextButton("Spielen", on_click=lambda e, q=quiz: start_custom_quiz_play(e.page, state, q)),
                        ft.TextButton("Löschen", on_click=lambda e, qid=quiz["id"]: confirm_delete_custom_quiz(e.page, state, qid)),
                    ], spacing=0),
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
        page.close(dlg)
        delete_custom_quiz(state, quiz_id)
        show_custom_quiz_hub(page, state)

    dlg = ft.AlertDialog(
        title=ft.Text("Spiel löschen?"),
        content=ft.Text(f'"{title}" wirklich löschen?', color=theme_txt(theme, "secondary")),
        actions=[
            ft.TextButton("Abbrechen", on_click=lambda e: page.close(dlg)),
            ft.TextButton("Löschen", on_click=do_delete),
        ],
    )
    page.open(dlg)


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
    title_field = ft.TextField(
        label="Titel des Spiels",
        value=quiz.get("title", ""),
        width=360,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )

    def save_draft(e):
        q = state["editing_quiz"]
        q["title"] = (title_field.value or "").strip() or "Mein Quiz"
        q["is_draft"] = True
        upsert_custom_quiz(state, q, mark_finished=False)
        page.snack_bar = ft.SnackBar(content=ft.Text("Zwischengespeichert ✓"))
        page.snack_bar.open = True
        page.update()

    def save_finished(e):
        q = state["editing_quiz"]
        q["title"] = (title_field.value or "").strip() or "Mein Quiz"
        if not q.get("questions"):
            page.snack_bar = ft.SnackBar(content=ft.Text("Mindestens eine Frage erforderlich."))
            page.snack_bar.open = True
            page.update()
            return
        upsert_custom_quiz(state, q, mark_finished=True)
        page.snack_bar = ft.SnackBar(content=ft.Text("Spiel gespeichert ✓"))
        page.snack_bar.open = True
        show_custom_quiz_hub(page, state)

    def add_question(e):
        if len(state["editing_quiz"].get("questions", [])) >= MAX_CUSTOM_QUESTIONS:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Maximal {MAX_CUSTOM_QUESTIONS} Fragen."))
            page.snack_bar.open = True
            page.update()
            return
        show_custom_question_editor(page, state, None)

    def play_now(e):
        q = dict(state["editing_quiz"])
        q["title"] = (title_field.value or "").strip() or q.get("title", "Mein Quiz")
        upsert_custom_quiz(state, q, mark_finished=bool(q.get("questions")))
        start_custom_quiz_play(page, state, q)

    question_items = []
    for idx, q in enumerate(state["editing_quiz"].get("questions", [])):
        preview = str(q.get("question", ""))[:60]
        if len(str(q.get("question", ""))) > 60:
            preview += "…"
        correct_letter = ANSWER_LETTERS[int(q.get("correct_idx", 0))]
        question_items.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(f"{idx + 1}. {preview}", size=13, color=theme_txt(theme, "primary"), expand=True),
                    ft.Text(f"✓ {correct_letter}", size=12, color=theme["gold"], weight="bold"),
                    ft.TextButton(
                        "Bearbeiten",
                        on_click=lambda e, i=idx: show_custom_question_editor(page, state, i),
                    ),
                    ft.TextButton(
                        "Entf.",
                        on_click=lambda e, i=idx: delete_question_from_editor(page, state, i, title_field),
                        style=ft.ButtonStyle(color=theme["danger"]),
                    ),
                ]),
                padding=ft.Padding(4, 0, 4, 0),
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
                ft.Row([
                    _game_menu_button("➕ Frage", add_question, theme["accent"], width=120),
                    _game_menu_button("💾 Zwischenspeichern", save_draft, "#5C6BC0", width=180),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                ft.Row([
                    _game_menu_button("✅ Speichern", save_finished, theme["success"], width=140),
                    _game_menu_button("▶ Spielen", play_now, theme["gold"], width=140),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                ft.TextButton(
                    "← Zurück zur Liste",
                    on_click=lambda e: show_custom_quiz_hub(e.page, state),
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
        q["title"] = (title_field.value or "").strip() or q.get("title", "Mein Quiz")
        state["editing_quiz"] = q
        upsert_custom_quiz(state, q, mark_finished=False)
    show_custom_quiz_editor(page, state, q.get("id"))


def show_custom_question_editor(page: ft.Page, state: dict, question_index: int | None):
    theme = get_theme(state)
    quiz = state.get("editing_quiz")
    if not quiz:
        show_custom_quiz_hub(page, state)
        return

    existing = None
    if question_index is not None and 0 <= question_index < len(quiz.get("questions", [])):
        existing = dict(quiz["questions"][question_index])

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
        upsert_custom_quiz(state, quiz, mark_finished=False)
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
                question_field,
                *answer_fields,
                correct_dropdown,
                ft.Container(height=8),
                _game_menu_button("💾 Frage speichern", save_question, theme["success"], width=220),
                ft.TextButton(
                    "← Zurück zum Editor",
                    on_click=lambda e: show_custom_quiz_editor(e.page, state, quiz.get("id")),
                    style=ft.ButtonStyle(color="white"),
                ),
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
    theme = get_theme(state)
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

    def choose_age(e: ft.ControlEvent):
        age = e.control.data
        state["player_age"] = age
        state["questions"] = create_game_questions(age)
        save_current_game(state)
        show_next_question(page, state)

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
    pad = 6 if compact else 10
    return ft.Container(
        content=content,
        bgcolor=theme.get("panel", "#0c1814"),
        border_radius=6,
        padding=ft.Padding(pad, pad - 2, pad, pad - 2),
        border=_neon_panel_border(theme),
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


def show_next_question_themed(page: ft.Page, state: dict):
    """Themed game screen with background image and readable UI panels."""
    theme = get_theme(state)
    zones = theme.get("layout_zones", THEME_GAME_ZONES)
    answer_palette = theme.get("answer_colors", ANSWER_COLORS)
    question_text_color = theme_value(theme, "question_text", "#F5FFF5")
    answer_text_color = theme_value(theme, "answer_text", "#F0FFF0")
    answer_bg = theme_value(theme, "answer_bg", "#08120e")
    question, options, correct_idx = state["questions"][state["question_index"]]
    q_num = state["question_index"] + 1
    total_q = len(state["questions"])
    page_w, page_h = _page_size(page)
    is_mobile = page_w < 720

    answer_buttons: list[ft.Container] = []
    answers_disabled = [False]

    def handle_answer(e):
        if answers_disabled[0]:
            return
        answers_disabled[0] = True
        chosen = e.control.data
        for idx, btn_container in enumerate(answer_buttons):
            if idx == correct_idx:
                btn_container.bgcolor = "#00C853"
                btn_container.border = ft.border.Border.all(3, "#76FF03")
            elif idx == chosen and idx != correct_idx:
                btn_container.bgcolor = "#B71C1C"
                btn_container.border = ft.border.Border.all(3, "#FF1744")
        page.update()

        async def _next():
            await asyncio.sleep(1.5)
            if chosen == correct_idx:
                state["correct"] += 1
                levels = money_levels_for_state(state)
                state["money"] = levels[min(state["correct"] - 1, len(levels) - 1)]
                state["questions_answered"] += 1
                state["question_index"] += 1
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

    def make_answer_box(idx: int, text: str) -> ft.Container:
        letter = ANSWER_LETTERS[idx]
        color = answer_palette[idx % len(answer_palette)]
        inner = ft.Row([
            ft.Container(
                content=ft.Text(letter, size=12, weight="bold", color="#001a0a"),
                width=26, height=26,
                border_radius=4,
                bgcolor=color,
                alignment=ft.Alignment(0, 0),
                border=ft.border.Border.all(1, theme["border"]),
            ),
            ft.Text(
                text, size=12 if is_mobile else 13,
                color=answer_text_color, weight="bold", expand=True,
                max_lines=2, no_wrap=False,
            ),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        box = ft.Container(
            content=inner,
            data=idx,
            on_click=handle_answer,
            bgcolor=answer_bg,
            border_radius=6,
            padding=ft.Padding(8, 5, 8, 5),
            border=_neon_panel_border(theme),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )
        answer_buttons.append(box)
        return box

    answer_boxes = [make_answer_box(i, option) for i, option in enumerate(options)]
    answer_zone_keys = ["answer_a", "answer_b", "answer_c", "answer_d"]

    question_inner = ft.Column([
        ft.Container(
            content=ft.Text(f"FRAGE {q_num}", size=10, weight="bold", color="#001a0a"),
            bgcolor=theme["gold"],
            border_radius=4,
            padding=ft.Padding(8, 3, 8, 3),
        ),
        ft.Container(
            content=ft.Text(
                question, size=14 if is_mobile else 16, weight="bold",
                color=question_text_color, text_align=ft.TextAlign.CENTER,
                max_lines=4 if is_mobile else 3, no_wrap=False,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        ),
    ], spacing=5, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    question_panel = _neon_solid_panel(question_inner, theme, compact=True)

    ladder_inner = build_neon_nexus_money_ladder(state, compact=is_mobile)
    ladder_panel = _neon_solid_panel(ladder_inner, theme, compact=True)
    footer_panel = _neon_solid_panel(
        ft.Row([
            ft.Text(f"Frage {q_num} von {total_q}", size=11, color=theme_txt(theme, "secondary"), weight="bold"),
            ft.Text(f"◆ {state.get('money', '0 €')}", size=12, color=theme["gold"], weight="bold"),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        theme,
        compact=True,
    )
    exit_btn = ft.Container(
        content=ft.Row([
            ft.Text("🚪", size=12),
            ft.Text("Pause", size=11, weight="bold", color="white"),
        ], spacing=4),
        on_click=lambda e: show_exit_confirmation(page, state),
        bgcolor=theme["danger"],
        border_radius=4,
        padding=ft.Padding(10, 6, 10, 6),
    )

    bg_image = theme.get("game_bg")
    overlay_color = "#00000099" if not theme.get("is_light") else "#00000055"
    if bg_image:
        bg_layer = _themed_game_background(bg_image, page_w, page_h, overlay_color)
    else:
        bg_layer = ft.Container(
            width=max(1, int(page_w)),
            height=max(1, int(page_h)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -0.5),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
        )

    if is_mobile:
        mobile_stack = ft.Column(
            [
                exit_btn,
                question_panel,
                ft.Row([answer_boxes[0], answer_boxes[1]], spacing=8),
                ft.Row([answer_boxes[2], answer_boxes[3]], spacing=8),
                footer_panel,
                ladder_panel,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )
        hud_layers = [bg_layer, ft.Container(expand=True, padding=12, content=mobile_stack)]
    else:
        hud_layers = [
            bg_layer,
            _neon_zone_box(zones["exit"], page_w, page_h, exit_btn),
            _neon_zone_box(zones["question"], page_w, page_h, question_panel),
            *[
                _neon_zone_box(zones[key], page_w, page_h, answer_boxes[i])
                for i, key in enumerate(answer_zone_keys)
            ],
            _neon_zone_box(zones["footer"], page_w, page_h, footer_panel),
            _neon_zone_box(zones["ladder"], page_w, page_h, ladder_panel),
        ]

    pw, ph = max(1, int(page_w)), max(1, int(page_h))
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            width=pw,
            height=ph,
            bgcolor="#000000",
            content=ft.Stack(hud_layers, expand=True, width=pw, height=ph),
        )
    )
    _set_themed_game_resize(page, state)
    page.update()


def show_next_question(page: ft.Page, state: dict):
    """Display question with typing animation; all 4 answer boxes shown immediately."""
    if state["question_index"] >= len(state["questions"]):
        _show_win_screen(page, state)
        return

    theme = get_theme(state)
    if uses_themed_game(theme):
        show_next_question_themed(page, state)
        return

    answer_palette = theme.get("answer_colors", ANSWER_COLORS)
    question_bg = theme_value(theme, "question_bg", "white")
    question_text_color = theme_value(theme, "question_text", "#2C1654")
    answer_bg = theme_value(theme, "answer_bg", "white")
    answer_text_color = theme_value(theme, "answer_text", "#2C1654")
    question, options, correct_idx = state["questions"][state["question_index"]]
    q_num = state["question_index"] + 1
    total_q = len(state["questions"])
    page_width = page.width or page.window.width or 1100
    is_mobile = page_width < 720

    # ----- Answer button state tracking -----
    answer_buttons: list[ft.Control] = []
    answers_disabled = [False]  # mutable flag

    def handle_answer(e):
        if answers_disabled[0]:
            return
        answers_disabled[0] = True
        chosen = e.control.data

        # Highlight chosen & correct
        for idx, btn_container in enumerate(answer_buttons):
            btn_inner = btn_container.content  # Row inside
            if idx == correct_idx:
                btn_container.bgcolor = "#2ECC71"
                btn_container.border = ft.border.Border.all(3, "#27AE60")
            elif idx == chosen and idx != correct_idx:
                btn_container.bgcolor = "#E74C3C"
                btn_container.border = ft.border.Border.all(3, "#C0392B")
        page.update()

        async def _next():
            await asyncio.sleep(1.5)
            if chosen == correct_idx:
                state["correct"] += 1
                levels = money_levels_for_state(state)
                state["money"] = levels[min(state["correct"] - 1, len(levels) - 1)]
                state["questions_answered"] += 1
                state["question_index"] += 1
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

    # ----- Build 4 answer boxes immediately -----
    def make_answer_box(idx: int, text: str) -> ft.Container:
        letter = ANSWER_LETTERS[idx]
        color = answer_palette[idx % len(answer_palette)]
        box = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(letter, size=15 if is_mobile else 16, weight="bold", color="white"),
                    width=34 if is_mobile else 36,
                    height=34 if is_mobile else 36,
                    border_radius=17 if is_mobile else 18,
                    bgcolor=color,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Text(text, size=14 if is_mobile else 16, color=answer_text_color, weight="bold", expand=True),
            ], spacing=8 if is_mobile else 10),
            data=idx,
            on_click=handle_answer,
            bgcolor=answer_bg,
            border_radius=22 if is_mobile else 50,
            padding=ft.Padding(12, 10, 14 if is_mobile else 20, 10),
            border=ft.border.Border.all(2, theme["border"]),
            shadow=ft.BoxShadow(blur_radius=14, color="#30000000"),
            expand=True,
        )
        answer_buttons.append(box)
        return box

    answer_boxes = [make_answer_box(i, option) for i, option in enumerate(options)]
    if is_mobile:
        answer_layout = ft.Column(answer_boxes, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    else:
        answer_layout = ft.Column([
            ft.Row([answer_boxes[0], answer_boxes[1]], spacing=16),
            ft.Row([answer_boxes[2], answer_boxes[3]], spacing=16),
        ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ----- Question box (text filled by animation) -----
    question_text = ft.Text(
        question,
        size=18 if is_mobile else 22,
        weight="bold",
        color=question_text_color,
        text_align="center",
        max_lines=4 if is_mobile else 3,
        no_wrap=False,
    )
    question_box = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text(f"FRAGE {q_num}", size=13 if is_mobile else 14, weight="bold", color="white"),
                bgcolor=theme["accent"],
                border_radius=20,
                padding=ft.Padding(14 if is_mobile else 16, 6, 14 if is_mobile else 16, 6),
            ),
            ft.Container(
                content=question_text,
                expand=True,
                alignment=ft.Alignment(0, 0),
                width=900,
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        bgcolor=question_bg,
        border_radius=20,
        padding=ft.Padding(18 if is_mobile else 24, 18 if is_mobile else 20, 18 if is_mobile else 24, 18 if is_mobile else 20),
        border=ft.border.Border.all(2, theme["border"]),
        shadow=ft.BoxShadow(blur_radius=26, color="#40000000"),
        height=150 if is_mobile else 170,
        alignment=ft.Alignment(0, 0),
    )

    # ----- Money ladder -----
    ladder = build_money_ladder(state, compact=is_mobile)

    # ----- Layout: left game area + right ladder -----
    game_area = ft.Column([
        ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Text("🚪", size=13),
                    ft.Text("Spiel unterbrechen", size=13, weight="bold", color="white"),
                ], spacing=4),
                on_click=lambda e: show_exit_confirmation(page, state),
                bgcolor=theme["danger"],
                border_radius=30,
                padding=ft.Padding(16, 8, 16, 8),
            )
        ], alignment=ft.MainAxisAlignment.START),
        question_box,
        answer_layout,
        ft.Row([
            ft.Text(f"Frage {q_num} von {total_q}", size=13, color="#E0D0F0"),
            ft.Text(f"💰 {state.get('money', '0 €')}", size=13,
                    color="#FFD700", weight="bold"),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
    ], spacing=12 if is_mobile else 16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, width=None if is_mobile else 700)

    if is_mobile:
        main_content = ft.Column([
            game_area,
            ladder,
        ], spacing=14, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    else:
        main_content = ft.Row([
            ft.Container(content=game_area, expand=True, alignment=ft.Alignment(0, -1)),
            ft.Container(width=16),
            ladder,
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=theme["gradient"],
            ),
            padding=ft.Padding(12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20),
            content=main_content,
        )
    )
    page.update()


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


def _show_win_screen(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
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

    def finish_login(auth_data: dict):
        uid = auth_data["localId"]
        email = auth_data["email"]
        user = ensure_firebase_user(uid, email)

        db = load_db()
        db["users"][email] = user
        update_last_active(db, email)
        save_db(db)

        state["current_user_email"] = email
        state["current_user_uid"] = uid
        page.run_task(save_remembered_login, page, auth_data, bool(remember_checkbox.value))
        
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

    def run_auth(action: str):
        email, password = validate_inputs()
        if not email or not password:
            return

        status_text.value = "Verbindung mit Firebase..."
        status_text.color = theme["gold"]
        page.update()

        try:
            finish_login(firebase_auth_request(action, email, password))
        except Exception as ex:
            status_text.value = str(ex)
            status_text.color = "red"
            page.update()

    def on_login(e):
        run_auth("signInWithPassword")

    def on_register(e):
        run_auth("signUp")

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
            ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
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


def _close_overlay(page: ft.Page, overlay):
    if hasattr(page, "close"):
        page.close(overlay)
    else:
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

    def close_dlg():
        _close_overlay(page, dlg)

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
    if hasattr(page, "open"):
        page.open(dlg)
    else:
        page.overlay.append(dlg)
        dlg.open = True
    page.update()


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
                ft.TextButton(
                    "← Zurück",
                    on_click=lambda e: open_main_menu(e.page, state),
                    style=ft.ButtonStyle(color="white"),
                )
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

    page.on_route_change = on_route_change
    page.add(build_welcome_view(page, app_state))

    async def init_task():
        await restore_remembered_login(page, app_state)
        check_url_parameters()

    page.run_task(init_task)
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
