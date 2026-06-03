import flet as ft
import asyncio
import copy
import inspect
import json
import math
import os
import random
import re
import urllib.request
import time
import shutil
from datetime import datetime, date, timezone
import uuid
import smtplib
import ssl
import base64
import io
from email.message import EmailMessage

import requests
import unicodedata

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    Image = None
    ImageDraw = None
    ImageFilter = None

try:
    from flet_video import Video as FletVideo, VideoMedia, PlaylistMode
except ImportError:
    FletVideo = None
    VideoMedia = None
    PlaylistMode = None

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
    "points_quiz_games_played": 0,
    "points_quiz_questions_judged": 0,
    "points_quiz_finished_games": 0,
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
    "points_quiz_games_played": 0,
    "points_quiz_questions_judged": 0,
    "points_quiz_finished_games": 0,
}
ACHIEVEMENT_DEFINITIONS = [
    {"id": "first_game", "name": "Erster Schritt", "desc": "Dein erstes Spiel abschließen."},
    {"id": "quiz_fan", "name": "Quiz-Fan", "desc": "5 Spiele insgesamt spielen."},
    {"id": "marathon", "name": "Marathon", "desc": "10 Spiele insgesamt spielen."},
    {"id": "veteran", "name": "Veteran", "desc": "25 Spiele insgesamt spielen."},
    {"id": "legend_50", "name": "Legende", "desc": "50 Spiele insgesamt spielen."},
    {"id": "first_win", "name": "Siegertyp", "desc": "Zum ersten Mal gewinnen."},
    {"id": "streak_3", "name": "Heißlauf", "desc": "3 Siege in Folge schaffen."},
    {"id": "streak_5", "name": "Unaufhaltbar", "desc": "5 Siege in Folge schaffen."},
    {"id": "purist", "name": "Purist", "desc": "Ein Spiel gewinnen, ohne Joker zu nutzen."},
    {"id": "joker_friend", "name": "Jokerfreund", "desc": "Zum ersten Mal einen Joker einsetzen."},
    {"id": "joker_master", "name": "Joker-Meister", "desc": "Insgesamt 25 Joker einsetzen."},
    {"id": "perfect_round", "name": "Fehlerfrei", "desc": "Ein perfektes Spiel ohne falsche Antwort gewinnen."},
    {"id": "perfectionist", "name": "Perfektionist", "desc": "3 perfekte Spiele gewinnen."},
    {"id": "money_1000", "name": "Vierstellig", "desc": "Mindestens 1.000 € erreichen."},
    {"id": "money_32000", "name": "High Roller", "desc": "Mindestens 32.000 € erreichen."},
    {"id": "money_125000", "name": "Elite-Spieler", "desc": "Mindestens 125.000 € erreichen."},
    {"id": "millionaire", "name": "Millionär", "desc": "Die Million gewinnen."},
    {"id": "correct_50", "name": "Schlaufuchs", "desc": "Insgesamt 50 richtige Antworten geben."},
    {"id": "correct_200", "name": "Quizmaschine", "desc": "Insgesamt 200 richtige Antworten geben."},
    {"id": "daily_first", "name": "Tagesstarter", "desc": "Die Daily Challenge einmal spielen."},
    {"id": "daily_streak_3", "name": "Daily-Serie", "desc": "3 Daily Challenges in Folge gewinnen."},
    {"id": "daily_streak_7", "name": "Daily-Champion", "desc": "7 Daily Challenges in Folge gewinnen."},
]
QUESTION_HISTORY_LIMIT = 360
QUESTION_PERFORMANCE_LIMIT = 1500


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
        "game_bg": "backgrounds/neon_nexus/hintergrund_bild_neon_nexus.mp4",
        "layout_zones": NEON_NEXUS_ZONES,
        "is_light": False,
        "text_primary": "#F8FAFC",
        "text_secondary": "#D1E7FF",
        "text_muted": "#9FB8D9",
        "gradient": ["#000000", "#021208", "#042810"],
        "panel": "#00000000",
        "border": "#00000000",
        "accent": "#00000000",
        "accent_2": "#D946EF",
        "success": "#16A34A",
        "danger": "#DC2626",
        "gold": "#22D3EE",
        "question_bg": "#00000000",
        "question_text": "#F8FAFC",
        "answer_bg": "#00000000",
        "answer_text": "#F8FAFC",
        "answer_colors": ["#0ea5e9", "#d946ef", "#10b981", "#f59e0b"],
    },
    "hacker": {
        "label": "Hacker Matrix",
        "game_layout": "themed",
        "game_bg": "backgrounds/hacker_matrix/hintergrund_hacker_matrix_3.mp4",
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
        "game_layout": "themed",
        "game_bg": "backgrounds/royale_gold/hintergrund_royale_gold_3.mp4",
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
    "ocean": {
        "label": "Ocean",
        "game_layout": "themed",
        "game_bg": "backgrounds/ocean/hintergrund_ocean_3.mp4",
        "is_light": False,
        "text_primary": "#E6F6FF",
        "text_secondary": "#B4E4FF",
        "text_muted": "#8CBFD9",
        "gradient": ["#041A2D", "#053657", "#02101C"],
        "panel": "#03233abf",
        "border": "#36B5FF",
        "accent": "#36B5FF",
        "accent_2": "#2EE6D6",
        "success": "#22C55E",
        "danger": "#EF4444",
        "gold": "#7DD3FC",
        "question_bg": "#03233ad9",
        "question_text": "#EAF9FF",
        "answer_bg": "#03233ad9",
        "answer_text": "#EAF9FF",
        "answer_colors": ["#0EA5E9", "#38BDF8", "#06B6D4", "#22D3EE"],
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
DEFAULT_USER_SETTINGS = {"theme": "classic", "play_audio": True, "background_music": True}

SHOP_CATALOG = {
    "themes": [
        {"id": "hacker", "name": "Hacker Matrix", "price": 5000, "type": "theme"},
        {"id": "royal", "name": "Royal Gold", "price": 25000, "type": "theme"},
        {"id": "ocean", "name": "Ocean", "price": 35000, "type": "theme"},
        {"id": "cyberpunk", "name": "Cyberpunk 2077", "price": 100000, "type": "theme"},
    ],
    "titles": [
        {"id": "Neuling", "name": "Neuling", "price": 0, "type": "title"},
        {"id": "Quiz-Lehrling", "name": "Quiz-Lehrling", "price": 2500, "type": "title"},
        {"id": "Alleswisser", "name": "Alleswisser", "price": 15000, "type": "title"},
        {"id": "Millionär-Club", "name": "Millionär-Club", "price": 150000, "type": "title"},
        {"id": "Quiz-Gott", "name": "Quiz-Gott", "price": 1000000, "type": "title"},
    ],
    "avatar_items": [
        {"id": "top_basic", "slot": "top", "name": "Basic Shirt", "icon": "👕", "price": 0},
        {"id": "top_neon", "slot": "top", "name": "Neon Jacket", "icon": "🧥", "price": 3500},
        {"id": "top_royal", "slot": "top", "name": "Royal Cape", "icon": "🎽", "price": 12000},
        {"id": "top_ocean", "slot": "top", "name": "Ocean Suit", "icon": "🫧", "price": 9000},
        {"id": "top_hacker", "slot": "top", "name": "Matrix Hoodie", "icon": "💻", "price": 8000},
        {"id": "top_gold_blazer", "slot": "top", "name": "Gold Blazer", "icon": "🧥", "price": 18000},
        {"id": "pants_basic", "slot": "pants", "name": "Basic Pants", "icon": "👖", "price": 0},
        {"id": "pants_dark", "slot": "pants", "name": "Dark Pants", "icon": "🩳", "price": 2500},
        {"id": "pants_neon", "slot": "pants", "name": "Neon Nexus Pants", "icon": "🥋", "price": 4200},
        {"id": "pants_royal", "slot": "pants", "name": "Royal Pants", "icon": "👘", "price": 9000},
        {"id": "pants_ocean", "slot": "pants", "name": "Ocean Cargo", "icon": "🌊", "price": 7600},
        {"id": "shoes_basic", "slot": "shoes", "name": "Basic Shoes", "icon": "👟", "price": 0},
        {"id": "shoes_lux", "slot": "shoes", "name": "Luxury Shoes", "icon": "🥾", "price": 6500},
        {"id": "shoes_ocean", "slot": "shoes", "name": "Diver Boots", "icon": "🩴", "price": 7000},
        {"id": "shoes_neon", "slot": "shoes", "name": "Neon Runner", "icon": "⚡", "price": 7200},
        {"id": "acc_none", "slot": "accessory", "name": "Kein Accessoire", "icon": "➖", "price": 0},
        {"id": "acc_glasses", "slot": "accessory", "name": "Matrix Brille", "icon": "🕶️", "price": 4500},
        {"id": "acc_chain", "slot": "accessory", "name": "Goldkette", "icon": "📿", "price": 11000},
        {"id": "acc_crown", "slot": "accessory", "name": "Krone", "icon": "👑", "price": 30000},
        {"id": "acc_headset", "slot": "accessory", "name": "Gaming Headset", "icon": "🎧", "price": 6500},
    ],
}

AVATAR_SLOTS = ("top", "pants", "shoes", "accessory")
AVATAR_BASE_EQUIPPED = {
    "top": "top_basic",
    "pants": "pants_basic",
    "shoes": "shoes_basic",
    "accessory": "acc_none",
}
AVATAR_GENDER_OPTIONS = [("male", "Männlich"), ("female", "Weiblich"), ("diverse", "Divers")]


# ---------- Audio & TTS System ----------
AUDIO_DIR = os.path.join("assets", "audio")
try:
    os.makedirs(AUDIO_DIR, exist_ok=True)
except Exception:
    pass  # read-only filesystem on Render is fine, TTS just won't work
BG_MUSIC_FILE = "bg_music.wav"
THEME_BG_ROOT = "backgrounds"
NEON_THEME_BG_DIR = "neon_nexus"
ROYALE_GOLD_THEME_BG_DIR = "royale_gold"
OCEAN_THEME_BG_DIR = "ocean"
HACKER_MATRIX_THEME_BG_DIR = "hacker_matrix"
THEME_BG_CONFIG = {
    "neon_nexus": {
        "folder": NEON_THEME_BG_DIR,
        "menu": "hintergrund_neon_nexus",
        "game": "hintergrund_bild_neon_nexus",
        "joker": "hintergrund_joker_neon_nexus",
    },
    "royal": {
        "folder": ROYALE_GOLD_THEME_BG_DIR,
        "menu": "hintergrund_royale_gold",
        "joker": "hintergrund_royale_gold_2",
        "game": "hintergrund_royale_gold_3",
    },
    "ocean": {
        "folder": OCEAN_THEME_BG_DIR,
        "menu": "hintergrund_ocean",
        "joker": "hintergrund_ocean_2",
        "game": "hintergrund_ocean_3",
    },
    "hacker": {
        "folder": HACKER_MATRIX_THEME_BG_DIR,
        "menu": "hintergrund_hacker_matrix",
        "joker": "hintergrund_hacker_matrix_2",
        "game": "hintergrund_hacker_matrix_3",
    },
}

def play_tts(page: ft.Page, text: str, state: dict | None = None):
    """Generates an MP3 via gTTS and plays it on the page."""
    if not HAS_TTS:
        return
    if state is not None:
        settings = get_user_settings(state)
        if not bool(settings.get("play_audio", True)):
            return
    
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
        audio_kwargs = {
            "src": f"audio/{BG_MUSIC_FILE}",
            "autoplay": False,
            "volume": 0.22,
        }
        release_mode = getattr(ft, "ReleaseMode", None)
        if release_mode is not None and hasattr(release_mode, "LOOP"):
            audio_kwargs["release_mode"] = release_mode.LOOP
        bg = ft.Audio(**audio_kwargs)
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
        "avatar": default_avatar_profile(),
        "question_profile": {"recent_prompts": [], "performance": {}},
        "custom_points_quizzes": [],
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
    ensure_avatar_defaults(user)
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
    ensure_avatar_defaults(user)
    ensure_question_profile_defaults(user)


def ensure_unlocked_themes(user: dict):
    unlocked = user.setdefault("unlocked_themes", ["classic", "neon_nexus"])
    if not isinstance(unlocked, list):
        unlocked = ["classic", "neon_nexus"]
    cleaned: list[str] = []
    for theme_id in unlocked:
        key = str(theme_id or "").strip()
        if not key or key not in THEMES:
            continue
        if key not in cleaned:
            cleaned.append(key)
    for base_theme in ("classic", "neon_nexus"):
        if base_theme not in cleaned:
            cleaned.append(base_theme)
    user["unlocked_themes"] = cleaned


def get_unlocked_theme_keys(user: dict) -> list[str]:
    ensure_unlocked_themes(user)
    return list(user.get("unlocked_themes", ["classic", "neon_nexus"]))


def _avatar_catalog_by_id() -> dict[str, dict]:
    return {item["id"]: item for item in SHOP_CATALOG.get("avatar_items", [])}


def default_avatar_profile() -> dict:
    owned = list(dict.fromkeys(list(AVATAR_BASE_EQUIPPED.values())))
    return {
        "gender": "male",
        "owned_items": owned,
        "equipped": dict(AVATAR_BASE_EQUIPPED),
    }


def ensure_avatar_defaults(user: dict):
    avatar = user.setdefault("avatar", default_avatar_profile())
    if not isinstance(avatar, dict):
        user["avatar"] = default_avatar_profile()
        avatar = user["avatar"]
    avatar.setdefault("gender", "male")
    if avatar.get("gender") not in {"male", "female", "diverse"}:
        avatar["gender"] = "diverse"

    owned = avatar.setdefault("owned_items", [])
    if not isinstance(owned, list):
        owned = []
        avatar["owned_items"] = owned
    for base_item in AVATAR_BASE_EQUIPPED.values():
        if base_item not in owned:
            owned.append(base_item)

    equipped = avatar.setdefault("equipped", dict(AVATAR_BASE_EQUIPPED))
    if not isinstance(equipped, dict):
        equipped = dict(AVATAR_BASE_EQUIPPED)
        avatar["equipped"] = equipped

    catalog = _avatar_catalog_by_id()
    for slot in AVATAR_SLOTS:
        current = equipped.get(slot, AVATAR_BASE_EQUIPPED[slot])
        item = catalog.get(current)
        if not item or item.get("slot") != slot:
            equipped[slot] = AVATAR_BASE_EQUIPPED[slot]
            current = equipped[slot]
        if current not in owned:
            owned.append(current)


def ensure_stats_defaults(stats: dict):
    for key, value in DEFAULT_USER_STATS.items():
        stats.setdefault(key, value)
    for key, value in EXTRA_STATS_DEFAULTS.items():
        stats.setdefault(key, value)


def ensure_question_profile_defaults(user: dict):
    profile = user.setdefault("question_profile", {})
    if not isinstance(profile, dict):
        profile = {}
        user["question_profile"] = profile

    recent = profile.setdefault("recent_prompts", [])
    if not isinstance(recent, list):
        recent = []
    normalized_recent: list[str] = []
    for entry in recent:
        key = str(entry or "").strip().lower()
        if not key:
            continue
        if key in normalized_recent:
            normalized_recent.remove(key)
        normalized_recent.append(key)
    profile["recent_prompts"] = normalized_recent[-QUESTION_HISTORY_LIMIT:]

    performance = profile.setdefault("performance", {})
    if not isinstance(performance, dict):
        performance = {}
    cleaned_performance: dict[str, dict] = {}
    for raw_key, raw_value in performance.items():
        key = str(raw_key or "").strip().lower()
        if not key or not isinstance(raw_value, dict):
            continue
        seen = max(0, int(raw_value.get("seen", 0)))
        correct = max(0, int(raw_value.get("correct", 0)))
        wrong = max(0, int(raw_value.get("wrong", 0)))
        cleaned_performance[key] = {
            "seen": seen,
            "correct": min(correct, seen if seen else correct),
            "wrong": min(wrong, seen if seen else wrong),
            "last_seen": str(raw_value.get("last_seen", "")),
        }
    if len(cleaned_performance) > QUESTION_PERFORMANCE_LIMIT:
        # Keep the most recent entries first.
        sorted_items = sorted(
            cleaned_performance.items(),
            key=lambda item: str(item[1].get("last_seen", "")),
            reverse=True,
        )[:QUESTION_PERFORMANCE_LIMIT]
        cleaned_performance = dict(sorted_items)
    profile["performance"] = cleaned_performance


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
    user.setdefault("custom_points_quizzes", [])
    ensure_question_profile_defaults(user)


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
    state_settings = state.get("settings")
    if isinstance(state_settings, dict):
        merged = DEFAULT_USER_SETTINGS.copy()
        merged.update(state_settings)
        return merged
    return DEFAULT_USER_SETTINGS.copy()


def get_theme(state: dict) -> dict:
    theme_name = get_user_settings(state).get("theme", "classic")
    email = state.get("current_user_email")
    if email:
        db = load_db()
        user = db.get("users", {}).get(email)
        if user:
            ensure_unlocked_themes(user)
            if theme_name not in user.get("unlocked_themes", []):
                theme_name = "classic"
                user.setdefault("settings", {})["theme"] = "classic"
                save_db(db)
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


def theme_ui_palette(theme: dict) -> dict:
    theme_key = _theme_key_from_theme(theme) or "classic"
    palettes = {
        "royal": {
            "card_bg": "#2B1500CC",
            "card_border": "#F2C94C",
            "hover": "#FFD76A",
            "text": "#FFF6D5",
        },
        "hacker": {
            "card_bg": "#041109D9",
            "card_border": "#00FF41",
            "hover": "#3BFF7A",
            "text": "#D5FFE2",
        },
        "ocean": {
            "card_bg": "#03233AE0",
            "card_border": "#4FC3FF",
            "hover": "#7CE8FF",
            "text": "#EAF9FF",
        },
        "neon_nexus": {
            "card_bg": "#07151DE0",
            "card_border": "#22D3EE",
            "hover": "#D946EF",
            "text": "#F8FAFC",
        },
    }
    default_palette = {
        "card_bg": theme.get("panel", "#0f172acc"),
        "card_border": theme.get("border", "#60A5FA"),
        "hover": theme.get("accent_2", "#C084FC"),
        "text": theme_txt(theme, "primary"),
    }
    return palettes.get(theme_key, default_palette)


def avatar_scene(theme_key: str) -> str:
    return {
        "ocean": "🛥️ U‑Boot Mission",
        "hacker": "💻 Matrix-Konsole",
        "royal": "🏰 Königliche Lounge",
        "neon_nexus": "🌌 Neon Deck",
        "classic": "🎮 Quiz-Studio",
    }.get(theme_key, "🎮 Quiz-Studio")


def avatar_base_emoji(gender: str) -> str:
    return {
        "male": "🧑‍💼",
        "female": "👩‍💼",
        "diverse": "🧑‍🎤",
    }.get(gender, "🧑")


def _resolve_avatar_base_image(gender: str) -> str | None:
    male_tokens = ["avatar_männlich", "avatar_maennlich", "avatarmannlich", "avatar_male", "avatar"]
    female_tokens = ["avatar_weiblich", "avatar_female", "avatar_frau", "avatar_männlich", "avatar_maennlich", "avatar"]
    preferred_tokens = male_tokens if gender != "female" else female_tokens
    if gender == "diverse":
        preferred_tokens = male_tokens + [t for t in female_tokens if t not in male_tokens]

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    try:
        os.makedirs("assets", exist_ok=True)
    except Exception:
        pass

    def collect(folder: str) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        try:
            for f in os.listdir(folder):
                full = os.path.join(folder, f)
                if os.path.isfile(full):
                    stem, ext = os.path.splitext(f)
                    if ext.lower() in (".png", ".webp", ".jpg", ".jpeg", ".gif"):
                        items.append((f, norm(stem)))
        except Exception:
            pass
        return items

    assets_files = collect("assets")
    avatar_files = collect(os.path.join("assets", "avatar"))
    root_files = collect(".")
    alias = "avatar_female_base.png" if gender == "female" else "avatar_male_base.png"
    alias_path = os.path.join("assets", alias)
    if os.path.exists(alias_path):
        return alias

    for token in preferred_tokens:
        nt = norm(token)
        for name, nstem in assets_files:
            if nstem == nt or nstem.startswith(nt):
                src = os.path.join("assets", name)
                try:
                    shutil.copy2(src, alias_path)
                except Exception:
                    return name
                return alias if os.path.exists(alias_path) else name
        for name, nstem in avatar_files:
            if nstem == nt or nstem.startswith(nt):
                src = os.path.join("assets", "avatar", name)
                try:
                    shutil.copy2(src, alias_path)
                except Exception:
                    return src
                return alias if os.path.exists(alias_path) else src
        for name, nstem in root_files:
            if nstem == nt or nstem.startswith(nt):
                src = name
                try:
                    shutil.copy2(src, alias_path)
                except Exception:
                    return name
                return alias if os.path.exists(alias_path) else name
    return None


def _avatar_image_source(asset_name: str | None) -> str | bytes | None:
    if not asset_name:
        return None


def _ensure_bg_music_control(page: ft.Page, state: dict) -> ft.Audio | None:
    audio = state.get("_bg_music_audio")
    if audio is not None:
        return audio
    audio = init_bg_music(page)
    if audio is None:
        return None
    state["_bg_music_audio"] = audio
    try:
        if audio not in page.overlay:
            page.overlay.append(audio)
    except Exception:
        pass
    return audio


async def _sync_bg_music_async(page: ft.Page, state: dict):
    audio = _ensure_bg_music_control(page, state)
    if audio is None:
        return
    settings = get_user_settings(state)
    enabled = bool(settings.get("play_audio", True)) and bool(settings.get("background_music", True))
    try:
        if enabled:
            await audio.resume()
        else:
            await audio.pause()
    except Exception:
        try:
            if enabled:
                await audio.play()
            else:
                await audio.pause()
        except Exception:
            pass
    candidates = [
        os.path.join("assets", asset_name),
        asset_name,
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except Exception:
                return asset_name
    return asset_name


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


def _set_resize_view(state: dict, renderer, *args, **kwargs):
    state["_resize_renderer"] = renderer
    state["_resize_args"] = args
    state["_resize_kwargs"] = kwargs


def _run_resize_view(page: ft.Page, state: dict) -> bool:
    renderer = state.get("_resize_renderer")
    if not callable(renderer):
        return False
    try:
        renderer(page, state, *(state.get("_resize_args") or ()), **(state.get("_resize_kwargs") or {}))
        return True
    except Exception as ex:
        print(f"Resize rerender error: {ex}")
        return False


def _sync_page_route(page: ft.Page, route: str):
    try:
        if getattr(page, "route", None) != route:
            page.route = route
    except Exception:
        pass


def _settings_button(page: ft.Page, state: dict, size: int = 16) -> ft.Container:
    return ft.Container(
        content=ft.Icon(ft.Icons.SETTINGS, size=size, color="white"),
        bgcolor="#0000008f",
        border_radius=14,
        padding=ft.Padding(8, 6, 8, 6),
        on_click=lambda e: show_settings_view(page, state),
        tooltip="Einstellungen",
    )


def _go_route_or_render(page: ft.Page, route: str, renderer, state: dict):
    try:
        if getattr(page, "route", None) == route:
            renderer(page, state)
        else:
            page.go(route)
    except Exception:
        renderer(page, state)


def _go_home(page: ft.Page, state: dict):
    _go_route_or_render(page, "/", open_main_menu, state)


def _is_video_background(src: str | None) -> bool:
    return bool(src) and str(src).lower().endswith(".mp4")


def _theme_key_from_theme(theme: dict | None) -> str | None:
    if not theme:
        return None
    label = theme.get("label")
    for key, entry in THEMES.items():
        if entry.get("label") == label:
            return key
    return None


def _is_themed_video_theme(theme: dict | None) -> bool:
    return (_theme_key_from_theme(theme) or "") in THEME_BG_CONFIG


def _resolve_theme_background(theme_key: str, role: str, allow_video: bool = True) -> str | None:
    cfg = THEME_BG_CONFIG.get(theme_key)
    if not cfg:
        return None
    stem = cfg.get(role)
    if not stem:
        return None
    folder = cfg.get("folder")
    if not folder:
        return None

    video_exts = [".mp4", ".webm", ".mov", ".m4v"]
    image_exts = [".gif", ".png", ".jpg", ".jpeg"]
    exts = (video_exts + image_exts) if allow_video else image_exts

    folder_abs = os.path.join("assets", THEME_BG_ROOT, folder)
    folder_rel = f"{THEME_BG_ROOT}/{folder}"
    if not os.path.isdir(folder_abs):
        return None

    target_stem = stem.lower()
    files_by_lower = {name.lower(): name for name in os.listdir(folder_abs)}
    for ext in exts:
        candidate = f"{target_stem}{ext}"
        real_name = files_by_lower.get(candidate)
        if real_name:
            return f"{folder_rel}/{real_name}"
    return None


def _video_poster_source(src: str | None) -> str | None:
    if not src or not _is_video_background(src):
        return None
    folder, filename = os.path.split(src)
    stem, _ext = os.path.splitext(filename)
    folder_abs = os.path.join("assets", folder) if folder else "assets"
    if not os.path.isdir(folder_abs):
        return None
    files_by_lower = {name.lower(): name for name in os.listdir(folder_abs)}
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        real_name = files_by_lower.get(f"{stem.lower()}{ext}")
        if real_name:
            return f"{folder}/{real_name}" if folder else real_name
    return None


def _build_looping_background_from_src(page: ft.Page, src: str | None) -> ft.Control | None:
    if not src:
        return None
    page_w, page_h = _page_size(page)
    width, height = max(1, int(page_w)), max(1, int(page_h))

    if _is_video_background(src) and FletVideo and VideoMedia and PlaylistMode:
        video = FletVideo(
            expand=True,
            width=width,
            height=height,
            playlist=[VideoMedia(src)],
            playlist_mode=PlaylistMode.LOOP,
            autoplay=True,
            muted=True,
            fill_color="#120D06",
            fit=ft.BoxFit.COVER,
            show_controls=False,
            aspect_ratio=None,
        )
        poster_src = _video_poster_source(src)
        if poster_src:
            return ft.Stack(
                [
                    ft.Image(src=poster_src, fit=ft.BoxFit.COVER, width=width, height=height),
                    video,
                ],
                expand=True,
            )
        return video

    return ft.Image(
        src=src,
        fit=ft.BoxFit.COVER,
        width=width,
        height=height,
    )


def _build_looping_menu_background(page: ft.Page, theme: dict) -> ft.Control | None:
    theme_key = _theme_key_from_theme(theme)
    if not theme_key:
        return None
    src = _resolve_theme_background(theme_key, "menu", allow_video=bool(FletVideo and VideoMedia and PlaylistMode))
    return _build_looping_background_from_src(page, src)


def _build_looping_joker_background(page: ft.Page, theme: dict) -> ft.Control | None:
    theme_key = _theme_key_from_theme(theme)
    if not theme_key:
        return None
    src = _resolve_theme_background(theme_key, "joker", allow_video=bool(FletVideo and VideoMedia and PlaylistMode))
    return _build_looping_background_from_src(page, src)


def _themed_screen_background(page: ft.Page, theme: dict, overlay_color: str = "#00000088") -> ft.Control:
    bg = _build_looping_menu_background(page, theme)
    if bg:
        return ft.Stack(
            [
                bg,
                ft.Container(expand=True, bgcolor=overlay_color),
            ],
            expand=True,
        )
    return ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=theme["gradient"],
        ),
    )


def _theme_action_button(
    label: str,
    theme: dict,
    on_click,
    *,
    width: int = 240,
    bg: str | None = None,
) -> ft.Container:
    ui = theme_ui_palette(theme)
    color_bg = bg or ui["card_bg"]
    border_color = ui["card_border"]
    btn = ft.Container(
        content=ft.Text(label, size=16, weight="bold", color=ui["text"]),
        on_click=on_click,
        bgcolor=color_bg,
        border_radius=30,
        padding=ft.Padding(30, 12, 30, 12),
        alignment=ft.Alignment(0, 0),
        width=width,
        border=ft.border.Border.all(1.8, border_color),
        shadow=ft.BoxShadow(blur_radius=14, color=f"#55{border_color[1:]}", spread_radius=0),
    )

    def on_hover(e):
        hovering = e.data == "true"
        hover_color = ui["hover"]
        e.control.border = ft.border.Border.all(2.8 if hovering else 1.8, hover_color if hovering else border_color)
        e.control.shadow = ft.BoxShadow(
            blur_radius=26 if hovering else 14,
            color=f"#88{hover_color[1:]}" if hovering else f"#55{border_color[1:]}",
            spread_radius=2 if hovering else 0,
        )
        e.control.scale = 1.03 if hovering else 1.0
        e.control.update()

    btn.on_hover = on_hover
    btn.animate_scale = ft.Animation(180, ft.AnimationCurve.EASE_OUT)
    return btn


def _themed_game_background(bg_image: str, page_w: float, page_h: float, overlay_color: str) -> ft.Stack:
    """Background stretched to the full viewport (bottom layer in game Stack)."""
    w, h = max(1, int(page_w)), max(1, int(page_h))
    if _is_video_background(bg_image) and FletVideo and VideoMedia and PlaylistMode:
        video = FletVideo(
            width=w,
            height=h,
            playlist=[VideoMedia(bg_image)],
            playlist_mode=PlaylistMode.LOOP,
            autoplay=True,
            muted=True,
            fill_color="#120D06",
            fit=ft.BoxFit.COVER,
            show_controls=False,
            aspect_ratio=None,
        )
        poster_src = _video_poster_source(bg_image)
        media = ft.Stack(
            [
                ft.Image(src=poster_src, fit=ft.BoxFit.COVER, width=w, height=h) if poster_src else ft.Container(width=w, height=h, bgcolor="#120D06"),
                video,
            ],
            width=w,
            height=h,
        )
    else:
        media = ft.Image(src=bg_image, fit=ft.BoxFit.FILL, width=w, height=h)

    return ft.Stack(
        [
            media,
            ft.Container(width=w, height=h, bgcolor=overlay_color),
        ],
        width=w,
        height=h,
    )


def _set_themed_game_resize(page: ft.Page, state: dict):
    state["_themed_game_active"] = True


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
        u["shop_coins"] = u.get("shop_coins", 0) + _coins_for_money_level(money_level_idx)
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


def get_achievement_definitions() -> list[dict]:
    return ACHIEVEMENT_DEFINITIONS


def _unlock_achievement(unlocked: list[str], newly_unlocked: list[str], achievement_id: str, achievement_name: str, condition: bool):
    if condition and achievement_id not in unlocked:
        unlocked.append(achievement_id)
        newly_unlocked.append(achievement_name)


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
POINTS_QUIZ_POINT_VALUES = [20, 40, 60, 80, 100]
POINTS_QUIZ_DEFAULT_CATEGORIES = 5
POINTS_QUIZ_MIN_CATEGORIES = 2
POINTS_QUIZ_MAX_CATEGORIES = 12
POINTS_QUIZ_MIN_TEAMS = 2
POINTS_QUIZ_MAX_TEAMS = 6
POINTS_QUIZ_AGE_OPTIONS = [
    ("young", "6 - 10 Jahre"),
    ("mid", "11 - 16 Jahre"),
    ("old", "Ab 16 Jahre"),
]

POINTS_QUIZ_RANDOM_BANK = {
    "young": {
        "Englisch": {
            20: [
                {"question": "Wie heißt 'Katze' auf Englisch?", "answer": "Cat."},
                {"question": "Wie heißt 'Haus' auf Englisch?", "answer": "House."},
                {"question": "Wie heißt 'Schule' auf Englisch?", "answer": "School."},
                {"question": "Wie heißt 'Wasser' auf Englisch?", "answer": "Water."},
            ],
            40: [
                {"question": "Wie heißt die Mehrzahl von 'dog'?", "answer": "Dogs."},
                {"question": "Wie heißt die Mehrzahl von 'book'?", "answer": "Books."},
                {"question": "Wie heißt 'Ich bin' auf Englisch?", "answer": "I am."},
                {"question": "Wie heißt 'Wir sind' auf Englisch?", "answer": "We are."},
            ],
            60: [
                {"question": "Setze richtig ein: 'She ___ my friend.'", "answer": "Is."},
                {"question": "Setze richtig ein: 'They ___ in class.'", "answer": "Are."},
                {"question": "Was ist die Vergangenheit von 'play'?", "answer": "Played."},
                {"question": "Wie fragt man auf Englisch: 'Wie heißt du?'", "answer": "What is your name?"},
            ],
            80: [
                {"question": "Setze ein: 'He ___ not like milk.'", "answer": "Does."},
                {"question": "Welche Form ist richtig: 'a apple' oder 'an apple'?", "answer": "An apple."},
                {"question": "Was ist die Steigerung von 'small'?", "answer": "Smaller."},
                {"question": "Was ist die Steigerung von 'happy'?", "answer": "Happier."},
            ],
            100: [
                {"question": "Bilde den Satz im Present Progressive: 'Ich lese gerade.'", "answer": "I am reading."},
                {"question": "Setze richtig ein: 'Yesterday we ___ to school.'", "answer": "Went."},
                {"question": "Welche Form ist korrekt: 'There is' oder 'There are' bei mehreren Dingen?", "answer": "There are."},
                {"question": "Übersetze: 'Wenn es regnet, bleiben wir drinnen.'", "answer": "If it rains, we stay inside."},
            ],
        },
        "Sport": {
            20: [
                {"question": "Wie heißt ein bekannter Ballsport mit Toren?", "answer": "Fußball."},
                {"question": "Mit welchem Körperteil wirft man beim Basketball meistens?", "answer": "Mit den Händen."},
                {"question": "Wie viele Spieler hat eine Fußballmannschaft auf dem Feld?", "answer": "11."},
                {"question": "Welche Farbe hat oft eine Sieger-Medaille für Platz 1?", "answer": "Gold."},
            ],
            40: [
                {"question": "Wie viele Punkte bringt ein Freiwurf im Basketball?", "answer": "1 Punkt."},
                {"question": "Wie nennt man den Startsprung beim Schwimmen?", "answer": "Startsprung vom Block."},
                {"question": "Wie viele Halbzeiten hat ein Fußballspiel?", "answer": "2."},
                {"question": "Wie viele Sätze gewinnt man meist im Tischtennis-Spiel?", "answer": "3 Gewinnsaetze (best of 5)."},
            ],
            60: [
                {"question": "Wie lang ist ein Marathon?", "answer": "42,195 Kilometer."},
                {"question": "Wie nennt man den Strafstoß im Fußball?", "answer": "Elfmeter."},
                {"question": "Wie viele Spieler hat ein Volleyball-Team auf dem Feld?", "answer": "6."},
                {"question": "Was bedeutet ein 'Ass' im Tennis?", "answer": "Direkter Punkt durch Aufschlag."},
            ],
            80: [
                {"question": "Wie heißt die olympische Mehrkampf-Sportart aus 10 Disziplinen?", "answer": "Zehnkampf."},
                {"question": "Wie oft finden Olympische Sommerspiele regulär statt?", "answer": "Alle 4 Jahre."},
                {"question": "Wie viele Minuten dauert ein Handballspiel im Erwachsenenbereich?", "answer": "60 Minuten."},
                {"question": "Wie heißt die Linie im Basketball, von der man 3 Punkte werfen kann?", "answer": "Dreierlinie."},
            ],
            100: [
                {"question": "Welche Kartenfarbe steht im Fußball für Feldverweis?", "answer": "Rot."},
                {"question": "Wie viele Meter ist ein Elfmeter vom Tor entfernt?", "answer": "11 Meter."},
                {"question": "Wie heißt die Technik, bei der man im Hochsprung rücklings springt?", "answer": "Fosbury-Flop."},
                {"question": "Welches Land gewann die FIFA-WM 2014?", "answer": "Deutschland."},
            ],
        },
        "Natur & Tiere": {
            20: [
                {"question": "Welches Tier sagt 'Miau'?", "answer": "Die Katze."},
                {"question": "Welches Tier gibt Milch: Kuh oder Löwe?", "answer": "Kuh."},
                {"question": "Wie heißt das große graue Tier mit Rüssel?", "answer": "Elefant."},
                {"question": "Welches Insekt sammelt Honig?", "answer": "Die Biene."},
            ],
            40: [
                {"question": "Wie nennt man ein Tier, das im Wasser und an Land lebt?", "answer": "Amphib."},
                {"question": "Was fressen Kühe hauptsächlich?", "answer": "Gras."},
                {"question": "Wie heißen junge Hunde?", "answer": "Welpen."},
                {"question": "Welcher Vogel kann nicht fliegen und lebt am Südpol?", "answer": "Pinguin."},
            ],
            60: [
                {"question": "Wie nennt man den Lebensraum vieler Tiere und Pflanzen?", "answer": "Oekosystem."},
                {"question": "Wie heißt die Schutzhülle eines Eies?", "answer": "Eierschale."},
                {"question": "Was brauchen Pflanzen außer Wasser zum Wachsen?", "answer": "Licht."},
                {"question": "Wie nennt man Tiere, die nur Pflanzen fressen?", "answer": "Pflanzenfresser."},
            ],
            80: [
                {"question": "Wie heißt der Prozess, bei dem Pflanzen mit Licht Zucker bilden?", "answer": "Fotosynthese."},
                {"question": "Welches Tier ist ein Säugetier: Hai oder Delfin?", "answer": "Delfin."},
                {"question": "Wie heißt das größte Landraubtier der Arktis?", "answer": "Eisbär."},
                {"question": "Wie nennt man den Wechsel von Raupe zu Schmetterling?", "answer": "Metamorphose."},
            ],
            100: [
                {"question": "Wie nennt man Arten, die nur in einem Gebiet vorkommen?", "answer": "Endemische Arten."},
                {"question": "Was bedeutet 'nachtaktiv'?", "answer": "Vor allem nachts aktiv."},
                {"question": "Wie nennt man Tiere, die in Winterruhe oder Winterschlaf gehen?", "answer": "Winterschlaefer."},
                {"question": "Wie nennt man den Schutz gefährdeter Lebensräume und Arten?", "answer": "Naturschutz."},
            ],
        },
        "Geografie": {
            20: [
                {"question": "Wie heißt die Hauptstadt von Deutschland?", "answer": "Berlin."},
                {"question": "Welcher Kontinent ist Deutschland zugeordnet?", "answer": "Europa."},
                {"question": "Wie heißt die Hauptstadt von Frankreich?", "answer": "Paris."},
                {"question": "Wie heißt der größte Ozean?", "answer": "Pazifik."},
            ],
            40: [
                {"question": "Welcher Fluss fließt durch Köln?", "answer": "Rhein."},
                {"question": "Welches Land hat die Hauptstadt Rom?", "answer": "Italien."},
                {"question": "Wie heißt die Hauptstadt von Spanien?", "answer": "Madrid."},
                {"question": "Wie heißt das Gebirge zwischen Frankreich und Spanien?", "answer": "Pyrenaeen."},
            ],
            60: [
                {"question": "Wie heißt der höchste Berg der Erde?", "answer": "Mount Everest."},
                {"question": "Welche Wüste ist die größte heiße Wüste?", "answer": "Sahara."},
                {"question": "Wie heißt die Hauptstadt von Norwegen?", "answer": "Oslo."},
                {"question": "Welches Meer liegt zwischen Europa und Afrika?", "answer": "Mittelmeer."},
            ],
            80: [
                {"question": "Wie heißt die Hauptstadt von Australien?", "answer": "Canberra."},
                {"question": "Welcher Kontinent hat die meisten Staaten?", "answer": "Afrika."},
                {"question": "Welche Meerenge trennt Europa von Afrika bei Spanien?", "answer": "Strasse von Gibraltar."},
                {"question": "Wie heißt der längste Fluss der Welt nach vielen Schulbüchern?", "answer": "Nil."},
            ],
            100: [
                {"question": "Welche Länder grenzen an Deutschland im Westen? Nenne zwei.", "answer": "Zum Beispiel Frankreich, Belgien, Niederlande oder Luxemburg."},
                {"question": "Wie heißt das Hochland im Inneren Spaniens?", "answer": "Meseta."},
                {"question": "Welcher Staat hat die Hauptstadt Reykjavik?", "answer": "Island."},
                {"question": "Welche Klimazone liegt rund um den Äquator?", "answer": "Tropische Klimazone."},
            ],
        },
        "Musik": {
            20: [
                {"question": "Wie viele Linien hat ein Notensystem?", "answer": "5."},
                {"question": "Wie heißt ein Instrument mit Tasten: Klavier oder Trommel?", "answer": "Klavier."},
                {"question": "Wie nennt man ein Lied mit zwei Singenden?", "answer": "Duett."},
                {"question": "Wie heißt sehr leise in der Musik?", "answer": "Piano."},
            ],
            40: [
                {"question": "Welches Symbol erhöht einen Ton um einen Halbton?", "answer": "Kreuz."},
                {"question": "Wie heißt ein sehr schnelles Tempo oft auf Italienisch?", "answer": "Presto."},
                {"question": "Wie viele Saiten hat eine Violine?", "answer": "4."},
                {"question": "Wie nennt man eine Gruppe mit vielen Instrumenten?", "answer": "Orchester."},
            ],
            60: [
                {"question": "Wie heißt ein Musikstück für ein Instrument allein?", "answer": "Solo."},
                {"question": "Wie nennt man den Grundschlag eines Liedes?", "answer": "Takt."},
                {"question": "Welche Note kommt im Deutschen nach A?", "answer": "H."},
                {"question": "Wie nennt man den Anfang eines Liedes?", "answer": "Intro."},
            ],
            80: [
                {"question": "Wie heißt eine Tonleiter aus 8 Tönen?", "answer": "Oktave."},
                {"question": "Was bedeutet 'forte'?", "answer": "Laut."},
                {"question": "Wie heißt die Pause über einen ganzen Takt im 4/4-Takt?", "answer": "Ganze Pause."},
                {"question": "Wie nennt man ein Werk für Orchester ohne Gesang?", "answer": "Sinfonie."},
            ],
            100: [
                {"question": "Wie heißt das Symbol, das einen Ton erniedrigt?", "answer": "B."},
                {"question": "Wie nennt man das gleichzeitige Klingen mehrerer Töne?", "answer": "Akkord."},
                {"question": "Wie nennt man den Übergang von langsam zu schneller?", "answer": "Accelerando."},
                {"question": "Wie heißt die Wiederholung eines Themas in einer Fuge?", "answer": "Einsatz."},
            ],
        },
        "Mathe": {
            20: [
                {"question": "Was ist 7 + 6?", "answer": "13."},
                {"question": "Was ist 10 - 4?", "answer": "6."},
                {"question": "Was ist 5 x 5?", "answer": "25."},
                {"question": "Was ist 36 : 6?", "answer": "6."},
            ],
            40: [
                {"question": "Wie viele Grad hat ein rechter Winkel?", "answer": "90."},
                {"question": "Was ist 12 x 8?", "answer": "96."},
                {"question": "Was ist die Hälfte von 150?", "answer": "75."},
                {"question": "Wie viel ist 25 Prozent von 100?", "answer": "25."},
            ],
            60: [
                {"question": "Was ist die Quadratwurzel von 144?", "answer": "12."},
                {"question": "Wie viele Seiten hat ein Hexagon?", "answer": "6."},
                {"question": "Was ist 0,5 als Bruch?", "answer": "1/2."},
                {"question": "Was ist 15 Prozent von 200?", "answer": "30."},
            ],
            80: [
                {"question": "Wie lautet 9 hoch 2?", "answer": "81."},
                {"question": "Wie viele Minuten sind 2,5 Stunden?", "answer": "150."},
                {"question": "Löse: 3x + 5 = 20.", "answer": "x = 5."},
                {"question": "Wie groß ist der Umfang eines Quadrats mit Seitenlänge 7?", "answer": "28."},
            ],
            100: [
                {"question": "Wie lautet die Formel für den Flächeninhalt eines Rechtecks?", "answer": "Laenge mal Breite."},
                {"question": "Was ist das Ergebnis von 1000 - 275?", "answer": "725."},
                {"question": "Wie lautet die Dezimalzahl zu 3/8?", "answer": "0,375."},
                {"question": "Ein Zug fährt 120 km in 2 Stunden. Wie hoch ist die Durchschnittsgeschwindigkeit?", "answer": "60 km/h."},
            ],
        },
        "Deutsch": {
            20: [
                {"question": "Wie heißt die Mehrzahl von 'Haus'?", "answer": "Haeuser."},
                {"question": "Welches Satzzeichen beendet eine Frage?", "answer": "Fragezeichen."},
                {"question": "Was ist das Gegenteil von 'laut'?", "answer": "Leise."},
                {"question": "Wie heißt die Grundform eines Verbs?", "answer": "Infinitiv."},
            ],
            40: [
                {"question": "Welche Wortart ist 'schnell'?", "answer": "Adjektiv."},
                {"question": "Wie nennt man Wörter mit gleicher Bedeutung?", "answer": "Synonyme."},
                {"question": "Wie lautet die Mehrzahl von 'Kind'?", "answer": "Kinder."},
                {"question": "Welches Wort ist ein Verb: 'laufen' oder 'blau'?", "answer": "Laufen."},
            ],
            60: [
                {"question": "Setze das richtige Pronomen ein: '___ gehe nach Hause.'", "answer": "Ich."},
                {"question": "Wie nennt man das Gegenteil eines Wortes?", "answer": "Antonym."},
                {"question": "Was ist die Vergangenheit von 'gehen'?", "answer": "Ging."},
                {"question": "Welche Zeitform ist: 'Ich habe gelernt'?", "answer": "Perfekt."},
            ],
            80: [
                {"question": "Welche Fallfrage passt zu Dativ?", "answer": "Wem?"},
                {"question": "Wie heißt der 4. Fall?", "answer": "Akkusativ."},
                {"question": "Welche Wortart ist 'und'?", "answer": "Konjunktion."},
                {"question": "Wie nennt man einen Satz ohne Verb?", "answer": "Nominalsatz."},
            ],
            100: [
                {"question": "Setze ein passendes Relativpronomen ein: 'Das Buch, ___ ich lese ...'", "answer": "Das."},
                {"question": "Wie heißt die Steigerung von 'gut'?", "answer": "Besser, am besten."},
                {"question": "Welche Satzart ist: 'Mach die Tür zu!'", "answer": "Imperativsatz."},
                {"question": "Wie heißt die Nomenbildung zu 'entscheiden'?", "answer": "Entscheidung."},
            ],
        },
        "Allgemeinwissen": {
            20: [
                {"question": "Wie viele Tage hat eine Woche?", "answer": "7."},
                {"question": "Welche Farbe entsteht aus Blau und Gelb?", "answer": "Gruen."},
                {"question": "Wie viele Monate hat ein Jahr?", "answer": "12."},
                {"question": "Welcher Monat hat meistens 28 Tage?", "answer": "Februar."},
            ],
            40: [
                {"question": "Wie viele Minuten hat eine Stunde?", "answer": "60."},
                {"question": "Wie viele Kontinente gibt es meist in der Schule?", "answer": "7."},
                {"question": "Welcher Planet heißt auch roter Planet?", "answer": "Mars."},
                {"question": "Welche Himmelsrichtung ist gegenüber von Westen?", "answer": "Osten."},
            ],
            60: [
                {"question": "Wie viele Sekunden hat eine Minute?", "answer": "60."},
                {"question": "Wie viele Tage hat ein Schaltjahr?", "answer": "366."},
                {"question": "Wie viele Minuten hat ein Tag?", "answer": "1440."},
                {"question": "Wie heißt unser Heimatplanet?", "answer": "Erde."},
            ],
            80: [
                {"question": "Wie viele Knochen hat ein erwachsener Mensch ungefähr?", "answer": "206."},
                {"question": "Wie heißt das größte Organ des Menschen?", "answer": "Haut."},
                {"question": "Welche Zahl ist eine Primzahl: 21, 23 oder 27?", "answer": "23."},
                {"question": "Wie viele Farben hat ein klassischer Regenbogen?", "answer": "7."},
            ],
            100: [
                {"question": "Wie heißt das Messgerät für Temperatur?", "answer": "Thermometer."},
                {"question": "Was ist schneller: Schall oder Licht?", "answer": "Licht."},
                {"question": "Wie heißt der Vorgang, wenn Wasser zu Eis wird?", "answer": "Gefrieren."},
                {"question": "Welche Einheit wird für elektrische Stromstärke genutzt?", "answer": "Ampere."},
            ],
        },
    },
    "mid": {
        "Englisch": {
            20: [
                {"question": "Wie heißt 'Straße' auf Englisch?", "answer": "Street."},
                {"question": "Wie heißt 'Fenster' auf Englisch?", "answer": "Window."},
                {"question": "Wie heißt 'Frühstück' auf Englisch?", "answer": "Breakfast."},
                {"question": "Wie heißt 'lernen' auf Englisch?", "answer": "Learn."},
            ],
            40: [
                {"question": "Bilde die Mehrzahl von 'child'.", "answer": "Children."},
                {"question": "Bilde die Mehrzahl von 'city'.", "answer": "Cities."},
                {"question": "Setze ein: 'She ___ to school every day.'", "answer": "Goes."},
                {"question": "Setze ein: 'We ___ football on Fridays.'", "answer": "Play."},
            ],
            60: [
                {"question": "Welche Form ist korrekt: 'much people' oder 'many people'?", "answer": "Many people."},
                {"question": "Setze korrekt ein: 'I have lived here ___ 2020.'", "answer": "Since."},
                {"question": "Welche Zeit ist: 'They have finished their homework.'", "answer": "Present Perfect."},
                {"question": "Wie lautet die Komparativform von 'good'?", "answer": "Better."},
            ],
            80: [
                {"question": "Setze ein: 'If I ___ more time, I would travel.'", "answer": "Had."},
                {"question": "Wandle um ins Passive: 'They build houses.'", "answer": "Houses are built."},
                {"question": "Welche Form ist richtig: 'fewer' oder 'less' bei zählbaren Nomen?", "answer": "Fewer."},
                {"question": "Setze ein: 'He asked me ___ I could help him.'", "answer": "If/whether."},
            ],
            100: [
                {"question": "Nenne den Unterschied zwischen 'present perfect' und 'simple past' in einem Satz.", "answer": "Present perfect verbindet zur Gegenwart, simple past ist abgeschlossene Vergangenheit."},
                {"question": "Forme in reported speech um: 'I am tired,' she said.", "answer": "She said that she was tired."},
                {"question": "Setze korrekt ein: 'Hardly ___ he arrived when it started to rain.'", "answer": "Had."},
                {"question": "Welche Verbform folgt auf 'wish' für irreale Gegenwart?", "answer": "Simple past."},
            ],
        },
        "Sport": {
            20: [
                {"question": "Wie viele Ringe hat das olympische Symbol?", "answer": "5."},
                {"question": "In welcher Sportart gibt es einen Slam Dunk?", "answer": "Basketball."},
                {"question": "Wie nennt man den Torhüter beim Handball oft?", "answer": "Torwart."},
                {"question": "Wie lange dauert eine Halbzeit im Fußball?", "answer": "45 Minuten."},
            ],
            40: [
                {"question": "Wie viele Spieler stehen bei Volleyball pro Team auf dem Feld?", "answer": "6."},
                {"question": "Wie heißt ein Unentschieden im Tennis ohne Entscheidungssatz?", "answer": "Tie-Break als Entscheidung eines Satzes."},
                {"question": "Wie viele Basen hat ein Baseball-Feld?", "answer": "4."},
                {"question": "Wie viele Punkte bringt ein Touchdown im American Football ohne Extrapunkt?", "answer": "6."},
            ],
            60: [
                {"question": "Wie lang ist ein olympisches Schwimmbecken?", "answer": "50 Meter."},
                {"question": "Wie heißt der wichtigste Vereinswettbewerb im europäischen Fußball?", "answer": "UEFA Champions League."},
                {"question": "Wie nennt man den Ballbesitzwechsel im Basketball nach Regelverstoß?", "answer": "Turnover."},
                {"question": "Welcher Belag ist bei den French Open üblich?", "answer": "Sand."},
            ],
            80: [
                {"question": "Wie viele Minuten dauert ein NBA-Spiel regulär?", "answer": "48 Minuten."},
                {"question": "In welcher Disziplin startet man im Block und läuft über 110 m Hürden (Männer)?", "answer": "Huerdenlauf."},
                {"question": "Wie heißt die Regel, die im Fußball eine Angriffsposition begrenzt?", "answer": "Abseitsregel."},
                {"question": "Wie heißt die Wurftechnik beim Kugelstoßen, bei der man gleitet?", "answer": "O'Brien-Technik (Gleittechnik)."},
            ],
            100: [
                {"question": "Welche Nation gewann die Fußball-WM 2018?", "answer": "Frankreich."},
                {"question": "Was bedeutet VO2max im Ausdauersport?", "answer": "Maximale Sauerstoffaufnahme."},
                {"question": "Wie lang ist eine Runde auf einer Standard-Laufbahn?", "answer": "400 Meter."},
                {"question": "Was ist ein Triple-Double im Basketball?", "answer": "Zweistellige Werte in drei Statistik-Kategorien."},
            ],
        },
        "Biologie": {
            20: [
                {"question": "Welches Organ pumpt Blut?", "answer": "Herz."},
                {"question": "Wie heißt der grüne Farbstoff in Pflanzen?", "answer": "Chlorophyll."},
                {"question": "Welches Gas atmen wir ein?", "answer": "Sauerstoff."},
                {"question": "Wie nennt man die kleinste lebende Einheit?", "answer": "Zelle."},
            ],
            40: [
                {"question": "Wie heißt der Prozess der Zellteilung im Körperwachstum?", "answer": "Mitose."},
                {"question": "Welche Blutkörperchen sind für die Immunabwehr wichtig?", "answer": "Weiße Blutkörperchen."},
                {"question": "Wie nennt man Tiere, die gleichwarm sind?", "answer": "Endotherme/Gleichwarme Tiere."},
                {"question": "Wie heißt das Erbmaterial in den Zellen?", "answer": "DNA."},
            ],
            60: [
                {"question": "Welches Organ entgiftet den Körper stark?", "answer": "Leber."},
                {"question": "Wie nennt man die Herstellung von Eiweißen in der Zelle?", "answer": "Proteinsynthese."},
                {"question": "Welche Zellorganellen erzeugen Energie (ATP)?", "answer": "Mitochondrien."},
                {"question": "Wie nennt man den Stoffaustausch zwischen Lunge und Blut?", "answer": "Diffusion/Gasaustausch."},
            ],
            80: [
                {"question": "Wie heißt der Prozess, bei dem aus einer mRNA ein Protein entsteht?", "answer": "Translation."},
                {"question": "Was ist der Unterschied zwischen Genotyp und Phänotyp kurz?", "answer": "Genotyp ist Erbanlage, Phänotyp ist sichtbare Ausprägung."},
                {"question": "Wie nennt man die aktive Immunisierung im Alltag?", "answer": "Impfung."},
                {"question": "Welche Phase der Meiose halbiert den Chromosomensatz?", "answer": "Meiose I (Reduktionsteilung)."},
            ],
            100: [
                {"question": "Wie nennt man die Veränderung der Allelhäufigkeit in Populationen?", "answer": "Evolution/Mikroevolution."},
                {"question": "Was beschreibt die Hardy-Weinberg-Regel?", "answer": "Genetisches Gleichgewicht in idealer Population."},
                {"question": "Wie heißt der programmierte Zelltod?", "answer": "Apoptose."},
                {"question": "Welche Struktur trennt in Pflanzenzellen Vakuole und Cytoplasma?", "answer": "Tonoplast."},
            ],
        },
        "Geschichte": {
            20: [
                {"question": "In welchem Jahr fiel die Berliner Mauer?", "answer": "1989."},
                {"question": "Wie hieß das geteilte Ostdeutschland von 1949 bis 1990?", "answer": "DDR."},
                {"question": "In welchem Land stehen die Pyramiden von Gizeh?", "answer": "Ägypten."},
                {"question": "Wer war erster Bundeskanzler der BRD?", "answer": "Konrad Adenauer."},
            ],
            40: [
                {"question": "Wie heißt die Epoche des Aufblühens von Kunst und Wissenschaft in Europa?", "answer": "Renaissance."},
                {"question": "Welche Stadt war Zentrum des Römischen Reiches?", "answer": "Rom."},
                {"question": "Wann begann der Erste Weltkrieg?", "answer": "1914."},
                {"question": "Wie heißt der Vertrag von 1919 nach dem Ersten Weltkrieg?", "answer": "Versailler Vertrag."},
            ],
            60: [
                {"question": "Wann endete der Zweite Weltkrieg in Europa?", "answer": "1945."},
                {"question": "Wie hieß die deutsche Wiedervereinigung politisch?", "answer": "Deutsche Einheit 1990."},
                {"question": "Welche Schiffe nutzte Kolumbus 1492? Nenne eines.", "answer": "Santa Maria, Nina oder Pinta."},
                {"question": "Wie nennt man die Umwälzung von Handarbeit zu Maschinenarbeit ab dem 18. Jahrhundert?", "answer": "Industrielle Revolution."},
            ],
            80: [
                {"question": "Wann wurde die Bundesrepublik Deutschland gegründet?", "answer": "1949."},
                {"question": "Wie heißt die friedliche Revolution in Osteuropa 1989/90 kurz?", "answer": "Systemwandel/Ende des Ostblocks."},
                {"question": "Was war der Kalte Krieg in einem Satz?", "answer": "Konflikt zwischen USA und UdSSR ohne direkten Großkrieg."},
                {"question": "In welchem Jahr wurde die Europäische Union durch den Maastricht-Vertrag gegründet?", "answer": "1993."},
            ],
            100: [
                {"question": "Welches Ereignis gilt als Auslöser des Ersten Weltkriegs?", "answer": "Attentat von Sarajevo."},
                {"question": "Wie nennt man den Wiederaufbauplan der USA für Europa nach 1945?", "answer": "Marshallplan."},
                {"question": "Wann fand die Französische Revolution statt (Beginn)?", "answer": "1789."},
                {"question": "Welche Mauer trennte Berlin von 1961 bis 1989?", "answer": "Berliner Mauer."},
            ],
        },
        "Geografie": {
            20: [
                {"question": "Wie heißt die Hauptstadt von Italien?", "answer": "Rom."},
                {"question": "Welcher Kontinent ist der größte?", "answer": "Asien."},
                {"question": "Wie heißt das Gebirge in Süddeutschland und Österreich?", "answer": "Alpen."},
                {"question": "Welcher Ozean liegt zwischen Europa/Afrika und Amerika?", "answer": "Atlantik."},
            ],
            40: [
                {"question": "Welcher Fluss fließt durch Wien und Budapest?", "answer": "Donau."},
                {"question": "Wie heißt die Hauptstadt von Kanada?", "answer": "Ottawa."},
                {"question": "Welche Insel gehört zu Dänemark und ist sehr groß?", "answer": "Gronland."},
                {"question": "Wie heißt die größte Insel im Mittelmeer?", "answer": "Sizilien."},
            ],
            60: [
                {"question": "Wie heißt der höchste Berg Afrikas?", "answer": "Kilimandscharo."},
                {"question": "Welche Wüste liegt in Nordafrika?", "answer": "Sahara."},
                {"question": "Welches Land hat die Hauptstadt Oslo?", "answer": "Norwegen."},
                {"question": "Wie heißt der längste Fluss Europas?", "answer": "Wolga."},
            ],
            80: [
                {"question": "Wie heißt die Hauptstadt von Neuseeland?", "answer": "Wellington."},
                {"question": "Welche Klimazone hat ganzjährig hohe Niederschläge nahe dem Äquator?", "answer": "Tropen/Regenwaldklima."},
                {"question": "Wie heißt die Meeresströmung, die Westeuropa erwärmt?", "answer": "Golfstrom."},
                {"question": "Welcher Staat liegt sowohl in Europa als auch in Asien und hat Istanbul?", "answer": "Türkei."},
            ],
            100: [
                {"question": "Wie heißt die Hauptstadt von Kasachstan (heutiger Name)?", "answer": "Astana."},
                {"question": "Was bezeichnet die geographische Breite 0 Grad?", "answer": "Äquator."},
                {"question": "Welcher Kontinent ist flächenmäßig der zweitkleinste?", "answer": "Europa."},
                {"question": "Wie heißt die trockenste Wüste außerhalb der Polarregionen?", "answer": "Atacama."},
            ],
        },
        "Musik": {
            20: [
                {"question": "Wie viele Tasten hat ein Klavier meist?", "answer": "88."},
                {"question": "Wie heißt eine sehr laute Dynamikbezeichnung?", "answer": "Forte."},
                {"question": "Wie heißt ein Musikstück für zwei Personen?", "answer": "Duett."},
                {"question": "Welches Instrument hat Saiten und wird gestrichen: Violine oder Trompete?", "answer": "Violine."},
            ],
            40: [
                {"question": "Wie nennt man den Abstand gleicher Töne, z. B. c zu c?", "answer": "Oktave."},
                {"question": "Wie heißt die Pause über einen ganzen Takt?", "answer": "Ganze Pause."},
                {"question": "Wie nennt man mehrere gleichzeitig klingende Töne?", "answer": "Akkord."},
                {"question": "Welches Vorzeichen erniedrigt einen Ton?", "answer": "B."},
            ],
            60: [
                {"question": "Wie heißt die Form, in der ein Thema von mehreren Stimmen nacheinander aufgegriffen wird?", "answer": "Fuge."},
                {"question": "Wie heißt ein langsam schneller werdendes Tempo?", "answer": "Accelerando."},
                {"question": "Wie heißt die Tonart ohne Vorzeichen in Dur?", "answer": "C-Dur."},
                {"question": "Wie nennt man den Schluss eines Musikstücks?", "answer": "Coda."},
            ],
            80: [
                {"question": "Wie heißt eine Opernstimme zwischen Sopran und Alt?", "answer": "Mezzosopran."},
                {"question": "Was bedeutet 'legato'?", "answer": "Gebunden spielen."},
                {"question": "Wie nennt man in der Klassik eine Sonate für Soloinstrument und Begleitung?", "answer": "Sonate."},
                {"question": "Wie heißt die Taktart mit drei Schlägen pro Takt häufig?", "answer": "Dreivierteltakt."},
            ],
            100: [
                {"question": "Wie heißt die barocke Verzierung mit schnellem Wechsel zum Nebenton?", "answer": "Triller."},
                {"question": "Wie nennt man den Grundton einer Tonart?", "answer": "Tonika."},
                {"question": "Welcher Akkord steht auf der 5. Stufe in Dur oft als Spannungsakkord?", "answer": "Dominante."},
                {"question": "Wie heißt die Form mit Exposition, Durchführung und Reprise?", "answer": "Sonatenhauptsatzform."},
            ],
        },
        "Mathe": {
            20: [
                {"question": "Was ist 14 + 19?", "answer": "33."},
                {"question": "Was ist 81 : 9?", "answer": "9."},
                {"question": "Was ist 13 x 6?", "answer": "78."},
                {"question": "Was ist 100 - 47?", "answer": "53."},
            ],
            40: [
                {"question": "Wie groß ist die Innenwinkelsumme im Dreieck?", "answer": "180 Grad."},
                {"question": "Was ist 30 Prozent von 90?", "answer": "27."},
                {"question": "Wie lautet 11 hoch 2?", "answer": "121."},
                {"question": "Löse: 5x = 45.", "answer": "x = 9."},
            ],
            60: [
                {"question": "Was ist die Quadratwurzel von 225?", "answer": "15."},
                {"question": "Wie viele Kanten hat ein Würfel?", "answer": "12."},
                {"question": "Wie lautet die Formel für den Kreisumfang?", "answer": "2 mal pi mal r."},
                {"question": "Löse: 2x - 7 = 19.", "answer": "x = 13."},
            ],
            80: [
                {"question": "Wie lautet 3/5 als Dezimalzahl?", "answer": "0,6."},
                {"question": "Wie groß ist die Fläche eines Rechtecks mit 12 und 7?", "answer": "84."},
                {"question": "Was ist 1,2 x 0,5?", "answer": "0,6."},
                {"question": "Löse: x^2 = 169.", "answer": "x = 13 oder x = -13."},
            ],
            100: [
                {"question": "Wie lautet die pq-Formel-Idee in einem Satz?", "answer": "Loest quadratische Gleichungen der Form x^2+px+q=0."},
                {"question": "Was ist der Sinus von 30 Grad?", "answer": "0,5."},
                {"question": "Ein Kapital wächst von 1000 auf 1210 in zwei Jahren. Wie hoch war der jährliche Faktor?", "answer": "1,1."},
                {"question": "Wie lautet die Ableitung von x^2?", "answer": "2x."},
            ],
        },
        "Informatik": {
            20: [
                {"question": "Wofür steht CPU?", "answer": "Central Processing Unit."},
                {"question": "Wie heißt das Zahlensystem mit 0 und 1?", "answer": "Binaersystem."},
                {"question": "Wie heißt ein Programm zum Anzeigen von Webseiten?", "answer": "Browser."},
                {"question": "Wie nennt man eine Sicherungskopie von Daten?", "answer": "Backup."},
            ],
            40: [
                {"question": "Wofür steht URL?", "answer": "Uniform Resource Locator."},
                {"question": "Wie nennt man schädliche Software?", "answer": "Malware."},
                {"question": "Welche Taste löscht links vom Cursor?", "answer": "Backspace."},
                {"question": "Wie heißt ein weltweites Netz aus Rechnern?", "answer": "Internet."},
            ],
            60: [
                {"question": "Was bedeutet HTTPS grob?", "answer": "Verschluesselte Webverbindung."},
                {"question": "Wie nennt man den Hauptspeicher eines Computers?", "answer": "RAM."},
                {"question": "Was ist ein Algorithmus?", "answer": "Schrittweise Loesungsvorschrift."},
                {"question": "Wie nennt man ein Programmierfehler im Code?", "answer": "Bug."},
            ],
            80: [
                {"question": "Wie heißt das Modell aus Client und Server im Web?", "answer": "Client-Server-Modell."},
                {"question": "Was macht ein DNS-Server?", "answer": "Uebersetzt Domainnamen in IP-Adressen."},
                {"question": "Wie nennt man Versionsverwaltung mit Branches und Commits?", "answer": "Git."},
                {"question": "Was ist ein API-Endpunkt?", "answer": "Adresse einer Programmschnittstelle."},
            ],
            100: [
                {"question": "Was beschreibt Big-O-Notation?", "answer": "Asymptotische Laufzeit-/Speicherkomplexitaet."},
                {"question": "Was ist der Unterschied zwischen Frontend und Backend kurz?", "answer": "Frontend ist Benutzeroberflaeche, Backend verarbeitet Logik und Daten."},
                {"question": "Was bedeutet SQL-Injection?", "answer": "Angriff durch manipulierte Datenbankabfragen."},
                {"question": "Was ist ein Hash in der Informatik?", "answer": "Fester Ausgabewert aus Daten per Hashfunktion."},
            ],
        },
        "Deutsch": {
            20: [
                {"question": "Welche Wortart ist 'laufen'?", "answer": "Verb."},
                {"question": "Was ist die Mehrzahl von 'Maus'?", "answer": "Maeuse."},
                {"question": "Welches Zeichen beendet einen Ausruf?", "answer": "Ausrufezeichen."},
                {"question": "Was ist ein Synonym von 'schnell'?", "answer": "Rasch."},
            ],
            40: [
                {"question": "Welcher Fall ist 'wem'?", "answer": "Dativ."},
                {"question": "Wie heißt die Nennform eines Verbs?", "answer": "Infinitiv."},
                {"question": "Welche Zeitform ist 'ich ging'?", "answer": "Praeteritum."},
                {"question": "Wie nennt man Wörter mit entgegengesetzter Bedeutung?", "answer": "Antonyme."},
            ],
            60: [
                {"question": "Was ist das Prädikat im Satz 'Der Hund bellt laut'?", "answer": "Bellt."},
                {"question": "Wie nennt man Nebensätze mit 'weil'?", "answer": "Kausalsaetze."},
                {"question": "Welche Wortart ist 'deshalb'?", "answer": "Adverb/Konjunktionaladverb."},
                {"question": "Wie heißt der 2. Fall?", "answer": "Genitiv."},
            ],
            80: [
                {"question": "Wie nennt man eine direkte Rede in einen Nebensatz umgewandelt?", "answer": "Indirekte Rede."},
                {"question": "Welche Verbform nutzt man oft für Wünsche: 'Wenn ich doch ...'?", "answer": "Konjunktiv."},
                {"question": "Was ist ein Relativsatz?", "answer": "Nebensatz, der ein Nomen naeher beschreibt."},
                {"question": "Wie nennt man die Lehre vom Satzbau?", "answer": "Syntax."},
            ],
            100: [
                {"question": "Wie heißt das Stilmittel bei 'Zeit ist Geld'?", "answer": "Metapher."},
                {"question": "Wie nennt man die Wiederholung des Anfangslauts wie in 'Milch macht muede Maenner munter'?", "answer": "Alliteration."},
                {"question": "Welche Kasus-Regel gilt nach der Präposition 'wegen' im Standarddeutsch?", "answer": "Genitiv."},
                {"question": "Wie nennt man die Wortstellung Verb am Ende im Nebensatz?", "answer": "Verbendstellung."},
            ],
        },
        "Allgemeinwissen": {
            20: [
                {"question": "Wie viele Sekunden hat eine Minute?", "answer": "60."},
                {"question": "Welcher Planet ist der Erde am nächsten (im Mittel meist genannt)?", "answer": "Venus."},
                {"question": "Wie viele Zentimeter hat ein Meter?", "answer": "100."},
                {"question": "Wie heißt die Einheit für Gewicht im Alltag?", "answer": "Kilogramm."},
            ],
            40: [
                {"question": "Welche Farbe hat Kupfersulfat-Lösung oft in der Schule?", "answer": "Blau."},
                {"question": "Wie viele Bundesländer hat Deutschland?", "answer": "16."},
                {"question": "Wie heißt die Hauptstadt von Österreich?", "answer": "Wien."},
                {"question": "Wie viele Stunden hat ein Tag?", "answer": "24."},
            ],
            60: [
                {"question": "Wie nennt man den Übergang von fest zu flüssig?", "answer": "Schmelzen."},
                {"question": "Welche Einheit misst elektrische Spannung?", "answer": "Volt."},
                {"question": "Welches Gas ist in der Luft am häufigsten?", "answer": "Stickstoff."},
                {"question": "Wie viele Zähne hat ein Erwachsener meistens?", "answer": "32."},
            ],
            80: [
                {"question": "Wie heißt die Hauptstadt von Finnland?", "answer": "Helsinki."},
                {"question": "Wie viele Chromosomen hat ein Mensch in Körperzellen?", "answer": "46."},
                {"question": "Welches Organ verbraucht viel Sauerstoff und steuert Denken?", "answer": "Gehirn."},
                {"question": "Was bedeutet die Abkürzung UNESCO?", "answer": "UN-Organisation fuer Bildung, Wissenschaft und Kultur."},
            ],
            100: [
                {"question": "Wie heißt das SI-Basissymbol für elektrische Stromstärke?", "answer": "A (Ampere)."},
                {"question": "Welcher Naturwissenschaftler formulierte die Gravitationstheorie klassisch?", "answer": "Isaac Newton."},
                {"question": "Wie heißt die Hauptstadt von Südkorea?", "answer": "Seoul."},
                {"question": "Was ist der pH-Wert von neutralem Wasser bei 25 Grad?", "answer": "7."},
            ],
        },
    },
    "old": {
        "Englisch": {
            20: [
                {"question": "Wie heißt 'Nachhaltigkeit' auf Englisch?", "answer": "Sustainability."},
                {"question": "Wie heißt 'Entscheidung' auf Englisch?", "answer": "Decision."},
                {"question": "Wie heißt 'Herausforderung' auf Englisch?", "answer": "Challenge."},
                {"question": "Wie heißt 'Verantwortung' auf Englisch?", "answer": "Responsibility."},
            ],
            40: [
                {"question": "Setze ein: 'By the time we arrived, the film ___ already started.'", "answer": "Had."},
                {"question": "Welche Form ist korrekt: 'less people' oder 'fewer people'?", "answer": "Fewer people."},
                {"question": "Setze ein: 'I look forward to ___ from you.'", "answer": "Hearing."},
                {"question": "Welche Form ist korrekt: 'neither ... nor' oder 'either ... or' für Verneinung?", "answer": "Neither ... nor."},
            ],
            60: [
                {"question": "Wandle um in passive voice: 'They have announced the results.'", "answer": "The results have been announced."},
                {"question": "Setze ein: 'If she ___ earlier, she would have caught the train.'", "answer": "Had left."},
                {"question": "Welche Zeit drückt eine Handlung aus, die vor einer anderen in der Vergangenheit abgeschlossen war?", "answer": "Past Perfect."},
                {"question": "Setze richtig ein: 'No sooner ___ we sat down than the bell rang.'", "answer": "Had."},
            ],
            80: [
                {"question": "Was ist ein defining relative clause?", "answer": "Ein notwendiger Relativsatz ohne Kommas."},
                {"question": "Welche Struktur ist korrekt für unreal conditionals Typ 3?", "answer": "If + past perfect, would have + past participle."},
                {"question": "Formuliere indirekt: 'Do you know where he is?' she asked.", "answer": "She asked if I knew where he was."},
                {"question": "Welche Funktion hat 'inversion' in formeller Sprache?", "answer": "Betonung und formeller Stil, oft ohne if."},
            ],
            100: [
                {"question": "Ergänze: 'Scarcely ___ the meeting begun when the alarm went off.'", "answer": "Had."},
                {"question": "Wie nennt man die Verwendung eines Gerundiums als Subjekt?", "answer": "Gerund as subject."},
                {"question": "Was ist der Unterschied zwischen 'which' und 'that' in defining clauses (US/UK-Nutzung)?", "answer": "That ist typisch fuer defining; which oft non-defining mit Komma."},
                {"question": "Welche Form folgt auf 'would rather' für Gegenwart (anderes Subjekt)?", "answer": "Past simple."},
            ],
        },
        "Sport": {
            20: [
                {"question": "Wie viele Spieler hat ein Rugby-Union-Team auf dem Feld?", "answer": "15."},
                {"question": "Wie lang ist ein Standard-Tennis-Matchsatz im Tie-Break-Modus mindestens?", "answer": "Bis 6 Spiele mit 2 Vorsprung oder Tie-Break."},
                {"question": "Wie viele Minuten dauert ein Eishockeyspiel regulär?", "answer": "60 Minuten."},
                {"question": "Wie viele Bahnen hat ein olympisches Schwimmbecken häufig in Wettkämpfen?", "answer": "8 oder 10."},
            ],
            40: [
                {"question": "Wie heißt die höchste Fußballliga in Deutschland?", "answer": "Bundesliga."},
                {"question": "Welche Distanz hat ein Halbmarathon?", "answer": "21,0975 km."},
                {"question": "Wie viele Punkte gibt ein Conversion Kick im Rugby Union?", "answer": "2."},
                {"question": "Wie nennt man den Start aus dem Block im Sprint regeltechnisch?", "answer": "Tiefstart."},
            ],
            60: [
                {"question": "Wie viele Schiedsrichter sind im Basketball nach FIBA meist auf dem Feld?", "answer": "3."},
                {"question": "Welche Nation gewann die Fußball-WM 2022?", "answer": "Argentinien."},
                {"question": "Wie lang ist eine Laufbahn-Runde?", "answer": "400 Meter."},
                {"question": "Was bedeutet 'offside trap' im Fußball?", "answer": "Bewusstes Stellen einer Abseitsfalle."},
            ],
            80: [
                {"question": "Wie wird im Radsport die Gesamtwertung der Tour de France gekennzeichnet?", "answer": "Gelbes Trikot."},
                {"question": "Wie viele Durchgänge hat ein alpiner Riesenslalom?", "answer": "2."},
                {"question": "Wie nennt man den Wurfkreis beim Diskuswurf nach IAAF-Maß ungefähr?", "answer": "2,50 m Durchmesser."},
                {"question": "Was ist ein 'false start' im Sprint?", "answer": "Fehlstart."},
            ],
            100: [
                {"question": "Wie nennt man die maximale Sauerstoffaufnahme in der Leistungsdiagnostik?", "answer": "VO2max."},
                {"question": "Welche Spielsituation wird im Fußball per VAR auf klare Fehler geprüft?", "answer": "Tor, Elfmeter, direkte rote Karte, Spielerverwechslung."},
                {"question": "Was ist der Unterschied zwischen anaerob-alaktazid und anaerob-laktazid kurz?", "answer": "Ohne Laktatbildung vs. mit Laktatbildung."},
                {"question": "Welche Energiequelle dominiert bei sehr kurzen Maximalsprints unter 10 Sekunden?", "answer": "ATP-Kreatinphosphat-System."},
            ],
        },
        "Biologie": {
            20: [
                {"question": "Wie heißt der Prozess vom Ablesen der DNA in RNA?", "answer": "Transkription."},
                {"question": "Welche Blutgruppe gilt als Universalempfänger im AB0-System?", "answer": "AB."},
                {"question": "Wie heißen die Zellorganellen für Zellatmung?", "answer": "Mitochondrien."},
                {"question": "Wie nennt man den Grundbaustein von Proteinen?", "answer": "Aminosäure."},
            ],
            40: [
                {"question": "Was macht ein Enzym grundsätzlich?", "answer": "Es katalysiert/beschleunigt Reaktionen."},
                {"question": "Wie nennt man den Austausch von Allelen zwischen homologen Chromosomen in der Meiose?", "answer": "Crossing-over."},
                {"question": "Welche Phase der Mitose trennt Chromatiden?", "answer": "Anaphase."},
                {"question": "Wie heißt der gerichtete Transport von Wasser durch Membran?", "answer": "Osmose."},
            ],
            60: [
                {"question": "Was ist die Funktion von mRNA?", "answer": "Transportiert genetische Information zur Proteinsynthese."},
                {"question": "Wie nennt man den Anteil variabler Positionen in Populationen?", "answer": "Genetische Diversität."},
                {"question": "Wie heißt der Prozess der Umwandlung von Lichtenergie in chemische Energie?", "answer": "Fotosynthese."},
                {"question": "Welche Struktur enthält in Pflanzenzellen chlorophyllhaltige Thylakoide?", "answer": "Chloroplast."},
            ],
            80: [
                {"question": "Was beschreibt die allosterische Hemmung?", "answer": "Enzymhemmung durch Bindung an anderer Stelle als dem aktiven Zentrum."},
                {"question": "Wie heißt die Selektion gegen extreme Merkmalsausprägungen in der Mitte?", "answer": "Aufspaltende Selektion ist gegen Mitte; stabilisierende gegen Extreme."},
                {"question": "Was ist Epigenetik kurz?", "answer": "Vererbbare Genregulation ohne Änderung der DNA-Sequenz."},
                {"question": "Welche Immunzellen bilden Antikörper nach Aktivierung aus?", "answer": "B-Lymphozyten/Plasmazellen."},
            ],
            100: [
                {"question": "Was beschreibt die Michaelis-Menten-Kinetik?", "answer": "Zusammenhang zwischen Substratkonzentration und Reaktionsgeschwindigkeit von Enzymen."},
                {"question": "Was ist horizontale Genübertragung?", "answer": "Genübertragung zwischen Organismen außerhalb der Fortpflanzung."},
                {"question": "Welche Technik nutzt CRISPR-Cas9?", "answer": "Gezielte Genomeditierung."},
                {"question": "Was versteht man unter genetischer Drift?", "answer": "Zufällige Änderung von Allelhäufigkeiten."},
            ],
        },
        "Geschichte": {
            20: [
                {"question": "Wann begann der Erste Weltkrieg?", "answer": "1914."},
                {"question": "Wann endete der Zweite Weltkrieg in Europa?", "answer": "1945."},
                {"question": "Wie heißt die politische Ordnung Europas nach 1945 mit West/Ost-Block?", "answer": "Kalter Krieg."},
                {"question": "Wann fiel die Berliner Mauer?", "answer": "1989."},
            ],
            40: [
                {"question": "Wie nennt man die politische Neuordnung Europas 1815?", "answer": "Wiener Kongress."},
                {"question": "Wann wurde die BRD gegründet?", "answer": "1949."},
                {"question": "Wie heißt die Reichsgründung Deutschlands im 19. Jahrhundert (Jahr)?", "answer": "1871."},
                {"question": "Wie heißt die Revolution von 1789 in Frankreich?", "answer": "Französische Revolution."},
            ],
            60: [
                {"question": "Was war die Weimarer Republik?", "answer": "Deutsche Demokratie von 1919 bis 1933."},
                {"question": "Welche Krise traf die Weltwirtschaft 1929 schwer?", "answer": "Weltwirtschaftskrise."},
                {"question": "Wie heißt der Wiederaufbauplan der USA nach 1945?", "answer": "Marshallplan."},
                {"question": "Wann trat Deutschland der EU in ihrer Vorform EWG bei?", "answer": "1957 als Gruendungsmitglied."},
            ],
            80: [
                {"question": "Was war der Auslöser des Ersten Weltkriegs?", "answer": "Attentat von Sarajevo."},
                {"question": "Wie nennt man die Entspannungspolitik zwischen Ost und West in den 1970ern?", "answer": "Détente/Entspannungspolitik."},
                {"question": "Wann wurde der Euro als Bargeld eingeführt?", "answer": "2002."},
                {"question": "Welche Konferenz regelte 1945 Nachkriegsfragen in Deutschland?", "answer": "Potsdamer Konferenz."},
            ],
            100: [
                {"question": "Was regelte der Westfälische Frieden 1648 grundlegend?", "answer": "Ende des Dreißigjährigen Krieges und neue europäische Ordnung."},
                {"question": "Wie hieß die Politik Bismarcks zur Isolation Frankreichs?", "answer": "Buendnissystem Bismarcks."},
                {"question": "Welche Bedeutung hatte die KSZE-Schlussakte von Helsinki 1975?", "answer": "Sicherheits- und Menschenrechtsrahmen in Europa."},
                {"question": "Was war der Prager Frühling 1968?", "answer": "Reformbewegung in der Tschechoslowakei, durch Warschauer-Pakt-Truppen niedergeschlagen."},
            ],
        },
        "Geografie": {
            20: [
                {"question": "Wie heißt die Hauptstadt von Japan?", "answer": "Tokio."},
                {"question": "Wie heißt der längste Fluss Südamerikas?", "answer": "Amazonas."},
                {"question": "Wie heißt die größte Insel der Erde?", "answer": "Gronland."},
                {"question": "Welcher Ozean liegt östlich von Afrika?", "answer": "Indischer Ozean."},
            ],
            40: [
                {"question": "Wie heißt die Hauptstadt von Brasilien?", "answer": "Brasilia."},
                {"question": "Welche Meerenge verbindet Mittelmeer und Atlantik?", "answer": "Strasse von Gibraltar."},
                {"question": "Welches Land hat die meisten Zeitzonen (inklusive Überseegebiete)?", "answer": "Frankreich."},
                {"question": "Wie heißt der größte See Afrikas?", "answer": "Victoriasee."},
            ],
            60: [
                {"question": "Welche Klimaklassifikation ist weltweit häufig genutzt?", "answer": "Koeppen-Geiger."},
                {"question": "Wie heißt die Hauptstadt von Südafrika mit Regierungssitz (administrativ)?", "answer": "Pretoria."},
                {"question": "Was ist ein Fjord?", "answer": "Tief eingeschnittene Meeresbucht glaezialen Ursprungs."},
                {"question": "Wie heißt das Gebirge, das Europa und Asien traditionell trennt?", "answer": "Ural."},
            ],
            80: [
                {"question": "Welche Zone beschreibt die ITCZ in der Klimatologie?", "answer": "Innertropische Konvergenzzone."},
                {"question": "Wie heißt das Meer südlich von Europa und nördlich von Afrika?", "answer": "Mittelmeer."},
                {"question": "Welche tektonische Ursache hat den Himalaya geformt?", "answer": "Kollision der Indischen mit der Eurasischen Platte."},
                {"question": "Wie nennt man dauerhaft gefrorenen Boden in kalten Regionen?", "answer": "Permafrost."},
            ],
            100: [
                {"question": "Wie heißt die Hauptstadt von Bolivien (verfassungsrechtlich)?", "answer": "Sucre."},
                {"question": "Was ist der Unterschied zwischen Verwitterung und Erosion?", "answer": "Verwitterung zersetzt Gestein, Erosion transportiert es ab."},
                {"question": "Welche geographische Breite markiert den nördlichen Wendekreis?", "answer": "23,5 Grad Nord."},
                {"question": "Wie heißt die größte heiße Wüste Nordamerikas?", "answer": "Sonora-Wueste (oft genannt)."},
            ],
        },
        "Musik": {
            20: [
                {"question": "Wie heißt die Tonart mit zwei Kreuzen (Dur)?", "answer": "D-Dur."},
                {"question": "Welche Form hat ein Blues-Schema klassisch häufig?", "answer": "12-Takt-Blues."},
                {"question": "Was bedeutet adagio?", "answer": "Langsam."},
                {"question": "Wie nennt man den gleichbleibenden Bass in Barockmusik?", "answer": "Basso continuo."},
            ],
            40: [
                {"question": "Wie heißt ein Akkord mit Grundton, Terz und Quinte?", "answer": "Dreiklang."},
                {"question": "Was ist eine Kadenz in der Harmonielehre?", "answer": "Typische Akkordfolge mit Schlusswirkung."},
                {"question": "Wie nennt man die Lehre von Tonarten und Akkorden?", "answer": "Harmonielehre."},
                {"question": "Welches Intervall hat 7 Halbtonschritte?", "answer": "Quinte."},
            ],
            60: [
                {"question": "Wie heißt die Form A-B-A im Lied oft?", "answer": "Da-Capo-Form."},
                {"question": "Was ist Polyphonie?", "answer": "Mehrstimmigkeit mit eigenständigen Stimmen."},
                {"question": "Wie nennt man den Leitton in C-Dur?", "answer": "H."},
                {"question": "Wie heißt die Kirchentonart mit erhöhter 4. Stufe über Dur-Grundcharakter?", "answer": "Lydisch."},
            ],
            80: [
                {"question": "Was ist ein Trugschluss in der Kadenzlehre?", "answer": "Unerwartete Auflösung, oft V nach VI statt I."},
                {"question": "Wie nennt man die übermäßige Quarte/verringerte Quinte historisch?", "answer": "Tritonus."},
                {"question": "Welche Form dominiert häufig den ersten Satz klassischer Sinfonien?", "answer": "Sonatenhauptsatzform."},
                {"question": "Was bedeutet rubato?", "answer": "Freie Tempogestaltung."},
            ],
            100: [
                {"question": "Wie heißt die Technik, bei der ein Motiv in verschiedenen Stimmen versetzt einsetzt?", "answer": "Imitation/Kanonprinzip."},
                {"question": "Was ist eine enharmonische Verwechslung?", "answer": "Gleicher Klang mit anderer Notation."},
                {"question": "Wie nennt man die verminderte Septime über dem Leittonakkord?", "answer": "Leittonseptakkord."},
                {"question": "Welche Epoche folgt auf die Romantik in der Kunstmusik grob um 1900?", "answer": "Moderne."},
            ],
        },
        "Mathe": {
            20: [
                {"question": "Was ist 18 x 7?", "answer": "126."},
                {"question": "Was ist 256 : 16?", "answer": "16."},
                {"question": "Was ist 15 Prozent von 240?", "answer": "36."},
                {"question": "Löse: 4x + 12 = 44.", "answer": "x = 8."},
            ],
            40: [
                {"question": "Wie lautet die binomische Formel (a+b)^2?", "answer": "a^2 + 2ab + b^2."},
                {"question": "Wie groß ist die Wahrscheinlichkeit bei fairem Münzwurf für Kopf?", "answer": "1/2."},
                {"question": "Löse: 3x - 2 = 4x + 5.", "answer": "x = -7."},
                {"question": "Wie lautet die Formel für die Steigung zwischen zwei Punkten?", "answer": "(y2-y1)/(x2-x1)."},
            ],
            60: [
                {"question": "Was ist die Ableitung von x^3?", "answer": "3x^2."},
                {"question": "Wie lautet die Umkehrfunktion von f(x)=2x+6?", "answer": "f^-1(x)=(x-6)/2."},
                {"question": "Wie groß ist sin(90 Grad)?", "answer": "1."},
                {"question": "Was ist ln(1)?", "answer": "0."},
            ],
            80: [
                {"question": "Welche Gleichung beschreibt einen Kreis mit Mittelpunkt (0,0) und Radius r?", "answer": "x^2 + y^2 = r^2."},
                {"question": "Was ist die Determinante von [[a,b],[c,d]]?", "answer": "ad - bc."},
                {"question": "Wie lautet die Summenformel 1+2+...+n?", "answer": "n(n+1)/2."},
                {"question": "Wie heißt der Satz a^2+b^2=c^2?", "answer": "Satz des Pythagoras."},
            ],
            100: [
                {"question": "Wann ist eine quadratische Funktion konkav nach oben?", "answer": "Wenn der x^2-Koeffizient positiv ist."},
                {"question": "Was ist die Stammfunktion von 2x?", "answer": "x^2 + C."},
                {"question": "Wie lautet e^(ln(x)) für x>0?", "answer": "x."},
                {"question": "Was beschreibt das Integral einer Geschwindigkeit über die Zeit?", "answer": "Zurueckgelegter Weg (Ortsaenderung)."},
            ],
        },
        "Physik": {
            20: [
                {"question": "Welche Einheit hat die Kraft?", "answer": "Newton."},
                {"question": "Wie schnell ist Licht im Vakuum ungefähr?", "answer": "300.000 km/s."},
                {"question": "Wie heißt die Kraft, die Körper zur Erde zieht?", "answer": "Gravitation."},
                {"question": "Welche Einheit hat elektrische Spannung?", "answer": "Volt."},
            ],
            40: [
                {"question": "Wie lautet die Formel für Geschwindigkeit?", "answer": "Strecke durch Zeit (v=s/t)."},
                {"question": "Wie heißt der Übergang von flüssig zu gasförmig?", "answer": "Verdampfen."},
                {"question": "Welche Einheit misst Frequenz?", "answer": "Hertz."},
                {"question": "Welche Teilchen tragen negative Ladung?", "answer": "Elektronen."},
            ],
            60: [
                {"question": "Wie lautet das Ohmsche Gesetz?", "answer": "U = R mal I."},
                {"question": "Wie heißt die Energieform gespeicherter Lage?", "answer": "Potenzielle Energie."},
                {"question": "Welche Einheit hat Leistung?", "answer": "Watt."},
                {"question": "Wie nennt man die Trägheit eines Körpers gegen Beschleunigung?", "answer": "Masse/Traegheit."},
            ],
            80: [
                {"question": "Wie lautet die Formel für kinetische Energie?", "answer": "1/2 m v^2."},
                {"question": "Wie nennt man den Widerstand gegen Stromfluss in Leitern?", "answer": "Elektrischer Widerstand."},
                {"question": "Welche Art Strahlung hat die kürzeste Wellenlänge im sichtbaren Umfeld darüber hinaus?", "answer": "Gammastrahlung/hochenergetische Strahlung."},
                {"question": "Wie heißt die Bewegung mit konstanter Winkelgeschwindigkeit auf Kreisbahn?", "answer": "Gleichfoermige Kreisbewegung."},
            ],
            100: [
                {"question": "Was beschreibt die zweite Newtonsche Axiomformel?", "answer": "F = m mal a."},
                {"question": "Wie nennt man die Energieerhaltung in abgeschlossenem System?", "answer": "Energieerhaltungssatz."},
                {"question": "Was ist die Planck-Konstante einzuordnen?", "answer": "Naturkonstante der Quantenphysik."},
                {"question": "Wie lautet die Grundidee von Einsteins Relativität in einem Satz?", "answer": "Raum und Zeit sind relativ und verknuepft zu Raumzeit."},
            ],
        },
        "Chemie": {
            20: [
                {"question": "Wie lautet die Formel von Wasser?", "answer": "H2O."},
                {"question": "Welches Element hat das Symbol O?", "answer": "Sauerstoff."},
                {"question": "Wie heißt Kochsalz chemisch?", "answer": "Natriumchlorid."},
                {"question": "Wie nennt man Stoffe mit pH kleiner 7?", "answer": "Saeuren."},
            ],
            40: [
                {"question": "Wie heißt das negativ geladene Teilchen im Atom?", "answer": "Elektron."},
                {"question": "Welches Element hat das Symbol Fe?", "answer": "Eisen."},
                {"question": "Wie nennt man die kleinste Einheit einer chemischen Verbindung?", "answer": "Molekuel."},
                {"question": "Was entsteht bei Neutralisation von Saeure und Base oft?", "answer": "Salz und Wasser."},
            ],
            60: [
                {"question": "Wie viele Protonen hat Kohlenstoff?", "answer": "6."},
                {"question": "Welche Bindung entsteht durch Elektronenpaar-Teilung?", "answer": "Kovalente Bindung."},
                {"question": "Was beschreibt das Periodensystem?", "answer": "Anordnung der Elemente nach Ordnungszahl und Eigenschaften."},
                {"question": "Wie heißt die Stoffmenge-Einheit?", "answer": "Mol."},
            ],
            80: [
                {"question": "Wie lautet die Oxidationszahl von Sauerstoff in den meisten Verbindungen?", "answer": "-2."},
                {"question": "Was ist ein Katalysator?", "answer": "Stoff, der Reaktion beschleunigt und nicht verbraucht wird."},
                {"question": "Wie nennt man Reaktionen mit Elektronenübertragung?", "answer": "Redoxreaktionen."},
                {"question": "Wie lautet die allgemeine Formel von Alkanen?", "answer": "CnH2n+2."},
            ],
            100: [
                {"question": "Was beschreibt das Massenwirkungsgesetz?", "answer": "Beziehung zwischen Konzentrationen im chemischen Gleichgewicht."},
                {"question": "Wie heißt der pH-Bereich einer starken Base ungefähr?", "answer": "Nahe 14."},
                {"question": "Was ist der Unterschied zwischen endotherm und exotherm?", "answer": "Endotherm nimmt Energie auf, exotherm gibt Energie ab."},
                {"question": "Welche Bindungsart hat Natriumchlorid überwiegend?", "answer": "Ionenbindung."},
            ],
        },
        "Informatik": {
            20: [
                {"question": "Was bedeutet RAM?", "answer": "Random Access Memory."},
                {"question": "Welche Einheit misst Datenmengen?", "answer": "Byte."},
                {"question": "Wie nennt man den zentralen Rechner in einem Netzwerkdienst?", "answer": "Server."},
                {"question": "Wie heißt die Sprache, die Webseiten strukturiert?", "answer": "HTML."},
            ],
            40: [
                {"question": "Wofür steht SQL?", "answer": "Structured Query Language."},
                {"question": "Wie nennt man ein Datenmodell mit Tabellen?", "answer": "Relationale Datenbank."},
                {"question": "Was ist ein Betriebssystem?", "answer": "Grundsoftware zur Verwaltung von Hardware und Programmen."},
                {"question": "Wie nennt man den Prozess, Quellcode in Maschinencode zu übersetzen?", "answer": "Kompilieren."},
            ],
            60: [
                {"question": "Was ist der Unterschied zwischen HTTP und HTTPS?", "answer": "HTTPS ist verschluesselt per TLS."},
                {"question": "Was bedeutet OOP?", "answer": "Objektorientierte Programmierung."},
                {"question": "Wie nennt man eine Datenstruktur nach dem LIFO-Prinzip?", "answer": "Stack."},
                {"question": "Was beschreibt ein REST-API grob?", "answer": "Ressourcenorientierte Web-Schnittstelle mit HTTP-Methoden."},
            ],
            80: [
                {"question": "Was ist ein Deadlock?", "answer": "Blockierung durch gegenseitiges Warten von Prozessen/Threads."},
                {"question": "Wie nennt man unveränderliche Datenobjekte?", "answer": "Immutable Objekte."},
                {"question": "Was ist der Zweck eines Index in Datenbanken?", "answer": "Schnellere Abfragen."},
                {"question": "Wie nennt man den Schutz gegen Cross-Site Request Forgery?", "answer": "CSRF-Schutz/Token."},
            ],
            100: [
                {"question": "Was beschreibt CAP-Theorem in verteilten Systemen?", "answer": "Nicht gleichzeitig volle Konsistenz, Verfuegbarkeit und Partitionstoleranz."},
                {"question": "Was ist der Unterschied zwischen symmetrischer und asymmetrischer Verschlüsselung?", "answer": "Ein gemeinsamer Schluessel vs. Schluesselpaar."},
                {"question": "Was bedeutet ACID bei Datenbanken?", "answer": "Atomicity, Consistency, Isolation, Durability."},
                {"question": "Was ist ein Race Condition?", "answer": "Fehler durch zeitkritischen gleichzeitigen Zugriff."},
            ],
        },
        "Politik & Gesellschaft": {
            20: [
                {"question": "Wie oft wird der Bundestag regulär gewählt?", "answer": "Alle 4 Jahre."},
                {"question": "Wie heißt das Parlament in Deutschland?", "answer": "Bundestag."},
                {"question": "Wie nennt man die Gewaltenteilung in drei Bereiche? Nenne einen.", "answer": "Legislative, Exekutive oder Judikative."},
                {"question": "Wie heißt die Hauptstadt der EU-Institutionen oft politisch genannt?", "answer": "Bruessel."},
            ],
            40: [
                {"question": "Was bedeutet Demokratie in einem Satz?", "answer": "Herrschaft geht vom Volk aus."},
                {"question": "Wie heißt das Staatsoberhaupt in Deutschland?", "answer": "Bundespraesident."},
                {"question": "Wie viele Mitgliedsstaaten hatte die EU Stand 2026?", "answer": "27."},
                {"question": "Was ist ein Kompromiss?", "answer": "Einigung durch gegenseitige Zugestaendnisse."},
            ],
            60: [
                {"question": "Was ist der Unterschied zwischen Verhältnis- und Mehrheitswahl grob?", "answer": "Verhaeltniswahl bildet Stimmenanteile ab, Mehrheitswahl bevorzugt Sieger pro Wahlkreis."},
                {"question": "Wie heißt die deutsche Verfassung?", "answer": "Grundgesetz."},
                {"question": "Was ist Föderalismus in Deutschland?", "answer": "Aufteilung von Staatsaufgaben zwischen Bund und Laendern."},
                {"question": "Wie nennt man gezielte Falschinformationen in politischen Debatten?", "answer": "Desinformation."},
            ],
            80: [
                {"question": "Was prüft das Bundesverfassungsgericht?", "answer": "Vereinbarkeit von Gesetzen und staatlichem Handeln mit dem Grundgesetz."},
                {"question": "Wie nennt man den Haushaltssaldo zwischen Staatseinnahmen und -ausgaben?", "answer": "Budgetsaldo/Haushaltssaldo."},
                {"question": "Was ist politische Partizipation?", "answer": "Beteiligung an politischen Entscheidungsprozessen."},
                {"question": "Wofür steht die Abkürzung NGO?", "answer": "Nichtregierungsorganisation."},
            ],
            100: [
                {"question": "Was ist der Unterschied zwischen Rechtsstaat und Willkürherrschaft?", "answer": "Rechtsstaat bindet Macht an Gesetze und Kontrolle, Willkuerherrschaft nicht."},
                {"question": "Was versteht man unter sozialer Marktwirtschaft?", "answer": "Marktwirtschaft mit sozialem Ausgleich und staatlichem Rahmen."},
                {"question": "Wie heißt das Prinzip, nach dem Entscheidungen möglichst auf niedriger Ebene getroffen werden sollen (EU)?", "answer": "Subsidiaritaetsprinzip."},
                {"question": "Was bedeutet Pluralismus in einer Gesellschaft?", "answer": "Anerkennung mehrerer legitimer Meinungen und Lebensformen."},
            ],
        },
        "Allgemeinwissen": {
            20: [
                {"question": "Wie viele Stunden hat eine Woche?", "answer": "168."},
                {"question": "Welcher Planet ist der größte im Sonnensystem?", "answer": "Jupiter."},
                {"question": "Wie viele Milliliter sind 1 Liter?", "answer": "1000."},
                {"question": "Wie heißt die Einheit für elektrische Leistung?", "answer": "Watt."},
            ],
            40: [
                {"question": "Wie viele Knochen hat der Mensch im Erwachsenenalter meistens?", "answer": "206."},
                {"question": "Welches Metall hat das chemische Symbol Au?", "answer": "Gold."},
                {"question": "Wie viele Länder bilden das Vereinigte Königreich?", "answer": "4."},
                {"question": "Wie heißt die Hauptstadt von Australien?", "answer": "Canberra."},
            ],
            60: [
                {"question": "Was ist die SI-Einheit der Frequenz?", "answer": "Hertz."},
                {"question": "Welches Gas entsteht bei vollständiger Verbrennung von Kohlenstoff hauptsächlich?", "answer": "Kohlendioxid."},
                {"question": "Wie heißt das längste Knochen im menschlichen Körper?", "answer": "Oberschenkelknochen/Femur."},
                {"question": "Wie viele Nullen hat eine Milliarde?", "answer": "9."},
            ],
            80: [
                {"question": "Wer formulierte die allgemeine Relativitätstheorie?", "answer": "Albert Einstein."},
                {"question": "Welche Einheit misst elektrische Ladung?", "answer": "Coulomb."},
                {"question": "Welche Stadt ist Sitz der Vereinten Nationen (Hauptquartier)?", "answer": "New York."},
                {"question": "Welche Sprache hat weltweit die meisten Muttersprachler?", "answer": "Mandarin-Chinesisch."},
            ],
            100: [
                {"question": "Was beschreibt der zweite Hauptsatz der Thermodynamik vereinfacht?", "answer": "Entropie in abgeschlossenen Systemen nimmt nicht ab."},
                {"question": "Welche Zahl ist der Näherungswert von pi auf 4 Nachkommastellen?", "answer": "3,1416."},
                {"question": "Wie lautet die chemische Formel von Schwefelsäure?", "answer": "H2SO4."},
                {"question": "Wie heißt die Hauptstadt von Kanada?", "answer": "Ottawa."},
            ],
        },
    },
}


def _points_quiz_bank_for_age(age: str) -> dict:
    if age not in POINTS_QUIZ_RANDOM_BANK:
        return POINTS_QUIZ_RANDOM_BANK["mid"]
    return POINTS_QUIZ_RANDOM_BANK[age]


def _points_quiz_age_label(age: str) -> str:
    for key, label in POINTS_QUIZ_AGE_OPTIONS:
        if key == age:
            return label
    return "11 - 16 Jahre"


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


def _wiki_local_hint(term: str, question: str = "", options: list[str] | None = None) -> str:
    key = (term or "").strip().lower()
    q = (question or "").strip().lower()
    for hint_key, text in WIKIPEDIA_HINTS.items():
        if hint_key in key:
            return text

    if "tier" in q:
        return "Ein Lebewesen aus dem Tierreich, oft in Biologie und Alltag bekannt."
    if any(k in q for k in ("land", "hauptstadt", "stadt", "kontinent")):
        return "Ein geografischer Begriff mit Bezug zu Ort, Region oder Staat."
    if any(k in q for k in ("farbe", "misch", "farben")):
        return "Ein Begriff aus der Farblehre oder visuellen Wahrnehmung."
    if any(k in q for k in ("jahr", "monat", "tag", "uhr", "zeit")):
        return "Ein Begriff aus Zeitrechnung, Kalender oder Tagesablauf."
    if any(k in q for k in ("element", "chem", "formel", "gas")):
        return "Ein Fachbegriff aus Chemie oder Naturwissenschaft."
    if any(k in q for k in ("musik", "instrument", "komponist")):
        return "Ein Begriff aus Musik, Kultur oder Kunstgeschichte."
    if any(k in q for k in ("planet", "sonne", "mond", "stern")):
        return "Ein Begriff aus Astronomie oder Weltraumforschung."
    if options:
        return (
            "Die Lösung ist ein Fachbegriff, der klar in den Kontext der Frage passt. "
            "Vergleiche die Antwortmöglichkeiten nach Bedeutung statt nach Klang."
        )
    return "Ein Begriff aus Allgemeinwissen mit klarer Definition in Lexika."


def wikipedia_definition(term: str, question: str = "", options: list[str] | None = None) -> str:
    """Fetches a short extract from German Wikipedia and hides spoiler words."""
    # 1. Try Wikipedia API (German)
    try:
        search_url = "https://de.wikipedia.org/w/api.php?action=opensearch&search=" + requests.utils.quote(term.strip()) + "&limit=1&format=json"
        s_resp = requests.get(search_url, timeout=3)
        if s_resp.status_code == 200:
            s_data = s_resp.json()
            if len(s_data) >= 2 and s_data[1]:
                best_title = s_data[1][0]
                base_title = best_title.split("(")[0].strip()
                url = "https://de.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(best_title)
                resp = requests.get(url, timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    extract: str = data.get("extract", "")
                    if extract and len(extract) > 20:
                        for w in [term.strip(), term.strip().capitalize(), best_title, best_title.capitalize(), base_title, base_title.capitalize()]:
                            if w and len(w) > 3 and w in extract:
                                extract = extract.replace(w, "___")
                        if len(extract) > 300:
                            extract = extract[:300].rsplit(" ", 1)[0] + " …"
                        return extract
    except Exception:
        pass

    # 2. Local fallback
    return _wiki_local_hint(term, question, options)


def word_tip_for(term: str, question: str = "", options: list[str] | None = None) -> str:
    key = term.strip().lower()
    # Prefer a distinctive token from the correct answer that does not appear in other options.
    if options:
        opt_keys = [str(o).strip().lower() for o in options]
        parts = [p for p in re.split(r"[\s,;/()\-]+", key) if len(p) >= 4]
        for p in parts:
            if sum(1 for o in opt_keys if p in o) == 1:
                return p.capitalize()
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


def set_game_modal(state: dict, panel: ft.Control, page: ft.Page | None = None):
    """Wrap panel in a draggable overlay that cannot leave the screen."""
    state["_modal_overlay"] = _DraggableModal(panel, page=page)


def clear_game_modal(state: dict):
    state.pop("_modal_overlay", None)


def _DraggableModal(panel: ft.Control, page: ft.Page | None = None) -> ft.Stack:
    """Darkened overlay + draggable card, centered initially and clamped to viewport."""
    panel_w = int(getattr(panel, "width", None) or 420)
    panel_h_est = 360
    pos = {"left": None, "top": None}

    panel_host = ft.Container(content=panel, width=panel_w)
    initial_left = 120
    initial_top = 120
    if page is not None:
        pw, ph = _page_size(page)
        initial_left = max(10, int((pw - panel_w) / 2))
        initial_top = max(10, int((ph - panel_h_est) / 2))
        pos["left"] = float(initial_left)
        pos["top"] = float(initial_top)

    floating = ft.Container(
        content=ft.Column([], spacing=0),
        left=initial_left,
        top=initial_top,
    )

    def ensure_position(page: ft.Page):
        pw, ph = _page_size(page)
        max_w = max(280, min(panel_w, int(pw - 20)))
        panel_host.width = max_w
        if pos["left"] is None or pos["top"] is None:
            pos["left"] = max(10, (pw - max_w) / 2)
            pos["top"] = max(10, (ph - panel_h_est) / 2)
        pos["left"] = max(10, min(float(pos["left"]), max(10, pw - max_w - 10)))
        pos["top"] = max(10, min(float(pos["top"]), max(10, ph - 140)))
        floating.left = pos["left"]
        floating.top = pos["top"]

    def on_pan_update(e):
        try:
            page = e.control.page
            if page is None:
                return
            ensure_position(page)
            pw, ph = _page_size(page)
            max_w = float(panel_host.width or panel_w)
            pos["left"] = max(10, min((pos["left"] or 10) + e.delta_x, max(10, pw - max_w - 10)))
            pos["top"] = max(10, min((pos["top"] or 10) + e.delta_y, max(10, ph - 140)))
            floating.left = pos["left"]
            floating.top = pos["top"]
            floating.update()
        except Exception:
            pass

    drag_handle = ft.GestureDetector(
        content=ft.Container(
            content=ft.Text("⠿ verschieben", size=11, color="#D1D5DB", text_align="center"),
            height=26,
            bgcolor="#33415599",
            border_radius=ft.BorderRadius(14, 14, 0, 0),
            alignment=ft.Alignment(0, 0),
            width=panel_w,
        ),
        on_pan_update=on_pan_update,
        mouse_cursor=ft.MouseCursor.MOVE,
        drag_interval=12,
    )

    floating.content.controls = [
        ft.Container(
            content=ft.Column([drag_handle, panel_host], spacing=0),
            border_radius=16,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=ft.BoxShadow(blur_radius=30, color="#AA000000", spread_radius=2),
        )
    ]

    backdrop = ft.Container(expand=True, bgcolor="#0000009a", blur=8)
    return ft.Stack([backdrop, floating], expand=True)


async def _flash_joker_activation(page: ft.Page, state: dict, theme: dict):
    """Large animated pulse effect when a joker is used (pauses timer)."""
    accent = theme.get("accent", "#22D3EE")
    gold = theme.get("gold", "#FFD700")
    duration = 3.0
    state["_timer_pause_until"] = time.time() + duration

    pulse = ft.Container(
        content=ft.Stack(
            [
                ft.Container(width=360, height=360, border_radius=180, border=ft.border.Border.all(8, f"#66{accent[1:]}"), bgcolor="#00000000"),
                ft.Container(width=240, height=240, border_radius=120, border=ft.border.Border.all(6, f"#77{gold[1:]}"), bgcolor="#00000000"),
                ft.Container(content=ft.Text("✦", size=64, color=gold), alignment=ft.Alignment(0, 0), width=180, height=180),
            ],
            alignment=ft.Alignment(0, 0),
        ),
        alignment=ft.Alignment(0, 0),
        expand=True,
        bgcolor="#00000044",
        scale=0.4,
        opacity=0.0,
        animate_scale=ft.Animation(2600, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(2600, ft.AnimationCurve.EASE_OUT),
    )
    page.overlay.append(pulse)
    try:
        pulse.opacity = 1.0
        pulse.scale = 0.9
        page.update()
        await asyncio.sleep(0.25)
        pulse.scale = 2.8
        pulse.opacity = 0.02
        page.update()
        await asyncio.sleep(max(0.1, duration - 0.25))
    except Exception:
        pass
    finally:
        state.pop("_timer_pause_until", None)
        if pulse in page.overlay:
            page.overlay.remove(pulse)
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

    panel_bg = "#060d09f0" if _is_video_background(_resolve_theme_background(_theme_key_from_theme(theme) or "", "game")) else theme["panel"]
    set_game_modal(
        state,
        ft.Container(
            content=ft.Column([
                ft.Text(title, size=20, weight="bold", color=theme_txt(theme, "primary"), text_align="center"),
                body_ctrl,
                ft.Container(height=8),
                _game_menu_button("OK", close, theme["accent"], width=160),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            bgcolor=panel_bg,
            border_radius=16,
            padding=24,
            border=ft.border.Border.all(2, theme["gold"]),
            width=360,
        ),
        page=page,
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
        bgcolor="#060d09f0" if _is_video_background(_resolve_theme_background(_theme_key_from_theme(theme) or "", "game")) else theme.get("panel", "#1A1A1A"),
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
                definition = await loop.run_in_executor(None, lambda: wikipedia_definition(term, question, options))
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
        word = word_tip_for(options[correct_idx], question, options)
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
        state["info_hint"] = "W/F aktiv: Tippe eine Antwort, um richtig/falsch zu testen."
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Tippe eine Antwort zum Testen – danach kannst du normal weiterwählen."),
            duration=3500,
        )
        page.snack_bar.open = True
        render_game_screen(page, state)
        return

    if joker_id == "emoji":
        mark_joker_used(state, joker_id)
        term = options[correct_idx]
        body_ref = ft.Text("⏳ Suche Emojis …", size=24, color=theme_txt(theme, "secondary"), text_align="center")
        show_game_message_with_body(page, state, "Emoji-Joker", body_ref, theme)

        async def _load_emoji():
            loop = asyncio.get_event_loop()
            try:
                em = await loop.run_in_executor(None, lambda: emoji_hint_for_answer(f"{term} {question}"))
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
        panel_bg = "#060d09f0" if _is_video_background(_resolve_theme_background(_theme_key_from_theme(theme) or "", "game")) else theme["panel"]
        percents = generate_audience_percents(correct_idx)
        # Make bars less uniform and keep correct answer around ~85% chance to lead.
        if random.random() < 0.85:
            top = random.randint(46, 72)
            rest = 100 - top
            wrong = [i for i in range(len(options)) if i != correct_idx]
            random.shuffle(wrong)
            split = [random.randint(5, max(8, rest - 10)), random.randint(3, 25)]
            split.append(max(3, rest - split[0] - split[1]))
            random.shuffle(split)
            for i, v in zip(wrong, split):
                percents[i] = max(3, v)
            percents[correct_idx] = max(35, 100 - sum(percents[i] for i in wrong))
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
                bgcolor=panel_bg,
                border_radius=16,
                padding=20,
                border=ft.border.Border.all(2, theme["border"]),
                width=400,
            ),
            page=page,
        )
        render_game_screen(page, state)
        return

    if joker_id == "phone":
        mark_joker_used(state, joker_id)
        if bool(state.get("time_pressure_enabled", True)):
            state["phone_until"] = time.time() + PHONE_JOKER_SEC
        else:
            state.pop("phone_until", None)
        try:
            page.launch_url("tel:")
        except Exception:
            pass
        if bool(state.get("time_pressure_enabled", True)):
            sync_timer_display(page, state)
            _show_joker_countdown_dialog(page, state, theme, "📞 Telefon-Joker", PHONE_JOKER_SEC, "phone_until")
        else:
            show_game_message(page, state, "📞 Telefon-Joker", "Timer ist aus. Nimm dir die Zeit, die du brauchst.", theme)
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
        if selected and not used:
            text_color = "#FFFFFF"
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
    def on_hover(e):
        e.control.shadow = ft.BoxShadow(blur_radius=26, color="#66D946EF", spread_radius=2) if e.data == "true" else (
            ft.BoxShadow(blur_radius=14, color="#60FFD700") if selected and not used else None
        )
        e.control.border = ft.border.Border.all(
            3 if e.data == "true" else border_w,
            "#F0ABFC" if e.data == "true" else border_color,
        )
        e.control.update()

    tile.on_click = on_click
    tile.on_hover = on_hover
    tile.ink = True
    return tile


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
            await _flash_joker_activation(page, state, theme)
            activate_joker(page, state, joker_id, ctx)

        page.run_task(run_joker)

    page_w = page.width or (page.window.width if getattr(page, "window", None) else 1100) or 1100
    is_small_mobile = page_w < 430
    chip_size = 48 if is_small_mobile else 60
    chip_spacing = 6 if is_small_mobile else 8

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
                size=chip_size,
                on_click=lambda e, j=jid: on_joker_tap(j),
                show_name=True,
            )
        )
    while len(chips) < JOKER_SELECT_COUNT:
        chips.append(
            ft.Container(
                width=chip_size,
                height=chip_size,
                border_radius=12,
                bgcolor=theme.get("question_bg", "#FFFFFF"),
                border=ft.border.Border.all(1, theme["border"]),
            )
        )

    return ft.Row(chips, spacing=chip_spacing, alignment=ft.MainAxisAlignment.CENTER, wrap=is_small_mobile, run_spacing=chip_spacing)


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
    theme_key = _theme_key_from_theme(theme)
    video_available = bool(FletVideo and VideoMedia and PlaylistMode)
    joker_bg_src = _resolve_theme_background(theme_key, "joker", allow_video=video_available) if theme_key else None
    has_video_bg = video_available and _is_video_background(joker_bg_src)
    panel_bg = "#060d09f0" if has_video_bg else theme["panel"]
    secondary_text = "#D7DEE9" if has_video_bg else theme_txt(theme, "secondary")

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
            content=ft.Stack(
                [
                    *([_build_looping_joker_background(page, theme)] if joker_bg_src else []),
                    ft.Container(expand=True, bgcolor="#000000b8" if has_video_bg else "#00000055"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Joker bestätigen", size=28, weight="bold", color="white", text_align="center"),
                            ft.Text(
                                "Möchtest du diese Joker auswählen?",
                                size=16,
                                text_align="center",
                                color=secondary_text,
                            ),
                            ft.Container(height=12),
                            ft.Container(
                                content=chips,
                                bgcolor=panel_bg,
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
                    ),
                ],
                expand=True,
            ),
            alignment=ft.Alignment(0, 0),
        )
    )
    page.update()


