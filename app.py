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


# Safe global translation script placeholder/fixer
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
    # Compatible avec les anciens comptes qui auraient été sauvegardés en texte brut
    # et avec les nouveaux comptes sauvegardés en SHA256.
    if udata.get('password_hash') == hash_password(password):
        return True
    if udata.get('password') == password:
        udata['password_hash'] = hash_password(password)
        udata.pop('password', None)
        return True
    return False



def bootstrap_admin_user():
    """Crée Yohanna automatiquement si ADMIN_PASSWORD est défini."""
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

def public_profile(username, data):
    # Profil public : email caché aux autres joueurs.
    p = {
        "username": username,
        "chips": data.get("chips", 1000),
        "wins": data.get("wins", 0),
        "games": data.get("games", 0),
        "avatar": data.get("avatar", "woman.png"),
        "avatarData": data.get("avatarData", ""),
        "nameColor": data.get("nameColor", "default"),
        "avatarFrame": data.get("avatarFrame", "none"),
        "inventory": data.get("inventory", []),
        "createdAt": data.get("createdAt", ""),
        "vip": data.get("vip", False),
        "vipLevel": data.get("vipLevel", ""),
        "vipUntil": data.get("vipUntil", 0),
        "membershipLevel": data.get("membershipLevel", ""),
        "membershipLabel": data.get("membershipLabel", ""),
        "membershipUntil": data.get("membershipUntil", 0),
        "xp": int(data.get("xp", 0)),
        "level": monte_calc_level(data.get("xp", 0))[0],
        "xpProgress": monte_calc_level(data.get("xp", 0))[2],
        "achievements": data.get("achievements", [])
    }
    if username.lower() == "yohanna":
        p["vip"] = True
        p["vipLevel"] = "OWNER"
        p["membershipLevel"] = "owner"
        p["membershipLabel"] = "👑 OWNER"
        p["isOwner"] = True
        if not p.get("nameColor") or p.get("nameColor") == "default":
            p["nameColor"] = "owner"
        if not p.get("avatarFrame") or p.get("avatarFrame") == "none":
            p["avatarFrame"] = "baroque-owner"
    strict_owner = username.lower() == OWNER_USERNAME
    if strict_owner:
        p["vip"] = True
        p["vipLevel"] = "OWNER"
        p["membershipLevel"] = "owner"
        p["membershipLabel"] = "👑 OWNER"
        p["isOwner"] = True
        p["nameColor"] = "owner"
        p["avatarFrame"] = "baroque-owner"
    else:
        p["isOwner"] = False
        if p.get("membershipLevel") == "owner":
            p["membershipLevel"] = ""
            p["membershipLabel"] = ""
        if p.get("vipLevel") == "OWNER":
            p["vipLevel"] = ""
    return p

def private_profile(username, data):
    # Profil privé : email visible uniquement par le propriétaire connecté.
    p = public_profile(username, data)
    p["email"] = data.get("email", "")
    return p

def send_reset_email(to_email, reset_link):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_password:
        print("RESET PASSWORD LINK:", reset_link)
        return False

    message = f"Subject: Codenames VIP - Reset password\n\nClique sur ce lien pour renouveler ton mot de passe :\n{reset_link}\n\nSi tu n'as rien demandé, ignore ce message."
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, to_email, message.encode("utf-8"))
    return True

def save_player_to_user(player):
    username = player.get("account")
    if not username:
        return
    users = load_users()
    if username in users:
        users[username]["chips"] = int(player.get("chips", users[username].get("chips", 1000)))
        users[username]["avatar"] = player.get("avatar", users[username].get("avatar", "woman.png"))
        users[username]["avatarData"] = player.get("avatarData", users[username].get("avatarData", ""))
        users[username]["nameColor"] = player.get("nameColor", users[username].get("nameColor", "default"))
        users[username]["avatarFrame"] = player.get("avatarFrame", users[username].get("avatarFrame", "none"))
        users[username]["vip"] = player.get("vip", users[username].get("vip", False))
        users[username]["vipLevel"] = player.get("vipLevel", users[username].get("vipLevel", ""))
        users[username]["vipUntil"] = player.get("vipUntil", users[username].get("vipUntil", 0))
        save_users(users)



def ensure_user_account(account):
    """Retourne la clé utilisateur exacte. Si l'interface a déjà un compte local,
    on crée une fiche serveur minimale pour éviter le faux message 'giriş yapmalısın'."""
    account = (account or '').strip()
    if not account:
        return None
    users = load_users()
    key = find_user_key(users, account)
    if key:
        return key
    users[account] = {
        'email': '',
        'password_hash': '',
        'chips': 1000,
        'wins': 0,
        'games': 0,
        'avatar': 'woman.png',
        'avatarData': '',
        'nameColor': 'default',
        'avatarFrame': 'none',
        'inventory': [],
        'createdAt': str(int(time.time())),
        'autoCreated': True
    }
    save_users(users)
    return account



