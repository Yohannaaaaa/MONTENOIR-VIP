import string, os, json, hashlib, time, random
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, render_template
from flask_socketio import SocketIO, emit, join_room
try:
    import psycopg2
except:
    psycopg2 = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'codenamesvip'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

USERS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "users.json")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

def db_enabled():
    return bool(DATABASE_URL) and psycopg2 is not None

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    if not db_enabled():
        return
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, data JSONB NOT NULL)")
        conn.commit()
        cur.close()
        conn.close()
    except:
        pass

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except:
        pass

# ===== MONOPOLY CODE =====
METROPOLY_CELLS = [
    ("ALLEZ", "start", 0, 0, ""),
    ("Banque", "bank", 0, 0, ""),
    ("New York", "property", 220, 18, "green"),
    ("Monaco", "property", 200, 16, "green"),
    ("Aeroport", "transport", 200, 25, "transport"),
    ("Londres", "property", 200, 16, "green"),
    ("Varsovie", "property", 100, 6, "brown"),
    ("Zurich", "property", 100, 6, "brown"),
    ("Prison", "jail", 0, 0, ""),
    ("Paris", "property", 160, 12, "orange"),
    ("Milan", "property", 140, 10, "orange"),
    ("Amsterdam", "property", 140, 10, "orange"),
    ("Eau", "utility", 100, 0, "utility"),
    ("Moscou", "property", 120, 8, "purple"),
    ("Rome", "property", 100, 6, "purple"),
    ("Madrid", "property", 100, 6, "purple"),
    ("Impots", "tax", 0, 0, ""),
    ("Sofia", "property", 60, 4, "yellow"),
    ("Belgrad", "property", 70, 4, "yellow"),
    ("Gare", "transport", 100, 25, "transport"),
    ("Istanbul", "property", 70, 4, "yellow"),
    ("Prague", "property", 80, 5, "blue"),
    ("Lisbonne", "property", 90, 5, "blue"),
    ("Encheres", "auction", 0, 0, ""),
    ("Dubai", "property", 160, 12, "red"),
    ("Pekin", "property", 160, 12, "red"),
    ("Electricite", "utility", 150, 0, "utility"),
    ("Tokyo", "property", 180, 14, "red")
]

METROPOLY_ROOMS = {}
METROPOLY_TOKENS = ["🎩", "🚗", "🐕", "🚀", "⚓", "💎"]

def m_code():
    return "MON-" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=4))

def m_room(c, u):
    return {
        "code": c,
        "players": {u: {"position": 0, "money": 1500, "properties": [], "jailed": 0, "token": random.choice(METROPOLY_TOKENS), "bankrupt": False, "hasRolled": False}},
        "turnIndex": 0,
        "owners": {},
        "houses": {},
        "hotels": {},
        "lastDice": 0,
        "lastLog": f"{u} cree la partie.",
        "started": False
    }

def m_public(r):
    return {
        "code": r["code"],
        "players": r["players"],
        "owners": r["owners"],
        "houses": r["houses"],
        "hotels": r["hotels"],
        "lastLog": r["lastLog"],
        "started": r["started"],
        "turnIndex": r["turnIndex"]
    }

@socketio.on("monopoly_create_room")
def mc(data):
    u = (data or {}).get("username", "").strip()
    token = (data or {}).get("token", "🎩").strip()
    if not u:
        emit("monopoly_error", {"msg": "Nom vide."})
        return
    c = m_code()
    r = m_room(c, u)
    r["players"][u]["token"] = token
    METROPOLY_ROOMS[c] = r
    join_room(c)
    emit("monopoly_room_state", m_public(r))