def show_joker_selection(page: ft.Page, state: dict, on_start):
    """Pick 4 jokers from catalog, confirm, then start the game."""
    theme = get_theme(state)
    theme_key = _theme_key_from_theme(theme)
    video_available = bool(FletVideo and VideoMedia and PlaylistMode)
    joker_bg_src = _resolve_theme_background(theme_key, "joker", allow_video=video_available) if theme_key else None
    has_video_bg = video_available and _is_video_background(joker_bg_src)
    panel_bg = "#060d09f0" if has_video_bg else theme["panel"]
    secondary_text = "#D7DEE9" if has_video_bg else theme_txt(theme, "secondary")
    pick = list(state.get("joker_pick_buffer", []))
    state.setdefault("time_pressure_enabled", True)
    state.setdefault("question_time_sec", QUESTION_TIME_SEC)
    state.setdefault("jokers_enabled", True)

    def toggle_joker(joker_id: str):
        nonlocal pick
        if joker_id in pick:
            pick.remove(joker_id)
        elif len(pick) < JOKER_SELECT_COUNT:
            pick.append(joker_id)
        state["joker_pick_buffer"] = pick
        refresh_ui()

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

    def on_time_pressure_change(e):
        state["time_pressure_enabled"] = bool(e.control.value)
        refresh_ui()

    def on_question_time_change(e):
        try:
            state["question_time_sec"] = int(e.control.value)
        except Exception:
            state["question_time_sec"] = QUESTION_TIME_SEC
        refresh_ui()

    def on_jokers_enabled_change(e):
        state["jokers_enabled"] = bool(e.control.value)
        refresh_ui()

    def on_back(e):
        reset_joker_pick_state(state)
        if state.get("is_custom_game") or state.get("custom_quiz_id"):
            show_custom_quiz_hub(page, state)
        else:
            show_game_start_menu(page, state, get_saved_game_for_state(state))

    timer_checkbox = ft.Checkbox(
        label="Timer aktivieren",
        value=bool(state.get("time_pressure_enabled", True)),
        on_change=on_time_pressure_change,
        fill_color=theme["accent"],
        check_color="white",
        label_style=ft.TextStyle(color=secondary_text, size=13),
    )
    jokers_checkbox = ft.Checkbox(
        label="Joker aktivieren",
        value=bool(state.get("jokers_enabled", True)),
        on_change=on_jokers_enabled_change,
        fill_color=theme["accent"],
        check_color="white",
        label_style=ft.TextStyle(color=secondary_text, size=13),
    )
    time_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(str(v)) for v in QUESTION_TIME_OPTIONS],
        value=str(int(state.get("question_time_sec", QUESTION_TIME_SEC))),
        width=120,
    )
    time_dropdown.on_select = on_question_time_change
    timer_off_text = ft.Text(
        "Timer aus – kein Countdown",
        size=13,
        color=secondary_text,
        weight="bold",
    )
    timer_row = ft.Row(
        [
            ft.Text("Sekunden pro Frage:", size=13, color=secondary_text),
            time_dropdown,
            timer_off_text,
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
    )

    check_btn = ft.Container(
        content=ft.Text("✓", size=28, weight="bold", color="#888888"),
        width=58,
        height=58,
        border_radius=12,
        bgcolor="#555555",
        alignment=ft.Alignment(0, 0),
        on_click=on_check,
        ink=True,
        border=ft.border.Border.all(3, theme["border"]),
    )
    check_btn.on_hover = lambda e: (
        setattr(e.control, "shadow", ft.BoxShadow(blur_radius=24, color="#55D946EF", spread_radius=1))
        or e.control.update()
    ) if e.data == "true" else (
        setattr(e.control, "shadow", None) or e.control.update()
    )

    selected_row = ft.Row([], alignment=ft.MainAxisAlignment.CENTER, spacing=10, wrap=True)
    selected_panel_width = min(520, int((58 * JOKER_SELECT_COUNT) + 58 + (10 * (JOKER_SELECT_COUNT + 1)) + 32))
    selected_panel = ft.Container(
        content=ft.Row([selected_row, check_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=14),
        bgcolor=panel_bg,
        border_radius=14,
        padding=16,
        border=ft.border.Border.all(2, theme["border"]),
        width=selected_panel_width,
    )
    start_without_joker = ft.Container(
        content=ft.ElevatedButton("Start ohne Joker", on_click=on_check, style=ft.ButtonStyle(bgcolor=theme["success"], color="white")),
        padding=20,
    )
    selection_label = ft.Text("Deine Auswahl", size=13, color=theme["gold"], weight="bold")
    catalog_row = ft.Row([], wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)
    catalog_wrap = ft.Container(content=catalog_row, width=520, padding=10)

    def refresh_ui():
        time_pressure_enabled = bool(state.get("time_pressure_enabled", True))
        jokers_enabled = bool(state.get("jokers_enabled", True))

        timer_checkbox.value = time_pressure_enabled
        jokers_checkbox.value = jokers_enabled
        time_dropdown.visible = time_pressure_enabled
        timer_off_text.visible = not time_pressure_enabled
        time_dropdown.value = str(int(state.get("question_time_sec", QUESTION_TIME_SEC)))

        check_enabled = len(pick) == JOKER_SELECT_COUNT
        check_btn.content.value = "✓"
        check_btn.content.color = "white" if check_enabled else "#888888"
        check_btn.bgcolor = theme["success"] if check_enabled else "#555555"
        check_btn.border = ft.border.Border.all(3, theme["gold"] if check_enabled else theme["border"])

        selected_row.controls = [
            build_joker_tile(
                get_joker(jid),
                theme,
                selected=True,
                size=58,
                on_click=lambda e, jid=jid: toggle_joker(jid),
                show_name=True,
            )
            for jid in pick
            if get_joker(jid)
        ]

        catalog_row.controls = []
        for joker in JOKER_CATALOG:
            is_sel = joker["id"] in pick
            disabled = len(pick) >= JOKER_SELECT_COUNT and not is_sel
            catalog_row.controls.append(
                build_joker_tile(
                    joker,
                    theme,
                    selected=is_sel,
                    size=62,
                    on_click=None if disabled else (lambda e, jid=joker["id"]: toggle_joker(jid)),
                    show_name=True,
                )
            )

        selected_panel.visible = jokers_enabled
        selection_label.visible = jokers_enabled
        catalog_wrap.visible = jokers_enabled
        start_without_joker.visible = not jokers_enabled
        page.update()

    config_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [timer_checkbox, ft.Container(width=20), jokers_checkbox],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=6),
                timer_row,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=panel_bg,
        border_radius=14,
        padding=12,
        border=ft.border.Border.all(2, theme["border"]),
    )

    foreground = ft.Column([
        ft.Text("Wähle deinen Joker", size=28, weight="bold", color="white", text_align="center"),
        ft.Text(
            f"Tippe {JOKER_SELECT_COUNT} Joker an (oben oder unten) · erneut tippen zum Abwählen",
            size=14,
            color=secondary_text,
            text_align="center",
        ),
        ft.Container(height=8),
        config_card,
        ft.Container(height=10),
        selected_panel,
        start_without_joker,
        selection_label,
        catalog_wrap,
        ft.TextButton("← Zurück", on_click=on_back, style=ft.ButtonStyle(color="white")),
    ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )

    background = _build_looping_joker_background(page, theme)
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    *([background] if background else []),
                    ft.Container(expand=True, bgcolor="#000000b8" if has_video_bg else "#00000055"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=foreground,
                    ),
                ],
                expand=True,
            ),
            alignment=ft.Alignment(0, 0),
        )
    )
    refresh_ui()


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

