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
from datetime import datetime, timezone
from email.message import EmailMessage

import requests

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


THEMES = {
    "classic": {
        "label": "Klassisch",
        "gradient": ["#2C1654", "#6B2FA0", "#C2185B"],
        "panel": "#1A0A30",
        "border": "#9B59B6",
        "accent": "#9B59B6",
        "accent_2": "#F4A460",
        "success": "#2ECC71",
        "danger": "#C2185B",
        "gold": "#FFD700",
    },
    "ocean": {
        "label": "Ocean",
        "gradient": ["#062A38", "#0E7490", "#14B8A6"],
        "panel": "#06202A",
        "border": "#38BDF8",
        "accent": "#0891B2",
        "accent_2": "#22C55E",
        "success": "#10B981",
        "danger": "#E11D48",
        "gold": "#FDE68A",
    },
    "neon": {
        "label": "Neon Night",
        "gradient": ["#020617", "#11126B", "#E11D8E"],
        "panel": "#070A2D",
        "border": "#22D3EE",
        "accent": "#EC4899",
        "accent_2": "#F59E0B",
        "success": "#22C55E",
        "danger": "#F43F5E",
        "gold": "#FDE047",
    },
    "forest": {
        "label": "Forest",
        "gradient": ["#F8F3E7", "#DDEBDD", "#F4B46A"],
        "panel": "#264D3A",
        "border": "#7DA88A",
        "accent": "#3D7A59",
        "accent_2": "#F2B84B",
        "success": "#2F855A",
        "danger": "#B45309",
        "gold": "#FFE08A",
    },
    "arcade": {
        "label": "Arcade",
        "gradient": ["#050807", "#0B1F12", "#4D7C0F"],
        "panel": "#06110B",
        "border": "#84CC16",
        "accent": "#65A30D",
        "accent_2": "#A3E635",
        "success": "#84CC16",
        "danger": "#DC2626",
        "gold": "#BEF264",
    },
    "candy": {
        "label": "Candy Pop",
        "gradient": ["#DFF6FF", "#BDEBFF", "#FFE66D"],
        "panel": "#FFFFFF",
        "border": "#60A5FA",
        "accent": "#3B82F6",
        "accent_2": "#F97316",
        "success": "#22C55E",
        "danger": "#FB7185",
        "gold": "#FACC15",
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
    return f"Frage {current_question} von {total} · {money} · {correct} richtig"


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
    })
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


# ---------- Build money ladder column ----------
def build_money_ladder(state: dict, compact: bool = False) -> ft.Control:
    """Build the right-side money ladder as a normal Column (no overlay)."""
    items = []
    correct = state.get("correct", 0)

    for i, level in enumerate(reversed(MONEY_LEVELS)):
        orig_idx = len(MONEY_LEVELS) - 1 - i  # index in MONEY_LEVELS
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
            str(len(MONEY_LEVELS) - i),
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
        bgcolor="#1A0A30",
        border_radius=16,
        border=ft.border.Border.all(2, "#9B59B6"),
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
                        color="#FFD700", text_align="center"),
                ft.Text("MILLIONÄR?", size=34, weight="black",
                        color="white", text_align="center"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            padding=30,
            border_radius=24,
            bgcolor=theme["panel"],
            shadow=ft.BoxShadow(blur_radius=40, color="#80FFD700"),
            border=ft.border.Border.all(3, theme["gold"]),
        ),
        ft.Container(height=10),
        ft.Text(greeting, size=18, weight="bold", color="#E0D0F0", text_align="center"),
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


def show_game_start_choice(page: ft.Page, state: dict, saved: dict):
    theme = get_theme(state)
    summary = saved_game_summary(saved)

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
                    content=ft.Column([
                        ft.Text("Gespeichertes Spiel gefunden", size=18, weight="bold", color=theme["gold"], text_align="center"),
                        ft.Text(summary, size=14, color="#E0D0F0", text_align="center"),
                        ft.Container(height=10),
                        ft.Container(
                            content=ft.Text("Altes Spiel fortsetzen", size=16, weight="bold", color="white"),
                            on_click=lambda e: resume_saved_game(e.page, state, saved),
                            bgcolor=theme["success"],
                            border_radius=30,
                            padding=ft.Padding(30, 12, 30, 12),
                            alignment=ft.Alignment(0, 0),
                            width=260,
                        ),
                        ft.Container(
                            content=ft.Text("Neues Spiel starten", size=16, weight="bold", color="white"),
                            on_click=lambda e: start_new_game(e.page, state, force_new=True),
                            bgcolor=theme["accent"],
                            border_radius=30,
                            padding=ft.Padding(30, 12, 30, 12),
                            alignment=ft.Alignment(0, 0),
                            width=260,
                        ),
                    ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=theme["panel"],
                    border_radius=16,
                    padding=24,
                    border=ft.border.Border.all(2, theme["border"]),
                    width=380,
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


# ---------- Age Selection ----------
def start_new_game(page: ft.Page, state: dict, force_new: bool = False):
    """Reset state and ask for age group."""
    theme = get_theme(state)
    saved = None if force_new else get_saved_game_for_state(state)
    if saved:
        show_game_start_choice(page, state, saved)
        return

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

    def choose_age(e: ft.ControlEvent):
        age = e.control.data
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
                    on_click=lambda e: open_main_menu(e.page, state),
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
    page.controls.clear()
    page.add(build_welcome_view(page, state))
    page.update()


# ---------- Game Screen ----------
def show_next_question(page: ft.Page, state: dict):
    """Display question with typing animation; all 4 answer boxes shown immediately."""
    if state["question_index"] >= len(state["questions"]):
        _show_win_screen(page, state)
        return

    theme = get_theme(state)
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
                state["money"] = MONEY_LEVELS[min(state["correct"] - 1, len(MONEY_LEVELS) - 1)]
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
        color = ANSWER_COLORS[idx]
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
                ft.Text(text, size=14 if is_mobile else 16, color="#2C1654", weight="bold", expand=True),
            ], spacing=8 if is_mobile else 10),
            data=idx,
            on_click=handle_answer,
            bgcolor="white",
            border_radius=22 if is_mobile else 50,
            padding=ft.Padding(12, 10, 14 if is_mobile else 20, 10),
            border=ft.border.Border.all(2, "#E0D0F0"),
            shadow=ft.BoxShadow(blur_radius=6, color="#20000000"),
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
        color="#2C1654",
        text_align="center",
        max_lines=4 if is_mobile else 3,
        no_wrap=False,
    )
    question_box = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text(f"FRAGE {q_num}", size=13 if is_mobile else 14, weight="bold", color="white"),
                bgcolor="#9B59B6",
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
        bgcolor="white",
        border_radius=20,
        padding=ft.Padding(18 if is_mobile else 24, 18 if is_mobile else 20, 18 if is_mobile else 24, 18 if is_mobile else 20),
        shadow=ft.BoxShadow(blur_radius=20, color="#30000000"),
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
        save_db(db)

        state["current_user_email"] = email
        state["current_user_uid"] = uid
        page.run_task(save_remembered_login, page, auth_data, bool(remember_checkbox.value))
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
        ft.Text("Einstellungen", size=30, weight="bold", color="white"),
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
                    color="#E0D0F0",
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
                ft.Text("Design", size=30, weight="bold", color="white"),
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
            ], alignment=ft.MainAxisAlignment.CENTER,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=14,
               scroll=ft.ScrollMode.AUTO),
            padding=20,
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
    page.add(build_welcome_view(page, app_state))
    page.run_task(restore_remembered_login, page, app_state)
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
