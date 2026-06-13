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
# ---------- Answer Letters Constant ----------
ANSWER_LETTERS = ["A", "B", "C", "D"]

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
BG_MUSIC_FILE = "hintergrundmusick.mp3"
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
    audio_cls = getattr(ft, "Audio", None)
    if audio_cls is None:
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
                audio = audio_cls(
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
        audio_cls = getattr(ft, "Audio", None)
        if audio_cls is None:
            print("ft.Audio not available in this Flet version - audio disabled")
            return None
        audio_kwargs = {
            "autoplay": True,
            "volume": 0.22,
        }
        music_path = os.path.join(AUDIO_DIR, BG_MUSIC_FILE)
        if os.path.exists(music_path):
            try:
                with open(music_path, "rb") as f:
                    audio_kwargs["src_base64"] = base64.b64encode(f.read()).decode("ascii")
            except Exception:
                audio_kwargs["src"] = f"audio/{BG_MUSIC_FILE}"
        else:
            audio_kwargs["src"] = f"audio/{BG_MUSIC_FILE}"
        release_mode = getattr(ft, "ReleaseMode", None)
        if release_mode is not None and hasattr(release_mode, "LOOP"):
            audio_kwargs["release_mode"] = release_mode.LOOP
        bg = audio_cls(**audio_kwargs)
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
        "questions_path_profiles": [],
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
    ensure_questions_path_defaults(user)
    for key, value in DEFAULT_USER_SETTINGS.items():
        user["settings"].setdefault(key, value)
    ensure_stats_defaults(user["stats"])

    ref.set(user, merge=True)
    return user


def get_page_storage(page: ft.Page):
    return getattr(page, "shared_preferences", None) or getattr(page, "client_storage", None)


async def call_storage_method(method, *args, timeout: float = 2.0):
    try:
        result = method(*args)
        if inspect.isawaitable(result):
            return await asyncio.wait_for(result, timeout=timeout)
        return result
    except Exception:
        return None


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


QUESTIONS_PATH_PROFILE_MIN = 1
QUESTIONS_PATH_PROFILE_MAX = 10
QUESTIONS_PATH_PROFILE_COUNT = QUESTIONS_PATH_PROFILE_MAX
QUESTIONS_PATH_LEVEL_ORDER = [
    "waldpfad",
    "stadtpfad",
    "himmelsroute",
    "geschichtsinsel",
    "technikfjord",
    "sportlagune",
    "kulturbucht",
    "matheklippen",
    "wissenschaftsriff",
    "wirtschaftshafen",
]
QUESTIONS_PATH_DEFAULT_PROFILE_NAME = "Profil"


def _questions_path_default_level_state() -> dict:
    return {
        "node_index": 0,
        "completed_nodes": [],
        "done": False,
        "last_saved_at": None,
    }


def _questions_path_default_profile(index: int) -> dict:
    return {
        "name": f"{QUESTIONS_PATH_DEFAULT_PROFILE_NAME} {index + 1}",
        "selected_age": "mid",
        "progression_mode": "adventure",
        "active_level_index": 0,
        "active_game": None,
        "custom_islands": [],
        "custom_maps": [],
        "map_overrides": {},
        "custom_designs": [],
        "level_progress": {
            map_key: _questions_path_default_level_state() for map_key in QUESTIONS_PATH_LEVEL_ORDER
        },
    }


def ensure_questions_path_defaults(user: dict):
    profiles = user.setdefault("questions_path_profiles", [])
    if not isinstance(profiles, list):
        profiles = []
    normalized = []
    for idx in range(min(len(profiles), QUESTIONS_PATH_PROFILE_MAX)):
        raw = profiles[idx] if idx < len(profiles) and isinstance(profiles[idx], dict) else {}
        profile = _questions_path_default_profile(idx)
        profile["name"] = str(raw.get("name", profile["name"])).strip() or profile["name"]
        profile["selected_age"] = str(raw.get("selected_age", profile["selected_age"])).strip() or profile["selected_age"]
        profile["progression_mode"] = str(raw.get("progression_mode", profile["progression_mode"])).strip() or "adventure"
        profile["active_level_index"] = max(0, min(int(raw.get("active_level_index", 0) or 0), len(QUESTIONS_PATH_LEVEL_ORDER) - 1))
        active_game = raw.get("active_game")
        if isinstance(active_game, dict):
            profile["active_game"] = active_game
        custom_islands = raw.get("custom_islands", [])
        if isinstance(custom_islands, list):
            normalized_islands = []
            for item_idx, item in enumerate(custom_islands[:10]):
                if not isinstance(item, dict):
                    continue
                island = _questions_path_default_custom_island(item_idx)
                island.update(dict(item))
                island["title"] = str(island.get("title", f"Eigene Insel {item_idx + 1}")).strip() or f"Eigene Insel {item_idx + 1}"
                island["subtitle"] = str(island.get("subtitle", "Hier kannst du eigene Fragen sammeln.")).strip() or "Hier kannst du eigene Fragen sammeln."
                island["world_name"] = str(island.get("world_name", f"Welt {item_idx + 1}")).strip() or f"Welt {item_idx + 1}"
                island["world_description"] = str(island.get("world_description", "Gestalte hier deine eigene Fragen-Route.")).strip() or "Gestalte hier deine eigene Fragen-Route."
                try:
                    island["map_x"] = float(island.get("map_x", 20) or 20)
                except Exception:
                    island["map_x"] = 20.0
                try:
                    island["map_y"] = float(island.get("map_y", 20) or 20)
                except Exception:
                    island["map_y"] = 20.0
                try:
                    island["card_scale"] = max(0.8, min(1.8, float(island.get("card_scale", 1.0) or 1.0)))
                except Exception:
                    island["card_scale"] = 1.0
                custom_points = island.get("custom_points", [])
                if isinstance(custom_points, list):
                    cleaned_points = []
                    for point_idx, raw_point in enumerate(custom_points[:10]):
                        if not isinstance(raw_point, dict):
                            continue
                        cleaned_points.append(
                            {
                                "x": max(2, min(96, int(raw_point.get("x", 10) or 10))),
                                "y": max(2, min(96, int(raw_point.get("y", 10) or 10))),
                                "label": str(raw_point.get("label", f"Punkt {point_idx + 1}")).strip() or f"Punkt {point_idx + 1}",
                            }
                        )
                    island["custom_points"] = cleaned_points
                normalized_islands.append(island)
            profile["custom_islands"] = normalized_islands
        map_overrides = raw.get("map_overrides", {})
        if isinstance(map_overrides, dict):
            cleaned_overrides = {}
            for map_key, raw_map in list(map_overrides.items()):
                if not isinstance(raw_map, dict):
                    continue
                map_cfg = dict(QUESTIONS_PATH_MAPS.get(str(map_key), _questions_path_default_custom_map(0)))
                map_cfg.update(raw_map)
                map_cfg["map_key"] = str(map_key)
                map_cfg["title"] = str(map_cfg.get("title", f"Map {map_key}")).strip() or f"Map {map_key}"
                map_cfg["subtitle"] = str(map_cfg.get("subtitle", "Eigener Hintergrund mit frei platzierbaren Punkten.")).strip() or "Eigener Hintergrund mit frei platzierbaren Punkten."
                map_cfg["image"] = str(map_cfg.get("image", "")).strip()
                map_cfg["map_image_src"] = str(map_cfg.get("map_image_src", "")).strip()
                map_cfg["topic"] = str(map_cfg.get("topic", "custom")).strip() or "custom"
                points = list(map_cfg.get("points", []) or [])
                cleaned_points = []
                for point_idx, raw_point in enumerate(points[:20]):
                    if not isinstance(raw_point, dict):
                        continue
                    cleaned_points.append(
                        {
                            "x": max(2, min(96, int(raw_point.get("x", 10) or 10))),
                            "y": max(2, min(96, int(raw_point.get("y", 10) or 10))),
                            "label": str(raw_point.get("label", f"Punkt {point_idx + 1}")).strip() or f"Punkt {point_idx + 1}",
                        }
                    )
                map_cfg["points"] = cleaned_points or _path_nodes([(50, 55)], ["Start"])
                questions = list(map_cfg.get("questions", []) or [])
                map_cfg["questions"] = [_path_question_to_dict(q) for q in questions[:20]] or [_questions_path_default_custom_question(0)]
                cleaned_overrides[str(map_key)] = map_cfg
            profile["map_overrides"] = cleaned_overrides
        else:
            profile["map_overrides"] = {}
        custom_maps = raw.get("custom_maps", [])
        if isinstance(custom_maps, list):
            normalized_maps = []
            for map_idx, raw_map in enumerate(custom_maps[:12]):
                if not isinstance(raw_map, dict):
                    continue
                map_cfg = _questions_path_default_custom_map(map_idx)
                map_cfg.update(dict(raw_map))
                map_cfg["map_key"] = str(map_cfg.get("map_key", f"custom_map_{map_idx + 1}")).strip() or f"custom_map_{map_idx + 1}"
                map_cfg["title"] = str(map_cfg.get("title", f"Eigene Map {map_idx + 1}")).strip() or f"Eigene Map {map_idx + 1}"
                map_cfg["subtitle"] = str(map_cfg.get("subtitle", "Eigener Hintergrund mit frei platzierbaren Punkten.")).strip() or "Eigener Hintergrund mit frei platzierbaren Punkten."
                map_cfg["image"] = str(map_cfg.get("image", "")).strip()
                map_cfg["map_image_src"] = str(map_cfg.get("map_image_src", "")).strip()
                map_cfg["topic"] = "custom"
                map_cfg["points"] = list(map_cfg.get("points", []) or [])
                if not map_cfg["points"]:
                    map_cfg["points"] = _path_nodes([(50, 55)], ["Start"])
                map_cfg["questions"] = [_path_question_to_dict(q) for q in list(map_cfg.get("questions", []) or [])[:20]] or [_questions_path_default_custom_question(0)]
                normalized_maps.append(map_cfg)
            profile["custom_maps"] = normalized_maps
        else:
            profile["custom_maps"] = []
        custom_designs = raw.get("custom_designs", [])
        if isinstance(custom_designs, list):
            profile["custom_designs"] = [str(item).strip() for item in custom_designs if str(item).strip()][:12]
        level_progress = raw.get("level_progress", {})
        if not isinstance(level_progress, dict):
            level_progress = {}
        for map_key in QUESTIONS_PATH_LEVEL_ORDER:
            raw_level = level_progress.get(map_key, {})
            level_state = _questions_path_default_level_state()
            if isinstance(raw_level, dict):
                level_state["node_index"] = max(0, int(raw_level.get("node_index", 0) or 0))
                level_state["completed_nodes"] = [int(v) for v in list(raw_level.get("completed_nodes", []) or []) if str(v).isdigit() or isinstance(v, int)]
                level_state["done"] = bool(raw_level.get("done", False))
                level_state["last_saved_at"] = raw_level.get("last_saved_at")
            profile["level_progress"][map_key] = level_state
        normalized.append(profile)
    while len(normalized) < QUESTIONS_PATH_PROFILE_MIN:
        normalized.append(_questions_path_default_profile(len(normalized)))
    user["questions_path_profiles"] = normalized[:QUESTIONS_PATH_PROFILE_MAX]


def get_questions_path_profiles(state: dict) -> list[dict]:
    email = state.get("current_user_email")
    if not email:
        return []
    db = load_db()
    user = db.get("users", {}).get(email)
    if not user:
        return []
    ensure_social_defaults(user)
    ensure_questions_path_defaults(user)
    return list(user.get("questions_path_profiles", []) or [])


def persist_questions_path_profiles(state: dict, profiles: list[dict]):
    email = state.get("current_user_email")
    if not email:
        return
    db = load_db()
    if email not in db.get("users", {}):
        return
    db["users"][email]["questions_path_profiles"] = profiles
    save_db(db)

    uid = state.get("current_user_uid") or db.get("users", {}).get(email, {}).get("uid")
    client = get_firestore_client()
    if client is not None and uid and firestore is not None:
        try:
            client.collection("users").document(uid).update({"questions_path_profiles": profiles})
        except Exception as e:
            print(f"Firebase questions_path_profiles save error: {e}")


def get_questions_path_profile_index(state: dict) -> int:
    profiles = state.get("questions_path_profiles")
    if not isinstance(profiles, list) or not profiles:
        profiles = get_questions_path_profiles(state)
    max_index = max(0, len(profiles) - 1) if profiles else 0
    return max(0, min(int(state.get("questions_path_profile_index", 0) or 0), max_index))


def set_questions_path_profile_index(state: dict, index: int):
    profiles = state.get("questions_path_profiles")
    if not isinstance(profiles, list) or not profiles:
        profiles = get_questions_path_profiles(state)
    max_index = max(0, len(profiles) - 1) if profiles else 0
    state["questions_path_profile_index"] = max(0, min(int(index), max_index))


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
    user.setdefault("questions_path_profiles", [])
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


def _ensure_bg_music_control(page: ft.Page, state: dict):
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
    w_candidates = [page.width]
    h_candidates = [page.height]
    win = getattr(page, "window", None)
    if win:
        w_candidates.append(getattr(win, "width", None))
        h_candidates.append(getattr(win, "height", None))
    media = getattr(page, "media", None)
    media_size = getattr(media, "size", None) if media else None
    if media_size:
        w_candidates.append(getattr(media_size, "width", None))
        h_candidates.append(getattr(media_size, "height", None))
    w = max((float(v) for v in w_candidates if v and v > 0), default=1100.0)
    h = max((float(v) for v in h_candidates if v and v > 0), default=720.0)
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
    if route in {"/points", "/path"}:
        renderer(page, state)
        return
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
            fill_color="#000000",
            fit=ft.BoxFit.FILL,
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

    return ft.Container(
        expand=True,
        content=ft.Image(
            src=src,
            fit=ft.BoxFit.FILL,
            width=width,
            height=height,
            expand=True,
        ),
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
            fill_color="#000000",
            fit=ft.BoxFit.FILL,
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
        media = ft.Container(
            expand=True,
            content=ft.Image(src=bg_image, fit=ft.BoxFit.FILL, width=w, height=h, expand=True),
        )

    return ft.Stack(
        [
            media,
            ft.Container(expand=True, width=w, height=h, bgcolor=overlay_color),
        ],
        expand=True,
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
    page.run_task(_sync_bg_music_async, page, state)


def save_questions_path_game(state: dict):
    email = state.get("current_user_email")
    game = state.get("questions_path_game")
    if not email or not game:
        return

    db = load_db()
    if email not in db.get("users", {}):
        return
    user = db["users"][email]
    ensure_social_defaults(user)
    ensure_questions_path_defaults(user)
    profiles = list(user.get("questions_path_profiles", []) or [])
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index]
    map_key = game.get("map_key", "waldpfad")
    map_cfg = _questions_path_map_lookup_for_profile(profile, map_key)

    level_progress = profile.setdefault("level_progress", {})
    level_state = level_progress.setdefault(map_key, _questions_path_default_level_state())
    level_state["node_index"] = int(game.get("node_index", 0))
    level_state["completed_nodes"] = [int(v) for v in list(game.get("completed_nodes", [])) if isinstance(v, int) or str(v).isdigit()]
    level_state["done"] = bool(game.get("game_finished", False))
    level_state["last_saved_at"] = datetime.now(timezone.utc).isoformat()

    profile["selected_age"] = str(game.get("age", profile.get("selected_age", "mid"))).strip() or "mid"
    profile["active_game"] = {
        "map_key": map_key,
        "map_title": game.get("map_title", map_cfg.get("title", QUESTIONS_PATH_MAPS["waldpfad"]["title"])),
        "age": profile["selected_age"],
        "node_index": int(game.get("node_index", 0)),
        "completed_nodes": list(game.get("completed_nodes", [])),
        "questions": list(game.get("questions", [])),
        "game_finished": bool(game.get("game_finished", False)),
        "checkpoint_index": int(game.get("checkpoint_index", 0)),
        "current_hint": game.get("current_hint"),
        "current_level_index": int(game.get("current_level_index", profile.get("active_level_index", 0))),
    }
    if (
        bool(game.get("game_finished", False))
        and _questions_path_profile_mode(profile) == "adventure"
        and map_key in QUESTIONS_PATH_LEVEL_ORDER
    ):
        lvl_index = QUESTIONS_PATH_LEVEL_ORDER.index(map_key)
        profile["active_level_index"] = min(lvl_index + 1, len(QUESTIONS_PATH_LEVEL_ORDER) - 1)
        profile["active_game"] = None
    user["questions_path_profiles"] = profiles
    save_db(db)
    state["questions_path_profiles"] = profiles
    state["saved_questions_path_game"] = profile.get("active_game")
    uid = state.get("current_user_uid") or db.get("users", {}).get(email, {}).get("uid")
    client = get_firestore_client()
    if client is not None and uid and firestore is not None:
        try:
            client.collection("users").document(uid).update({"questions_path_profiles": profiles})
        except Exception as e:
            print(f"Firebase questions_path_profiles save error: {e}")


def clear_questions_path_game(state: dict):
    email = state.get("current_user_email")
    state.pop("questions_path_game", None)
    state.pop("_questions_path_active_node", None)
    state.pop("_questions_path_modal", None)
    state.pop("saved_questions_path_game", None)
    if not email:
        return

    db = load_db()
    if email in db.get("users", {}):
        user = db["users"][email]
        ensure_social_defaults(user)
        ensure_questions_path_defaults(user)
        profiles = list(user.get("questions_path_profiles", []) or [])
        idx = get_questions_path_profile_index(state)
        if idx < len(profiles):
            profiles[idx]["active_game"] = None
            user["questions_path_profiles"] = profiles
            save_db(db)
        state["questions_path_profiles"] = profiles

    uid = state.get("current_user_uid") or db.get("users", {}).get(email, {}).get("uid")
    client = get_firestore_client()
    if client is not None and uid and firestore is not None:
        try:
            client.collection("users").document(uid).update({"questions_path_profiles": db.get("users", {}).get(email, {}).get("questions_path_profiles", [])})
        except Exception as e:
            print(f"Firebase questions_path_profiles delete error: {e}")


def get_saved_questions_path_game(state: dict) -> dict | None:
    email = state.get("current_user_email")
    if not email:
        return None
    saved = state.get("saved_questions_path_game")
    if not saved:
        profiles = get_questions_path_profiles(state)
        idx = get_questions_path_profile_index(state)
        if idx < len(profiles):
            saved = profiles[idx].get("active_game")
            if saved:
                state["saved_questions_path_game"] = saved
                state["questions_path_profiles"] = profiles
    if not saved or not saved.get("questions"):
        return None
    return saved


def resume_questions_path_game(page: ft.Page, state: dict, saved: dict | None = None):
    saved = saved or get_saved_questions_path_game(state)
    if not saved:
        show_questions_path_hub(page, state)
        return
    state["questions_path_game"] = {
        "map_key": saved.get("map_key", "waldpfad"),
        "map_title": saved.get("map_title", QUESTIONS_PATH_MAPS["waldpfad"]["title"]),
        "age": saved.get("age", "mid"),
        "node_index": int(saved.get("node_index", 0)),
        "completed_nodes": list(saved.get("completed_nodes", [])),
        "questions": [_path_question_to_dict(q) for q in saved.get("questions", [])],
        "game_finished": bool(saved.get("game_finished", False)),
        "checkpoint_index": int(saved.get("checkpoint_index", 0)),
        "current_hint": saved.get("current_hint"),
        "current_level_index": int(saved.get("current_level_index", 0)),
    }
    state.pop("_questions_path_active_node", None)
    state.pop("_questions_path_modal", None)
    render_questions_path_game(page, state)



def _questions_path_map_art_asset() -> str:
    return "Fragenpfad/questions_path_forest.png"


def _questions_path_island_hub_asset() -> str:
    return "Fragenpfad/Inseln.png"


def _questions_path_level_background_asset() -> str:
    return "Fragenpfad/level_insel_1.png"


QUESTIONS_PATH_MAPS = {}


QUESTIONS_PATH_MAPS["ernaehrung"] = {
    "title": "Ernährungswelt",
    "subtitle": "Klicke die Insel und löse 10 Fragen zu gesunder Ernährung.",
    "topic": "ernährung",
    "icon": "🥗",
    "accent": "#38BDF8",
    "panel": "#0B1620E8",
    "border": "#7DD3FC",
    "line": "#38BDF8",
    "image": _questions_path_level_background_asset(),
    "points": [{"x": 50.0, "y": 55.0, "label": "Start"}],
}


QUESTIONS_PATH_NUTRITION_BANK = [
    ("Was ist ein gesunder Snack?", ["Apfel", "Chips", "Limonade", "Zuckerwatte"], 0),
    ("Wovon sollte man genug trinken?", ["Wasser", "Cola", "Sirup", "Eis"], 0),
    ("Welches Lebensmittel liefert Eiweiß?", ["Eier", "Bonbons", "Zucker", "Limo"], 0),
    ("Was gehört zu Obst?", ["Banane", "Wurst", "Pizza", "Pommes"], 0),
    ("Was ist oft ballaststoffreich?", ["Vollkornbrot", "Sahnetorte", "Eis", "Kekse"], 0),
    ("Was sollte man eher seltener essen?", ["Süßigkeiten", "Gemüse", "Haferflocken", "Nüsse"], 0),
    ("Wofür braucht der Körper gesunde Nahrung?", ["Energie", "Lärm", "Kälte", "Schlaf"], 0),
    ("Welches Gemüse ist grün?", ["Brokkoli", "Zitrone", "Banane", "Kirsche"], 0),
    ("Was ist ein gutes Frühstück?", ["Haferflocken", "Nur Süßigkeiten", "Nur Cola", "Nichts"], 0),
    ("Was ist in der Ernährung hilfreich?", ["Abwechslungsreich essen", "Immer nur Pizza", "Nie trinken", "Nur Zucker"], 0),
]


def build_questions_path_questions(age: str, map_key: str, state: dict | None = None) -> list[dict]:
    if map_key == "ernaehrung":
        items = list(QUESTIONS_PATH_NUTRITION_BANK)
        random.shuffle(items)
        return [_path_question_to_dict(item) for item in items[:10]]

    bank = build_level_question_bank(age)
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key) or QUESTIONS_PATH_MAPS["waldpfad"]
    total_nodes = len(map_cfg["points"])
    target_topic = _questions_path_map_topic(map_key)
    profile = _get_question_profile(state)
    recent_prompts = []
    performance = {}
    if profile:
        recent_prompts = list(profile.get("recent_prompts", []) or [])
        performance = dict(profile.get("performance", {}) or {})
    recent_set = {str(key).strip().lower() for key in recent_prompts[-QUESTION_HISTORY_LIMIT:]}
    used: set[str] = set()
    questions: list[dict] = []
    for node_idx in range(total_nodes):
        level_idx = min(len(bank) - 1, int(round(node_idx * (len(bank) - 1) / max(total_nodes - 1, 1))))
        candidates = [q for q in list(bank[level_idx] or []) if _question_prompt_key(q) not in used]
        if not candidates:
            candidates = [(f"Frage {node_idx + 1}", ["A", "B", "C", "D"], 0)]
        best_score = None
        chosen = None
        for question in candidates:
            score = _score_question_candidate(question, target_topic, level_idx, recent_set, performance) + random.random() * 0.8
            if best_score is None or score > best_score:
                best_score = score
                chosen = question
        if chosen is None:
            chosen = random.choice(candidates)
        used.add(_question_prompt_key(chosen))
        questions.append(_path_question_to_dict(chosen))
    return questions


def _questions_path_go_to_profiles(page: ft.Page, state: dict):
    state["questions_path_scene"] = "profiles"
    state.pop("questions_path_selected_profile_index", None)
    state.pop("_questions_path_active_node", None)
    show_questions_path_hub(page, state)


def render_questions_path_complete(page: ft.Page, state: dict):
    game = state.get("questions_path_game") or {}
    theme = get_theme(state)
    clear_questions_path_game(state)
    state.pop("_questions_path_active_node", None)
    state["questions_path_scene"] = "islands"
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#05131AD6"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(500, max(320, int(_page_size(page)[0] - 28))),
                            padding=24,
                            bgcolor="#0B1620EE",
                            border_radius=26,
                            border=ft.border.Border.all(2, "#7DD3FC"),
                            content=ft.Column(
                                [
                                    ft.Text("Ernährungswelt geschafft!", size=28, weight="bold", color="white", text_align="center"),
                                    ft.Text("Du hast alle 10 Fragen gelöst.", size=14, color=theme_txt(theme, "secondary"), text_align="center"),
                                    ft.Container(height=10),
                                    _game_menu_button("Zur Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#38BDF8", width=240, height=42),
                                    _game_menu_button("Zur Profilwahl", lambda e: _questions_path_go_to_profiles(e.page, state), "#475569", width=240, height=42),
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
    page.run_task(_sync_bg_music_async, page, state)


def _questions_path_map_art_asset() -> str:
    return "Fragenpfad/questions_path_forest.png"


def _questions_path_island_hub_asset() -> str:
    return "Fragenpfad/Inseln.png"


def _questions_path_level_background_asset() -> str:
    return "Fragenpfad/level_insel_1.png"


QUESTIONS_PATH_MAPS["ernaehrung"] = {
    "title": "Ernährungswelt",
    "subtitle": "Klicke die Insel und löse 10 Fragen zu gesunder Ernährung.",
    "topic": "ernährung",
    "icon": "🥗",
    "accent": "#38BDF8",
    "panel": "#0B1620E8",
    "border": "#7DD3FC",
    "line": "#38BDF8",
    "image": _questions_path_level_background_asset(),
    "points": [{"x": 50.0, "y": 55.0, "label": "Start"}],
}


QUESTIONS_PATH_NUTRITION_BANK = [
    ("Was ist ein gesunder Snack?", ["Apfel", "Chips", "Limonade", "Zuckerwatte"], 0),
    ("Wovon sollte man genug trinken?", ["Wasser", "Cola", "Sirup", "Eis"], 0),
    ("Welches Lebensmittel liefert Eiweiß?", ["Eier", "Bonbons", "Zucker", "Limo"], 0),
    ("Was gehört zu Obst?", ["Banane", "Wurst", "Pizza", "Pommes"], 0),
    ("Was ist oft ballaststoffreich?", ["Vollkornbrot", "Sahnetorte", "Eis", "Kekse"], 0),
    ("Was sollte man eher seltener essen?", ["Süßigkeiten", "Gemüse", "Haferflocken", "Nüsse"], 0),
    ("Wofür braucht der Körper gesunde Nahrung?", ["Energie", "Lärm", "Kälte", "Schlaf"], 0),
    ("Welches Gemüse ist grün?", ["Brokkoli", "Zitrone", "Banane", "Kirsche"], 0),
    ("Was ist ein gutes Frühstück?", ["Haferflocken", "Nur Süßigkeiten", "Nur Cola", "Nichts"], 0),
    ("Was ist in der Ernährung hilfreich?", ["Abwechslungsreich essen", "Immer nur Pizza", "Nie trinken", "Nur Zucker"], 0),
]


def build_questions_path_questions(age: str, map_key: str, state: dict | None = None) -> list[dict]:
    if map_key == "ernaehrung":
        items = list(QUESTIONS_PATH_NUTRITION_BANK)
        random.shuffle(items)
        return [_path_question_to_dict(item) for item in items[:10]]
    bank = build_level_question_bank(age)
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key) or QUESTIONS_PATH_MAPS["waldpfad"]
    total_nodes = len(map_cfg["points"])
    target_topic = _questions_path_map_topic(map_key)
    profile = _get_question_profile(state)
    recent_prompts = []
    performance = {}
    if profile:
        recent_prompts = list(profile.get("recent_prompts", []) or [])
        performance = dict(profile.get("performance", {}) or {})
    recent_set = {str(key).strip().lower() for key in recent_prompts[-QUESTION_HISTORY_LIMIT:]}
    used: set[str] = set()
    questions: list[dict] = []
    for node_idx in range(total_nodes):
        level_idx = min(len(bank) - 1, int(round(node_idx * (len(bank) - 1) / max(total_nodes - 1, 1))))
        candidates = [q for q in list(bank[level_idx] or []) if _question_prompt_key(q) not in used]
        if not candidates:
            candidates = [(f"Frage {node_idx + 1}", ["A", "B", "C", "D"], 0)]
        best_score = None
        chosen = None
        for question in candidates:
            score = _score_question_candidate(question, target_topic, level_idx, recent_set, performance) + random.random() * 0.8
            if best_score is None or score > best_score:
                best_score = score
                chosen = question
        if chosen is None:
            chosen = random.choice(candidates)
        used.add(_question_prompt_key(chosen))
        questions.append(_path_question_to_dict(chosen))
    return questions


def _questions_path_go_to_profiles(page: ft.Page, state: dict):
    state["questions_path_scene"] = "profiles"
    state.pop("questions_path_selected_profile_index", None)
    state.pop("_questions_path_active_node", None)
    show_questions_path_hub(page, state)


def render_questions_path_complete(page: ft.Page, state: dict):
    theme = get_theme(state)
    clear_questions_path_game(state)
    state.pop("_questions_path_active_node", None)
    state["questions_path_scene"] = "islands"
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#05131AD6"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(500, max(320, int(_page_size(page)[0] - 28))),
                            padding=24,
                            bgcolor="#0B1620EE",
                            border_radius=26,
                            border=ft.border.Border.all(2, "#7DD3FC"),
                            content=ft.Column(
                                [
                                    ft.Text("Ernährungswelt geschafft!", size=28, weight="bold", color="white", text_align="center"),
                                    ft.Text("Du hast alle 10 Fragen gelöst.", size=14, color=theme_txt(theme, "secondary"), text_align="center"),
                                    ft.Container(height=10),
                                    _game_menu_button("Zur Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#38BDF8", width=240, height=42),
                                    _game_menu_button("Zur Profilwahl", lambda e: _questions_path_go_to_profiles(e.page, state), "#475569", width=240, height=42),
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
    page.run_task(_sync_bg_music_async, page, state)


def render_questions_path_game(page: ft.Page, state: dict):
    game = state.get("questions_path_game")
    if not game:
        show_questions_path_hub(page, state)
        return

    map_key = game.get("map_key", "ernaehrung")
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["ernaehrung"])
    questions = list(game.get("questions", []))
    node_idx = int(game.get("node_index", 0))
    if node_idx >= len(questions):
        render_questions_path_complete(page, state)
        return

    page_w, page_h = _page_size(page)
    theme = get_theme(state)
    active_node = state.get("_questions_path_active_node")

    if map_key == "ernaehrung" and active_node is None:
        point_left = int(page_w * 0.17)
        point_top = int(page_h * 0.54)
        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        ft.Image(src=_questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                        ft.Container(expand=True, bgcolor="#05131AD6"),
                        _settings_corner_overlay(page, state),
                        ft.Container(left=18, top=18, content=_game_menu_button("← Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#475569", width=160, height=40)),
                        ft.Container(left=0, right=0, top=24, alignment=ft.Alignment(0, -1), content=ft.Text(map_cfg.get("title", "Ernährungswelt"), size=30, weight="bold", color="white")),
                        ft.Container(left=0, right=0, bottom=20, alignment=ft.Alignment(0, 1), content=ft.Text("Klicke den blauen Punkt, um die 10 Fragen zu starten.", size=13, color="#E0F2FE", text_align=ft.TextAlign.CENTER)),
                        ft.Container(left=point_left, top=point_top, width=66, height=66, border_radius=999, bgcolor="#1D4ED8", border=ft.border.Border.all(4, "#93C5FD"), shadow=ft.BoxShadow(blur_radius=28, color="#664F9CF9", spread_radius=2), on_click=lambda e: (state.__setitem__("_questions_path_active_node", 0), render_questions_path_game(e.page, state)), content=ft.Container(alignment=ft.Alignment(0, 0), content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color="white", size=34))),
                    ],
                    expand=True,
                ),
            )
        )
        page.update()
        page.run_task(_sync_bg_music_async, page, state)
        return

    question = questions[node_idx]
    answers = list(question.get("answers", []) or ["A", "B", "C", "D"])
    correct_idx = int(question.get("correct_idx", 0) or 0)
    progress = (node_idx + 1) / max(len(questions), 1)

    def choose_answer(idx: int):
        def _handler(e):
            game_state = state.get("questions_path_game")
            if not game_state or int(game_state.get("node_index", 0)) != node_idx:
                return
            if idx == correct_idx:
                completed = list(game_state.get("completed_nodes", []))
                if node_idx not in completed:
                    completed.append(node_idx)
                game_state["completed_nodes"] = completed
                next_idx = node_idx + 1
                game_state["node_index"] = next_idx
                game_state["current_hint"] = None
                save_questions_path_game(state)
                if next_idx >= len(game_state.get("questions", [])):
                    game_state["game_finished"] = True
                    save_questions_path_game(state)
                    render_questions_path_complete(e.page, state)
                    return
                state["_questions_path_active_node"] = next_idx
                render_questions_path_game(e.page, state)
            else:
                game_state["current_hint"] = "Noch nicht ganz. Versuch es noch einmal."
                save_questions_path_game(state)
                render_questions_path_game(e.page, state)
        return _handler

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=map_cfg.get("image") or _questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#06121AD8"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(620, max(320, int(page_w - 28))),
                            padding=24,
                            bgcolor="#0B1620EE",
                            border_radius=26,
                            border=ft.border.Border.all(2, "#7DD3FC"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            _game_menu_button("← Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#475569", width=160, height=40),
                                            ft.Text(f"Frage {node_idx + 1} / {len(questions)}", size=13, color="#7DD3FC"),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text(question.get("question", "?"), size=20, weight="bold", color="white", text_align="center"),
                                    ft.ProgressBar(value=progress, color="#38BDF8", expand=True),
                                    ft.Container(height=4),
                                    *[
                                        _game_menu_button(f"{ANSWER_LETTERS[idx]}. {answer}", choose_answer(idx), "#16A34A" if idx == correct_idx else "#334155", width=320, height=42)
                                        for idx, answer in enumerate(answers)
                                    ],
                                    ft.Container(height=6),
                                    ft.Text(game.get("current_hint") or "Wähle die richtige Antwort.", size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                                ],
                                spacing=10,
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
    page.run_task(_sync_bg_music_async, page, state)


def start_questions_path_game(page: ft.Page, state: dict, map_key: str):
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["ernaehrung"])
    profiles = get_questions_path_profiles(state)
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)
    age = profile.get("selected_age", state.get("questions_path_age", "mid"))
    questions = build_questions_path_questions(age, map_key, state)
    state["questions_path_game"] = {
        "map_key": map_key,
        "map_title": map_cfg.get("title", "Ernährungswelt"),
        "age": age,
        "node_index": 0,
        "completed_nodes": [],
        "questions": questions,
        "game_finished": False,
        "checkpoint_index": 0,
        "current_hint": None,
        "profile_index": profile_index,
    }
    state["questions_path_age"] = age
    state["questions_path_scene"] = "level"
    state.pop("_questions_path_active_node", None)
    save_questions_path_game(state)
    render_questions_path_game(page, state)


