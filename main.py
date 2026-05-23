import flet as ft
import asyncio
import random
import json
import os
import time
import re
import smtplib
import ssl
from email.message import EmailMessage

# ---------- Persistent Database ----------
DB_FILE = "user_data.json"
ENV_FILE = ".env"
CODE_REQUEST_COOLDOWN_SECONDS = 10


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

def update_game_stats(correct: int, answered: int, money: str, money_level_idx: int, email: str | None = None):
    db = load_db()
    
    # 1. Update Global Stats
    g = db["global_stats"]
    g["games_played"] += 1
    g["correct_answers"] += correct
    g["questions_answered"] += answered
    if money_level_idx > g.get("highest_money_level", -1):
        g["highest_money"] = money
        g["highest_money_level"] = money_level_idx
        
    # 2. Update Personal Stats if logged in
    if email and email in db["users"]:
        u = db["users"][email]["stats"]
        u["games_played"] += 1
        u["correct_answers"] += correct
        u["questions_answered"] += answered
        if money_level_idx > u.get("highest_money_level", -1):
            u["highest_money"] = money
            u["highest_money_level"] = money_level_idx
            
    save_db(db)

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

QUESTIONS_PER_LEVEL = 100


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


def _young_question(level_idx: int, variant: int) -> tuple:
    level = level_idx + 1
    n = variant + 1
    kind = variant % 10
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
    value = (level * 10) + (n % 10)
    return _number_question(f"Welche Zahl ist um 1 größer als {value}?", value + 1, 2)


def _mid_question(level_idx: int, variant: int) -> tuple:
    level = level_idx + 1
    n = variant + 1
    kind = variant % 10

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
    fractions = [(1, 2, "die Hälfte"), (1, 4, "ein Viertel"), (3, 4, "drei Viertel")]
    numerator, denominator, label = fractions[(level + n) % len(fractions)]
    amount = denominator * (n % 20 + 5)
    correct = amount * numerator // denominator
    return _number_question(f"Wie viel ist {label} von {amount}?", correct, 4)


def _hard_question(level_idx: int, variant: int) -> tuple:
    level = level_idx + 1
    n = variant + 1
    kind = variant % 10

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
    value = (level + n % 15) * 6
    correct = value // 3 + level
    return _number_question(f"Was ist ein Drittel von {value} plus {level}?", correct, 4)


def build_level_question_bank(age: str) -> list[list[tuple]]:
    builders = {
        "young": _young_question,
        "mid": _mid_question,
        "old": _hard_question,
    }
    builder = builders.get(age, _mid_question)
    return [
        [builder(level_idx, variant) for variant in range(QUESTIONS_PER_LEVEL)]
        for level_idx in range(len(MONEY_LEVELS))
    ]


def create_game_questions(age: str) -> list[tuple]:
    bank = build_level_question_bank(age)
    questions = []
    for level_questions in bank:
        questions.append(random.choice(level_questions))
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
    email = state.get("current_user_email")
    if email and email in db["users"]:
        username = db["users"][email].get("name", email)
        greeting = f"Hallo, {username}! 👋"
        logged_in = True
    else:
        greeting = "Hallo, Gast! 👋"
        logged_in = False

    def on_logout(e):
        state["current_user_email"] = None
        open_main_menu(e.page, state)

    def resume_game(e):
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

    menu_buttons = []
    if logged_in and db["users"][email].get("saved_game"):
        menu_buttons.append(
            _menu_button("▶️  Spiel fortsetzen", resume_game, "#2ECC71")
        )
    menu_buttons.append(
        _menu_button("🎮  Spiel starten",
                     lambda e: start_new_game(e.page, state), "#F4A460")
    )
    menu_buttons.append(
        _menu_button("📊  Statistiken",
                     lambda e: show_stats(e.page, state), "#9B59B6")
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
            bgcolor="#1A0A30",
            shadow=ft.BoxShadow(blur_radius=40, color="#80FFD700"),
            border=ft.border.Border.all(3, "#FFD700"),
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
            colors=["#2C1654", "#6B2FA0", "#C2185B"],
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


# ---------- Age Selection ----------
def start_new_game(page: ft.Page, state: dict):
    """Reset state and ask for age group."""
    state.update({
        "money": "0 €",
        "questions_answered": 0,
        "correct": 0,
        "jokers_used": 0,
        "question_index": 0,
        "questions": [],
    })

    def choose_age(e: ft.ControlEvent):
        age = e.control.data
        state["questions"] = create_game_questions(age)
        show_next_question(page, state)

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
                _show_correct_screen(page, state)
            else:
                state["questions_answered"] += 1
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
                bgcolor="#C2185B",
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
                colors=["#2C1654", "#6B2FA0", "#C2185B"],
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
        state["question_index"] += 1
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
    # Update persistent stats
    correct = state.get("correct", 0)
    answered = state.get("questions_answered", 0)
    money = state.get("money", "0 €")
    money_idx = -1
    if money in MONEY_LEVELS:
        money_idx = MONEY_LEVELS.index(money)
    update_game_stats(correct, answered, money, money_idx, state.get("current_user_email"))

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
    # Update persistent stats
    correct = state.get("correct", 0)
    answered = state.get("questions_answered", 0)
    money = state.get("money", "0 €")
    money_idx = -1
    if money in MONEY_LEVELS:
        money_idx = MONEY_LEVELS.index(money)
    update_game_stats(correct, answered, money, money_idx, state.get("current_user_email"))

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
def show_login_view(page: ft.Page, state: dict):
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
                "stats": {
                    "games_played": 0,
                    "correct_answers": 0,
                    "questions_answered": 0,
                    "highest_money": "0 €",
                    "highest_money_level": -1
                }
            }
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