CURATED_EASY_QUESTIONS = [
    ("In welchem Land liegt die Stadt Wien?", "Oesterreich", ["Schweiz", "Belgien", "Niederlande"]),
    ("Welches Meer liegt zwischen Europa und Afrika?", "Mittelmeer", ["Nordsee", "Ostsee", "Karibik"]),
    ("Welcher Kontinent ist flaechenmaessig der groesste?", "Asien", ["Europa", "Australien", "Antarktis"]),
    ("Wie nennt man die gedachte Linie um die Erde auf halber Hoehe?", "Aequator", ["Nullmeridian", "Wendekreis", "Polarkreis"]),
    ("Welche Farbe hat ein typisches Stoppschild?", "Rot", ["Gruen", "Blau", "Gelb"]),
    ("Wie nennt man das Parlament in Deutschland?", "Bundestag", ["Bundesrat", "EU-Rat", "Landtag"]),
    ("Wer malte die 'Sternennacht'?", "Vincent van Gogh", ["Pablo Picasso", "Claude Monet", "Edvard Munch"]),
    ("Welche Zahl ist eine Primzahl?", "13", ["12", "15", "21"]),
    ("Welche Einheit wird fuer elektrische Stromstaerke genutzt?", "Ampere", ["Volt", "Watt", "Ohm"]),
    ("Welche Sprache spricht man hauptsaechlich in Argentinien?", "Spanisch", ["Portugiesisch", "Franzoesisch", "Italienisch"]),
    ("Welches Organ ist fuer den Gasaustausch zustaendig?", "Lunge", ["Leber", "Milz", "Bauchspeicheldruese"]),
    ("Welche Sportart spielt man auf einem Eisfeld mit Schlaeger und Puck?", "Eishockey", ["Handball", "Volleyball", "Baseball"]),
    ("Wie heisst die Hauptstadt von Irland?", "Dublin", ["Cork", "Belfast", "Galway"]),
    ("Welches Material gewinnt man aus Kautschukbaeumen?", "Gummi", ["Glas", "Beton", "Kupfer"]),
    ("Welcher Planet wird oft der 'rote Planet' genannt?", "Mars", ["Saturn", "Neptun", "Venus"]),
    ("Welche Himmelsrichtung zeigt ein Kompass in der Regel an?", "Norden", ["Sueden", "Westen", "Osten"]),
]