def show_questions_path_hub(page: ft.Page, state: dict):
    _set_resize_view(state, show_questions_path_hub)
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        db = load_db()
        email = state.get("current_user_email")
        if email and email in db.get("users", {}):
            user = db["users"][email]
            ensure_social_defaults(user)
            ensure_questions_path_defaults(user)
            save_db(db)
            profiles = list(user.get("questions_path_profiles", []) or [])
        else:
            profiles = [_questions_path_default_profile(i) for i in range(QUESTIONS_PATH_PROFILE_COUNT)]
    state["questions_path_profiles"] = profiles

    if state.pop("_startup_recovering", False):
        saved = get_saved_questions_path_game(state)
        if saved:
            resume_questions_path_game(page, state, saved)
            return

    scene = state.get("questions_path_scene") or "profiles"
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)

    def select_profile(idx: int):
        def _handler(e):
            set_questions_path_profile_index(state, idx)
            state["questions_path_scene"] = "islands"
            state["questions_path_selected_profile_index"] = idx
            show_questions_path_hub(e.page, state)
        return _handler

    if scene == "profiles":
        profile_cards = []
        for i, p in enumerate(profiles):
            active = i == profile_index
            profile_cards.append(
                ft.Container(
                    width=160,
                    padding=14,
                    bgcolor="#0A0F15E8" if active else "#07110DCC",
                    border_radius=18,
                    border=ft.border.Border.all(2.4 if active else 1.2, theme.get("accent_2", "#60A5FA") if active else "#475569"),
                    on_click=select_profile(i),
                    content=ft.Column(
                        [
                            ft.Text(f"P{i + 1}", size=18, weight="bold", color="white", text_align="center"),
                            ft.Text(p.get("name", f"Profil {i + 1}"), size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                            ft.Text("Auswählen", size=11, color=theme["gold"], text_align="center"),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        _themed_screen_background(page, theme, "#07130FE8"),
                        _settings_corner_overlay(page, state),
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment(0, 0),
                            padding=16,
                            content=ft.Container(
                                width=min(1120, max(320, int(_page_size(page)[0] - 24))),
                                padding=ft.Padding(24, 20, 24, 20),
                                bgcolor="#0B1620E8",
                                border_radius=28,
                                border=ft.border.Border.all(2, "#5EEAD4"),
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                _game_menu_button("← Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=180, height=40),
                                                ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center"),
                                                ft.Container(width=180),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        ft.Text("Wähle zuerst ein Profil.", size=13, color=theme_txt(theme, "secondary"), text_align="center"),
                                        ft.Container(height=14),
                                        ft.Text("Profile", size=16, weight="bold", color=theme["gold"], text_align="center"),
                                        ft.Row(profile_cards, spacing=12, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
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
        page.run_task(_sync_bg_music_async, page, state)
        return

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_island_hub_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#071B12B8"),
                    ft.Container(expand=True, bgcolor="#1D4ED82E"),
                    _settings_corner_overlay(page, state),
                    ft.Container(left=18, top=18, content=_game_menu_button("← Profile", lambda e: _questions_path_go_to_profiles(e.page, state), "#475569", width=160, height=40)),
                    ft.Container(left=0, top=20, right=0, alignment=ft.Alignment(0, -1), content=ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center")),
                    ft.Container(left=0, bottom=18, right=0, alignment=ft.Alignment(0, 1), content=ft.Text("Klicke die Insel oben links, um die Ernährungswelt zu öffnen.", size=13, color="white", text_align="center")),
                    ft.Container(
                        left="12%",
                        top="16%",
                        width=260,
                        height=220,
                        bgcolor="#00000000",
                        on_click=lambda e: start_questions_path_game(e.page, state, "ernaehrung"),
                        content=ft.Container(alignment=ft.Alignment(0, 0), content=ft.Text("Naturinsel", size=18, weight="bold", color="white")),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def _questions_path_map_art_asset() -> str:
    return "Fragenpfad/questions_path_forest.png"


def _questions_path_island_hub_asset() -> str:
    return "Fragenpfad/Inseln.png"


def _questions_path_level_background_asset() -> str:
    return "Fragenpfad/level_insel_1.png"


QUESTIONS_PATH_MAPS["ernaehrung"] = {
    "title": "Ernährungswelt",
    "subtitle": "Klicke die Insel und löse 10 Fragen zu gesunder Ernährung.",
    "topic": "ernährung",
    "icon": "🥗",
    "accent": "#38BDF8",
    "panel": "#0B1620E8",
    "border": "#7DD3FC",
    "line": "#38BDF8",
    "image": _questions_path_level_background_asset(),
    "points": [{"x": 50.0, "y": 55.0, "label": "Start"}],
}


QUESTIONS_PATH_NUTRITION_BANK = [
    ("Was ist ein gesunder Snack?", ["Apfel", "Chips", "Limonade", "Zuckerwatte"], 0),
    ("Wovon sollte man genug trinken?", ["Wasser", "Cola", "Sirup", "Eis"], 0),
    ("Welches Lebensmittel liefert Eiweiß?", ["Eier", "Bonbons", "Zucker", "Limo"], 0),
    ("Was gehört zu Obst?", ["Banane", "Wurst", "Pizza", "Pommes"], 0),
    ("Was ist oft ballaststoffreich?", ["Vollkornbrot", "Sahnetorte", "Eis", "Kekse"], 0),
    ("Was sollte man eher seltener essen?", ["Süßigkeiten", "Gemüse", "Haferflocken", "Nüsse"], 0),
    ("Wofür braucht der Körper gesunde Nahrung?", ["Energie", "Lärm", "Kälte", "Schlaf"], 0),
    ("Welches Gemüse ist grün?", ["Brokkoli", "Zitrone", "Banane", "Kirsche"], 0),
    ("Was ist ein gutes Frühstück?", ["Haferflocken", "Nur Süßigkeiten", "Nur Cola", "Nichts"], 0),
    ("Was ist in der Ernährung hilfreich?", ["Abwechslungsreich essen", "Immer nur Pizza", "Nie trinken", "Nur Zucker"], 0),
]


def build_questions_path_questions(age: str, map_key: str, state: dict | None = None) -> list[dict]:
    if map_key == "ernaehrung":
        items = list(QUESTIONS_PATH_NUTRITION_BANK)
        random.shuffle(items)
        return [_path_question_to_dict(item) for item in items[:10]]
    bank = build_level_question_bank(age)
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key) or QUESTIONS_PATH_MAPS["waldpfad"]
    total_nodes = len(map_cfg["points"])
    target_topic = _questions_path_map_topic(map_key)
    profile = _get_question_profile(state)
    recent_prompts = []
    performance = {}
    if profile:
        recent_prompts = list(profile.get("recent_prompts", []) or [])
        performance = dict(profile.get("performance", {}) or {})
    recent_set = {str(key).strip().lower() for key in recent_prompts[-QUESTION_HISTORY_LIMIT:]}
    used: set[str] = set()
    questions: list[dict] = []
    for node_idx in range(total_nodes):
        level_idx = min(len(bank) - 1, int(round(node_idx * (len(bank) - 1) / max(total_nodes - 1, 1))))
        candidates = [q for q in list(bank[level_idx] or []) if _question_prompt_key(q) not in used]
        if not candidates:
            candidates = [(f"Frage {node_idx + 1}", ["A", "B", "C", "D"], 0)]
        best_score = None
        chosen = None
        for question in candidates:
            score = _score_question_candidate(question, target_topic, level_idx, recent_set, performance) + random.random() * 0.8
            if best_score is None or score > best_score:
                best_score = score
                chosen = question
        if chosen is None:
            chosen = random.choice(candidates)
        used.add(_question_prompt_key(chosen))
        questions.append(_path_question_to_dict(chosen))
    return questions


def _questions_path_go_to_profiles(page: ft.Page, state: dict):
    state["questions_path_scene"] = "profiles"
    state.pop("questions_path_selected_profile_index", None)
    state.pop("_questions_path_active_node", None)
    show_questions_path_hub(page, state)


def render_questions_path_complete(page: ft.Page, state: dict):
    theme = get_theme(state)
    clear_questions_path_game(state)
    state.pop("_questions_path_active_node", None)
    state["questions_path_scene"] = "islands"
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#05131AD6"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(500, max(320, int(_page_size(page)[0] - 28))),
                            padding=24,
                            bgcolor="#0B1620EE",
                            border_radius=26,
                            border=ft.border.Border.all(2, "#7DD3FC"),
                            content=ft.Column(
                                [
                                    ft.Text("Ernährungswelt geschafft!", size=28, weight="bold", color="white", text_align="center"),
                                    ft.Text("Du hast alle 10 Fragen gelöst.", size=14, color=theme_txt(theme, "secondary"), text_align="center"),
                                    ft.Container(height=10),
                                    _game_menu_button("Zur Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#38BDF8", width=240, height=42),
                                    _game_menu_button("Zur Profilwahl", lambda e: _questions_path_go_to_profiles(e.page, state), "#475569", width=240, height=42),
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
    page.run_task(_sync_bg_music_async, page, state)


def render_questions_path_game(page: ft.Page, state: dict):
    game = state.get("questions_path_game")
    if not game:
        show_questions_path_hub(page, state)
        return

    map_key = game.get("map_key", "ernaehrung")
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["ernaehrung"])
    questions = list(game.get("questions", []))
    node_idx = int(game.get("node_index", 0))
    if node_idx >= len(questions):
        render_questions_path_complete(page, state)
        return

    page_w, page_h = _page_size(page)
    theme = get_theme(state)
    active_node = state.get("_questions_path_active_node")

    if map_key == "ernaehrung" and active_node is None:
        point_left = int(page_w * 0.17)
        point_top = int(page_h * 0.54)
        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        ft.Image(src=_questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                        ft.Container(expand=True, bgcolor="#05131AD6"),
                        _settings_corner_overlay(page, state),
                        ft.Container(left=18, top=18, content=_game_menu_button("← Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#475569", width=160, height=40)),
                        ft.Container(left=0, right=0, top=24, alignment=ft.Alignment(0, -1), content=ft.Text(map_cfg.get("title", "Ernährungswelt"), size=30, weight="bold", color="white")),
                        ft.Container(left=0, right=0, bottom=20, alignment=ft.Alignment(0, 1), content=ft.Text("Klicke den blauen Punkt, um die 10 Fragen zu starten.", size=13, color="#E0F2FE", text_align=ft.TextAlign.CENTER)),
                        ft.Container(left=point_left, top=point_top, width=66, height=66, border_radius=999, bgcolor="#1D4ED8", border=ft.border.Border.all(4, "#93C5FD"), shadow=ft.BoxShadow(blur_radius=28, color="#664F9CF9", spread_radius=2), on_click=lambda e: (state.__setitem__("_questions_path_active_node", 0), render_questions_path_game(e.page, state)), content=ft.Container(alignment=ft.Alignment(0, 0), content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color="white", size=34))),
                    ],
                    expand=True,
                ),
            )
        )
        page.update()
        page.run_task(_sync_bg_music_async, page, state)
        return

    question = questions[node_idx]
    answers = list(question.get("answers", []) or ["A", "B", "C", "D"])
    correct_idx = int(question.get("correct_idx", 0) or 0)
    progress = (node_idx + 1) / max(len(questions), 1)

    def choose_answer(idx: int):
        def _handler(e):
            game_state = state.get("questions_path_game")
            if not game_state or int(game_state.get("node_index", 0)) != node_idx:
                return
            if idx == correct_idx:
                completed = list(game_state.get("completed_nodes", []))
                if node_idx not in completed:
                    completed.append(node_idx)
                game_state["completed_nodes"] = completed
                next_idx = node_idx + 1
                game_state["node_index"] = next_idx
                game_state["current_hint"] = None
                save_questions_path_game(state)
                if next_idx >= len(game_state.get("questions", [])):
                    game_state["game_finished"] = True
                    save_questions_path_game(state)
                    render_questions_path_complete(e.page, state)
                    return
                state["_questions_path_active_node"] = next_idx
                render_questions_path_game(e.page, state)
            else:
                game_state["current_hint"] = "Noch nicht ganz. Versuch es noch einmal."
                save_questions_path_game(state)
                render_questions_path_game(e.page, state)
        return _handler

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=map_cfg.get("image") or _questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#06121AD8"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(620, max(320, int(page_w - 28))),
                            padding=24,
                            bgcolor="#0B1620EE",
                            border_radius=26,
                            border=ft.border.Border.all(2, "#7DD3FC"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            _game_menu_button("← Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#475569", width=160, height=40),
                                            ft.Text(f"Frage {node_idx + 1} / {len(questions)}", size=13, color="#7DD3FC"),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text(question.get("question", "?"), size=20, weight="bold", color="white", text_align="center"),
                                    ft.ProgressBar(value=progress, color="#38BDF8", expand=True),
                                    ft.Container(height=4),
                                    *[
                                        _game_menu_button(f"{ANSWER_LETTERS[idx]}. {answer}", choose_answer(idx), "#16A34A" if idx == correct_idx else "#334155", width=320, height=42)
                                        for idx, answer in enumerate(answers)
                                    ],
                                    ft.Container(height=6),
                                    ft.Text(game.get("current_hint") or "Wähle die richtige Antwort.", size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                                ],
                                spacing=10,
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
    page.run_task(_sync_bg_music_async, page, state)


def start_questions_path_game(page: ft.Page, state: dict, map_key: str):
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["ernaehrung"])
    profiles = get_questions_path_profiles(state)
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)
    age = profile.get("selected_age", state.get("questions_path_age", "mid"))
    questions = build_questions_path_questions(age, map_key, state)
    state["questions_path_game"] = {
        "map_key": map_key,
        "map_title": map_cfg.get("title", "Ernährungswelt"),
        "age": age,
        "node_index": 0,
        "completed_nodes": [],
        "questions": questions,
        "game_finished": False,
        "checkpoint_index": 0,
        "current_hint": None,
        "profile_index": profile_index,
    }
    state["questions_path_age"] = age
    state["questions_path_scene"] = "level"
    state.pop("_questions_path_active_node", None)
    save_questions_path_game(state)
    render_questions_path_game(page, state)


def show_questions_path_hub(page: ft.Page, state: dict):
    _set_resize_view(state, show_questions_path_hub)
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        db = load_db()
        email = state.get("current_user_email")
        if email and email in db.get("users", {}):
            user = db["users"][email]
            ensure_social_defaults(user)
            ensure_questions_path_defaults(user)
            save_db(db)
            profiles = list(user.get("questions_path_profiles", []) or [])
        else:
            profiles = [_questions_path_default_profile(i) for i in range(QUESTIONS_PATH_PROFILE_COUNT)]
    state["questions_path_profiles"] = profiles

    if state.pop("_startup_recovering", False):
        saved = get_saved_questions_path_game(state)
        if saved:
            resume_questions_path_game(page, state, saved)
            return

    scene = state.get("questions_path_scene") or "profiles"
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)

    def select_profile(idx: int):
        def _handler(e):
            set_questions_path_profile_index(state, idx)
            state["questions_path_scene"] = "islands"
            state["questions_path_selected_profile_index"] = idx
            show_questions_path_hub(e.page, state)
        return _handler

    if scene == "profiles":
        profile_cards = []
        for i, p in enumerate(profiles):
            active = i == profile_index
            profile_cards.append(
                ft.Container(
                    width=160,
                    padding=14,
                    bgcolor="#0A0F15E8" if active else "#07110DCC",
                    border_radius=18,
                    border=ft.border.Border.all(2.4 if active else 1.2, theme.get("accent_2", "#60A5FA") if active else "#475569"),
                    on_click=select_profile(i),
                    content=ft.Column(
                        [
                            ft.Text(f"P{i + 1}", size=18, weight="bold", color="white", text_align="center"),
                            ft.Text(p.get("name", f"Profil {i + 1}"), size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                            ft.Text("Auswählen", size=11, color=theme["gold"], text_align="center"),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        _themed_screen_background(page, theme, "#07130FE8"),
                        _settings_corner_overlay(page, state),
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment(0, 0),
                            padding=16,
                            content=ft.Container(
                                width=min(1120, max(320, int(_page_size(page)[0] - 24))),
                                padding=ft.Padding(24, 20, 24, 20),
                                bgcolor="#0B1620E8",
                                border_radius=28,
                                border=ft.border.Border.all(2, "#5EEAD4"),
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                _game_menu_button("← Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=180, height=40),
                                                ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center"),
                                                ft.Container(width=180),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        ft.Text("Wähle zuerst ein Profil.", size=13, color=theme_txt(theme, "secondary"), text_align="center"),
                                        ft.Container(height=14),
                                        ft.Text("Profile", size=16, weight="bold", color=theme["gold"], text_align="center"),
                                        ft.Row(profile_cards, spacing=12, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
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
        page.run_task(_sync_bg_music_async, page, state)
        return

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_island_hub_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#071B12B8"),
                    ft.Container(expand=True, bgcolor="#1D4ED82E"),
                    _settings_corner_overlay(page, state),
                    ft.Container(left=18, top=18, content=_game_menu_button("← Profile", lambda e: _questions_path_go_to_profiles(e.page, state), "#475569", width=160, height=40)),
                    ft.Container(left=0, top=20, right=0, alignment=ft.Alignment(0, -1), content=ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center")),
                    ft.Container(left=0, bottom=18, right=0, alignment=ft.Alignment(0, 1), content=ft.Text("Klicke die Insel oben links, um die Ernährungswelt zu öffnen.", size=13, color="white", text_align="center")),
                    ft.Container(
                        left=int(_page_size(page)[0] * 0.12),
                        top=int(_page_size(page)[1] * 0.16),
                        width=260,
                        height=220,
                        bgcolor="#00000000",
                        on_click=lambda e: start_questions_path_game(e.page, state, "ernaehrung"),
                        content=ft.Container(alignment=ft.Alignment(0, 0), content=ft.Text("Naturinsel", size=18, weight="bold", color="white")),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


# ---------- Points quiz ----------
def new_points_quiz_id() -> str:
    return f"points_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

def render_questions_path_game(page: ft.Page, state: dict):
    game = state.get("questions_path_game")
    if not game:
        show_questions_path_hub(page, state)
        return

    map_key = game.get("map_key", "ernaehrung")
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["ernaehrung"])
    questions = list(game.get("questions", []))
    node_idx = int(game.get("node_index", 0))
    if node_idx >= len(questions):
        render_questions_path_complete(page, state)
        return

    page_w, page_h = _page_size(page)
    theme = get_theme(state)
    active_node = state.get("_questions_path_active_node")

    if map_key == "ernaehrung" and active_node is None:
        point_left = int(page_w * 0.17)
        point_top = int(page_h * 0.54)
        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        ft.Image(src=_questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                        ft.Container(expand=True, bgcolor="#05131AD6"),
                        _settings_corner_overlay(page, state),
                        ft.Container(left=18, top=18, content=_game_menu_button("← Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#475569", width=160, height=40)),
                        ft.Container(left=0, right=0, top=24, alignment=ft.Alignment(0, -1), content=ft.Text(map_cfg.get("title", "Ernährungswelt"), size=30, weight="bold", color="white")),
                        ft.Container(left=0, right=0, bottom=20, alignment=ft.Alignment(0, 1), content=ft.Text("Klicke den blauen Punkt, um die 10 Fragen zu starten.", size=13, color="#E0F2FE", text_align=ft.TextAlign.CENTER)),
                        ft.Container(left=point_left, top=point_top, width=66, height=66, border_radius=999, bgcolor="#1D4ED8", border=ft.border.Border.all(4, "#93C5FD"), shadow=ft.BoxShadow(blur_radius=28, color="#664F9CF9", spread_radius=2), on_click=lambda e: (state.__setitem__("_questions_path_active_node", 0), render_questions_path_game(e.page, state)), content=ft.Container(alignment=ft.Alignment(0, 0), content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color="white", size=34))),
                    ],
                    expand=True,
                ),
            )
        )
        page.update()
        page.run_task(_sync_bg_music_async, page, state)
        return

    question = questions[node_idx]
    answers = list(question.get("answers", []) or ["A", "B", "C", "D"])
    correct_idx = int(question.get("correct_idx", 0) or 0)
    progress = (node_idx + 1) / max(len(questions), 1)

    def choose_answer(idx: int):
        def _handler(e):
            game_state = state.get("questions_path_game")
            if not game_state or int(game_state.get("node_index", 0)) != node_idx:
                return
            if idx == correct_idx:
                completed = list(game_state.get("completed_nodes", []))
                if node_idx not in completed:
                    completed.append(node_idx)
                game_state["completed_nodes"] = completed
                next_idx = node_idx + 1
                game_state["node_index"] = next_idx
                game_state["current_hint"] = None
                save_questions_path_game(state)
                if next_idx >= len(game_state.get("questions", [])):
                    game_state["game_finished"] = True
                    save_questions_path_game(state)
                    render_questions_path_complete(e.page, state)
                    return
                state["_questions_path_active_node"] = next_idx
                render_questions_path_game(e.page, state)
            else:
                game_state["current_hint"] = "Noch nicht ganz. Versuch es noch einmal."
                save_questions_path_game(state)
                render_questions_path_game(e.page, state)
        return _handler

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=map_cfg.get("image") or _questions_path_level_background_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#06121AD8"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(620, max(320, int(page_w - 28))),
                            padding=24,
                            bgcolor="#0B1620EE",
                            border_radius=26,
                            border=ft.border.Border.all(2, "#7DD3FC"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            _game_menu_button("← Inselkarte", lambda e: show_questions_path_hub(e.page, state), "#475569", width=160, height=40),
                                            ft.Text(f"Frage {node_idx + 1} / {len(questions)}", size=13, color="#7DD3FC"),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text(question.get("question", "?"), size=20, weight="bold", color="white", text_align="center"),
                                    ft.ProgressBar(value=progress, color="#38BDF8", expand=True),
                                    ft.Container(height=4),
                                    *[
                                        _game_menu_button(f"{ANSWER_LETTERS[idx]}. {answer}", choose_answer(idx), "#16A34A" if idx == correct_idx else "#334155", width=320, height=42)
                                        for idx, answer in enumerate(answers)
                                    ],
                                    ft.Container(height=6),
                                    ft.Text(game.get("current_hint") or "Wähle die richtige Antwort.", size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                                ],
                                spacing=10,
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
    page.run_task(_sync_bg_music_async, page, state)


def start_questions_path_game(page: ft.Page, state: dict, map_key: str):
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["ernaehrung"])
    profiles = get_questions_path_profiles(state)
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)
    age = profile.get("selected_age", state.get("questions_path_age", "mid"))
    questions = build_questions_path_questions(age, map_key, state)
    state["questions_path_game"] = {
        "map_key": map_key,
        "map_title": map_cfg.get("title", "Ernährungswelt"),
        "age": age,
        "node_index": 0,
        "completed_nodes": [],
        "questions": questions,
        "game_finished": False,
        "checkpoint_index": 0,
        "current_hint": None,
        "profile_index": profile_index,
    }
    state["questions_path_age"] = age
    state["questions_path_scene"] = "level"
    state.pop("_questions_path_active_node", None)
    save_questions_path_game(state)
    render_questions_path_game(page, state)


def show_questions_path_hub(page: ft.Page, state: dict):
    _set_resize_view(state, show_questions_path_hub)
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        db = load_db()
        email = state.get("current_user_email")
        if email and email in db.get("users", {}):
            user = db["users"][email]
            ensure_social_defaults(user)
            ensure_questions_path_defaults(user)
            save_db(db)
            profiles = list(user.get("questions_path_profiles", []) or [])
        else:
            profiles = [_questions_path_default_profile(i) for i in range(QUESTIONS_PATH_PROFILE_COUNT)]
    state["questions_path_profiles"] = profiles

    if state.pop("_startup_recovering", False):
        saved = get_saved_questions_path_game(state)
        if saved:
            resume_questions_path_game(page, state, saved)
            return

    scene = state.get("questions_path_scene") or "profiles"
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)

    def select_profile(idx: int):
        def _handler(e):
            set_questions_path_profile_index(state, idx)
            state["questions_path_scene"] = "islands"
            state["questions_path_selected_profile_index"] = idx
            show_questions_path_hub(e.page, state)
        return _handler

    if scene == "profiles":
        profile_cards = []
        for i, p in enumerate(profiles):
            active = i == profile_index
            profile_cards.append(
                ft.Container(
                    width=160,
                    padding=14,
                    bgcolor="#0A0F15E8" if active else "#07110DCC",
                    border_radius=18,
                    border=ft.border.Border.all(2.4 if active else 1.2, theme.get("accent_2", "#60A5FA") if active else "#475569"),
                    on_click=select_profile(i),
                    content=ft.Column(
                        [
                            ft.Text(f"P{i + 1}", size=18, weight="bold", color="white", text_align="center"),
                            ft.Text(p.get("name", f"Profil {i + 1}"), size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                            ft.Text("Auswählen", size=11, color=theme["gold"], text_align="center"),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                content=ft.Stack(
                    [
                        _themed_screen_background(page, theme, "#07130FE8"),
                        _settings_corner_overlay(page, state),
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment(0, 0),
                            padding=16,
                            content=ft.Container(
                                width=min(1120, max(320, int(_page_size(page)[0] - 24))),
                                padding=ft.Padding(24, 20, 24, 20),
                                bgcolor="#0B1620E8",
                                border_radius=28,
                                border=ft.border.Border.all(2, "#5EEAD4"),
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                _game_menu_button("← Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=180, height=40),
                                                ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center"),
                                                ft.Container(width=180),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        ft.Text("Wähle zuerst ein Profil.", size=13, color=theme_txt(theme, "secondary"), text_align="center"),
                                        ft.Container(height=14),
                                        ft.Text("Profile", size=16, weight="bold", color=theme["gold"], text_align="center"),
                                        ft.Row(profile_cards, spacing=12, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
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
        page.run_task(_sync_bg_music_async, page, state)
        return

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_island_hub_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#071B12B8"),
                    ft.Container(expand=True, bgcolor="#1D4ED82E"),
                    _settings_corner_overlay(page, state),
                    ft.Container(left=18, top=18, content=_game_menu_button("← Profile", lambda e: _questions_path_go_to_profiles(e.page, state), "#475569", width=160, height=40)),
                    ft.Container(left=0, top=20, right=0, alignment=ft.Alignment(0, -1), content=ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center")),
                    ft.Container(left=0, bottom=18, right=0, alignment=ft.Alignment(0, 1), content=ft.Text("Klicke die Insel oben links, um die Ernährungswelt zu öffnen.", size=13, color="white", text_align="center")),
                    ft.Container(
                        left="12%",
                        top="16%",
                        width=260,
                        height=220,
                        bgcolor="#00000000",
                        on_click=lambda e: start_questions_path_game(e.page, state, "ernaehrung"),
                        content=ft.Container(alignment=ft.Alignment(0, 0), content=ft.Text("Naturinsel", size=18, weight="bold", color="white")),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


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
    page.run_task(_sync_bg_music_async, page, state)


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


def _path_nodes(points: list[tuple[float, float]], labels: list[str]) -> list[dict]:
    nodes = []
    for idx, point in enumerate(points):
        label = labels[idx] if idx < len(labels) else f"Station {idx + 1}"
        nodes.append({"x": float(point[0]), "y": float(point[1]), "label": label})
    return nodes


def _questions_path_map_art_asset() -> str:
    return "Fragenpfad/questions_path_forest.png"


def _questions_path_island_hub_asset() -> str:
    folder = os.path.join("assets", "Fragenpfad")
    best_path = None
    best_size = -1
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if not name.lower().endswith(".png"):
                continue
            if name.lower() == "questions_path_forest.png":
                continue
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            if size > best_size:
                best_size = size
                best_path = path
    if best_path:
        return os.path.relpath(best_path, "assets").replace("\\", "/")
    return "Fragenpfad/questions_path_forest.png"


QUESTIONS_PATH_MAPS = {
    "waldpfad": {
        "title": "Naturinsel",
        "subtitle": "Wald, Tiere und ruhige Pfade.",
        "topic": "natur",
        "icon": "🌿",
        "accent": "#34D399",
        "panel": "#0A1712E8",
        "border": "#38BDF8",
        "line": "#86EFAC",
        "map_image_src": "Fragenpfad/weg_wald.png",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 39), (20, 32), (32, 28), (45, 24), (58, 26), (71, 31), (82, 39), (86, 52), (76, 67), (60, 75)],
            ["Start", "Waldtor", "Wiesenpfad", "Moosbrücke", "Baumhaus", "Bachufer", "Aussicht", "Klippe", "Wasserfall", "Ziel"],
        ),
    },
    "stadtpfad": {
        "title": "Genussinsel",
        "subtitle": "Ernährung, Alltag und Energie.",
        "topic": "ernährung",
        "icon": "🥗",
        "accent": "#22C55E",
        "panel": "#101B16E8",
        "border": "#6EE7B7",
        "line": "#34D399",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 36), (21, 29), (33, 24), (46, 24), (58, 27), (70, 31), (81, 39), (86, 50), (79, 65), (63, 76)],
            ["Markt", "Gasse", "Obst", "Küche", "Vitamine", "Getreide", "Wasser", "Energie", "Snack", "Ziel"],
        ),
    },
    "himmelsroute": {
        "title": "Meeresinsel",
        "subtitle": "Fische, Wellen und Riffe.",
        "topic": "meer",
        "icon": "🐠",
        "accent": "#A78BFA",
        "panel": "#120A1EE8",
        "border": "#C4B5FD",
        "line": "#DDD6FE",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 74), (18, 66), (28, 73), (40, 65), (54, 69), (66, 61), (74, 51), (81, 42), (87, 31), (77, 20)],
            ["Ufer", "Bucht", "Riff", "Algen", "Fische", "Strömung", "Mole", "Leuchtturm", "Tiefsee", "Ziel"],
        ),
    },
    "geschichtsinsel": {
        "title": "Geschichtsinsel",
        "subtitle": "Zeitreisen durch Epochen und Entdeckungen.",
        "topic": "geschichte",
        "icon": "🏛️",
        "accent": "#F59E0B",
        "panel": "#191105E8",
        "border": "#FCD34D",
        "line": "#FBBF24",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(9, 62), (18, 51), (27, 42), (36, 35), (46, 31), (57, 33), (68, 39), (77, 49), (84, 62), (76, 75)],
            ["Archiv", "Tor", "Antike", "Forum", "Mittelalter", "Werkstatt", "Reise", "Krone", "Bibliothek", "Ziel"],
        ),
    },
    "technikfjord": {
        "title": "Technikfjord",
        "subtitle": "Codes, Computer und digitale Wege.",
        "topic": "technik",
        "icon": "💻",
        "accent": "#06B6D4",
        "panel": "#07161BE8",
        "border": "#67E8F9",
        "line": "#22D3EE",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 28), (19, 34), (30, 31), (41, 25), (52, 29), (63, 38), (73, 47), (81, 58), (86, 69), (78, 79)],
            ["Boot", "Signal", "Pixel", "Router", "Code", "Server", "Cloud", "Chip", "Labor", "Ziel"],
        ),
    },
    "sportlagune": {
        "title": "Sportlagune",
        "subtitle": "Bewegung, Rekorde und faire Spiele.",
        "topic": "sport",
        "icon": "⚽",
        "accent": "#EF4444",
        "panel": "#1D0B0BE8",
        "border": "#FCA5A5",
        "line": "#F87171",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 68), (18, 58), (29, 52), (40, 46), (51, 43), (62, 45), (71, 51), (80, 58), (87, 66), (78, 78)],
            ["Arena", "Sprint", "Team", "Pass", "Finale", "Tribüne", "Pokal", "Lauf", "Rekord", "Ziel"],
        ),
    },
    "kulturbucht": {
        "title": "Kulturbucht",
        "subtitle": "Kunst, Musik und große Geschichten.",
        "topic": "kultur",
        "icon": "🎭",
        "accent": "#EC4899",
        "panel": "#1A0A15E8",
        "border": "#F9A8D4",
        "line": "#F472B6",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(9, 33), (18, 28), (29, 31), (40, 40), (49, 50), (58, 58), (68, 62), (78, 59), (87, 50), (79, 38)],
            ["Bühne", "Atelier", "Roman", "Oper", "Galerie", "Film", "Poesie", "Museum", "Finale", "Ziel"],
        ),
    },
    "matheklippen": {
        "title": "Matheklippen",
        "subtitle": "Zahlen, Muster und clevere Sprünge.",
        "topic": "mathematik",
        "icon": "📐",
        "accent": "#8B5CF6",
        "panel": "#110A1EE8",
        "border": "#C4B5FD",
        "line": "#A78BFA",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 72), (20, 67), (31, 61), (42, 54), (53, 47), (64, 41), (74, 37), (82, 43), (87, 55), (78, 69)],
            ["Null", "Summe", "Bruch", "Prozent", "Formel", "Winkel", "Kurve", "Prim", "Beweis", "Ziel"],
        ),
    },
    "wissenschaftsriff": {
        "title": "Wissensriff",
        "subtitle": "Experimente, Naturgesetze und Ideen.",
        "topic": "wissenschaft",
        "icon": "🔬",
        "accent": "#14B8A6",
        "panel": "#081816E8",
        "border": "#5EEAD4",
        "line": "#2DD4BF",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 24), (21, 29), (31, 36), (41, 45), (52, 52), (63, 57), (73, 60), (81, 54), (87, 43), (78, 30)],
            ["Funke", "Zelle", "Atom", "Licht", "Labor", "Reaktion", "Formel", "Messung", "Hypothese", "Ziel"],
        ),
    },
    "wirtschaftshafen": {
        "title": "Wirtschaftshafen",
        "subtitle": "Preise, Geld und gute Entscheidungen.",
        "topic": "wirtschaft",
        "icon": "💼",
        "accent": "#F97316",
        "panel": "#1A1208E8",
        "border": "#FDBA74",
        "line": "#FB923C",
        "image": _questions_path_map_art_asset(),
        "points": _path_nodes(
            [(10, 55), (19, 49), (29, 43), (40, 39), (52, 38), (63, 42), (73, 49), (82, 58), (87, 68), (79, 77)],
            ["Markt", "Budget", "Preis", "Rabatt", "Kasse", "Währung", "Handel", "Lager", "Chance", "Ziel"],
        ),
    },
}