# =========================
# Londres SAFE SYSTEMS HELPERS
# =========================
def monte_ensure_user_defaults(u):
    u.setdefault("chips", 1000)
    u.setdefault("xp", 0)
    u.setdefault("level", 1)
    u.setdefault("achievements", [])
    u.setdefault("friends", [])
    u.setdefault("friendRequests", [])
    u.setdefault("messages", [])
    u.setdefault("ownedFrames", [])
    u.setdefault("ownedNameColors", [])
    u.setdefault("ownedBadges", [])
    u.setdefault("openedChests", 0)
    u.setdefault("tournaments", [])
    u.setdefault("premiumTarotRequests", [])
    return u

def monte_calc_level(xp):
    xp = int(xp or 0)
    level = max(1, int((xp / 100) ** 0.5) + 1)
    current_xp = (level - 1) ** 2 * 100
    next_xp = level ** 2 * 100
    progress = int(((xp - current_xp) / max(1, next_xp-current_xp)) * 100)
    return level, next_xp, max(0, min(100, progress))

def monte_find_or_create_user(username):
    username = (username or "").strip()
    if not username:
        return None, None
    users = load_users()
    key = find_user_key(users, username)
    if not key:
        ensure_user_account(username)
        users = load_users()
        key = find_user_key(users, username)
    if key:
        monte_ensure_user_defaults(users[key])
        lvl, nxt, prog = monte_calc_level(users[key].get("xp", 0))
        users[key]["level"] = lvl
        save_users(users)
    return users, key

def monte_add_xp(users, key, amount):
    if not users or not key or key not in users:
        return
    monte_ensure_user_defaults(users[key])
    users[key]["xp"] = int(users[key].get("xp", 0)) + int(amount)
    lvl, nxt, prog = monte_calc_level(users[key]["xp"])
    users[key]["level"] = lvl
    monte_unlock_achievements(users, key)

def monte_unlock_achievements(users, key):
    u = monte_ensure_user_defaults(users[key])
    ach = set(u.get("achievements", []))
    if int(u.get("games", 0)) >= 1: ach.add("🎮 İlk Oyun")
    if int(u.get("wins", 0)) >= 1: ach.add("🏆 İlk Zafer")
    if int(u.get("wins", 0)) >= 10: ach.add("🔥 10 Oyun Kazandı")
    if int(u.get("games", 0)) >= 100: ach.add("🎮 100 Oyun Oynadı")
    if int(u.get("openedChests", 0)) >= 1: ach.add("🎁 İlk 🚢 Port International")
    if len(u.get("premiumTarotRequests", [])) >= 1: ach.add("🔮 Tarot Ustası")
    if int(u.get("level", 1)) >= 10: ach.add("⭐ Seviye 10")
    u["achievements"] = sorted(list(ach))

def monte_public_payload(key, u):
    monte_ensure_user_defaults(u)
    lvl, nxt, prog = monte_calc_level(u.get("xp", 0))
    return {"username": key, "chips": int(u.get("chips", 1000)), "xp": int(u.get("xp", 0)),
            "level": lvl, "nextLevelXp": nxt, "xpProgress": prog, "wins": int(u.get("wins", 0)),
            "games": int(u.get("games", 0)), "membershipLabel": u.get("membershipLabel", ""),
            "achievements": u.get("achievements", []), "friends": u.get("friends", []),
            "friendRequests": u.get("friendRequests", []), "ownedFrames": u.get("ownedFrames", []),
            "ownedNameColors": u.get("ownedNameColors", []), "ownedBadges": u.get("ownedBadges", [])}


ANIMALS = ['ASLAN','KAPLAN','KEDİ','KÖPEK','KURT','TİLKİ','AYI','YILAN','KARTAL','ŞAHİN','BALİNA','YUNUS','AHTAPOT','KAPLUMBAĞA','TAVŞAN','GEYİK','ZÜRAFA','FİL','GORİL','MAYMUN','PANDA','KOALA','KANGURU','PENGUEN','BAYKUŞ','KARGA','AT','EŞEK','İNEK','KEÇİ','KOYUN','DEVE','YARASA','KARINCA','ARI','KELEBEK','AKREP','ÖRÜMCEK','KURBAĞA','TİMSAH','PAPAĞAN']
ADULT = ['GECE','PARTİ','BAR','KULÜP','FLÖRT','GİZEM','TUTKU','ÇEKİM','BAKIŞ','ÖPÜCÜK','DANS','ŞAMPANYA','KIRMIZI','SİYAH','KADİFE','RUJ','PARFÜM','AŞK','MACERA','SIR','MASKELİ','CASINO','VIP','LÜKS','IŞIK','MÜZİK','ROMANTİK','ATEŞ','FANTEZİ','GÜNAH','ÇEKİCİ','YAKINLIK','GÜLÜMSEME','KISKANÇLIK','BÜYÜ','ODA']
FALLBACK = ['ASLAN','KEDİ','UZAY','AY','ROBOT','ORMAN','DENİZ','KALE','ELMAS','TAVŞAN','KORSAN','PİRAMİT','DRAGON','YILDIZ','GEZEGEN','ARABA','TELEFON','MÜZİK','KÖPEK','BALIK','KRAL','GÜNEŞ','KALEM','OKYANUS','MAYMUN']