CURATED_MEDIUM_QUESTIONS = [
    ("Welche Stadt ist Sitz des Internationalen Gerichtshofs?", "Den Haag", ["Bruessel", "Genf", "Wien"]),
    ("Welche chemische Formel hat Kochsalz?", "NaCl", ["KCl", "HCl", "CaCO3"]),
    ("Welcher Fluss fliesst durch Budapest?", "Donau", ["Rhein", "Loire", "Po"]),
    ("Wer schrieb den Roman '1984'?", "George Orwell", ["Aldous Huxley", "Ray Bradbury", "Ernest Hemingway"]),
    ("Wie heisst die Waehrung in Japan?", "Yen", ["Won", "Renminbi", "Ringgit"]),
    ("Was beschreibt der Begriff 'Inflation' am besten?", "Anstieg des allgemeinen Preisniveaus", ["Sinkende Steuern", "Mehr Exporte", "Steigende Geburtenrate"]),
    ("In welchem Jahr wurde die Europaeische Union in ihrer heutigen Form begruendet (Maastricht)?", "1993", ["1989", "1999", "2004"]),
    ("Welche Schicht der Erdatmosphaere enthaelt den Grossteil des Ozons?", "Stratosphaere", ["Troposphaere", "Mesosphaere", "Thermosphaere"]),
    ("Wie heisst das groesste Organ des Menschen?", "Haut", ["Leber", "Lunge", "Darm"]),
    ("Welches Instrument misst Luftdruck?", "Barometer", ["Hygrometer", "Seismograf", "Spektrometer"]),
    ("Wer war der erste Bundeskanzler der Bundesrepublik Deutschland?", "Konrad Adenauer", ["Willy Brandt", "Helmut Kohl", "Ludwig Erhard"]),
    ("Welcher Staat besitzt die meisten Zeitzonen auf seinem Staatsgebiet?", "Frankreich", ["Russland", "USA", "China"]),
    ("Was ist ein Isotop?", "Atom gleicher Protonenzahl mit anderer Neutronenzahl", ["Atom mit gleicher Masse", "Elektron ohne Ladung", "Molekuel mit einem Atom"]),
    ("Welche Stadt liegt auf zwei Kontinenten?", "Istanbul", ["Kairo", "Athen", "Lissabon"]),
    ("Welche Energieeinheit wird in der Physik verwendet?", "Joule", ["Tesla", "Hertz", "Kelvin"]),
    ("Welches Land hat den Euro eingefuehrt, war aber nicht Gruendungsmitglied der EU?", "Kroatien", ["Belgien", "Italien", "Luxemburg"]),
]

CURATED_HARD_QUESTIONS = [
    ("Wie lautet die Hauptstadt von Kasachstan seit der Rueckbenennung 2022?", "Astana", ["Almaty", "Bischkek", "Taschkent"]),
    ("Welches Abkommen beendete 1648 den Dreissigjaehrigen Krieg?", "Westfaelischer Friede", ["Frieden von Utrecht", "Wiener Kongressakte", "Pariser Frieden"]),
    ("Welches Teilchen vermittelt in der Standardtheorie die starke Wechselwirkung?", "Gluon", ["Photon", "Neutrino", "Graviton"]),
    ("Was ist die Ableitung von sin(x)?", "cos(x)", ["-sin(x)", "-cos(x)", "tan(x)"]),
    ("Welche Stadt war Austragungsort der ersten modernen Olympischen Spiele 1896?", "Athen", ["Paris", "London", "Rom"]),
    ("Welche DNA-Base paart mit Guanin?", "Cytosin", ["Adenin", "Thymin", "Uracil"]),
    ("Welche Inselgruppe gehoert zu Spanien und liegt im Atlantik vor Afrika?", "Kanarische Inseln", ["Balearen", "Azoren", "Kapverden"]),
    ("Wie heisst das oekonomische Modell mit Angebots-Nachfrage-Gleichgewichtspunkt?", "Marktgleichgewicht", ["Goldener Schnitt", "Nash-Gewicht", "Pareto-Front"]),
    ("Welche Kunststroemung ist mit Claude Monet besonders verbunden?", "Impressionismus", ["Expressionismus", "Kubismus", "Dadaismus"]),
    ("Welches Metall hat die Ordnungszahl 82?", "Blei", ["Zinn", "Wismut", "Kupfer"]),
    ("Welche Programmiersprache laeuft typischerweise auf der JVM?", "Java", ["C", "Go", "Rust"]),
    ("Was ist die Loesung von 2x + 3 = 19?", "8", ["7", "9", "6"]),
    ("Welches Land war Gastgeber der FIFA-WM 2010?", "Suedafrika", ["Brasilien", "Deutschland", "Japan"]),
    ("Welche Skala misst Erdbeben als Magnitude?", "Richter-Skala", ["Beaufort-Skala", "Kelvin-Skala", "Mohs-Skala"]),
    ("Welcher Denker praegte den kategorischen Imperativ?", "Immanuel Kant", ["John Locke", "Thomas Hobbes", "David Hume"]),
    ("Was beschreibt die Halbwertszeit?", "Zeit bis zur Halbierung einer Menge", ["Dauer bis zur Verdopplung", "Zeit bis zur Reaktion", "Zeit pro Messung"]),
]

CURATED_EXPERT_QUESTIONS = [
    ("Welches Prinzip besagt, dass keine Information schneller als Licht uebertragen werden kann?", "Kausalitaetsprinzip der Relativitaet", ["Unschärferelation", "Pauli-Prinzip", "Entropiesatz"]),
    ("Wie heisst die Hauptstadt von Myanmar?", "Naypyidaw", ["Yangon", "Mandalay", "Bangkok"]),
    ("Welche mathematische Konstante ist die Basis des natuerlichen Logarithmus?", "e", ["pi", "phi", "i"]),
    ("Welcher Vertrag gruendete 1957 die EWG?", "Roemische Vertraege", ["Vertrag von Maastricht", "Vertrag von Lissabon", "Schengener Abkommen"]),
    ("Welches physikalische Gesetz verbindet Spannung, Stromstaerke und Widerstand?", "Ohmsches Gesetz", ["Hookesches Gesetz", "Boyle-Mariotte-Gesetz", "Bernoulli-Gesetz"]),
    ("Welche Programmiersprache wurde von Guido van Rossum entwickelt?", "Python", ["Perl", "Ruby", "Lua"]),
    ("Welche Stadt liegt am Zusammenfluss von Weissblauem und Blauem Nil?", "Khartum", ["Kairo", "Addis Abeba", "Alexandria"]),
    ("Wer schrieb die 'Kritik der praktischen Vernunft'?", "Immanuel Kant", ["Fichte", "Hegel", "Schopenhauer"]),
    ("Welche chemische Bindung entsteht durch Elektronenpaarteilung?", "kovalente Bindung", ["Ionenbindung", "Metallbindung", "Wasserstoffbruecke"]),
    ("Wie heisst die groesste Wuestenregion Asiens?", "Gobi", ["Kalahari", "Atacama", "Sahara"]),
    ("Welche Konstante beschreibt die universelle Gravitationswirkung?", "Gravitationskonstante G", ["Planck-Konstante", "Avogadro-Zahl", "Faraday-Konstante"]),
    ("Welcher Begriff beschreibt die Streuung eines Portfolios zur Risikominderung?", "Diversifikation", ["Liquidation", "Arbitrage", "Kapitalflucht"]),
    ("Welches Molekuel traegt genetische Information in Zellen?", "DNA", ["ATP", "NADH", "mRNA"]),
    ("Welche Stadt ist Sitz der EZB?", "Frankfurt am Main", ["Bruessel", "Luxemburg", "Strassburg"]),
    ("Welcher Philosoph verfasste 'Also sprach Zarathustra'?", "Friedrich Nietzsche", ["Arthur Schopenhauer", "Soren Kierkegaard", "Karl Jaspers"]),
    ("Welcher Ozean ist der tiefste?", "Pazifischer Ozean", ["Atlantischer Ozean", "Indischer Ozean", "Arktischer Ozean"]),
]


def supplemental_question(level_idx: int, variant: int) -> tuple:
    prompt, correct, wrongs = EXTRA_TOPIC_QUESTIONS[(level_idx * 17 + variant) % len(EXTRA_TOPIC_QUESTIONS)]
    return _make_question(prompt, correct, wrongs)


def _difficulty_bucket_for_level(level_idx: int) -> str:
    total = max(1, len(MONEY_LEVELS))
    ratio = (level_idx + 1) / total
    if ratio <= 0.27:
        return "easy"
    if ratio <= 0.53:
        return "medium"
    if ratio <= 0.80:
        return "hard"
    return "expert"


def _curated_question_for_level(level_idx: int, variant: int) -> tuple:
    bucket = _difficulty_bucket_for_level(level_idx)
    pools = {
        "easy": CURATED_EASY_QUESTIONS,
        "medium": CURATED_MEDIUM_QUESTIONS,
        "hard": CURATED_HARD_QUESTIONS,
        "expert": CURATED_EXPERT_QUESTIONS,
    }
    pool = pools.get(bucket, CURATED_MEDIUM_QUESTIONS)
    prompt, correct, wrongs = pool[(level_idx * 31 + variant) % len(pool)]
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
            *[supplemental_question(level_idx, variant) for variant in range(80)],
            *[_curated_question_for_level(level_idx, variant) for variant in range(120)],
        ]
        for level_idx in range(len(MONEY_LEVELS))
    ]


QUESTION_TOPIC_KEYWORDS = {
    "geschichte": ["jahr", "krieg", "revolution", "mittelalter", "kaiser", "vertrag", "histor", "griech", "röm", "mauer"],
    "geografie": ["hauptstadt", "fluss", "kontinent", "insel", "meer", "ozean", "gebirge", "land", "wüste", "graben"],
    "wissenschaft": ["chem", "physik", "biolog", "zelle", "dna", "atom", "licht", "temperatur", "gravitation", "reaktion"],
    "mathematik": ["was ist", "gleichung", "prozent", "quadrat", "primzahl", "drittel", "hälfte", "x ", " + ", " - ", " %"],
    "technik": ["internet", "algorithm", "html", "ip-", "passwort", "computer", "programmier", "jvm", "software"],
    "kultur": ["roman", "oper", "musik", "künstler", "malte", "kompon", "literatur", "philosoph", "kunst", "film"],
    "sport": ["sport", "fußball", "wm", "olymp", "puck", "tennis", "badminton", "basketball", "tour"],
    "wirtschaft": ["inflation", "währung", "budget", "bip", "diversifikation", "preis", "rabatt", "opportunitätskosten"],
    "natur": ["tier", "pflanze", "ozean", "wald", "blume", "sonnen", "frosch", "sauerstoff", "ozon", "korallen"],
}
QUESTION_TOPIC_ROTATION = [
    "geschichte",
    "geografie",
    "wissenschaft",
    "kultur",
    "natur",
    "technik",
    "sport",
    "wirtschaft",
    "mathematik",
]
SEASONAL_QUESTIONS = {
    "winter": [
        ("Was ist in Mitteleuropa ein typisches Winter-Phänomen?", "Schneefall", ["Monsunregen", "Hitzewelle", "Sandsturm"]),
        ("Welche Farbe haben Streusalz-Kristalle meist?", "weiß", ["grün", "rot", "blau"]),
        ("Welcher Monat gehört meteorologisch zum Winter?", "Januar", ["Mai", "August", "Oktober"]),
        ("Welches Fest liegt häufig im Winter?", "Weihnachten", ["Ostern", "Pfingsten", "Erntedank"]),
    ],
    "spring": [
        ("Welche Jahreszeit folgt direkt auf den Winter?", "Frühling", ["Sommer", "Herbst", "Nacht"]),
        ("Was machen viele Bäume im Frühling?", "Sie treiben neue Blätter aus", ["Sie verlieren alle Blätter", "Sie gefrieren", "Sie verdorren"]),
        ("Welcher Monat gehört meteorologisch zum Frühling?", "April", ["Juli", "November", "Dezember"]),
        ("Welches Tier wird oft mit Frühlingswiesen verbunden?", "Hase", ["Pinguin", "Kamel", "Wal"]),
    ],
    "summer": [
        ("Welche Jahreszeit hat in Europa häufig die höchsten Temperaturen?", "Sommer", ["Winter", "Frühling", "Herbst"]),
        ("Welcher Monat gehört meteorologisch zum Sommer?", "August", ["Februar", "November", "März"]),
        ("Was ist an Sommertagen oft länger?", "Tageslicht", ["Mondfinsternis", "Nebel", "Schneefall"]),
        ("Welche Aktivität ist typisch für heiße Sommertage?", "Schwimmen", ["Schlittenfahren", "Eisangeln", "Skispringen"]),
    ],
    "autumn": [
        ("In welcher Jahreszeit verfärben sich viele Laubblätter?", "Herbst", ["Winter", "Sommer", "Frühling"]),
        ("Welcher Monat gehört meteorologisch zum Herbst?", "Oktober", ["Januar", "April", "Juni"]),
        ("Welche Ernte ist in vielen Regionen im Herbst typisch?", "Apfelernte", ["Mangoernte in Europa", "Olivenblüte", "Reisernte in Skandinavien"]),
        ("Was passiert im Herbst häufiger als im Hochsommer?", "Laubfall", ["Polarnacht", "Monsun", "Gletscherschmelze auf Null"]),
    ],
}


def _question_prompt_key(question: tuple) -> str:
    return str(question[0]).strip().lower()


def _question_text_blob(question: tuple) -> str:
    prompt = str(question[0] if len(question) > 0 else "")
    answers = question[1] if len(question) > 1 else []
    options_txt = " ".join(str(a) for a in (answers or []))
    return f"{prompt} {options_txt}".lower()


def _question_topic(question: tuple) -> str:
    text = _question_text_blob(question)
    if is_math_question(question):
        return "mathematik"
    for topic, keywords in QUESTION_TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return topic
    return "allgemein"


def _current_season_key() -> str:
    month = datetime.now().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _seasonal_question_for_level(level_idx: int) -> tuple | None:
    # Roughly every 4th level gets a season-themed option.
    if level_idx % 4 != 1:
        return None
    season_key = _current_season_key()
    pool = SEASONAL_QUESTIONS.get(season_key) or SEASONAL_QUESTIONS["spring"]
    prompt, correct, wrongs = pool[(level_idx * 7) % len(pool)]
    return _make_question(prompt, correct, wrongs)


def _build_topic_plan(total: int) -> list[str]:
    topics = list(QUESTION_TOPIC_ROTATION)
    random.shuffle(topics)
    plan: list[str] = []
    while len(plan) < max(1, total):
        plan.extend(topics)
    return plan[:total]


def _get_question_profile(state: dict | None) -> dict | None:
    if not isinstance(state, dict):
        return None
    email = state.get("current_user_email")
    if not email:
        return None
    db = load_db()
    user = db.get("users", {}).get(email)
    if not user:
        return None
    ensure_question_profile_defaults(user)
    return user.get("question_profile")


def _score_question_candidate(
    candidate: tuple,
    target_topic: str,
    level_idx: int,
    recent_set: set[str],
    performance: dict,
) -> float:
    key = _question_prompt_key(candidate)
    topic = _question_topic(candidate)
    entry = performance.get(key, {}) if isinstance(performance, dict) else {}
    seen = max(0, int(entry.get("seen", 0)))
    wrong = max(0, int(entry.get("wrong", 0)))
    wrong_rate = (wrong / seen) if seen else 0.0
    review_boost = wrong_rate * 40.0 + min(wrong, 6) * 2.5
    topic_boost = 24.0 if topic == target_topic else (7.5 if topic == "allgemein" else 0.0)
    novelty_boost = 9.0 if seen == 0 else max(0.0, 4.0 - seen * 0.35)
    seasonal_boost = 10.0 if "jahreszeit" in _question_text_blob(candidate) else 0.0
    session_math_penalty = 4.0 if level_idx < 6 and is_math_question(candidate) else 0.0
    history_penalty = 100.0 if key in recent_set else 0.0
    return topic_boost + review_boost + novelty_boost + seasonal_boost - session_math_penalty - history_penalty


def create_game_questions(age: str, state: dict | None = None) -> list[tuple]:
    bank = build_level_question_bank(age)
    profile = _get_question_profile(state)
    recent_prompts = []
    performance = {}
    if profile:
        recent_prompts = list(profile.get("recent_prompts", []) or [])
        performance = dict(profile.get("performance", {}) or {})

    recent_set = {str(key).strip().lower() for key in recent_prompts[-QUESTION_HISTORY_LIMIT:]}
    topic_plan = _build_topic_plan(len(bank))
    questions: list[tuple] = []
    used_prompts: set[str] = set()

    for level_idx, level_questions in enumerate(bank):
        candidates = list(level_questions)
        non_math = [question for question in candidates if not is_math_question(question)]
        if len(non_math) >= 8:
            candidates = non_math
        seasonal = _seasonal_question_for_level(level_idx)
        if seasonal is not None:
            candidates.append(seasonal)

        candidates = [q for q in candidates if _question_prompt_key(q) not in used_prompts]
        if not candidates:
            raise RuntimeError("Nicht genug eindeutige Fragen fuer dieses Spiel.")

        unseen = [q for q in candidates if _question_prompt_key(q) not in recent_set]
        if unseen:
            candidates = unseen

        target_topic = topic_plan[level_idx]
        best_score = None
        chosen = None
        for question in candidates:
            score = _score_question_candidate(question, target_topic, level_idx, recent_set, performance) + random.random() * 0.8
            if best_score is None or score > best_score:
                best_score = score
                chosen = question

        if chosen is None:
            chosen = random.choice(candidates)
        prompt_key = _question_prompt_key(chosen)
        used_prompts.add(prompt_key)
        questions.append(chosen)

    return questions


def _remember_generated_questions(state: dict, questions: list[tuple]):
    email = state.get("current_user_email")
    if not email:
        return
    db = load_db()
    user = db.get("users", {}).get(email)
    if not user:
        return
    ensure_question_profile_defaults(user)
    profile = user["question_profile"]
    recent = list(profile.get("recent_prompts", []) or [])
    for question in questions:
        key = _question_prompt_key(question)
        if key in recent:
            recent.remove(key)
        recent.append(key)
    profile["recent_prompts"] = recent[-QUESTION_HISTORY_LIMIT:]
    save_db(db)


def record_question_result(state: dict, question: tuple, was_correct: bool):
    email = state.get("current_user_email")
    if not email:
        return
    db = load_db()
    user = db.get("users", {}).get(email)
    if not user:
        return
    ensure_question_profile_defaults(user)
    profile = user["question_profile"]
    key = _question_prompt_key(question)
    perf = profile.setdefault("performance", {})
    row = perf.setdefault(key, {"seen": 0, "correct": 0, "wrong": 0, "last_seen": ""})
    row["seen"] = max(0, int(row.get("seen", 0))) + 1
    if was_correct:
        row["correct"] = max(0, int(row.get("correct", 0))) + 1
    else:
        row["wrong"] = max(0, int(row.get("wrong", 0))) + 1
    row["last_seen"] = datetime.now().date().isoformat()

    # Keep profile compact.
    if len(perf) > QUESTION_PERFORMANCE_LIMIT:
        sorted_items = sorted(
            perf.items(),
            key=lambda item: str(item[1].get("last_seen", "")),
            reverse=True,
        )[:QUESTION_PERFORMANCE_LIMIT]
        profile["performance"] = dict(sorted_items)
    save_db(db)


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


# ---------- Avatar ----------
def _avatar_piece_icon(user: dict, slot: str) -> str:
    catalog = _avatar_catalog_by_id()
    ensure_avatar_defaults(user)
    item_id = user["avatar"]["equipped"].get(slot, AVATAR_BASE_EQUIPPED[slot])
    item = catalog.get(item_id) or catalog.get(AVATAR_BASE_EQUIPPED[slot]) or {}
    return str(item.get("icon", "•"))


def _avatar_preview_text(user: dict, theme: dict) -> str:
    ensure_avatar_defaults(user)
    gender = user["avatar"].get("gender", "diverse")
    theme_key = _theme_key_from_theme(theme) or "classic"
    scene = avatar_scene(theme_key)
    gender_label = {"male": "Männlich", "female": "Weiblich", "diverse": "Divers"}.get(gender, "Divers")
    return f"Avatar bald verfügbar\n{scene}\nTyp: {gender_label}"


def _avatar_piece_color(item_id: str, theme: dict, fallback: str) -> str:
    item_id = str(item_id or "")
    item_id_l = item_id.lower()
    if "royal" in item_id_l or "crown" in item_id_l or "chain" in item_id_l:
        return "#F2C94C"
    if "neon" in item_id_l or "glasses" in item_id_l:
        return "#22D3EE"
    if "ocean" in item_id_l or "diver" in item_id_l:
        return "#38BDF8"
    if "dark" in item_id_l:
        return "#334155"
    return fallback


def _avatar_outfit_style(user: dict, theme: dict) -> dict:
    ensure_avatar_defaults(user)
    equipped = user.get("avatar", {}).get("equipped", {})
    top_id = str(equipped.get("top", "top_basic"))
    pants_id = str(equipped.get("pants", "pants_basic"))
    shoes_id = str(equipped.get("shoes", "shoes_basic"))
    acc_id = str(equipped.get("accessory", "acc_none"))
    gender = user.get("avatar", {}).get("gender", "male")

    top_palette = {
        "top_basic": {"main": "#F3F4F6", "line": "#CBD5E1", "sleeve": "#E5E7EB", "glow": None},
        "top_neon": {"main": "#0F172A", "line": "#D946EF", "sleeve": "#111827", "glow": "#22D3EE"},
        "top_royal": {"main": "#2B1B0E", "line": "#F2C94C", "sleeve": "#3B2A13", "glow": "#FFD700"},
        "top_ocean": {"main": "#0B2942", "line": "#38BDF8", "sleeve": "#123E61", "glow": "#22D3EE"},
        "top_hacker": {"main": "#06140B", "line": "#22C55E", "sleeve": "#082313", "glow": "#86EFAC"},
        "top_gold_blazer": {"main": "#3A2608", "line": "#FACC15", "sleeve": "#4A300A", "glow": "#FDE68A"},
    }
    pants_palette = {
        "pants_basic": {"main": "#1E3A8A", "line": "#2563EB"},
        "pants_dark": {"main": "#1F2937", "line": "#334155"},
        "pants_neon": {"main": "#0B1020", "line": "#22D3EE"},
        "pants_royal": {"main": "#3B2A13", "line": "#F2C94C"},
        "pants_ocean": {"main": "#0F3B57", "line": "#38BDF8"},
    }
    shoes_palette = {
        "shoes_basic": {"main": "#111827", "line": "#6B7280"},
        "shoes_lux": {"main": "#2E1A0E", "line": "#F59E0B"},
        "shoes_ocean": {"main": "#0B2942", "line": "#38BDF8"},
        "shoes_neon": {"main": "#090E1F", "line": "#22D3EE"},
    }
    # fallback colors adapt to current theme
    top = top_palette.get(top_id, {
        "main": theme.get("question_bg", "#1F2937"),
        "line": theme.get("accent", "#22D3EE"),
        "sleeve": theme.get("panel", "#0F172A"),
        "glow": theme.get("accent_2", "#38BDF8"),
    })
    pants = pants_palette.get(pants_id, {"main": "#1F2937", "line": theme.get("accent", "#22D3EE")})
    shoes = shoes_palette.get(shoes_id, {"main": "#111827", "line": theme.get("accent", "#22D3EE")})

    if gender == "female":
        skin = "#F2C9A5"
        hair = "#3F2A1F"
    elif gender == "diverse":
        skin = "#E3B88A"
        hair = "#2C3342"
    else:
        skin = "#E7BE9A"
        hair = "#2E251C"

    return {
        "gender": gender,
        "skin": skin,
        "hair": hair,
        "top": top,
        "pants": pants,
        "shoes": shoes,
        "accessory": acc_id,
    }


_AVATAR_COMPOSED_CACHE: dict[tuple[str, str, str, str, str, str, float], bytes] = {}


def _avatar_hex_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = (value or "#FFFFFF").strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        return (255, 255, 255, alpha)
    try:
        return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), max(0, min(255, alpha)))
    except Exception:
        return (255, 255, 255, alpha)


def _avatar_tint(c: tuple[int, int, int, int], mul: float = 1.0, alpha: int | None = None) -> tuple[int, int, int, int]:
    r, g, b, a = c
    return (
        max(0, min(255, int(r * mul))),
        max(0, min(255, int(g * mul))),
        max(0, min(255, int(b * mul))),
        a if alpha is None else max(0, min(255, alpha)),
    )


def _avatar_open_base_image(base_name: str) -> Image.Image | None:
    if Image is None:
        return None
    src = _avatar_image_source(base_name)
    try:
        if isinstance(src, (bytes, bytearray)):
            return Image.open(io.BytesIO(src)).convert("RGBA")
        if isinstance(src, str):
            path_candidates = [os.path.join("assets", src), src]
            for p in path_candidates:
                if os.path.exists(p):
                    return Image.open(p).convert("RGBA")
    except Exception:
        return None
    return None