@socketio.on("monopoly_join_room")
def mj(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    u = (data or {}).get("username", "").strip()
    token = (data or {}).get("token", "🎩").strip()
    if c not in METROPOLY_ROOMS:
        emit("monopoly_error", {"msg": "Oda bulunamadi."})
        return
    r = METROPOLY_ROOMS[c]
    if u in r["players"]:
        emit("monopoly_error", {"msg": "Isim kullanimda."})
        return
    r["players"][u] = {"position": 0, "money": 1500, "properties": [], "jailed": 0, "token": token, "bankrupt": False, "hasRolled": False}
    join_room(c)
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_start_game")
def ms(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    r = METROPOLY_ROOMS.get(c)
    if not r:
        return
    r["started"] = True
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_roll_dice")
def mr(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    u = (data or {}).get("username", "").strip()
    r = METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        emit("monopoly_error", {"msg": "Oda/oyuncu yok."})
        return
    names = [n for n, p in r["players"].items() if not p.get("bankrupt")]
    if u != names[r["turnIndex"] % len(names)]:
        emit("monopoly_error", {"msg": "Sira sende degil."})
        return
    p = r["players"][u]
    if p.get("hasRolled"):
        emit("monopoly_error", {"msg": "Tu as deja lance les des."})
        return
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    d = d1 + d2
    is_double_six = (d1 == 6 and d2 == 6)
    old = p["position"]
    new = (old + d) % len(METROPOLY_CELLS)
    if new < old:
        p["money"] += 200
    p["position"] = new
    name, typ, price, rent, grp = METROPOLY_CELLS[new]
    log = f"{u} a fait {d1} et {d2} ({d}). {name}."
    pending = False
    if typ in ["property", "transport", "utility"]:
        owner = r["owners"].get(str(new))
        if owner and owner != u:
            pay = rent + int(r["houses"].get(str(new), 0)) * 15
            p["money"] -= pay
            r["players"][owner]["money"] += pay
            log += f" {owner} sahibine {pay} euro kira odedi."
        elif not owner:
            pending = True
            log += f" Satilabilir: {price} euro."
    elif typ == "tax":
        p["money"] -= 200
        log += " Vergi: -200 euro."
    elif typ == "bank":
        b = random.choice([50, 75, 100, 150])
        p["money"] += b
        log += f" Banka: +{b} euro."
    if p["money"] < 0:
        p["bankrupt"] = True
        log += " Iflas."
    p["hasRolled"] = not is_double_six
    if is_double_six:
        log += " Double 6: tu rejoues!"
    r["lastDice"] = d
    r["lastLog"] = log
    emit("monopoly_animate_move", {"username": u, "from": old, "to": new, "dice1": d1, "dice2": d2, "dice": d, "state": m_public(r), "pendingBuy": pending}, room=c)

@socketio.on("monopoly_end_turn")
def me(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    r = METROPOLY_ROOMS.get(c)
    if not r:
        return
    names = [n for n, p in r["players"].items() if not p.get("bankrupt")]
    if names:
        r["turnIndex"] = (r["turnIndex"] + 1) % len(names)
        next_player = names[r["turnIndex"]]
        r["players"][next_player]["hasRolled"] = False
        r["lastLog"] = "Sira: " + next_player
    emit("monopoly_room_state", m_public(r), room=c)

# ===== ROUTES =====

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/metropoly")
def metropoly():
    return render_template("metropoly.html")

@app.route("/codenames")
def codenames():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Codenames VIP</title></head>
    <body style="margin:0;background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px">
        <h1 style="font-size:48px">Codenames VIP</h1>
        <p style="font-size:18px">Jeu de mots en equipe - Bientot disponible</p>
        <a href="/games" style="display:inline-block;margin-top:30px;padding:14px 30px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold">← Retour aux jeux</a>
    </body>
    </html>
    """)

@app.route("/games")
def games():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Jeux</title></head>
    <body style="margin:0;background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px">
        <h1 style="font-size:48px">Jeux Montenoir</h1>
        <div style="margin-top:40px">
            <a href="/metropoly" style="display:inline-block;margin:10px;padding:20px 40px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold;font-size:18px">Metropoly Luxe</a>
            <a href="/codenames" style="display:inline-block;margin:10px;padding:20px 40px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold;font-size:18px">Codenames VIP</a>
        </div>
        <a href="/" style="display:inline-block;margin-top:30px;padding:10px 20px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold">← Accueil</a>
    </body>
    </html>
    """)

@app.route("/register")
def register():
    return render_template_string("<h1>Inscription</h1><a href='/'>Retour</a>")

@app.route("/login")
def login():
    return render_template_string("<h1>Connexion</h1><a href='/'>Retour</a>")

@app.route("/premium")
def premium():
    return render_template_string("<h1>Premium</h1><a href='/'>Retour</a>")

if __name__ == "__main__":
    import sys, traceback
    try:
        init_db()
    except:
        pass
    port = int(os.environ.get("PORT", 10000))
    print(f"Londres VIP on port {port}", flush=True)
    try:
        socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        raise
