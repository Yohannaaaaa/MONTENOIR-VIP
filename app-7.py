import os, json, hashlib, time, random, string
from flask import Flask, render_template, render_template_string, request, redirect
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'codenamesvip'
socketio = SocketIO(app, cors_allowed_origins='*')

# Database
USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def init_db():
    if not os.path.exists(USERS_FILE):
        save_users({})

def bootstrap_admin_user():
    users = load_users()
    if 'admin' not in users:
        users['admin'] = {'password_hash': hash_password('admin'), 'email': 'admin@montenoir.vip'}
        save_users(users)

# ===== MONOPOLY =====
MONOPOLY_ROOMS = {}

def m_code():
    return "MON-" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=4))

@socketio.on("monopoly_create_room")
def create_room(data):
    username = (data or {}).get("username", "").strip()
    token = (data or {}).get("token", "🎩")
    if not username:
        emit("monopoly_error", {"msg": "Pseudo requis"})
        return
    code = m_code()
    MONOPOLY_ROOMS[code] = {
        "code": code,
        "players": {username: {"position": 0, "money": 1500, "token": token, "hasRolled": False}},
        "started": False
    }
    join_room(code)
    emit("monopoly_room_state", {
        "code": code,
        "players": MONOPOLY_ROOMS[code]["players"],
        "started": False
    })

@socketio.on("monopoly_join_room")
def join_room_monopoly(data):
    code = ((data or {}).get("code", "") or "").strip().upper()
    username = (data or {}).get("username", "").strip()
    token = (data or {}).get("token", "🎩")
    
    if code not in MONOPOLY_ROOMS:
        emit("monopoly_error", {"msg": "Salle introuvable"})
        return
    
    room = MONOPOLY_ROOMS[code]
    if username in room["players"]:
        emit("monopoly_error", {"msg": "Pseudo déjà utilisé"})
        return
    
    room["players"][username] = {"position": 0, "money": 1500, "token": token, "hasRolled": False}
    join_room(code)
    emit("monopoly_room_state", {
        "code": code,
        "players": room["players"],
        "started": room["started"]
    }, room=code)

@socketio.on("monopoly_start_game")
def start_game(data):
    code = ((data or {}).get("code", "") or "").strip().upper()
    if code in MONOPOLY_ROOMS:
        MONOPOLY_ROOMS[code]["started"] = True
        emit("monopoly_room_state", {
            "code": code,
            "players": MONOPOLY_ROOMS[code]["players"],
            "started": True
        }, room=code)

@socketio.on("monopoly_roll_dice")
def roll_dice(data):
    code = ((data or {}).get("code", "") or "").strip().upper()
    username = (data or {}).get("username", "").strip()
    
    if code not in MONOPOLY_ROOMS:
        return
    
    room = MONOPOLY_ROOMS[code]
    if username not in room["players"]:
        return
    
    player = room["players"][username]
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    old_pos = player["position"]
    new_pos = (old_pos + d1 + d2) % 28
    player["position"] = new_pos
    
    emit("monopoly_animate_move", {
        "username": username,
        "from": old_pos,
        "to": new_pos,
        "dice1": d1,
        "dice2": d2
    }, room=code)

# ===== ROUTES =====

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/metropoly")
@app.route("/monopoly")
def metropoly():
    return render_template("metropoly.html")

@app.route("/codenames")
def codenames():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Codenames VIP</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}
    a{display:inline-block;margin-top:30px;padding:14px 30px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold}</style>
    </head><body>
    <h1 style="font-size:48px;letter-spacing:3px">🎯 CODENAMES VIP</h1>
    <p style="font-size:18px">Jeu de mots en équipe</p>
    <a href="/">← ACCUEIL</a>
    </body></html>'''
    return render_template_string(html)

@app.route("/tarot")
def tarot():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Tarot VIP</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}
    a{display:inline-block;margin-top:30px;padding:14px 30px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold}</style>
    </head><body>
    <h1 style="font-size:48px;letter-spacing:3px">🔮 TAROT VIP</h1>
    <p style="font-size:18px">IA Tarot Premium</p>
    <a href="/">← ACCUEIL</a>
    </body></html>'''
    return render_template_string(html)

@app.route("/poker")
def poker():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Poker VIP</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}
    a{display:inline-block;margin-top:30px;padding:14px 30px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold}</style>
    </head><body>
    <h1 style="font-size:48px;letter-spacing:3px">♠️ POKER VIP</h1>
    <p style="font-size:18px">Texas Hold'em Multijoueur</p>
    <a href="/">← ACCUEIL</a>
    </body></html>'''
    return render_template_string(html)

@app.route("/games")
def games():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Jeux Montenoir</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;max-width:900px;margin:40px auto}
    a{display:inline-block;padding:30px 20px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold;font-size:16px}</style>
    </head><body>
    <h1 style="font-size:48px;letter-spacing:3px">🎮 JEUX MONTENOIR</h1>
    <div class="grid">
    <a href="/metropoly">🏛️ Metropoly</a>
    <a href="/codenames">🎯 Codenames</a>
    <a href="/tarot">🔮 Tarot</a>
    <a href="/poker">♠️ Poker</a>
    </div>
    <a href="/" style="display:inline-block;margin-top:30px;padding:14px 30px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px;font-weight:bold">← ACCUEIL</a>
    </body></html>'''
    return render_template_string(html)

@app.route("/register")
def register():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Inscription</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}</style>
    </head><body>
    <h1>📝 INSCRIPTION</h1>
    <p>Formulaire d'inscription - Bientôt disponible</p>
    <a href="/" style="display:inline-block;padding:10px 20px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px">Retour</a>
    </body></html>'''
    return render_template_string(html)

@app.route("/login")
def login():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Connexion</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}</style>
    </head><body>
    <h1>👤 CONNEXION</h1>
    <p>Formulaire de connexion - Bientôt disponible</p>
    <a href="/" style="display:inline-block;padding:10px 20px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px">Retour</a>
    </body></html>'''
    return render_template_string(html)

@app.route("/premium")
def premium():
    html = '''<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Premium</title>
    <style>body{background:#050505;color:#d4af37;font-family:Georgia;text-align:center;padding:50px;margin:0}</style>
    </head><body>
    <h1>💎 PREMIUM</h1>
    <p>Offre Premium - Bientôt disponible</p>
    <a href="/" style="display:inline-block;padding:10px 20px;background:#d4af37;color:#050505;text-decoration:none;border-radius:8px">Retour</a>
    </body></html>'''
    return render_template_string(html)

if __name__ == "__main__":
    init_db()
    bootstrap_admin_user()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Montenoir VIP on port {port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