def _avatar_compose_image(user: dict, theme: dict, canvas_w: int = 512, canvas_h: int = 768) -> bytes | None:
    if Image is None or ImageDraw is None:
        return None
    ensure_avatar_defaults(user)
    style = _avatar_outfit_style(user, theme)
    equipped = user.get("avatar", {}).get("equipped", {})
    gender = style["gender"]
    top_id = str(equipped.get("top", "top_basic"))
    pants_id = str(equipped.get("pants", "pants_basic"))
    shoes_id = str(equipped.get("shoes", "shoes_basic"))
    acc_id = str(equipped.get("accessory", "acc_none"))
    canvas_w, canvas_h = 328, 492
    base_name = _resolve_avatar_base_image(gender)
    if not base_name:
        return None
    try:
        base_path = os.path.join("assets", base_name) if not os.path.isabs(base_name) else base_name
        mtime = os.path.getmtime(base_path) if os.path.exists(base_path) else 0.0
    except Exception:
        mtime = 0.0
    cache_key = (gender, top_id, pants_id, shoes_id, acc_id, str(_theme_key_from_theme(theme) or "classic"), float(mtime))
    cached = _AVATAR_COMPOSED_CACHE.get(cache_key)
    if cached:
        return cached

    base = _avatar_open_base_image(base_name)
    if base is None:
        return None
    base = base.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    canvas.alpha_composite(base)
    draw = ImageDraw.Draw(canvas, "RGBA")

    def rr(box, radius, fill, outline=None, width=1):
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

    def ellipse(box, fill, outline=None, width=1):
        draw.ellipse(box, fill=fill, outline=outline, width=width)

    def line(points, fill, width=1):
        draw.line(points, fill=fill, width=width, joint="curve")

    def poly(points, fill, outline=None):
        draw.polygon(points, fill=fill, outline=outline)

    is_female = gender == "female"
    cx = canvas_w // 2
    skin = _avatar_hex_rgba(style["skin"], 255)
    top_main = _avatar_hex_rgba(style["top"]["main"], 255)
    top_line = _avatar_hex_rgba(style["top"]["line"], 255)
    top_sleeve = _avatar_hex_rgba(style["top"]["sleeve"], 255)
    pants_main = _avatar_hex_rgba(style["pants"]["main"], 255)
    pants_line = _avatar_hex_rgba(style["pants"]["line"], 255)
    shoes_main = _avatar_hex_rgba(style["shoes"]["main"], 255)
    shoes_line = _avatar_hex_rgba(style["shoes"]["line"], 255)

    if is_female:
        shoulder = (96, 105, 232, 124)
        torso = [(108, 103), (220, 103), (218, 244), (110, 244)]
        waist = (105, 226, 223, 252)
        left_sleeve = [(94, 109), (112, 107), (105, 174), (88, 172)]
        right_sleeve = [(216, 107), (234, 109), (240, 172), (223, 174)]
        pants_left = [(109, 236), (157, 236), (151, 482), (96, 482)]
        pants_right = [(171, 236), (219, 236), (232, 482), (177, 482)]
        shoe_left = (92, 462, 153, 491)
        shoe_right = (175, 462, 236, 491)
        face = (104, 22, 224, 110)
    else:
        shoulder = (88, 97, 240, 120)
        torso = [(102, 95), (226, 95), (228, 258), (100, 258)]
        waist = (100, 240, 228, 270)
        left_sleeve = [(86, 102), (106, 100), (99, 178), (80, 176)]
        right_sleeve = [(222, 100), (242, 102), (248, 176), (229, 178)]
        pants_left = [(102, 240), (157, 240), (151, 486), (90, 486)]
        pants_right = [(171, 240), (226, 240), (238, 486), (177, 486)]
        shoe_left = (84, 462, 153, 491)
        shoe_right = (175, 462, 244, 491)
        face = (100, 18, 228, 108)

    if top_id in ("top_neon", "top_hacker"):
        poly(torso, _avatar_tint(top_main, 0.85))
        poly([(torso[0][0], torso[0][1]), (cx - 12, torso[0][1] + 8), (cx - 8, torso[2][1]), (torso[3][0], torso[3][1])], top_main)
        poly([(cx + 12, torso[1][1] + 8), (torso[1][0], torso[1][1]), (torso[2][0], torso[2][1]), (cx + 8, torso[2][1])], top_main)
        line([(cx, torso[0][1] + 18), (cx, torso[2][1] - 10)], top_line, 4)
        line([(torso[0][0] + 18, torso[0][1] + 18), (torso[3][0] + 8, torso[3][1] - 18)], top_line, 3)
        line([(torso[1][0] - 18, torso[1][1] + 18), (torso[2][0] - 8, torso[2][1] - 18)], _avatar_hex_rgba(style["top"].get("glow") or "#22D3EE"), 3)
    elif top_id in ("top_royal", "top_gold_blazer"):
        poly(torso, top_main)
        poly([(torso[0][0], torso[0][1]), (cx - 5, torso[0][1] + 45), (cx - 10, torso[2][1]), (torso[3][0], torso[3][1])], _avatar_tint(top_main, 0.82))
        poly([(torso[1][0], torso[1][1]), (cx + 5, torso[1][1] + 45), (cx + 10, torso[2][1]), (torso[2][0], torso[2][1])], _avatar_tint(top_main, 0.82))
        line([(torso[0][0] + 14, torso[0][1] + 18), (torso[1][0] - 14, torso[1][1] + 18)], top_line, 3)
        line([(cx, torso[0][1] + 44), (cx, torso[2][1] - 14)], top_line, 2)
    elif top_id == "top_ocean":
        poly(torso, top_main)
        rr((torso[0][0] + 18, torso[0][1] + 16, torso[1][0] - 18, torso[0][1] + 72), 22, _avatar_tint(top_main, 1.15), top_line, 2)
        for y in (272, 304, 336):
            line([(torso[0][0] + 20, y), (torso[1][0] - 20, y)], _avatar_tint(top_line, 1.2, 150), 2)
    else:
        poly(torso, top_main)
        rr((torso[0][0] + 24, torso[0][1] + 12, torso[1][0] - 24, torso[0][1] + 62), 26, _avatar_tint(top_main, 1.12), None)
        for y in (266, 306, 346):
            if y < torso[2][1] - 4:
                line([(torso[0][0] + 26, y), (torso[1][0] - 26, y)], _avatar_tint(top_line, 1.0, 95), 2)

    long_sleeve = top_id in ("top_neon", "top_hacker", "top_royal", "top_ocean", "top_gold_blazer")
    if long_sleeve:
        left_sleeve = [(left_sleeve[0][0], left_sleeve[0][1]), (left_sleeve[1][0], left_sleeve[1][1]), (left_sleeve[2][0] - 3, left_sleeve[2][1] + 92), (left_sleeve[3][0] + 4, left_sleeve[3][1] + 92)]
        right_sleeve = [(right_sleeve[0][0], right_sleeve[0][1]), (right_sleeve[1][0], right_sleeve[1][1]), (right_sleeve[2][0] - 4, right_sleeve[2][1] + 92), (right_sleeve[3][0] + 3, right_sleeve[3][1] + 92)]
    poly(left_sleeve, top_sleeve, _avatar_tint(top_line, 1.0, 180))
    poly(right_sleeve, top_sleeve, _avatar_tint(top_line, 1.0, 180))
    line([(left_sleeve[0][0] + 8, left_sleeve[0][1] + 10), (left_sleeve[2][0] + 4, left_sleeve[2][1] - 10)], _avatar_tint(top_line, 1.05, 145), 2)
    line([(right_sleeve[1][0] - 8, right_sleeve[1][1] + 10), (right_sleeve[2][0] - 4, right_sleeve[2][1] - 10)], _avatar_tint(top_line, 1.05, 145), 2)
    rr(waist, 14, _avatar_tint(top_main, 0.82), _avatar_tint(top_line, 0.9), 2)

    left_leg = pants_left
    right_leg = pants_right
    poly(left_leg, pants_main, pants_line)
    poly(right_leg, pants_main, pants_line)
    rr((left_leg[0][0] - 3, left_leg[0][1] - 10, right_leg[1][0] + 3, left_leg[0][1] + 24), 12, _avatar_tint(pants_main, 0.92), pants_line, 2)
    line([(left_leg[1][0], left_leg[0][1] + 16), (left_leg[2][0], left_leg[2][1] - 24)], _avatar_tint(pants_line, 1.0, 140), 2)
    line([(right_leg[0][0], right_leg[0][1] + 16), (right_leg[3][0], right_leg[3][1] - 24)], _avatar_tint(pants_line, 1.0, 140), 2)
    if pants_id in ("pants_neon", "pants_ocean"):
        line([(left_leg[0][0] + 12, left_leg[0][1] + 34), (left_leg[3][0] + 10, left_leg[3][1] - 26)], pants_line, 3)
        line([(right_leg[1][0] - 12, right_leg[1][1] + 34), (right_leg[2][0] - 10, right_leg[2][1] - 26)], pants_line, 3)

    rr(shoe_left, 15, shoes_main, shoes_line, 3)
    rr(shoe_right, 15, shoes_main, shoes_line, 3)
    line([(shoe_left[0] + 12, shoe_left[1] + 11), (shoe_left[2] - 12, shoe_left[1] + 11)], _avatar_tint(shoes_line, 1.18), 2)
    line([(shoe_right[0] + 12, shoe_right[1] + 11), (shoe_right[2] - 12, shoe_right[1] + 11)], _avatar_tint(shoes_line, 1.18), 2)

    if acc_id == "acc_glasses":
        y = face[1] + 48
        rr((face[0] + 28, y, face[0] + 58, y + 16), 7, (0, 0, 0, 80), (10, 15, 25, 255), 2)
        rr((face[2] - 58, y, face[2] - 28, y + 16), 7, (0, 0, 0, 80), (10, 15, 25, 255), 2)
        line([(face[0] + 58, y + 8), (face[2] - 58, y + 8)], (10, 15, 25, 255), 2)
    elif acc_id == "acc_chain":
        draw.arc((cx - 32, torso[0][1] + 12, cx + 32, torso[0][1] + 62), 20, 160, fill=(242, 201, 76, 255), width=4)
    elif acc_id == "acc_crown":
        cy = max(4, face[1] - 16)
        poly([(cx - 42, cy + 30), (cx - 26, cy + 2), (cx - 8, cy + 30), (cx + 10, cy), (cx + 28, cy + 30), (cx + 42, cy + 30), (cx + 38, cy + 48), (cx - 38, cy + 48)], (242, 201, 76, 245), (180, 83, 9, 255))
    elif acc_id == "acc_headset":
        draw.arc((face[0] + 4, face[1] + 12, face[2] - 4, face[3] + 28), 190, 350, fill=(16, 24, 39, 255), width=5)
        rr((face[0] - 2, face[1] + 54, face[0] + 18, face[1] + 90), 7, (16, 24, 39, 255), top_line, 2)
        rr((face[2] - 18, face[1] + 54, face[2] + 2, face[1] + 90), 7, (16, 24, 39, 255), top_line, 2)

    # A soft studio pass keeps the generated character from looking flat.
    highlight = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight, "RGBA")
    hd.ellipse((78, 42, 218, 420), fill=(255, 255, 255, 18))
    hd.ellipse((170, 120, 290, 480), fill=(0, 0, 0, 12))
    canvas = Image.alpha_composite(canvas, highlight.filter(ImageFilter.GaussianBlur(radius=8)))

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    data = out.getvalue()
    _AVATAR_COMPOSED_CACHE[cache_key] = data
    return data


def build_avatar_figure(user: dict, theme: dict, size: int = 110, angle_deg: float = 0.0) -> ft.Control:
    w = int(max(84, size))
    h = int(w * 1.5)
    return ft.Container(
        width=w,
        height=h,
        border_radius=14,
        padding=10,
        alignment=ft.Alignment(0, 0),
        bgcolor="#00000055",
        border=ft.border.Border.all(1.5, theme.get("border", "#60A5FA")),
        content=ft.Column(
            [
                ft.Icon(ft.Icons.PERSON_OUTLINE, color=theme.get("accent", "#60A5FA"), size=max(24, int(w * 0.28))),
                ft.Text("Avatar", color=theme_txt(theme, "primary"), size=max(11, int(w * 0.11)), weight="bold"),
                ft.Text("bald verfügbar", color=theme_txt(theme, "secondary"), size=max(10, int(w * 0.095))),
            ],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
        ),
    )


