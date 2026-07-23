import string
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, redirect, render_template
from flask_socketio import SocketIO, emit, join_room
import random, string, os, json, hashlib, time, smtplib, ssl
try:
    import psycopg2
except Exception:
    psycopg2 = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'codenamesvip'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
rooms = {}
MAX_PLAYERS = 10
OWNER_USERNAME = "yohanna"

Londres_I18N_SCRIPT = ""

USERS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "users.json")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

def db_enabled():
    return bool(DATABASE_URL) and psycopg2 is not None

def get_db_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    if not db_enabled():
        return
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                data JSONB NOT NULL
            )
        """)
        conn.commit()
        cur.close()
    finally:
        conn.close()

def load_users():
    if db_enabled():
        try:
            init_db()
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("SELECT username, data FROM users")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            users = {}
            for username, data in rows:
                if isinstance(data, str):
                    data = json.loads(data)
                users[username] = data or {}
            return users
        except Exception as e:
            print("DB load error, fallback users.json:", e, flush=True)

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    if db_enabled():
        try:
            init_db()
            conn = get_db_conn()
            cur = conn.cursor()
            for username, data in users.items():
                cur.execute(
                    """
                    INSERT INTO users (username, data)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (username)
                    DO UPDATE SET data = EXCLUDED.data
                    """,
                    (username, json.dumps(data, ensure_ascii=False))
                )
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception as e:
            print("DB save error, fallback users.json:", e, flush=True)

    data_dir = os.path.dirname(USERS_FILE)
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def find_user_key(users, username):
    username = (username or '').strip()
    for key in users.keys():
        if key.lower() == username.lower():
            return key
    return None

def verify_password(udata, password):
    if udata.get('password_hash') == hash_password(password):
        return True
    if udata.get('password') == password:
        udata['password_hash'] = hash_password(password)
        udata.pop('password', None)
        return True
    return False

def bootstrap_admin_user():
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        return
    users = load_users()
    key = find_user_key(users, OWNER_USERNAME)
    if not key:
        key = OWNER_USERNAME
        users[key] = {}
    users[key].update({
        "email": os.environ.get("ADMIN_EMAIL", "admin@montenoir.vip"),
        "password_hash": hash_password(admin_password),
        "chips": int(users[key].get("chips", 999999)),
        "wins": int(users[key].get("wins", 0)),
        "games": int(users[key].get("games", 0)),
        "avatar": users[key].get("avatar", "woman.png"),
        "avatarData": users[key].get("avatarData", ""),
        "nameColor": users[key].get("nameColor", "gold"),
        "avatarFrame": users[key].get("avatarFrame", "diamond"),
        "inventory": users[key].get("inventory", []),
        "membershipLabel": "ADMIN VIP",
        "membershipLevel": "admin",
        "isAdmin": True,
        "createdAt": users[key].get("createdAt", str(int(time.time())))
    })
    save_users(users)
    print("✅ Admin Yohanna prêt dans la base de données.", flush=True)

# ===== MONOPOLY CODE =====
METROPOLY_CELLS = [
    ("ALLEZ", "start", 0, 0, ""),
    ("Banque", "bank", 0, 0, ""),
    ("New York", "property", 220, 18, "green"),
    ("Monaco", "property", 200, 16, "green"),
    ("Aéroport International", "transport", 200, 25, "transport"),
    ("Londres", "property", 200, 16, "green"),
    ("Varsovie", "property", 100, 6, "brown"),
    ("Zurich", "property", 100, 6, "brown"),
    ("Prison", "jail", 0, 0, ""),
    ("Paris", "property", 160, 12, "orange"),
    ("Milan", "property", 140, 10, "orange"),
    ("Amsterdam", "property", 140, 10, "orange"),
    ("Compagnies des Eaux", "utility", 100, 0, "utility"),
    ("Moscou", "property", 120, 8, "purple"),
    ("Rome", "property", 100, 6, "purple"),
    ("Madrid", "property", 100, 6, "purple"),
    ("Impôts", "tax", 0, 0, ""),
    ("Sofia", "property", 60, 4, "yellow"),
    ("Belgrad", "property", 70, 4, "yellow"),
    ("Gare Grande Vitesse", "transport", 100, 25, "transport"),
    ("Istanbul", "property", 70, 4, "yellow"),
    ("Prague", "property", 80, 5, "blue"),
    ("Lisbonne", "property", 90, 5, "blue"),
    ("Enchères", "auction", 0, 0, ""),
    ("Dubaï", "property", 160, 12, "red"),
    ("Pékin", "property", 160, 12, "red"),
    ("Compagnie Électrique", "utility", 150, 0, "utility"),
    ("Tokyo", "property", 180, 14, "red")
]

METROPOLY_ROOMS = {}
METROPOLY_TOKENS = ["🎩", "🚗", "🐕", "🚀", "⚓", "💎"]
GRID_POS = [
    (50, 95), (50, 85), (50, 75), (50, 65), (50, 55), (50, 45), (50, 35), (50, 25),
    (60, 5), (70, 5), (80, 5), (90, 5), (100, 5),
    (100, 15), (100, 25), (100, 35), (100, 45), (100, 55), (100, 65), (100, 75), (100, 85),
    (90, 95), (80, 95), (70, 95), (60, 95)
]

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
        "lastLog": f"{u} crée la partie.",
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
    if not u: emit("monopoly_error", {"msg": "Nom vide."}); return
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
    if c not in METROPOLY_ROOMS: emit("monopoly_error", {"msg": "Oda bulunamadı."}); return
    r = METROPOLY_ROOMS[c]
    if u in r["players"]: emit("monopoly_error", {"msg": "İsim kullanımda."}); return
    r["players"][u] = {"position": 0, "money": 1500, "properties": [], "jailed": 0, "token": token, "bankrupt": False, "hasRolled": False}
    join_room(c)
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_start_game")
def ms(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    r = METROPOLY_ROOMS.get(c)
    if not r: return
    r["started"] = True
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_roll_dice")
def mr(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    u = (data or {}).get("username", "").strip()
    r = METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]: emit("monopoly_error", {"msg": "Oda/oyuncu yok."}); return
    names = [n for n, p in r["players"].items() if not p.get("bankrupt")]
    if u != names[r["turnIndex"] % len(names)]: emit("monopoly_error", {"msg": "Sıra sende değil."}); return
    p = r["players"][u]
    if p.get("hasRolled"):
        emit("monopoly_error", {"msg": "Tu as déjà lancé les dés. Termine ton tour."}); return
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    d = d1 + d2
    is_double_six = (d1 == 6 and d2 == 6)
    old = p["position"]
    new = (old + d) % len(METROPOLY_CELLS)
    if new < old: p["money"] += 200
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
            log += f" {owner} sahibine {pay}€ kira ödedi."
        elif not owner: pending = True; log += f" Satın alınabilir: {price}€."
    elif typ == "tax": p["money"] -= 200; log += " Vergi: -200€."
    elif typ == "bank": b = random.choice([50, 75, 100, 150]); p["money"] += b; log += f" Banka: +{b}€."
    elif typ == "bonus": b = random.choice([-50, 50, 100, 150]); p["money"] += b; log += f" Enchères: {b}€."
    elif typ == "jail": p["jailed"] = 1; log += " Prison."
    if p["money"] < 0: p["bankrupt"] = True; log += " İflas."
    p["hasRolled"] = not is_double_six
    if is_double_six:
        log += " Double 6 : tu rejoues !"
    r["lastDice"] = d
    r["lastLog"] = log
    emit("monopoly_animate_move", {"username": u, "from": old, "to": new, "dice1": d1, "dice2": d2, "dice": d, "state": m_public(r), "pendingBuy": pending}, room=c)

@socketio.on("monopoly_end_turn")
def me(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    r = METROPOLY_ROOMS.get(c)
    if not r: return
    names = [n for n, p in r["players"].items() if not p.get("bankrupt")]
    if names:
        r["turnIndex"] = (r["turnIndex"] + 1) % len(names)
        next_player = names[r["turnIndex"]]
        r["players"][next_player]["hasRolled"] = False
        r["lastLog"] = "Sıra: " + next_player
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_buy_property")
def mb(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    u = (data or {}).get("username", "").strip()
    r = METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]: return
    p = r["players"][u]
    pos = p["position"]
    name, typ, price, rent, grp = METROPOLY_CELLS[pos]
    if typ not in ["property", "transport", "utility"] or str(pos) in r["owners"] or p["money"] < price: emit("monopoly_error", {"msg": "Satın alınamaz."}); return
    p["money"] -= price
    r["owners"][str(pos)] = u
    r["lastLog"] = f"{u}, {name} aldı."
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_add_house")
def monopoly_add_house(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    u = (data or {}).get("username", "").strip()
    cell = str((data or {}).get("cell", ""))
    r = METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        return
    r.setdefault("houses", {})
    r.setdefault("hotels", {})
    if r.get("owners", {}).get(cell) != u:
        emit("monopoly_error", {"msg": "Bu mülk senin değil."})
        return
    if r["hotels"].get(cell):
        emit("monopoly_error", {"msg": "Bu mülkte zaten otel var."})
        return
    count = int(r["houses"].get(cell, 0))
    if count >= 4:
        emit("monopoly_error", {"msg": "4 evden sonra otel almalısın."})
        return
    if r["players"][u]["money"] < 50:
        emit("monopoly_error", {"msg": "Ev için para yetmiyor."})
        return
    r["players"][u]["money"] -= 50
    r["houses"][cell] = count + 1
    r["lastLog"] = u + " ev aldı."
    emit("monopoly_room_state", m_public(r), room=c)

@socketio.on("monopoly_chat")
def monopoly_chat(data):
    c = ((data or {}).get("code", "") or "").strip().upper()
    u = (data or {}).get("username", "").strip() or "Oyuncu"
    msg = (data or {}).get("message", "").strip()
    if c and msg:
        emit("monopoly_chat_message", {"username": u, "message": msg}, room=c)

# ===== ROUTES WITH PROPER PAGES =====

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/games")
def games():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🎮 Jeux Montenoir VIP</title>
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            html,body{background:#050505;color:#d4af37;font-family:Georgia,serif;min-height:100vh}
            .wrap{max-width:1200px;margin:0 auto;padding:40px 20px}
            header{text-align:center;margin-bottom:50px}
            h1{font-size:48px;letter-spacing:3px;text-shadow:0 0 20px #d4af37;margin-bottom:10px}
            .back{display:inline-block;margin-top:20px;padding:12px 24px;background:#d4af37;color:#050505;text-decoration:none;border-radius:10px;font-weight:bold}
            .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}
            .card{text-decoration:none;color:#050505;padding:30px 20px;border-radius:15px;background:linear-gradient(145deg,#fff4b0,#d4af37 50%,#8a6a1f);border:2px solid #fff0a8;box-shadow:0 0 20px rgba(212,175,55,.7);transition:.3s;text-align:center}
            .card:hover{transform:translateY(-8px);box-shadow:0 0 35px rgba(212,175,55,1)}
            .emoji{font-size:48px;margin-bottom:10px}
            .name{font-weight:bold;font-size:16px}
        </style>
    </head>
    <body>
        <div class="wrap">
            <header>
                <h1>🎮 JEUX MONTENOIR</h1>
                <p style="font-size:18px;margin-top:10px">Choisis ton jeu et démolis tes adversaires!</p>
            </header>
            <div class="grid">
                <a href="/metropoly" class="card">
                    <div class="emoji">🏛️</div>
                    <div class="name">METROPOLY LUXE</div>
                </a>
                <a href="#" class="card" style="opacity:0.6;cursor:not-allowed">
                    <div class="emoji">♠️</div>
                    <div class="name">POKER</div>
                    <div style="font-size:12px;margin-top:5px">(Bientôt)</div>
                </a>
                <a href="#" class="card" style="opacity:0.6;cursor:not-allowed">
                    <div class="emoji">🎲</div>
                    <div class="name">TAVLA</div>
                    <div style="font-size:12px;margin-top:5px">(Bientôt)</div>
                </a>
                <a href="#" class="card" style="opacity:0.6;cursor:not-allowed">
                    <div class="emoji">🀄</div>
                    <div class="name">OKEY</div>
                    <div style="font-size:12px;margin-top:5px">(Bientôt)</div>
                </a>
                <a href="#" class="card" style="opacity:0.6;cursor:not-allowed">
                    <div class="emoji">🎯</div>
                    <div class="name">CODENAMES</div>
                    <div style="font-size:12px;margin-top:5px">(Bientôt)</div>
                </a>
                <a href="#" class="card" style="opacity:0.6;cursor:not-allowed">
                    <div class="emoji">🎳</div>
                    <div class="name">BOWLING</div>
                    <div style="font-size:12px;margin-top:5px">(Bientôt)</div>
                </a>
            </div>
            <a href="/" class="back">← Retour accueil</a>
        </div>
    </body>
    </html>
    """)