def show_edit_profile_view(page: ft.Page, state: dict):
    db = load_db()
    email = state.get("current_user_email")
    if not email:
        open_main_menu(page, state)
        return
        
    user_info = db["users"].get(email, {})
    current_name = user_info.get("name", "")
    
    name_input = ft.TextField(
        label="Dein Anzeigename",
        value=current_name,
        width=300,
        bgcolor="#1A0A30",
        border_color="#9B59B6",
        color="white",
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
            save_db(db)
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
                colors=["#2C1654", "#6B2FA0", "#C2185B"],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Column([
                ft.Text("✏️ Profil bearbeiten", size=30, weight="bold", color="white"),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"Konto: {email}", size=13, color="#E0D0F0"),
                        name_input,
                        ft.Container(
                            content=ft.Text("Speichern", size=16, weight="bold", color="white"),
                            on_click=on_save,
                            bgcolor="#2ECC71",
                            border_radius=30,
                            padding=ft.Padding(30, 12, 30, 12),
                            alignment=ft.Alignment(0, 0),
                            width=150,
                        ),
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
def show_stats(page: ft.Page, state: dict):
    db = load_db()
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
            ft.Text("🌍 Globale Statistik", size=18, weight="bold", color="#FFD700"),
            ft.Divider(color="#9B59B6", thickness=1),
            _stat_row("🎮 Spiele gesamt", str(g_games)),
            _stat_row("📝 Beantwortete Fragen", str(g_answered)),
            _stat_row("✅ Richtige Antworten", f"{g_correct} ({g_rate})"),
            _stat_row("🏆 Höchster Gewinn", g_money),
        ], spacing=12),
        bgcolor="#1A0A30",
        border_radius=16,
        padding=20,
        border=ft.border.Border.all(2, "#9B59B6"),
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
            bgcolor="#1A0A30",
            border_radius=16,
            padding=20,
            border=ft.border.Border.all(2, "#2ECC71"),
            width=card_width,
        )
    else:
        personal_card = ft.Container(
            content=ft.Column([
                ft.Text("👤 Persönliche Statistik", size=18, weight="bold", color="#CCCCCC"),
                ft.Divider(color="#CCCCCC", thickness=1),
                ft.Text(
                    "Melde dich an, um deine persönlichen Statistiken dauerhaft zu sichern!",
                    size=13,
                    color="#CCCCCC",
                    text_align="center",
                ),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Text("🔑 Anmelden", size=16, weight="bold", color="white"),
                    on_click=lambda e: show_login_view(e.page, state),
                    bgcolor="#9B59B6",
                    border_radius=30,
                    padding=ft.Padding(30, 12, 30, 12),
                    alignment=ft.Alignment(0, 0),
                    width=200,
                ),
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="#1A0A30",
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
                colors=["#2C1654", "#6B2FA0", "#C2185B"],
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
                    bgcolor="#9B59B6",
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
    }

    page.title = "Wer wird Millionär?"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#2C1654"
    page.padding = 0
    page.window.width = 1100
    page.window.height = 680
    page.add(build_welcome_view(page, app_state))
    page.update()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