COSMETIC_PRICES = {
    "frame-gold": 1000,
    "frame-vip": 5000,
    "frame-legendary": 15000,
    "name-red": 500,
    "name-blue": 500,
    "name-purple": 1000,
    "name-green": 3000,
    "name-rainbow": 10000
}


VIP_PACKAGES = {
    "vip-bronze": {"label": "VIP Bronze", "price": 3000, "days": 7},
    "vip-gold": {"label": "VIP Gold", "price": 9000, "days": 30},
    "vip-diamond": {"label": "VIP Diamond", "price": 25000, "days": 90}
}

def load_words(category='default'):
    if category == 'animals':
        return ANIMALS
    if category == 'adult':
        return ADULT
    try:
        with open('CodeNames8.txt', 'r', encoding='utf-8-sig') as f:
            words = [x.strip() for x in f if x.strip()]
            words = list(dict.fromkeys(words))
            if len(words) >= 25:
                print('Kelime sayısı:', len(words))
                return words
    except Exception as e:
        print('Kelime dosyası okunamadı:', e)
    return FALLBACK

def room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def new_game(category='default'):
    words = load_words(category)
    if len(words) < 25:
        words = FALLBACK
    selected = random.sample(words, 25)
    roles = ['blue'] * 9 + ['red'] * 8 + ['neutral'] * 7 + ['assassin']
    random.shuffle(roles)
    return {
        'cards': [{'word': selected[i], 'role': roles[i], 'open': False, 'guessed': False, 'guessedBy': [], 'guessedTeam': ''} for i in range(25)],
        'blueCount': 9, 'redCount': 8, 'turn': 'blue', 'winner': '',
        'phase': "🧠 Mavi takımın Spymaster'ı ipucu düşünüyor...",
        'clue': 'İpucu: -', 'clueLog': [], 'moveLog': [],
        'guessLimit': 0, 'guessesMade': 0, 'clueActive': False, 'category': category, 'roundNo': 1, 'started': False
    }

def pdata(code):
    r = rooms[code]
    return {'players': r['players'], 'game': r['game'], 'stats': r['stats'], 'locks': r['locks'], 'bets': r['bets'], 'micStates': r.get('micStates', {}), 'ready': r.get('ready', {}), 'room': code}

def by_sid(code, sid):
    return next((p for p in rooms[code]['players'] if p['sid'] == sid), None)

def by_name(code, name):
    return next((p for p in rooms[code]['players'] if p['name'].lower() == name.lower()), None)

def is_admin(code):
    if code not in rooms: return False
    p = by_sid(code, request.sid)
    return bool((p and p.get('isAdmin')) or rooms[code]['adminSid'] == request.sid)

def switch_turn(g):
    g['clueActive'] = False; g['guessLimit'] = 0; g['guessesMade'] = 0; g['clue'] = 'İpucu: -'
    if g['turn'] == 'blue':
        g['turn'] = 'red'; g['phase'] = "🧠 Kırmızı takımın Spymaster'ı ipucu düşünüyor..."
    else:
        g['turn'] = 'blue'; g['phase'] = "🧠 Mavi takımın Spymaster'ı ipucu düşünüyor..."

def update_winner(code, text):
    st = rooms[code]['stats']
    winning_team = None
    if 'MAVİ' in text:
        st['blueWins'] += 1; st['history'].append('Mavi Takım'); winning_team = 'blue'
    if 'KIRMIZI' in text:
        st['redWins'] += 1; st['history'].append('Kırmızı Takım'); winning_team = 'red'

    users = load_users()
    for p in rooms[code].get('players', []):
        account = p.get('account')
        if not account or account not in users:
            continue
        monte_ensure_user_defaults(users[account])
        users[account]['games'] = int(users[account].get('games', 0)) + 1
        users[account]['chips'] = int(p.get('chips', users[account].get('chips', 1000)))
        monte_add_xp(users, account, 10)
        if winning_team and p.get('team') == winning_team:
            users[account]['wins'] = int(users[account].get('wins', 0)) + 1
            monte_add_xp(users, account, 100)
    save_users(users)

def save_history(code, text):
    st = rooms[code]['stats']; g = rooms[code]['game']; st['gameNo'] += 1
    st['wordHistory'].append({'gameNo': st['gameNo'], 'winner': text, 'words': [c['word'] + '(' + c['role'] + ')' for c in g['cards']]})

def can_clue(p, g):
    return bool(p and ((g['turn'] == 'blue' and p['role'] == 'blueSpy') or (g['turn'] == 'red' and p['role'] == 'redSpy')))

def settle_bets(code, winner_team):
    r = rooms[code]
    for sid, b in list(r['bets'].items()):
        p = by_sid(code, sid) or by_name(code, b.get('name',''))
        if not p: continue
        if b['team'] == winner_team:
            gain = b['amount'] * 2; p['chips'] += gain; r['stats']['betHistory'].append(f"🎰 {p['name']} kazandı: +{gain} jeton")
        else:
            r['stats']['betHistory'].append(f"🎰 {p['name']} kaybetti: -{b['amount']} jeton")
    r['bets'] = {}
    for p in r.get('players', []):
        save_player_to_user(p)