def _path_question_to_dict(question) -> dict:
    if isinstance(question, dict):
        prompt = str(question.get("question", "")).strip() or "?"
        answers = [str(a) for a in (question.get("answers", []) or [])]
        correct_idx = int(question.get("correct_idx", 0) or 0)
        if answers:
            correct_idx = max(0, min(correct_idx, len(answers) - 1))
        return {"question": prompt, "answers": answers or ["A", "B", "C", "D"], "correct_idx": correct_idx}
    if isinstance(question, (list, tuple)) and len(question) >= 3:
        prompt = str(question[0]).strip() or "?"
        answers = [str(a) for a in list(question[1])]
        correct_idx = int(question[2]) if str(question[2]).isdigit() or isinstance(question[2], int) else 0
        if answers:
            correct_idx = max(0, min(correct_idx, len(answers) - 1))
        return {"question": prompt, "answers": answers or ["A", "B", "C", "D"], "correct_idx": correct_idx}
    return {"question": "?", "answers": ["A", "B", "C", "D"], "correct_idx": 0}


def _questions_path_map_topic(map_key: str) -> str:
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key) or QUESTIONS_PATH_MAPS["waldpfad"]
    return str(map_cfg.get("topic") or "natur")


QUESTIONS_PATH_CREATIVE_THEMES = [
    {"accent": "#34D399", "panel": "#0A1712E8", "border": "#38BDF8", "line": "#86EFAC", "icon": "🏝️"},
    {"accent": "#A78BFA", "panel": "#120A1EE8", "border": "#C4B5FD", "line": "#DDD6FE", "icon": "🌌"},
    {"accent": "#F97316", "panel": "#1A1208E8", "border": "#FDBA74", "line": "#FB923C", "icon": "🌋"},
    {"accent": "#06B6D4", "panel": "#07161BE8", "border": "#67E8F9", "line": "#22D3EE", "icon": "🏖️"},
    {"accent": "#EC4899", "panel": "#1A0A15E8", "border": "#F9A8D4", "line": "#F472B6", "icon": "🎡"},
]


def _questions_path_default_custom_question(index: int = 0) -> dict:
    return {
        "question": f"Eigene Frage {index + 1}",
        "answers": [f"Antwort {letter}" for letter in ANSWER_LETTERS[:4]],
        "correct_idx": 0,
    }


def _questions_path_default_custom_island(index: int = 0) -> dict:
    theme = QUESTIONS_PATH_CREATIVE_THEMES[index % len(QUESTIONS_PATH_CREATIVE_THEMES)]
    return {
        "map_key": f"custom_{index + 1}",
        "title": f"Eigene Insel {index + 1}",
        "subtitle": "Hier kannst du eigene Fragen sammeln.",
        "topic": "custom",
        "icon": theme["icon"],
        "image_src": "",
        "map_image_src": "",
        "accent": theme["accent"],
        "panel": theme["panel"],
        "border": theme["border"],
        "line": theme["line"],
        "design_id": f"theme_{index % len(QUESTIONS_PATH_CREATIVE_THEMES)}",
        "world_layout": "classic",
        "world_name": f"Welt {index + 1}",
        "world_description": "Gestalte hier deine eigene Fragen-Route.",
        "map_x": 6 + (index % 3) * 29,
        "map_y": 8 + (index // 3) * 24,
        "card_scale": 1.0,
        "custom_points": [],
        "questions": [_questions_path_default_custom_question(0)],
    }


def _questions_path_default_custom_map(index: int = 0) -> dict:
    theme = QUESTIONS_PATH_CREATIVE_THEMES[index % len(QUESTIONS_PATH_CREATIVE_THEMES)]
    return {
        "map_key": f"custom_map_{index + 1}",
        "title": f"Eigene Map {index + 1}",
        "subtitle": "Eigener Hintergrund mit frei platzierbaren Punkten.",
        "topic": "custom",
        "icon": "🗺️",
        "image": "",
        "map_image_src": "",
        "accent": theme["accent"],
        "panel": theme["panel"],
        "border": theme["border"],
        "line": theme["line"],
        "points": [_path_nodes([(50, 55)], ["Start"])[0]],
        "questions": [_questions_path_default_custom_question(0)],
    }


QUESTIONS_PATH_WORLD_LAYOUTS = {
    "classic": {"label": "Klassischer Pfad", "points": _path_nodes([(10, 62), (20, 48), (31, 32), (42, 22), (55, 28), (67, 44), (77, 60), (69, 76), (51, 82), (32, 74)], ["Start", "Tor", "Pfad", "Brücke", "Hain", "Lichtung", "Bucht", "Gipfel", "Finale", "Ziel"])},
    "spiral": {"label": "Spiralroute", "points": _path_nodes([(18, 18), (34, 18), (50, 26), (62, 40), (65, 56), (58, 69), (45, 76), (31, 72), (22, 60), (24, 42)], ["Start", "Tor", "Kurve", "Bogen", "Mitte", "Schleife", "Wende", "Rückweg", "Finale", "Ziel"])},
    "coast": {"label": "Küstenweg", "points": _path_nodes([(10, 70), (18, 60), (30, 54), (43, 48), (56, 44), (69, 40), (79, 33), (84, 24), (74, 18), (58, 16)], ["Hafen", "Steg", "Bucht", "Düne", "Pfad", "Klippe", "Leuchtturm", "Welle", "Finale", "Ziel"])},
}


def _questions_path_point_template() -> list[tuple[int, int]]:
    return [(10, 62), (20, 48), (31, 32), (42, 22), (55, 28), (67, 44), (77, 60), (69, 76), (51, 82), (32, 74)]


def _questions_path_points_for_count(count: int) -> list[dict]:
    labels = ["Start", "Tor", "Pfad", "Brücke", "Hain", "Lichtung", "Bucht", "Gipfel", "Finale", "Ziel"]
    template = _questions_path_point_template()
    count = max(1, min(len(template), int(count or 1)))
    return _path_nodes(template[:count], labels[:count])


def _questions_path_custom_map(raw_island: dict, index: int) -> dict:
    theme = QUESTIONS_PATH_CREATIVE_THEMES[index % len(QUESTIONS_PATH_CREATIVE_THEMES)]
    questions = [_path_question_to_dict(q) for q in list(raw_island.get("questions", []) or [])]
    if not questions:
        questions = [_questions_path_default_custom_question(0)]
    layout_key = str(raw_island.get("world_layout", "classic")).strip() or "classic"
    layout = QUESTIONS_PATH_WORLD_LAYOUTS.get(layout_key, QUESTIONS_PATH_WORLD_LAYOUTS["classic"])
    custom_points = list(raw_island.get("custom_points", []) or [])
    if custom_points:
        point_list = []
        labels = [f"Punkt {i + 1}" for i in range(len(custom_points))]
        for i, raw_point in enumerate(custom_points):
            if isinstance(raw_point, dict):
                point_list.append(
                    {
                        "x": max(2, min(96, int(raw_point.get("x", 10) or 10))),
                        "y": max(2, min(96, int(raw_point.get("y", 10) or 10))),
                        "label": str(raw_point.get("label", labels[i])).strip() or labels[i],
                    }
                )
    else:
        point_list = layout["points"]
    return {
        "title": str(raw_island.get("title", f"Eigene Insel {index + 1}")).strip() or f"Eigene Insel {index + 1}",
        "subtitle": str(raw_island.get("subtitle", "Hier kannst du eigene Fragen sammeln.")).strip() or "Hier kannst du eigene Fragen sammeln.",
        "world_name": str(raw_island.get("world_name", raw_island.get("title", f"Welt {index + 1}"))).strip() or f"Welt {index + 1}",
        "world_description": str(raw_island.get("world_description", raw_island.get("subtitle", "Gestalte hier deine eigene Fragen-Route."))).strip() or "Gestalte hier deine eigene Fragen-Route.",
        "topic": "custom",
        "icon": str(raw_island.get("icon", theme["icon"])).strip() or theme["icon"],
        "image_src": str(raw_island.get("image_src", "")).strip(),
        "map_image_src": str(raw_island.get("map_image_src", "")).strip(),
        "accent": str(raw_island.get("accent", theme["accent"])).strip() or theme["accent"],
        "panel": str(raw_island.get("panel", theme["panel"])).strip() or theme["panel"],
        "border": str(raw_island.get("border", theme["border"])).strip() or theme["border"],
        "line": str(raw_island.get("line", theme["line"])).strip() or theme["line"],
        "map_x": max(2.0, min(88.0, float(raw_island.get("map_x", 20) or 20))),
        "map_y": max(2.0, min(82.0, float(raw_island.get("map_y", 20) or 20))),
        "card_scale": max(0.8, min(1.8, float(raw_island.get("card_scale", 1.0) or 1.0))),
        "questions": questions,
        "world_layout": layout_key,
        "custom_points": custom_points,
        "points": point_list[: max(1, min(len(point_list), len(questions)))],
    }


def _questions_path_custom_assets_dir() -> tuple[str, str]:
    abs_dir = os.path.join("assets", "questions_path_custom")
    rel_dir = "questions_path_custom"
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir, rel_dir


_QUESTIONS_PATH_IMAGE_SRC_CACHE: dict[tuple[str, int, int], str] = {}


def _questions_path_cached_image_src(src: str) -> str:
    raw_src = str(src or "").strip()
    if not raw_src:
        return ""
    if raw_src.startswith(("data:image/", "http://", "https://")):
        return raw_src

    candidates = [raw_src]
    if not os.path.isabs(raw_src):
        candidates.append(os.path.join("assets", raw_src))
        if raw_src.startswith("assets/"):
            candidates.append(raw_src)
        else:
            candidates.append(os.path.join("assets", raw_src.lstrip("/\\")))

    for candidate in candidates:
        if not candidate:
            continue
        if not os.path.isfile(candidate):
            continue
        abs_path = os.path.abspath(candidate)
        try:
            stat = os.stat(abs_path)
        except OSError:
            continue
        cache_key = (abs_path, stat.st_mtime_ns, stat.st_size)
        cached = _QUESTIONS_PATH_IMAGE_SRC_CACHE.get(cache_key)
        if cached:
            return cached
        try:
            with open(abs_path, "rb") as file_obj:
                encoded = base64.b64encode(file_obj.read()).decode("ascii")
            ext = os.path.splitext(abs_path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ext == ".webp":
                mime = "image/webp"
            elif ext == ".gif":
                mime = "image/gif"
            else:
                mime = "image/png"
            data_src = f"data:{mime};base64,{encoded}"
            _QUESTIONS_PATH_IMAGE_SRC_CACHE[cache_key] = data_src
            return data_src
        except Exception:
            return raw_src

    return raw_src


def _questions_path_warm_image_cache(*sources: str):
    for src in sources:
        _questions_path_cached_image_src(src)


async def _questions_path_pick_and_store_image(page: ft.Page, prefix: str = "island") -> str | None:
    picker = ft.FilePicker()
    try:
        pick_call = picker.pick_files(
            dialog_title="Bild auswählen",
            allow_multiple=False,
            with_data=True,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
        )
    except TypeError:
        pick_call = picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
        )
    picked_files = await pick_call if inspect.isawaitable(pick_call) else pick_call
    picked_files = list(picked_files or [])
    if not picked_files:
        return None
    picked = picked_files[0]
    original_name = str(getattr(picked, "name", "") or "").strip()
    if not original_name:
        return None
    ext = os.path.splitext(original_name)[1].lower() or ".png"
    if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
        return None
    abs_dir, rel_dir = _questions_path_custom_assets_dir()
    safe_base = _sanitize_filename_part(os.path.splitext(original_name)[0] or prefix)
    unique_name = f"{prefix}_{safe_base}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}{ext}"
    abs_path = os.path.join(abs_dir, unique_name)
    rel_path = f"{rel_dir}/{unique_name}"
    picked_bytes = getattr(picked, "bytes", None)
    if picked_bytes:
        with open(abs_path, "wb") as file_obj:
            file_obj.write(picked_bytes)
        return rel_path
    try:
        upload_jobs = []
        try:
            upload_jobs.append(
                ft.FilePickerUploadFile(
                    id=getattr(picked, "id", None),
                    name=original_name,
                    upload_url=page.get_upload_url(rel_path, 600),
                )
            )
        except TypeError:
            upload_jobs.append(
                ft.FilePickerUploadFile(
                    name=original_name,
                    upload_url=page.get_upload_url(rel_path, 600),
                )
            )
        upload_call = picker.upload(files=upload_jobs)
        if inspect.isawaitable(upload_call):
            await upload_call
        return rel_path
    except Exception:
        return None


def _questions_path_maps_for_profile(profile: dict) -> list[tuple[str, dict]]:
    mode = str(profile.get("progression_mode", "adventure")).strip().lower()
    if mode == "creative":
        custom_islands = list(profile.get("custom_islands", []) or [])
        return [
            (str(item.get("map_key", f"custom_{idx + 1}")), _questions_path_custom_map(item, idx))
            for idx, item in enumerate(custom_islands)
            if isinstance(item, dict)
        ]
    return [(map_key, QUESTIONS_PATH_MAPS[map_key]) for map_key in QUESTIONS_PATH_LEVEL_ORDER]


def _questions_path_map_lookup_for_profile(profile: dict, map_key: str) -> dict:
    for visible_key, map_cfg in _questions_path_maps_for_profile(profile):
        if visible_key == map_key:
            return map_cfg
    return QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["waldpfad"])


def _questions_path_editor_map_lookup(profile: dict, map_key: str) -> dict:
    map_overrides = profile.get("map_overrides", {})
    if isinstance(map_overrides, dict) and map_key in map_overrides and isinstance(map_overrides[map_key], dict):
        return dict(map_overrides[map_key])
    custom_maps = list(profile.get("custom_maps", []) or [])
    for item in custom_maps:
        if isinstance(item, dict) and str(item.get("map_key", "")).strip() == map_key:
            return dict(item)
    return dict(QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["waldpfad"]))


def _questions_path_editor_maps_for_profile(profile: dict) -> list[tuple[str, dict, bool]]:
    maps: list[tuple[str, dict, bool]] = []
    for map_key in QUESTIONS_PATH_LEVEL_ORDER:
        maps.append((map_key, _questions_path_editor_map_lookup(profile, map_key), False))
    for item in list(profile.get("custom_maps", []) or []):
        if isinstance(item, dict):
            map_key = str(item.get("map_key", "")).strip()
            if map_key:
                maps.append((map_key, _questions_path_editor_map_lookup(profile, map_key), True))
    return maps


def _questions_path_editor_save_map(profile: dict, map_key: str, map_cfg: dict):
    map_cfg = dict(map_cfg)
    map_cfg["map_key"] = map_key
    if map_key in QUESTIONS_PATH_MAPS:
        overrides = dict(profile.get("map_overrides", {}) or {})
        overrides[map_key] = map_cfg
        profile["map_overrides"] = overrides
        return
    custom_maps = list(profile.get("custom_maps", []) or [])
    for idx, item in enumerate(custom_maps):
        if isinstance(item, dict) and str(item.get("map_key", "")).strip() == map_key:
            custom_maps[idx] = map_cfg
            profile["custom_maps"] = custom_maps
            return
    custom_maps.append(map_cfg)
    profile["custom_maps"] = custom_maps[-12:]


def _questions_path_copy_points(points: list[dict] | None) -> list[dict]:
    cleaned: list[dict] = []
    for idx, point in enumerate(list(points or [])[:20]):
        if not isinstance(point, dict):
            continue
        cleaned.append(
            {
                "x": max(2, min(96, int(point.get("x", 10) or 10))),
                "y": max(2, min(96, int(point.get("y", 10) or 10))),
                "label": str(point.get("label", f"Punkt {idx + 1}")).strip() or f"Punkt {idx + 1}",
            }
        )
    return cleaned


def _questions_path_copy_questions(questions: list[dict] | None) -> list[dict]:
    return [_path_question_to_dict(question) for question in list(questions or [])[:20]]


def _questions_path_profile_mode(profile: dict) -> str:
    mode = str(profile.get("progression_mode", "adventure")).strip().lower()
    return "creative" if mode == "creative" else "adventure"