def show_avatar_wardrobe(page: ft.Page, state: dict, back_to_main: bool = True):
    db = load_db()
    email = state.get("current_user_email")
    if not email or email not in db.get("users", {}):
        show_login_view(page, state)
        return
    user = db["users"][email]
    ensure_user_settings(db, email)
    ensure_avatar_defaults(user)
    save_db(db)
    theme = get_theme(state)
    ui = theme_ui_palette(theme)
    slot_state = {"value": "top"}
    status = ft.Text("", size=12, color=theme_txt(theme, "secondary"))

    def buy_item(item: dict, persist: bool = True):
        wallet = int(user.get("stats", {}).get("wallet_balance", 0))
        if item["id"] in user["avatar"]["owned_items"]:
            return
        if wallet < int(item.get("price", 0)):
            status.value = "Nicht genug Guthaben für diesen Avatar-Item."
            status.color = theme.get("danger", "#EF4444")
            return
        user["stats"]["wallet_balance"] = wallet - int(item.get("price", 0))
        user["avatar"]["owned_items"].append(item["id"])
        status.value = f"Gekauft: {item['name']}"
        status.color = theme.get("success", "#22C55E")
        if persist:
            save_db(db)

    def equip_item(item: dict, persist: bool = True):
        slot = item["slot"]
        if item["id"] not in user["avatar"]["owned_items"]:
            buy_item(item, persist=False)
            if item["id"] not in user["avatar"]["owned_items"]:
                return
        user["avatar"]["equipped"][slot] = item["id"]
        status.value = f"Ausgerüstet: {item['name']}"
        status.color = theme.get("success", "#22C55E")
        if persist:
            save_db(db)

    wallet_text = ft.Text("", size=16, weight="bold", color=theme["gold"])
    preview_text = ft.Text("", size=13, color=ui["text"], text_align=ft.TextAlign.CENTER)
    preview_figure = ft.Container(alignment=ft.Alignment(0, 0))
    gender_row = ft.Row(spacing=8, alignment=ft.MainAxisAlignment.CENTER)
    item_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    slot_dropdown = ft.Dropdown(
        label="Kategorie",
        value=slot_state["value"],
        width=220,
        options=[
            ft.dropdown.Option("top", "Oberteil"),
            ft.dropdown.Option("pants", "Hose"),
            ft.dropdown.Option("shoes", "Schuhe"),
            ft.dropdown.Option("accessory", "Accessoire"),
        ],
    )

    def render():
        ensure_avatar_defaults(user)
        wallet_text.value = f"Guthaben: {int(user.get('stats', {}).get('wallet_balance', 0))} €"
        preview_text.value = _avatar_preview_text(user, theme)
        preview_figure.content = build_avatar_figure(user, theme, size=260)

        gender_buttons = []
        for g_key, g_label in AVATAR_GENDER_OPTIONS:
            selected = user["avatar"].get("gender") == g_key
            gender_buttons.append(
                _theme_action_button(
                    g_label,
                    theme,
                    lambda e, g=g_key: set_gender(g),
                    width=120,
                    bg=theme.get("accent", "#2563EB") if selected else ui["card_bg"],
                )
            )
        gender_row.controls = gender_buttons

        slot = slot_state["value"]
        cards = []
        for item in [it for it in SHOP_CATALOG.get("avatar_items", []) if it.get("slot") == slot]:
            owned = item["id"] in user["avatar"]["owned_items"]
            equipped = user["avatar"]["equipped"].get(slot) == item["id"]
            if equipped:
                action = ft.ElevatedButton("Ausgerüstet", disabled=True)
            elif owned:
                action = ft.ElevatedButton("Anziehen", on_click=lambda e, itm=item: (equip_item(itm), render(), page.update()))
            else:
                action = ft.ElevatedButton(f"Kaufen ({item['price']} €)", on_click=lambda e, itm=item: (buy_item(itm), render(), page.update()))

            cards.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(item.get("icon", "•"), size=24),
                            ft.Column(
                                [
                                    ft.Text(item["name"], size=14, weight="bold", color=ui["text"]),
                                    ft.Text("Besitzt du" if owned else f"Preis: {item['price']} €", size=11, color=theme_txt(theme, "secondary")),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            action,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ui["card_bg"],
                    border_radius=12,
                    padding=10,
                    border=ft.border.Border.all(1.5, ui["card_border"]),
                )
            )
        item_list.controls = cards

    def set_gender(gender: str):
        user["avatar"]["gender"] = gender
        save_db(db)
        render()
        page.update()

    def on_slot_change(e):
        slot_state["value"] = e.control.value or "top"
        render()
        page.update()

    slot_dropdown.on_select = on_slot_change
    render()

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000095"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(12, 12, 12, 12),
                        content=ft.Container(
                            width=min(1120, int(_page_size(page)[0] - 20)),
                            border_radius=16,
                            bgcolor="#060d09f0",
                            border=ft.border.Border.all(2, ui["card_border"]),
                            padding=18,
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text("Avatar-Garderobe", size=26, weight="bold", color=ui["text"], expand=True),
                                            wallet_text,
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Container(
                                                width=380,
                                                border_radius=14,
                                                border=ft.border.Border.all(1.5, ui["card_border"]),
                                                bgcolor=ui["card_bg"],
                                                padding=ft.Padding(14, 14, 14, 14),
                                                content=ft.Column(
                                                    [
                                                        ft.Text("Garderobe", size=20, weight="bold", color=ui["text"]),
                                                        gender_row,
                                                        ft.Row([slot_dropdown], alignment=ft.MainAxisAlignment.START),
                                                        item_list,
                                                    ],
                                                    spacing=10,
                                                    expand=True,
                                                ),
                                            ),
                                            ft.Container(width=16),
                                            ft.Container(
                                                expand=True,
                                                border_radius=14,
                                                border=ft.border.Border.all(1.5, ui["card_border"]),
                                                bgcolor=ui["card_bg"],
                                                padding=ft.Padding(16, 16, 16, 16),
                                                content=ft.Column(
                                                    [
                                                        ft.Text("Avatar-Vorschau", size=20, weight="bold", color=ui["text"], text_align=ft.TextAlign.CENTER),
                                                        ft.Container(
                                                            content=preview_figure,
                                                            expand=True,
                                                            alignment=ft.Alignment(0, 0),
                                                        ),
                                                        preview_text,
                                                    ],
                                                    spacing=8,
                                                    expand=True,
                                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                ),
                                            ),
                                        ],
                                        expand=True,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        vertical_alignment=ft.CrossAxisAlignment.START,
                                    ),
                                    status,
                                    ft.Row(
                                        [
                                            _theme_action_button(
                                                "Zurück",
                                                theme,
                                                lambda e: open_main_menu(e.page, state) if back_to_main else show_shop_screen(e.page, state),
                                                width=180,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                ],
                                spacing=12,
                                scroll=ft.ScrollMode.AUTO,
                            ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


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
    menu_card_bg = theme.get("panel", "#0A150F")
    menu_card_border = theme.get("border", "#10B981")
    menu_card_glow = theme.get("accent_2", menu_card_border)
    menu_card_icon = theme.get("accent", "#10B981")
    page_w, _page_h = _page_size(page)
    is_mobile = page_w < 900
    compact = page_w < 1180
    title_size = 32 if page_w < 760 else (36 if compact else 38)
    subtitle_size = 12 if compact else 13
    hero_width = min(600, max(300, int(page_w - 24)))
    avatar_size = 68 if compact else 86
    tile_w = max(148, int((page_w - 52) / 2)) if is_mobile else (225 if compact else 265)
    small_card_h = 88 if compact else 95
    tall_card_h = 188 if compact else 205

    def on_logout(e):
        state["current_user_email"] = None
        state["current_user_uid"] = None
        page.run_task(clear_remembered_login, e.page)
        _go_home(e.page, state)

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
                size=(22 if compact else 24) if is_tall else (18 if compact else 20)
            ),
            width=(44 if compact else 48) if is_tall else (38 if compact else 42),
            height=(44 if compact else 48) if is_tall else (38 if compact else 42),
            shape=ft.BoxShape.CIRCLE,
            bgcolor=None,
            border=ft.border.Border.all(1, accent_color),
            alignment=ft.Alignment(0, 0)
        )
        
        if is_tall:
            card_content = ft.Column([
                icon_ctrl,
                ft.Container(expand=True),
                ft.Row([
                    ft.Column([
                        ft.Text(title, size=20 if compact else 22, weight="bold", color="white"),
                        ft.Text(desc, size=12 if compact else 13, color="#8B9A90")
                    ], spacing=2, tight=True),
                    ft.Container(expand=True),
                    ft.Text("▶", color="white", size=20 if compact else 22)
                ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)
            
            if extra_content:
                card_content.controls.insert(2, extra_content)
        else:
            card_content = ft.Row([
                icon_ctrl,
                ft.Container(width=10),
                ft.Column([
                    ft.Text(title, size=15 if compact else 16, weight="bold", color="white"),
                    ft.Text(desc, size=10 if compact else 11, color="#8F949D" if not locked else "#E06B6B")
                ], spacing=2, tight=True, expand=True),
                ft.Text("▶" if not locked else "🔒", color="#4A505A" if locked else "white", size=16 if compact else 18)
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
            
        # The main card Container
        card = ft.Container(
            content=card_content,
            bgcolor=bg_hex,
            width=width,
            height=height,
            border_radius=18 if is_tall else 16,
            padding=ft.Padding(20, 16, 20, 16) if (is_tall and compact) else (ft.Padding(24, 20, 24, 20) if is_tall else ft.Padding(16, 12, 16, 12) if compact else ft.Padding(18, 14, 18, 14)),
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
                e.control.border = ft.border.Border.all(2.2, theme.get("accent_2", accent_color))
                e.control.shadow = ft.BoxShadow(
                    blur_radius=30,
                    color=f"#50{(theme.get('accent_2', glow_hex))[1:]}",
                    spread_radius=-2
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

    background_media = _build_looping_menu_background(page, theme)

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
    if logged_in and email in db.get("users", {}):
        try:
            user_info = db["users"][email]
            ensure_avatar_defaults(user_info)
            avatar_box = ft.Container(
                content=ft.Column(
                    [
                        build_avatar_figure(user_info, theme, size=avatar_size),
                        ft.Text(avatar_scene(_theme_key_from_theme(theme) or "classic"), size=10, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                        ft.Text(f"Hallo, {username}", size=12, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#07110DCC",
                border=ft.border.Border.all(1.8, menu_card_border),
                border_radius=14,
                padding=ft.Padding(10, 8, 10, 8),
                on_click=lambda e: show_avatar_wardrobe(e.page, state, back_to_main=True),
                shadow=ft.BoxShadow(blur_radius=16, color="#44000000"),
                tooltip="Avatar öffnen",
            )
            header_actions = ft.Row([avatar_box], spacing=8)
        except Exception:
            header_actions = ft.Row([])
    else:
        header_actions = ft.Row([])

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
                border=ft.border.Border.all(2, theme.get("accent", "#10B981")),
                alignment=ft.Alignment(0, 0),
                shadow=ft.BoxShadow(
                    blur_radius=15,
                    color=theme.get("accent", "#10B981"),
                    spread_radius=-4
                )
            ),
            ft.Container(height=8),
            # Title
            ft.Text("WER WIRD", size=20 if compact else 24, weight="bold", color="white"),
            ft.Text("MILLIONÄR?", size=title_size, weight="w900", color=theme.get("accent", "#10B981"), text_align=ft.TextAlign.CENTER),
            ft.Container(height=4),
            # Subtitle
            ft.Text("Teste dein Wissen. Werde Millionär.", size=subtitle_size, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        width=hero_width,
        padding=ft.Padding(26, 22, 26, 22) if compact else ft.Padding(32, 28, 32, 28),
        border_radius=24,
        bgcolor="#070A08",
        border=ft.border.Border.all(1.5, theme.get("border", "#0E2919")),
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
            ft.Text(username, color=theme.get("accent", "#10B981"), size=13, weight="bold")
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
        color_hex=menu_card_icon,
        bg_hex=menu_card_bg,
        glow_hex=menu_card_glow,
        on_click=(lambda e: show_game_start_menu(e.page, state, saved_game)) if saved_game else (lambda e: start_new_game(e.page, state)),
        width=tile_w if is_mobile else (225 if compact else 265),
        height=tall_card_h,
        is_tall=True
    )

    card_settings = create_hover_card(
        title="Einstellungen",
        desc="Anpassen & konfigurieren",
        icon_name="⚙️",
        color_hex=menu_card_icon,
        bg_hex=menu_card_bg,
        glow_hex=menu_card_glow,
        on_click=lambda e: show_settings_view(e.page, state),
        width=tile_w,
        height=small_card_h
    )
    
    if logged_in:
        card_shop = create_hover_card(
            title="Shop",
            desc="Power-Ups & Extras",
            icon_name="🛒",
            color_hex=menu_card_icon,
            bg_hex=menu_card_bg,
            glow_hex=menu_card_glow,
            on_click=lambda e: e.page.go("/shop"),
            width=tile_w,
            height=small_card_h
        )
    else:
        card_shop = create_hover_card(
            title="Anmelden",
            desc="Profil verbinden",
            icon_name="🔑",
            color_hex=menu_card_icon,
            bg_hex=menu_card_bg,
            glow_hex=menu_card_glow,
            on_click=lambda e: show_login_view(e.page, state),
            width=tile_w,
            height=small_card_h
        )
        
    card_daily = create_hover_card(
        title="Daily Challenge",
        desc="Jeden Tag neu" if logged_in else "Anmelden zum Spielen",
        icon_name="📅",
        color_hex=menu_card_icon,
        bg_hex=menu_card_bg,
        glow_hex=menu_card_glow,
        on_click=lambda e: e.page.go("/daily") if logged_in else show_login_view(e.page, state),
        locked=not logged_in,
        width=tile_w,
        height=small_card_h
    )
    
    card_achievements = create_hover_card(
        title="Erfolge",
        desc="Deine Meilensteine" if logged_in else "Anmelden zum Freischalten",
        icon_name="🏆",
        color_hex=menu_card_icon,
        bg_hex=menu_card_bg,
        glow_hex=menu_card_glow,
        on_click=lambda e: e.page.go("/achievements") if logged_in else show_login_view(e.page, state),
        locked=not logged_in,
        width=tile_w,
        height=small_card_h
    )

    if is_mobile:
        grid_row = ft.Column([
            card_start,
            ft.Row([card_settings, card_daily], spacing=12, alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([card_shop, card_achievements], spacing=12, alignment=ft.MainAxisAlignment.CENTER),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
    else:
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
            ft.Text("🏆", color=theme.get("accent", "#10B981"), size=18),
            ft.VerticalDivider(width=1, color="#1F2A22", thickness=1),
            ft.Text("Wissen ist Macht.", color="white", size=12, weight="w500"),
            ft.Text("Bist du bereit?", color=theme.get("accent", "#10B981"), size=12, weight="bold"),
            ft.VerticalDivider(width=1, color="#1F2A22", thickness=1),
            ft.Container(width=40, height=2, bgcolor=theme.get("accent", "#10B981"), opacity=0.3)
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
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14, scroll=ft.ScrollMode.AUTO)
    
    stack_controls = []
    if background_media:
        stack_controls.extend([
            background_media,
            ft.Container(expand=True, bgcolor="#020403", opacity=0.62),
        ])
    stack_controls.extend([
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
        # Centered main content
        ft.Container(
            content=main_column,
            alignment=ft.Alignment(0, 0),
            expand=True
        ),
        # Header action buttons (last layer so it's always clickable)
        ft.Container(
            content=header_actions,
            top=20,
            right=20,
            alignment=ft.Alignment(1, -1),
        ),
        _settings_corner_overlay(page, state),
        ft.Container(
            content=ft.Container(
                content=ft.TextButton(
                    "← Spielauswahl",
                    on_click=lambda e: e.page.go("/"),
                    style=ft.ButtonStyle(color="white"),
                ),
                bgcolor="#0000008f",
                border_radius=14,
                padding=ft.Padding(6, 2, 6, 2),
            ),
            top=18,
            left=66,
            alignment=ft.Alignment(-1, -1),
        ),
    ])
    stack = ft.Stack(stack_controls, expand=True)
    
    return ft.Container(
        expand=True,
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
    btn = ft.Container(
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
        border=ft.border.Border.all(1.6, "#A7F3D0"),
    )
    def on_hover(e):
        hovering = e.data == "true"
        e.control.shadow = ft.BoxShadow(blur_radius=28, color="#88FFFFFF", spread_radius=2) if hovering else ft.BoxShadow(blur_radius=10, color="#33000000")
        e.control.border = ft.border.Border.all(2.8, "#FDE68A") if hovering else ft.border.Border.all(1.6, "#A7F3D0")
        e.control.scale = 1.04 if hovering else 1.0
        e.control.update()
    btn.on_hover = on_hover
    btn.animate_scale = ft.Animation(140, ft.AnimationCurve.EASE_OUT)
    return btn


def show_game_start_menu(page: ft.Page, state: dict, saved: dict | None = None):
    """Spiel starten: fortsetzen, Standard-Quiz oder eigene Quizzes."""
    _set_resize_view(state, show_game_start_menu, saved)
    theme = get_theme(state)
    ui = theme_ui_palette(theme)
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
                ui["card_bg"],
            ),
        ])

    buttons.append(
        _game_menu_button(
            "🎲  Neues Spiel starten",
            lambda e: show_age_selection(e.page, state),
            ui["card_bg"],
        )
    )
    if logged_in:
        buttons.append(
            _game_menu_button(
                "✏️  Eigene Spiele erstellen",
                lambda e: show_custom_quiz_hub(e.page, state),
                ui["card_bg"],
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000095"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Spiel starten", size=30, weight="bold", color=ui["text"], text_align="center"),
                            ft.Container(height=8),
                            ft.Container(
                                content=ft.Column(buttons, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                bgcolor=ui["card_bg"],
                                border_radius=16,
                                padding=24,
                                border=ft.border.Border.all(2, ui["card_border"]),
                                width=400,
                            ),
                            ft.TextButton(
                                "Zurück",
                                on_click=lambda e: open_main_menu(e.page, state),
                                style=ft.ButtonStyle(color=ui["text"]),
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=14),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_custom_quiz_hub(page: ft.Page, state: dict):
    theme = get_theme(state)
    ui = theme_ui_palette(theme)
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000095"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Eigene Spiele", size=28, weight="bold", color=ui["text"], text_align="center"),
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
                                ui["card_bg"],
                            ),
                            ft.TextButton(
                                "← Zurück",
                                on_click=lambda e: show_game_start_menu(e.page, state, get_saved_game_for_state(state)),
                                style=ft.ButtonStyle(color=ui["text"]),
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=10),
                    ),
                ],
                expand=True,
            ),
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

    time_sec_dropdown.on_select = on_time_sec_change

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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000096"),
                    ft.Container(
                        expand=True,
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
                    ),
                ],
                expand=True,
            ),
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000096"),
                    ft.Container(
                        expand=True,
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
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


# ---------- Points quiz ----------
def new_points_quiz_id() -> str:
    return f"points_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"


POINTS_QUIZ_MEDIA_DIR = os.path.join("assets", "points_quiz_media")
POINTS_QUIZ_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
POINTS_QUIZ_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS = sorted(POINTS_QUIZ_IMAGE_EXTENSIONS | POINTS_QUIZ_VIDEO_EXTENSIONS)


def _points_quiz_media_kind(filename: str) -> str | None:
    ext = os.path.splitext(str(filename or ""))[1].lower()
    if ext in POINTS_QUIZ_IMAGE_EXTENSIONS:
        return "image"
    if ext in POINTS_QUIZ_VIDEO_EXTENSIONS:
        return "video"
    return None


def _sanitize_filename_part(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return clean.strip("._-") or "file"


def _points_quiz_media_to_data_url(raw_bytes: bytes | bytearray, filename: str) -> str | None:
    kind = _points_quiz_media_kind(filename)
    if not kind:
        return None
    ext = os.path.splitext(str(filename or ""))[1].lower()
    if ext not in POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS:
        return None
    if not isinstance(raw_bytes, (bytes, bytearray)) or not raw_bytes:
        return None
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".m4v": "video/x-m4v",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
    }.get(ext, "application/octet-stream")
    encoded = base64.b64encode(bytes(raw_bytes)).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _points_quiz_media_target_dir(quiz_id: str) -> tuple[str, str]:
    safe_quiz = _sanitize_filename_part(quiz_id or "quiz")
    abs_dir = os.path.join(POINTS_QUIZ_MEDIA_DIR, safe_quiz)
    rel_dir = f"points_quiz_media/{safe_quiz}"
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir, rel_dir


def _store_points_quiz_media_from_path(source_path: str, quiz_id: str, display_name: str | None = None) -> dict | None:
    if not source_path or not os.path.isfile(source_path):
        return None
    original_name = display_name or os.path.basename(source_path)
    kind = _points_quiz_media_kind(original_name) or _points_quiz_media_kind(source_path)
    if not kind:
        return None
    ext = os.path.splitext(original_name)[1].lower() or os.path.splitext(source_path)[1].lower()
    if ext not in POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS:
        return None
    try:
        with open(source_path, "rb") as f:
            raw_bytes = f.read()
    except Exception:
        return None
    data_url = _points_quiz_media_to_data_url(raw_bytes, original_name)
    if not data_url:
        return None
    return {
        "src": data_url,
        "kind": kind,
        "name": original_name,
    }


def _store_points_quiz_media_from_data(raw_data, filename: str, quiz_id: str) -> dict | None:
    kind = _points_quiz_media_kind(filename)
    if not kind:
        return None
    ext = os.path.splitext(filename)[1].lower()
    if ext not in POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS:
        return None
    data = raw_data
    if isinstance(data, str):
        payload = data
        if payload.startswith("data:") and "," in payload:
            payload = payload.split(",", 1)[1]
        try:
            data = base64.b64decode(payload)
        except Exception:
            return None
    if not isinstance(data, (bytes, bytearray)) or not data:
        return None
    data_url = _points_quiz_media_to_data_url(bytes(data), filename)
    if not data_url:
        return None
    return {
        "src": data_url,
        "kind": kind,
        "name": filename,
    }


def _normalize_points_quiz_media_item(raw_item) -> dict | None:
    src = ""
    kind = ""
    name = ""
    data_url = ""
    if isinstance(raw_item, str):
        src = raw_item.strip()
    elif isinstance(raw_item, dict):
        src = str(raw_item.get("src", "")).strip()
        kind = str(raw_item.get("kind", "")).strip().lower()
        name = str(raw_item.get("name", "")).strip()
        data_url = str(raw_item.get("data_url", "")).strip()
    if not src:
        src = data_url
    if not src:
        return None
    inferred_kind = _points_quiz_media_kind(src)
    if kind not in {"image", "video"}:
        kind = inferred_kind or "image"
    if not name:
        name = os.path.basename(src) or ("Bild" if kind == "image" else "Video")
    if not src.startswith("data:") and not os.path.exists(src):
        local_candidates = [
            os.path.join("assets", src),
            os.path.join(POINTS_QUIZ_MEDIA_DIR, src),
            src,
        ]
        for candidate in local_candidates:
            if os.path.exists(candidate):
                try:
                    with open(candidate, "rb") as f:
                        raw_bytes = f.read()
                    migrated = _points_quiz_media_to_data_url(raw_bytes, name or os.path.basename(candidate))
                    if migrated:
                        src = migrated
                        break
                except Exception:
                    pass
    result = {"src": src, "kind": kind, "name": name}
    if data_url:
        result["data_url"] = data_url
    return result


def _normalize_points_quiz_media_list(raw_items) -> list[dict]:
    items = []
    seen: set[str] = set()
    for raw_item in list(raw_items or []):
        item = _normalize_points_quiz_media_item(raw_item)
        if not item:
            continue
        src = str(item.get("src", "")).strip()
        if not src or src in seen:
            continue
        seen.add(src)
        items.append(item)
    return items


def _points_quiz_media_display_src(item: dict) -> str | None:
    src = str(item.get("src", "")).strip()
    if not src:
        return None
    if src.startswith("data:"):
        return src
    if os.path.exists(src):
        return src
    assets_src = os.path.join("assets", src)
    if os.path.exists(assets_src):
        return assets_src
    return None


def _build_points_quiz_media_gallery(items: list[dict], max_width: int, card_width: int = 240, card_height: int = 150) -> ft.Control:
    normalized_items = _normalize_points_quiz_media_list(items)
    if not normalized_items:
        return ft.Container(height=0)

    cards: list[ft.Control] = []
    for item in normalized_items:
        src = _points_quiz_media_display_src(item)
        kind = item.get("kind", "image")
        label = item.get("name") or (os.path.basename(src) if src else "Datei")
        if kind == "video":
            if src and FletVideo and VideoMedia and PlaylistMode:
                media = FletVideo(
                    width=card_width,
                    height=card_height,
                    playlist=[VideoMedia(src)],
                    autoplay=False,
                    muted=True,
                    fit=ft.BoxFit.COVER,
                    show_controls=True,
                    aspect_ratio=16 / 9,
                )
            else:
                media = ft.Container(
                    width=card_width,
                    height=card_height,
                    bgcolor="#00000088",
                    border_radius=10,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("Video nicht mehr verfügbar" if not src else (label or "Video"), color="white", weight="bold", text_align=ft.TextAlign.CENTER),
                )
        else:
            media = (
                ft.Image(src=src, width=card_width, height=card_height, fit=ft.BoxFit.COVER, border_radius=10)
                if src
                else ft.Container(
                    width=card_width,
                    height=card_height,
                    bgcolor="#1F2937",
                    border_radius=10,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("Bild nicht mehr verfügbar", color="white", size=11, text_align=ft.TextAlign.CENTER),
                )
            )

        cards.append(
            ft.Container(
                width=card_width,
                padding=6,
                border_radius=12,
                bgcolor="#08120DE0",
                border=ft.border.Border.all(1, "#2A3A32"),
                content=ft.Column(
                    [
                        media,
                        ft.Text(label, size=11, color="#D1D5DB", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=4,
                ),
            )
        )

    return ft.Container(
        width=max_width,
        content=ft.Row(cards, wrap=True, spacing=8, run_spacing=8, alignment=ft.MainAxisAlignment.CENTER),
    )


def _cleanup_points_quiz_cell_media_pickers(page: ft.Page, state: dict):
    # Legacy cleanup hook; old picker-controls are no longer used.
    state.pop("_points_quiz_question_media_picker", None)
    state.pop("_points_quiz_answer_media_picker", None)


async def _points_quiz_pick_and_upload_media(page: ft.Page, quiz_id: str) -> tuple[list[dict], int, str | None]:
    picker = ft.FilePicker()
    extensions = [ext.lstrip(".") for ext in POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS]
    try:
        pick_call = picker.pick_files(
            dialog_title="Dateien für Punkte-Quiz auswählen",
            allow_multiple=True,
            with_data=True,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=extensions,
        )
    except TypeError:
        try:
            pick_call = picker.pick_files(
                allow_multiple=True,
                with_data=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=extensions,
            )
        except TypeError:
            pick_call = picker.pick_files(
                allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=extensions,
            )
    except Exception as ex:
        return [], 0, f"Dateiauswahl konnte nicht geöffnet werden: {ex}"

    picked_files = await pick_call if inspect.isawaitable(pick_call) else pick_call
    picked_files = list(picked_files or [])
    if not picked_files:
        return [], 0, None

    added_items: list[dict] = []
    invalid_count = 0

    for picked in picked_files:
        original_name = str(getattr(picked, "name", "") or "").strip()
        if not original_name:
            invalid_count += 1
            continue
        kind = _points_quiz_media_kind(original_name)
        if not kind:
            invalid_count += 1
            continue
        ext = os.path.splitext(original_name)[1].lower()
        if ext not in POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS:
            invalid_count += 1
            continue

        item = None
        picked_bytes = getattr(picked, "bytes", None)
        if picked_bytes:
            item = _store_points_quiz_media_from_data(picked_bytes, original_name, quiz_id)
        if item is None:
            picked_path = str(getattr(picked, "path", "") or "")
            if picked_path:
                item = _store_points_quiz_media_from_path(
                    picked_path,
                    quiz_id=quiz_id,
                    display_name=original_name,
                )
        if item is not None:
            added_items.append(item)
        else:
            invalid_count += 1

    if added_items:
        return _normalize_points_quiz_media_list(added_items), invalid_count, None

    # Last fallback for older picker variants: try upload API when bytes/path were unavailable.
    try:
        _abs_dir, rel_dir = _points_quiz_media_target_dir(quiz_id)
        upload_jobs = []
        expected_items = []
        for picked in picked_files:
            original_name = str(getattr(picked, "name", "") or "").strip()
            if not original_name:
                continue
            ext = os.path.splitext(original_name)[1].lower()
            if ext not in POINTS_QUIZ_ALLOWED_MEDIA_EXTENSIONS:
                continue
            kind = _points_quiz_media_kind(original_name) or "image"
            base = _sanitize_filename_part(os.path.splitext(original_name)[0])
            unique_name = f"{base}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}{ext}"
            rel_src = f"{rel_dir}/{unique_name}"
            expected_items.append({"src": rel_src, "kind": kind, "name": original_name})
            try:
                upload_jobs.append(
                    ft.FilePickerUploadFile(
                        id=getattr(picked, "id", None),
                        name=original_name,
                        upload_url=page.get_upload_url(rel_src, 600),
                    )
                )
            except TypeError:
                upload_jobs.append(
                    ft.FilePickerUploadFile(
                        name=original_name,
                        upload_url=page.get_upload_url(rel_src, 600),
                    )
                )
        if not upload_jobs:
            return [], invalid_count, None
        try:
            upload_call = picker.upload(files=upload_jobs)
        except TypeError:
            upload_call = picker.upload(upload_jobs)
        if inspect.isawaitable(upload_call):
            await upload_call
        return _normalize_points_quiz_media_list(expected_items), invalid_count, None
    except Exception:
        return [], invalid_count, "Dateien konnten nicht übernommen werden. Bitte erneut versuchen."


def _blank_points_question(points: int) -> dict:
    return {"points": points, "question": "", "answer": "", "question_media": [], "answer_media": [], "used": False}


def _default_points_category(index: int) -> dict:
    return {
        "name": f"Kategorie {index + 1}",
        "questions": [_blank_points_question(points) for points in POINTS_QUIZ_POINT_VALUES],
    }


def normalize_points_quiz(quiz: dict) -> dict:
    normalized = dict(quiz or {})
    categories = list(normalized.get("categories") or [])
    desired_count = len(categories) if categories else POINTS_QUIZ_DEFAULT_CATEGORIES
    desired_count = max(POINTS_QUIZ_MIN_CATEGORIES, min(POINTS_QUIZ_MAX_CATEGORIES, desired_count))
    result_categories = []
    for idx in range(desired_count):
        raw_cat = categories[idx] if idx < len(categories) and isinstance(categories[idx], dict) else {}
        name = str(raw_cat.get("name", f"Kategorie {idx + 1}")).strip() or f"Kategorie {idx + 1}"
        raw_questions = list(raw_cat.get("questions") or [])
        questions = []
        for q_idx, points in enumerate(POINTS_QUIZ_POINT_VALUES):
            raw_q = raw_questions[q_idx] if q_idx < len(raw_questions) and isinstance(raw_questions[q_idx], dict) else {}
            questions.append({
                "points": points,
                "question": str(raw_q.get("question", "")).strip(),
                "answer": str(raw_q.get("answer", "")).strip(),
                "question_media": _normalize_points_quiz_media_list(raw_q.get("question_media", [])),
                "answer_media": _normalize_points_quiz_media_list(raw_q.get("answer_media", [])),
            })
        result_categories.append({"name": name, "questions": questions})
    normalized["categories"] = result_categories
    normalized.setdefault("id", new_points_quiz_id())
    normalized["title"] = str(normalized.get("title", "Mein Punkte-Quiz")).strip() or "Mein Punkte-Quiz"
    normalized.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    normalized["updated_at"] = normalized.get("updated_at") or normalized["created_at"]
    normalized["is_draft"] = bool(normalized.get("is_draft", True))
    return normalized


def new_empty_points_quiz(title: str = "Mein Punkte-Quiz") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return normalize_points_quiz({
        "id": new_points_quiz_id(),
        "title": title,
        "created_at": now,
        "updated_at": now,
        "is_draft": True,
        "categories": [_default_points_category(i) for i in range(POINTS_QUIZ_DEFAULT_CATEGORIES)],
    })


def get_user_points_quizzes(state: dict) -> list[dict]:
    email = state.get("current_user_email")
    if not email:
        return []
    db = load_db()
    user = db.get("users", {}).get(email)
    if not user:
        return []
    ensure_social_defaults(user)
    return [normalize_points_quiz(q) for q in list(user.get("custom_points_quizzes", []) or [])]


def persist_user_points_quizzes(state: dict, quizzes: list[dict]):
    email = state.get("current_user_email")
    if not email:
        return
    db = load_db()
    if email not in db.get("users", {}):
        return
    ensure_social_defaults(db["users"][email])
    db["users"][email]["custom_points_quizzes"] = [normalize_points_quiz(q) for q in quizzes]
    save_db(db)


def find_points_quiz(quizzes: list[dict], quiz_id: str) -> dict | None:
    for quiz in quizzes:
        if quiz.get("id") == quiz_id:
            return normalize_points_quiz(quiz)
    return None


def upsert_points_quiz(state: dict, quiz: dict, mark_finished: bool = False) -> dict:
    quiz = normalize_points_quiz(quiz)
    quiz["updated_at"] = datetime.now(timezone.utc).isoformat()
    if mark_finished:
        quiz["is_draft"] = False
    quizzes = get_user_points_quizzes(state)
    replaced = False
    for idx, existing in enumerate(quizzes):
        if existing.get("id") == quiz.get("id"):
            quizzes[idx] = quiz
            replaced = True
            break
    if not replaced:
        quizzes.append(quiz)
    persist_user_points_quizzes(state, quizzes)
    return quiz


def delete_points_quiz(state: dict, quiz_id: str):
    quizzes = [q for q in get_user_points_quizzes(state) if q.get("id") != quiz_id]
    persist_user_points_quizzes(state, quizzes)


def points_quiz_is_playable(quiz: dict) -> bool:
    categories = normalize_points_quiz(quiz).get("categories", [])
    return all(
        str(cat.get("name", "")).strip() and all(str(q.get("question", "")).strip() and str(q.get("answer", "")).strip() for q in cat.get("questions", []))
        for cat in categories
    )


def build_random_points_quiz(age: str = "mid") -> dict:
    age = age if age in {opt[0] for opt in POINTS_QUIZ_AGE_OPTIONS} else "mid"
    age_bank = _points_quiz_bank_for_age(age)
    categories_pool = list(age_bank.items())
    picked = random.sample(categories_pool, k=min(POINTS_QUIZ_DEFAULT_CATEGORIES, len(categories_pool)))
    categories = []
    used_prompts: set[str] = set()
    for cat_name, level_map in picked:
        questions = []
        for points in POINTS_QUIZ_POINT_VALUES:
            entries = list(level_map.get(points, []))
            if not entries:
                fallback = [q for lvl_entries in level_map.values() for q in lvl_entries]
                entries = fallback
            if not entries:
                continue
            candidates = [item for item in entries if str(item.get("question", "")).strip().lower() not in used_prompts]
            entry = random.choice(candidates or entries)
            used_prompts.add(str(entry.get("question", "")).strip().lower())
            questions.append({
                "points": points,
                "question": entry["question"],
                "answer": entry["answer"],
            })
        categories.append({"name": cat_name, "questions": questions})
    return normalize_points_quiz({
        "id": f"random_points_{int(time.time())}",
        "title": "Zufälliges Punkte-Quiz",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_draft": False,
        "categories": categories,
        "source": "random",
        "age_group": age,
        "age_label": _points_quiz_age_label(age),
    })


def _points_quiz_total_cells(quiz: dict) -> int:
    categories = normalize_points_quiz(quiz).get("categories", [])
    return sum(len(cat.get("questions", [])) for cat in categories)


def _points_quiz_used_cells(session: dict) -> int:
    return len(session.get("used_cells", []))


def _points_quiz_team_label(index: int) -> str:
    return f"Team {index + 1}"


def _game_portal_back_overlay(page: ft.Page, state: dict) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.SETTINGS, size=16, color="white"),
                    bgcolor="#0000008f",
                    border_radius=14,
                    padding=ft.Padding(8, 6, 8, 6),
                    on_click=lambda e: show_settings_view(page, state),
                    tooltip="Einstellungen",
                ),
                ft.Container(
                    content=ft.TextButton(
                        "← Spielauswahl",
                        on_click=lambda e: e.page.go("/"),
                        style=ft.ButtonStyle(color="white"),
                    ),
                    bgcolor="#0000008f",
                    border_radius=14,
                    padding=ft.Padding(6, 2, 6, 2),
                ),
            ],
            spacing=8,
        ),
        top=18,
        left=18,
        alignment=ft.Alignment(-1, -1),
    )


def _settings_corner_overlay(page: ft.Page, state: dict) -> ft.Container:
    return ft.Container(
        content=ft.Container(
            content=ft.Icon(ft.Icons.SETTINGS, size=18, color="white"),
            bgcolor="#0000008f",
            border_radius=14,
            padding=ft.Padding(8, 6, 8, 6),
            on_click=lambda e: show_settings_view(page, state),
            tooltip="Einstellungen",
        ),
        top=18,
        left=18,
        alignment=ft.Alignment(-1, -1),
    )


def _coins_for_money_level(money_level_idx: int) -> int:
    if money_level_idx < 0:
        return 0
    steps = max(len(MONEY_LEVELS) - 1, 1)
    return max(1, int(round(1 + (money_level_idx * 99 / steps))))


def _shop_price_coins(item: dict) -> int:
    raw = int(item.get("price", 0))
    if raw <= 0:
        return 0
    # Legacy prices were in euro-space; coins use a smaller progression.
    return max(1, raw // 1000)


def show_portal_stats(page: ft.Page, state: dict):
    db = load_db()
    theme = get_theme(state)
    g = db.get("global_stats", {})
    ensure_stats_defaults(g)
    email = state.get("current_user_email")
    user = db.get("users", {}).get(email) if email else None
    if user:
        ensure_stats_defaults(user.setdefault("stats", {}))
    u_stats = user.get("stats", {}) if user else {}

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=20,
                        content=ft.Container(
                            width=min(860, int((_page_size(page)[0]) - 24)),
                            border_radius=18,
                            bgcolor="#08120DE8",
                            border=ft.border.Border.all(2, theme["border"]),
                            padding=20,
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.TextButton("← Zurück", on_click=lambda e: open_main_menu(e.page, state), style=ft.ButtonStyle(color="white")),
                                            ft.Text("Allgemeine Statistik", size=28, weight="bold", color="white"),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Divider(color=theme["border"]),
                                    ft.Text("Global", size=18, weight="bold", color=theme["gold"]),
                                    ft.Text(f"Gesamte WWM-Spiele: {g.get('games_played', 0)}", color="white"),
                                    ft.Text(f"Punkte-Quiz-Spiele: {g.get('points_quiz_games_played', 0)}", color="white"),
                                    ft.Text(f"Punkte-Quiz (komplett beendet): {g.get('points_quiz_finished_games', 0)}", color="white"),
                                    ft.Text(f"Bewertete Punkte-Quiz-Fragen: {g.get('points_quiz_questions_judged', 0)}", color="white"),
                                    ft.Container(height=8),
                                    ft.Text("Dein Konto", size=18, weight="bold", color=theme["accent"]),
                                    ft.Text(f"Eingeloggt als: {email}" if email and user else "Du bist aktuell nicht eingeloggt.", color=theme_txt(theme, "secondary")),
                                    ft.Text(f"Deine WWM-Spiele: {u_stats.get('games_played', 0)}", color="white"),
                                    ft.Text(f"Deine Punkte-Quiz-Spiele: {u_stats.get('points_quiz_games_played', 0)}", color="white"),
                                    ft.Text(f"Deine kompletten Punkte-Quiz-Runden: {u_stats.get('points_quiz_finished_games', 0)}", color="white"),
                                    ft.Text(f"Deine bewerteten Punkte-Quiz-Fragen: {u_stats.get('points_quiz_questions_judged', 0)}", color="white"),
                                    ft.Text(f"Deine Spiel-Münzen: {u_stats.get('shop_coins', 0)}", color=theme["gold"], weight="bold"),
                                ],
                                spacing=8,
                                scroll=ft.ScrollMode.AUTO,
                            ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_portal_settings(page: ft.Page, state: dict):
    theme = get_theme(state)
    email = state.get("current_user_email")
    logged_in = bool(email)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=420,
                            padding=22,
                            bgcolor="#08120DE8",
                            border_radius=18,
                            border=ft.border.Border.all(2, theme["border"]),
                            content=ft.Column(
                                [
                                    ft.Text("Einstellungen", size=30, weight="bold", color="white"),
                                    _theme_action_button("Allgemeine Statistik", theme, lambda e: show_portal_stats(e.page, state), width=280),
                                    _theme_action_button("Design auswählen", theme, lambda e: show_design_view(e.page, state), width=280),
                                    _theme_action_button("Shop", theme, lambda e: e.page.go("/shop") if logged_in else show_login_view(e.page, state), width=280),
                                    _theme_action_button("Anmelden", theme, lambda e: show_login_view(e.page, state), width=280, bg=theme["success"]) if not logged_in else _theme_action_button(f"Profil: {email}", theme, lambda e: show_login_view(e.page, state), width=280, bg=theme["success"]),
                                    _theme_action_button("Abmelden", theme, lambda e: e.page.run_task(_do_logout, e.page, state), width=280, bg=theme["danger"]) if logged_in else ft.Container(),
                                    ft.Text(f"Konto: {email}" if logged_in else "Nicht eingeloggt", size=12, color=theme_txt(theme, "secondary")),
                                    ft.TextButton("← Zurück", on_click=lambda e: open_main_menu(e.page, state), style=ft.ButtonStyle(color="white")),
                                ],
                                spacing=12,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def open_wwm_main_menu(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    _set_resize_view(state, open_wwm_main_menu)
    _sync_page_route(page, "/wwm")
    if state.pop("_startup_recovering", False):
        saved = get_saved_game_for_state(state)
        if saved:
            resume_saved_game(page, state, saved)
            return
    page.controls.clear()
    page.add(build_welcome_view(page, state))
    page.update()


def build_game_portal_view(page: ft.Page, state: dict) -> ft.Control:
    theme = get_theme(state)
    page_w, _ = _page_size(page)
    mobile = page_w < 760
    compact = page_w < 1080
    logged_in = bool(state.get("current_user_email"))
    email = state.get("current_user_email")
    avatar_preview = ft.Text("👤", size=18)
    if logged_in:
        try:
            db = load_db()
            user_info = db.get("users", {}).get(email)
            if user_info:
                ensure_avatar_defaults(user_info)
                avatar_preview = build_avatar_figure(user_info, theme, size=30 if compact else 36)
        except Exception:
            avatar_preview = ft.Text("👤", size=18)
    hero_width = min(860, max(300, int(page_w - 24)))
    card_width = min(360, max(260, int(page_w - 28))) if mobile else min(340, max(280, int((page_w - 78) / 2))) if compact else 360
    card_height = 220 if compact else 250
    action_btn_w = 170 if page_w < 900 else 200
    profile_max_w = min(280, max(180, int(page_w - 40)))
    hero = ft.Container(
        width=hero_width,
        padding=ft.Padding(24, 22, 24, 22) if compact else ft.Padding(28, 26, 28, 26),
        bgcolor="#08120DE0",
        border_radius=28,
        border=ft.border.Border.all(1.5, theme.get("border", "#17432C")),
        shadow=ft.BoxShadow(blur_radius=28, color="#44000000"),
        content=ft.Column(
            [
                ft.Text("QUIZ ARENA", size=18, weight="bold", color=theme.get("accent", "#10B981")),
                ft.Text("Wähle deinen Spielmodus", size=28 if compact else 34, weight="w900", color="white", text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Klassisches Wer wird Millionär oder ein Team-basiertes Punkte-Quiz mit Kategorien, Tafel und Live-Wertung.",
                    size=13 if compact else 14,
                    color=theme_txt(theme, "secondary"),
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment(0, 0),
    )

    def portal_card(title: str, subtitle: str, accent: str, icon: str, on_click):
        return ft.Container(
            width=card_width,
            height=card_height,
            border_radius=26,
            on_click=on_click,
            bgcolor="#07110DDF",
            border=ft.border.Border.all(1.6, accent),
            shadow=ft.BoxShadow(blur_radius=24, color=f"#44{accent[1:]}", spread_radius=1),
            padding=ft.Padding(20, 18, 20, 18) if compact else ft.Padding(24, 22, 24, 22),
            content=ft.Column(
                [
                    ft.Text(icon, size=36 if compact else 42),
                    ft.Text(title, size=24 if compact else 28, weight="w900", color="white"),
                    ft.Text(subtitle, size=13 if compact else 14, color=theme_txt(theme, "secondary")),
                    ft.Container(expand=True),
                    ft.Row(
                        [
                            ft.Text("Modus öffnen", size=14, weight="bold", color=accent),
                            ft.Text("→", size=18, color=accent),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=8,
            ),
        )

    cards = ft.Column(
        [
            portal_card("Wer wird Millionär", "Das bisherige Solo-Spiel mit Jokern, Daily Challenge und eigenem Quiz-Modus.", theme.get("accent", "#10B981"), "💰", lambda e: _go_route_or_render(e.page, "/wwm", open_wwm_main_menu, state)),
            portal_card("Punkte-Quiz", "Team gegen Team auf einer Punktetafel mit Kategorien, Bewertung durch dich und freiem Spielende.", theme.get("gold", "#FACC15"), "🏟️", lambda e: _go_route_or_render(e.page, "/points", show_points_quiz_hub, state)),
        ],
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    ) if mobile else ft.Row(
        [
            portal_card("Wer wird Millionär", "Das bisherige Solo-Spiel mit Jokern, Daily Challenge und eigenem Quiz-Modus.", theme.get("accent", "#10B981"), "💰", lambda e: _go_route_or_render(e.page, "/wwm", open_wwm_main_menu, state)),
            portal_card("Punkte-Quiz", "Team gegen Team auf einer Punktetafel mit Kategorien, Bewertung durch dich und freiem Spielende.", theme.get("gold", "#FACC15"), "🏟️", lambda e: _go_route_or_render(e.page, "/points", show_points_quiz_hub, state)),
        ],
        spacing=18 if not compact else 14,
        run_spacing=18,
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    general_actions = ft.Row(
        [
            _game_menu_button("Einstellungen", lambda e: show_portal_settings(e.page, state), theme["accent"], width=action_btn_w, height=40),
            _game_menu_button("Shop", lambda e: e.page.go("/shop") if logged_in else show_login_view(e.page, state), theme["gold"], width=140 if page_w >= 900 else 150, height=40),
            _game_menu_button("Anmelden" if not logged_in else "Profil", lambda e: show_login_view(e.page, state), theme["success"], width=150 if page_w >= 900 else 160, height=40),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
        wrap=True,
    )

    profile_chip = ft.Container(
        bgcolor="#00000095",
        border_radius=14,
        border=ft.border.Border.all(1, theme["border"]),
        padding=ft.Padding(10, 8, 10, 8),
        on_click=lambda e: show_login_view(e.page, state),
        width=profile_max_w,
        content=ft.Row(
            [
                avatar_preview,
                ft.Text((email or "Anmelden"), size=12, color="white", weight="bold", expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=6,
        ),
    )

    return ft.Container(
        expand=True,
        content=ft.Stack(
            [
                _themed_screen_background(page, theme, "#00000090"),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    padding=16 if compact else 20,
                    content=ft.Column(
                        ([ft.Row([profile_chip], alignment=ft.MainAxisAlignment.CENTER, wrap=True)] if mobile else []) + [hero, general_actions, cards],
                        spacing=18 if compact else 24,
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ),
                _settings_corner_overlay(page, state),
                ft.Container(top=18, right=18, content=profile_chip, visible=not mobile),
            ],
            expand=True,
        ),
    )


def show_points_quiz_hub(page: ft.Page, state: dict):
    _set_resize_view(state, show_points_quiz_hub)
    _sync_page_route(page, "/points")
    _cleanup_points_quiz_cell_media_pickers(page, state)
    stale_delete_overlay = state.pop("_points_quiz_delete_overlay", None)
    if stale_delete_overlay is not None:
        try:
            while stale_delete_overlay in page.overlay:
                page.overlay.remove(stale_delete_overlay)
        except Exception:
            pass
    theme = get_theme(state)
    ui = theme_ui_palette(theme)
    logged_in = bool(state.get("current_user_email"))
    own_quizzes = get_user_points_quizzes(state) if logged_in else []

    random_card = ft.Container(
        width=420,
        border_radius=20,
        padding=20,
        bgcolor="#08120DE8",
        border=ft.border.Border.all(1.4, theme["gold"]),
        content=ft.Column(
            [
                ft.Text("🎲 Zufälliges Punkte-Quiz", size=22, weight="bold", color="white"),
                ft.Text("Erstellt ein fertiges Brett mit Alterswahl, Schwierigkeitsstufen und gemischten Kategorien.", size=13, color=theme_txt(theme, "secondary")),
                ft.Container(height=8),
                _game_menu_button("Jetzt spielen", lambda e: show_points_quiz_team_setup(e.page, state, build_random_points_quiz("mid"), "mid"), theme["gold"], width=220),
            ],
            spacing=6,
        ),
    )

    own_rows = []
    for quiz in sorted(own_quizzes, key=lambda q: q.get("updated_at", ""), reverse=True):
        ready = points_quiz_is_playable(quiz)
        own_rows.append(
            ft.Container(
                padding=12,
                border_radius=14,
                bgcolor=theme["panel"],
                border=ft.border.Border.all(1, theme["border"]),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(quiz.get("title", "Punkte-Quiz"), size=16, weight="bold", color="white", expand=True),
                                ft.Container(
                                    content=ft.Text("Fertig" if ready else "Entwurf", size=10, weight="bold", color="white"),
                                    bgcolor=theme["success"] if ready else theme["accent_2"],
                                    border_radius=8,
                                    padding=ft.Padding(8, 3, 8, 3),
                                ),
                            ]
                        ),
                        ft.Text(f"{len(quiz.get('categories', []))} Kategorien · {len(POINTS_QUIZ_POINT_VALUES) * len(quiz.get('categories', []))} Felder", size=12, color=theme_txt(theme, "secondary")),
                        ft.Row(
                            [
                                _game_menu_button("Bearbeiten", lambda e, qid=quiz["id"]: show_points_quiz_editor(e.page, state, qid), theme["accent"], width=110, height=36),
                                _game_menu_button("Spielen", lambda e, q=quiz: show_points_quiz_team_setup(e.page, state, q), theme["success"] if ready else "#666666", width=110, height=36),
                                _game_menu_button("Löschen", lambda e, qid=quiz["id"]: confirm_delete_points_quiz(e.page, state, qid), theme["danger"], width=110, height=36),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=8,
                        ),
                    ],
                    spacing=6,
                ),
            )
        )

    if not own_rows:
        own_rows.append(ft.Text("Noch keine eigenen Punkte-Quiz-Spiele.", size=13, color=theme_txt(theme, "secondary")))

    own_card = ft.Container(
        width=420,
        border_radius=20,
        padding=20,
        bgcolor="#08120DE8",
        border=ft.border.Border.all(1.4, theme["accent"]),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("🧩 Eigene Punkte-Quiz-Spiele", size=22, weight="bold", color="white", expand=True),
                        _game_menu_button("Neu", lambda e: show_points_quiz_editor(e.page, state, None) if logged_in else show_login_view(e.page, state), theme["accent"], width=100, height=34),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text("Erstelle eigene Kategorien und Fragen oder spiele gespeicherte Bretter.", size=13, color=theme_txt(theme, "secondary")),
                ft.Container(
                    height=300,
                    content=ft.Column(own_rows, spacing=10, scroll=ft.ScrollMode.AUTO),
                ),
                ft.Text("Anmeldung erforderlich, um eigene Punkte-Spiele zu speichern.", size=12, color=theme_txt(theme, "muted")) if not logged_in else ft.Container(height=0),
            ],
            spacing=8,
        ),
    )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000090"),
                    ft.Container(
                        expand=True,
                        padding=20,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            [
                                ft.Text("Punkte-Quiz", size=30, weight="w900", color=ui["text"]),
                                ft.Text("Teams, Kategorien, Punktebrett und freie Spielleitung.", size=14, color=theme_txt(theme, "secondary")),
                                ft.Row([random_card, own_card], spacing=18, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
                                ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                            ],
                            spacing=16,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_points_quiz_team_setup(page: ft.Page, state: dict, quiz: dict, default_age: str = "mid"):
    _set_resize_view(state, show_points_quiz_team_setup, quiz, default_age)
    quiz = normalize_points_quiz(quiz)
    is_random_quiz = quiz.get("source") == "random"
    selected_age = default_age if default_age in {opt[0] for opt in POINTS_QUIZ_AGE_OPTIONS} else str(quiz.get("age_group", "mid"))
    if selected_age not in {opt[0] for opt in POINTS_QUIZ_AGE_OPTIONS}:
        selected_age = "mid"
    if not points_quiz_is_playable(quiz):
        page.snack_bar = ft.SnackBar(content=ft.Text("Dieses Punkte-Quiz ist noch nicht vollständig ausgefüllt."))
        page.snack_bar.open = True
        page.update()
        if quiz.get("source") == "random":
            show_points_quiz_hub(page, state)
        else:
            show_points_quiz_editor(page, state, quiz.get("id"))
        return

    theme = get_theme(state)
    team_count = ft.Dropdown(
        label="Anzahl Teams",
        width=240,
        value="2",
        options=[ft.dropdown.Option(str(i)) for i in range(POINTS_QUIZ_MIN_TEAMS, POINTS_QUIZ_MAX_TEAMS + 1)],
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )
    age_dropdown = ft.Dropdown(
        label="Altersgruppe",
        width=240,
        value=selected_age,
        options=[ft.dropdown.Option(k, text=label) for k, label in POINTS_QUIZ_AGE_OPTIONS],
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
        visible=is_random_quiz,
    )
    team_fields = []
    fields_column = ft.Column(spacing=8)

    def rebuild_team_fields(count: int):
        team_fields.clear()
        fields_column.controls.clear()
        for idx in range(count):
            field = ft.TextField(
                label=_points_quiz_team_label(idx),
                value=_points_quiz_team_label(idx),
                width=320,
                bgcolor=theme["question_bg"],
                color=theme["question_text"],
                border_color=theme["border"],
            )
            team_fields.append(field)
            fields_column.controls.append(field)

    rebuild_team_fields(2)

    def on_team_count_change(e):
        try:
            count = max(POINTS_QUIZ_MIN_TEAMS, min(POINTS_QUIZ_MAX_TEAMS, int(e.control.value or "2")))
        except Exception:
            count = 2
        rebuild_team_fields(count)
        page.update()

    team_count.on_change = on_team_count_change
    team_count.on_select = on_team_count_change

    def start_game(e):
        start_quiz = quiz
        if is_random_quiz:
            age = age_dropdown.value if age_dropdown.value in {opt[0] for opt in POINTS_QUIZ_AGE_OPTIONS} else "mid"
            start_quiz = build_random_points_quiz(age)
        teams = []
        for idx, field in enumerate(team_fields):
            name = (field.value or "").strip() or _points_quiz_team_label(idx)
            teams.append({"name": name, "score": 0})
        start_points_quiz_session(page, state, start_quiz, teams)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000092"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=560,
                            padding=24,
                            bgcolor="#08120DE8",
                            border_radius=22,
                            border=ft.border.Border.all(1.5, theme["gold"]),
                            content=ft.Column(
                                [
                                    ft.Text(quiz.get("title", "Punkte-Quiz"), size=28, weight="w900", color="white", text_align=ft.TextAlign.CENTER),
                                    ft.Text("Lege Teams fest und starte danach das Brett.", size=13, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                                    ft.Text("Altersstufe passt den Fragenpool an." if is_random_quiz else "Bei eigenen Quizzen bleiben deine Fragen unverändert.", size=12, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                                    age_dropdown,
                                    team_count,
                                    fields_column,
                                    ft.Row(
                                        [
                                            _game_menu_button("Starten", start_game, theme["success"]),
                                            _game_menu_button("Zurück", lambda e: show_points_quiz_hub(e.page, state), theme["danger"]),
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=12,
                                    ),
                                ],
                                spacing=14,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def start_points_quiz_session(page: ft.Page, state: dict, quiz: dict, teams: list[dict]):
    state["points_quiz_session"] = {
        "quiz": normalize_points_quiz(quiz),
        "teams": teams,
        "current_team_idx": 0,
        "used_cells": [],
        "correct_judged": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished": False,
    }
    state.pop("active_points_question", None)
    show_points_quiz_board(page, state)


def _find_points_question(quiz: dict, cat_idx: int, q_idx: int) -> dict | None:
    categories = normalize_points_quiz(quiz).get("categories", [])
    if 0 <= cat_idx < len(categories):
        questions = categories[cat_idx].get("questions", [])
        if 0 <= q_idx < len(questions):
            return questions[q_idx]
    return None


def _points_cell_key(cat_idx: int, q_idx: int) -> str:
    return f"{cat_idx}:{q_idx}"


def show_points_quiz_board(page: ft.Page, state: dict):
    _set_resize_view(state, show_points_quiz_board)
    session = state.get("points_quiz_session")
    if not session:
        show_points_quiz_hub(page, state)
        return
    quiz = normalize_points_quiz(session.get("quiz", {}))
    teams = session.get("teams", [])
    if not teams:
        show_points_quiz_hub(page, state)
        return
    used_cells = set(session.get("used_cells", []))
    theme = get_theme(state)
    page_w, page_h = _page_size(page)
    is_mobile = page_w < 980
    is_landscape_mobile = page_w < 1180 and page_w > page_h
    current_team = teams[session.get("current_team_idx", 0) % len(teams)]
    total_cells = _points_quiz_total_cells(quiz)
    used_count = _points_quiz_used_cells(session)
    if used_count >= total_cells:
        show_points_quiz_summary(page, state, finished_early=False)
        return

    scoreboard = ft.Column(
        [
            ft.Container(
                padding=10,
                border_radius=12,
                bgcolor=theme["gold"] if idx == session.get("current_team_idx", 0) else theme["panel"],
                border=ft.border.Border.all(1, theme["gold"] if idx == session.get("current_team_idx", 0) else theme["border"]),
                content=ft.Row(
                    [
                        ft.Text(team["name"], color="#111111" if idx == session.get("current_team_idx", 0) else "white", weight="bold", expand=True),
                        ft.Text(str(team["score"]), color="#111111" if idx == session.get("current_team_idx", 0) else theme["gold"], weight="bold"),
                    ]
                ),
            )
            for idx, team in enumerate(teams)
        ],
        spacing=8,
    )

    categories = quiz.get("categories", [])
    cat_count = len(categories)
    label_w = 84 if is_landscape_mobile else (88 if is_mobile else 96)
    cell_w = 150 if is_landscape_mobile else (160 if is_mobile else 180)
    cell_h = 58 if is_landscape_mobile else (62 if is_mobile else 66)
    spacing = 8 if is_mobile else 10
    board_width = label_w + (cat_count * cell_w) + (cat_count * spacing)
    frame_width = min(max(board_width + 36, 470), max(320, int(page_w - 24)))
    score_width = min(420, max(250, frame_width - 28))

    header_row = ft.Row(
        [ft.Container(width=label_w)] + [
            ft.Container(
                width=cell_w,
                height=cell_h,
                border_radius=14,
                bgcolor="#0B1A14",
                border=ft.border.Border.all(1.2, theme["accent"]),
                alignment=ft.Alignment(0, 0),
                padding=8,
                content=ft.Text(cat.get("name", "Kategorie"), size=13 if is_mobile else 15, weight="bold", color="white", text_align=ft.TextAlign.CENTER, max_lines=2, no_wrap=False),
            )
            for cat in categories
        ],
        spacing=spacing,
        wrap=False,
    )

    grid_rows = []
    for q_idx, points in enumerate(POINTS_QUIZ_POINT_VALUES):
        row_controls = [
            ft.Container(
                width=label_w,
                height=cell_h,
                border_radius=14,
                bgcolor="#07110D",
                border=ft.border.Border.all(1.2, theme["border"]),
                alignment=ft.Alignment(0, 0),
                content=ft.Text(str(points), size=20 if is_mobile else 24, weight="w900", color=theme["gold"]),
            )
        ]
        for cat_idx, cat in enumerate(categories):
            key = _points_cell_key(cat_idx, q_idx)
            question = _find_points_question(quiz, cat_idx, q_idx) or {}
            is_used = key in used_cells
            row_controls.append(
                ft.Container(
                    width=cell_w,
                    height=cell_h,
                    border_radius=16,
                    bgcolor="#334155" if is_used else theme["accent"],
                    border=ft.border.Border.all(1.2, theme["border"]),
                    alignment=ft.Alignment(0, 0),
                    on_click=None if is_used else (lambda e, c=cat_idx, q=q_idx: open_points_question(e.page, state, c, q)),
                    content=ft.Text("Bereits gespielt" if is_used else f"{question.get('points', points)} Punkte", size=13 if is_mobile else 15, weight="bold", color="white", text_align=ft.TextAlign.CENTER, max_lines=2, no_wrap=False),
                )
            )
        grid_rows.append(ft.Row(row_controls, spacing=spacing, wrap=False))

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000094"),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(14, 14, 14, 14),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=frame_width,
                            content=ft.Column(
                            [
                                ft.Column(
                                    [
                                        ft.Column(
                                            [
                                                ft.Text(quiz.get("title", "Punkte-Quiz"), size=24 if is_mobile else 28, weight="w900", color="white"),
                                                ft.Text(f"Am Zug: {current_team['name']}", size=16, weight="bold", color=theme["gold"]),
                                                ft.Text(f"{used_count} / {total_cells} Felder gespielt", size=12, color=theme_txt(theme, "secondary")),
                                            ],
                                            spacing=4,
                                            horizontal_alignment=ft.CrossAxisAlignment.START,
                                        ),
                                        ft.Row(
                                            [
                                                _game_menu_button("Spielauswahl", lambda e: e.page.go("/"), "#4B5563", width=150 if is_mobile else 170, height=40),
                                                _game_menu_button("Spiel beenden", lambda e: show_points_quiz_summary(e.page, state, finished_early=True), theme["danger"], width=170 if is_mobile else 180, height=40),
                                                _game_menu_button("Zurück", lambda e: show_points_quiz_hub(e.page, state), "#4B5563", width=130 if is_mobile else 140, height=40),
                                            ],
                                            spacing=10,
                                            wrap=True,
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                ft.Container(
                                    width=frame_width,
                                    padding=16,
                                    bgcolor="#08120DE0",
                                    border_radius=20,
                                    border=ft.border.Border.all(1.4, theme["border"]),
                                    content=ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Container(
                                                        width=board_width,
                                                        content=ft.Column([header_row] + grid_rows, spacing=10),
                                                    )
                                                ],
                                                scroll=ft.ScrollMode.AUTO,
                                            ),
                                            ft.Container(height=12),
                                            ft.Container(
                                                width=score_width,
                                                padding=14,
                                                bgcolor="#08120DE0",
                                                border_radius=16,
                                                border=ft.border.Border.all(1.2, theme["gold"]),
                                                content=ft.Column(
                                                    [
                                                        ft.Text("Punktestand", size=20, weight="bold", color="white"),
                                                        scoreboard,
                                                    ],
                                                    spacing=12,
                                                ),
                                            ),
                                        ],
                                        spacing=8,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ),
                            ],
                            spacing=16,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def open_points_question(page: ft.Page, state: dict, cat_idx: int, q_idx: int):
    session = state.get("points_quiz_session")
    if not session:
        show_points_quiz_hub(page, state)
        return
    quiz = normalize_points_quiz(session.get("quiz", {}))
    question = _find_points_question(quiz, cat_idx, q_idx)
    if not question:
        show_points_quiz_board(page, state)
        return
    state["active_points_question"] = {
        "cat_idx": cat_idx,
        "q_idx": q_idx,
        "question": question,
        "category_name": quiz["categories"][cat_idx]["name"],
    }
    show_points_quiz_question(page, state)


def show_points_quiz_question(page: ft.Page, state: dict):
    _set_resize_view(state, show_points_quiz_question)
    session = state.get("points_quiz_session")
    active = state.get("active_points_question")
    if not session or not active:
        show_points_quiz_board(page, state)
        return
    theme = get_theme(state)
    page_w, _ = _page_size(page)
    panel_width = min(860, max(320, int(page_w - 36)))
    solution_width = min(panel_width - 40, max(260, int(page_w - 48)))
    btn_width = 210 if page_w < 900 else 240
    teams = session.get("teams", [])
    current_team = teams[session.get("current_team_idx", 0) % len(teams)]
    question = active["question"]
    question_media = _normalize_points_quiz_media_list(question.get("question_media", []))
    answer_media = _normalize_points_quiz_media_list(question.get("answer_media", []))

    active.setdefault("solution_revealed", False)

    def resolve_question(correct: bool):
        if not active.get("solution_revealed"):
            page.snack_bar = ft.SnackBar(content=ft.Text("Bitte zuerst die Lösung anzeigen."))
            page.snack_bar.open = True
            page.update()
            return
        delta = int(question.get("points", 0)) * (1 if correct else -1)
        current_team["score"] += delta
        if correct:
            session["correct_judged"] = session.get("correct_judged", 0) + 1
        key = _points_cell_key(active["cat_idx"], active["q_idx"])
        if key not in session["used_cells"]:
            session["used_cells"].append(key)
        state["points_quiz_session"] = session
        if _points_quiz_used_cells(session) >= _points_quiz_total_cells(session.get("quiz", {})):
            show_points_quiz_summary(page, state, finished_early=False)
            return
        session["current_team_idx"] = (session.get("current_team_idx", 0) + 1) % max(1, len(teams))
        state["points_quiz_session"] = session
        state.pop("active_points_question", None)
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"{current_team['name']}: {'+' if delta >= 0 else ''}{delta} Punkte"),
            bgcolor=theme["success"] if delta >= 0 else theme["danger"],
        )
        page.snack_bar.open = True
        show_points_quiz_board(page, state)

    def toggle_solution(e):
        active["solution_revealed"] = not active.get("solution_revealed", False)
        state["active_points_question"] = active
        show_points_quiz_question(page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000092"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=18,
                        content=ft.Container(
                            width=panel_width,
                            padding=26,
                            border_radius=24,
                            bgcolor="#08120DE8",
                            border=ft.border.Border.all(1.5, theme["accent"]),
                            content=ft.Column(
                                [
                                    ft.Text(active["category_name"], size=15, color=theme["gold"], weight="bold"),
                                    ft.Text(f"{question.get('points', 0)} Punkte für {current_team['name']}", size=18, color="white", weight="bold"),
                                    ft.Container(height=8),
                                    ft.Text(question.get("question", "Frage"), size=22 if page_w < 900 else 28, color="white", text_align=ft.TextAlign.CENTER, weight="w900"),
                                    _build_points_quiz_media_gallery(
                                        question_media,
                                        max_width=panel_width - 48,
                                        card_width=230 if page_w < 900 else 260,
                                        card_height=130 if page_w < 900 else 150,
                                    ),
                                    ft.Container(height=18),
                                    ft.Container(
                                        width=solution_width,
                                        padding=14,
                                        border_radius=16,
                                        bgcolor="#0B1A14",
                                        border=ft.border.Border.all(1.4, theme["gold"]),
                                        content=ft.Column(
                                            [
                                                ft.Text("Lösung", size=16, weight="bold", color=theme["gold"]),
                                                ft.Text(
                                                    question.get("answer", "") if active.get("solution_revealed") else "Tippen, um die Lösung aufzudecken",
                                                    size=18 if active.get("solution_revealed") else 15,
                                                    color="white",
                                                    text_align=ft.TextAlign.CENTER,
                                                ),
                                                _build_points_quiz_media_gallery(
                                                    answer_media if active.get("solution_revealed") else [],
                                                    max_width=solution_width - 24,
                                                    card_width=220 if page_w < 900 else 240,
                                                    card_height=120 if page_w < 900 else 140,
                                                ),
                                            ],
                                            spacing=8,
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        on_click=toggle_solution,
                                    ),
                                    ft.Text(
                                        "Lösung sichtbar - jetzt richtig oder falsch wählen."
                                        if active.get("solution_revealed")
                                        else "Erst Lösung anzeigen, dann bewerten.",
                                        size=12,
                                        color=theme_txt(theme, "secondary"),
                                    ),
                                    ft.Row(
                                        [
                                            _game_menu_button("Richtig beantwortet", lambda e: resolve_question(True), theme["success"], width=btn_width, height=48),
                                            _game_menu_button("Falsch beantwortet", lambda e: resolve_question(False), theme["danger"], width=btn_width, height=48),
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=16,
                                    ),
                                ],
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_points_quiz_answer_screen(page: ft.Page, state: dict):
    _set_resize_view(state, show_points_quiz_answer_screen)
    session = state.get("points_quiz_session")
    active = state.get("active_points_question")
    if not session or not active:
        show_points_quiz_board(page, state)
        return
    theme = get_theme(state)
    page_w, _ = _page_size(page)
    panel_width = min(900, max(320, int(page_w - 36)))
    btn_width = 190 if page_w < 900 else 220
    teams = session.get("teams", [])
    current_idx = session.get("current_team_idx", 0)
    current_team = teams[current_idx % len(teams)]
    correct = bool(active.get("result_correct"))

    def continue_after_result(e):
        if _points_quiz_used_cells(session) >= _points_quiz_total_cells(session.get("quiz", {})):
            show_points_quiz_summary(page, state, finished_early=False)
            return
        session["current_team_idx"] = (current_idx + 1) % len(teams)
        state["points_quiz_session"] = session
        state.pop("active_points_question", None)
        show_points_quiz_board(page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000092"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=18,
                        content=ft.Container(
                            width=panel_width,
                            padding=28,
                            border_radius=24,
                            bgcolor="#08120DE8",
                            border=ft.border.Border.all(1.5, theme["gold"] if correct else theme["danger"]),
                            content=ft.Column(
                                [
                                    ft.Text("Richtig!" if correct else "Leider falsch", size=34, weight="w900", color=theme["success"] if correct else theme["danger"]),
                                    ft.Text(f"{current_team['name']} erhält {'+' if active.get('delta', 0) >= 0 else ''}{active.get('delta', 0)} Punkte.", size=18, color="white"),
                                    ft.Container(height=6),
                                    ft.Text("Richtige Antwort", size=16, weight="bold", color=theme["gold"]),
                                    ft.Text(active["question"].get("answer", ""), size=22, color="white", text_align=ft.TextAlign.CENTER),
                                    ft.Container(height=12),
                                    _game_menu_button("Weiter", continue_after_result, theme["accent"], width=btn_width, height=48),
                                ],
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_points_quiz_summary(page: ft.Page, state: dict, finished_early: bool):
    _set_resize_view(state, show_points_quiz_summary, finished_early)
    session = state.get("points_quiz_session")
    if not session:
        show_points_quiz_hub(page, state)
        return
    if not session.get("stats_recorded"):
        db = load_db()
        g = db.setdefault("global_stats", DEFAULT_GLOBAL_STATS.copy())
        ensure_stats_defaults(g)
        judged = len(session.get("used_cells", []))
        g["points_quiz_games_played"] = g.get("points_quiz_games_played", 0) + 1
        g["points_quiz_questions_judged"] = g.get("points_quiz_questions_judged", 0) + judged
        if not finished_early:
            g["points_quiz_finished_games"] = g.get("points_quiz_finished_games", 0) + 1

        email = state.get("current_user_email")
        if email and email in db.get("users", {}):
            u_stats = db["users"][email].setdefault("stats", DEFAULT_USER_STATS.copy())
            ensure_stats_defaults(u_stats)
            u_stats["points_quiz_games_played"] = u_stats.get("points_quiz_games_played", 0) + 1
            u_stats["points_quiz_questions_judged"] = u_stats.get("points_quiz_questions_judged", 0) + judged
            u_stats["shop_coins"] = u_stats.get("shop_coins", 0) + session.get("correct_judged", 0)
            if not finished_early:
                u_stats["points_quiz_finished_games"] = u_stats.get("points_quiz_finished_games", 0) + 1
        save_db(db)
        session["stats_recorded"] = True
        state["points_quiz_session"] = session

    theme = get_theme(state)
    page_w, _ = _page_size(page)
    panel_width = min(760, max(320, int(page_w - 36)))
    score_width = min(420, max(250, panel_width - 80))
    teams = sorted(session.get("teams", []), key=lambda team: team.get("score", 0), reverse=True)
    top_score = teams[0]["score"] if teams else 0
    winners = [team["name"] for team in teams if team.get("score", 0) == top_score]

    def back_to_points_hub(e):
        state.pop("points_quiz_session", None)
        state.pop("active_points_question", None)
        show_points_quiz_hub(page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000092"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=20,
                        content=ft.Container(
                            width=panel_width,
                            padding=28,
                            border_radius=24,
                            bgcolor="#08120DE8",
                            border=ft.border.Border.all(1.5, theme["gold"]),
                            content=ft.Column(
                                [
                                    ft.Text("Punkte-Quiz beendet", size=32, weight="w900", color="white"),
                                    ft.Text("Vorzeitig beendet" if finished_early else "Alle Fragen wurden gespielt", size=14, color=theme_txt(theme, "secondary")),
                                    ft.Text("Gewinner: " + ", ".join(winners), size=20, weight="bold", color=theme["gold"], text_align=ft.TextAlign.CENTER),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Row(
                                                    [
                                                        ft.Text(f"{idx + 1}. {team['name']}", color="white", weight="bold", expand=True),
                                                        ft.Text(str(team["score"]), color=theme["gold"], weight="bold"),
                                                    ]
                                                )
                                                for idx, team in enumerate(teams)
                                            ],
                                            spacing=10,
                                        ),
                                        width=score_width,
                                        padding=16,
                                        bgcolor=theme["panel"],
                                        border_radius=16,
                                        border=ft.border.Border.all(1, theme["border"]),
                                    ),
                                    _game_menu_button("Zurück zum Punkte-Quiz", back_to_points_hub, theme["accent"], width=280, height=46),
                                ],
                                spacing=14,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def confirm_delete_points_quiz(page: ft.Page, state: dict, quiz_id: str):
    theme = get_theme(state)
    quiz = find_points_quiz(get_user_points_quizzes(state), quiz_id)
    title = quiz.get("title", "Punkte-Quiz") if quiz else "Punkte-Quiz"
    old_overlay = state.pop("_points_quiz_delete_overlay", None)
    if old_overlay is not None:
        try:
            while old_overlay in page.overlay:
                page.overlay.remove(old_overlay)
        except Exception:
            pass

    overlay_ref = [None]

    def _close_popup():
        overlay = overlay_ref[0]
        if state.get("_points_quiz_delete_overlay") is overlay:
            state.pop("_points_quiz_delete_overlay", None)
        if overlay is not None:
            try:
                while overlay in page.overlay:
                    page.overlay.remove(overlay)
            except Exception:
                pass
        page.update()

    def _cancel(ev):
        _close_popup()

    def _confirm_delete(ev):
        _close_popup()
        delete_points_quiz(state, quiz_id)
        show_points_quiz_hub(page, state)

    overlay = ft.Container(
        expand=True,
        bgcolor="#000000B8",
        alignment=ft.Alignment(0, 0),
        on_click=_cancel,
        content=ft.Container(
            width=min(430, int(_page_size(page)[0] - 44)),
            padding=ft.Padding(24, 20, 24, 18),
            border_radius=20,
            bgcolor=theme["question_bg"],
            border=ft.border.Border.all(1.2, theme["border"]),
            shadow=ft.BoxShadow(blur_radius=18, color="#66000000", spread_radius=0),
            on_click=lambda e: None,
            content=ft.Column(
                [
                    ft.Text("Punkte-Quiz löschen?", size=20, weight="w900", color="white"),
                    ft.Text(
                        f'"{title}" wirklich löschen?',
                        size=14,
                        color=theme_txt(theme, "secondary"),
                        text_align=ft.TextAlign.LEFT,
                    ),
                    ft.Row(
                        [
                            _game_menu_button("Abbrechen", _cancel, theme["panel"], width=148, height=40),
                            _game_menu_button("Löschen", _confirm_delete, theme["danger"], width=148, height=40),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                    ),
                ],
                tight=True,
                spacing=16,
            ),
        ),
    )
    overlay_ref[0] = overlay
    state["_points_quiz_delete_overlay"] = overlay
    page.overlay.append(overlay)
    page.update()


def show_points_quiz_editor(page: ft.Page, state: dict, quiz_id: str | None):
    _set_resize_view(state, show_points_quiz_editor, quiz_id)
    _cleanup_points_quiz_cell_media_pickers(page, state)
    if not state.get("current_user_email"):
        show_login_view(page, state)
        return
    stale_delete_overlay = state.pop("_points_quiz_category_delete_overlay", None)
    if stale_delete_overlay is not None:
        try:
            while stale_delete_overlay in page.overlay:
                page.overlay.remove(stale_delete_overlay)
        except Exception:
            pass
    force_close_all_dialogs(page)
    theme = get_theme(state)
    page_w, page_h = _page_size(page)
    is_compact = page_w < 900
    is_landscape_mobile = page_w < 1100 and page_w > page_h
    title_field_width = min(420, max(260, int(page_w - 56)))
    category_field_width = 190 if is_compact else 220
    category_stack_height = 70 if is_compact else 74
    action_btn_width = 190 if is_compact else 220
    action_btn_small_width = 160 if is_compact else 180
    editing_quiz = state.get("editing_points_quiz")
    if quiz_id and isinstance(editing_quiz, dict) and editing_quiz.get("id") == quiz_id:
        quiz = editing_quiz
    elif quiz_id:
        quiz = find_points_quiz(get_user_points_quizzes(state), quiz_id) or new_empty_points_quiz()
    else:
        quiz = new_empty_points_quiz()
    quiz = normalize_points_quiz(quiz)
    state["editing_points_quiz"] = quiz

    title_field = ft.TextField(
        label="Titel des Punkte-Quiz",
        value=quiz.get("title", ""),
        width=title_field_width,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )
    category_fields: list[ft.TextField] = []
    header_labels: list[ft.Text] = []

    def _collect_current_quiz_from_fields() -> dict:
        local_quiz = state.get("editing_points_quiz", quiz)
        local_quiz["title"] = (title_field.value or "").strip() or "Mein Punkte-Quiz"
        for idx, field in enumerate(category_fields):
            local_quiz["categories"][idx]["name"] = (field.value or "").strip() or f"Kategorie {idx + 1}"
        state["editing_points_quiz"] = local_quiz
        return local_quiz

    def _refresh_header_labels():
        for idx, label in enumerate(header_labels):
            if idx < len(category_fields):
                label.value = (category_fields[idx].value or f"K{idx + 1}").strip() or f"K{idx + 1}"
                label.update()

    def _question_preview(entry: dict) -> str:
        question = str(entry.get("question", "")).strip()
        question_media_count = len(_normalize_points_quiz_media_list(entry.get("question_media", [])))
        answer_media_count = len(_normalize_points_quiz_media_list(entry.get("answer_media", [])))
        if not question:
            return "Ausfüllen"
        short = question[:26] + ("..." if len(question) > 26 else "")
        media_hint = ""
        if question_media_count or answer_media_count:
            media_hint = f"\n🖼️{question_media_count} / 🎬{answer_media_count}"
        return f"Bearbeiten\n{short}{media_hint}"

    def _build_category_field(idx: int, category: dict) -> ft.TextField:
        field = ft.TextField(
            label=f"Kategorie {idx + 1}",
            value=category.get("name", ""),
            width=category_field_width,
            bgcolor=theme["question_bg"],
            color=theme["question_text"],
            border_color=theme["border"],
        )
        field.on_change = lambda e: _refresh_header_labels()
        return field

    for idx, category in enumerate(quiz.get("categories", [])):
        category_fields.append(_build_category_field(idx, category))

    def save_quiz(mark_finished: bool = False):
        local_quiz = _collect_current_quiz_from_fields()
        state["editing_points_quiz"] = upsert_points_quiz(state, local_quiz, mark_finished=mark_finished)

    def add_category(e):
        local_quiz = _collect_current_quiz_from_fields()
        categories = local_quiz.get("categories", [])
        if len(categories) >= POINTS_QUIZ_MAX_CATEGORIES:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Maximal {POINTS_QUIZ_MAX_CATEGORIES} Kategorien."))
            page.snack_bar.open = True
            page.update()
            return
        categories.append(_default_points_category(len(categories)))
        local_quiz["categories"] = categories
        state["editing_points_quiz"] = upsert_points_quiz(state, local_quiz, mark_finished=False)
        show_points_quiz_editor(page, state, local_quiz.get("id"))

    def remove_category(index: int):
        local_quiz = _collect_current_quiz_from_fields()
        categories = local_quiz.get("categories", [])
        if index < 0 or index >= len(categories):
            return
        if len(categories) <= POINTS_QUIZ_MIN_CATEGORIES:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Mindestens {POINTS_QUIZ_MIN_CATEGORIES} Kategorien erforderlich."))
            page.snack_bar.open = True
            page.update()
            return
        to_delete = categories[index]
        has_content = False
        if str(to_delete.get("name", "")).strip() and str(to_delete.get("name", "")).strip() != f"Kategorie {index + 1}":
            has_content = True
        for q in to_delete.get("questions", []):
            if str(q.get("question", "")).strip() or str(q.get("answer", "")).strip():
                has_content = True
                break

        def do_delete(_e=None):
            cats = local_quiz.get("categories", [])
            if 0 <= index < len(cats):
                cats.pop(index)
            for i, cat in enumerate(cats):
                if not str(cat.get("name", "")).strip():
                    cat["name"] = f"Kategorie {i + 1}"
            local_quiz["categories"] = cats
            state["editing_points_quiz"] = upsert_points_quiz(state, local_quiz, mark_finished=False)
            show_points_quiz_editor(page, state, local_quiz.get("id"))

        if not has_content:
            do_delete()
            return

        overlay_ref: list[ft.Container | None] = [None]

        def _close_delete_popup():
            overlay = overlay_ref[0] or state.get("_points_quiz_category_delete_overlay")
            overlay_ref[0] = None
            if state.get("_points_quiz_category_delete_overlay") is overlay:
                state.pop("_points_quiz_category_delete_overlay", None)
            if overlay is not None:
                try:
                    while overlay in page.overlay:
                        page.overlay.remove(overlay)
                except Exception:
                    pass
            page.update()

        def on_cancel(ev):
            _close_delete_popup()

        def on_confirm_delete(ev):
            _close_delete_popup()
            do_delete()

        overlay = ft.Container(
            expand=True,
            bgcolor="#000000B8",
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=min(430, int(_page_size(page)[0] - 44)),
                padding=ft.Padding(24, 20, 24, 18),
                border_radius=20,
                bgcolor=theme["question_bg"],
                border=ft.border.Border.all(1.2, theme["border"]),
                shadow=ft.BoxShadow(blur_radius=18, color="#66000000", spread_radius=0),
                content=ft.Column(
                    [
                        ft.Text("Kategorie löschen?", size=20, weight="w900", color="white"),
                        ft.Text(
                            "Diese Kategorie enthält Inhalte. Wirklich mit allen Fragen löschen?",
                            size=14,
                            color=theme_txt(theme, "secondary"),
                            text_align=ft.TextAlign.LEFT,
                        ),
                        ft.Row(
                            [
                                _game_menu_button("Abbrechen", on_cancel, theme["panel"], width=148, height=40),
                                _game_menu_button("Löschen", on_confirm_delete, theme["danger"], width=148, height=40),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    ],
                    tight=True,
                    spacing=16,
                ),
            ),
        )
        overlay_ref[0] = overlay
        state["_points_quiz_category_delete_overlay"] = overlay
        page.overlay.append(overlay)
        page.update()

    def back_to_hub(e):
        save_quiz(mark_finished=False)
        show_points_quiz_hub(page, state)

    def play_quiz(e):
        save_quiz(mark_finished=points_quiz_is_playable(state.get("editing_points_quiz", quiz)))
        show_points_quiz_team_setup(page, state, state["editing_points_quiz"])

    def finish_quiz(e):
        save_quiz(mark_finished=points_quiz_is_playable(state.get("editing_points_quiz", quiz)))
        show_points_quiz_hub(page, state)

    cell_label_w = 100 if is_landscape_mobile else (92 if is_compact else 120)
    cell_btn_w = 150 if is_landscape_mobile else (140 if is_compact else 180)
    table_spacing = 6 if is_compact else 8
    category_count = len(quiz.get("categories", []))
    table_width = cell_label_w + (category_count * cell_btn_w) + (category_count * table_spacing)
    header_labels = [
        ft.Text(
            (category_fields[idx].value or f"K{idx + 1}").strip() or f"K{idx + 1}",
            color=theme_txt(theme, "secondary"),
            text_align=ft.TextAlign.CENTER,
        )
        for idx in range(category_count)
    ]
    cell_rows = []
    for q_idx, points in enumerate(POINTS_QUIZ_POINT_VALUES):
        row_controls = [
            ft.Container(
                width=cell_label_w,
                alignment=ft.Alignment(-1, 0),
                content=ft.Text(f"{points} Punkte", color=theme["gold"], weight="bold"),
            )
        ]
        for cat_idx, category in enumerate(quiz.get("categories", [])):
            entry = category.get("questions", [])[q_idx]
            ready = bool(str(entry.get("question", "")).strip() and str(entry.get("answer", "")).strip())
            row_controls.append(
                _game_menu_button(
                    _question_preview(entry),
                    lambda e, c=cat_idx, q=q_idx: show_points_quiz_cell_editor(page, state, c, q),
                    theme["success"] if ready else theme["accent"],
                    width=cell_btn_w,
                    height=36,
                )
            )
        cell_rows.append(ft.Row(row_controls, spacing=table_spacing, wrap=False))

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000092"),
                    ft.Container(
                        expand=True,
                        padding=20,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            [
                                ft.Text("Punkte-Quiz bearbeiten", size=28, weight="w900", color="white"),
                                title_field,
                                ft.Row(
                                    [
                                        ft.Stack(
                                            [
                                                field,
                                                ft.Container(
                                                    top=-4,
                                                    right=-4,
                                                    visible=len(category_fields) > POINTS_QUIZ_MIN_CATEGORIES,
                                                    content=ft.Container(
                                                        width=18,
                                                        height=18,
                                                        border_radius=9,
                                                        bgcolor="#B91C1C",
                                                        alignment=ft.Alignment(0, 0),
                                                        on_click=lambda e, i=idx: remove_category(i),
                                                        content=ft.Text("×", size=11, color="white", weight="bold"),
                                                    ),
                                                ),
                                            ],
                                            width=category_field_width,
                                            height=category_stack_height,
                                        )
                                        for idx, field in enumerate(category_fields)
                                    ] + [
                                        _game_menu_button("+ Kategorie", add_category, theme["accent"], width=action_btn_small_width, height=42)
                                    ],
                                    spacing=10,
                                    wrap=True,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                ft.Container(
                                    width=min(1220, int(_page_size(page)[0] - 28)),
                                    padding=18,
                                    bgcolor="#08120DE8",
                                    border_radius=20,
                                    border=ft.border.Border.all(1.4, theme["border"]),
                                    content=ft.Column(
                                        [
                                            ft.Text("Felder der Tafel", size=18, weight="bold", color="white"),
                                            ft.Row(
                                                [
                                                    ft.Container(
                                                        width=table_width,
                                                        content=ft.Column(
                                                            [
                                                                ft.Row(
                                                                    [ft.Container(width=cell_label_w)] + [
                                                                        ft.Container(
                                                                            width=cell_btn_w,
                                                                            alignment=ft.Alignment(0, 0),
                                                                            content=header_labels[idx],
                                                                        )
                                                                        for idx in range(category_count)
                                                                    ],
                                                                    spacing=table_spacing,
                                                                    wrap=False,
                                                                ),
                                                            ] + cell_rows,
                                                            spacing=10,
                                                        ),
                                                    )
                                                ],
                                                scroll=ft.ScrollMode.AUTO,
                                            ),
                                        ],
                                        spacing=10,
                                    ),
                                ),
                                ft.Row(
                                    [
                                        _game_menu_button("Speichern / Zurück", back_to_hub, theme["success"], width=action_btn_width, height=42),
                                        _game_menu_button("Jetzt spielen", play_quiz, theme["gold"], width=action_btn_width, height=42),
                                        _game_menu_button("Fertig", finish_quiz, theme["accent"], width=action_btn_small_width, height=42),
                                    ],
                                    spacing=12,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=16,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_points_quiz_cell_editor(page: ft.Page, state: dict, cat_idx: int, q_idx: int):
    _set_resize_view(state, show_points_quiz_cell_editor, cat_idx, q_idx)
    theme = get_theme(state)
    page_w, _ = _page_size(page)
    panel_width = min(760, max(320, int(page_w - 36)))
    field_width = max(260, panel_width - 64)
    btn_width = 180 if page_w < 900 else 220
    media_card_width = 170 if page_w < 900 else 200
    media_card_height = 96 if page_w < 900 else 112
    quiz = state.get("editing_points_quiz")
    if not quiz:
        show_points_quiz_hub(page, state)
        return
    quiz = normalize_points_quiz(quiz)
    state["editing_points_quiz"] = quiz
    category = quiz["categories"][cat_idx]
    entry = dict(category["questions"][q_idx])
    question_media = _normalize_points_quiz_media_list(entry.get("question_media", []))
    answer_media = _normalize_points_quiz_media_list(entry.get("answer_media", []))

    _cleanup_points_quiz_cell_media_pickers(page, state)

    question_field = ft.TextField(
        label="Frage",
        value=entry.get("question", ""),
        multiline=True,
        min_lines=3,
        max_lines=5,
        expand=True,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )
    answer_field = ft.TextField(
        label="Richtige Antwort / Auflösung",
        value=entry.get("answer", ""),
        multiline=True,
        min_lines=2,
        max_lines=4,
        expand=True,
        bgcolor=theme["question_bg"],
        color=theme["question_text"],
        border_color=theme["border"],
    )

    def _sync_editor_draft():
        quiz_local = state.get("editing_points_quiz", quiz)
        quiz_local["categories"][cat_idx]["questions"][q_idx]["question"] = (question_field.value or "").strip()
        quiz_local["categories"][cat_idx]["questions"][q_idx]["answer"] = (answer_field.value or "").strip()
        quiz_local["categories"][cat_idx]["questions"][q_idx]["question_media"] = _normalize_points_quiz_media_list(question_media)
        quiz_local["categories"][cat_idx]["questions"][q_idx]["answer_media"] = _normalize_points_quiz_media_list(answer_media)
        state["editing_points_quiz"] = upsert_points_quiz(state, quiz_local, mark_finished=False)

    question_field.on_change = lambda e: _sync_editor_draft()
    answer_field.on_change = lambda e: _sync_editor_draft()

    question_media_column = ft.Column(spacing=8, width=field_width)
    answer_media_column = ft.Column(spacing=8, width=field_width)

    def _media_plus_button(on_click):
        return ft.Container(
            width=36,
            height=36,
            border_radius=18,
            bgcolor=theme["accent"],
            border=ft.border.Border.all(1.2, theme["gold"]),
            alignment=ft.Alignment(0, 0),
            content=ft.Text("+", size=22, weight="w900", color="white"),
            on_click=on_click,
            tooltip="Datei hinzufügen",
            shadow=ft.BoxShadow(blur_radius=8, color="#44000000"),
        )

    def _media_thumb(item: dict) -> ft.Control:
        src = str(item.get("src", "")).strip()
        kind = item.get("kind", "image")
        if kind == "video":
            if FletVideo and VideoMedia:
                return ft.Container(
                    width=media_card_width,
                    height=media_card_height,
                    border_radius=10,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=FletVideo(
                        width=media_card_width,
                        height=media_card_height,
                        playlist=[VideoMedia(src)],
                        autoplay=False,
                        muted=True,
                        fit=ft.BoxFit.COVER,
                        show_controls=False,
                        aspect_ratio=16 / 9,
                    ),
                )
            return ft.Container(
                width=media_card_width,
                height=media_card_height,
                border_radius=10,
                bgcolor="#111827",
                alignment=ft.Alignment(0, 0),
                content=ft.Text("Video", color="white", weight="bold"),
            )
        return ft.Image(src=src, width=media_card_width, height=media_card_height, fit=ft.BoxFit.COVER, border_radius=10)

    def _build_media_rows(items: list[dict], kind: str) -> list[ft.Control]:
        if not items:
            return []

        rows: list[ft.Control] = []
        for idx, item in enumerate(items):
            rows.append(
                ft.Container(
                    padding=8,
                    border_radius=12,
                    bgcolor=theme["panel"],
                    border=ft.border.Border.all(1, theme["border"]),
                    content=ft.Row(
                        [
                            _media_thumb(item),
                            ft.Column(
                                [
                                    ft.Text(item.get("name", "Datei"), size=12, color="white", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text("Bild" if item.get("kind") == "image" else "Video", size=11, color=theme_txt(theme, "secondary")),
                                    _game_menu_button(
                                        "Entfernen",
                                        lambda e, i=idx, t=kind: _remove_media_item(t, i),
                                        theme["danger"],
                                        width=110,
                                        height=34,
                                    ),
                                ],
                                spacing=6,
                                expand=True,
                                alignment=ft.MainAxisAlignment.START,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                )
            )
        return rows

    def _refresh_media_lists(update_page: bool = True):
        question_media_column.controls = _build_media_rows(question_media, "question")
        answer_media_column.controls = _build_media_rows(answer_media, "answer")
        if update_page:
            page.update()

    def _remove_media_item(target: str, index: int):
        items = question_media if target == "question" else answer_media
        if 0 <= index < len(items):
            items.pop(index)
            _refresh_media_lists(update_page=True)
            _sync_editor_draft()

    async def _pick_media_for_target(target: str):
        target_items = question_media if target == "question" else answer_media
        quiz_id = str(quiz.get("id") or new_points_quiz_id())
        added_items, failed, error_msg = await _points_quiz_pick_and_upload_media(page, quiz_id)
        if error_msg:
            page.snack_bar = ft.SnackBar(content=ft.Text(error_msg), bgcolor=theme["danger"])
            page.snack_bar.open = True
            page.update()
            return
        if not added_items and failed == 0:
            return
        target_items.extend(added_items)
        target_items[:] = _normalize_points_quiz_media_list(target_items)
        _sync_editor_draft()
        _refresh_media_lists(update_page=False)
        page.snack_bar = ft.SnackBar(
            content=ft.Text(
                f"{len(added_items)} Datei(en) hinzugefügt."
                if failed == 0
                else f"{len(added_items)} hinzugefügt, {failed} nicht unterstützt.",
            ),
            bgcolor=theme["success"] if failed == 0 else theme["danger"],
        )
        page.snack_bar.open = True
        page.update()

    def add_question_media(e):
        e.page.run_task(_pick_media_for_target, "question")

    def add_answer_media(e):
        e.page.run_task(_pick_media_for_target, "answer")

    def back_to_editor(e):
        _cleanup_points_quiz_cell_media_pickers(page, state)
        show_points_quiz_editor(page, state, quiz.get("id"))

    def save_cell(e):
        if not (question_field.value or "").strip() or not (answer_field.value or "").strip():
            page.snack_bar = ft.SnackBar(content=ft.Text("Bitte Frage und richtige Antwort ausfüllen."))
            page.snack_bar.open = True
            page.update()
            return
        quiz_local = state.get("editing_points_quiz", quiz)
        quiz_local["categories"][cat_idx]["questions"][q_idx]["question"] = question_field.value.strip()
        quiz_local["categories"][cat_idx]["questions"][q_idx]["answer"] = answer_field.value.strip()
        quiz_local["categories"][cat_idx]["questions"][q_idx]["question_media"] = _normalize_points_quiz_media_list(question_media)
        quiz_local["categories"][cat_idx]["questions"][q_idx]["answer_media"] = _normalize_points_quiz_media_list(answer_media)
        state["editing_points_quiz"] = upsert_points_quiz(
            state,
            quiz_local,
            mark_finished=not bool(quiz_local.get("is_draft", True)),
        )
        _cleanup_points_quiz_cell_media_pickers(page, state)
        show_points_quiz_editor(page, state, quiz_local.get("id"))

    _refresh_media_lists(update_page=False)
    _sync_editor_draft()

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000092"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=20,
                        content=ft.Container(
                            width=panel_width,
                            padding=24,
                            bgcolor="#08120DE8",
                            border_radius=22,
                            border=ft.border.Border.all(1.4, theme["gold"]),
                            content=ft.Column(
                                [
                                    ft.Text(f"{category['name']} · {POINTS_QUIZ_POINT_VALUES[q_idx]} Punkte", size=24, weight="w900", color="white"),
                                    ft.Container(
                                        width=field_width,
                                        content=ft.Row(
                                            [
                                                question_field,
                                                _media_plus_button(add_question_media),
                                            ],
                                            spacing=8,
                                            vertical_alignment=ft.CrossAxisAlignment.START,
                                        ),
                                    ),
                                    question_media_column,
                                    ft.Container(
                                        width=field_width,
                                        content=ft.Row(
                                            [
                                                answer_field,
                                                _media_plus_button(add_answer_media),
                                            ],
                                            spacing=8,
                                            vertical_alignment=ft.CrossAxisAlignment.START,
                                        ),
                                    ),
                                    answer_media_column,
                                    ft.Row(
                                        [
                                            _game_menu_button("Speichern", save_cell, theme["success"], width=btn_width, height=42),
                                            _game_menu_button("Zurück", back_to_editor, theme["danger"], width=btn_width, height=42),
                                        ],
                                        spacing=12,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                ],
                                spacing=14,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ),
                    _game_portal_back_overlay(page, state),
                ],
                expand=True,
            ),
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
    _set_resize_view(state, show_age_selection)
    reset_game_timer(state)
    theme = get_theme(state)
    ui = theme_ui_palette(theme)
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
        state["questions"] = create_game_questions(age, state)
        _remember_generated_questions(state, state["questions"])
        state.pop("selected_jokers", None)
        state.pop("jokers_used_ids", None)
        reset_joker_pick_state(state)
        save_current_game(state)
        launch_game_after_jokers(page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000009f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Wähle deine Altersgruppe", size=26, weight="bold",
                                    color=ui["text"], text_align="center"),
                            ft.Container(height=10),
                            _age_button("🌟  6 – 10 Jahre", "young", ui["card_bg"], choose_age, theme),
                            _age_button("🔥  11 – 16 Jahre", "mid", ui["card_bg"], choose_age, theme),
                            _age_button("⚡  Ab 16 Jahre", "old", ui["card_bg"], choose_age, theme),
                            ft.Container(height=10),
                            ft.TextButton(
                                "← Zurück",
                                on_click=lambda e: show_game_start_menu(
                                    e.page, state, get_saved_game_for_state(state)
                                ),
                                style=ft.ButtonStyle(color=ui["text"]),
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=14),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def _age_button(label: str, data: str, color: str, on_click, theme: dict | None = None) -> ft.Control:
    hover = theme_ui_palette(theme or THEMES["classic"])["hover"] if theme else "#93C5FD"
    border = theme_ui_palette(theme or THEMES["classic"])["card_border"] if theme else "#60A5FA"
    btn = ft.Container(
        content=ft.Text(label, size=20, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
        data=data,
        on_click=on_click,
        bgcolor=color,
        border_radius=50,
        padding=ft.Padding(50, 16, 50, 16),
        shadow=ft.BoxShadow(blur_radius=12, color="#40000000"),
        border=ft.border.Border.all(2, border),
        width=340,
    )
    def on_hover(e):
        hovering = e.data == "true"
        e.control.shadow = ft.BoxShadow(blur_radius=28, color=f"#88{hover[1:]}", spread_radius=2) if hovering else ft.BoxShadow(blur_radius=12, color="#40000000")
        e.control.border = ft.border.Border.all(2.8 if hovering else 2, hover if hovering else border)
        e.control.scale = 1.03 if hovering else 1.0
        e.control.update()
    btn.on_hover = on_hover
    btn.animate_scale = ft.Animation(140, ft.AnimationCurve.EASE_OUT)
    return btn


# ---------- Open main menu ----------
def open_main_menu(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    _set_resize_view(state, open_main_menu)
    _sync_page_route(page, "/")
    page.controls.clear()
    page.add(build_game_portal_view(page, state))
    page.update()


# ---------- Game Screen ----------
def _neon_panel_border(theme: dict, width: int = 2) -> ft.Border:
    return ft.border.Border.all(width, theme["border"])


def _neon_solid_panel(content: ft.Control, theme: dict, expand: bool = True, compact: bool = False) -> ft.Container:
    """Opaque panel so text stays readable on any background."""
    is_nexus = theme.get("label") == "Neon Nexus"
    has_video_bg = _is_video_background(theme.get("game_bg"))
    pad = 6 if compact else 10
    return ft.Container(
        content=content,
        bgcolor="#08120de0" if (is_nexus and has_video_bg) else ("#00000000" if is_nexus else theme.get("panel", "#0c1814")),
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
    has_video_bg = _is_video_background(theme.get("game_bg"))
    return ft.Container(
        content=content,
        width=width,
        bgcolor="#08120de0" if (is_nexus and has_video_bg) else ("#00000000" if is_nexus else theme.get("question_bg", "#FFFFFF")),
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
    state["_question_autosave_ts"] = float(state.get("_question_autosave_ts", 0.0) or 0.0)
    sync_timer_display(page, state)

    async def tick():
        while not state.get("_timer_cancel") and state.get("_timer_active_key") == timer_key:
            now = time.time()
            pause_until = float(state.get("_timer_pause_until") or 0)
            phone_until = float(state.get("phone_until") or 0)
            friend_until = float(state.get("friend_until") or 0)

            # Joker-Countdowns laufen unabhängig vom Frage-Timer
            if pause_until > now:
                sync_timer_display(page, state)
                await asyncio.sleep(0.05)
                continue
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
                try:
                    q = state["questions"][state["question_index"]]
                    record_question_result(state, q, was_correct=False)
                except Exception:
                    pass
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

            last_save = float(state.get("_question_autosave_ts", 0.0) or 0.0)
            if now - last_save >= 6:
                save_current_game(state)
                state["_question_autosave_ts"] = now

    page.run_task(tick)


def render_game_screen(page: ft.Page, state: dict):
    """Unified game UI: timer, question, answers, status, jokers; classic + neon_nexus."""
    _set_resize_view(state, render_game_screen)
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
    question_bg_color = theme_value(theme, "question_bg", "#FFFFFF")
    question, options, correct_idx = state["questions"][state["question_index"]]
    q_num = state["question_index"] + 1
    total_q = len(state["questions"])
    page_w, page_h = _page_size(page)
    is_mobile = page_w < 720
    ui_scale = min(1.0, max(0.72, page_w / 1280))

    def sc(value: int, minimum: int = 1) -> int:
        return max(minimum, int(value * ui_scale))

    is_nexus = theme.get("label") == "Neon Nexus"
    if is_mobile and is_nexus:
        is_nexus = False
    theme_key = _theme_key_from_theme(theme)
    themed_bg_preview = _resolve_theme_background(theme_key, "game", allow_video=bool(FletVideo and VideoMedia and PlaylistMode)) if theme_key else None
    has_themed_video_bg = themed and _is_video_background(themed_bg_preview if themed_bg_preview else theme.get("game_bg"))
    answer_border_default = ft.border.Border.all(
        2,
        (theme.get("border", "#60A5FA") if not has_themed_video_bg else theme.get("gold", "#93C5FD")),
    )

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
                record_question_result(state, (question, options, correct_idx), was_correct=True)
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
                record_question_result(state, (question, options, correct_idx), was_correct=False)
                state["questions_answered"] += 1
                state["game_finished"] = True
                clear_saved_game(state)
                _show_wrong_screen(page, state)

        page.run_task(_next)

    def reset_answer_styles():
        for btn in answer_buttons:
            btn.bgcolor = answer_bg
            btn.border = answer_border_default

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
                    btn.border = answer_border_default
            page.update()

            async def clear_test_feedback():
                await asyncio.sleep(1.4)
                reset_answer_styles()
                state.pop("truefalse_mode", None)
                state.pop("info_hint", None)
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
            content=ft.Text(letter, size=sc(13, 10), weight="bold", color="white"),
            width=sc(30, 22), height=sc(30, 22),
            border_radius=sc(15, 11),
            bgcolor=color,
            alignment=ft.Alignment(0, 0),
        )

        inner = ft.Row([
            letter_ctrl,
            ft.Text(text, size=sc(14 if is_mobile else 15, 11),
                    color=answer_text_color, weight="bold", expand=True,
                    max_lines=2, no_wrap=False),
        ], spacing=sc(8, 6), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        box = ft.Container(
            content=inner,
            data=idx,
            on_click=handle_answer,
            bgcolor=answer_bg,
            border_radius=10,
            padding=ft.Padding(sc(10, 8), sc(10, 8), sc(10, 8), sc(10, 8)),
            border=answer_border_default,
            expand=True,
            visible=idx not in hidden,
            height=None if _is_nexus else sc(56 if not is_mobile else 50, 42),
        )
        def on_hover(e):
            if answers_disabled[0]:
                return
            if e.data == "true":
                e.control.border = ft.border.Border.all(3, theme.get("accent_2", theme["gold"]))
                e.control.shadow = ft.BoxShadow(blur_radius=18, color="#55D946EF", spread_radius=1)
            else:
                e.control.border = answer_border_default
                e.control.shadow = None
            e.control.update()
        box.on_hover = on_hover
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
        size=sc(16, 12), weight="bold",
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
    themed_bg = themed_bg_preview
    bg_image = themed_bg if themed_bg else (theme.get("game_bg") if themed else None)
    has_video_bg = _is_video_background(bg_image)
    if themed and has_video_bg:
        overlay_color = "#000000d6"
        question_text_color = "#F8FAFC"
        answer_text_color = "#F8FAFC"
        answer_bg = "#08121cee"
        question_bg_color = "#08121cee"
    else:
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
        pause_btn_bg = theme.get("panel", "#0f172aee") if has_video_bg else ("#00000000" if is_nexus else theme["danger"])
        pause_btn_border = ft.border.Border.all(2, theme.get("accent", theme["danger"])) if has_video_bg else None
        nexus_settings_btn = ft.Container(
            content=ft.Icon(ft.Icons.SETTINGS, size=14, color=theme.get("accent", theme["danger"])),
            bgcolor=pause_btn_bg,
            border_radius=8,
            border=pause_btn_border,
            padding=ft.Padding(9, 7, 9, 7),
            alignment=ft.Alignment(0, 0),
            on_click=lambda e: show_settings_view(page, state),
            tooltip="Einstellungen",
        )
        nexus_pause_btn = ft.Container(
            content=ft.Row([
                ft.Text("🚪", size=14, color=theme.get("accent", theme["danger"])),
                ft.Text("Pause", size=13, weight="bold", color=theme.get("accent", theme["danger"])),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: (stop_game_timer(state), save_current_game(state), show_exit_confirmation(page, state)),
            bgcolor=pause_btn_bg, border_radius=8,
            border=pause_btn_border,
            padding=ft.Padding(10, 6, 10, 6), alignment=ft.Alignment(0, 0),
        )
        nexus_exit_btn = ft.Row([
            nexus_settings_btn,
            nexus_pause_btn,
        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER)
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
    classic_panel_border = None if (themed and has_video_bg) else ft.border.Border.all(2, theme["border"])
    ladder_panel = build_money_ladder(state, compact=is_mobile)

    # Pause / exit button
    pause_btn_bg = theme.get("panel", "#0f172aee") if has_video_bg else theme["danger"]
    pause_btn_border = ft.border.Border.all(2, theme.get("accent", theme["danger"])) if has_video_bg else None
    settings_btn = ft.Container(
        content=ft.Icon(ft.Icons.SETTINGS, size=sc(12, 10), color=theme.get("accent", "#FFFFFF") if has_video_bg else "white"),
        bgcolor=pause_btn_bg,
        border_radius=6,
        padding=ft.Padding(sc(10, 8), sc(7, 6), sc(10, 8), sc(7, 6)),
        border=pause_btn_border,
        on_click=lambda e: show_settings_view(page, state),
        tooltip="Einstellungen",
    )
    exit_btn = ft.Container(
        content=ft.Row([
            ft.Text("🚪", size=sc(12, 10), color=theme.get("accent", "#FFFFFF") if has_video_bg else "white"),
            ft.Text("Pause", size=sc(12, 10), weight="bold", color=theme.get("accent", "#FFFFFF") if has_video_bg else "white"),
        ], spacing=sc(5, 4), tight=True),
        on_click=lambda e: (stop_game_timer(state), save_current_game(state), show_exit_confirmation(page, state)),
        bgcolor=pause_btn_bg,
        border_radius=6,
        padding=ft.Padding(sc(12, 9), sc(7, 6), sc(12, 9), sc(7, 6)),
        border=pause_btn_border,
    )

    # Top bar: [Pause btn] + [timer bar + countdown]
    top_bar = ft.Row([
        settings_btn,
        exit_btn,
        ft.Container(
            content=ft.Row([
                ft.Container(content=timer_bar, expand=True),
                ft.Container(content=timer_text, width=sc(36, 28), alignment=ft.Alignment(1, 0)),
            ], spacing=sc(8, 6), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            bgcolor=question_bg_color,
            border_radius=6,
            padding=ft.Padding(sc(10, 8), sc(7, 6), sc(10, 8), sc(7, 6)),
            border=classic_panel_border,
        ),
    ], spacing=sc(10, 8), vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # Question panel
    question_panel = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text(f"FRAGE {q_num}", size=sc(11, 9), weight="bold", color="#001a0a"),
                bgcolor=theme["gold"], border_radius=4,
                padding=ft.Padding(sc(8, 6), sc(3, 2), sc(8, 6), sc(3, 2)), alignment=ft.Alignment(0, 0),
            ),
            ft.Text(question, size=sc(16 if is_mobile else 18, 13), weight="bold",
                    color=question_text_color, text_align=ft.TextAlign.CENTER,
                    max_lines=4, no_wrap=False),
        ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=question_bg_color,
        border_radius=10,
        padding=ft.Padding(sc(16, 12), sc(12, 10), sc(16, 12), sc(12, 10)),
        border=classic_panel_border,
    )

    # Answer grid (2x2 on all sizes for better mobile readability)
    answers_grid = ft.Column([
        ft.Row([answer_boxes[0], answer_boxes[1]], spacing=8 if is_mobile else 10),
        ft.Row([answer_boxes[2], answer_boxes[3]], spacing=8 if is_mobile else 10),
    ], spacing=8 if is_mobile else 10)

    # Status bar (question number + money)
    status_bar = ft.Container(
        content=ft.Row([
            ft.Text(f"Frage {q_num} von {total_q}", size=13,
                    color=theme_txt(theme, "secondary"), weight="bold"),
            ft.Text(f"◆ {state.get('money', '0 €')}", size=14,
                    color=theme["gold"], weight="bold"),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=question_bg_color,
        border_radius=8,
        padding=ft.Padding(14, 8, 14, 8),
        border=classic_panel_border,
    )
    info_hint = state.get("info_hint")
    if info_hint:
        status_bar.content = ft.Column(
            [
                status_bar.content,
                ft.Text(info_hint, size=11, color=theme.get("accent", "#93C5FD"), text_align=ft.TextAlign.CENTER),
            ],
            spacing=4,
        )

    # Joker bar — always its own row, never overlaps timer or question
    has_jokers = len(state.get("selected_jokers", [])) > 0
    joker_bar = ft.Container(
        content=build_game_joker_bar(page, state, theme, ctx),
        bgcolor=question_bg_color,
        border_radius=8,
        padding=ft.Padding(10, 10, 10, 10),
        border=classic_panel_border,
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
        save_current_game(state)
        state["_question_autosave_ts"] = time.time()
        play_tts(page, text, state)

    render_game_screen(page, state)


def show_exit_confirmation(page: ft.Page, state: dict):
    theme = get_theme(state)
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
        _go_home(e.page, state)

    def on_resume_game(e):
        show_next_question(e.page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000096"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Spiel unterbrechen?", size=24, weight="bold", color="white", text_align="center"),
                                    ft.Container(height=10),
                                    ft.Text(info_text, size=16, color=theme_txt(theme, "secondary"), text_align="center"),
                                    ft.Container(height=20),
                                    ft.Row([
                                        _theme_action_button("Ja, beenden", theme, on_confirm_exit, width=170, bg=theme.get("danger", "#C0392B")),
                                        _theme_action_button("Nein, weiter", theme, on_resume_game, width=170, bg=theme.get("success", "#2ECC71")),
                                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
                                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                                bgcolor=theme.get("panel", "#1A0A30"),
                                border_radius=20,
                                padding=30,
                                border=ft.border.Border.all(2, theme.get("border", "#9B59B6")),
                                width=420,
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


# ---------- Result Screens ----------
def _show_correct_screen(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    theme = get_theme(state)

    def next_q(e):
        show_next_question(e.page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000096"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("✅", size=80),
                            ft.Text("RICHTIG!", size=48, weight="black", color="white"),
                            ft.Text(f"Du gewinnst: {state.get('money', '?')}",
                                    size=22, color=theme["gold"], weight="bold"),
                            ft.Container(height=20),
                            _theme_action_button("➡  Nächste Frage", theme, next_q, width=280, bg=theme.get("success", "#27AE60")),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=12),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def _show_wrong_screen(page: ft.Page, state: dict):
    _clear_themed_game_resize(state)
    theme = get_theme(state)
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

    # Check achievements after all stats, including daily challenge stats, are updated
    _check_and_show_achievements(page, state, money, won=False)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#00000096"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("❌", size=80),
                            ft.Text("FALSCH!", size=48, weight="black", color="white"),
                            ft.Text(f"Dein Gewinn: {state.get('money', '0 €')}",
                                    size=22, color=theme["gold"], weight="bold"),
                            ft.Container(height=20),
                            _theme_action_button("🏠  Zurück zum Menü", theme, lambda e: _go_home(e.page, state), width=320, bg=theme.get("danger", "#C0392B")),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=12),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def _check_and_show_achievements(page: ft.Page, state: dict, money: str, won: bool, show_snackbar: bool = True):
    db = load_db()
    email = state.get("current_user_email")
    if email and email in db["users"]:
        user = db["users"][email]
        stats = user["stats"]
        history = user.get("game_history", [])
        unlocked = user.setdefault("unlocked_achievements", [])
        newly_unlocked = []

        games_played = stats.get("games_played", 0)
        games_won = stats.get("games_won", 0)
        best_streak = stats.get("best_streak", 0)
        jokers_total = stats.get("jokers_used", 0)
        perfect_games = stats.get("perfect_games", 0)
        highest_money_level = stats.get("highest_money_level", -1)
        correct_answers = stats.get("correct_answers", 0)
        daily_games_played = stats.get("daily_games_played", 0)
        daily_best_streak = stats.get("daily_best_streak", 0)
        has_purist_win = any(entry.get("won") and entry.get("jokers_used", 0) == 0 for entry in history)

        _unlock_achievement(unlocked, newly_unlocked, "first_game", "Erster Schritt", games_played >= 1)
        _unlock_achievement(unlocked, newly_unlocked, "quiz_fan", "Quiz-Fan", games_played >= 5)
        _unlock_achievement(unlocked, newly_unlocked, "marathon", "Marathon", games_played >= 10)
        _unlock_achievement(unlocked, newly_unlocked, "veteran", "Veteran", games_played >= 25)
        _unlock_achievement(unlocked, newly_unlocked, "legend_50", "Legende", games_played >= 50)

        _unlock_achievement(unlocked, newly_unlocked, "first_win", "Siegertyp", games_won >= 1)
        _unlock_achievement(unlocked, newly_unlocked, "streak_3", "Heißlauf", best_streak >= 3)
        _unlock_achievement(unlocked, newly_unlocked, "streak_5", "Unaufhaltbar", best_streak >= 5)

        _unlock_achievement(unlocked, newly_unlocked, "purist", "Purist", has_purist_win)
        _unlock_achievement(unlocked, newly_unlocked, "joker_friend", "Jokerfreund", jokers_total >= 1)
        _unlock_achievement(unlocked, newly_unlocked, "joker_master", "Joker-Meister", jokers_total >= 25)

        _unlock_achievement(unlocked, newly_unlocked, "perfect_round", "Fehlerfrei", perfect_games >= 1)
        _unlock_achievement(unlocked, newly_unlocked, "perfectionist", "Perfektionist", perfect_games >= 3)

        _unlock_achievement(unlocked, newly_unlocked, "money_1000", "Vierstellig", highest_money_level >= 5)
        _unlock_achievement(unlocked, newly_unlocked, "money_32000", "High Roller", highest_money_level >= 10)
        _unlock_achievement(unlocked, newly_unlocked, "money_125000", "Elite-Spieler", highest_money_level >= 12)
        _unlock_achievement(unlocked, newly_unlocked, "millionaire", "Millionär", highest_money_level >= 14)

        _unlock_achievement(unlocked, newly_unlocked, "correct_50", "Schlaufuchs", correct_answers >= 50)
        _unlock_achievement(unlocked, newly_unlocked, "correct_200", "Quizmaschine", correct_answers >= 200)

        _unlock_achievement(unlocked, newly_unlocked, "daily_first", "Tagesstarter", daily_games_played >= 1)
        _unlock_achievement(unlocked, newly_unlocked, "daily_streak_3", "Daily-Serie", daily_best_streak >= 3)
        _unlock_achievement(unlocked, newly_unlocked, "daily_streak_7", "Daily-Champion", daily_best_streak >= 7)

        if newly_unlocked:
            save_db(db)
            if show_snackbar:
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

    # Check achievements after all stats, including daily challenge stats, are updated
    _check_and_show_achievements(page, state, money, won=True)

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
                    on_click=lambda e: _go_home(e.page, state),
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Anmelden", size=30, weight="bold", color="white"),
                            ft.Container(height=10),
                            ft.Container(
                                content=ft.Column([
                                    email_input,
                                    password_input,
                                    remember_checkbox,
                                    _theme_action_button("Einloggen", theme, on_login, width=220, bg=theme["success"]),
                                    _theme_action_button("Registrieren", theme, on_register, width=220, bg=theme["accent"]),
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
                                on_click=lambda e: open_main_menu(e.page, state),
                                style=ft.ButtonStyle(color="white"),
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=14),
                    ),
                ],
                expand=True,
            )
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
    theme_key = _theme_key_from_theme(theme)
    title_color = theme["gold"] if theme_key in ("royal",) else theme_txt(theme, "primary")
    email = state.get("current_user_email")
    logged_in = bool(email)
    settings = get_user_settings(state)

    def update_setting(key: str, value):
        if logged_in and email:
            db = load_db()
            if email in db.get("users", {}):
                ensure_user_settings(db, email)
                db["users"][email]["settings"][key] = value
                save_db(db)
        state.setdefault("settings", DEFAULT_USER_SETTINGS.copy())
        state["settings"][key] = value

    async def sync_audio_after_change():
        await _sync_bg_music_async(page, state)

    def set_setting_and_sync(key: str, value):
        update_setting(key, value)
        page.run_task(sync_audio_after_change)

    menu_items = [
        ft.Text("Einstellungen", size=30, weight="bold", color=title_color),
        ft.Container(height=10),
        ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Audio", size=18, weight="bold", color=theme["gold"]),
                        ft.Switch(
                            label="Sound allgemein",
                            value=bool(settings.get("play_audio", True)),
                            on_change=lambda e: set_setting_and_sync("play_audio", bool(e.control.value)),
                            active_color=theme["accent"],
                        ),
                        ft.Switch(
                            label="Hintergrundmusik",
                            value=bool(settings.get("background_music", True)),
                            on_change=lambda e: set_setting_and_sync("background_music", bool(e.control.value)),
                            active_color=theme["accent"],
                        ),
                        ft.Text(
                            "Sound umfasst TTS, Effekte und Hintergrundmusik. Du kannst Musik hier separat stummschalten.",
                            size=11,
                            color=theme_txt(theme, "secondary"),
                            text_align="center",
                        ),
                    ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=300,
                    padding=16,
                    bgcolor=theme["panel"],
                    border_radius=16,
                    border=ft.border.Border.all(1.5, theme["border"]),
                ),
                _theme_action_button("Statistiken", theme, lambda e: show_stats(e.page, state), width=240),
                _theme_action_button("Design", theme, lambda e: show_design_view(e.page, state) if logged_in else show_login_view(e.page, state), width=240),
                _theme_action_button("Freunde", theme, lambda e: show_friends_view(e.page, state) if logged_in else show_login_view(e.page, state), width=240),
                _theme_action_button("Profil bearbeiten", theme, lambda e: show_edit_profile_view(e.page, state) if logged_in else show_login_view(e.page, state), width=240),
                ft.Text(
                    "Melde dich an, um Designs pro Account zu speichern." if not logged_in else f"Konto: {email}",
                    size=12,
                    color=theme_txt(theme, "secondary"),
                    text_align="center",
                ),
            ] + ([
                ft.Container(height=4),
                _theme_action_button("🚪 Abmelden", theme, lambda e: page.run_task(_do_logout, page, state), width=240),
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            menu_items,
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=14,
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()


def show_design_view(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    logged_in = bool(email and email in db.get("users", {}))
    if logged_in:
        ensure_user_settings(db, email)
        ensure_unlocked_themes(db["users"][email])
        save_db(db)
        current_theme = db["users"][email].get("settings", {}).get("theme", "classic")
        unlocked_themes = set(get_unlocked_theme_keys(db["users"][email]))
        if current_theme not in unlocked_themes:
            current_theme = "classic"
            db["users"][email]["settings"]["theme"] = "classic"
            save_db(db)
    else:
        current_theme = get_user_settings(state).get("theme", "classic")
        unlocked_themes = {"classic", "neon_nexus"}
    theme = get_theme(state)
    status_text = ft.Text("", size=13, text_align="center")

    def choose_theme(theme_key: str):
        def _handler(e):
            if theme_key not in THEMES:
                return
            if logged_in:
                db_current = load_db()
                if email in db_current.get("users", {}):
                    ensure_user_settings(db_current, email)
                    ensure_unlocked_themes(db_current["users"][email])
                    if theme_key not in set(get_unlocked_theme_keys(db_current["users"][email])):
                        status_text.value = "Dieses Design ist noch nicht gekauft."
                        status_text.color = THEMES["classic"]["danger"]
                        e.page.update()
                        return
                    db_current["users"][email]["settings"]["theme"] = theme_key
                    save_db(db_current)
            state.setdefault("settings", DEFAULT_USER_SETTINGS.copy())
            state["settings"]["theme"] = theme_key
            status_text.value = "Design gespeichert."
            status_text.color = THEMES[theme_key]["success"]
            show_design_view(e.page, state)
        return _handler

    cards = []
    for key, value in THEMES.items():
        if key not in unlocked_themes:
            continue
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=20,
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
                                on_click=lambda e: show_portal_settings(e.page, state),
                                style=ft.ButtonStyle(color="white"),
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14, scroll=ft.ScrollMode.AUTO),
                    ),
                ],
                expand=True,
            ),
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
        except Exception:
            pass
    page.dialog = dlg
    dlg.open = True
    try:
        if dlg not in page.overlay:
            page.overlay.append(dlg)
    except Exception:
        pass
    page.update()


def close_page_dialog(page: ft.Page, dlg: ft.AlertDialog):
    if hasattr(page, "close"):
        try:
            page.close(dlg)
        except Exception:
            pass
    try:
        dlg.open = False
    except Exception:
        pass
    try:
        if getattr(page, "dialog", None) is dlg:
            page.dialog = None
    except Exception:
        pass
    try:
        while dlg in page.overlay:
            page.overlay.remove(dlg)
    except Exception:
        pass
    page.update()


def force_close_all_dialogs(page: ft.Page):
    """Best-effort close for stubborn dialogs across Flet versions."""
    try:
        current = getattr(page, "dialog", None)
        if isinstance(current, ft.AlertDialog):
            current.open = False
    except Exception:
        pass
    try:
        page.dialog = None
    except Exception:
        pass
    try:
        overlays = list(getattr(page, "overlay", []) or [])
        for overlay in overlays:
            if isinstance(overlay, ft.AlertDialog):
                try:
                    overlay.open = False
                except Exception:
                    pass
                try:
                    page.overlay.remove(overlay)
                except Exception:
                    pass
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass


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


def close_all_dialogs(page: ft.Page):
    """Close all open dialogs on the page."""
    # Close dialog if set
    if hasattr(page, "dialog") and page.dialog:
        close_page_dialog(page, page.dialog)
    
    # Close all AlertDialog overlays
    overlays_to_remove = []
    for overlay in page.overlay:
        if isinstance(overlay, ft.AlertDialog):
            overlays_to_remove.append(overlay)
    
    for overlay in overlays_to_remove:
        close_page_dialog(page, overlay)


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
    ensure_avatar_defaults(friend)
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
            overlay = dlg_ref[0]
            if overlay in page.overlay:
                page.overlay.remove(overlay)
            page.update()

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

    # Create a simple overlay container instead of AlertDialog
    overlay = ft.Container(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
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
                ft.Divider(color=theme["border"], height=1),
                ft.Text("Was möchtest du tun?", size=13, color="#CCCCCC"),
                ft.Text(duel_hint, size=12, color=theme["gold"], visible=bool(duel_hint)),
                menu_button("👤 Profil ansehen", theme["accent"], on_stats),
                menu_button(
                    "⚔️ Deine Runde spielen" if can_play_opponent else (
                        "⚔️ Duell fortsetzen" if can_resume else "⚔️ Herausfordern"
                    ),
                    theme["gold"],
                    on_challenge,
                    disabled=bool(active_duel and not can_resume and not can_play_opponent),
                ),
                menu_button("❌ Freund entfernen", theme["danger"], on_remove),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Text(
                        "Schließen",
                        size=14,
                        color="#CCCCCC",
                        weight=ft.FontWeight.BOLD,
                    ),
                    on_click=lambda e: close_dlg(),
                    ink=True,
                    padding=ft.Padding(16, 8, 16, 8),
                    alignment=ft.Alignment(1, 0),
                ),
            ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            bgcolor=theme["panel"],
            border_radius=16,
            width=320,
        ),
        bgcolor="#000000B3",
        alignment=ft.Alignment(0, 0),
        padding=20,
    )
    dlg_ref[0] = overlay
    page.overlay.append(overlay)
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
    # Close all AlertDialog overlays to ensure any open dialogs are closed
    overlays_to_remove = []
    for overlay in page.overlay:
        if isinstance(overlay, ft.AlertDialog):
            overlays_to_remove.append(overlay)
    for overlay in overlays_to_remove:
        if overlay in page.overlay:
            page.overlay.remove(overlay)
    if hasattr(page, "dialog"):
        page.dialog = None
    page.update()
    
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, -0.05),
                        padding=20,
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
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()



def show_friend_stats_view(page: ft.Page, state: dict, friend_email: str):
    # Close all AlertDialog overlays to ensure any open dialogs are closed
    overlays_to_remove = []
    for overlay in page.overlay:
        if isinstance(overlay, ft.AlertDialog):
            overlays_to_remove.append(overlay)
    for overlay in overlays_to_remove:
        if overlay in page.overlay:
            page.overlay.remove(overlay)
    if hasattr(page, "dialog"):
        page.dialog = None
    page.update()
    
    theme = get_theme(state)
    db = load_db()
    friend = db.get("users", {}).get(friend_email)
    if not friend:
        show_friends_view(page, state)
        return

    ensure_avatar_defaults(friend)
    stats = friend.get("stats", {})
    ensure_stats_defaults(stats)
    friend_title = str(friend.get("active_title") or "Neuling")
    friend_name = friend.get("name", friend_email)
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Freundesprofil", size=30, weight="bold", color="white"),
                            ft.Container(
                                width=min(760, int(_page_size(page)[0] - 24)),
                                border_radius=14,
                                bgcolor="#060d09e8",
                                border=ft.border.Border.all(1.5, theme.get("border", "#334155")),
                                padding=14,
                                content=ft.Row(
                                    [
                                        ft.Container(
                                            width=240,
                                            content=ft.Column(
                                                [
                                                    build_avatar_figure(friend, theme, size=180, angle_deg=18),
                                                    ft.Text(friend_name, size=18, weight="bold", color=theme_txt(theme, "primary"), text_align=ft.TextAlign.CENTER),
                                                    ft.Text(friend_title, size=13, color=theme.get("gold", "#F59E0B"), text_align=ft.TextAlign.CENTER),
                                                ],
                                                spacing=6,
                                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            ),
                                        ),
                                        ft.Container(width=12),
                                        ft.Container(content=card, expand=True),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                ),
                            ),
                            ft.TextButton(
                                "Zurück",
                                on_click=lambda e: show_friends_view(e.page, state),
                                style=ft.ButtonStyle(color="white"),
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=14),
                    ),
                ],
                expand=True,
            ),
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
    ensure_unlocked_themes(db["users"][email])
    save_db(db)
    theme = get_theme(state)
    user_info = db["users"].get(email, {})
    current_name = user_info.get("name", "")
    current_theme = user_info.get("settings", {}).get("theme", "classic")
    unlocked_themes = get_unlocked_theme_keys(user_info)
    if current_theme not in unlocked_themes:
        current_theme = "classic"
    
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
            if key in unlocked_themes
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
            ensure_unlocked_themes(db["users"][email])
            allowed_themes = set(get_unlocked_theme_keys(db["users"][email]))
            selected_theme = theme_dropdown.value if theme_dropdown.value in allowed_themes else "classic"
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("✏️ Profil bearbeiten", size=30, weight="bold", color="white"),
                            ft.Container(height=10),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text(f"Konto: {email}", size=13, color="#E0D0F0"),
                                    name_input,
                                    theme_dropdown,
                                    _theme_action_button("Speichern", theme, on_save, width=150, bg=theme["success"]),
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
                           spacing=14),
                    ),
                ],
                expand=True,
            )
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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20, 12 if is_mobile else 20),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column([
                            ft.Text("Statistiken", size=28 if is_mobile else 32, weight="bold", color="white"),
                            ft.Container(height=10),
                            stats_cards,
                            ft.Container(height=20),
                            _theme_action_button("Zurück", theme, lambda e: open_main_menu(e.page, state), width=200),
                        ], alignment=ft.MainAxisAlignment.CENTER,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=14,
                           scroll=ft.ScrollMode.AUTO),
                    ),
                ],
                expand=True,
            ),
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
    ensure_avatar_defaults(user)
    save_db(db)
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
        price = _shop_price_coins(item)
        if user["stats"].get("shop_coins", 0) >= price:
            user["stats"]["shop_coins"] -= price
            user.setdefault("unlocked_themes", ["classic", "neon_nexus"]).append(item["id"])
            save_db(db)
            build_shop()
        else:
            await flash_insufficient_funds(e.control)

    async def on_buy_title(e, item):
        price = _shop_price_coins(item)
        if user["stats"].get("shop_coins", 0) >= price:
            user["stats"]["shop_coins"] -= price
            user.setdefault("unlocked_titles", ["Neuling"]).append(item["id"])
            save_db(db)
            build_shop()
        else:
            await flash_insufficient_funds(e.control)

    def on_equip_theme(e, theme_id):
        ensure_unlocked_themes(user)
        if theme_id not in set(get_unlocked_theme_keys(user)):
            return
        user["settings"]["theme"] = theme_id
        state["settings"]["theme"] = theme_id
        save_db(db)
        show_shop_screen(page, state)

    def on_equip_title(e, title_id):
        user["active_title"] = title_id
        save_db(db)
        build_shop()

    def build_shop():
        ensure_unlocked_themes(user)
        unlocked_themes = user.get("unlocked_themes", ["classic", "neon_nexus"])
        unlocked_titles = user.get("unlocked_titles", ["Neuling"])
        current_theme = user.get("settings", {}).get("theme", "classic")
        current_title = user.get("active_title", "Neuling")
        coins = user["stats"].get("shop_coins", 0)
        ensure_avatar_defaults(user)
        avatar_open = bool(state.get("shop_avatar_section_open", False))

        card_w = 430 if _page_size(page)[0] > 980 else 330
        theme_cards = []
        for t in SHOP_CATALOG["themes"]:
            is_unlocked = t["id"] in unlocked_themes
            is_equipped = current_theme == t["id"]
            price_coins = _shop_price_coins(t)
            if is_equipped:
                btn = ft.ElevatedButton("Ausgerüstet", disabled=True, color="green")
            elif is_unlocked:
                btn = ft.ElevatedButton("Ausrüsten", on_click=lambda e, tid=t["id"]: on_equip_theme(e, tid))
            else:
                btn = ft.ElevatedButton(f"{price_coins} Münzen", on_click=lambda e, itm=t: page.run_task(on_buy_theme, e, itm))
            
            theme_cards.append(ft.Container(
                content=ft.Column(
                    [
                        ft.Text(t["name"], size=16, weight="bold", color=theme_txt(theme, "primary")),
                        ft.Row([ft.Text(f"Preis: {price_coins} Münzen", size=12, color=theme_txt(theme, "secondary")), ft.Container(expand=True), btn]),
                    ],
                    spacing=6,
                ),
                width=card_w,
                padding=10, border_radius=10, bgcolor=theme["panel"], border=ft.border.Border.all(1, theme["border"])
            ))

        title_cards = []
        for t in SHOP_CATALOG["titles"]:
            is_unlocked = t["id"] in unlocked_titles
            is_equipped = current_title == t["id"]
            price_coins = _shop_price_coins(t)
            if is_equipped:
                btn = ft.ElevatedButton("Ausgerüstet", disabled=True, color="green")
            elif is_unlocked:
                btn = ft.ElevatedButton("Ausrüsten", on_click=lambda e, tid=t["id"]: on_equip_title(e, tid))
            else:
                btn = ft.ElevatedButton(f"{price_coins} Münzen", on_click=lambda e, itm=t: page.run_task(on_buy_title, e, itm))
            
            title_cards.append(ft.Container(
                content=ft.Column(
                    [
                        ft.Text(t["name"], size=16, weight="bold", color=theme_txt(theme, "primary")),
                        ft.Row([ft.Text(f"Preis: {price_coins} Münzen", size=12, color=theme_txt(theme, "secondary")), ft.Container(expand=True), btn]),
                    ],
                    spacing=6,
                ),
                width=card_w,
                padding=10, border_radius=10, bgcolor=theme["panel"], border=ft.border.Border.all(1, theme["border"])
            ))

        avatar_cards = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Avatar-Designs", size=16, weight="bold", color=theme_txt(theme, "primary")),
                        ft.Text("Bald verfügbar - neue Outfits und Kleidungssets.", size=12, color=theme_txt(theme, "secondary")),
                    ],
                    spacing=4,
                ),
                width=card_w,
                padding=10,
                border_radius=8,
                bgcolor=theme["panel"],
                border=ft.border.Border.all(1, theme["border"]),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Kleidung & Accessoires", size=16, weight="bold", color=theme_txt(theme, "primary")),
                        ft.Text("Shop-Käufe für den Avatar sind aktuell deaktiviert.", size=12, color=theme_txt(theme, "secondary")),
                    ],
                    spacing=4,
                ),
                width=card_w,
                padding=10,
                border_radius=8,
                bgcolor=theme["panel"],
                border=ft.border.Border.all(1, theme["border"]),
            ),
        ]

        themes_wrap = ft.Row(theme_cards, wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        titles_wrap = ft.Row(title_cards, wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        avatar_wrap = ft.Row(avatar_cards, wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        _themed_screen_background(page, theme, "#0000008f"),
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment(0, 0),
                            padding=14,
                            content=ft.Container(
                                width=min(980, int(_page_size(page)[0] - 24)),
                                border_radius=16,
                                bgcolor="#060d09f0",
                                border=ft.border.Border.all(2, theme["border"]),
                                padding=16,
                                content=ft.Column([
                                    ft.Row([
                                        ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                                        ft.Text("Shop", size=24, weight="bold", color="white"),
                                        ft.Container(expand=True),
                                        ft.Text(f"Kontostand: {coins} Münzen", size=20, weight="bold", color=theme["gold"]),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Divider(color=theme["border"]),
                                    ft.Text("🎨 Designs", size=20, weight="bold", color="white"),
                                    themes_wrap,
                                    ft.Divider(color=theme["border"]),
                                    ft.Text("🏷️ Titel", size=20, weight="bold", color="white"),
                                    titles_wrap,
                                    ft.Divider(color=theme["border"]),
                                    ft.Row(
                                        [
                                            ft.Text("🧍 Avatar", size=20, weight="bold", color="white"),
                                            ft.Container(expand=True),
                                            _theme_action_button(
                                                "Ausklappen" if not avatar_open else "Einklappen",
                                                theme,
                                                lambda e: state.update({"shop_avatar_section_open": not avatar_open}) or build_shop(),
                                                width=160,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    avatar_wrap if avatar_open else ft.Text("Avatar-Design und Kleidung: bald verfügbar.", color=theme_txt(theme, "secondary")),
                                ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10),
                            ),
                        ),
                    ],
                    expand=True,
                )
            )
        )
        page.update()
    
    build_shop()


def show_achievements_screen(page: ft.Page, state: dict):
    _check_and_show_achievements(page, state, "", won=False, show_snackbar=False)
    db = load_db()
    email = state.get("current_user_email")
    if not email or email not in db["users"]:
        open_main_menu(page, state)
        return
    user = db["users"][email]
    theme = get_theme(state)

    achievements = get_achievement_definitions()
    unlocked = user.get("unlocked_achievements", [])
    unlocked_count = sum(1 for achievement in achievements if achievement["id"] in unlocked)

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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    ft.Container(
                        expand=True,
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                                ft.Text("Erfolge", size=24, weight="bold", color="white"),
                            ]),
                            ft.Text(
                                f"{unlocked_count} / {len(achievements)} Erfolge freigeschaltet",
                                size=14,
                                color=theme_txt(theme, "muted"),
                            ),
                            ft.Column(cards, scroll=ft.ScrollMode.AUTO, expand=True)
                        ])
                    ),
                ],
                expand=True,
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
        state["questions"] = create_game_questions("old", state)
        random.seed() # Reset seed
        _remember_generated_questions(state, state["questions"])

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
            content=ft.Stack(
                [
                    _themed_screen_background(page, theme, "#0000008f"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=20,
                        content=ft.Container(
                            width=min(760, int((_page_size(page)[0]) - 28)),
                            border_radius=16,
                            bgcolor=theme.get("panel", "#111827c0"),
                            border=ft.border.Border.all(2, theme.get("border", "#334155")),
                            padding=20,
                            content=ft.Column([
                                ft.Row([
                                    ft.TextButton("← Zurück", on_click=lambda e: e.page.go("/"), style=ft.ButtonStyle(color="white")),
                                    ft.Text("Daily Challenge", size=24, weight="bold", color="white"),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text("Spiele jeden Tag die exakt gleichen 15 Fragen wie alle anderen Spieler!", color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                                ft.Container(height=12),
                                ft.Row([btn], alignment=ft.MainAxisAlignment.CENTER),
                                ft.Container(height=16),
                                ft.Text("Deine Daily Stats", size=18, weight="bold", color=theme["gold"], text_align=ft.TextAlign.CENTER),
                                ft.Text(f"🔥 Aktueller Streak: {stats.get('daily_current_streak', 0)} Tage", color="white"),
                                ft.Text(f"👑 Bester Streak: {stats.get('daily_best_streak', 0)} Tage", color="white"),
                                ft.Text(f"💰 Bestes Ergebnis: {stats.get('daily_best_result', '0 €')}", color="white"),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        ),
                    ),
                ],
                expand=True,
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
        "settings": DEFAULT_USER_SETTINGS.copy(),
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
        if path == "/wwm":
            open_wwm_main_menu(page, app_state)
        elif path == "/points":
            show_points_quiz_hub(page, app_state)
        elif path == "/shop":
            show_shop_screen(page, app_state)
        elif path == "/achievements":
            show_achievements_screen(page, app_state)
        elif path == "/daily":
            show_daily_challenge_hub(page, app_state)
        else:
            open_main_menu(page, app_state)

    page.on_route_change = on_route_change

    def on_resize(e):
        if app_state.get("_themed_game_active") and uses_themed_game(get_theme(app_state)):
            render_game_screen(page, app_state)
            return
        if _run_resize_view(page, app_state):
            return
        on_route_change(None)

    page.on_resize = on_resize

    # Show main menu immediately so the page is not blank while init runs.
    # We mark app_state so that restore_remembered_login can signal whether
    # it already handled navigation (logged-in) — in that case we skip the
    # second on_route_change that would overwrite the authenticated screen.
    app_state["_init_nav_done"] = False
    app_state["_startup_recovering"] = True

    async def init_task():
        await restore_remembered_login(page, app_state)
        # restore_remembered_login always ends with open_main_menu, so mark done.
        app_state["_init_nav_done"] = True
        check_url_parameters()
        # Only re-run route logic for special deep-link paths.
        route = page.route or "/"
        path = route.split("?")[0]
        if path in ("/wwm", "/points", "/shop", "/achievements", "/daily"):
            on_route_change(None)
        app_state["_startup_recovering"] = False

    page.run_task(init_task)
    # Render a blank/loading screen immediately; init_task will replace it.
    open_main_menu(page, app_state)
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets", upload_dir="assets")