# =========================
# TAROT & RITUEL MODULE
# =========================
TAROT_REQUESTS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "tarot_requests.json")

TAROT_PRICES = {
    "tek_soru": 300,
    "uc_soru": 700,
    "ask_acilimi": 1000,
    "genel_bakim": 1500,
    "rituel_ask_iliski": 800,
    "rituel_ozguven_cekim": 800,
    "rituel_sans_bolluk": 800,
    "rituel_kariyer_basari": 800,
    "rituel_negatif_enerji": 800,
    "rituel_kisisel_niyet": 1500,
    "ai_otomatik_bakim": 100
}

TAROT_LABELS = {
    "tek_soru": "Tek Soru Bakımı",
    "uc_soru": "3 Soru Bakımı",
    "ask_acilimi": "Aşk Açılımı",
    "genel_bakim": "Genel Bakım",
    "rituel_ask_iliski": "Aşk ve İlişki Ritüeli",
    "rituel_ozguven_cekim": "Öz Güven ve Çekim Gücü Ritüeli",
    "rituel_sans_bolluk": "✈️ Aéroport International ve Bolluk Ritüeli",
    "rituel_kariyer_basari": "Kariyer ve Başarı Ritüeli",
    "rituel_negatif_enerji": "Negatif Enerjiden Arınma Ritüeli",
    "rituel_kisisel_niyet": "Kişisel Niyet Ritüeli",
    "ai_otomatik_bakim": "Otomatik Yapay Zekâ Bakımı"
}

TAROT_PACKAGES = [
    {"chips": 200, "price": "4,99 £"},
    {"chips": 500, "price": "9,99 £"},
    {"chips": 1200, "price": "19,99 £"},
    {"chips": 3000, "price": "39,99 £"},
    {"chips": 8000, "price": "89,99 £"}
]