@app.route("/metropoly")
def metropoly():
    return render_template("metropoly.html")

@app.route("/register")
def register_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>📝 Inscription</title>
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            html,body{background:#050505;color:#d4af37;font-family:Georgia,serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
            .form-box{background:linear-gradient(180deg,rgba(0,0,0,.8),rgba(0,0,0,.6));border:2px solid #d4af37;border-radius:15px;padding:40px;max-width:400px;width:100%;box-shadow:0 0 30px rgba(212,175,55,.5)}
            h1{text-align:center;font-size:36px;margin-bottom:30px;text-shadow:0 0 10px #d4af37}
            .form-group{margin-bottom:20px}
            label{display:block;margin-bottom:8px;font-weight:bold;font-size:14px}
            input{width:100%;padding:12px;border:1px solid #d4af37;border-radius:8px;background:#0d0d0d;color:#d4af37;font-size:14px}
            input:focus{outline:none;box-shadow:0 0 10px rgba(212,175,55,.7)}
            button{width:100%;padding:14px;background:linear-gradient(180deg,#d4af37,#8a6a1f);color:#050505;border:none;border-radius:8px;font-weight:bold;font-size:16px;cursor:pointer;margin-top:20px}
            button:hover{box-shadow:0 0 15px rgba(212,175,55,.9)}
            .link{text-align:center;margin-top:20px;font-size:14px}
            .link a{color:#d4af37;text-decoration:none}
            .link a:hover{text-decoration:underline}
            .back{display:inline-block;margin-top:20px;padding:10px 16px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold;font-size:12px}
        </style>
    </head>
    <body>
        <div class="form-box">
            <h1>📝 Inscription</h1>
            <form method="POST" action="/api/register">
                <div class="form-group">
                    <label for="username">Nom d'utilisateur</label>
                    <input type="text" id="username" name="username" required placeholder="Yohanna">
                </div>
                <div class="form-group">
                    <label for="email">Email</label>
                    <input type="email" id="email" name="email" required placeholder="email@exemple.com">
                </div>
                <div class="form-group">
                    <label for="password">Mot de passe</label>
                    <input type="password" id="password" name="password" required placeholder="••••••••">
                </div>
                <div class="form-group">
                    <label for="password2">Confirmer le mot de passe</label>
                    <input type="password" id="password2" name="password2" required placeholder="••••••••">
                </div>
                <button type="submit">S'inscrire</button>
            </form>
            <div class="link">
                Déjà inscrit? <a href="/login">Se connecter</a>
            </div>
            <a href="/" class="back">← Accueil</a>
        </div>
    </body>
    </html>
    """)

@app.route("/login")
def login_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>👤 Connexion</title>
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            html,body{background:#050505;color:#d4af37;font-family:Georgia,serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
            .form-box{background:linear-gradient(180deg,rgba(0,0,0,.8),rgba(0,0,0,.6));border:2px solid #d4af37;border-radius:15px;padding:40px;max-width:400px;width:100%;box-shadow:0 0 30px rgba(212,175,55,.5)}
            h1{text-align:center;font-size:36px;margin-bottom:30px;text-shadow:0 0 10px #d4af37}
            .form-group{margin-bottom:20px}
            label{display:block;margin-bottom:8px;font-weight:bold;font-size:14px}
            input{width:100%;padding:12px;border:1px solid #d4af37;border-radius:8px;background:#0d0d0d;color:#d4af37;font-size:14px}
            input:focus{outline:none;box-shadow:0 0 10px rgba(212,175,55,.7)}
            button{width:100%;padding:14px;background:linear-gradient(180deg,#d4af37,#8a6a1f);color:#050505;border:none;border-radius:8px;font-weight:bold;font-size:16px;cursor:pointer;margin-top:20px}
            button:hover{box-shadow:0 0 15px rgba(212,175,55,.9)}
            .link{text-align:center;margin-top:20px;font-size:14px}
            .link a{color:#d4af37;text-decoration:none}
            .link a:hover{text-decoration:underline}
            .back{display:inline-block;margin-top:20px;padding:10px 16px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold;font-size:12px}
        </style>
    </head>
    <body>
        <div class="form-box">
            <h1>👤 Connexion</h1>
            <form method="POST" action="/api/login">
                <div class="form-group">
                    <label for="username">Nom d'utilisateur</label>
                    <input type="text" id="username" name="username" required placeholder="Yohanna">
                </div>
                <div class="form-group">
                    <label for="password">Mot de passe</label>
                    <input type="password" id="password" name="password" required placeholder="••••••••">
                </div>
                <button type="submit">Se connecter</button>
            </form>
            <div class="link">
                Pas encore inscrit? <a href="/register">S'inscrire</a>
            </div>
            <a href="/" class="back">← Accueil</a>
        </div>
    </body>
    </html>
    """)

@app.route("/premium")
def premium_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>💎 Premium</title>
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            html,body{background:#050505;color:#d4af37;font-family:Georgia,serif;min-height:100vh}
            .wrap{max-width:1000px;margin:0 auto;padding:50px 20px;text-align:center}
            h1{font-size:48px;margin-bottom:30px;text-shadow:0 0 20px #d4af37}
            .box{background:linear-gradient(180deg,rgba(0,0,0,.8),rgba(0,0,0,.6));border:2px solid #d4af37;border-radius:15px;padding:40px;margin:20px 0}
            .features{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin:30px 0}
            .feature{padding:20px;background:#0d0d0d;border:1px solid #d4af37;border-radius:10px}
            .emoji{font-size:32px;margin-bottom:10px}
            button{padding:14px 30px;background:linear-gradient(180deg,#d4af37,#8a6a1f);color:#050505;border:none;border-radius:8px;font-weight:bold;font-size:16px;cursor:pointer;margin-top:20px}
            button:hover{box-shadow:0 0 15px rgba(212,175,55,.9)}
            .back{display:inline-block;margin-top:20px;padding:10px 16px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold;font-size:12px}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>💎 MONTENOIR PREMIUM</h1>
            <div class="box">
                <p style="font-size:18px">Déverrouille un monde de possibilités illimitées!</p>
                <div class="features">
                    <div class="feature">
                        <div class="emoji">♾️</div>
                        <div>Jeux illimités</div>
                    </div>
                    <div class="feature">
                        <div class="emoji">🎁</div>
                        <div>Bonus quotidiens</div>
                    </div>
                    <div class="feature">
                        <div class="emoji">⭐</div>
                        <div>Status VIP</div>
                    </div>
                    <div class="feature">
                        <div class="emoji">💰</div>
                        <div>Plus de jetons</div>
                    </div>
                </div>
                <button onclick="alert('Premium bientôt disponible!')">Devenir Premium</button>
            </div>
            <a href="/" class="back">← Accueil</a>
        </div>
    </body>
    </html>
    """)

if __name__ == "__main__":
    import sys, traceback
    try:
        init_db()
        bootstrap_admin_user()
    except:
        pass
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Londres VIP on port {port}", flush=True)
    try:
        socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        raise