def build_questions_path_questions(age: str, map_key: str, state: dict | None = None) -> list[dict]:
    profile = _get_question_profile(state)
    if profile:
        mode = _questions_path_profile_mode(profile)
        if mode == "creative":
            map_cfg = _questions_path_map_lookup_for_profile(profile, map_key)
            if str(map_cfg.get("topic", "")) == "custom":
                return [_path_question_to_dict(q) for q in list(map_cfg.get("questions", []) or [])]

    bank = build_level_question_bank(age)
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key) or QUESTIONS_PATH_MAPS["waldpfad"]
    total_nodes = len(map_cfg["points"])
    target_topic = _questions_path_map_topic(map_key)
    recent_prompts = []
    performance = {}
    if profile:
        recent_prompts = list(profile.get("recent_prompts", []) or [])
        performance = dict(profile.get("performance", {}) or {})
    recent_set = {str(key).strip().lower() for key in recent_prompts[-QUESTION_HISTORY_LIMIT:]}
    used: set[str] = set()
    questions: list[dict] = []
    for node_idx in range(total_nodes):
        level_idx = min(len(bank) - 1, int(round(node_idx * (len(bank) - 1) / max(total_nodes - 1, 1))))
        candidates = list(bank[level_idx] or [])
        if not candidates:
            candidates = [(f"Frage {node_idx + 1}", ["A", "B", "C", "D"], 0)]
        candidates = [q for q in candidates if _question_prompt_key(q) not in used]
        if not candidates:
            candidates = [(f"Frage {node_idx + 1}", ["A", "B", "C", "D"], 0)]
        pool = candidates
        best_score = None
        chosen = None
        for question in pool:
            score = _score_question_candidate(question, target_topic, level_idx, recent_set, performance) + random.random() * 0.8
            if best_score is None or score > best_score:
                best_score = score
                chosen = question
        if chosen is None:
            chosen = random.choice(pool)
        used.add(_question_prompt_key(chosen))
        questions.append(_path_question_to_dict(chosen))
    return questions


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
    "ernährung": ["gesund", "ernähr", "vitamin", "kalorien", "protein", "frühstück", "essen", "obst", "gemüse", "wasser", "trinken", "calcium"],
    "meer": ["fisch", "meer", "ozean", "korallen", "algen", "salz", "welle", "strand", "bucht", "riff", "delta", "strom"],
}
QUESTION_TOPIC_ROTATION = [
    "geschichte",
    "geografie",
    "wissenschaft",
    "kultur",
    "natur",
    "ernährung",
    "meer",
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
    display_label = str(label or "")
    display_label = display_label.replace("hinzufuegen", "hinzuf\u00fcgen")
    display_label = display_label.replace("Hinzufuegen", "Hinzuf\u00fcgen")
    display_label = display_label.replace("hinzufÃ¼gen", "hinzuf\u00fcgen")
    display_label = display_label.replace("HinzufÃ¼gen", "Hinzuf\u00fcgen")
    btn = ft.Container(
        content=ft.Text(
            display_label, size=14, weight="bold", color="white",
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


def _questions_path_map_line(start: dict, end: dict, map_w: float, map_h: float, color: str) -> ft.Container:
    sx = map_w * start["x"] / 100.0
    sy = map_h * start["y"] / 100.0
    ex = map_w * end["x"] / 100.0
    ey = map_h * end["y"] / 100.0
    dx = ex - sx
    dy = ey - sy
    length = max(18.0, math.hypot(dx, dy))
    angle = math.atan2(dy, dx)
    return ft.Container(
        left=sx + 18,
        top=sy + 18 - 2,
        width=length,
        height=4,
        bgcolor=color,
        opacity=0.65,
        rotate=ft.Rotate(angle=angle),
        border_radius=999,
    )


def _questions_path_map_node(
    page: ft.Page,
    state: dict,
    game: dict,
    map_cfg: dict,
    map_w: float,
    map_h: float,
    idx: int,
) -> ft.Container:
    point = map_cfg["points"][idx]
    current = int(game.get("node_index", 0))
    completed = set(int(x) for x in game.get("completed_nodes", []))
    unlocked = idx == current
    is_completed = idx in completed
    accent = map_cfg.get("accent", "#FACC15")
    node_color = accent if unlocked else ("#22C55E" if is_completed else "#475569")
    border_color = "#FFFFFF" if unlocked else ("#A7F3D0" if is_completed else "#94A3B8")
    label_color = "white"
    label = point.get("label", f"Etappe {idx + 1}")
    r = 22

    def open_node(e):
        if int(game.get("node_index", 0)) != idx:
            return
        state["_questions_path_active_node"] = idx
        render_questions_path_game(page, state)

    return ft.Container(
        left=(map_w * point["x"] / 100.0) - r,
        top=(map_h * point["y"] / 100.0) - r,
        width=r * 2,
        height=r * 2,
        shape=ft.BoxShape.CIRCLE,
        bgcolor=node_color,
        border=ft.border.Border.all(2, border_color),
        shadow=ft.BoxShadow(blur_radius=18 if unlocked else 8, color=f"#99{node_color[1:]}" if len(node_color) == 7 else "#66000000"),
        alignment=ft.Alignment(0, 0),
        on_click=open_node,
        tooltip=label,
        content=ft.Text(str(idx + 1), size=14, weight="bold", color=label_color),
        animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
    )


def _questions_path_build_map_stack(page: ft.Page, state: dict, game: dict, map_cfg: dict, map_w: float, map_h: float) -> list[ft.Control]:
    points = map_cfg["points"]
    stack_items: list[ft.Control] = []
    for idx in range(len(points) - 1):
        stack_items.append(_questions_path_map_line(points[idx], points[idx + 1], map_w, map_h, map_cfg.get("line", "#FFFFFF")))
    for idx in range(len(points)):
        stack_items.append(_questions_path_map_node(page, state, game, map_cfg, map_w, map_h, idx))
    return stack_items


def _questions_path_answer_buttons(page: ft.Page, state: dict, node_idx: int, question: dict, map_cfg: dict) -> ft.Control:
    answers = list(question.get("answers", []))
    correct_idx = int(question.get("correct_idx", 0))
    accent = map_cfg.get("accent", "#FACC15")
    buttons = []

    def choose(idx: int):
        def _handler(e):
            game = state.get("questions_path_game")
            if not game or int(game.get("node_index", 0)) != node_idx:
                return
            if idx == correct_idx:
                completed = list(game.get("completed_nodes", []))
                if node_idx not in completed:
                    completed.append(node_idx)
                game["completed_nodes"] = completed
                game["node_index"] = node_idx + 1
                game["current_hint"] = None
                if node_idx + 1 >= len(game.get("questions", [])):
                    game["game_finished"] = True
                    save_questions_path_game(state)
                    state.pop("_questions_path_active_node", None)
                    render_questions_path_complete(page, state)
                    return
                game["checkpoint_index"] = max(game.get("checkpoint_index", 0), node_idx + 1 if (node_idx + 1) % 4 == 0 else game.get("checkpoint_index", 0))
                save_questions_path_game(state)
                state.pop("_questions_path_active_node", None)
                render_questions_path_game(page, state)
            else:
                game["current_hint"] = "Noch nicht ganz. Versuch diese Station nochmal."
                save_questions_path_game(state)
                state.pop("_questions_path_active_node", None)
                render_questions_path_game(page, state)
        return _handler

    for idx, answer in enumerate(answers):
        buttons.append(
            _game_menu_button(
                f"{ANSWER_LETTERS[idx]}. {answer}",
                choose(idx),
                "#16A34A" if idx == correct_idx else "#334155",
                width=280,
                height=42,
            )
        )

    return ft.Column(buttons, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def render_questions_path_complete(page: ft.Page, state: dict):
    game = state.get("questions_path_game") or {}
    map_key = game.get("map_key", "waldpfad")
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["waldpfad"])
    clear_questions_path_game(state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=(map_cfg.get("image") or _questions_path_map_art_asset()), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#04110BD8"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=440,
                            padding=24,
                            bgcolor=map_cfg.get("panel", "#0A1712E8"),
                            border_radius=24,
                            border=ft.border.Border.all(2, map_cfg.get("border", "#34D399")),
                            content=ft.Column(
                                [
                                    ft.Text("Map abgeschlossen!", size=28, weight="bold", color="white", text_align="center"),
                                    ft.Text(map_cfg.get("title", "Fragen-Pfad"), size=16, color="#D1FAE5", text_align="center"),
                                    ft.Container(height=6),
                                    ft.Text(
                                        "Du hast alle Stationen geschafft. Starte jetzt eine neue Map oder kehre zur Auswahl zurück.",
                                        size=13,
                                        color=theme_txt(get_theme(state), "secondary"),
                                        text_align="center",
                                    ),
                                    ft.Container(height=16),
                                    _game_menu_button("Zur Map-Auswahl", lambda e: show_questions_path_hub(e.page, state), map_cfg.get("accent", "#34D399"), width=250),
                                    _game_menu_button("Zur Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=250),
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
    page.run_task(_sync_bg_music_async, page, state)


def render_questions_path_game(page: ft.Page, state: dict):
    game = state.get("questions_path_game")
    if not game:
        show_questions_path_hub(page, state)
        return

    map_key = game.get("map_key", "waldpfad")
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["waldpfad"])
    questions = list(game.get("questions", []))
    node_idx = int(game.get("node_index", 0))
    if node_idx >= len(questions):
        render_questions_path_complete(page, state)
        return

    page_w, page_h = _page_size(page)
    theme = get_theme(state)
    is_mobile = page_w < 920
    map_w = max(260, min(980, int(page_w * (0.92 if is_mobile else 0.68))))
    map_h = max(280, min(560, int(page_h * (0.50 if is_mobile else 0.66))))
    panel_w = max(260, min(360, int(page_w * 0.28)))
    current_q = questions[node_idx]
    current_node = map_cfg["points"][node_idx]
    progress_value = node_idx / max(len(questions), 1)
    hint = game.get("current_hint")
    map_items = _questions_path_build_map_stack(page, state, game, map_cfg, map_w, map_h)

    def back_to_hub(e):
        save_questions_path_game(state)
        show_questions_path_hub(e.page, state)

    map_image = map_cfg.get("image") or _questions_path_map_art_asset()
    map_stack = ft.Container(
        width=map_w,
        height=map_h,
        border_radius=28,
        border=ft.border.Border.all(2.4, map_cfg.get("border", "#34D399")),
        padding=10,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Stack(
            [
                ft.Image(src=map_image, fit=ft.BoxFit.COVER, expand=True),
                ft.Container(expand=True, bgcolor="#06140B8C"),
                ft.Container(
                    expand=True,
                    padding=6,
                    content=ft.Stack(map_items, expand=True),
                ),
            ],
            expand=True,
        ),
    )

    status_panel = ft.Container(
        width=panel_w,
        padding=20,
        border_radius=24,
        bgcolor="#0A0F15E8",
        border=ft.border.Border.all(2, map_cfg.get("border", "#34D399")),
        content=ft.Column(
            [
                ft.Text(map_cfg.get("title", "Fragen-Pfad"), size=24, weight="bold", color="white"),
                ft.Text(map_cfg.get("subtitle", ""), size=13, color=theme_txt(theme, "secondary")),
                ft.Container(height=8),
                ft.Text(f"Alter: {game.get('age', 'mid')}", size=12, color="#FDE68A"),
                ft.Text(f"Fortschritt: {node_idx} / {len(questions)}", size=12, color="white"),
                ft.ProgressBar(value=progress_value, expand=True, color=map_cfg.get("accent", "#34D399")),
                ft.Text(f"Aktuelle Station: {current_node.get('label', f'Station {node_idx + 1}')}", size=12, color="white"),
                ft.Text(f"Checkpoint: {game.get('checkpoint_index', 0)}", size=12, color="white"),
                ft.Container(height=4),
                ft.Text(hint or "Klicke die leuchtende Station auf der Karte, um die nächste Frage zu öffnen.", size=11, color=theme_txt(theme, "muted")),
                ft.Container(height=10),
                _game_menu_button("Zurück zur Auswahl", back_to_hub, "#475569", width=panel_w - 40, height=42),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    main_area = ft.Row(
        [
            map_stack,
            status_panel,
        ],
        spacing=16,
        vertical_alignment=ft.CrossAxisAlignment.START,
        alignment=ft.MainAxisAlignment.CENTER,
        wrap=is_mobile,
    )

    modal = None
    active_node = state.get("_questions_path_active_node")
    if active_node is not None and 0 <= int(active_node) < len(questions):
        question = questions[int(active_node)]
        modal = ft.Container(
            expand=True,
            bgcolor="#000000A0",
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=min(560, max(320, int(page_w - 28))),
                padding=24,
                bgcolor="#111827",
                border_radius=24,
                border=ft.border.Border.all(2, map_cfg.get("accent", "#34D399")),
                content=ft.Column(
                    [
                        ft.Text(f"Station {int(active_node) + 1}: {map_cfg['points'][int(active_node)].get('label', '')}", size=12, color=map_cfg.get("accent", "#34D399")),
                        ft.Text(question.get("question", "?"), size=20, weight="bold", color="white", text_align="center"),
                        ft.Container(height=6),
                        _questions_path_answer_buttons(page, state, int(active_node), question, map_cfg),
                        ft.Container(height=8),
                        _game_menu_button("Schließen", lambda e: (state.pop("_questions_path_active_node", None), render_questions_path_game(e.page, state)), "#475569", width=220, height=40),
                    ],
                    spacing=10,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

    page.controls.clear()
    layers = [
        ft.Image(src=(map_cfg.get("image") or _questions_path_map_art_asset()), fit=ft.BoxFit.COVER, expand=True),
        ft.Container(expand=True, bgcolor="#04110B92"),
        _settings_corner_overlay(page, state),
        ft.Container(
            expand=True,
            padding=16,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            _game_menu_button("← Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=160, height=40),
                            ft.Text("Fragen-Pfad", size=28, weight="bold", color="white"),
                            ft.Container(width=160),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=10),
                    main_area,
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
    ]
    if modal:
        layers.append(modal)

    page.add(ft.Container(expand=True, content=ft.Stack(layers, expand=True)))
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def start_questions_path_game(page: ft.Page, state: dict, map_key: str):
    map_cfg = QUESTIONS_PATH_MAPS.get(map_key, QUESTIONS_PATH_MAPS["waldpfad"])
    profiles = get_questions_path_profiles(state)
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)
    age = profile.get("selected_age", state.get("questions_path_age", "mid"))
    active_game = profile.get("active_game")
    if isinstance(active_game, dict) and active_game.get("map_key") == map_key and not active_game.get("game_finished", False):
        resume_questions_path_game(page, state, active_game)
        return

    questions = build_questions_path_questions(age, map_key, state)
    state["questions_path_game"] = {
        "map_key": map_key,
        "map_title": map_cfg.get("title", "Fragen-Pfad"),
        "age": age,
        "node_index": 0,
        "completed_nodes": [],
        "questions": questions,
        "game_finished": False,
        "checkpoint_index": 0,
        "current_hint": None,
        "profile_index": profile_index,
    }
    state["questions_path_age"] = age
    state.pop("_questions_path_active_node", None)
    save_questions_path_game(state)
    render_questions_path_game(page, state)


def show_questions_path_hub(page: ft.Page, state: dict):
    _set_resize_view(state, show_questions_path_hub)
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        db = load_db()
        email = state.get("current_user_email")
        if email and email in db.get("users", {}):
            user = db["users"][email]
            ensure_social_defaults(user)
            ensure_questions_path_defaults(user)
            save_db(db)
            profiles = list(user.get("questions_path_profiles", []) or [])
        else:
            profiles = [_questions_path_default_profile(i) for i in range(QUESTIONS_PATH_PROFILE_COUNT)]
    state["questions_path_profiles"] = profiles

    if state.pop("_startup_recovering", False):
        saved = get_saved_questions_path_game(state)
        if saved:
            resume_questions_path_game(page, state, saved)
            return

    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)
    selected_age = profile.get("selected_age", "mid")
    saved = profile.get("active_game")

    def persist_and_refresh():
        current_profiles = get_questions_path_profiles(state)
        if not current_profiles:
            current_profiles = [_questions_path_default_profile(i) for i in range(QUESTIONS_PATH_PROFILE_COUNT)]
        if profile_index < len(current_profiles):
            current_profiles[profile_index] = profile
            persist_questions_path_profiles(state, current_profiles)
            state["questions_path_profiles"] = current_profiles

    def choose_profile(idx: int):
        def _handler(e):
            set_questions_path_profile_index(state, idx)
            show_questions_path_hub(e.page, state)
        return _handler

    def set_age(e):
        profile["selected_age"] = e.control.value
        persist_and_refresh()
        show_questions_path_hub(e.page, state)

    def level_state_for(profile_data: dict, map_key: str, level_index: int) -> str:
        level_progress = (profile_data.get("level_progress", {}) or {}).get(map_key, {})
        if isinstance(level_progress, dict) and level_progress.get("done"):
            return "done"
        current_idx = int(profile_data.get("active_level_index", 0) or 0)
        if level_index < current_idx:
            return "done"
        if level_index == current_idx:
            return "active"
        return "locked"

    def open_level(map_key: str, level_index: int):
        def _handler(e):
            state["questions_path_profile_index"] = profile_index
            current_profiles = get_questions_path_profiles(state)
            current_profile = current_profiles[profile_index] if profile_index < len(current_profiles) else profile
            lvl_state = level_state_for(current_profile, map_key, level_index)
            saved_game = current_profile.get("active_game")
            if saved_game and saved_game.get("map_key") == map_key and not saved_game.get("game_finished", False):
                resume_questions_path_game(e.page, state, saved_game)
                return
            if lvl_state == "locked":
                e.page.snack_bar = ft.SnackBar(content=ft.Text("Schließe zuerst das vorherige Level ab."), open=True)
                e.page.update()
                return
            start_questions_path_game(e.page, state, map_key)
        return _handler

    age_dropdown = ft.Dropdown(
        value=selected_age,
        width=260,
        bgcolor="#0B1620",
        color="white",
        border_color=theme["border"],
        options=[ft.dropdown.Option(k, text=label) for k, label in POINTS_QUIZ_AGE_OPTIONS],
    )
    age_dropdown.on_change = set_age

    profile_cards = []
    for i, p in enumerate(profiles):
        level_done = sum(1 for lvl in (p.get("level_progress", {}) or {}).values() if isinstance(lvl, dict) and lvl.get("done"))
        active = i == profile_index
        profile_cards.append(
            ft.Container(
                width=150,
                padding=14,
                bgcolor="#0A0F15E8" if active else "#07110DCC",
                border_radius=18,
                border=ft.border.Border.all(2.4 if active else 1.2, theme.get("accent_2", "#60A5FA") if active else "#475569"),
                on_click=choose_profile(i),
                content=ft.Column(
                    [
                        ft.Text(f"P{i + 1}", size=18, weight="bold", color="white", text_align="center"),
                        ft.Text(p.get("name", f"Profil {i + 1}"), size=12, color=theme_txt(theme, "secondary"), text_align="center"),
                        ft.Text(f"{level_done}/3 Inseln", size=11, color=theme["gold"], text_align="center"),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    resume_section = []
    if saved:
        resume_section.extend([
            ft.Text("Fortsetzung vorhanden", size=16, weight="bold", color=theme["gold"]),
            ft.Text(f"{saved.get('map_title', 'Fragen-Pfad')} · Station {int(saved.get('node_index', 0)) + 1}", size=12, color=theme_txt(theme, "secondary")),
            _game_menu_button("▶ Weiterspielen", lambda e: resume_questions_path_game(e.page, state, saved), theme["success"], width=220, height=42),
        ])

    island_layout = [
        {"map_key": "waldpfad", "left": 0.05, "top": 0.50, "w": 0.28, "h": 0.30},
        {"map_key": "stadtpfad", "left": 0.37, "top": 0.18, "w": 0.28, "h": 0.30},
        {"map_key": "himmelsroute", "left": 0.68, "top": 0.46, "w": 0.25, "h": 0.28},
    ]

    page_w, page_h = _page_size(page)
    card_w = min(1260, max(320, int(page_w - 24)))
    map_h = max(390, min(560, int(page_h * 0.56)))
    stage_layers = [
        ft.Container(expand=True, bgcolor="#8DD8FF"),
        ft.Container(left=18, top=18, width=150, height=46, border_radius=999, bgcolor="#FFFFFFAA"),
        ft.Container(left=120, top=36, width=240, height=62, border_radius=999, bgcolor="#FFFFFF66"),
        ft.Container(left=card_w - 300, top=36, width=180, height=52, border_radius=999, bgcolor="#FFFFFF88"),
        ft.Container(left=card_w - 200, top=90, width=120, height=36, border_radius=999, bgcolor="#FFFFFF66"),
        ft.Container(left=24, top=map_h - 92, width=210, height=54, border_radius=999, bgcolor="#FFFFFF55"),
        ft.Container(left=int(card_w * 0.18), top=int(map_h * 0.63), width=120, height=22, border_radius=999, bgcolor="#2ECC7155"),
        ft.Container(left=int(card_w * 0.47), top=int(map_h * 0.35), width=130, height=18, border_radius=999, bgcolor="#F59E0B66"),
        ft.Container(left=int(card_w * 0.76), top=int(map_h * 0.58), width=120, height=20, border_radius=999, bgcolor="#A78BFA55"),
    ]
    stage = ft.Container(
        width=card_w,
        height=map_h,
        border_radius=30,
        border=ft.border.Border.all(2, "#BFE7FF"),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        bgcolor="#7CC8FF",
        content=ft.Stack(stage_layers, expand=True),
    )

    stage_items = []
    for i, item in enumerate(island_layout):
        map_key = item["map_key"]
        map_cfg = QUESTIONS_PATH_MAPS[map_key]
        state_name = level_state_for(profile, map_key, i)
        accent = {"done": "#22C55E", "active": "#3B82F6", "locked": "#64748B"}[state_name]
        label = {"done": "Abgeschlossen", "active": "Aktiv", "locked": "Gesperrt"}[state_name]
        current_level = (profile.get("active_game") or {}).get("map_key") == map_key
        left = int(card_w * item["left"])
        top = int(map_h * item["top"])
        width = int(card_w * item["w"])
        height = int(map_h * item["h"])
        stage_items.append(
            ft.Container(
                left=left,
                top=top,
                width=width,
                height=height,
                border_radius=999,
                padding=16,
                bgcolor="#F8F7F0" if state_name != "active" else "#FFF7E6",
                border=ft.border.Border.all(3 if state_name == "active" else 2, accent),
                shadow=ft.BoxShadow(blur_radius=18, color=f"#55{accent[1:]}", spread_radius=1),
                on_click=open_level(map_key, i),
                content=ft.Column(
                    [
                        ft.Text(map_cfg.get("icon", "🗺️"), size=30, text_align=ft.TextAlign.CENTER),
                        ft.Text(map_cfg.get("title", "Insel"), size=20, weight="bold", color="#0F172A", text_align="center"),
                        ft.Text(map_cfg.get("subtitle", ""), size=11, color="#334155", text_align="center"),
                        ft.Container(height=2),
                        ft.Text(f"{len(map_cfg['points'])} Fragen", size=11, color="#1D4ED8", text_align="center"),
                        ft.Container(
                            content=ft.Text(label, size=10, weight="bold", color="white"),
                            bgcolor=accent,
                            border_radius=999,
                            padding=ft.Padding(10, 3, 10, 3),
                        ),
                        ft.Container(height=2),
                        _game_menu_button(
                            "Fortsetzen" if current_level and saved else ("Starten" if state_name != "locked" else "Gesperrt"),
                            open_level(map_key, i),
                            accent,
                            width=width - 44,
                            height=36,
                        ),
                    ],
                    spacing=5,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            )
        )

    path_dots = []
    for offset in range(12):
        path_dots.append(
            ft.Container(
                left=int(card_w * (0.16 + offset * 0.055)),
                top=int(map_h * (0.42 + (offset % 2) * 0.04)),
                width=12,
                height=12,
                border_radius=999,
                bgcolor="#FDE68A",
                opacity=0.8,
            )
        )

    stage.content = ft.Stack([*stage_layers, *path_dots, *stage_items], expand=True)

    settings_panel = ft.Container(
        width=320,
        padding=16,
        bgcolor="#06131BE0",
        border_radius=20,
        border=ft.border.Border.all(1.5, "#2D6A4F"),
        content=ft.Column(
            [
                ft.Text("Profil-Einstellungen", size=16, weight="bold", color="white"),
                ft.Text(f"Aktives Profil: {profile.get('name', f'Profil {profile_index + 1}')}", size=12, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                age_dropdown,
                *resume_section,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    bottom_panel = ft.Container(
        expand=True,
        padding=16,
        bgcolor="#06131BE0",
        border_radius=20,
        border=ft.border.Border.all(1.5, "#334155"),
        content=ft.Column(
            [
                ft.Text("Deine Inselkarte", size=16, weight="bold", color=theme["gold"]),
                ft.Text("Klicke eine Insel an, um ihren Pfad und die Fragen zu öffnen.", size=12, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(f"{map_cfg['title']}", size=12, color="white", weight="bold"),
                            bgcolor=theme["accent_2"],
                            border_radius=999,
                            padding=ft.Padding(10, 4, 10, 4),
                        )
                        for map_cfg in QUESTIONS_PATH_MAPS.values()
                    ],
                    spacing=10,
                    wrap=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Image(src=_questions_path_island_hub_asset(), fit=ft.BoxFit.COVER, expand=True),
                    ft.Container(expand=True, bgcolor="#071B12B8"),
                    ft.Container(expand=True, bgcolor="#1D4ED82E"),
                    _settings_corner_overlay(page, state),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=16,
                        content=ft.Column(
                            [
                                ft.Container(
                                    width=card_w,
                                    padding=ft.Padding(22, 18, 22, 18),
                                    bgcolor="#0A1320EE",
                                    border_radius=28,
                                    border=ft.border.Border.all(2, "#5EEAD4"),
                                    content=ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    _game_menu_button("← Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=180, height=40),
                                                    ft.Column(
                                                        [
                                                            ft.Text("Fragen-Pfad", size=30, weight="bold", color="white", text_align="center"),
                                                            ft.Text("Wähle eine Insel und öffne ihren Fragen-Pfad.", size=13, color=theme_txt(theme, "secondary"), text_align="center"),
                                                        ],
                                                        spacing=3,
                                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                    ),
                                                    ft.Container(width=180),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            ),
                                            ft.Container(height=10),
                                            ft.Text("Profile", size=16, weight="bold", color=theme["gold"], text_align="center"),
                                            ft.Row(profile_cards, spacing=12, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
                                            ft.Container(height=12),
                                            ft.Container(content=stage, alignment=ft.Alignment(0, 0)),
                                            ft.Container(height=8),
                                            ft.Row(
                                                [
                                                    settings_panel,
                                                    bottom_panel,
                                                ],
                                                spacing=16,
                                                wrap=True,
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                vertical_alignment=ft.CrossAxisAlignment.START,
                                            ),
                                        ],
                                        spacing=10,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ),
                            ],
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


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
    page.run_task(_sync_bg_music_async, page, state)


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
                    "Wer wird Millionär, Punkte-Quiz oder der neue Fragen-Pfad mit langem Map-Fortschritt und kleinen Etappen.",
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
            portal_card("Fragen-Pfad", "Eine lange Karte mit vielen Stationen, die du Stück für Stück freischaltest.", theme.get("accent_2", "#A78BFA"), "🗺️", lambda e: _go_route_or_render(e.page, "/path", show_questions_path_hub, state)),
        ],
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    ) if mobile else ft.Row(
        [
            portal_card("Wer wird Millionär", "Das bisherige Solo-Spiel mit Jokern, Daily Challenge und eigenem Quiz-Modus.", theme.get("accent", "#10B981"), "💰", lambda e: _go_route_or_render(e.page, "/wwm", open_wwm_main_menu, state)),
            portal_card("Punkte-Quiz", "Team gegen Team auf einer Punktetafel mit Kategorien, Bewertung durch dich und freiem Spielende.", theme.get("gold", "#FACC15"), "🏟️", lambda e: _go_route_or_render(e.page, "/points", show_points_quiz_hub, state)),
            portal_card("Fragen-Pfad", "Eine lange Karte mit vielen Stationen, die du Stück für Stück freischaltest.", theme.get("accent_2", "#A78BFA"), "🗺️", lambda e: _go_route_or_render(e.page, "/path", show_questions_path_hub, state)),
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
    page.run_task(_sync_bg_music_async, page, state)


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
        bgcolor="#08120df2" if is_nexus else theme.get("panel", "#0c1814"),
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
        bgcolor="#08120df2" if is_nexus else theme.get("question_bg", "#FFFFFF"),
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
    display_key = f"{state.get('custom_quiz_id') or 'standard'}:{state['question_index']}:{question}"
    display_order = list(range(len(options)))
    random.Random(display_key).shuffle(display_order)
    display_options = [options[i] for i in display_order]
    display_correct_idx = display_order.index(correct_idx)
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
    themed_bg = themed_bg_preview
    bg_image = themed_bg if themed_bg else (theme.get("game_bg") if themed else None)
    has_video_bg = _is_video_background(bg_image)
    if bg_image:
        overlay_color = "#000000e2" if has_video_bg else "#000000b8"
        question_text_color = "#F8FAFC"
        answer_text_color = "#F8FAFC"
        question_bg_color = "#08120df8" if is_nexus else "#08121df6"
        answer_bg = "#08120df8" if is_nexus else "#08121df6"
    else:
        overlay_color = "#00000000" if is_nexus else (
            "#00000099" if not theme.get("is_light") else "#00000055"
        )
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
            if chosen == display_correct_idx:
                record_question_result(state, (question, display_options, display_correct_idx), was_correct=True)
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
                record_question_result(state, (question, display_options, display_correct_idx), was_correct=False)
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
            is_correct = chosen == display_correct_idx
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
            if idx == display_correct_idx:
                btn_container.bgcolor = "#00C853" if themed else "#2ECC71"
                btn_container.border = ft.border.Border.all(3, "#76FF03" if themed else "#27AE60")
            elif idx == chosen and idx != display_correct_idx:
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

    answer_boxes = [make_answer_box(i, option) for i, option in enumerate(display_options)]
    ctx = {
        "theme": theme,
        "question": question,
        "options": display_options,
        "correct_idx": display_correct_idx,
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
                ft.Text("🗺️", size=14, color=theme.get("accent", theme["danger"])),
                ft.Text("Inselkarte", size=13, weight="bold", color=theme.get("accent", theme["danger"])),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: (stop_game_timer(state), save_current_game(state), e.page.go("/wwm")),
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
            ft.Text("🗺️", size=sc(12, 10), color=theme.get("accent", "#FFFFFF") if has_video_bg else "white"),
            ft.Text("Inselkarte", size=sc(12, 10), weight="bold", color=theme.get("accent", "#FFFFFF") if has_video_bg else "white"),
        ], spacing=sc(5, 4), tight=True),
        on_click=lambda e: (stop_game_timer(state), save_current_game(state), e.page.go("/wwm")),
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
    page.run_task(_sync_bg_music_async, page, state)


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


QUESTIONS_PATH_NUTRITION_QUESTIONS = [
    {
        "question": "Welches Getränk ist im Alltag meist die beste Wahl?",
        "answers": ["Wasser", "Cola", "Energydrink", "Eistee"],
        "correct": 0,
    },
    {
        "question": "Was gehört zu einer ausgewogenen Mahlzeit?",
        "answers": ["Gemüse, Eiweiß und Kohlenhydrate", "Nur Süßigkeiten", "Nur Chips", "Nur Getränke"],
        "correct": 0,
    },
    {
        "question": "Welche Frucht liefert oft viel Vitamin C?",
        "answers": ["Orange", "Kuchen", "Käse", "Brot"],
        "correct": 0,
    },
    {
        "question": "Was ist ein Vollkornprodukt?",
        "answers": ["Vollkornbrot", "Milchshake", "Schokoriegel", "Bonbon"],
        "correct": 0,
    },
    {
        "question": "Wofür braucht der Körper Eiweiß besonders?",
        "answers": ["Für Aufbau und Erhalt von Muskeln", "Zum Fliegen", "Nur für Süßes", "Gar nicht"],
        "correct": 0,
    },
    {
        "question": "Welche Speise ist meist ballaststoffreich?",
        "answers": ["Haferflocken", "Limonade", "Gummibärchen", "Butter"],
        "correct": 0,
    },
    {
        "question": "Was sollte man eher selten essen?",
        "answers": ["Sehr zuckerreiche Snacks", "Gemüse", "Wasser", "Nüsse"],
        "correct": 0,
    },
    {
        "question": "Welche Fettquelle ist meist günstiger für den Körper?",
        "answers": ["Nüsse und Pflanzenöle", "Frittierfett aus jedem Snack", "Zucker", "Salz"],
        "correct": 0,
    },
    {
        "question": "Was hilft dem Körper nach Sport besonders gut?",
        "answers": ["Wasser und eine ausgewogene Mahlzeit", "Nur Süßigkeiten", "Gar nichts", "Nur Kaffee"],
        "correct": 0,
    },
    {
        "question": "Wie viele Portionen Obst und Gemüse werden oft pro Tag empfohlen?",
        "answers": ["Fünf", "Eine", "Zehn", "Keine"],
        "correct": 0,
    },
]


def _questions_path_island_hub_asset() -> str:
    return os.path.join("Fragenpfad", "Inseln.png")


def _questions_path_level_background_asset() -> str:
    return os.path.join("Fragenpfad", "level_insel_1.png")


def _questions_path_level_start_asset() -> str:
    return os.path.join("Fragenpfad", "level_start.png")


def _questions_path_profile_cards(page: ft.Page, state: dict, profiles: list[dict]):
    theme = get_theme(state)
    cards = []
    active_index = get_questions_path_profile_index(state)

    def choose_profile(index: int):
        def _handler(e):
            set_questions_path_profile_index(state, index)
            _questions_path_render_profiles(e.page, state)

        return _handler

    def remove_specific(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            if len(current_profiles) <= QUESTIONS_PATH_PROFILE_MIN:
                e.page.snack_bar = ft.SnackBar(content=ft.Text("Mindestens ein Profil muss bleiben."), open=True)
                e.page.update()
                return
            current_profiles.pop(index)
            for idx, profile in enumerate(current_profiles):
                if isinstance(profile, dict) and str(profile.get("name", "")).startswith(QUESTIONS_PATH_DEFAULT_PROFILE_NAME):
                    profile["name"] = f"{QUESTIONS_PATH_DEFAULT_PROFILE_NAME} {idx + 1}"
            persist_questions_path_profiles(state, current_profiles)
            state["questions_path_profiles"] = current_profiles
            set_questions_path_profile_index(state, min(get_questions_path_profile_index(state), len(current_profiles) - 1))
            _questions_path_render_profiles(e.page, state)

        return _handler

    for index, profile in enumerate(profiles):
        active = index == active_index
        mode = "Kreativ" if _questions_path_profile_mode(profile) == "creative" else "Abenteuer"
        cards.append(
            ft.Container(
                width=180,
                padding=18,
                border_radius=22,
                bgcolor="#0B1620" if active else "#07110D",
                border=ft.border.Border.all(2.4 if active else 1.2, theme.get("accent_2", "#38BDF8") if active else "#334155"),
                shadow=ft.BoxShadow(blur_radius=10, color="#22000000"),
                on_click=choose_profile(index),
                content=ft.Column(
                    [
                        ft.Text(f"P{index + 1}", size=20, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                        ft.Text(profile.get("name", f"Profil {index + 1}"), size=14, color="white", text_align=ft.TextAlign.CENTER, weight="bold"),
                        ft.Text(mode, size=11, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                        _game_menu_button("Profil löschen", remove_specific(index), "#7C2D12", width=130, height=34),
                    ],
                    spacing=5,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )
    return cards


def _questions_path_render_profiles(page: ft.Page, state: dict):
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        profiles = [_questions_path_default_profile(0)]
        persist_questions_path_profiles(state, profiles)
        state["questions_path_profiles"] = profiles

    page_w, page_h = _page_size(page)
    panel_w = max(320, int(page_w - 28))
    panel_h = max(520, int(page_h - 28))
    cards = _questions_path_profile_cards(page, state, profiles)
    state["questions_path_profiles"] = profiles
    active_index = get_questions_path_profile_index(state)
    active_profile = profiles[active_index] if active_index < len(profiles) else profiles[0]
    active_mode = _questions_path_profile_mode(active_profile)

    def save_active_profile(updated_profile: dict):
        current_profiles = get_questions_path_profiles(state)
        if not current_profiles:
            current_profiles = [_questions_path_default_profile(0)]
        while active_index >= len(current_profiles):
            current_profiles.append(_questions_path_default_profile(len(current_profiles)))
        current_profiles[active_index] = updated_profile
        persist_questions_path_profiles(state, current_profiles)
        state["questions_path_profiles"] = current_profiles

    def set_mode(mode: str):
        def _handler(e):
            refreshed = get_questions_path_profiles(state)
            profile = dict(refreshed[active_index] if active_index < len(refreshed) else active_profile)
            profile["progression_mode"] = mode
            if mode == "creative" and not list(profile.get("custom_islands", []) or []):
                profile["custom_islands"] = [_questions_path_default_custom_island(0)]
            save_active_profile(profile)
            _questions_path_render_profiles(e.page, state)

        return _handler

    def play_selected(e):
        refreshed = get_questions_path_profiles(state)
        profile = dict(refreshed[active_index] if active_index < len(refreshed) else active_profile)
        profile["progression_mode"] = "adventure"
        save_active_profile(profile)
        state["questions_path_scene"] = "islands"
        state["_questions_path_level_progress"] = 0
        state["_questions_path_level_complete"] = False
        show_questions_path_hub(e.page, state)

    def open_creator(e):
        refreshed = get_questions_path_profiles(state)
        profile = dict(refreshed[active_index] if active_index < len(refreshed) else active_profile)
        if not list(profile.get("custom_islands", []) or []):
            profile["custom_islands"] = [_questions_path_default_custom_island(0)]
            save_active_profile(profile)
        state["questions_path_scene"] = "creator"
        show_questions_path_hub(e.page, state)

    def open_custom_menu(e):
        refreshed = get_questions_path_profiles(state)
        profile = dict(refreshed[active_index] if active_index < len(refreshed) else active_profile)
        profile["progression_mode"] = "creative"
        if not list(profile.get("custom_islands", []) or []):
            profile["custom_islands"] = [_questions_path_default_custom_island(0)]
        save_active_profile(profile)
        state["questions_path_creative_action"] = "play"
        state["questions_path_scene"] = "islands"
        show_questions_path_hub(e.page, state)

    def edit_custom_game(e):
        refreshed = get_questions_path_profiles(state)
        profile = dict(refreshed[active_index] if active_index < len(refreshed) else active_profile)
        profile["progression_mode"] = "creative"
        if not list(profile.get("custom_islands", []) or []):
            profile["custom_islands"] = [_questions_path_default_custom_island(0)]
        save_active_profile(profile)
        state["questions_path_creative_action"] = "edit"
        state["questions_path_scene"] = "islands"
        show_questions_path_hub(e.page, state)

    def add_profile(e):
        current_profiles = get_questions_path_profiles(state)
        if len(current_profiles) >= QUESTIONS_PATH_PROFILE_MAX:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Maximal 10 Profile sind moeglich."), open=True)
            e.page.update()
            return
        current_profiles.append(_questions_path_default_profile(len(current_profiles)))
        persist_questions_path_profiles(state, current_profiles)
        state["questions_path_profiles"] = current_profiles
        set_questions_path_profile_index(state, len(current_profiles) - 1)
        _questions_path_render_profiles(e.page, state)

    def remove_profile(e):
        current_profiles = get_questions_path_profiles(state)
        current_index = get_questions_path_profile_index(state)
        if len(current_profiles) <= QUESTIONS_PATH_PROFILE_MIN:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Mindestens ein Profil muss bleiben."), open=True)
            e.page.update()
            return
        current_profiles.pop(current_index)
        for idx, profile in enumerate(current_profiles):
            if isinstance(profile, dict):
                default_name = f"{QUESTIONS_PATH_DEFAULT_PROFILE_NAME} {idx + 1}"
                if str(profile.get("name", "")).startswith(QUESTIONS_PATH_DEFAULT_PROFILE_NAME):
                    profile["name"] = default_name
        persist_questions_path_profiles(state, current_profiles)
        state["questions_path_profiles"] = current_profiles
        set_questions_path_profile_index(state, min(current_index, len(current_profiles) - 1))
        _questions_path_render_profiles(e.page, state)

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    ft.Container(expand=True, bgcolor="#07130F"),
                    ft.Container(expand=True, bgcolor="#071B24E0"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=14,
                        content=ft.Container(
                            width=panel_w,
                            height=panel_h,
                            padding=ft.Padding(24, 20, 24, 20),
                            border_radius=24,
                            bgcolor="#071019F2",
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            _game_menu_button("← Spielauswahl", lambda e: open_main_menu(e.page, state), "#475569", width=180, height=40),
                                            ft.Text("Fragen-Pfad", size=30, weight="bold", color="white"),
                                            ft.Row(
                                                [
                                                    _game_menu_button("+ Profil", add_profile, "#0F766E", width=130, height=40),
                                                ],
                                                spacing=10,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("Wähle ein Profil.", size=13, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                                    ft.Text(f"{len(profiles)}/{QUESTIONS_PATH_PROFILE_MAX} Profile", size=12, color="#8FB7C9", text_align=ft.TextAlign.CENTER),
                                    ft.Container(height=8),
                                    ft.Text("Profile", size=16, weight="bold", color=theme["gold"], text_align=ft.TextAlign.CENTER),
                                    ft.Container(
                                        expand=True,
                                        content=ft.Column(
                                            [
                                                ft.Row(cards, spacing=12, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
                                                ft.Container(height=10),
                                                ft.Text(
                                                    f"Aktives Profil: {active_profile.get('name', f'Profil {active_index + 1}')}",
                                                    size=13,
                                                    color="#D7E6F5",
                                                    text_align=ft.TextAlign.CENTER,
                                                ),
                                                ft.Row(
                                                    [
                                                        _game_menu_button("Schnelles Spiel", play_selected, "#0F766E", width=220, height=42),
                                                        _game_menu_button(
                                                            "Eigenes Spiel",
                                                            open_custom_menu,
                                                            "#1D4ED8",
                                                            width=220,
                                                            height=42,
                                                        ),
                                                        _game_menu_button(
                                                            "Spiel bearbeiten",
                                                            edit_custom_game,
                                                            "#475569",
                                                            width=220,
                                                            height=42,
                                                        ),
                                                    ],
                                                    alignment=ft.MainAxisAlignment.CENTER,
                                                    spacing=12,
                                                ),
                                                ft.Row(
                                                    [
                                                        ft.Container(
                                                            tooltip="Abenteuer: Inseln werden nach und nach freigeschaltet.",
                                                            content=_game_menu_button(
                                                                "Abenteuer Modus",
                                                                set_mode("adventure"),
                                                                "#0F766E" if active_mode == "adventure" else "#334155",
                                                                width=220,
                                                                height=42,
                                                            ),
                                                        ),
                                                        ft.Container(
                                                            tooltip="Kreativ: Eigene Inseln sind direkt verfügbar und frei bearbeitbar.",
                                                            content=_game_menu_button(
                                                                "Kreativ Modus",
                                                                set_mode("creative"),
                                                                "#0F766E" if active_mode == "creative" else "#334155",
                                                                width=220,
                                                                height=42,
                                                            ),
                                                        ),
                                                    ],
                                                    alignment=ft.MainAxisAlignment.CENTER,
                                                    spacing=12,
                                                ),
                                                ft.Text(
                                                    "Abenteuer schaltet Inseln nach und nach frei. Kreativ zeigt alle selbstgebauten Inseln direkt an.",
                                                    size=12,
                                                    color="#A8C0D2",
                                                    text_align=ft.TextAlign.CENTER,
                                                ),
                                            ],
                                            spacing=10,
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            scroll=ft.ScrollMode.AUTO,
                                        ),
                                    ),
                                ],
                                spacing=10,
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
    page.run_task(_sync_bg_music_async, page, state)


def _questions_path_render_creator(page: ft.Page, state: dict):
    profiles = get_questions_path_profiles(state)
    if not profiles:
        profiles = [_questions_path_default_profile(0)]
        persist_questions_path_profiles(state, profiles)
    state["questions_path_profiles"] = profiles
    active_index = get_questions_path_profile_index(state)
    profile = dict(profiles[active_index] if active_index < len(profiles) else profiles[0])
    custom_islands = list(profile.get("custom_islands", []) or [])
    custom_designs = list(profile.get("custom_designs", []) or [])
    selected_index = max(0, min(int(state.get("_questions_path_creator_index", 0) or 0), max(0, len(custom_islands) - 1)))
    selected_exists = bool(custom_islands)
    state["_questions_path_creator_index"] = selected_index if selected_exists else 0
    selection_visible = bool(state.get("_questions_path_creator_selection_visible", True))
    state.setdefault("_questions_path_creator_selection_visible", selection_visible)
    selected = dict(custom_islands[selected_index]) if selected_exists else _questions_path_default_custom_island(0)
    selected_cfg = _questions_path_custom_map(selected, selected_index if selected_exists else 0)
    add_mode = state.get("_questions_path_add_island_mode")
    choose_custom_design = bool(state.get("_questions_path_choose_custom_design", False))
    creator_world_open = bool(state.get("_questions_path_creator_world_open", False))
    creator_zoom = max(0.5, min(1.8, float(state.get("questions_path_creator_zoom", 1.0) or 1.0)))
    state["questions_path_creator_zoom"] = creator_zoom
    creator_canvas_w = 1600
    creator_canvas_h = 1000

    island_name_ref = ft.Ref[ft.TextField]()
    island_icon_ref = ft.Ref[ft.TextField]()
    island_subtitle_ref = ft.Ref[ft.TextField]()
    world_name_ref = ft.Ref[ft.TextField]()
    world_description_ref = ft.Ref[ft.TextField]()
    custom_design_ref = ft.Ref[ft.TextField]()
    world_layout_ref = ft.Ref[ft.Dropdown]()
    drag_points = state.setdefault("_questions_path_drag_points", {})
    drag_positions = state.setdefault("_questions_path_drag_positions", {})
    resize_positions = state.setdefault("_questions_path_resize_positions", {})
    point_drag_positions = state.setdefault("_questions_path_drag_point_positions", {})
    island_marker_refs: dict[int, ft.Ref[ft.Container]] = {}
    point_marker_refs: dict[int, ft.Ref[ft.Container]] = {}
    active_point_index = max(0, int(state.get("_questions_path_active_point_index", 0) or 0))
    question_dialog_open = bool(state.get("_questions_path_question_dialog_open", False))
    choose_world_map = bool(state.get("_questions_path_choose_world_map", False))

    def clear_island_selection(e):
        state["_questions_path_creator_selection_visible"] = False
        _questions_path_render_creator(e.page, state)

    def island_card_scale(island: dict) -> float:
        try:
            return max(0.8, min(1.8, float(island.get("card_scale", 1.0) or 1.0)))
        except Exception:
            return 1.0

    def island_card_size(island: dict) -> tuple[int, int]:
        scale = island_card_scale(island)
        return max(180, int(240 * scale)), max(132, int(176 * scale))

    def island_left_from_percent(percent_x: float, card_w: int) -> int:
        return max(24, min(int(creator_canvas_w - card_w - 24), int((float(percent_x) / 100.0) * (creator_canvas_w - card_w))))

    def island_top_from_percent(percent_y: float, card_h: int) -> int:
        return max(24, min(int(creator_canvas_h - card_h - 24), int((float(percent_y) / 100.0) * (creator_canvas_h - card_h))))

    def point_left_from_percent(percent_x: float) -> int:
        point_size = 54
        return max(8, min(int(creator_canvas_w - point_size - 8), int((float(percent_x) / 100.0) * (creator_canvas_w - point_size))))

    def point_top_from_percent(percent_y: float) -> int:
        point_size = 54
        return max(8, min(int(creator_canvas_h - point_size - 8), int((float(percent_y) / 100.0) * (creator_canvas_h - point_size))))

    def persist(current_profile: dict):
        current_profiles = get_questions_path_profiles(state)
        if not current_profiles:
            current_profiles = [_questions_path_default_profile(0)]
        while active_index >= len(current_profiles):
            current_profiles.append(_questions_path_default_profile(len(current_profiles)))
        current_profiles[active_index] = current_profile
        persist_questions_path_profiles(state, current_profiles)
        state["questions_path_profiles"] = current_profiles

    def update_profile(mutator):
        current_profiles = get_questions_path_profiles(state)
        current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
        mutator(current_profile)
        persist(current_profile)

    def update_selected(mutator, rerender_page=None):
        current_profiles = get_questions_path_profiles(state)
        current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
        islands = list(current_profile.get("custom_islands", []) or [])
        if not islands:
            return
        idx = max(0, min(int(state.get("_questions_path_creator_index", 0) or 0), len(islands) - 1))
        island = dict(islands[idx])
        mutator(island)
        islands[idx] = island
        for island_idx, item in enumerate(islands):
            item["map_key"] = f"custom_{island_idx + 1}"
        current_profile["custom_islands"] = islands
        current_profile["progression_mode"] = "creative"
        persist(current_profile)
        _questions_path_render_creator(rerender_page or page, state)

    def select_island(index: int):
        def _handler(e):
            state["_questions_path_creator_index"] = index
            state["_questions_path_creator_selection_visible"] = True
            _questions_path_render_creator(e.page, state)

        return _handler

    def open_add_menu(e):
        state["_questions_path_add_island_mode"] = "preset"
        _questions_path_render_creator(e.page, state)

    def close_add_menu(e):
        state.pop("_questions_path_add_island_mode", None)
        state.pop("_questions_path_choose_custom_design", None)
        _questions_path_render_creator(e.page, state)

    def choose_preset(design_idx: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if len(islands) >= 10:
                e.page.snack_bar = ft.SnackBar(content=ft.Text("Maximal 10 eigene Inseln sind möglich."), open=True)
                e.page.update()
                return
            island = _questions_path_default_custom_island(len(islands))
            theme = QUESTIONS_PATH_CREATIVE_THEMES[design_idx % len(QUESTIONS_PATH_CREATIVE_THEMES)]
            island["icon"] = theme["icon"]
            island["accent"] = theme["accent"]
            island["panel"] = theme["panel"]
            island["border"] = theme["border"]
            island["line"] = theme["line"]
            island["design_id"] = f"theme_{design_idx}"
            islands.append(island)
            current_profile["custom_islands"] = islands
            current_profile["progression_mode"] = "creative"
            persist(current_profile)
            state["_questions_path_creator_index"] = len(islands) - 1
            state.pop("_questions_path_add_island_mode", None)
            _questions_path_render_creator(e.page, state)

        return _handler

    def open_custom_design(e):
        state["_questions_path_choose_custom_design"] = True
        _questions_path_render_creator(e.page, state)

    async def pick_custom_design_task(page_obj: ft.Page):
        rel_path = await _questions_path_pick_and_store_image(page_obj, "island_design")
        if not rel_path:
            return
        current_profiles = get_questions_path_profiles(state)
        current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
        designs = list(current_profile.get("custom_designs", []) or [])
        if rel_path not in designs:
            designs.append(rel_path)
        current_profile["custom_designs"] = designs[-12:]
        persist(current_profile)
        state["_questions_path_choose_custom_design"] = False
        state.pop("_questions_path_add_island_mode", None)
        _questions_path_render_creator(page_obj, state)

    def pick_custom_design(e):
        e.page.run_task(pick_custom_design_task, e.page)

    def add_custom_design(e):
        raw_value = str(custom_design_ref.current.value or "").strip() if custom_design_ref.current else ""
        if not raw_value:
            return
        current_profiles = get_questions_path_profiles(state)
        current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
        designs = list(current_profile.get("custom_designs", []) or [])
        if raw_value not in designs:
            designs.append(raw_value)
        current_profile["custom_designs"] = designs[-12:]
        persist(current_profile)
        state["_questions_path_choose_custom_design"] = False
        state.pop("_questions_path_add_island_mode", None)
        _questions_path_render_creator(e.page, state)

    def choose_saved_design(design_value: str):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if len(islands) >= 10:
                e.page.snack_bar = ft.SnackBar(content=ft.Text("Maximal 10 eigene Inseln sind möglich."), open=True)
                e.page.update()
                return
            island = _questions_path_default_custom_island(len(islands))
            island["image_src"] = design_value
            island["icon"] = "🖼️"
            island["design_id"] = "custom_image"
            islands.append(island)
            current_profile["custom_islands"] = islands
            current_profile["progression_mode"] = "creative"
            persist(current_profile)
            state["_questions_path_creator_index"] = len(islands) - 1
            state.pop("_questions_path_add_island_mode", None)
            state["_questions_path_choose_custom_design"] = False
            _questions_path_render_creator(e.page, state)

        return _handler

    def remove_island(e):
        current_profiles = get_questions_path_profiles(state)
        current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
        islands = list(current_profile.get("custom_islands", []) or [])
        if not islands:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Es gibt noch keine Insel zum Löschen."), open=True)
            e.page.update()
            return
        if len(islands) <= 1:
            islands = []
            current_profile["custom_islands"] = islands
            persist(current_profile)
            state["_questions_path_creator_index"] = 0
            state["_questions_path_creator_world_open"] = False
            _questions_path_render_creator(e.page, state)
            e.page.update()
            return
        islands.pop(selected_index)
        for island_idx, item in enumerate(islands):
            item["map_key"] = f"custom_{island_idx + 1}"
        current_profile["custom_islands"] = islands
        persist(current_profile)
        state["_questions_path_creator_index"] = min(selected_index, len(islands) - 1)
        _questions_path_render_creator(e.page, state)

    def toggle_world_editor(e):
        if not custom_islands:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Füge zuerst eine Insel hinzu."), open=True)
            e.page.update()
            return
        state["_questions_path_creator_world_open"] = not creator_world_open
        _questions_path_render_creator(e.page, state)

    def save_island_details(e):
        def _mutate(island):
            island["title"] = str(island_name_ref.current.value or island.get("title", "")).strip() or island.get("title", "Eigene Insel")
            island["icon"] = str(island_icon_ref.current.value or island.get("icon", "")).strip() or island.get("icon", "🏝️")
            island["subtitle"] = str(island_subtitle_ref.current.value or island.get("subtitle", "")).strip() or island.get("subtitle", "")
            island["world_name"] = str(world_name_ref.current.value or island.get("world_name", "")).strip() or island.get("world_name", "Eigene Welt")
            island["world_description"] = str(world_description_ref.current.value or island.get("world_description", "")).strip() or island.get("world_description", "")
            if world_layout_ref.current:
                island["world_layout"] = str(world_layout_ref.current.value or island.get("world_layout", "classic"))

        update_selected(_mutate, e.page)

    async def pick_selected_island_image_task(page_obj: ft.Page):
        rel_path = await _questions_path_pick_and_store_image(page_obj, "island_card")
        if not rel_path:
            return
        def _mutate(island):
            island["image_src"] = rel_path
            island["design_id"] = "custom_image"
        update_selected(_mutate, page_obj)

    async def pick_selected_map_image_task(page_obj: ft.Page):
        rel_path = await _questions_path_pick_and_store_image(page_obj, "world_map")
        if not rel_path:
            return
        def _mutate(island):
            island["map_image_src"] = rel_path
        update_selected(_mutate, page_obj)

    def pick_selected_island_image(e):
        e.page.run_task(pick_selected_island_image_task, e.page)

    def pick_selected_map_image(e):
        e.page.run_task(pick_selected_map_image_task, e.page)

    def open_world_map_menu(e):
        state["_questions_path_choose_world_map"] = True
        _questions_path_render_creator(e.page, state)

    def close_world_map_menu(e):
        state["_questions_path_choose_world_map"] = False
        _questions_path_render_creator(e.page, state)

    def choose_world_layout(layout_key: str):
        def _handler(e):
            def _mutate(island):
                island["world_layout"] = layout_key
                if not list(island.get("custom_points", []) or []):
                    island["custom_points"] = [
                        {"x": int(p["x"]), "y": int(p["y"]), "label": str(p.get("label", f"Punkt {idx + 1}"))}
                        for idx, p in enumerate(QUESTIONS_PATH_WORLD_LAYOUTS.get(layout_key, QUESTIONS_PATH_WORLD_LAYOUTS["classic"])["points"][: max(1, len(list(island.get("questions", []) or [])) )])
                    ]

            state["_questions_path_choose_world_map"] = False
            update_selected(_mutate, e.page)

        return _handler

    def set_active_point(index: int):
        def _handler(e):
            state["_questions_path_active_point_index"] = index
            _questions_path_render_creator(e.page, state)

        return _handler

    def open_question_dialog_for(index: int):
        def _handler(e):
            state["_questions_path_active_point_index"] = index
            state["_questions_path_question_dialog_open"] = True
            _questions_path_render_creator(e.page, state)

        return _handler

    def close_question_dialog(e):
        state["_questions_path_question_dialog_open"] = False
        _questions_path_render_creator(e.page, state)

    def move_selected_island(dx: float, dy: float):
        def _handler(e):
            def _mutate(island):
                island["map_x"] = max(2, min(88, float(island.get("map_x", 20)) + dx))
                island["map_y"] = max(2, min(82, float(island.get("map_y", 20)) + dy))

            update_selected(_mutate, e.page)

        return _handler

    def nudge_point(point_index: int, dx: float, dy: float):
        def _handler(e):
            def _mutate(island):
                custom_points = ensure_custom_points(island)
                if point_index < len(custom_points):
                    custom_points[point_index]["x"] = int(max(4, min(96, float(custom_points[point_index].get("x", 10)) + dx)))
                    custom_points[point_index]["y"] = int(max(4, min(96, float(custom_points[point_index].get("y", 10)) + dy)))
                    island["custom_points"] = custom_points

            update_selected(_mutate, e.page)

        return _handler

    def add_point(e):
        def _mutate(island):
            questions = list(island.get("questions", []) or [])
            if len(questions) < 10:
                questions.append(_questions_path_default_custom_question(len(questions)))
                custom_points = ensure_custom_points(island)
                custom_points.append(
                    {
                        "x": max(8, min(90, 18 + len(custom_points) * 7)),
                        "y": max(10, min(86, 18 + (len(custom_points) % 4) * 10)),
                        "label": f"Punkt {len(custom_points) + 1}",
                    }
                )
                island["custom_points"] = custom_points[: len(questions)]
            island["questions"] = questions

        update_selected(_mutate, e.page)
        refreshed_profiles = get_questions_path_profiles(state)
        refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else profile)
        refreshed_islands = list(refreshed_profile.get("custom_islands", []) or [])
        if selected_index < len(refreshed_islands):
            refreshed_selected = dict(refreshed_islands[selected_index])
            state["_questions_path_active_point_index"] = max(0, len(list(refreshed_selected.get("questions", []) or [])) - 1)
        state["_questions_path_question_dialog_open"] = True
        _questions_path_render_creator(e.page, state)

    def remove_active_point(e):
        def _mutate(island):
            questions = list(island.get("questions", []) or [])
            custom_points = ensure_custom_points(island)
            point_idx = max(0, min(int(state.get("_questions_path_active_point_index", 0) or 0), len(custom_points) - 1))
            if len(custom_points) <= 1 or len(questions) <= 1:
                return
            custom_points.pop(point_idx)
            questions.pop(point_idx)
            island["custom_points"] = custom_points
            island["questions"] = questions

        new_index = max(0, active_point_index - 1)
        state["_questions_path_active_point_index"] = new_index
        state["_questions_path_question_dialog_open"] = False
        update_selected(_mutate, e.page)

    def remove_question(question_index: int):
        def _handler(e):
            def _mutate(island):
                questions = list(island.get("questions", []) or [])
                if len(questions) > 1 and question_index < len(questions):
                    questions.pop(question_index)
                island["questions"] = questions

            update_selected(_mutate, e.page)

        return _handler

    def save_question(question_index: int, question_ref, answer_refs, correct_ref):
        def _handler(e):
            def _mutate(island):
                questions = list(island.get("questions", []) or [])
                if question_index >= len(questions):
                    return
                question = dict(questions[question_index])
                question["question"] = str(question_ref.current.value or question.get("question", "")).strip() or question.get("question", "Frage")
                answers = []
                existing_answers = list(question.get("answers", []) or [])
                while len(existing_answers) < 4:
                    existing_answers.append("")
                for idx, ref in enumerate(answer_refs):
                    answer_text = str(ref.current.value or "").strip() if ref.current else ""
                    answers.append(answer_text or existing_answers[idx] or f"Antwort {ANSWER_LETTERS[idx]}")
                question["answers"] = answers[:4]
                question["correct_idx"] = int(correct_ref.current.value or question.get("correct_idx", 0)) if correct_ref.current else int(question.get("correct_idx", 0))
                questions[question_index] = question
                island["questions"] = questions

            state["_questions_path_question_dialog_open"] = False
            update_selected(_mutate, e.page)

        return _handler

    def drag_start_island(index: int):
        def _handler(e):
            state["_questions_path_creator_selection_visible"] = True
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index < len(islands):
                island = dict(islands[index])
                drag_positions[index] = {
                    "map_x": float(island.get("map_x", 20)),
                    "map_y": float(island.get("map_y", 20)),
                }

        return _handler

    def drag_island(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index >= len(islands):
                return
            delta_x = float(getattr(e, "delta_x", 0.0) or 0.0)
            delta_y = float(getattr(e, "delta_y", 0.0) or 0.0)
            if delta_x == 0.0 and delta_y == 0.0:
                current_x = float(getattr(e, "global_x", getattr(e, "local_x", 0.0)) or 0.0)
                current_y = float(getattr(e, "global_y", getattr(e, "local_y", 0.0)) or 0.0)
                last_x, last_y = drag_points.get(index, (current_x, current_y))
                delta_x = current_x - last_x
                delta_y = current_y - last_y
                drag_points[index] = (current_x, current_y)
            current_drag = drag_positions.get(index, {"map_x": float(islands[index].get("map_x", 20)), "map_y": float(islands[index].get("map_y", 20))})
            current_drag["map_x"] = max(2, min(88, float(current_drag.get("map_x", 20)) + (delta_x / max(1, creator_canvas_w * creator_zoom)) * 100))
            current_drag["map_y"] = max(2, min(82, float(current_drag.get("map_y", 20)) + (delta_y / max(1, creator_canvas_h * creator_zoom)) * 100))
            drag_positions[index] = current_drag
            marker_ref = island_marker_refs.get(index)
            if marker_ref and marker_ref.current:
                current_card_w, current_card_h = island_card_size(islands[index])
                marker_ref.current.left = island_left_from_percent(current_drag["map_x"], current_card_w)
                marker_ref.current.top = island_top_from_percent(current_drag["map_y"], current_card_h)
                e.page.update()

        return _handler

    def drag_end_island(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index < len(islands) and index in drag_positions:
                island = dict(islands[index])
                island["map_x"] = float(drag_positions[index].get("map_x", island.get("map_x", 20)))
                island["map_y"] = float(drag_positions[index].get("map_y", island.get("map_y", 20)))
                islands[index] = island
                current_profile["custom_islands"] = islands
                persist(current_profile)
            drag_points.pop(index, None)
            drag_positions.pop(index, None)
            _questions_path_render_creator(e.page, state)

        return _handler

    def resize_start_island(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index < len(islands):
                island = dict(islands[index])
                card_w, card_h = island_card_size(island)
                left_px = island_left_from_percent(float(island.get("map_x", 20) or 20), card_w)
                top_px = island_top_from_percent(float(island.get("map_y", 20) or 20), card_h)
                resize_positions[index] = {
                    "card_scale": island_card_scale(island),
                    "card_w": card_w,
                    "card_h": card_h,
                    "left_px": left_px,
                    "top_px": top_px,
                    "anchor_x": float(card_w),
                    "anchor_y": float(card_h),
                }

        return _handler

    def resize_island(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index >= len(islands):
                return
            island = dict(islands[index])
            start_data = resize_positions.get(index)
            if not start_data:
                card_w, card_h = island_card_size(island)
                start_data = {
                    "card_scale": island_card_scale(island),
                    "card_w": card_w,
                    "card_h": card_h,
                    "left_px": island_left_from_percent(float(island.get("map_x", 20) or 20), card_w),
                    "top_px": island_top_from_percent(float(island.get("map_y", 20) or 20), card_h),
                    "anchor_x": float(card_w),
                    "anchor_y": float(card_h),
                }
                resize_positions[index] = dict(start_data)
            delta_x = float(getattr(e, "delta_x", 0.0) or 0.0)
            delta_y = float(getattr(e, "delta_y", 0.0) or 0.0)
            delta = (delta_x + delta_y) / 2.0
            current_drag = dict(start_data)
            new_scale = max(0.8, min(1.8, float(current_drag.get("card_scale", 1.0)) + (delta / 220.0)))
            new_w = max(180, int(240 * new_scale))
            new_h = max(132, int(176 * new_scale))
            left_px = int(current_drag.get("left_px", 0))
            top_px = int(current_drag.get("top_px", 0))
            anchor_x = float(current_drag.get("anchor_x", current_drag.get("card_w", new_w)))
            anchor_y = float(current_drag.get("anchor_y", current_drag.get("card_h", new_h)))
            map_x = max(2, min(96, (left_px / max(1, creator_canvas_w - new_w)) * 100))
            map_y = max(2, min(96, (top_px / max(1, creator_canvas_h - new_h)) * 100))
            current_drag["card_scale"] = new_scale
            current_drag["card_w"] = new_w
            current_drag["card_h"] = new_h
            current_drag["map_x"] = map_x
            current_drag["map_y"] = map_y
            resize_positions[index] = current_drag
            island["card_scale"] = new_scale
            island["map_x"] = map_x
            island["map_y"] = map_y
            islands[index] = island
            current_profile["custom_islands"] = islands
            persist(current_profile)
            marker_ref = island_marker_refs.get(index)
            if marker_ref and marker_ref.current:
                marker_ref.current.width = new_w
                marker_ref.current.height = new_h
                marker_ref.current.left = left_px
                marker_ref.current.top = top_px
                e.page.update()

        return _handler

    def resize_end_island(index: int):
        def _handler(e):
            resize_positions.pop(index, None)
            _questions_path_render_creator(e.page, state)

        return _handler

    def scale_start_island(index: int):
        def _handler(e):
            state["_questions_path_creator_selection_visible"] = True
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index < len(islands):
                island = dict(islands[index])
                card_w, card_h = island_card_size(island)
                left_px = island_left_from_percent(float(island.get("map_x", 20) or 20), card_w)
                top_px = island_top_from_percent(float(island.get("map_y", 20) or 20), card_h)
                focal = getattr(e, "local_focal_point", None)
                focal_x = float(getattr(focal, "x", card_w / 2) or (card_w / 2))
                focal_y = float(getattr(focal, "y", card_h / 2) or (card_h / 2))
                resize_positions[index] = {
                    "card_scale": island_card_scale(island),
                    "card_w": card_w,
                    "card_h": card_h,
                    "left_px": left_px,
                    "top_px": top_px,
                    "anchor_x": focal_x,
                    "anchor_y": focal_y,
                }

        return _handler

    def scale_island(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if index >= len(islands):
                return
            island = dict(islands[index])
            start_data = resize_positions.get(index)
            if not start_data:
                card_w, card_h = island_card_size(island)
                start_data = {
                    "card_scale": island_card_scale(island),
                    "card_w": card_w,
                    "card_h": card_h,
                    "left_px": island_left_from_percent(float(island.get("map_x", 20) or 20), card_w),
                    "top_px": island_top_from_percent(float(island.get("map_y", 20) or 20), card_h),
                    "anchor_x": card_w / 2,
                    "anchor_y": card_h / 2,
                }
                resize_positions[index] = dict(start_data)
            start_scale = float(start_data.get("card_scale", island_card_scale(island)) or 1.0)
            try:
                gesture_scale = max(0.05, float(getattr(e, "scale", 1.0) or 1.0))
            except Exception:
                gesture_scale = 1.0
            new_scale = max(0.8, min(1.8, start_scale * gesture_scale))
            start_w = int(start_data.get("card_w", 240))
            start_h = int(start_data.get("card_h", 176))
            new_w = max(180, int(240 * new_scale))
            new_h = max(132, int(176 * new_scale))
            left_px = int(start_data.get("left_px", 0) + float(start_data.get("anchor_x", start_w / 2)) * (1 - (new_w / max(1, start_w))))
            top_px = int(start_data.get("top_px", 0) + float(start_data.get("anchor_y", start_h / 2)) * (1 - (new_h / max(1, start_h))))
            map_x = max(2, min(96, (left_px / max(1, creator_canvas_w - new_w)) * 100))
            map_y = max(2, min(96, (top_px / max(1, creator_canvas_h - new_h)) * 100))
            island["card_scale"] = new_scale
            island["map_x"] = map_x
            island["map_y"] = map_y
            islands[index] = island
            current_profile["custom_islands"] = islands
            persist(current_profile)
            marker_ref = island_marker_refs.get(index)
            if marker_ref and marker_ref.current:
                marker_ref.current.width = new_w
                marker_ref.current.height = new_h
                marker_ref.current.left = left_px
                marker_ref.current.top = top_px
                marker_ref.current.update()

        return _handler

    def scale_end_island(index: int):
        def _handler(e):
            resize_positions.pop(index, None)
            _questions_path_render_creator(e.page, state)

        return _handler

    def ensure_custom_points(island: dict) -> list[dict]:
        custom_points = list(island.get("custom_points", []) or [])
        desired_count = max(1, min(10, len(list(island.get("questions", []) or []))))
        if not custom_points:
            base_points = QUESTIONS_PATH_WORLD_LAYOUTS.get(str(island.get("world_layout", "classic")), QUESTIONS_PATH_WORLD_LAYOUTS["classic"])["points"]
            custom_points = [{"x": int(p["x"]), "y": int(p["y"]), "label": str(p.get("label", f"Punkt {idx + 1}"))} for idx, p in enumerate(base_points[:desired_count])]
        while len(custom_points) < desired_count:
            custom_points.append({"x": 20 + len(custom_points) * 6, "y": 20 + len(custom_points) * 5, "label": f"Punkt {len(custom_points) + 1}"})
        return custom_points[:desired_count]

    def point_drag_start(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if selected_index < len(islands):
                island = dict(islands[selected_index])
                custom_points = ensure_custom_points(island)
                if index < len(custom_points):
                    point_drag_positions[index] = {
                        "x": float(custom_points[index].get("x", 10)),
                        "y": float(custom_points[index].get("y", 10)),
                    }

        return _handler

    def point_drag_update(index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            current_profile = dict(current_profiles[active_index] if active_index < len(current_profiles) else profile)
            islands = list(current_profile.get("custom_islands", []) or [])
            if selected_index >= len(islands):
                return
            island = dict(islands[selected_index])
            custom_points = ensure_custom_points(island)
            delta_x = float(getattr(e, "delta_x", 0.0) or 0.0)
            delta_y = float(getattr(e, "delta_y", 0.0) or 0.0)
            if delta_x == 0.0 and delta_y == 0.0:
                current_x = float(getattr(e, "global_x", getattr(e, "local_x", 0.0)) or 0.0)
                current_y = float(getattr(e, "global_y", getattr(e, "local_y", 0.0)) or 0.0)
                last_x, last_y = drag_points.get(f"point_{index}", (current_x, current_y))
                delta_x = current_x - last_x
                delta_y = current_y - last_y
                drag_points[f"point_{index}"] = (current_x, current_y)
            if index < len(custom_points):
                current_drag = point_drag_positions.get(index, {"x": float(custom_points[index].get("x", 10)), "y": float(custom_points[index].get("y", 10))})
                current_drag["x"] = max(4, min(96, float(current_drag.get("x", 10)) + (delta_x / max(1, creator_canvas_w * creator_zoom)) * 100))
                current_drag["y"] = max(4, min(96, float(current_drag.get("y", 10)) + (delta_y / max(1, creator_canvas_h * creator_zoom)) * 100))
                point_drag_positions[index] = current_drag
                custom_points[index]["x"] = int(current_drag["x"])
                custom_points[index]["y"] = int(current_drag["y"])
                island["custom_points"] = custom_points
                islands[selected_index] = island
                current_profile["custom_islands"] = islands
                persist(current_profile)
                point_ref = point_marker_refs.get(index)
                if point_ref and point_ref.current:
                    point_ref.current.left = point_left_from_percent(current_drag["x"])
                    point_ref.current.top = point_top_from_percent(current_drag["y"])
                    e.page.update()

        return _handler

    def point_drag_end(index: int):
        def _handler(e):
            drag_points.pop(f"point_{index}", None)
            point_drag_positions.pop(index, None)
            _questions_path_render_creator(e.page, state)

        return _handler

    island_markers = []
    for idx, island in enumerate(custom_islands):
        cfg = _questions_path_custom_map(island, idx)
        active = idx == selected_index and selection_visible
        preview_position = drag_positions.get(idx, {})
        marker_x = float(preview_position.get("map_x", island.get("map_x", 20)))
        marker_y = float(preview_position.get("map_y", island.get("map_y", 20)))
        card_w, card_h = island_card_size(island)
        marker_ref = ft.Ref[ft.Container]()
        island_marker_refs[idx] = marker_ref
        marker_content = ft.Container(
            width=card_w,
            height=card_h,
            padding=18,
            border_radius=24,
            bgcolor="#09131DE8",
            border=ft.border.Border.all(2, cfg.get("accent", "#34D399") if active else "#334155"),
            shadow=ft.BoxShadow(blur_radius=22, color=f"#33{cfg.get('accent', '#34D399')[1:]}", spread_radius=0),
            content=ft.Stack(
                [
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(0, 0, 28, 0),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            width=58,
                                            height=58,
                                            border_radius=999,
                                            alignment=ft.Alignment(0, 0),
                                            gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=["#14304A", "#1D4F73", "#17365A"]),
                                            content=ft.Image(src=cfg.get("image_src", ""), fit=ft.BoxFit.COVER, border_radius=999, error_content=ft.Text(cfg.get("icon", "🏝️"), size=26, color="white")) if cfg.get("image_src") else ft.Text(cfg.get("icon", "🏝️"), size=28, color="white"),
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(cfg.get("title", f"Insel {idx + 1}"), size=16, weight="bold", color="white", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                                ft.Text(QUESTIONS_PATH_WORLD_LAYOUTS.get(cfg.get("world_layout", "classic"), QUESTIONS_PATH_WORLD_LAYOUTS["classic"])["label"], size=11, color="#A8C0D2"),
                                            ],
                                            spacing=4,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                ft.Text(cfg.get("subtitle", ""), size=12, color="#D5E3EE", max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(f"{len(cfg.get('questions', []))} Fragen", size=12, color=cfg.get("accent", "#34D399"), weight="bold"),
                            ],
                            spacing=10,
                        ),
                    ),
                    ft.Container(
                        right=4,
                        bottom=4,
                        width=28,
                        height=28,
                        border_radius=9,
                        bgcolor="#0F172AEE",
                        border=ft.border.Border.all(1.2, "#D1D5DB"),
                        alignment=ft.Alignment(0, 0),
                        content=ft.GestureDetector(
                            on_pan_start=resize_start_island(idx),
                            on_pan_update=resize_island(idx),
                            on_pan_end=resize_end_island(idx),
                            mouse_cursor=ft.MouseCursor.RESIZE_DOWN_RIGHT,
                            drag_interval=6,
                            content=ft.Text("↘", size=14, color="white", weight="bold"),
                        ),
                    ),
                ],
            ),
        )
        island_markers.append(
            ft.Container(
                ref=marker_ref,
                left=island_left_from_percent(marker_x, card_w),
                top=island_top_from_percent(marker_y, card_h),
                width=card_w,
                height=card_h,
                content=ft.GestureDetector(
                    on_pan_start=drag_start_island(idx),
                    on_pan_update=drag_island(idx),
                    on_pan_end=drag_end_island(idx),
                    on_scale_start=scale_start_island(idx),
                    on_scale_update=scale_island(idx),
                    on_scale_end=scale_end_island(idx),
                    on_tap=select_island(idx),
                    drag_interval=6,
                    mouse_cursor=ft.MouseCursor.MOVE,
                    content=marker_content,
                ),
            )
        )

    preset_cards = []
    for idx, theme in enumerate(QUESTIONS_PATH_CREATIVE_THEMES):
        preset_cards.append(
            ft.Container(
                width=180,
                height=120,
                border_radius=22,
                padding=16,
                bgcolor="#0B1620",
                border=ft.border.Border.all(1.5, theme["accent"]),
                on_click=choose_preset(idx),
                content=ft.Column(
                    [
                        ft.Text(theme["icon"], size=28, text_align=ft.TextAlign.CENTER),
                        ft.Text(f"Vorlage {idx + 1}", size=16, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                        ft.Text("Design übernehmen", size=12, color="#A8C0D2", text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    selected_questions = list(selected.get("questions", []) or [])
    if not selected_questions:
        selected_questions = [_questions_path_default_custom_question(0)]
    active_point_index = max(0, min(active_point_index, len(selected_questions) - 1))
    state["_questions_path_active_point_index"] = active_point_index
    active_question = dict(selected_questions[active_point_index])
    active_answers = list(active_question.get("answers", []) or [])
    while len(active_answers) < 4:
        active_answers.append("")
    question_ref = ft.Ref[ft.TextField]()
    answer_refs = [ft.Ref[ft.TextField]() for _ in range(4)]
    correct_ref = ft.Ref[ft.Dropdown]()

    world_dropdown = ft.Dropdown(
        ref=world_layout_ref,
        value=str(selected.get("world_layout", "classic") or "classic"),
        label="Weltdesign",
        bgcolor="#111827",
        color="white",
        border_color="#334155",
        options=[ft.dropdown.Option(key, text=value["label"]) for key, value in QUESTIONS_PATH_WORLD_LAYOUTS.items()],
    )

    point_controls = []
    point_overlay_controls = []
    editable_points = ensure_custom_points(selected)
    for point_index, point in enumerate(editable_points):
        point_ref = ft.Ref[ft.Container]()
        point_marker_refs[point_index] = point_ref
        point_overlay_controls.append(
            ft.Container(
                ref=point_ref,
                left=point_left_from_percent(point["x"]),
                top=point_top_from_percent(point["y"]),
                content=ft.GestureDetector(
                    on_pan_start=point_drag_start(point_index),
                    on_pan_update=point_drag_update(point_index),
                    on_pan_end=point_drag_end(point_index),
                    on_tap=open_question_dialog_for(point_index),
                    drag_interval=6,
                    mouse_cursor=ft.MouseCursor.MOVE,
                    content=ft.Container(
                        width=54,
                        height=54,
                        border_radius=999,
                        bgcolor="#10B981" if point_index == active_point_index else "#0EA5E9",
                        border=ft.border.Border.all(3, "#D1FAE5" if point_index == active_point_index else "#BFDBFE"),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(str(point_index + 1), size=18, weight="bold", color="#08131F"),
                    ),
                ),
            )
        )
        point_controls.append(
            ft.Row(
                [
                    ft.Text(f"Punkt {point_index + 1}: {point.get('label', f'Punkt {point_index + 1}')}", size=12, color="#D5E3EE"),
                    ft.Row(
                        [
                            ft.Text(f"x={point['x']}  y={point['y']}", size=11, color="#8FB7C9"),
                            _game_menu_button("←", nudge_point(point_index, -2, 0), "#334155", width=40, height=30),
                            _game_menu_button("↑", nudge_point(point_index, 0, -2), "#334155", width=40, height=30),
                            _game_menu_button("↓", nudge_point(point_index, 0, 2), "#334155", width=40, height=30),
                            _game_menu_button("→", nudge_point(point_index, 2, 0), "#334155", width=40, height=30),
                        ],
                        spacing=6,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _questions_path_backdrop("#34D399", "#38BDF8"),
                    ft.Container(
                        expand=True,
                        padding=14,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        _game_menu_button("← Profile", lambda e: (state.__setitem__("questions_path_scene", "profiles"), show_questions_path_hub(e.page, state)), "#475569", width=180, height=40),
                                        ft.Text("Eigene Inselwelt", size=30, weight="bold", color="white"),
                                        ft.Row(
                                            [
                                                _game_menu_button("Welt betreten", toggle_world_editor, "#0F766E", width=180, height=40),
                                                _game_menu_button("+ Insel", open_add_menu, "#1D4ED8", width=140, height=40),
                                                _game_menu_button("- Insel", remove_island, "#7C2D12", width=140, height=40),
                                            ],
                                            spacing=10,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Container(
                                    expand=True,
                                    border_radius=28,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    bgcolor="#061621E8",
                                    content=ft.Container(
                                        alignment=ft.Alignment(0, 0),
                                        content=ft.Container(
                                            width=int(creator_canvas_w * creator_zoom),
                                            height=int(creator_canvas_h * creator_zoom),
                                            animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
                                            content=ft.Container(
                                                width=creator_canvas_w,
                                                height=creator_canvas_h,
                                                scale=creator_zoom,
                                                content=ft.Stack(
                                                    [
                                                        ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=["#06111A", "#092638", "#06131D"]), on_click=clear_island_selection),
                                                        ft.Container(
                                                            expand=True,
                                                            opacity=0.34,
                                                            on_click=clear_island_selection,
                                                            content=ft.Image(
                                                                src=_questions_path_cached_image_src(selected_cfg.get("map_image_src", "")),
                                                                fit=ft.BoxFit.COVER,
                                                                error_content=ft.Container(),
                                                            ) if selected_cfg.get("map_image_src") else ft.Container(),
                                                        ),
                                                        ft.Container(left=140, top=80, width=320, height=180, border_radius=999, bgcolor="#0BFFFFFF"),
                                                        ft.Container(right=160, bottom=120, width=420, height=220, border_radius=999, bgcolor="#08FFFFFF"),
                                                        *island_markers,
                                                        ft.Container(
                                                            visible=not custom_islands,
                                                            expand=True,
                                                            alignment=ft.Alignment(0, 0),
                                                            content=ft.Container(
                                                                width=420,
                                                                padding=24,
                                                                border_radius=24,
                                                                bgcolor="#071019E6",
                                                                border=ft.border.Border.all(1.5, "#38BDF8"),
                                                                content=ft.Column(
                                                                    [
                                                                        ft.Text("Leere Inselwelt", size=28, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                                                                        ft.Text("Hier kannst du deine eigene Welt aufbauen. Starte oben rechts mit `+ Insel` und ziehe die Karten danach frei auf der Fläche herum.", size=14, color="#D5E3EE", text_align=ft.TextAlign.CENTER),
                                                                    ],
                                                                    spacing=10,
                                                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                                ),
                                    ),
                                                        ),
                                                    ],
                                                    expand=True,
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                                ft.Row(
                                    [
                                        _questions_path_zoom_controls(state, "questions_path_creator_zoom", lambda p, s: _questions_path_render_creator(p, s)),
                                        ft.Text("Inseln ziehen, zoomen und dann Welt betreten für Fragen/Punkte.", size=13, color="#A8C0D2"),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Container(
                                    visible=selected_exists,
                                    padding=ft.Padding(12, 0, 12, 0),
                                    content=ft.Row(
                                        [
                                            ft.TextField(
                                                ref=island_name_ref,
                                                value=selected.get("title", ""),
                                                label="Inselname",
                                                bgcolor="#111827",
                                                color="white",
                                                border_color="#334155",
                                                expand=True,
                                            ),
                                            _game_menu_button("Name speichern", save_island_details, "#0F766E", width=180, height=40),
                                        ],
                                        spacing=10,
                                    ),
                                ),
                                ft.Container(
                                    visible=creator_world_open and selected_exists,
                                    height=620,
                                    border_radius=24,
                                    bgcolor="#071019F2",
                                    padding=20,
                                    content=ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Text(f"Bearbeite: {selected_cfg.get('title', 'Eigene Insel')}", size=22, weight="bold", color="white"),
                                                    _game_menu_button("Insel speichern", save_island_details, "#0F766E", width=180, height=40),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.TextField(ref=island_icon_ref, value=selected.get("icon", "🏝️"), label="Emoji / Symbol", bgcolor="#111827", color="white", border_color="#334155", width=180),
                                                    ft.Text("Inselname oben ändern", size=12, color="#A8C0D2"),
                                                ],
                                                spacing=10,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.TextField(ref=island_subtitle_ref, value=selected.get("subtitle", ""), label="Beschreibung", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                                    world_dropdown,
                                                ],
                                                spacing=10,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.TextField(ref=world_name_ref, value=selected.get("world_name", selected.get("title", "Eigene Welt")), label="Weltname", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                                    ft.TextField(ref=world_description_ref, value=selected.get("world_description", selected.get("subtitle", "")), label="Weltbeschreibung", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                                ],
                                                spacing=10,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.Text("Insel verschieben", size=14, weight="bold", color="white"),
                                                    ft.Row(
                                                        [
                                                            _game_menu_button("←", move_selected_island(-2.5, 0), "#334155", width=52, height=36),
                                                            _game_menu_button("↑", move_selected_island(0, -2.5), "#334155", width=52, height=36),
                                                            _game_menu_button("↓", move_selected_island(0, 2.5), "#334155", width=52, height=36),
                                                            _game_menu_button("→", move_selected_island(2.5, 0), "#334155", width=52, height=36),
                                                        ],
                                                        spacing=8,
                                                    ),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            ),
                                            ft.Text("Punkt-Editor", size=16, weight="bold", color="white"),
                                            ft.Text("Klicke einen Punkt an, um seine Frage zu bearbeiten. Du kannst Punkte verschieben, neue hinzufügen und löschen.", size=12, color="#A8C0D2"),
                                            ft.Container(
                                                height=220,
                                                border_radius=20,
                                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                                bgcolor="#061621E8",
                                                content=ft.Stack(
                                                    [
                                                        ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=["#081521", "#0A2B3E", "#07131C"])),
                                                        ft.Container(
                                                            expand=True,
                                                            opacity=0.30,
                                                            content=ft.Image(src=_questions_path_cached_image_src(selected_cfg.get("map_image_src", "")), fit=ft.BoxFit.COVER, error_content=ft.Container()) if selected_cfg.get("map_image_src") else ft.Container(),
                                                        ),
                                                        *point_overlay_controls,
                                                    ],
                                                    expand=True,
                                                ),
                                            ),
                                            ft.Row(
                                                [
                                                    _game_menu_button("Frage hinzufügen", add_point, "#0F766E", width=170, height=40),
                                                    _game_menu_button("- Punkt", remove_active_point, "#7C2D12", width=140, height=40),
                                                    _game_menu_button("Karte auswählen", open_world_map_menu, "#1D4ED8", width=180, height=40),
                                                    _game_menu_button("Frage öffnen", open_question_dialog_for(active_point_index), "#7C3AED", width=170, height=40),
                                                ],
                                                spacing=10,
                                            ),
                                            ft.Column(point_controls, spacing=6),
                                            ft.Row(
                                                [
                                                    _game_menu_button("Inselbild wählen", pick_selected_island_image, "#1D4ED8", width=180, height=40),
                                                    _game_menu_button("Kartenbild wählen", pick_selected_map_image, "#7C3AED", width=180, height=40),
                                                ],
                                                spacing=10,
                                            ),
                                            ft.Container(
                                                padding=16,
                                                border_radius=18,
                                                bgcolor="#0B1220DD",
                                                border=ft.border.Border.all(1.4, "#334155"),
                                                content=ft.Column(
                                                    [
                                                        ft.Text(f"Aktueller Punkt: {active_point_index + 1}", size=16, weight="bold", color="white"),
                                                        ft.Text(active_question.get("question", "Noch keine Frage hinterlegt."), size=14, color="#D5E3EE", max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                                                        ft.Text(f"Richtige Antwort: {ANSWER_LETTERS[min(3, int(active_question.get('correct_idx', 0) or 0))]}", size=12, color="#86EFAC"),
                                                        ft.Text(f"{len(selected_questions)} Fragen / Punkte in dieser Welt", size=12, color="#8FB7C9"),
                                                    ],
                                                    spacing=8,
                                                ),
                                            ),
                                        ],
                                        spacing=12,
                                    ),
                                ),
                            ],
                            spacing=12,
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        visible=add_mode == "preset",
                        bgcolor="#010611F0",
                        blur=16,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(980, max(360, int(_page_size(page)[0] - 60))),
                            padding=24,
                            border_radius=24,
                            bgcolor="#08111BFE",
                            border=ft.border.Border.all(2, "#38BDF8"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text("Insel hinzufügen", size=28, weight="bold", color="white"),
                                            _game_menu_button("Schließen", close_add_menu, "#475569", width=160, height=40),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("Wähle ein Standarddesign oder füge rechts einen eigenen Bildpfad / eine Bild-URL hinzu.", size=13, color="#B8CBD8"),
                                    ft.Row(preset_cards, wrap=True, spacing=12, alignment=ft.MainAxisAlignment.CENTER),
                                    ft.Container(height=8),
                                    ft.Row(
                                        [
                                            ft.Text("Eigene Designs", size=18, weight="bold", color="white"),
                                            _game_menu_button("+ Eigenes Design", open_custom_design, "#7C3AED", width=200, height=40),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Container(
                                                width=220,
                                                padding=12,
                                                border_radius=18,
                                                bgcolor="#0B1620",
                                                border=ft.border.Border.all(1.2, "#334155"),
                                                content=ft.Column(
                                                    [ft.Text("Gespeichert", size=14, weight="bold", color="white")]
                                                    + [
                                                        ft.Container(
                                                            padding=10,
                                                            border_radius=14,
                                                            bgcolor="#111827",
                                                            on_click=choose_saved_design(design_value),
                                                            content=ft.Row(
                                                                [
                                                                    ft.Container(
                                                                        width=48,
                                                                        height=48,
                                                                        border_radius=12,
                                                                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                                                        bgcolor="#0B1620",
                                                                        content=ft.Image(src=design_value, fit=ft.BoxFit.COVER, error_content=ft.Text("🖼️", size=18)),
                                                                    ),
                                                                    ft.Text(design_value, size=11, color="#D4E2ED", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                                                ],
                                                                spacing=10,
                                                            ),
                                                        )
                                                        for design_value in custom_designs
                                                    ],
                                                    spacing=8,
                                                ),
                                            )
                                        ],
                                        scroll=ft.ScrollMode.AUTO,
                                    ),
                                ],
                                spacing=14,
                            ),
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        visible=choose_custom_design,
                        bgcolor="#010611F0",
                        blur=16,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(760, max(340, int(_page_size(page)[0] - 80))),
                            padding=24,
                            border_radius=24,
                            bgcolor="#08111BFE",
                            border=ft.border.Border.all(2, "#7C3AED"),
                            content=ft.Column(
                                [
                                    ft.Text("Eigenes Design hinzufügen", size=28, weight="bold", color="white"),
                                    ft.Text("Für maximale Kompatibilität nutze bitte einen Bildpfad aus dem Projekt, eine direkte HTTPS-Bild-URL oder wähle eine Datei aus.", size=13, color="#B8CBD8"),
                                    ft.TextField(ref=custom_design_ref, value="", label="Bildpfad oder Bild-URL", bgcolor="#111827", color="white", border_color="#334155"),
                                    ft.Row(
                                        [
                                            _game_menu_button("Abbrechen", lambda e: (state.pop("_questions_path_choose_custom_design", None), _questions_path_render_creator(e.page, state)), "#475569", width=180, height=42),
                                            _game_menu_button("Bild auswählen", pick_custom_design, "#1D4ED8", width=180, height=42),
                                            _game_menu_button("Design speichern", add_custom_design, "#0F766E", width=220, height=42),
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
                    ft.Container(
                        expand=True,
                        visible=choose_world_map and selected_exists,
                        bgcolor="#010611F0",
                        blur=16,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(920, max(360, int(_page_size(page)[0] - 60))),
                            padding=24,
                            border_radius=24,
                            bgcolor="#08111BFE",
                            border=ft.border.Border.all(2, "#38BDF8"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text("Karte auswählen", size=28, weight="bold", color="white"),
                                            _game_menu_button("Schließen", close_world_map_menu, "#475569", width=160, height=40),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("Wähle ein Grundlayout oder nutze ein eigenes Kartenbild. Punkte kannst du danach trotzdem frei hinzufügen, löschen und verschieben.", size=13, color="#B8CBD8"),
                                    ft.Row(
                                        [
                                            ft.Container(
                                                width=210,
                                                height=140,
                                                border_radius=20,
                                                bgcolor="#0B1620",
                                                border=ft.border.Border.all(1.5, "#38BDF8"),
                                                padding=16,
                                                on_click=choose_world_layout(layout_key),
                                                content=ft.Column(
                                                    [
                                                        ft.Text(layout_data["label"], size=18, weight="bold", color="white"),
                                                        ft.Text(f"{len(layout_data['points'])} Startpunkte", size=12, color="#A8C0D2"),
                                                        ft.Text("Vorlage auswählen", size=12, color="#7DD3FC"),
                                                    ],
                                                    spacing=8,
                                                ),
                                            )
                                            for layout_key, layout_data in QUESTIONS_PATH_WORLD_LAYOUTS.items()
                                        ],
                                        wrap=True,
                                        spacing=12,
                                    ),
                                    ft.Row(
                                        [
                                            _game_menu_button("Eigenes Kartenbild wählen", pick_selected_map_image, "#7C3AED", width=250, height=42),
                                            _game_menu_button("Nur Punkte behalten", close_world_map_menu, "#334155", width=200, height=42),
                                        ],
                                        spacing=12,
                                    ),
                                ],
                                spacing=14,
                            ),
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        visible=question_dialog_open and selected_exists,
                        bgcolor="#010611F0",
                        blur=18,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(860, max(360, int(_page_size(page)[0] - 70))),
                            padding=24,
                            border_radius=24,
                            bgcolor="#08111BFE",
                            border=ft.border.Border.all(2, "#7C3AED"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(f"Frage für Punkt {active_point_index + 1}", size=28, weight="bold", color="white"),
                                            _game_menu_button("Schließen", close_question_dialog, "#475569", width=160, height=40),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("Hier legst du die Frage und die vier Antwortmöglichkeiten für den ausgewählten Punkt fest.", size=13, color="#B8CBD8"),
                                    ft.TextField(ref=question_ref, value=active_question.get("question", ""), label="Frage", bgcolor="#111827", color="white", border_color="#334155"),
                                    ft.Row(
                                        [
                                            ft.TextField(ref=answer_refs[0], value=active_answers[0], label="Antwort A", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                            ft.TextField(ref=answer_refs[1], value=active_answers[1], label="Antwort B", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                        ],
                                        spacing=10,
                                    ),
                                    ft.Row(
                                        [
                                            ft.TextField(ref=answer_refs[2], value=active_answers[2], label="Antwort C", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                            ft.TextField(ref=answer_refs[3], value=active_answers[3], label="Antwort D", bgcolor="#111827", color="white", border_color="#334155", expand=True),
                                        ],
                                        spacing=10,
                                    ),
                                    ft.Dropdown(
                                        ref=correct_ref,
                                        value=str(int(active_question.get("correct_idx", 0) or 0)),
                                        label="Richtige Antwort",
                                        bgcolor="#111827",
                                        color="white",
                                        border_color="#334155",
                                        options=[ft.dropdown.Option(str(i), text=f"{ANSWER_LETTERS[i]}") for i in range(4)],
                                    ),
                                    ft.Row(
                                        [
                                            _game_menu_button("Punkt löschen", remove_active_point, "#7C2D12", width=170, height=42),
                                            _game_menu_button("Frage speichern", save_question(active_point_index, question_ref, answer_refs, correct_ref), "#0F766E", width=200, height=42),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                        spacing=12,
                                    ),
                                ],
                                spacing=14,
                            ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def _questions_path_render_custom_menu(page: ft.Page, state: dict):
    profiles = get_questions_path_profiles(state)
    if not profiles:
        profiles = [_questions_path_default_profile(0)]
        persist_questions_path_profiles(state, profiles)
        state["questions_path_profiles"] = profiles
    active_index = get_questions_path_profile_index(state)
    active_profile = profiles[active_index] if active_index < len(profiles) else _questions_path_default_profile(0)
    theme = get_theme(state)

    world_name_ref = ft.Ref[ft.TextField]()
    world_create_dialog_open = bool(state.get("_questions_path_create_world_dialog", False))

    def save_world(profile_index: int, profile: dict):
        current_profiles = get_questions_path_profiles(state)
        while profile_index >= len(current_profiles):
            current_profiles.append(_questions_path_default_profile(len(current_profiles)))
        current_profiles[profile_index] = profile
        persist_questions_path_profiles(state, current_profiles)
        state["questions_path_profiles"] = current_profiles

    def open_world(profile_index: int, edit: bool, e):
        refreshed = get_questions_path_profiles(state)
        profile = dict(refreshed[profile_index] if profile_index < len(refreshed) else _questions_path_default_profile(profile_index))
        profile["progression_mode"] = "creative"
        save_world(profile_index, profile)
        set_questions_path_profile_index(state, profile_index)
        state["questions_path_scene"] = "editor" if edit else "islands"
        show_questions_path_hub(e.page, state)

    def play_world(profile_index: int):
        def _handler(e):
            open_world(profile_index, False, e)

        return _handler

    def edit_world(profile_index: int):
        def _handler(e):
            open_world(profile_index, True, e)

        return _handler

    def open_create_world_dialog(e):
        state["_questions_path_create_world_dialog"] = True
        _questions_path_render_custom_menu(e.page, state)

    def close_create_world_dialog(e):
        state["_questions_path_create_world_dialog"] = False
        _questions_path_render_custom_menu(e.page, state)

    def create_world(e):
        current_profiles = get_questions_path_profiles(state)
        if len(current_profiles) >= QUESTIONS_PATH_PROFILE_MAX:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Maximal 10 Welten sind möglich."), open=True)
            e.page.update()
            return
        raw_name = str(world_name_ref.current.value or "").strip() if world_name_ref.current else ""
        new_profile = _questions_path_default_profile(len(current_profiles))
        if raw_name:
            new_profile["name"] = raw_name
        new_profile["progression_mode"] = "creative"
        current_profiles.append(new_profile)
        persist_questions_path_profiles(state, current_profiles)
        state["questions_path_profiles"] = current_profiles
        set_questions_path_profile_index(state, len(current_profiles) - 1)
        state["_questions_path_create_world_dialog"] = False
        state["questions_path_scene"] = "creator"
        show_questions_path_hub(e.page, state)

    page.controls.clear()

    world_cards = []
    for idx, profile_item in enumerate(profiles):
        is_active = idx == active_index
        profile_name = str(profile_item.get("name", f"Profil {idx + 1}")).strip() or f"Profil {idx + 1}"
        mode_label = "Kreativ" if _questions_path_profile_mode(profile_item) == "creative" else "Abenteuer"
        custom_count = len(list(profile_item.get("custom_islands", []) or []))
        last_label = "Noch keine Insel"
        if custom_count:
            last_label = f"{custom_count} eigene Inseln"
        mode_description = (
            "Bearbeiten öffnet die eigene Inselwelt mit Drag & Drop, Fragen und Layout."
            if str(profile_item.get("progression_mode", "adventure")).lower() == "creative"
            else "Spielen startet die standardisierte Insel-Reihenfolge."
        )
        world_cards.append(
            ft.Container(
                padding=16,
                border_radius=22,
                bgcolor="#0B1620F0" if is_active else "#08111BF0",
                border=ft.border.Border.all(2, "#38BDF8" if is_active else "#1F2937"),
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(profile_name, size=18, weight="bold", color="white"),
                                        _questions_path_island_chip(mode_label, "#0F766E" if mode_label == "Kreativ" else "#334155"),
                                    ],
                                    spacing=10,
                                ),
                                ft.Text(
                                    str(profile_item.get("selected_age", "mid")).capitalize() + " / " + last_label,
                                    size=12,
                                    color="#A8C0D2",
                                ),
                                ft.Text(mode_description, size=12, color="#D5E3EE"),
                            ],
                            spacing=5,
                            expand=True,
                        ),
                        ft.Column(
                            [
                                _game_menu_button("Spielen", play_world(idx), "#0F766E", width=140, height=40),
                                _game_menu_button("Bearbeiten", edit_world(idx), "#1D4ED8", width=140, height=40),
                            ],
                            spacing=8,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _questions_path_backdrop("#34D399", "#38BDF8"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        padding=20,
                        content=ft.Container(
                            width=min(920, max(360, int(_page_size(page)[0] - 40))),
                            padding=24,
                            border_radius=28,
                            bgcolor="#08111BFE",
                            border=ft.border.Border.all(2, "#38BDF8"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            _game_menu_button("← Profile", lambda e: (state.__setitem__("questions_path_scene", "profiles"), show_questions_path_hub(e.page, state)), "#475569", width=170, height=40),
                                            ft.Text("Eigenes Spiel", size=30, weight="bold", color="white"),
                                            _game_menu_button("+ Welt", open_create_world_dialog, "#1D4ED8", width=140, height=40),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("Hier verwaltest du deine Welten. Spielen öffnet die aktuelle Welt, Bearbeiten bringt dich in den Editor.", size=13, color="#B8CBD8", text_align=ft.TextAlign.CENTER),
                                    ft.Container(height=4),
                                    ft.Text("Meine Welten", size=18, weight="bold", color=theme_value(theme, "gold", "#F6C453"), text_align=ft.TextAlign.LEFT),
                                    ft.Container(
                                        expand=True,
                                        content=ft.Column(
                                            world_cards if world_cards else [
                                                ft.Container(
                                                    padding=18,
                                                    border_radius=22,
                                                    bgcolor="#0B1620F0",
                                                    border=ft.border.Border.all(1.5, "#334155"),
                                                    content=ft.Column(
                                                        [
                                                            ft.Text("Noch keine eigene Welt", size=22, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                                                            ft.Text("Erstelle oben rechts mit + Welt deine erste Welt. Danach kannst du sie spielen oder bearbeiten.", size=13, color="#D5E3EE", text_align=ft.TextAlign.CENTER),
                                                        ],
                                                        spacing=10,
                                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                    ),
                                                )
                                            ],
                                            spacing=12,
                                            scroll=ft.ScrollMode.AUTO,
                                        ),
                                    ),
                                    ft.Row(
                                        [
                                            _questions_path_island_chip(f"{len(profiles)} Welt(en)", "#334155"),
                                            _questions_path_island_chip("Bearbeiten = Inseln + Punkte", "#0F766E"),
                                            _questions_path_island_chip("Spielen = aktuelle Welt", "#1D4ED8"),
                                        ],
                                        spacing=10,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                ],
                                spacing=16,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        visible=world_create_dialog_open,
                        bgcolor="#010611F0",
                        blur=16,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(520, max(320, int(_page_size(page)[0] - 60))),
                            padding=24,
                            border_radius=24,
                            bgcolor="#08111BFE",
                            border=ft.border.Border.all(2, "#38BDF8"),
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text("Neue Welt", size=28, weight="bold", color="white"),
                                            _game_menu_button("Schließen", close_create_world_dialog, "#475569", width=150, height=40),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("Vergib direkt einen Namen für die neue Welt.", size=13, color="#B8CBD8"),
                                    ft.TextField(ref=world_name_ref, label="Weltname", value=f"Welt {len(profiles) + 1}", bgcolor="#111827", color="white", border_color="#334155"),
                                    ft.Row(
                                        [
                                            _game_menu_button("Welt anlegen", create_world, "#1D4ED8", width=180, height=42),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=14,
                            ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def _questions_path_backdrop(accent_a: str = "#34D399", accent_b: str = "#38BDF8") -> ft.Control:
    return ft.Stack(
        [
            ft.Container(
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, -1),
                    end=ft.Alignment(1, 1),
                    colors=["#030712", "#071827", "#0A2233"],
                ),
            ),
            ft.Container(left=-180, top=-160, width=420, height=420, border_radius=999, bgcolor=f"#18{accent_a[1:]}"),
            ft.Container(right=-120, top=40, width=340, height=340, border_radius=999, bgcolor=f"#16{accent_b[1:]}"),
            ft.Container(left=80, bottom=-180, width=520, height=320, border_radius=999, bgcolor="#0BFFFFFF"),
            ft.Container(right=110, bottom=-20, width=260, height=260, border_radius=999, bgcolor="#08FFFFFF"),
        ],
        expand=True,
    )


def _questions_path_level_state_for(profile_data: dict, map_key: str, level_index: int) -> str:
    if _questions_path_profile_mode(profile_data) == "creative":
        return "active"
    level_progress = (profile_data.get("level_progress", {}) or {}).get(map_key, {})
    if bool(level_progress.get("done", False)):
        return "done"
    active_level = int(profile_data.get("active_level_index", 0) or 0)
    if level_index > active_level:
        return "locked"
    return "active"


def _questions_path_island_chip(label: str, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(label, size=10, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
        bgcolor=color,
        border_radius=999,
        padding=ft.Padding(10, 4, 10, 4),
    )


def _questions_path_zoom_controls(state: dict, key: str, rerender):
    zoom_value = float(state.get(key, 1.0) or 1.0)
    zoom_value = max(0.45, min(1.8, zoom_value))
    state[key] = zoom_value

    def set_zoom(next_zoom: float):
        def _handler(e):
            state[key] = max(0.45, min(1.8, round(next_zoom, 2)))
            rerender(e.page, state)

        return _handler

    return ft.Row(
        [
            _game_menu_button("−", set_zoom(zoom_value - 0.22), "#1E293B", width=52, height=36),
            _game_menu_button(f"{int(zoom_value * 100)}%", set_zoom(1.0), "#0F766E", width=84, height=36),
            _game_menu_button("+", set_zoom(zoom_value + 0.22), "#1E293B", width=52, height=36),
        ],
        spacing=8,
    )


def _questions_path_interactive_viewer(content: ft.Control) -> ft.Control:
    return ft.InteractiveViewer(
        content=content,
        min_scale=0.32,
        max_scale=2.4,
        boundary_margin=ft.Margin(240, 240, 240, 240),
        constrained=False,
        pan_enabled=True,
        scale_enabled=True,
        scale_factor=240,
        interaction_update_interval=16,
        trackpad_scroll_causes_scale=True,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )


def _questions_path_question_card(
    page: ft.Page,
    state: dict,
    game: dict,
    map_cfg: dict,
    active_node: int,
    card_w: int,
) -> ft.Control:
    question = (game.get("questions") or [])[active_node]
    accent = map_cfg.get("accent", "#34D399")
    neutral_bg = "#162033"
    neutral_border = "#2F3B52"
    feedback = game.get("answer_feedback") if isinstance(game.get("answer_feedback"), dict) else {}
    selected_wrong = feedback.get("chosen") if feedback.get("node") == active_node and feedback.get("kind") == "wrong" else None
    selected_correct = feedback.get("chosen") if feedback.get("node") == active_node and feedback.get("kind") == "correct" else None

    def continue_after_correct(e):
        current_game = state.get("questions_path_game") or {}
        current_idx = int(current_game.get("node_index", 0) or 0)
        questions = list(current_game.get("questions") or [])
        completed = {int(v) for v in list(current_game.get("completed_nodes", [])) if str(v).isdigit() or isinstance(v, int)}
        completed.add(current_idx)
        current_game["completed_nodes"] = sorted(completed)
        current_game["answer_feedback"] = None
        next_idx = current_idx + 1
        if next_idx >= len(questions):
            current_game["node_index"] = len(questions)
            current_game["game_finished"] = True
            state["_questions_path_active_node"] = None
            save_questions_path_game(state)
            render_questions_path_complete(e.page, state)
            return
        current_game["node_index"] = next_idx
        current_game["game_finished"] = False
        state["_questions_path_active_node"] = None
        save_questions_path_game(state)
        render_questions_path_game(e.page, state)

    def choose_answer(answer_index: int):
        def _handler(e):
            current_game = state.get("questions_path_game") or {}
            current_idx = int(current_game.get("node_index", 0) or 0)
            questions = list(current_game.get("questions") or [])
            if current_idx >= len(questions):
                return
            current_question = questions[current_idx]
            if answer_index != int(current_question.get("correct_idx", 0)):
                current_game["answer_feedback"] = {
                    "node": current_idx,
                    "chosen": answer_index,
                    "correct": int(current_question.get("correct_idx", 0)),
                    "kind": "wrong",
                }
                state["questions_path_game"] = current_game
                render_questions_path_game(e.page, state)
                return

            current_game["answer_feedback"] = {
                "node": current_idx,
                "chosen": answer_index,
                "correct": int(current_question.get("correct_idx", 0)),
                "kind": "correct",
            }
            state["questions_path_game"] = current_game
            render_questions_path_game(e.page, state)

        return _handler

    answer_controls = []
    for idx, answer in enumerate(question.get("answers", [])):
        is_wrong_choice = selected_wrong == idx
        is_correct_choice = selected_correct == idx
        answer_bg = "#451A1A" if is_wrong_choice else ("#123126" if is_correct_choice else neutral_bg)
        answer_border = "#F87171" if is_wrong_choice else ("#34D399" if is_correct_choice else neutral_border)
        answer_badge_bg = "#DC2626" if is_wrong_choice else ("#10B981" if is_correct_choice else accent)
        answer_controls.append(
            ft.Container(
                width=min(520, card_w - 90),
                padding=ft.Padding(14, 12, 14, 12),
                border_radius=18,
                bgcolor=answer_bg,
                border=ft.border.Border.all(1.6, answer_border),
                on_click=choose_answer(idx),
                content=ft.Row(
                    [
                        ft.Container(
                            width=34,
                            height=34,
                            border_radius=999,
                            bgcolor=answer_badge_bg,
                            alignment=ft.Alignment(0, 0),
                            content=ft.Text(ANSWER_LETTERS[idx], size=13, weight="bold", color="white" if (is_wrong_choice or is_correct_choice) else "#08131F"),
                        ),
                        ft.Text(answer, size=15, color="white", weight="bold", expand=True),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    return ft.Container(
        width=min(640, card_w - 48),
        padding=ft.Padding(24, 22, 24, 22),
        border_radius=26,
        bgcolor="#08111BFE",
        border=ft.border.Border.all(2, accent),
        shadow=ft.BoxShadow(blur_radius=26, color=f"#44{accent[1:]}", spread_radius=1),
        content=ft.Column(
            [
                ft.Row(
                    [
                        _questions_path_island_chip(f"Station {active_node + 1}", accent),
                        ft.Text(f"{len(game.get('completed_nodes', [])) + 1}/{len(map_cfg.get('points', []))}", size=12, color="#D7E6F5"),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(question.get("question", "Frage"), size=24, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                ft.Column(answer_controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(
                    f"Die richtige Antwort ist: {question.get('answers', [''])[selected_correct]}." if selected_correct is not None else ("Diese Antwort ist falsch." if selected_wrong is not None else "Wähle eine Antwort. Falsche Antworten werden rot markiert."),
                    size=12,
                    color="#86EFAC" if selected_correct is not None else ("#FCA5A5" if selected_wrong is not None else "#9FB3C8"),
                    text_align=ft.TextAlign.CENTER,
                ),
                _game_menu_button("Nächste Frage", continue_after_correct, accent, width=220, height=40) if selected_correct is not None else ft.Container(),
                _game_menu_button("Schließen", lambda e: (state.pop("_questions_path_active_node", None), render_questions_path_game(e.page, state)), "#475569", width=220, height=40),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _questions_path_render_islands(page: ft.Page, state: dict):
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        profiles = [_questions_path_default_profile(0)]
        persist_questions_path_profiles(state, profiles)
    state["questions_path_profiles"] = profiles
    active_index = get_questions_path_profile_index(state)
    active_profile = profiles[active_index] if active_index < len(profiles) else profiles[0]
    creative_mode = _questions_path_profile_mode(active_profile) == "creative"
    creative_action = str(state.get("questions_path_creative_action", "edit")).strip().lower()
    creative_edit_mode = creative_mode and creative_action != "play"
    page_w, page_h = _page_size(page)
    visible_maps = _questions_path_maps_for_profile(active_profile)
    base_canvas_w = max(2400, int(page_w * 1.6))
    base_canvas_h = max(1500, int(page_h * 1.55))
    fit_zoom = round(max(0.45, min(1.0, min(max(1, page_w - 40) / base_canvas_w, max(1, page_h - 220) / base_canvas_h))), 2)
    zoom = max(0.45, min(1.8, float(state.get("questions_path_map_zoom", fit_zoom) or fit_zoom)))
    state["questions_path_map_zoom"] = zoom
    card_w = max(320, int(page_w - 24))
    map_h = max(520, int(page_h - 180))
    canvas_w = base_canvas_w
    canvas_h = base_canvas_h
    island_marker_refs: dict[int, ft.Ref[ft.Container]] = {}

    def save_active_profile(updated_profile: dict):
        refreshed_profiles = get_questions_path_profiles(state)
        if not refreshed_profiles:
            refreshed_profiles = [_questions_path_default_profile(0)]
        while active_index >= len(refreshed_profiles):
            refreshed_profiles.append(_questions_path_default_profile(len(refreshed_profiles)))
        refreshed_profiles[active_index] = updated_profile
        persist_questions_path_profiles(state, refreshed_profiles)
        state["questions_path_profiles"] = refreshed_profiles

    def island_card_scale(island_cfg: dict) -> float:
        try:
            return max(0.8, min(1.8, float(island_cfg.get("card_scale", 1.0) or 1.0)))
        except Exception:
            return 1.0

    def island_card_size(island_cfg: dict) -> tuple[int, int]:
        scale = island_card_scale(island_cfg)
        return max(220, int(260 * scale)), max(168, int(176 * scale))

    def island_left_from_percent(percent_x: float, island_width: int) -> int:
        return max(24, min(int(canvas_w - island_width - 24), int((float(percent_x) / 100.0) * max(1, canvas_w - island_width))))

    def island_top_from_percent(percent_y: float, island_height: int) -> int:
        return max(24, min(int(canvas_h - island_height - 24), int((float(percent_y) / 100.0) * max(1, canvas_h - island_height))))

    def open_level(map_key: str, level_index: int):
        def _handler(e):
            current_profiles = get_questions_path_profiles(state)
            profile = current_profiles[active_index] if active_index < len(current_profiles) else active_profile
            state_name = _questions_path_level_state_for(profile, map_key, level_index)
            if state_name == "locked":
                e.page.snack_bar = ft.SnackBar(content=ft.Text("Schließe zuerst die vorherige Insel ab."), open=True)
                e.page.update()
                return
            saved_game = profile.get("active_game")
            if isinstance(saved_game, dict) and saved_game.get("map_key") == map_key and not saved_game.get("game_finished", False):
                resume_questions_path_game(e.page, state, saved_game)
                return
            start_questions_path_game(e.page, state, map_key)

        return _handler

    def open_editor(map_key: str):
        def _handler(e):
            state["_questions_path_editor_island_key"] = map_key
            state["_questions_path_editor_map_key"] = map_key
            state["_questions_path_editor_point_index"] = 0
            state["questions_path_creative_action"] = "edit"
            state["questions_path_scene"] = "editor"
            show_questions_path_hub(e.page, state)

        return _handler

    def add_creative_island(e):
        refreshed_profiles = get_questions_path_profiles(state)
        refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else active_profile)
        islands = creative_islands_for_profile(refreshed_profile)
        if len(islands) >= 10:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Maximal 10 eigene Inseln sind möglich."), open=True)
            e.page.update()
            return
        islands.append(_questions_path_default_custom_island(len(islands)))
        refreshed_profile["custom_islands"] = islands
        refreshed_profile["progression_mode"] = "creative"
        save_active_profile(refreshed_profile)
        _questions_path_render_islands(e.page, state)

    def creative_islands_for_profile(profile: dict) -> list[dict]:
        islands: list[dict] = []
        for idx, raw_island in enumerate(list(profile.get("custom_islands", []) or [])):
            if not isinstance(raw_island, dict):
                continue
            island = dict(raw_island)
            island["map_key"] = str(island.get("map_key", f"custom_{idx + 1}")).strip() or f"custom_{idx + 1}"
            island["map_x"] = max(2.0, min(88.0, float(island.get("map_x", 20) or 20)))
            island["map_y"] = max(2.0, min(82.0, float(island.get("map_y", 20) or 20)))
            island["card_scale"] = island_card_scale(island)
            islands.append(island)
        return islands

    def start_island_drag(index: int):
        def _handler(e):
            refreshed_profiles = get_questions_path_profiles(state)
            refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else active_profile)
            islands = creative_islands_for_profile(refreshed_profile)
            if index >= len(islands):
                return
            island = islands[index]
            drag_state = dict(state.get("_questions_path_island_drag_state") or {})
            drag_state[index] = {
                "start_map_x": float(island.get("map_x", 20)),
                "start_map_y": float(island.get("map_y", 20)),
                "map_x": float(island.get("map_x", 20)),
                "map_y": float(island.get("map_y", 20)),
                "card_w": island_card_size(island)[0],
                "card_h": island_card_size(island)[1],
            }
            state["_questions_path_island_drag_state"] = drag_state

        return _handler

    def move_island_drag(index: int):
        def _handler(e):
            drag_state = dict(state.get("_questions_path_island_drag_state") or {})
            current_drag = dict(drag_state.get(index) or {})
            if not current_drag:
                return
            dx = float(getattr(e, "delta_x", 0.0) or 0.0)
            dy = float(getattr(e, "delta_y", 0.0) or 0.0)
            current_drag["map_x"] = max(2.0, min(88.0, float(current_drag.get("map_x", 20)) + (dx / max(1.0, canvas_w * zoom)) * 100.0))
            current_drag["map_y"] = max(2.0, min(82.0, float(current_drag.get("map_y", 20)) + (dy / max(1.0, canvas_h * zoom)) * 100.0))
            drag_state[index] = current_drag
            state["_questions_path_island_drag_state"] = drag_state
            marker_ref = island_marker_refs.get(index)
            if marker_ref and marker_ref.current:
                marker_ref.current.left = island_left_from_percent(current_drag["map_x"], int(current_drag.get("card_w", 260)))
                marker_ref.current.top = island_top_from_percent(current_drag["map_y"], int(current_drag.get("card_h", 176)))
                e.page.update()

        return _handler

    def end_island_drag(index: int):
        def _handler(e):
            drag_state = dict(state.get("_questions_path_island_drag_state") or {})
            current_drag = dict(drag_state.get(index) or {})
            refreshed_profiles = get_questions_path_profiles(state)
            refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else active_profile)
            islands = creative_islands_for_profile(refreshed_profile)
            if current_drag and index < len(islands):
                island = dict(islands[index])
                island["map_x"] = float(current_drag.get("map_x", island.get("map_x", 20)))
                island["map_y"] = float(current_drag.get("map_y", island.get("map_y", 20)))
                islands[index] = island
                refreshed_profile["custom_islands"] = islands
                refreshed_profile["progression_mode"] = "creative"
                save_active_profile(refreshed_profile)
            drag_state.pop(index, None)
            state["_questions_path_island_drag_state"] = drag_state
            _questions_path_render_islands(e.page, state)

        return _handler

    route_dots = []
    for dot_index in range(62):
        route_dots.append(
            ft.Container(
                left=int(canvas_w * (0.05 + dot_index * 0.0145)),
                top=int(canvas_h * (0.50 + (0.13 if dot_index % 4 == 1 else (-0.09 if dot_index % 4 == 2 else (0.03 if dot_index % 4 == 3 else 0.0))))),
                width=10,
                height=10,
                border_radius=999,
                bgcolor="#B6F0E055" if dot_index % 2 else "#7DD3FC66",
            )
        )

    if creative_mode:
        for level_index, island in enumerate(creative_islands_for_profile(active_profile)):
            map_cfg = _questions_path_custom_map(island, level_index)
            _questions_path_warm_image_cache(map_cfg.get("image_src", ""), map_cfg.get("map_image_src", ""))
    else:
        for map_key, _map_cfg in visible_maps:
            map_cfg = _questions_path_map_lookup_for_profile(active_profile, map_key)
            _questions_path_warm_image_cache(map_cfg.get("image_src", ""), map_cfg.get("image", ""), map_cfg.get("map_image_src", ""))

    stage_items = []
    if creative_mode:
        creative_islands = creative_islands_for_profile(active_profile)
        for level_index, island in enumerate(creative_islands):
            map_key = island.get("map_key", f"custom_{level_index + 1}")
            map_cfg = _questions_path_custom_map(island, level_index)
            accent = map_cfg.get("accent", "#34D399")
            width, height = island_card_size(map_cfg)
            marker_ref = ft.Ref[ft.Container]()
            island_marker_refs[level_index] = marker_ref
            stage_items.append(
                ft.Container(
                    ref=marker_ref,
                    left=island_left_from_percent(float(map_cfg.get("map_x", 20)), width),
                    top=island_top_from_percent(float(map_cfg.get("map_y", 20)), height),
                    width=width,
                    height=height,
                    content=ft.GestureDetector(
                        on_tap=open_editor(map_key) if creative_edit_mode else open_level(map_key, level_index),
                        on_pan_start=start_island_drag(level_index) if creative_edit_mode else None,
                        on_pan_update=move_island_drag(level_index) if creative_edit_mode else None,
                        on_pan_end=end_island_drag(level_index) if creative_edit_mode else None,
                        drag_interval=1 if creative_edit_mode else 0,
                        mouse_cursor=ft.MouseCursor.MOVE,
                        content=ft.Container(
                            expand=True,
                            border_radius=36,
                            bgcolor="#09131DE8",
                            border=ft.border.Border.all(2.0, accent),
                            shadow=ft.BoxShadow(blur_radius=28, color=f"#44{accent[1:]}", spread_radius=0),
                            content=ft.Stack(
                                [
                                    ft.Container(
                                        expand=True,
                                        gradient=ft.LinearGradient(
                                            begin=ft.Alignment(-1, -1),
                                            end=ft.Alignment(1, 1),
                                            colors=["#0A1622", map_cfg.get("panel", "#112133"), "#091623"],
                                        ),
                                        on_click=clear_island_selection,
                                    ),
                                    ft.Container(left=22, top=20, width=78, height=78, border_radius=999, bgcolor=f"#22{accent[1:]}"),
                                    ft.Container(right=22, top=20, content=_questions_path_island_chip("Bearbeiten", accent)),
                                    ft.Container(
                                        left=26,
                                        right=24,
                                        top=26,
                                        bottom=22,
                                        content=ft.Row(
                                            [
                                                ft.Container(
                                                    width=88,
                                                    height=88,
                                                    border_radius=999,
                                                    alignment=ft.Alignment(0, 0),
                                                    gradient=ft.LinearGradient(
                                                        begin=ft.Alignment(-1, -1),
                                                        end=ft.Alignment(1, 1),
                                                        colors=["#14304A", "#1D4F73", "#17365A"],
                                                    ),
                                                    content=ft.Image(src=_questions_path_cached_image_src(map_cfg.get("image_src", "")), fit=ft.BoxFit.COVER, border_radius=999, error_content=ft.Text(map_cfg.get("icon", "🌍"), size=38, color="white", text_align=ft.TextAlign.CENTER)) if map_cfg.get("image_src") else ft.Text(map_cfg.get("icon", "🌍"), size=38, color="white", text_align=ft.TextAlign.CENTER),
                                                ),
                                                ft.Column(
                                                    [
                                                        ft.Text(map_cfg.get("title", "Insel"), size=24, weight="bold", color="white", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                                        ft.Text(map_cfg.get("subtitle", ""), size=14, color="#D3E3EE", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                                        ft.Text(f"{len(map_cfg.get('points', []))} Punkte", size=12, color=accent, weight="bold"),
                                                        ft.Text("Tippen zum Eintauchen, direkt ziehen zum Verschieben." if creative_edit_mode else "Tippen startet deine eigene Inselrunde.", size=11, color="#A8C0D2"),
                                                    ],
                                                    spacing=4,
                                                    expand=True,
                                                    alignment=ft.MainAxisAlignment.CENTER,
                                                ),
                                            ],
                                            spacing=18,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                    ),
                                ],
                                expand=True,
                            ),
                        ),
                    ),
                )
            )
    else:
        scatter_template = [
            (0.06, 0.08), (0.38, 0.07), (0.69, 0.10), (0.18, 0.34), (0.52, 0.29),
            (0.82, 0.31), (0.08, 0.67), (0.38, 0.73), (0.67, 0.63), (0.81, 0.80),
        ]
        island_positions = []
        for idx, (map_key, _map_cfg) in enumerate(visible_maps):
            sx, sy = scatter_template[idx % len(scatter_template)]
            island_positions.append({"map_key": map_key, "left": sx, "top": sy, "w": 0.20, "h": 0.20})

        for level_index, item in enumerate(island_positions):
            map_key = item["map_key"]
            map_cfg = _questions_path_map_lookup_for_profile(active_profile, map_key)
            _questions_path_warm_image_cache(map_cfg.get("image_src", ""), map_cfg.get("image", ""))
            island_state = _questions_path_level_state_for(active_profile, map_key, level_index)
            left = int(canvas_w * item["left"])
            top = int(canvas_h * item["top"])
            width = max(260, int(canvas_w * item["w"] * 0.42))
            height = max(210, int(canvas_h * item["h"] * 0.20))
            accent = map_cfg.get("accent", "#34D399")
            border_color = accent if island_state != "locked" else "#475569"
            glow_color = f"#44{accent[1:]}" if island_state != "locked" else "#22000000"
            chip_label = "Abgeschlossen" if island_state == "done" else ("Aktiv" if island_state == "active" else "Gesperrt")
            chip_color = "#16A34A" if island_state == "done" else (accent if island_state == "active" else "#475569")
            button_text = "Pfad öffnen" if island_state != "locked" else "Noch gesperrt"

            stage_items.append(
                ft.Container(
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    border_radius=36,
                    bgcolor="#09131DE8" if island_state != "locked" else "#0E1721D6",
                    border=ft.border.Border.all(2.0, border_color),
                    shadow=ft.BoxShadow(blur_radius=28, color=glow_color, spread_radius=0),
                    on_click=open_level(map_key, level_index) if island_state != "locked" else None,
                    content=ft.Stack(
                        [
                            ft.Container(
                                expand=True,
                                gradient=ft.LinearGradient(
                                    begin=ft.Alignment(-1, -1),
                                    end=ft.Alignment(1, 1),
                                    colors=["#0A1622", map_cfg.get("panel", "#112133"), "#091623"],
                                ),
                            ),
                            ft.Container(left=22, top=20, width=78, height=78, border_radius=999, bgcolor=f"#22{accent[1:]}"),
                            ft.Container(right=22, top=20, content=_questions_path_island_chip(chip_label, chip_color)),
                            ft.Container(
                                left=26,
                                right=24,
                                top=26,
                                bottom=22,
                                content=ft.Row(
                                    [
                                        ft.Container(
                                            width=88,
                                            height=88,
                                            border_radius=999,
                                            alignment=ft.Alignment(0, 0),
                                            gradient=ft.LinearGradient(
                                                begin=ft.Alignment(-1, -1),
                                                end=ft.Alignment(1, 1),
                                                colors=["#14304A", "#1D4F73", "#17365A"],
                                            ),
                                            content=ft.Image(src=_questions_path_cached_image_src(map_cfg.get("image_src", "")), fit=ft.BoxFit.COVER, border_radius=999, error_content=ft.Text(map_cfg.get("icon", "🌍"), size=38, color="white", text_align=ft.TextAlign.CENTER)) if map_cfg.get("image_src") else ft.Text(map_cfg.get("icon", "🌍"), size=38, color="white", text_align=ft.TextAlign.CENTER),
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(map_cfg.get("title", "Insel"), size=24, weight="bold", color="white", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                                ft.Text(map_cfg.get("subtitle", ""), size=14, color="#D3E3EE", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                                ft.Text(f"{len(map_cfg.get('points', []))} Stationen", size=12, color=accent, weight="bold"),
                                                ft.Container(
                                                    margin=ft.Margin(0, 8, 0, 0),
                                                    padding=ft.Padding(12, 8, 12, 8),
                                                    border_radius=16,
                                                    bgcolor=accent,
                                                    alignment=ft.Alignment(0, 0),
                                                    content=ft.Text(button_text, size=12, weight="bold", color="#03121A"),
                                                ),
                                            ],
                                            spacing=4,
                                            expand=True,
                                            alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                    ],
                                    spacing=18,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ),
                        ],
                        expand=True,
                    ),
                )
            )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _questions_path_backdrop("#34D399", "#38BDF8"),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(12, 10, 12, 10),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        _game_menu_button("← Profile", lambda e: _questions_path_render_profiles(e.page, state), "#475569", width=170, height=40),
                                        ft.Text("Fragen-Pfad", size=32, weight="bold", color="white"),
                                        ft.Row(
                                            [
                                                _game_menu_button("+ Insel", add_creative_island, "#1D4ED8", width=130, height=40) if creative_edit_mode else ft.Container(),
                                                _questions_path_zoom_controls(state, "questions_path_map_zoom", lambda p, s: _questions_path_render_islands(p, s)),
                                                _questions_path_island_chip(active_profile.get("name", f"Profil {active_index + 1}"), "#0F766E"),
                                            ],
                                            spacing=10,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(
                                    "Zoome mit Touch, Touchpad oder Mausrad direkt in die Karte. Im Bearbeiten-Modus verschiebst du einzelne Inseln per Drag, im Spiel-Modus startest du sie per Tipp.",
                                    size=13,
                                    color=theme_txt(theme, "secondary"),
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(
                                    expand=True,
                                    width=card_w,
                                    border_radius=28,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    bgcolor="#07101AE0",
                                    content=ft.Container(
                                        alignment=ft.Alignment(0, 0),
                                        content=ft.Container(
                                            width=int(canvas_w * zoom),
                                            height=int(canvas_h * zoom),
                                            content=ft.Container(
                                                width=canvas_w,
                                                height=canvas_h,
                                                scale=zoom,
                                                animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
                                                content=ft.Stack(
                                                    [
                                                        ft.Container(
                                                            expand=True,
                                                            gradient=ft.LinearGradient(
                                                                begin=ft.Alignment(-1, -1),
                                                                end=ft.Alignment(1, 1),
                                                                colors=["#05131E", "#0A2A3C", "#08111D"],
                                                            ),
                                                        ),
                                                        ft.Container(left=180, top=80, width=360, height=180, border_radius=999, bgcolor="#0EFFFFFF"),
                                                        ft.Container(left=1220, top=760, width=520, height=220, border_radius=999, bgcolor="#0AFFFFFF"),
                                                        ft.Container(right=220, top=120, width=420, height=200, border_radius=999, bgcolor="#0C7DD3FC"),
                                                        *route_dots,
                                                        *stage_items,
                                                        ft.Container(
                                                            visible=not visible_maps,
                                                            expand=True,
                                                            alignment=ft.Alignment(0, 0),
                                                            content=ft.Container(
                                                                width=480,
                                                                padding=26,
                                                                border_radius=28,
                                                                bgcolor="#071019E8",
                                                                border=ft.border.Border.all(1.8, "#38BDF8"),
                                                                content=ft.Column(
                                                                    [
                                                                        ft.Text("Noch keine eigene Welt", size=30, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                                                                        ft.Text("Gehe auf `Spiel bearbeiten`, füge Inseln hinzu und ordne sie dann frei auf der Fläche an.", size=14, color="#D5E3EE", text_align=ft.TextAlign.CENTER),
                                                                    ],
                                                                    spacing=10,
                                                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                                ),
                                                            ),
                                                        ),
                                                    ],
                                                    expand=True,
                                                ),
                                            ),
                                        ),
                                    ) if creative_mode else _questions_path_interactive_viewer(
                                        ft.Container(
                                            width=canvas_w,
                                            height=canvas_h,
                                            scale=zoom,
                                            animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
                                            content=ft.Stack(
                                                [
                                                    ft.Container(
                                                        expand=True,
                                                        gradient=ft.LinearGradient(
                                                            begin=ft.Alignment(-1, -1),
                                                            end=ft.Alignment(1, 1),
                                                            colors=["#05131E", "#0A2A3C", "#08111D"],
                                                        ),
                                                    ),
                                                    ft.Container(left=180, top=80, width=360, height=180, border_radius=999, bgcolor="#0EFFFFFF"),
                                                    ft.Container(left=1220, top=760, width=520, height=220, border_radius=999, bgcolor="#0AFFFFFF"),
                                                    ft.Container(right=220, top=120, width=420, height=200, border_radius=999, bgcolor="#0C7DD3FC"),
                                                    *route_dots,
                                                    *stage_items,
                                                ],
                                                expand=True,
                                            ),
                                        )
                                    ),
                                ),
                                ft.Row(
                                    [
                                        _questions_path_island_chip("Bearbeitbar", "#0EA5E9") if creative_mode else _questions_path_island_chip("Aktiv", "#0EA5E9"),
                                        _questions_path_island_chip("Abgeschlossen", "#16A34A") if not creative_mode else _questions_path_island_chip("Drag" if creative_edit_mode else "Spiel", "#16A34A"),
                                        _questions_path_island_chip("Gesperrt", "#475569") if not creative_mode else _questions_path_island_chip("Tap = Eintauchen" if creative_edit_mode else "Tap = Start", "#475569"),
                                        _questions_path_island_chip(f"{len(visible_maps)} Inseln", "#334155"),
                                    ],
                                    spacing=10,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def _questions_path_render_level(page: ft.Page, state: dict):
    theme = get_theme(state)
    game = state.get("questions_path_game")
    if not game:
        show_questions_path_hub(page, state)
        return

    profiles = get_questions_path_profiles(state)
    active_index = get_questions_path_profile_index(state)
    active_profile = profiles[active_index] if active_index < len(profiles) else _questions_path_default_profile(0)
    map_key = game.get("map_key", "waldpfad")
    map_cfg = _questions_path_map_lookup_for_profile(active_profile, map_key)
    questions = list(game.get("questions") or [])
    points = list(map_cfg.get("points", []) or [])
    if not questions or not points:
        show_questions_path_hub(page, state)
        return

    if bool(game.get("game_finished", False)) or int(game.get("node_index", 0) or 0) >= len(questions):
        render_questions_path_complete(page, state)
        return

    page_w, page_h = _page_size(page)
    base_canvas_w = max(1700, int(page_w * 1.30))
    base_canvas_h = max(1100, int(page_h * 1.05))
    fit_zoom = round(max(0.45, min(1.0, min(max(1, page_w - 40) / base_canvas_w, max(1, page_h - 240) / base_canvas_h))), 2)
    zoom = max(0.45, min(1.8, float(state.get("questions_path_level_zoom", fit_zoom) or fit_zoom)))
    state["questions_path_level_zoom"] = zoom
    card_w = max(320, int(page_w - 24))
    card_h = max(440, int(page_h * 0.52))
    canvas_w = base_canvas_w
    canvas_h = base_canvas_h
    current_index = int(game.get("node_index", 0) or 0)
    completed_nodes = {int(v) for v in list(game.get("completed_nodes", [])) if str(v).isdigit() or isinstance(v, int)}
    active_node = state.get("_questions_path_active_node")
    replay_prompt = state.get("_questions_path_replay_prompt")

    def open_current_node(e):
        state["_questions_path_active_node"] = current_index
        render_questions_path_game(e.page, state)

    def ask_restart(level_idx: int):
        def _handler(e):
            state["_questions_path_replay_prompt"] = level_idx
            render_questions_path_game(e.page, state)

        return _handler

    stage_items = []
    route_dots = []
    for idx in range(max(0, len(points) - 1)):
        x1, y1 = points[idx]["x"], points[idx]["y"]
        x2, y2 = points[idx + 1]["x"], points[idx + 1]["y"]
        for step in range(1, 5):
            mix = step / 5
            route_dots.append(
                ft.Container(
                    left=int(canvas_w * ((x1 + (x2 - x1) * mix) / 100.0)) - 6,
                    top=int(canvas_h * ((y1 + (y2 - y1) * mix) / 100.0)) - 6,
                    width=12,
                    height=12,
                    border_radius=999,
                    bgcolor="#E2E8F077" if idx < current_index else "#94A3B866",
                )
            )

    for idx, point in enumerate(points):
        node_state = "future"
        if idx in completed_nodes:
            node_state = "done"
        elif idx == current_index:
            node_state = "current"
        left = int(canvas_w * (point["x"] / 100.0)) - 34
        top = int(canvas_h * (point["y"] / 100.0)) - 34
        if node_state == "done":
            node_bg = "#10B981"
            node_border = "#D1FAE5"
            node_text = "✓"
        elif node_state == "current":
            node_bg = map_cfg.get("accent", "#34D399")
            node_border = "#F8FAFC"
            node_text = str(idx + 1)
        else:
            node_bg = "#1E293B"
            node_border = "#475569"
            node_text = str(idx + 1)
        stage_items.append(
            ft.Container(
                left=left,
                top=top,
                width=68,
                height=68,
                border_radius=999,
                bgcolor=node_bg,
                border=ft.border.Border.all(3, node_border),
                shadow=ft.BoxShadow(blur_radius=22, color=f"#55{node_bg[1:]}" if node_bg.startswith("#") and len(node_bg) == 7 else "#33000000", spread_radius=1),
                on_click=open_current_node if idx == current_index else (ask_restart(idx) if idx in completed_nodes else None),
                content=ft.Container(
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(node_text, size=22, weight="bold", color="#08131F" if node_state != "future" else "white"),
                ),
            )
        )
        stage_items.append(
            ft.Container(
                left=left - 18,
                top=top + 76,
                width=104,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(point.get("label", f"Station {idx + 1}"), size=11, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
            )
        )

    progress_value = min(1.0, current_index / max(1, len(points)))

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _questions_path_backdrop(map_cfg.get("accent", "#34D399"), map_cfg.get("border", "#38BDF8")),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(12, 10, 12, 10),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        _game_menu_button("← Inselkarte", lambda e: (state.__setitem__("questions_path_scene", "islands"), show_questions_path_hub(e.page, state)), "#475569", width=170, height=40),
                                        ft.Text("Fragen-Pfad", size=32, weight="bold", color="white"),
                                        ft.Row(
                                            [
                                                _questions_path_zoom_controls(state, "questions_path_level_zoom", lambda p, s: _questions_path_render_level(p, s)),
                                                _questions_path_island_chip(f"{len(completed_nodes)}/{len(points)} fertig", map_cfg.get("accent", "#34D399")),
                                            ],
                                            spacing=10,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(map_cfg.get("title", "Insel"), size=15, weight="bold", color=map_cfg.get("accent", "#34D399"), text_align=ft.TextAlign.CENTER),
                                ft.Text(map_cfg.get("subtitle", ""), size=13, color="#BDD2E1", text_align=ft.TextAlign.CENTER),
                                ft.ProgressBar(value=progress_value, height=10, color=map_cfg.get("accent", "#34D399"), bgcolor="#243244"),
                                ft.Container(
                                    expand=True,
                                    width=card_w,
                                    border_radius=28,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    bgcolor="#07101AE0",
                                    content=_questions_path_interactive_viewer(
                                        ft.Container(
                                            width=canvas_w,
                                            height=canvas_h,
                                            scale=zoom,
                                            animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
                                            content=ft.Stack(
                                                [
                                                    ft.Container(
                                                        expand=True,
                                                        gradient=ft.LinearGradient(
                                                            begin=ft.Alignment(-1, -1),
                                                            end=ft.Alignment(1, 1),
                                                            colors=[map_cfg.get("panel", "#0A1712E8"), "#0B1828", "#07101A"],
                                                        ),
                                                    ),
                                                    ft.Container(
                                                        expand=True,
                                                        opacity=0.38,
                                                            content=ft.Image(
                                                                src=_questions_path_cached_image_src(map_cfg.get("map_image_src", "")),
                                                                fit=ft.BoxFit.COVER,
                                                                error_content=ft.Container(),
                                                            ) if map_cfg.get("map_image_src") else ft.Container(),
                                                        ),
                                                    ft.Container(left=180, top=52, width=280, height=120, border_radius=999, bgcolor="#0BFFFFFF"),
                                                    ft.Container(right=120, bottom=36, width=260, height=110, border_radius=999, bgcolor="#08FFFFFF"),
                                                    *route_dots,
                                                    *stage_items,
                                                ],
                                                expand=True,
                                            ),
                                        )
                                    ),
                                ),
                                ft.Row(
                                    [
                                        ft.Text(f"Aktuelle Station: {points[current_index].get('label', f'Station {current_index + 1}')}", size=13, color="white"),
                                        ft.Text("Klicke auf grüne Haken, um eine Inselrunde erneut zu starten.", size=13, color="#B6C8D8"),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                            ],
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        visible=isinstance(active_node, int) and active_node == current_index,
                        content=ft.Container(
                            expand=True,
                            bgcolor="#010611F0",
                            blur=18,
                            alignment=ft.Alignment(0, 0),
                            content=_questions_path_question_card(page, state, game, map_cfg, current_index, card_w),
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        visible=isinstance(replay_prompt, int),
                        content=ft.Container(
                            expand=True,
                            bgcolor="#010611F0",
                            blur=18,
                            alignment=ft.Alignment(0, 0),
                            content=ft.Container(
                                width=min(520, card_w - 32),
                                padding=24,
                                border_radius=24,
                                bgcolor="#0B1220F4",
                                border=ft.border.Border.all(2, map_cfg.get("accent", "#34D399")),
                                content=ft.Column(
                                    [
                                        ft.Text("Level bereits geschafft", size=28, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                                        ft.Text(
                                            "Du hast dieses Level schon geschafft. Möchtest du die Insel noch einmal von vorne spielen?",
                                            size=14,
                                            color="#D3E3EE",
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        ft.Row(
                                            [
                                                _game_menu_button("Weiter spielen", lambda e: (state.pop("_questions_path_replay_prompt", None), render_questions_path_game(e.page, state)), "#475569", width=180, height=42),
                                                _game_menu_button("Nochmal spielen", lambda e: (state.pop("_questions_path_replay_prompt", None), start_questions_path_game(e.page, state, map_key)), map_cfg.get("accent", "#34D399"), width=180, height=42),
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                    ],
                                    spacing=16,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ),
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def render_questions_path_complete(page: ft.Page, state: dict):
    game = state.get("questions_path_game") or {}
    profiles = get_questions_path_profiles(state)
    active_index = get_questions_path_profile_index(state)
    active_profile = profiles[active_index] if active_index < len(profiles) else _questions_path_default_profile(0)
    map_key = game.get("map_key", "waldpfad")
    map_cfg = _questions_path_map_lookup_for_profile(active_profile, map_key)
    game["game_finished"] = True
    save_questions_path_game(state)
    state.pop("_questions_path_active_node", None)
    state["questions_path_scene"] = "complete"
    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Stack(
                [
                    _questions_path_backdrop(map_cfg.get("accent", "#34D399"), map_cfg.get("border", "#38BDF8")),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Container(
                            width=min(640, max(340, int(_page_size(page)[0] - 40))),
                            padding=28,
                            border_radius=28,
                            bgcolor="#0B1220F5",
                            border=ft.border.Border.all(2, map_cfg.get("accent", "#34D399")),
                            content=ft.Column(
                                [
                                    ft.Text("Pfad abgeschlossen", size=32, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
                                    ft.Text(map_cfg.get("title", "Insel"), size=18, weight="bold", color=map_cfg.get("accent", "#34D399"), text_align=ft.TextAlign.CENTER),
                                    ft.Text("Diese Insel ist geschafft. Du kannst sie jederzeit erneut spielen.", size=14, color="#C8D7E6", text_align=ft.TextAlign.CENTER),
                                    ft.Container(height=8),
                                    _game_menu_button("Nochmal spielen", lambda e: start_questions_path_game(e.page, state, map_key), map_cfg.get("accent", "#34D399"), width=260, height=42),
                                    _game_menu_button("Zur Inselkarte", lambda e: (clear_questions_path_game(state), state.__setitem__("questions_path_scene", "islands"), show_questions_path_hub(e.page, state)), "#334155", width=260, height=42),
                                    _game_menu_button("Zur Spielauswahl", lambda e: (clear_questions_path_game(state), open_main_menu(e.page, state)), "#475569", width=260, height=42),
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
    page.run_task(_sync_bg_music_async, page, state)


# ========================================
# ENHANCED MAP EDITOR - NEW HELPER FUNCTIONS
# ========================================

def _create_modern_marker(idx: int, point: dict, point_index: int, is_dragging: bool = False, 
                          on_click=None, on_pan_start=None, on_pan_update=None, 
                          on_pan_end=None) -> ft.Container:
    """
    Erstellt einen modernen, visuell ansprechenden Marker für einen Pfadpunkt.
    Features:
    - Schatten für Tiefenwirkung
    - Hover-Effekt (Skalierung und Farbwechsel)
    - Klare Sichtbarkeit auf verschiedenen Hintergründen
    - Animierte Übergänge
    """
    is_active = idx == point_index
    
    # Farben basierend auf Zustand
    bg_color = "#EC4899" if is_active else "#0EA5E9"
    border_color = "#FCE7F3" if is_active else "#DBEAFE"
    shadow_color = "#EC4899" if is_active else "#0EA5E9"
    
    # Größe anpassen basierend auf Zustand
    marker_size = 72 if is_active else 64
    
    return ft.Container(
        padding=8,
        border_radius=999,
        # Schatten-Effekt
        bgcolor="#00000020",
        shadow=ft.BoxShadow(
            blur_radius=12,
            spread_radius=2,
            color=shadow_color if is_active else "#00000040",
            offset=ft.Offset(0, 4)
        ),
        content=ft.GestureDetector(
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
            on_tap=on_click,
            drag_interval=1,
            mouse_cursor=ft.MouseCursor.MOVE,
            content=ft.Container(
                width=marker_size,
                height=marker_size,
                border_radius=999,
                bgcolor=bg_color,
                border=ft.border.Border.all(3, border_color),
                alignment=ft.Alignment(0, 0),
                # Animierte Skalierung bei Hover
                animate_scale=ft.animation.Animation(200, "easeOut"),
                scale=1.1 if is_active else 1.0,
                content=ft.Text(
                    str(idx + 1),
                    size=22 if is_active else 20,
                    weight="bold",
                    color="white"
                ),
            )
        ),
    )


def _create_point_label(point: dict, idx: int) -> ft.Container:
    """Erstellt ein ansprechendes Label für einen Pfadpunkt"""
    return ft.Container(
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=8,
        bgcolor="#08131D",
        border=ft.border.Border.all(1, "#334155"),
        content=ft.Text(
            point.get("label", f"Punkt {idx + 1}"),
            size=10,
            weight="bold",
            color="white",
            text_align=ft.TextAlign.CENTER,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS
        )
    )


def _questions_path_default_custom_question_enhanced(idx: int) -> dict:
    """
    Erstellt eine neue Frage mit Unterstützung für mehrfache richtige Antworten
    """
    return {
        "question": "",
        "answers": ["", "", "", ""],
        "correct_answers": ["A"],  # NEU: Liste statt einzelner Index
        # Fallback für Kompatibilität
        "correct_idx": 0,
    }


def _ensure_backward_compatibility(question: dict) -> dict:
    """
    Konvertiert alte Fragendaten zu neuem Format
    Fallback für alte Spieledaten
    """
    q = dict(question)
    
    # Wenn noch alte Struktur
    if "correct_idx" in q and "correct_answers" not in q:
        correct_idx = int(q.get("correct_idx", 0))
        if 0 <= correct_idx < 4:
            q["correct_answers"] = [ANSWER_LETTERS[correct_idx]]
        else:
            q["correct_answers"] = [ANSWER_LETTERS[0]]
    
    # Stelle sicher, dass correct_answers immer eine Liste ist
    if "correct_answers" not in q:
        q["correct_answers"] = [ANSWER_LETTERS[0]]
    
    return q


def _create_question_editor_modal(page: ft.Page, state: dict, point_index: int, 
                                  points: list, current_questions: list, 
                                  on_save=None, on_close=None) -> ft.AlertDialog:
    """
    Erstellt ein modales Fenster zur Bearbeitung von Fragen und Antworten.
    Features:
    - Checkboxen für mehrfache korrekte Antworten
    - Moderne UI mit guter Übersichtlichkeit
    - Live-Speicherung
    """
    
    if point_index >= len(current_questions):
        current_questions.append(_questions_path_default_custom_question_enhanced(point_index))
    
    active_question = dict(current_questions[point_index])
    active_answers = list(active_question.get("answers", []) or [])
    while len(active_answers) < 4:
        active_answers.append("")
    
    # Mehrfache korrekte Antworten
    correct_answers = set(active_question.get("correct_answers", []))
    if not correct_answers and "correct_idx" in active_question:
        # Fallback für alte Daten
        correct_idx = int(active_question.get("correct_idx", 0))
        if 0 <= correct_idx < 4:
            correct_answers = {ANSWER_LETTERS[correct_idx]}
    
    question_ref = ft.Ref[ft.TextField]()
    answer_refs = [ft.Ref[ft.TextField]() for _ in range(4)]
    checkbox_refs = [ft.Ref[ft.Checkbox]() for _ in range(4)]
    
    def save_question_data(e):
        """Speichert die Fragendaten mit Mehrfachauswahl"""
        if on_save:
            q_data = {
                "question": str(question_ref.current.value or "").strip() or 
                           active_question.get("question", "Frage"),
                "answers": [
                    str(answer_refs[i].current.value or "").strip() or 
                    active_answers[i] or f"Antwort {ANSWER_LETTERS[i]}"
                    for i in range(4)
                ],
                "correct_answers": [ANSWER_LETTERS[i] for i in range(4) 
                                   if checkbox_refs[i].current.value],
            }
            # Fallback: Wenn keine korrekte Antwort ausgewählt ist, Standard setzen
            if not q_data["correct_answers"]:
                q_data["correct_answers"] = [ANSWER_LETTERS[0]]
            
            on_save(point_index, q_data)
        
        if on_close:
            on_close(e)
    
    # Erstelle Antwort-Zeilen mit Checkboxen
    answer_rows = []
    for i in range(4):
        answer_rows.append(
            ft.Container(
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=12,
                bgcolor="#0F1823",
                border=ft.border.Border.all(1, "#334155"),
                content=ft.Row(
                    [
                        ft.Checkbox(
                            ref=checkbox_refs[i],
                            value=ANSWER_LETTERS[i] in correct_answers,
                            label=f"Korrekt",
                            fill_color="#0EA5E9",
                            check_color="white",
                        ),
                        ft.TextField(
                            ref=answer_refs[i],
                            value=active_answers[i],
                            label=f"Antwort {ANSWER_LETTERS[i]}",
                            bgcolor="#111827",
                            color="white",
                            border_color="#334155",
                            filled=False,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )
    
    content = ft.Container(
        width=600,
        padding=20,
        content=ft.Column(
            [
                ft.Text("Frage bearbeiten", size=20, weight="bold", color="white"),
                ft.Divider(color="#334155"),
                
                ft.Text("Frage:", size=12, weight="bold", color="#A8C0D2"),
                ft.TextField(
                    ref=question_ref,
                    value=active_question.get("question", ""),
                    label="Gib die Frage ein...",
                    bgcolor="#111827",
                    color="white",
                    border_color="#334155",
                    min_lines=2,
                ),
                
                ft.Text("Antworten (markiere alle korrekten):", size=12, weight="bold", 
                       color="#A8C0D2"),
                ft.Column(answer_rows, spacing=10),
                
                ft.Divider(color="#334155"),
                
                ft.Row(
                    [
                        ft.TextButton(
                            "Abbrechen",
                            icon=ft.icons.CLOSE,
                            style=ft.ButtonStyle(color="#A8C0D2"),
                            on_click=on_close,
                        ),
                        ft.ElevatedButton(
                            "Speichern",
                            icon=ft.icons.SAVE,
                            style=ft.ButtonStyle(
                                bgcolor="#0EA5E9",
                                color="white",
                            ),
                            on_click=save_question_data,
                        ),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
    
    dialog = ft.AlertDialog(
        modal=True,
        bgcolor="#07101A",
        content=content,
    )
    
    return dialog


def _questions_path_render_editor(page: ft.Page, state: dict):
    theme = get_theme(state)
    profiles = get_questions_path_profiles(state)
    if not profiles:
        profiles = [_questions_path_default_profile(0)]
        persist_questions_path_profiles(state, profiles)
    state["questions_path_profiles"] = profiles
    active_index = get_questions_path_profile_index(state)
    active_profile = profiles[active_index] if active_index < len(profiles) else _questions_path_default_profile(0)
    creative_mode = _questions_path_profile_mode(active_profile) == "creative"
    custom_islands = [dict(item) for item in list(active_profile.get("custom_islands", []) or []) if isinstance(item, dict)]
    editing_island_key = str(state.get("_questions_path_editor_island_key") or state.get("_questions_path_editor_map_key") or "").strip()
    editing_island_index = next((idx for idx, island in enumerate(custom_islands) if str(island.get("map_key", "")).strip() == editing_island_key), None)

    editor_maps = _questions_path_editor_maps_for_profile(active_profile)
    if not editor_maps:
        editor_maps = [("waldpfad", QUESTIONS_PATH_MAPS["waldpfad"], False)]

    selected_map_key = str(state.get("_questions_path_editor_map_key") or editor_maps[0][0]).strip() or editor_maps[0][0]
    if selected_map_key not in {key for key, _, _ in editor_maps}:
        selected_map_key = editor_maps[0][0]
    state["_questions_path_editor_map_key"] = selected_map_key

    if creative_mode and editing_island_index is not None:
        map_cfg = _questions_path_custom_map(custom_islands[editing_island_index], editing_island_index)
    else:
        map_cfg = _questions_path_editor_map_lookup(active_profile, selected_map_key)
        state.pop("_questions_path_editor_island_key", None)

    page_w, page_h = _page_size(page)
    card_w = max(320, int(page_w - 24))
    card_h = max(520, int(page_h - 160))
    base_canvas_w = max(1600, int(page_w * 1.25))
    base_canvas_h = max(1100, int(page_h * 1.08))
    fit_zoom = round(max(0.45, min(1.0, min(max(1, page_w - 40) / base_canvas_w, max(1, page_h - 220) / base_canvas_h))), 2)
    zoom = max(0.45, min(2.2, float(state.get("questions_path_editor_zoom", fit_zoom) or fit_zoom)))
    state["questions_path_editor_zoom"] = zoom

    point_index = max(0, int(state.get("_questions_path_editor_point_index", 0) or 0))
    points = list(map_cfg.get("points", []) or [])
    if not points:
        points = _path_nodes([(50, 55)], ["Start"])
    point_index = max(0, min(point_index, len(points) - 1))
    state["_questions_path_editor_point_index"] = point_index
    selection_visible = bool(state.get("_questions_path_editor_selection_visible", True))
    state.setdefault("_questions_path_editor_selection_visible", selection_visible)
    active_point = dict(points[point_index])

    map_title_ref = ft.Ref[ft.TextField]()
    map_subtitle_ref = ft.Ref[ft.TextField]()
    point_marker_refs: dict[int, ft.Ref[ft.Container]] = {}

    def clear_point_selection(e):
        state["_questions_path_editor_selection_visible"] = False
        _questions_path_render_editor(e.page, state)

    def normalize_map_payload(raw_map: dict) -> dict:
        current = dict(raw_map)
        current["title"] = str(current.get("title", "Map")).strip() or "Map"
        current["subtitle"] = str(current.get("subtitle", "")).strip()
        current["icon"] = str(current.get("icon", "🗺️")).strip() or "🗺️"
        current["points"] = ensure_points_list(current)
        current["questions"] = _questions_path_copy_questions(current.get("questions", [])) or [_questions_path_default_custom_question(0)]
        while len(current["questions"]) < len(current["points"]):
            current["questions"].append(_questions_path_default_custom_question(len(current["questions"])))
        current["questions"] = current["questions"][: len(current["points"])]
        return current

    def save_target(mutator):
        refreshed_profiles = get_questions_path_profiles(state)
        refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else active_profile)
        islands = [dict(item) for item in list(refreshed_profile.get("custom_islands", []) or []) if isinstance(item, dict)]
        if creative_mode and editing_island_index is not None and editing_island_index < len(islands):
            island = dict(islands[editing_island_index])
            current_map = normalize_map_payload(_questions_path_custom_map(island, editing_island_index))
            mutator(current_map)
            current_map = normalize_map_payload(current_map)
            island["title"] = current_map.get("title", island.get("title", "Eigene Insel"))
            island["subtitle"] = current_map.get("subtitle", island.get("subtitle", ""))
            island["world_name"] = current_map.get("world_name", island.get("world_name", island["title"]))
            island["world_description"] = current_map.get("world_description", island.get("world_description", island["subtitle"]))
            island["icon"] = current_map.get("icon", island.get("icon", "🏝️"))
            island["image_src"] = current_map.get("image_src", island.get("image_src", ""))
            island["map_image_src"] = current_map.get("map_image_src", island.get("map_image_src", ""))
            island["accent"] = current_map.get("accent", island.get("accent", "#34D399"))
            island["panel"] = current_map.get("panel", island.get("panel", "#0A1712E8"))
            island["border"] = current_map.get("border", island.get("border", "#38BDF8"))
            island["line"] = current_map.get("line", island.get("line", "#86EFAC"))
            island["world_layout"] = current_map.get("world_layout", island.get("world_layout", "classic"))
            island["custom_points"] = _questions_path_copy_points(current_map.get("points", []))
            island["questions"] = _questions_path_copy_questions(current_map.get("questions", []))
            islands[editing_island_index] = island
            refreshed_profile["custom_islands"] = islands
            refreshed_profile["progression_mode"] = "creative"
        else:
            current_map = normalize_map_payload(_questions_path_editor_map_lookup(refreshed_profile, selected_map_key))
            mutator(current_map)
            _questions_path_editor_save_map(refreshed_profile, selected_map_key, normalize_map_payload(current_map))
        refreshed_profiles[active_index] = refreshed_profile
        persist_questions_path_profiles(state, refreshed_profiles)
        state["questions_path_profiles"] = refreshed_profiles

    def live_editor_map() -> dict:
        refreshed_profiles = get_questions_path_profiles(state)
        refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else active_profile)
        islands = [dict(item) for item in list(refreshed_profile.get("custom_islands", []) or []) if isinstance(item, dict)]
        if creative_mode and editing_island_index is not None and editing_island_index < len(islands):
            return normalize_map_payload(_questions_path_custom_map(islands[editing_island_index], editing_island_index))
        return normalize_map_payload(_questions_path_editor_map_lookup(refreshed_profile, selected_map_key))

    def apply_template(map_key: str):
        def _handler(e):
            if creative_mode and editing_island_index is not None:
                template_cfg = dict(_questions_path_editor_map_lookup(active_profile, map_key))
                def _mutate(raw_map):
                    current_points = _questions_path_copy_points(raw_map.get("points", [])) or _path_nodes([(50, 55)], ["Start"])
                    current_questions = _questions_path_copy_questions(raw_map.get("questions", [])) or [_questions_path_default_custom_question(0)]
                    raw_map["subtitle"] = str(template_cfg.get("subtitle", raw_map.get("subtitle", ""))).strip()
                    raw_map["icon"] = str(template_cfg.get("icon", raw_map.get("icon", "🗺️"))).strip() or raw_map.get("icon", "🗺️")
                    raw_map["map_image_src"] = str(template_cfg.get("map_image_src", template_cfg.get("image", ""))).strip()
                    raw_map["image_src"] = str(template_cfg.get("image_src", raw_map.get("image_src", ""))).strip()
                    raw_map["accent"] = template_cfg.get("accent", raw_map.get("accent", "#34D399"))
                    raw_map["panel"] = template_cfg.get("panel", raw_map.get("panel", "#0A1712E8"))
                    raw_map["border"] = template_cfg.get("border", raw_map.get("border", "#38BDF8"))
                    raw_map["line"] = template_cfg.get("line", raw_map.get("line", "#86EFAC"))
                    raw_map["world_layout"] = template_cfg.get("world_layout", raw_map.get("world_layout", "classic"))
                    raw_map["points"] = current_points
                    raw_map["questions"] = current_questions[: len(current_points)]
                    while len(raw_map["questions"]) < len(current_points):
                        raw_map["questions"].append(_questions_path_default_custom_question(len(raw_map["questions"])))

                save_target(_mutate)
            else:
                state["_questions_path_editor_map_key"] = map_key
                state["_questions_path_editor_point_index"] = 0
            _questions_path_render_editor(e.page, state)

        return _handler

    def set_active_point(index: int):
        def _handler(e):
            state["_questions_path_editor_point_index"] = index
            state["_questions_path_editor_selection_visible"] = True
            _questions_path_render_editor(e.page, state)

        return _handler

    def ensure_points_list(raw_map: dict) -> list[dict]:
        pts = _questions_path_copy_points(raw_map.get("points", []))
        return pts or _path_nodes([(50, 55)], ["Start"])

    def add_point(e):
        current_map = live_editor_map()
        current_points = _questions_path_copy_points(current_map.get("points", []))
        if len(current_points) >= 20:
            e.page.snack_bar = ft.SnackBar(content=ft.Text("Maximal 20 Pfadpunkte sind möglich."), open=True)
            e.page.update()
            return
        new_index = len(current_points)

        def _mutate(raw_map):
            raw_points = ensure_points_list(raw_map)
            if raw_points:
                anchor = raw_points[-1]
                new_x = max(8, min(92, int(anchor.get("x", 50) or 50) + 8))
                new_y = max(8, min(92, int(anchor.get("y", 55) or 55) + 6))
                if any(abs(int(p.get("x", 0) or 0) - new_x) < 3 and abs(int(p.get("y", 0) or 0) - new_y) < 3 for p in raw_points):
                    new_x = max(8, min(92, new_x + 8 if new_x <= 84 else new_x - 12))
                    new_y = max(8, min(92, new_y + 6 if new_y <= 86 else new_y - 10))
            else:
                new_x = 50
                new_y = 55
            raw_points.append({"x": new_x, "y": new_y, "label": f"Punkt {len(raw_points) + 1}"})
            raw_map["points"] = raw_points[:20]
            raw_questions = list(raw_map.get("questions", []) or [])
            while len(raw_questions) < len(raw_points):
                raw_questions.append(_questions_path_default_custom_question_enhanced(len(raw_questions)))
            raw_map["questions"] = raw_questions[: len(raw_points)]

        save_target(_mutate)
        refreshed_map = live_editor_map()
        refreshed_points = _questions_path_copy_points(refreshed_map.get("points", []))
        refreshed_questions = _questions_path_copy_questions(refreshed_map.get("questions", []))
        state["_questions_path_editor_point_index"] = max(0, min(new_index, len(refreshed_points) - 1))
        state["_questions_path_editor_selection_visible"] = True
        _questions_path_render_editor(e.page, state)
        _open_question_editor_modal(
            e.page,
            state,
            state["_questions_path_editor_point_index"],
            refreshed_points,
            refreshed_questions,
        )

    def remove_point(e):
        def _mutate(raw_map):
            raw_points = ensure_points_list(raw_map)
            if len(raw_points) <= 1:
                return
            idx = max(0, min(int(state.get("_questions_path_editor_point_index", 0) or 0), len(raw_points) - 1))
            raw_points.pop(idx)
            raw_map["points"] = raw_points
            raw_questions = list(raw_map.get("questions", []) or [])
            if idx < len(raw_questions) and len(raw_questions) > 1:
                raw_questions.pop(idx)
            raw_map["questions"] = raw_questions or [_questions_path_default_custom_question(0)]

        save_target(_mutate)
        state["_questions_path_editor_point_index"] = max(0, point_index - 1)
        state["_questions_path_editor_selection_visible"] = True
        _questions_path_render_editor(e.page, state)

    def create_custom_map(rel_path: str, keep_content: bool, page_obj: ft.Page):
        refreshed_profiles = get_questions_path_profiles(state)
        refreshed_profile = dict(refreshed_profiles[active_index] if active_index < len(refreshed_profiles) else active_profile)
        custom_maps = list(refreshed_profile.get("custom_maps", []) or [])
        new_map = _questions_path_default_custom_map(len(custom_maps))
        new_map["map_key"] = f"custom_map_{len(custom_maps) + 1}"
        new_map["title"] = f"Eigene Map {len(custom_maps) + 1}"
        new_map["map_image_src"] = rel_path
        new_map["image"] = rel_path
        if keep_content:
            new_map["points"] = _questions_path_copy_points(map_cfg.get("points", [])) or _path_nodes([(50, 55)], ["Start"])
            new_map["questions"] = _questions_path_copy_questions(map_cfg.get("questions", [])) or [_questions_path_default_custom_question(0)]
        custom_maps.append(new_map)
        refreshed_profile["custom_maps"] = custom_maps[-12:]
        refreshed_profiles[active_index] = refreshed_profile
        persist_questions_path_profiles(state, refreshed_profiles)
        state["questions_path_profiles"] = refreshed_profiles
        if creative_mode and editing_island_index is not None:
            def _mutate(raw_map):
                raw_map["map_image_src"] = rel_path
                raw_map["image"] = rel_path
                if not keep_content:
                    raw_map["points"] = _path_nodes([(50, 55)], ["Start"])
                    raw_map["questions"] = [_questions_path_default_custom_question(0)]
            save_target(_mutate)
        else:
            state["_questions_path_editor_map_key"] = new_map["map_key"]
            if not keep_content:
                state["_questions_path_editor_point_index"] = 0
        _questions_path_render_editor(page_obj, state)

    def ask_custom_map_mode(page_obj: ft.Page, rel_path: str):
        dlg = ft.AlertDialog(
            modal=True,
            bgcolor="#0B1220",
            title=ft.Text("Eigene Map hinzufügen", color="white"),
            content=ft.Text("Sollen die vorhandenen Punkte und Fragen übernommen werden oder möchtest du komplett neu anfangen?", color="#D7E6F5"),
            actions_alignment=ft.MainAxisAlignment.END,
            actions=[
                _game_menu_button(
                    "Neu anfangen",
                    lambda e: (close_page_dialog(page_obj, dlg), create_custom_map(rel_path, False, page_obj)),
                    "#7C2D12",
                    width=170,
                    height=40,
                ),
                _game_menu_button(
                    "Punkte übernehmen",
                    lambda e: (close_page_dialog(page_obj, dlg), create_custom_map(rel_path, True, page_obj)),
                    "#0F766E",
                    width=190,
                    height=40,
                ),
            ],
        )
        open_page_dialog(page_obj, dlg)

    async def pick_custom_map_task(page_obj: ft.Page):
        rel_path = await _questions_path_pick_and_store_image(page_obj, "custom_map")
        if rel_path:
            ask_custom_map_mode(page_obj, rel_path)

    def pick_custom_map(e):
        e.page.run_task(pick_custom_map_task, e.page)

    def _open_question_editor_modal(pg: ft.Page, st: dict, pt_idx: int, pts: list, q_list: list):
        """Öffnet das Modal zur Fragenbearbeitung"""
        def save_question(point_idx: int, q_data: dict):
            def _mutate(raw_map):
                raw_questions = list(raw_map.get("questions", []) or [])
                while len(raw_questions) < len(raw_map.get("points", [])):
                    raw_questions.append(_questions_path_default_custom_question_enhanced(len(raw_questions)))
                if point_idx < len(raw_questions):
                    raw_questions[point_idx] = _ensure_backward_compatibility(q_data)
                raw_map["questions"] = raw_questions
            
            save_target(_mutate)
            # Schließe Dialog
            if pg.dialog:
                pg.dialog.open = False
            pg.update()
            _questions_path_render_editor(pg, st)
        
        def close_dialog(e):
            if pg.dialog:
                pg.dialog.open = False
            pg.update()
        
        dlg = _create_question_editor_modal(
            pg, st, pt_idx, pts, q_list,
            on_save=save_question,
            on_close=close_dialog
        )
        pg.dialog = dlg
        dlg.open = True
        pg.update()

    def save_point_details(e):
        def _mutate(raw_map):
            raw_points = ensure_points_list(raw_map)
            idx = max(0, min(int(state.get("_questions_path_editor_point_index", 0) or 0), len(raw_points) - 1))
            if idx < len(raw_points):
                raw_points[idx]["label"] = str(map_title_ref.current.value or raw_points[idx].get("label", f"Punkt {idx + 1}")).strip() or f"Punkt {idx + 1}"
                raw_points[idx]["x"] = max(2, min(96, int(raw_points[idx].get("x", 10) or 10)))
                raw_points[idx]["y"] = max(2, min(96, int(raw_points[idx].get("y", 10) or 10)))
            raw_map["points"] = raw_points

        save_target(_mutate)
        _questions_path_render_editor(e.page, state)

    def point_left_from_percent(percent_x: float) -> int:
        marker_w = 100
        return max(8, min(int(base_canvas_w - marker_w - 8), int((float(percent_x) / 100.0) * max(1, base_canvas_w - marker_w))))

    def point_top_from_percent(percent_y: float) -> int:
        marker_h = 94
        return max(8, min(int(base_canvas_h - marker_h - 8), int((float(percent_y) / 100.0) * max(1, base_canvas_h - marker_h))))

    def point_drag_start(idx: int):
        def _handler(e):
            state["_questions_path_editor_selection_visible"] = True
            current_points = ensure_points_list(map_cfg)
            if idx >= len(current_points):
                return
            drag_state = dict(state.get("_questions_path_editor_drag") or {})
            drag_state[idx] = {
                "start_x": float(current_points[idx].get("x", 10)),
                "start_y": float(current_points[idx].get("y", 10)),
                "x": float(current_points[idx].get("x", 10)),
                "y": float(current_points[idx].get("y", 10)),
            }
            state["_questions_path_editor_drag"] = drag_state
            state["_questions_path_editor_point_index"] = idx

        return _handler

    def point_drag_update(idx: int):
        def _handler(e):
            drag_state = dict(state.get("_questions_path_editor_drag") or {})
            current_drag = dict(drag_state.get(idx) or {})
            if not current_drag:
                return
            dx = float(getattr(e, "delta_x", 0.0) or 0.0)
            dy = float(getattr(e, "delta_y", 0.0) or 0.0)
            current_drag["x"] = max(2.0, min(96.0, float(current_drag.get("x", 10)) + (dx / max(1.0, base_canvas_w * zoom)) * 100.0))
            current_drag["y"] = max(2.0, min(96.0, float(current_drag.get("y", 10)) + (dy / max(1.0, base_canvas_h * zoom)) * 100.0))
            drag_state[idx] = current_drag
            state["_questions_path_editor_drag"] = drag_state
            marker_ref = point_marker_refs.get(idx)
            if marker_ref and marker_ref.current:
                marker_ref.current.left = point_left_from_percent(current_drag["x"])
                marker_ref.current.top = point_top_from_percent(current_drag["y"])
                e.page.update()

        return _handler

    def point_drag_end(idx: int):
        def _handler(e):
            drag_state = dict(state.get("_questions_path_editor_drag") or {})
            current_drag = dict(drag_state.get(idx) or {})
            if current_drag:
                def _mutate(raw_map):
                    raw_points = ensure_points_list(raw_map)
                    if idx < len(raw_points):
                        raw_points[idx]["x"] = max(2, min(96, int(current_drag.get("x", raw_points[idx].get("x", 10)))))
                        raw_points[idx]["y"] = max(2, min(96, int(current_drag.get("y", raw_points[idx].get("y", 10)))))
                        raw_map["points"] = raw_points
                save_target(_mutate)
            drag_state.pop(idx, None)
            state["_questions_path_editor_drag"] = drag_state
            _questions_path_render_editor(e.page, state)

        return _handler

    current_questions = list(map_cfg.get("questions", []) or [])
    while len(current_questions) < len(points):
        current_questions.append(_questions_path_default_custom_question(len(current_questions)))
    active_question = dict(current_questions[point_index]) if current_questions else _questions_path_default_custom_question(0)
    active_answers = list(active_question.get("answers", []) or [])
    while len(active_answers) < 4:
        active_answers.append("")
    render_point_index = point_index if selection_visible else -1
    map_cards = []
    for map_key, cfg, is_custom in editor_maps:
        selected = (map_key == selected_map_key) if editing_island_index is None else False
        preview_src = str(cfg.get("map_image_src") or cfg.get("image") or cfg.get("image_src") or "").strip()
        map_cards.append(
            ft.Container(
                padding=14,
                border_radius=18,
                bgcolor="#0C1723F0" if selected else "#08111BF0",
                border=ft.border.Border.all(2, cfg.get("accent", "#38BDF8") if selected else "#233244"),
                on_click=apply_template(map_key),
                content=ft.Column(
                    [
                        ft.Container(
                            height=110,
                            border_radius=14,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            bgcolor="#101827",
                            content=ft.Stack(
                                [
                                    ft.Container(
                                        expand=True,
                                        gradient=ft.LinearGradient(
                                            begin=ft.Alignment(-1, -1),
                                            end=ft.Alignment(1, 1),
                                            colors=[cfg.get("panel", "#0A1712E8"), "#132235", "#0B1020"],
                                        ),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        opacity=0.78,
                                        content=ft.Image(src=_questions_path_cached_image_src(preview_src), fit=ft.BoxFit.COVER, error_content=ft.Container()),
                                    ) if preview_src else ft.Container(),
                                    ft.Container(
                                        left=10,
                                        bottom=10,
                                        padding=ft.Padding(8, 4, 8, 4),
                                        border_radius=999,
                                        bgcolor="#09131DD8",
                                        content=ft.Text("Als Vorlage nutzen", size=10, color="white", weight="bold"),
                                    ),
                                ]
                            ),
                        ),
                        ft.Row(
                            [
                                ft.Text(cfg.get("icon", "🗺️"), size=18),
                                ft.Text(cfg.get("title", map_key), size=16, weight="bold", color="white"),
                            ],
                            spacing=8,
                        ),
                        ft.Text(cfg.get("subtitle", ""), size=11, color="#A8C0D2"),
                        ft.Text(f"{len(cfg.get('points', []) or [])} Punkte", size=11, color=cfg.get("accent", "#38BDF8")),
                    ],
                    spacing=6,
                ),
            )
        )

    point_markers = []
    for idx, point in enumerate(points):
        left = point_left_from_percent(point["x"])
        top = point_top_from_percent(point["y"])
        marker_ref = ft.Ref[ft.Container]()
        point_marker_refs[idx] = marker_ref
        
        point_markers.append(
            ft.Container(
                ref=marker_ref,
                left=left,
                top=top,
                width=100,
                height=110,
                content=ft.Column(
                    [
                        _create_modern_marker(
                            idx, point, render_point_index,
                            on_click=set_active_point(idx),
                            on_pan_start=point_drag_start(idx),
                            on_pan_update=point_drag_update(idx),
                            on_pan_end=point_drag_end(idx),
                        ),
                        _create_point_label(point, idx),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    page.controls.clear()
    page.add(
        ft.Container(
            expand=True,
            content=ft.Row(
                [
                    ft.Container(
                        expand=True,
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        _game_menu_button("← Inselkarte", lambda e: (state.__setitem__("questions_path_scene", "islands"), show_questions_path_hub(e.page, state)), "#475569", width=170, height=40),
                                        ft.Text("Fragen-Pfad", size=32, weight="bold", color="white"),
                                        ft.Row(
                                            [
                                                _questions_path_zoom_controls(state, "questions_path_editor_zoom", lambda p, s: _questions_path_render_editor(p, s)),
                                                _questions_path_island_chip(map_cfg.get("title", "Map"), map_cfg.get("accent", "#38BDF8")),
                                            ],
                                            spacing=10,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(map_cfg.get("subtitle", ""), size=13, color=theme_txt(theme, "secondary"), text_align=ft.TextAlign.CENTER),
                                ft.Container(
                                    expand=True,
                                    border_radius=28,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    bgcolor="#07101AE0",
                                    content=ft.Container(
                                        alignment=ft.Alignment(0, 0),
                                        content=ft.Container(
                                            width=int(base_canvas_w * zoom),
                                            height=int(base_canvas_h * zoom),
                                            content=ft.Container(
                                                width=base_canvas_w,
                                                height=base_canvas_h,
                                                scale=zoom,
                                                content=ft.Stack(
                                                    [
                                                        ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=[map_cfg.get("panel", "#0A1712E8"), "#0B1828", "#07101A"]), on_click=clear_point_selection),
                                                        ft.Container(expand=True, opacity=0.86, on_click=clear_point_selection, content=ft.Image(src=_questions_path_cached_image_src(map_cfg.get("map_image_src") or map_cfg.get("image", "")), fit=ft.BoxFit.COVER, error_content=ft.Container()) if (map_cfg.get("map_image_src") or map_cfg.get("image")) else ft.Container()),
                                                        *point_markers,
                                                    ],
                                                    expand=True,
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                                ft.Text("Punkt antippen zum Markieren. Danach mit Maus oder Finger gedrückt halten und direkt an die gewünschte Stelle ziehen.", size=12, color="#A8C0D2", text_align=ft.TextAlign.CENTER),
                            ],
                            spacing=10,
                        ),
                    ),
                    ft.Container(
                        width=390,
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Text("Maps", size=20, weight="bold", color="white"),
                                ft.Text("Vorlagen und eigene Hintergründe für diese Insel.", size=11, color="#A8C0D2") if editing_island_index is not None else ft.Container(),
                                ft.Container(height=220, content=ft.Column(map_cards, spacing=10, scroll=ft.ScrollMode.AUTO)),
                                _game_menu_button("Eigene Map hinzufügen", pick_custom_map, "#1D4ED8", width=280, height=40),
                                ft.Row([
                                    _game_menu_button("Pfadpunkt hinzufügen", add_point, "#0F766E", width=170, height=40),
                                    _game_menu_button("Punkt löschen", remove_point, "#7C2D12", width=130, height=40),
                                ], spacing=10),
                                ft.Divider(color="#243244"),
                                
                                # Punkt-Info Header
                                ft.Container(
                                    padding=ft.Padding(12, 10, 12, 10),
                                    border_radius=12,
                                    bgcolor="#0F1823",
                                    border=ft.border.Border.all(1, "#334155"),
                                    content=ft.Row(
                                        [
                                            ft.Container(
                                                width=40,
                                                height=40,
                                                border_radius=999,
                                                bgcolor="#0EA5E9",
                                                alignment=ft.Alignment(0, 0),
                                                content=ft.Text(str(point_index + 1), size=16, weight="bold", color="white")
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Text(active_point.get("label", ""), size=14, weight="bold", color="white"),
                                                    ft.Text(f"Punkt {point_index + 1}", size=11, color="#A8C0D2"),
                                                ],
                                                spacing=2,
                                                expand=True
                                            ),
                                        ],
                                        spacing=12,
                                    ),
                                ),
                                
                                ft.Divider(color="#243244"),
                                
                                ft.TextField(ref=map_title_ref, value=active_point.get("label", ""), label="Punktname", bgcolor="#111827", color="white", border_color="#334155"),
                                
                                ft.Divider(color="#243244", height=1),
                                
                                # Button um Modal zu öffnen
                                ft.ElevatedButton(
                                    "Frage bearbeiten",
                                    icon=ft.icons.EDIT,
                                    style=ft.ButtonStyle(
                                        bgcolor="#0EA5E9",
                                        color="white",
                                    ),
                                    width=280,
                                    height=44,
                                    on_click=lambda e: _open_question_editor_modal(page, state, point_index, points, current_questions),
                                ),
                                
                                # Fragen-Vorschau
                                ft.Container(
                                    padding=ft.Padding(12, 12, 12, 12),
                                    border_radius=12,
                                    bgcolor="#0F1823",
                                    border=ft.border.Border.all(1, "#334155"),
                                    content=ft.Column(
                                        [
                                            ft.Text("Fragen-Vorschau:", size=12, weight="bold", color="#A8C0D2"),
                                            ft.Text(
                                                active_question.get("question", "Keine Frage"),
                                                size=11, color="white", max_lines=3,
                                                overflow=ft.TextOverflow.ELLIPSIS
                                            ),
                                            ft.Divider(color="#334155", height=1),
                                            *[
                                                ft.Row(
                                                    [
                                                        ft.Checkbox(
                                                            value=ANSWER_LETTERS[i] in active_question.get("correct_answers", []),
                                                            disabled=True,
                                                            fill_color="#0EA5E9",
                                                        ),
                                                        ft.Text(
                                                            f"{ANSWER_LETTERS[i]}: " + active_answers[i],
                                                            size=10, color="white", expand=True,
                                                            overflow=ft.TextOverflow.ELLIPSIS,
                                                        ),
                                                    ],
                                                    spacing=8,
                                                )
                                                for i in range(4)
                                            ],
                                        ],
                                        spacing=8,
                                    ),
                                ),
                                
                                _game_menu_button("Speichern (Punkt)", save_point_details, "#0F766E", width=280, height=42),
                            ],
                            spacing=10,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ),
                ],
                expand=True,
            ),
        )
    )
    page.update()
    page.run_task(_sync_bg_music_async, page, state)


def start_questions_path_game(page: ft.Page, state: dict, map_key: str):
    profiles = get_questions_path_profiles(state)
    profile_index = get_questions_path_profile_index(state)
    profile = profiles[profile_index] if profile_index < len(profiles) else _questions_path_default_profile(profile_index)
    map_cfg = _questions_path_map_lookup_for_profile(profile, map_key)
    age = profile.get("selected_age", state.get("questions_path_age", "mid"))
    questions = build_questions_path_questions(age, map_key, state)
    visible_map_keys = [key for key, _cfg in _questions_path_maps_for_profile(profile)] or QUESTIONS_PATH_LEVEL_ORDER
    state["questions_path_game"] = {
        "map_key": map_key,
        "map_title": map_cfg.get("title", "Fragen-Pfad"),
        "age": age,
        "node_index": 0,
        "completed_nodes": [],
        "questions": questions,
        "game_finished": False,
        "checkpoint_index": 0,
        "current_hint": None,
        "current_level_index": visible_map_keys.index(map_key) if map_key in visible_map_keys else 0,
    }
    state["questions_path_age"] = age
    state.pop("_questions_path_active_node", None)
    state["questions_path_game"]["answer_feedback"] = None
    state["questions_path_scene"] = "level"
    save_questions_path_game(state)
    render_questions_path_game(page, state)


def resume_questions_path_game(page: ft.Page, state: dict, saved: dict | None = None):
    saved = saved or get_saved_questions_path_game(state)
    if not saved:
        show_questions_path_hub(page, state)
        return
    state["questions_path_game"] = {
        "map_key": saved.get("map_key", "waldpfad"),
        "map_title": saved.get("map_title", QUESTIONS_PATH_MAPS["waldpfad"]["title"]),
        "age": saved.get("age", "mid"),
        "node_index": int(saved.get("node_index", 0)),
        "completed_nodes": list(saved.get("completed_nodes", [])),
        "questions": [_path_question_to_dict(q) for q in saved.get("questions", [])],
        "game_finished": bool(saved.get("game_finished", False)),
        "checkpoint_index": int(saved.get("checkpoint_index", 0)),
        "current_hint": saved.get("current_hint"),
        "current_level_index": int(saved.get("current_level_index", 0)),
        "answer_feedback": None,
    }
    state["questions_path_scene"] = "level"
    state.pop("_questions_path_active_node", None)
    render_questions_path_game(page, state)


def render_questions_path_game(page: ft.Page, state: dict):
    scene = state.get("questions_path_scene") or "profiles"
    if scene == "islands":
        _questions_path_render_islands(page, state)
        return
    if scene == "custom_menu":
        _questions_path_render_custom_menu(page, state)
        return
    if scene == "level":
        _questions_path_render_level(page, state)
        return
    if scene == "editor":
        _questions_path_render_editor(page, state)
        return
    if scene == "complete":
        render_questions_path_complete(page, state)
        return
    _questions_path_render_profiles(page, state)


def show_questions_path_hub(page: ft.Page, state: dict):
    _set_resize_view(state, show_questions_path_hub)
    scene = state.get("questions_path_scene") or "profiles"
    if scene == "islands":
        _questions_path_render_islands(page, state)
    elif scene == "custom_menu":
        _questions_path_render_custom_menu(page, state)
    elif scene == "creator":
        _questions_path_render_creator(page, state)
    elif scene == "level":
        _questions_path_render_level(page, state)
    elif scene == "editor":
        _questions_path_render_editor(page, state)
    elif scene == "complete":
        render_questions_path_complete(page, state)
    else:
        state["questions_path_scene"] = "profiles"
        _questions_path_render_profiles(page, state)


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
        if path in ("/wwm", "/shop", "/achievements", "/daily"):
            on_route_change(None)
        app_state["_startup_recovering"] = False

    page.run_task(init_task)
    # Render a blank/loading screen immediately; init_task will replace it.
    open_main_menu(page, app_state)
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets", upload_dir="assets")