def load_tarot_requests():
    try:
        with open(TAROT_REQUESTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_tarot_requests(items):
    data_dir = os.path.dirname(TAROT_REQUESTS_FILE)
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    with open(TAROT_REQUESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


@app.route("/turnuvalar")
def turnuvalar_page():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>🏆 Turnuvalar</h1><p>Haftalık Codenames Turnuvası — Giriş: 100 jeton — Ödül: 5000 jeton.</p></body></html>"""

@app.route("/arkadaslar")
def arkadaslar_page():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>👥 Arkadaşlar</h1><p>Arkadaş ekleme, özel mesaj ve çevrimiçi durumu yakında.</p></body></html>"""

@app.route("/oyun-kurallari")
def oyun_kurallari_page():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>📜 Oyun Kuralları</h1><p>Saygılı oyun, hile yasak, uygunsuz davranış yasak.</p></body></html>"""

@app.route("/sandiklar")
def sandiklar_page():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>🎁 Sandık Sistemi</h1><p>Bronz, Gümüş, Altın ve Elmas sandıklar yakında.</p></body></html>"""

@app.route("/profil-magazasi")
def profil_magazasi_page():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>🎨 Profil Özelleştirme</h1><p>Altın çerçeve, elmas çerçeve, barok çerçeve, isim renkleri ve animasyonlu profil yakında.</p></body></html>"""

@app.route("/ai-tarot-premium")
def ai_tarot_premium_page_dup2():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>🤖 AI Tarot Premium</h1><p>Doğum tarihi, soru ve fotoğraf ile kişiselleştirilmiş yorum yakında.</p></body></html>"""



@app.after_request
def add_loca_button_to_secondary_pages(response):
    try:
        path = request.path or "/"
        if path != "/" and response.content_type and "text/html" in response.content_type:
            html = response.get_data(as_text=True)
            if 'id="globalLocaBtn"' not in html and "</body>" in html:
                loca = """
<style>
#globalLocaBtn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  gap:8px;
  margin:18px 0 10px 18px;
  color:#d4af37;
  text-decoration:none;
  border:1px solid #d4af37;
  border-radius:14px;
  background:rgba(0,0,0,.72);
  padding:10px 16px;
  font-weight:900;
  font-family:Arial;
  box-shadow:0 0 16px rgba(212,175,55,.28);
}
#globalLocaBtn:hover{background:#d4af37;color:#050505}
</style>
<a id="globalLocaBtn" href="/">🚪 LOCA</a>
"""
                if "<body>" in html:
                    html = html.replace("<body>", "<body>" + loca, 1)
                else:
                    html = html.replace("</body>", loca + "</body>")
                response.set_data(html)
    except Exception:
        pass
    return response




@app.route("/coming-soon/Metropoly")
def monopoly_redirect():
    return redirect("/monopoly")













METROPOLY_ROOMS={}

# name, type, price, base_rent, group
# Règles adaptées aux villes de ton plateau.
METROPOLY_CELLS=[
("ALLEZ","start",0,0,"corner"),
("Banque","bank",0,0,"corner"),
("New York","property",220,24,"green"),
("Monaco","property",200,22,"green"),
("Aéroport International","transport",200,25,"transport"),
("Londres","property",200,22,"green"),
("Varsovie","property",100,12,"brown"),
("Zurich","property",100,12,"brown"),
("Prison","jail",0,0,"corner"),
("Paris","property",160,18,"orange"),
("Milan","property",140,16,"orange"),
("Amsterdam","property",140,16,"orange"),
("Compagnies des Eaux","utility",100,0,"utility"),
("Moscou","property",120,14,"purple"),
("Rome","property",100,12,"purple"),
("Madrid","property",100,12,"purple"),
("Impôts","tax",0,200,"tax"),
("Sofia","property",60,6,"yellow"),
("Belgrad","property",70,8,"yellow"),
("Gare Grande Vitesse","transport",100,25,"transport"),
("Istanbul","property",70,8,"yellow"),
("Prague","property",80,10,"blue"),
("Lisbonne","property",90,12,"blue"),
("Enchères","auction",0,0,"special"),
("Dubaï","property",160,18,"red"),
("Pékin","property",160,18,"red"),
("Compagnie Électrique","utility",150,0,"utility"),
("Tokyo","property",180,20,"red")
]

METROPOLY_GROUPS={}
for i,c in enumerate(METROPOLY_CELLS):
    if c[1]=="property":
        METROPOLY_GROUPS.setdefault(c[4],[]).append(i)

HOUSE_COST=50
HOTEL_COST=50
START_MONEY=1000
PASS_START_BONUS=200
JAIL_FINE=50

def m_room(code,owner):
    return {"code":code,"owner":owner,"started":False,"turnIndex":0,"players":{},"owners":{},"houses":{},"hotels":{},"mortgages":{},"lastLog":"Oda hazır.","lastDice":None}

def m_public(r):
    return {"code":r["code"],"started":r["started"],"turnIndex":r["turnIndex"],"players":r["players"],"owners":r["owners"],"houses":r.get("houses",{}),"hotels":r.get("hotels",{}),"mortgages":r.get("mortgages",{}),"lastLog":r["lastLog"],"lastDice":r["lastDice"],"settings":r.get("settings",{"players":4,"turns":"illimite","target":7000})}

def m_code():
    while True:
        c="MON-"+"".join(random.choices(string.digits,k=4))
        if c not in METROPOLY_ROOMS:
            return c

def active_names(room):
    return [n for n,p in room["players"].items() if not p.get("bankrupt")]

def player_owns_full_group(room, username, group):
    group_cells=METROPOLY_GROUPS.get(group,[])
    return bool(group_cells) and all(room["owners"].get(str(i))==username for i in group_cells)

def group_building_counts(room, group):
    vals=[]
    for i in METROPOLY_GROUPS.get(group,[]):
        vals.append(int(room["houses"].get(str(i),0)) + (5 if room.get("hotels",{}).get(str(i)) else 0))
    return vals

def can_build_house(room, username, cell_index):
    name,typ,price,base,group=METROPOLY_CELLS[cell_index]
    if typ!="property":
        return False,"Sadece şehirlerin üzerine ev kurulabilir."
    if room["owners"].get(str(cell_index))!=username:
        return False,"Bu şehir senin değil."
    if not player_owns_full_group(room, username, group):
        return False,"Bu renkteki tüm şehirleri almalısın."
    if any(room.get("mortgages",{}).get(str(i)) for i in METROPOLY_GROUPS.get(group,[])):
        return False,"Bu renk grubunda ipotekli mülk varken bina kurulamaz."
    if room.get("hotels",{}).get(str(cell_index)):
        return False,"Otelli arsaya ev kurulamaz."
    current=int(room["houses"].get(str(cell_index),0))
    if current>=4:
        return False,"Bu arsada zaten 4 ev var. Otel kurabilirsin."
    # dengeli ev kuralı: bir arsaya ikinci ev koymadan önce gruptaki herkes en az bir ev almalı
    counts=[int(room["houses"].get(str(i),0)) for i in METROPOLY_GROUPS.get(group,[]) if not room.get("hotels",{}).get(str(i))]
    if counts and current>min(counts):
        return False,"Evler dengeli kurulmalı: önce aynı renkteki diğer şehirlere ev koy."
    return True,"OK"

def can_build_hotel(room, username, cell_index):
    name,typ,price,base,group=METROPOLY_CELLS[cell_index]
    if typ!="property":
        return False,"Sadece şehirlerin üzerine otel kurulabilir."
    if room["owners"].get(str(cell_index))!=username:
        return False,"Bu şehir senin değil."
    if not player_owns_full_group(room, username, group):
        return False,"Bu renkteki tüm şehirleri almalısın."
    if room.get("hotels",{}).get(str(cell_index)):
        return False,"Bu arsada zaten otel var."
    if int(room["houses"].get(str(cell_index),0))<4:
        return False,"Otel için bu arsada 4 ev olmalı."
    return True,"OK"

def property_rent(room, cell_index):
    name,typ,price,base,group=METROPOLY_CELLS[cell_index]
    if room.get("mortgages",{}).get(str(cell_index)):
        return 0
    if room.get("hotels",{}).get(str(cell_index)):
        return base*10
    h=int(room["houses"].get(str(cell_index),0))
    if h==1: return base*5
    if h==2: return base*15
    if h==3: return base*35
    if h==4: return base*50
    owner=room["owners"].get(str(cell_index))
    if owner and player_owns_full_group(room, owner, group):
        return base*2
    return base

def transport_rent(room, owner):
    count=sum(1 for i,c in enumerate(METROPOLY_CELLS) if c[1]=="transport" and room["owners"].get(str(i))==owner and not room.get("mortgages",{}).get(str(i)))
    return {1:25,2:50,3:100,4:200}.get(count,25)

def utility_rent(room, owner, dice):
    count=sum(1 for i,c in enumerate(METROPOLY_CELLS) if c[1]=="utility" and room["owners"].get(str(i))==owner and not room.get("mortgages",{}).get(str(i)))
    return dice*(10 if count>=2 else 4)

def next_turn(room):
    names=active_names(room)
    if names:
        room["turnIndex"]=(room["turnIndex"]+1)%len(names)
        room["lastLog"] += " Sıra: "+names[room["turnIndex"]]+"."

@socketio.on("monopoly_create_room")
def mc(data):
    u=(data or {}).get("username","Misafir").strip() or "Misafir"
    t=(data or {}).get("token","🎩")
    c=m_code()
    r=m_room(c,u)
    METROPOLY_ROOMS[c]=r
    join_room(c)
    colors=["#34c759","#ff3b30","#007aff","#ffd60a","#bf5af2","#ff9500"]; color=colors[(len(r["players"]))%len(colors)]; r["players"][u]={"name":u,"token":t,"color":color,"money":START_MONEY,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odayı kurdu."
    emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_join_room")
def mj(data):
    u=(data or {}).get("username","Misafir").strip() or "Misafir"
    t=(data or {}).get("token","🎩")
    c=((data or {}).get("code","") or "").strip().upper()
    if c not in METROPOLY_ROOMS:
        emit("monopoly_error",{"msg":"Oda bulunamadı."}); return
    r=METROPOLY_ROOMS[c]
    join_room(c)
    if u not in r["players"]:
        colors=["#34c759","#ff3b30","#007aff","#ffd60a","#bf5af2","#ff9500"]; color=colors[(len(r["players"]))%len(colors)]; r["players"][u]={"name":u,"token":t,"color":color,"money":START_MONEY,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odaya girdi."
    emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_start_game")
def ms(data):
    c=((data or {}).get("code","") or "").strip().upper()
    r=METROPOLY_ROOMS.get(c)
    if r:
        r["started"]=True
        r["turnIndex"]=0
        r["lastLog"]="Oyun başladı. Herkes 1000€ ile başladı."
        emit("monopoly_room_state",m_public(r),room=c)


def monopoly_apply_community_effect(r,u):
    import random
    p=r["players"][u]
    effects=["plus200","plus100","minus100","pay50","start","paris"]
    e=random.choice(effects)
    if e=="plus200":
        p["money"]+=200; msg="Banque sana 200€ verdi."
    elif e=="plus100":
        p["money"]+=100; msg="Banque sana 100€ verdi."
    elif e=="minus100":
        p["money"]-=100; msg="Banqueye 100€ ceza ödedin."
    elif e=="pay50":
        for n,op in r["players"].items():
            if n!=u:
                p["money"]-=50; op["money"]+=50
        msg="Her oyuncuya 50€ ödedin."
    elif e=="start":
        p["position"]=0; msg="ALLEZ karesine gittin."
    else:
        p["position"]=9; msg="Paris karesine gittin."
    r["lastLog"]=u+" - Caisse de Communauté: "+msg

@socketio.on("monopoly_roll_dice")
def mr(data):
    c=((data or {}).get("code","") or "").strip().upper()
    u=(data or {}).get("username","").strip()
    r=METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        emit("monopoly_error",{"msg":"Oda/oyuncu yok."}); return
    names=active_names(r)
    if not names:
        return
    if u!=names[r["turnIndex"]%len(names)]:
        emit("monopoly_error",{"msg":"Sıra sende değil."}); return
    p=r["players"][u]
    if p.get("hasRolled") and r.get("lastDice")!=6:
        emit("monopoly_error",{"msg":"Bu tur zaten zar attın. Sırayı bitir."}); return
    if p.get("jailed",0)>0:
        if p["money"]>=JAIL_FINE:
            p["money"]-=JAIL_FINE
            p["jailed"]=0
            r["lastLog"]=u+" kodes cezası ödedi: -50€."
        else:
            p["bankrupt"]=True
            r["lastLog"]=u+" kodes cezasını ödeyemedi ve iflas etti."
            next_turn(r)
            emit("monopoly_room_state",m_public(r),room=c); return

    d=random.randint(1,6)
    old=p["position"]
    new=(old+d)%len(METROPOLY_CELLS)
    if new<old:
        p["money"]+=PASS_START_BONUS
    p["position"]=new
    name,typ,price,base,group=METROPOLY_CELLS[new]
    log=f"{u} zar attı: {d}. {name} karesine geldi."
    if new<old:
        log+=" ALLEZ noktasından geçti: +200€."
    pending=False
    if typ in ["property","transport","utility"]:
        owner=r["owners"].get(str(new))
        if owner and owner!=u:
            if typ=="property":
                pay=property_rent(r,new)
            elif typ=="transport":
                pay=transport_rent(r,owner)
            else:
                pay=utility_rent(r,owner,d)
            p["money"]-=pay
            r["players"][owner]["money"]+=pay
            log+=f" {owner} sahibine {pay}€ kira ödedi."
        elif not owner:
            pending=True
            log+=f" Sahipsiz mülk. Satın alma fiyatı: {price}€."
    elif typ=="tax":
        p["money"]-=base
        log+=f" Vergi ödedi: -{base}€."
    elif typ=="bank":
        b=random.choice([50,75,100,150])
        p["money"]+=b
        log+=f" Bankadan para aldı: +{b}€."
    elif typ=="auction":
        b=random.choice([-50,50,100])
        p["money"]+=b
        log+=f" Enchères sonucu: {b}€."
    elif typ=="jail":
        p["jailed"]=1
        log+=" Prison: bir sonraki turda 50€ ödeyip çıkacak."
    if p["money"]<0:
        p["bankrupt"]=True
        log+=" Para eksiye düştü: iflas."
    r["lastDice"]=d
    p["hasRolled"]=True
    if d==6:
        p["hasRolled"]=False
        log+=" 6 geldi: tekrar oynama hakkı kazandı."
    r["lastLog"]=log

@socketio.on("monopoly_buy_property")
def mb(data):
    c=((data or {}).get("code","") or "").strip().upper()
    u=(data or {}).get("username","").strip()
    r=METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        return
    p=r["players"][u]
    pos=p["position"]
    name,typ,price,base,group=METROPOLY_CELLS[pos]
    if typ not in ["property","transport","utility"] or str(pos) in r["owners"] or p["money"]<price:
        emit("monopoly_error",{"msg":"Satın alınamaz."}); return
    p["money"]-=price
    r["owners"][str(pos)]=u
    r["lastLog"]=f"{u}, {name} mülkünü {price}€ karşılığı satın aldı."
    emit("monopoly_room_state",m_public(r),room=c)



@socketio.on("monopoly_end_turn")
def me(data):
    c=((data or {}).get("code","") or "").strip().upper()
    r=METROPOLY_ROOMS.get(c)
    if not r:
        return
    names=active_names(r)
    if len(names)<=1 and r.get("started"):
        r["lastLog"]="🏆 Kazanan: "+(names[0] if names else "yok")
    elif names:
        r["turnIndex"]=(r["turnIndex"]+1)%len(names)
        r["lastLog"]="Sıra: "+names[r["turnIndex"]]+"."
    emit("monopoly_room_state",m_public(r),room=c)


@socketio.on("monopoly_create_room")
def mc(data):
    u=(data or {}).get("username","Misafir").strip() or "Misafir"; t=(data or {}).get("token","🎩")
    c=m_code(); r=m_room(c,u); METROPOLY_ROOMS[c]=r; join_room(c)
    r["players"][u]={"name":u,"token":t,"money":1000,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odayı kurdu."; emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_join_room")
def mj(data):
    u=(data or {}).get("username","Misafir").strip() or "Misafir"; t=(data or {}).get("token","🎩"); c=((data or {}).get("code","") or "").strip().upper()
    if c not in METROPOLY_ROOMS: emit("monopoly_error",{"msg":"Oda bulunamadı."}); return
    r=METROPOLY_ROOMS[c]; join_room(c)
    if u not in r["players"]:
        r["players"][u]={"name":u,"token":t,"money":1000,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odaya girdi."; emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_start_game")
def ms(data):
    c=((data or {}).get("code","") or "").strip().upper(); r=METROPOLY_ROOMS.get(c)
    if r: r["started"]=True; r["lastLog"]="Oyun başladı."; emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_roll_dice")
def mr(data):
    c=((data or {}).get("code","") or "").strip().upper(); u=(data or {}).get("username","").strip(); r=METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]: emit("monopoly_error",{"msg":"Oda/oyuncu yok."}); return
    names=[n for n,p in r["players"].items() if not p.get("bankrupt")]
    if u!=names[r["turnIndex"]%len(names)]: emit("monopoly_error",{"msg":"Sıra sende değil."}); return
    p=r["players"][u]; d=random.randint(1,6); old=p["position"]; new=(old+d)%len(METROPOLY_CELLS)
    if new<old: p["money"]+=200
    p["position"]=new; name,typ,price,rent,grp=METROPOLY_CELLS[new]; log=f"{u} zar: {d}. {name}."
    pending=False
    if typ in ["property","transport","utility"]:
        owner=r["owners"].get(str(new))
        if owner and owner!=u:
            pay=rent+int(r["houses"].get(str(new),0))*15; p["money"]-=pay; r["players"][owner]["money"]+=pay; log+=f" {owner} sahibine {pay}€ kira ödedi."
        elif not owner: pending=True; log+=f" Satın alınabilir: {price}€."
    elif typ=="tax": p["money"]-=200; log+=" Vergi: -200€."
    elif typ=="bank": b=random.choice([50,75,100,150]); p["money"]+=b; log+=f" Banka: +{b}€."
    elif typ=="bonus": b=random.choice([-50,50,100,150]); p["money"]+=b; log+=f" Enchères: {b}€."
    elif typ=="jail": p["jailed"]=1; log+=" Prison."
    if p["money"]<0: p["bankrupt"]=True; log+=" İflas."
    r["lastDice"]=d; r["lastLog"]=log; emit("monopoly_animate_move",{"username":u,"from":old,"to":new,"dice":d,"state":m_public(r),"pendingBuy":pending},room=c)

@socketio.on("monopoly_buy_property")
def mb(data):
    c=((data or {}).get("code","") or "").strip().upper(); u=(data or {}).get("username","").strip(); r=METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]: return
    p=r["players"][u]; pos=p["position"]; name,typ,price,rent,grp=METROPOLY_CELLS[pos]
    if typ not in ["property","transport","utility"] or str(pos) in r["owners"] or p["money"]<price: emit("monopoly_error",{"msg":"Satın alınamaz."}); return
    p["money"]-=price; r["owners"][str(pos)]=u; r["lastLog"]=f"{u}, {name} aldı."; emit("monopoly_room_state",m_public(r),room=c)


@socketio.on("monopoly_end_turn")
def me(data):
    c=((data or {}).get("code","") or "").strip().upper(); r=METROPOLY_ROOMS.get(c)
    if not r: return
    names=[n for n,p in r["players"].items() if not p.get("bankrupt")]
    if names: r["turnIndex"]=(r["turnIndex"]+1)%len(names); r["lastLog"]="Sıra: "+names[r["turnIndex"]]
    emit("monopoly_room_state",m_public(r),room=c)


















@socketio.on("monopoly_chat")
def monopoly_chat(data):
    c=((data or {}).get("code","") or "").strip().upper()
    u=(data or {}).get("username","").strip() or "Oyuncu"
    msg=(data or {}).get("message","").strip()
    if c and msg:
        emit("monopoly_chat_message",{"username":u,"message":msg},room=c)


@socketio.on("monopoly_add_house")
def monopoly_add_house(data):
    c=((data or {}).get("code","") or "").strip().upper()
    u=(data or {}).get("username","").strip()
    cell=str((data or {}).get("cell",""))
    r=METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        return
    r.setdefault("houses",{})
    r.setdefault("hotels",{})
    if r.get("owners",{}).get(cell)!=u:
        emit("monopoly_error",{"msg":"Bu mülk senin değil."})
        return
    if r["hotels"].get(cell):
        emit("monopoly_error",{"msg":"Bu mülkte zaten otel var."})
        return
    count=int(r["houses"].get(cell,0))
    if count>=4:
        emit("monopoly_error",{"msg":"4 evden sonra otel almalısın."})
        return
    if r["players"][u]["money"]<50:
        emit("monopoly_error",{"msg":"Ev için para yetmiyor."})
        return
    r["players"][u]["money"]-=50
    r["houses"][cell]=count+1
    r["lastLog"]=u+" ev aldı."
    emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_add_hotel")
def monopoly_add_hotel(data):
    c=((data or {}).get("code","") or "").strip().upper()
    u=(data or {}).get("username","").strip()
    cell=str((data or {}).get("cell",""))
    r=METROPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        return
    r.setdefault("houses",{})
    r.setdefault("hotels",{})
    if r.get("owners",{}).get(cell)!=u:
        emit("monopoly_error",{"msg":"Bu mülk senin değil."})
        return
    if int(r["houses"].get(cell,0))<4:
        emit("monopoly_error",{"msg":"Otel için önce 4 ev gerekir."})
        return
    if r["players"][u]["money"]<100:
        emit("monopoly_error",{"msg":"Otel için para yetmiyor."})
        return
    r["players"][u]["money"]-=100
    r["houses"][cell]=0
    r["hotels"][cell]=1
    r["lastLog"]=u+" otel aldı."
    emit("monopoly_room_state",m_public(r),room=c)








# === CLEAN ROUTES MONTENOIR / METROPOLY ===

# === ROUTES PROPRES MONTENOIR / METROPOLY ===


# === ROUTES FORCEES MONTENOIR VIP ===

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/games")
def games():
    return render_template_string('<h1>Games</h1>')

@app.route("/metropoly")
def metropoly():
    return render_template("metropoly.html")

@app.route("/register")
def register_page():
    return render_template_string('<h1>Register</h1>')

@app.route("/login")
def login_page():
    return render_template_string('<h1>Login</h1>')

@app.route("/premium")
def premium_page():
    return render_template_string('<h1>Premium</h1>')

if __name__ == "__main__":
    import sys, traceback
    try:
        init_db()
        bootstrap_admin_user()
    except:
        pass
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Londres VIP on port {port}", flush=True)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
