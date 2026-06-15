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

@app.route("/tarot_old_disabled")
def tarot_world():
    return render_template_string(TAROT_HTML + Londres_I18N_SCRIPT)

@app.route("/tarot_pdf/<request_id>")
def tarot_pdf(request_id):
    reqs = load_tarot_requests()
    req = next((x for x in reqs if str(x.get("id")) == str(request_id)), None)
    if not req:
        return "Demande introuvable", 404
    title = req.get("serviceLabel", "Tarot & Ritüel")
    username = req.get("username", "-")
    created = req.get("createdAtText", "-")
    result = req.get("result") or "Ritüel talebin alındı. Bakımcı tarafından yorum hazırlandığında sonuç güncellenecek."
    html = f"""
    <html><head><meta charset='UTF-8'>
    <style>
    body{{font-family:Arial;background:#050505;color:#d4af37;padding:45px;}}
    .page{{border:2px solid #d4af37;border-radius:24px;padding:35px;background:#0b0b0b;}}
    h1{{text-align:center;text-shadow:0 0 12px #d4af37;}}
    .box{{border:1px solid #d4af37;border-radius:16px;padding:18px;margin:15px 0;color:#f8e7a0;}}
    
.topLeftFixed{
display:flex!important;
flex-direction:column!important;
align-items:flex-start!important;
gap:6px!important;
}
.topLeftFixed button{
width:190px!important;
}
.compactMenuWrap{
width:190px!important;
}

.footer{margin-top:25px;text-align:center}
.footerLine{width:220px;height:2px;margin:0 auto 12px auto;background:linear-gradient(90deg,transparent,#d4af37,transparent);box-shadow:0 0 12px #d4af37}
.footerText{color:#d4af37;font-size:15px;letter-spacing:4px;font-weight:bold;text-shadow:0 0 10px rgba(212,175,55,.7)}


.bigLogo,.mainTitle,.mainVip,.logoMark,.title,.vip{display:none!important}


/* realism patch */
.playerCard .colorDot{
  width:18px!important;
  height:18px!important;
  border:2px solid rgba(255,255,255,.75)!important;
}
.playerCard{
  background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(0,0,0,.52))!important;
}
.ownedLabel{
  display:inline-block;
  width:38px;
  height:7px;
  border-radius:6px;
  margin-left:8px;
  vertical-align:middle;
}


/* V2 controls dice chat fix */
.dice{width:110px!important;height:110px!important;perspective:900px!important;filter:drop-shadow(0 22px 18px #000) drop-shadow(0 0 12px rgba(255,255,255,.35))!important}
.face{width:110px!important;height:110px!important;border-radius:10px!important;background:linear-gradient(145deg,#fff,#e7e7e7 52%,#8c8c8c)!important;border:3px solid #fff!important}
.front{transform:translateZ(55px)!important}.back{transform:rotateY(180deg) translateZ(55px)!important}.right{transform:rotateY(90deg) translateZ(55px)!important}.leftf{transform:rotateY(-90deg) translateZ(55px)!important}.topf{transform:rotateX(90deg) translateZ(55px)!important}.bottomf{transform:rotateX(-90deg) translateZ(55px)!important}.pip{width:17px!important;height:17px!important}
.chatLog{position:fixed;left:18px;bottom:78px;z-index:170;min-width:260px;max-width:420px;padding:13px 16px;border:1px solid #d4af37;border-radius:14px;background:#000d;color:#fff;font-weight:900;box-shadow:0 0 20px #000;opacity:0;transform:translateY(10px);transition:.25s}.chatLog.show{opacity:1;transform:translateY(0)}
.modeSaved{position:fixed;right:330px;top:76px;z-index:120;color:#ffd989;background:#000c;border:1px solid #d4af37;border-radius:12px;padding:8px 12px;font-weight:900;display:none}
</style></head><body>
    <div class='page'>
    <h1>🔮 {title}</h1>
    <div class='box'><b>Kullanıcı:</b> {username}<br><b>Tarih:</b> {created}</div>
    <div class='box'><b>Ritüel / Bakım Sonucu:</b><br><br>{result}</div>
    <p style='text-align:center'>Codenames VIP · Tarot & Ritüel Dünyası</p>
    <script>window.print()</script>
    </div></body></html>
    """
    return html

@socketio.on("tarot_get_profile")
def tarot_get_profile(data):
    account = ensure_user_account(data.get("account"))
    if not account:
        emit("tarot_profile", {"ok": False, "msg": "Giriş gerekli."})
        return
    users = load_users()
    key = find_user_key(users, account)
    emit("tarot_profile", {"ok": True, "profile": private_profile(key, users[key]), "prices": TAROT_PRICES, "packages": TAROT_PACKAGES})

@socketio.on("tarot_submit_request")
def tarot_submit_request(data):
    account = ensure_user_account(data.get("account"))
    service = data.get("service", "")
    if service not in TAROT_PRICES:
        emit("tarot_result", {"ok": False, "msg": "Hizmet bulunamadı."})
        return
    users = load_users()
    key = find_user_key(users, account)
    if not key:
        emit("tarot_result", {"ok": False, "msg": "Kullanıcı bulunamadı."})
        return
    price = int(TAROT_PRICES[service])
    chips = int(users[key].get("chips", 1000))
    if not is_owner_name(key):
        if chips < price:
            emit("tarot_result", {"ok": False, "msg": "Yeterli jeton yok."})
            return
        users[key]["chips"] = chips - price
    else:
        users[key]["chips"] = max(chips, 999999)
    save_users(users)
    reqs = load_tarot_requests()
    rid = str(int(time.time() * 1000))[-6:]
    service_label = TAROT_LABELS.get(service, service)
    created_text = time.strftime("%d/%m/%Y %H:%M")
    ai_result = ""
    if service == "ai_otomatik_bakim":
        cards = random.sample(["Ay", "Güneş", "Yıldız", "Aşıklar", "Kule", "İmparatoriçe", "Azize", "Dünya", "Güç"], 3)
        ai_result = "Çekilen kartlar: " + ", ".join(cards) + ". Bu otomatik yorum, enerjinin şu anda dönüşüm ve karar kapısında olduğunu gösteriyor."
    req = {
        "id": rid, "service": service, "serviceLabel": service_label, "price": price,
        "username": key, "name": data.get("name", ""), "motherName": data.get("motherName", ""),
        "birthDate": data.get("birthDate", ""), "question": data.get("question", ""),
        "photoNote": data.get("photoNote", ""), "status": "Bekliyor" if service != "ai_otomatik_bakim" else "Tamamlandı",
        "result": ai_result, "createdAt": int(time.time()), "createdAtText": created_text
    }
    reqs.insert(0, req)
    save_tarot_requests(reqs)
    emit("tarot_result", {"ok": True, "msg": f"{service_label} talebin alındı. {price} jeton düşüldü.", "request": req, "profile": private_profile(key, users[key])})

@socketio.on("tarot_get_requests")
def tarot_get_requests(data):
    account = (data.get("account") or "").strip().lower()
    if account not in ["yohanna", "svetlana", "svetlana karaman", "admin"]:
        emit("tarot_requests", {"ok": False, "msg": "Admin yetkisi gerekli.", "requests": []})
        return
    emit("tarot_requests", {"ok": True, "requests": load_tarot_requests()[:100]})

@socketio.on("tarot_lucky_wheel")
def tarot_lucky_wheel(data):
    settings = load_site_settings() if "load_site_settings" in globals() else {"wheel": True, "wheelDailyLimit": 1, "wheelRewards": {"10":25, "20":20, "30":18, "50":15, "100":10, "200":8, "300":4}}
    if not settings.get("wheel", True):
        emit("tarot_wheel_result", {"ok": False, "msg": "Şans çarkı şu anda kapalı."})
        return
    account = ensure_user_account(data.get("account"))
    users = load_users()
    key = find_user_key(users, account)
    if not key:
        emit("tarot_wheel_result", {"ok": False, "msg": "Giriş gerekli."})
        return
    today = time.strftime("%Y-%m-%d")
    if not is_owner_name(key):
        wheel_log = users[key].setdefault("wheelLog", {})
        used = int(wheel_log.get(today, 0))
        limit = int(settings.get("wheelDailyLimit", 1))
        if used >= limit:
            emit("tarot_wheel_result", {"ok": False, "msg": f"Şans çarkını günde sadece {limit} kez çevirebilirsin."})
            return
        wheel_log[today] = used + 1
    rw = settings.get("wheelRewards", {"10":25, "20":20, "30":18, "50":15, "100":10, "200":8, "300":4})
    rewards = [int(k) for k in rw.keys()]
    weights = [int(v) for v in rw.values()]
    reward = random.choices(rewards, weights=weights, k=1)[0]
    users[key]["chips"] = int(users[key].get("chips", 1000)) + reward
    if is_owner_name(key):
        users[key]["chips"] = max(users[key]["chips"], 999999)
    users[key]["lastWheelDate"] = today
    save_users(users)
    emit("tarot_wheel_result", {"ok": True, "reward": reward, "profile": private_profile(key, users[key])})


TAROT_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Tarot & Ritüel</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=UnifrakturCook:wght@700&family=Cinzel:wght@400;700;900&display=swap');
body{margin:0;min-height:100vh;font-family:'Cinzel',Georgia,serif;color:#d4af37;background:radial-gradient(circle at top,#2a1a05 0%,#050505 48%,#000 100%);overflow-x:hidden;}
.tarotCardsBg{position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.18;background:radial-gradient(circle at 20% 30%,rgba(212,175,55,.35),transparent 13%),radial-gradient(circle at 80% 20%,rgba(212,175,55,.25),transparent 12%),radial-gradient(circle at 40% 80%,rgba(212,175,55,.22),transparent 15%),repeating-linear-gradient(45deg,rgba(212,175,55,.06) 0 1px,transparent 1px 48px);}
.tarotCardsBg:after{content:"☾  THE MOON   ✦   THE STAR   ✦   THE LOVERS   ✦   THE HIGH PRIESTESS   ☽";position:absolute;top:34%;left:-12%;width:130%;font-size:74px;font-weight:900;letter-spacing:18px;color:#d4af37;opacity:.18;transform:rotate(-8deg);font-family:'UnifrakturCook',Georgia,serif;}
.tarotCardsBg:before{content:"🂠  🂡  🂢  🂣  🂤";position:absolute;bottom:12%;left:5%;font-size:150px;letter-spacing:40px;color:#d4af37;opacity:.08;filter:blur(.4px);}
.stars{position:fixed;inset:0;z-index:0;pointer-events:none;background-image:radial-gradient(#d4af37 1px,transparent 1px);background-size:55px 55px;opacity:.18;animation:stars 25s linear infinite;}@keyframes stars{from{background-position:0 0}to{background-position:400px 700px}}
.fog{position:fixed;inset:-20%;z-index:0;pointer-events:none;background:radial-gradient(circle,rgba(255,255,255,.08),transparent 35%);filter:blur(35px);opacity:.35;animation:fog 12s ease-in-out infinite alternate;}@keyframes fog{from{transform:translateX(-6%)}to{transform:translateX(6%)}}
.wrap{position:relative;z-index:2;max-width:1200px;margin:auto;padding:28px;text-align:center}
h1{font-family:'UnifrakturCook',Georgia,serif;font-size:58px;text-align:left;text-shadow:0 0 18px #d4af37,0 0 50px #8a6a00;margin:20px 0 5px;letter-spacing:4px}.sub{text-align:left;color:#f4df94;letter-spacing:3px}.topbar{display:flex;justify-content:flex-start;gap:10px;flex-wrap:wrap;margin:20px 0}
.btn,.service{font-family:'Cinzel',Georgia,serif;background:linear-gradient(145deg,#000,#160f02,#000);color:#d4af37;border:1px solid #d4af37;border-radius:18px;padding:13px 18px;font-weight:900;cursor:pointer;box-shadow:0 0 12px rgba(212,175,55,.55),inset 0 0 14px rgba(212,175,55,.12);}
.btn:hover,.service:hover{transform:scale(1.04);box-shadow:0 0 25px #d4af37}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin-top:20px}
.panel{background:rgba(0,0,0,.72);border:1px solid rgba(212,175,55,.75);border-radius:24px;padding:20px;text-align:left;box-shadow:0 0 25px rgba(212,175,55,.25);}
.panel h2{text-align:center;color:#ffd978;font-family:'UnifrakturCook',Georgia,serif;font-size:32px}.service{width:100%;margin:6px 0;text-align:left}input,textarea,select{width:95%;padding:12px;border-radius:12px;border:1px solid #d4af37;background:#070707;color:#f8e7a0;margin:6px 0;}textarea{height:90px}.resultBox{white-space:pre-wrap;color:#f8e7a0;line-height:1.5}.adminItem{border:1px solid #d4af37;border-radius:14px;padding:12px;margin:8px 0;background:rgba(255,255,255,.04)}.candle{font-size:36px;animation:candle 1.4s ease-in-out infinite alternate}@keyframes candle{from{filter:drop-shadow(0 0 4px #d4af37)}to{filter:drop-shadow(0 0 20px #ffcc55)}}
.profileLine{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap}.profileLine img{width:58px;height:54px;border-radius:50%;object-fit:cover;border:2px solid #d4af37;box-shadow:0 0 14px #d4af37}.levelBadge{display:inline-block;border:1px solid #d4af37;border-radius:999px;padding:6px 12px;margin-left:6px;background:rgba(212,175,55,.12);box-shadow:0 0 12px rgba(212,175,55,.45)}.chatBox{height:170px;overflow:auto;background:#050505;border:1px solid #d4af37;border-radius:14px;padding:10px;color:#f8e7a0;margin-bottom:8px}.payBox{border:1px dashed #d4af37;border-radius:14px;padding:10px;margin:8px 0;background:rgba(212,175,55,.05)}
.ownerName{color:#d4af37!important;font-weight:900;text-shadow:0 0 9px #d4af37,0 0 25px #000,0 0 42px #ffd700;letter-spacing:2px;border:2px double #d4af37;border-radius:999px;padding:4px 10px;background:#000;box-shadow:0 0 18px #d4af37}.ownerBadge{display:inline-block;margin-left:8px;padding:4px 10px;border-radius:999px;border:1px solid #d4af37;background:#000;color:#d4af37;box-shadow:0 0 14px #d4af37}
.wheelWrap{text-align:center}.wheelPointer{font-size:34px;color:#ffd700;text-shadow:0 0 12px #d4af37;margin-bottom:-12px}.wheel{width:280px;height:280px;border-radius:50%;margin:15px auto;border:7px solid #d4af37;background:conic-gradient(#2a1b00 0deg 45deg,#000 45deg 90deg,#3b2600 90deg 135deg,#050505 135deg 180deg,#2a1b00 180deg 225deg,#000 225deg 270deg,#3b2600 270deg 315deg,#050505 315deg 360deg);box-shadow:0 0 24px #d4af37,inset 0 0 30px rgba(212,175,55,.25);display:flex;align-items:center;justify-content:center;position:relative;transition:transform 4s cubic-bezier(.12,.74,.12,1);overflow:hidden}.wheel span{position:absolute;left:50%;top:50%;transform-origin:0 0;color:#ffd700;font-weight:900;text-shadow:0 0 8px #d4af37}.wheel:after{content:"🔮";font-size:42px;z-index:2;background:#000;border:2px solid #d4af37;border-radius:50%;padding:18px;box-shadow:0 0 18px #d4af37}

/* === BIG WHEEL REWARD MESSAGE === */
#wheelRewardOverlay{
    display:none;
    position:fixed;
    inset:0;
    z-index:99999999;
    background:rgba(0,0,0,.72);
    align-items:center;
    justify-content:center;
    text-align:center;
}
#wheelRewardText{
    padding:36px 52px;
    border:3px double #d4af37;
    border-radius:34px;
    background:radial-gradient(circle at top,#3a2700,#000 70%);
    color:#ffd700;
    font-family:'UnifrakturCook',Georgia,serif;
    font-size:62px;
    font-weight:900;
    text-shadow:0 0 12px #ffd700,0 0 34px #d4af37,0 0 60px #000;
    box-shadow:0 0 28px #d4af37,0 0 80px rgba(212,175,55,.75), inset 0 0 30px rgba(212,175,55,.25);
    animation:rewardPop .7s ease-out;
}
@keyframes rewardPop{
    0%{transform:scale(.35);opacity:0}
    70%{transform:scale(1.08);opacity:1}
    100%{transform:scale(1);opacity:1}
}
@media(max-width:700px){
    #wheelRewardText{font-size:38px;padding:28px 28px}
}
</style></head>
<body>
<div id="wheelRewardOverlay">
  <div id="wheelRewardText"></div>
</div>
<div class="tarotCardsBg"></div><div class="stars"></div><div class="fog"></div><div class="wrap">
<h1>🔮 Tarot & Rituel</h1><div class="sub">Siyah kadife · Altın sır · Mum ışığı</div><div class="candle">🕯️ 🕯️ 🕯️</div>
<div class="topbar"><button data-base-label='Satın Al' class="btn" onclick="location.href='/'">♠ Codenames'e Dön</button><button class="btn" onclick="location.href='/'">👤 Üye Ol / Giriş</button><button class="btn" onclick="loadProfile()">🏆 Profil / Yenile</button><button class="btn" onclick="spinWheel()">🎡 Şans Çarkı</button><button class="btn" id="tarotOwnerBtn" style="display:none" onclick="loadAdminRequests()">👑 Admin Talep Paneli</button></div>
<div class="panel" style="text-align:center"><div class="profileLine"><img id="avatarImg" src=""><div><b>👤 <span id="userName">-</span><span id="ownerBadge"></span></b><br>🪙 <span id="chips">-</span> jeton <span id="levelBadge" class="levelBadge">-</span></div></div><p style="font-size:12px;color:#f4df94">Codenames hesabın otomatik kullanılır. Tarot tarafında yeniden giriş yok.</p></div>
<div class="panel wheelWrap"><h2>🎡 Şans Çarkı</h2><div class="wheelPointer">▼</div><div id="luckyWheel" class="wheel"><span style="transform:rotate(10deg) translate(45px,-112px)">50</span><span style="transform:rotate(55deg) translate(45px,-112px)">100</span><span style="transform:rotate(100deg) translate(45px,-112px)">200</span><span style="transform:rotate(145deg) translate(45px,-112px)">30</span><span style="transform:rotate(190deg) translate(45px,-112px)">10</span><span style="transform:rotate(235deg) translate(45px,-112px)">20</span><span style="transform:rotate(280deg) translate(45px,-112px)">300</span></div><button class="btn" onclick="spinWheel()">Günde 1 Kez Çevir</button><div id="wheelInfo" style="color:#f8e7a0;margin-top:8px;">Ödüller: 10, 20, 30, 50, 100, 200, 300 jeton</div></div>
<div class="grid"><div class="panel"><h2>🔮 Tarot Açılımları</h2><button class="service" onclick="selectService('genel_bakim')">Genel Bakım · 30 dk · 1500 🪙</button><button class="service" onclick="selectService('ask_acilimi')">Aşk Açılımı · 20 dk · 1000 🪙</button><button class="service" onclick="selectService('tek_soru')">Tek Soru · 5 dk · 300 🪙</button><button class="service" onclick="selectService('uc_soru')">3 Soru · 10 dk · 700 🪙</button><button class="service" onclick="selectService('ai_otomatik_bakim')">Otomatik AI Bakımı · 100 🪙</button></div>
<div class="panel"><h2>🕯️ Ritüeller</h2><button class="service" onclick="selectService('rituel_ask_iliski')">Aşk ve İlişki · 800 🪙</button><button class="service" onclick="selectService('rituel_ozguven_cekim')">Öz Güven ve Çekim Gücü · 800 🪙</button><button class="service" onclick="selectService('rituel_sans_bolluk')">Şans ve Bolluk · 800 🪙</button><button class="service" onclick="selectService('rituel_kariyer_basari')">Kariyer ve Başarı · 800 🪙</button><button class="service" onclick="selectService('rituel_negatif_enerji')">Negatif Enerjiden Arınma · 800 🪙</button><button class="service" onclick="selectService('rituel_kisisel_niyet')">Kişisel Niyet · 1500 🪙</button></div>
<div class="panel"><h2>🪙 Jeton Bakiyesi</h2><p>Jeton satın alma artık sadece Londres Kasası üzerinden yapılır.</p><button class="btn" onclick="location.href='/kasa'">🪙 <span data-i18n="cashier">Londres KASASI</span></button></div></div>
<div class="panel"><h2>📩 Talep Formu</h2><b>Seçilen hizmet:</b> <span id="selectedLabel">Henüz seçilmedi</span><input id="clientName" placeholder="İsmin"><input id="motherName" placeholder="Anne adı"><input id="birthDate" placeholder="Doğum tarihi"><textarea id="question" placeholder="Sorunu / niyetini yaz"></textarea><input id="photoNote" placeholder="Fotoğraf / özel bilgi notu"><button class="btn" onclick="submitTarot()">Jetonla Satın Al ve Gönder</button></div>
<div class="grid"><div class="panel"><h2>✨ Sonuç</h2><div id="resultBox" class="resultBox">Henüz sonuç yok.</div><div id="pdfBox"></div></div><div class="panel"><h2>💬 Canlı Sohbet</h2><div id="tarotChatBox" class="chatBox"></div><input id="tarotChatInput" placeholder="Bakımcıya mesaj yaz"><button class="btn" onclick="sendTarotChat()">Gönder</button></div></div>
<div class="panel" id="tarotAdminPanel" style="display:none"><h2>👑 Admin Talep Paneli</h2><div id="adminRequests">Yohanna / admin hesabıyla talepleri görebilirsin.</div></div>
</div>
<script>
const socket=io();let account=localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||'';let selectedService='';
function defaultAvatarData(avatar){const isMan=avatar==='man.png';const bg=isMan?'#111111':'#ff4fd8';const emoji=isMan?'👤':'👩';const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><circle cx="60" cy="60" r="56" fill="${bg}" stroke="#d4af37" stroke-width="6"/><text x="60" y="78" font-size="58" text-anchor="middle">${emoji}</text></svg>`;return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);}
function isOwner(){return (account||'').toLowerCase()==='yohanna'}
function levelName(chips){chips=parseInt(chips||0);if(chips>=15000)return'💎 Elmas';if(chips>=5000)return'🥇 Altın';if(chips>=1000)return'🥈 Gümüş';return'🥉 Bronz';}
function saveSharedProfile(p){localStorage.setItem('codenamesAccount',p.username);localStorage.setItem('loggedUser',p.username);localStorage.setItem('loggedIn','true');localStorage.setItem('codenamesProfile',JSON.stringify(p));localStorage.setItem('codenamesChips_'+p.username,String(p.chips||1000));}
function renderProfile(p){account=p.username;const owner=(p.username||'').toLowerCase()==='yohanna';userName.innerHTML=owner?'👑 '+p.username:p.username;userName.className=owner?'ownerName':'';ownerBadge.innerHTML='';chips.innerHTML=owner?'∞':p.chips;levelBadge.innerHTML=owner?'Owner hesabı':(p.membershipLabel||levelName(p.chips));avatarImg.src=p.avatarData||defaultAvatarData(p.avatar||'woman.png');tarotOwnerBtn.style.display=owner?'inline-block':'none';tarotAdminPanel.style.display=owner?'block':'none';saveSharedProfile(p);}
function loadProfile(){account=localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||account||'';if(!account){alert('Önce Codenames tarafında giriş yap.');location.href='/';return}socket.emit('tarot_get_profile',{account});}
function selectService(s){selectedService=s;const labels={genel_bakim:'Genel Bakım · 1500 jeton',ask_acilimi:'Aşk Açılımı · 1000 jeton',tek_soru:'Tek Soru · 300 jeton',uc_soru:'3 Soru · 700 jeton',ai_otomatik_bakim:'Otomatik AI Bakımı · 100 jeton',rituel_ask_iliski:'Aşk ve İlişki Ritüeli · 800 jeton',rituel_ozguven_cekim:'Öz Güven ve Çekim Gücü Ritüeli · 800 jeton',rituel_sans_bolluk:'Şans ve Bolluk Ritüeli · 800 jeton',rituel_kariyer_basari:'Kariyer ve Başarı Ritüeli · 800 jeton',rituel_negatif_enerji:'Negatif Enerjiden Arınma Ritüeli · 800 jeton',rituel_kisisel_niyet:'Kişisel Niyet Ritüeli · 1500 jeton'};selectedLabel.innerHTML=labels[s]||s;}
function submitTarot(){if(!account){alert('Giriş gerekli.');return}if(!selectedService){alert('Önce hizmet seç.');return}socket.emit('tarot_submit_request',{account,service:selectedService,name:clientName.value,motherName:motherName.value,birthDate:birthDate.value,question:question.value,photoNote:photoNote.value});}
function spinWheel(){if(!account){alert('Giriş gerekli.');return}const w=document.getElementById('luckyWheel');if(w){w.style.transform='rotate('+(1440+Math.floor(Math.random()*720))+'deg)';}setTimeout(()=>socket.emit('tarot_lucky_wheel',{account}),900);}
function loadAdminRequests(){socket.emit('tarot_get_requests',{account});}
function sendTarotChat(){let msg=tarotChatInput.value.trim();if(!msg)return;socket.emit('tarot_chat',{account,msg});tarotChatInput.value='';}
socket.on('tarot_profile',d=>{if(!d.ok){alert(d.msg);location.href='/';return}renderProfile(d.profile);});
socket.on('tarot_result',d=>{if(!d.ok){alert(d.msg);return}renderProfile(d.profile);resultBox.innerHTML=d.msg+"\n\nTalep #"+d.request.id+"\nDurum: "+d.request.status+"\n\n"+(d.request.result||"Bakımcı yorumu bekleniyor.");pdfBox.innerHTML='<br><button class="btn" onclick="window.open(\'/tarot_pdf/'+d.request.id+'\',\'_blank\')">📄 PDF Ritüelini İndir</button>';});

function showWheelReward(amount){
    const overlay=document.getElementById('wheelRewardOverlay');
    const box=document.getElementById('wheelRewardText');
    if(!overlay||!box)return;
    box.innerHTML='🎉 '+amount+' JETON ÇIKTI! 🎉<br><span style="font-family:Cinzel,Georgia,serif;font-size:28px;">Jeton hesabına eklendi</span>';
    overlay.style.display='flex';
    setTimeout(()=>{overlay.style.display='none';},2600);
}
socket.on('tarot_wheel_result',d=>{if(!d.ok){alert(d.msg);return}renderProfile(d.profile);wheelInfo.innerHTML='Bugünkü ödülün: +'+d.reward+' jeton · Jeton hesabına eklendi';showWheelReward(d.reward);});
socket.on('tarot_requests',d=>{if(!d.ok){adminRequests.innerHTML=d.msg;return}adminRequests.innerHTML=d.requests.map(r=>`<div class="adminItem"><b>Yeni talep #${r.id}</b><br>${r.serviceLabel}<br>Kullanıcı: ${r.username}<br>Soru: ${r.question||'-'}<br>Durum: ${r.status}</div>`).join('')||'Talep yok.';});
socket.on('tarot_chat_update',d=>{tarotChatBox.innerHTML+='<b>'+d.name+':</b> '+d.msg+'<br>';tarotChatBox.scrollTop=tarotChatBox.scrollHeight;});
loadProfile();
setTimeout(refreshOwnerButton,300);setInterval(refreshOwnerButton,2000);

/* === HARD BUTTON CLICK FIX === */
function hardBindButtons(){
    const bind = (id, fn) => {
        const el = document.getElementById(id);
        if(!el) return;
        el.onclick = function(e){
            e.preventDefault();
            e.stopPropagation();
            try{ fn(); }catch(err){ console.error('Button error '+id, err); alert('Buton hatası: '+id+' / '+err.message); }
            return false;
        };
    };
    bind('menuToggleBtn', ( )=>{ 
        const m=document.getElementById('mainCompactMenu');
        if(m)m.classList.toggle('show');
    });
    bind('btnTimerTop', ()=>{ if(typeof startTimer==='function') startTimer(); });
    bind('btnNewGameTop', ()=>{ if(typeof newGame==='function') newGame(); });
    bind('btnLobbyTop', ()=>{ if(typeof goLobby==='function') goLobby(); });

    bind('menuAuthBtn', ()=>{ if(typeof openAuth==='function') openAuth(); closeMainMenu(); });
    bind('menuProfileBtn', ()=>{ if(typeof openProfile==='function') openProfile(); closeMainMenu(); });
    bind('menuRankingBtn', ()=>{ if(typeof openRanking==='function') openRanking(); closeMainMenu(); });
    bind('menuSettingsBtn', ()=>{ if(typeof openSettings==='function') openSettings(); closeMainMenu(); });
    bind('menuWordsBtn', ()=>{ if(typeof openWords==='function') openWords(); closeMainMenu(); });
    bind('menuBetBtn', ()=>{ if(typeof openBet==='function') openBet(); closeMainMenu(); });
    bind('ownerPanelBtn', ()=>{ if(typeof openOwnerPanel==='function') openOwnerPanel(); closeMainMenu(); });
}
document.addEventListener('DOMContentLoaded', hardBindButtons);
setTimeout(hardBindButtons,500);
setTimeout(hardBindButtons,1500);

</script></body></html>
"""



@socketio.on("tarot_chat")
def tarot_chat(data):
    account = (data.get("account") or "Kullanıcı").strip()
    msg = (data.get("msg") or "").strip()
    if not msg:
        return
    emit("tarot_chat_update", {"name": account, "msg": msg}, broadcast=True)


# =========================
# OWNER PANEL FULL - ONLY YOHANNA
# =========================
SITE_SETTINGS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "site_settings.json")

def load_site_settings():
    try:
        with open(SITE_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "maintenance": False,
            "registrations": True,
            "wheel": True,
            "tarot": True,
            "ritual": True,
            "wheelDailyLimit": 1,
            "wheelRewards": {"10":25, "20":20, "30":18, "50":15, "100":10, "200":8, "300":4}
        }

def save_site_settings(settings):
    data_dir = os.path.dirname(SITE_SETTINGS_FILE)
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    with open(SITE_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

@socketio.on("owner_get_panel")
def owner_get_panel(data):
    if not is_owner_name(data.get("owner", "")):
        emit("owner_panel_data", {"ok": False, "msg": "Bu panel sadece Yohanna Owner içindir."})
        return
    users = load_users()
    reqs = load_tarot_requests() if "load_tarot_requests" in globals() else []
    stats = {
        "totalUsers": len(users),
        "onlineUsers": sum(len(r.get("players", [])) for r in rooms.values()),
        "todayUsers": 0,
        "soldChips": sum(int(u.get("chipsPurchased", 0)) for u in users.values()),
        "completedTarot": sum(1 for r in reqs if r.get("status") == "Tamamlandı"),
        "completedRitual": sum(1 for r in reqs if "rituel" in r.get("service", "") and r.get("status") == "Tamamlandı")
    }
    emit("owner_panel_data", {
        "ok": True,
        "users": [private_profile(k, v) for k, v in users.items()],
        "requests": reqs[:100],
        "settings": load_site_settings(),
        "stats": stats,
        "payments": {
            "stripe": {"today": "0 £", "month": "0 £", "total": "0 £"},
            "paypal": {"last": [], "refunds": []}
        }
    })

@socketio.on("owner_manage_user")
def owner_manage_user(data):
    if not is_owner_name(data.get("owner", "")):
        emit("owner_action_result", {"ok": False, "msg": "Bu işlemi sadece Yohanna yapabilir."})
        return
    users = load_users()
    key = find_user_key(users, data.get("target", ""))
    if not key:
        emit("owner_action_result", {"ok": False, "msg": "Kullanıcı bulunamadı."})
        return
    action = data.get("action")
    amount = int(data.get("amount", 0) or 0)
    if action == "add_chips":
        users[key]["chips"] = int(users[key].get("chips", 1000)) + amount
    elif action == "remove_chips":
        users[key]["chips"] = max(0, int(users[key].get("chips", 1000)) - amount)
    elif action == "freeze":
        users[key]["isFrozen"] = True
    elif action == "unfreeze":
        users[key]["isFrozen"] = False
    elif action == "delete":
        if is_owner_name(key):
            emit("owner_action_result", {"ok": False, "msg": "Owner hesabı silinemez."})
            return
        users.pop(key, None)
        save_users(users)
        emit("owner_action_result", {"ok": True, "msg": "Hesap silindi."})
        return
    elif action == "reset_avatar":
        users[key]["avatarData"] = ""
        users[key]["avatar"] = "woman.png"
    elif action == "reset_password_link":
        token = str(random.randint(100000, 999999))
        users[key]["resetToken"] = token
        save_users(users)
        emit("owner_action_result", {"ok": True, "msg": "Şifre reset token: " + token})
        return
    save_users(users)
    emit("owner_action_result", {"ok": True, "msg": "İşlem yapıldı."})

@socketio.on("owner_set_membership")
def owner_set_membership(data):
    if not is_owner_name(data.get("owner", "")):
        emit("owner_action_result", {"ok": False, "msg": "Bu işlemi sadece Yohanna yapabilir."})
        return
    users = load_users()
    key = find_user_key(users, data.get("target", ""))
    if not key:
        emit("owner_action_result", {"ok": False, "msg": "Kullanıcı bulunamadı."})
        return
    level = data.get("level", "")
    duration = data.get("duration", "forever")
    labels = {"bronze": "🥉 Bronz", "silver": "🥈 Gümüş", "gold": "🥇 Altın", "diamond": "💎 Elmas", "none": ""}
    if level == "none":
        users[key]["membershipLevel"] = ""
        users[key]["membershipLabel"] = ""
        users[key]["membershipUntil"] = 0
    else:
        users[key]["membershipLevel"] = level
        users[key]["membershipLabel"] = labels.get(level, level)
        if duration == "30":
            users[key]["membershipUntil"] = int(time.time()) + 30*86400
        elif duration == "90":
            users[key]["membershipUntil"] = int(time.time()) + 90*86400
        else:
            users[key]["membershipUntil"] = 0
    save_users(users)
    emit("owner_action_result", {"ok": True, "msg": "Üyelik güncellendi."})

@socketio.on("owner_update_request")
def owner_update_request(data):
    if not is_owner_name(data.get("owner", "")):
        emit("owner_action_result", {"ok": False, "msg": "Bu işlemi sadece Yohanna yapabilir."})
        return
    reqs = load_tarot_requests()
    for r in reqs:
        if str(r.get("id")) == str(data.get("id")):
            r["status"] = data.get("status", r.get("status", "Bekliyor"))
            if data.get("result") is not None:
                r["result"] = data.get("result")
            save_tarot_requests(reqs)
            emit("owner_action_result", {"ok": True, "msg": "Talep güncellendi."})
            return
    emit("owner_action_result", {"ok": False, "msg": "Talep bulunamadı."})

@socketio.on("owner_update_settings")
def owner_update_settings(data):
    if not is_owner_name(data.get("owner", "")):
        emit("owner_action_result", {"ok": False, "msg": "Bu işlemi sadece Yohanna yapabilir."})
        return
    settings = load_site_settings()
    for k in ["maintenance", "registrations", "wheel", "tarot", "ritual"]:
        if k in data:
            settings[k] = bool(data[k])
    if "wheelDailyLimit" in data:
        settings["wheelDailyLimit"] = int(data.get("wheelDailyLimit", 1))
    save_site_settings(settings)
    emit("owner_action_result", {"ok": True, "msg": "Site ayarları güncellendi.", "settings": settings})



# =========================
# Londres CLEAN AUTH SYSTEM
# =========================

def clean_username(name):
    return (name or "").strip()

def clean_email(email):
    return (email or "").strip().lower()

def normalize_user_record(username, data=None):
    data = data or {}
    data.setdefault("username", username)
    data.setdefault("email", "")
    data.setdefault("password_hash", "")
    data.setdefault("chips", 1000)
    data.setdefault("xp", 0)
    data.setdefault("level", 1)
    data.setdefault("wins", 0)
    data.setdefault("games", 0)
    data.setdefault("avatar", "👤")
    data.setdefault("avatarData", "")
    data.setdefault("nameColor", "gold")
    data.setdefault("avatarFrame", "gold")
    data.setdefault("membershipLabel", "")
    data.setdefault("membershipLevel", "")
    data.setdefault("inventory", [])
    data.setdefault("createdAt", str(int(time.time())))
    data.setdefault("lastLogin", "")
    data.setdefault("isAdmin", False)
    return data

def clean_find_user_key(users, username):
    wanted = clean_username(username).lower()
    for key in users.keys():
        if key.lower() == wanted:
            return key
    return None

def clean_profile_payload(username, data):
    data = normalize_user_record(username, data)
    return {
        "ok": True,
        "username": username,
        "email": data.get("email", ""),
        "chips": int(data.get("chips", 1000)),
        "xp": int(data.get("xp", 0)),
        "level": int(data.get("level", 1)),
        "wins": int(data.get("wins", 0)),
        "games": int(data.get("games", 0)),
        "avatar": data.get("avatar", "👤"),
        "avatarData": data.get("avatarData", ""),
        "nameColor": data.get("nameColor", "gold"),
        "avatarFrame": data.get("avatarFrame", "gold"),
        "membershipLabel": data.get("membershipLabel", ""),
        "membershipLevel": data.get("membershipLevel", ""),
        "isAdmin": bool(data.get("isAdmin", False)),
        "isOwner": bool(data.get("isOwner", False)) or is_owner_username(username),
    }

def clean_register_user(username, email, password, gender=""):
    username = clean_username(username)
    email = clean_email(email)
    password = password or ""
    if len(username) < 3:
        return {"ok": False, "msg": "Kullanıcı adı en az 3 karakter olmalı."}
    if "@" not in email or "." not in email:
        return {"ok": False, "msg": "Geçerli bir email yaz."}
    if len(password) < 4:
        return {"ok": False, "msg": "Şifre en az 4 karakter olmalı."}

    users = load_users()
    if clean_find_user_key(users, username):
        return {"ok": False, "msg": "Bu kullanıcı adı zaten var."}

    for _, u in users.items():
        if clean_email(u.get("email", "")) == email:
            return {"ok": False, "msg": "Bu email zaten kayıtlı."}

    users[username] = normalize_user_record(username, {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "chips": 1000,
        "xp": 0,
        "level": 1,
        "avatar": "👤",
        "createdAt": str(int(time.time())),
        "lastLogin": str(int(time.time())),
        "gender": gender,
    })
    save_users(users)
    return {"ok": True, "msg": "Kayıt başarılı.", "profile": clean_profile_payload(username, users[username])}

def clean_login_user(username, password):
    username = clean_username(username)
    password = password or ""
    users = load_users()
    key = clean_find_user_key(users, username)
    if not key:
        return {"ok": False, "msg": "Kullanıcı bulunamadı."}
    users[key] = normalize_user_record(key, users[key])
    if users[key].get("password_hash") != hash_password(password):
        return {"ok": False, "msg": "Şifre yanlış."}
    users[key]["lastLogin"] = str(int(time.time()))
    save_users(users)
    return {"ok": True, "msg": "Giriş başarılı.", "profile": clean_profile_payload(key, users[key])}

def clean_get_profile(username):
    users = load_users()
    key = clean_find_user_key(users, username)
    if not key:
        return {"ok": False, "msg": "Kullanıcı bulunamadı."}
    users[key] = normalize_user_record(key, users[key])
    save_users(users)
    return {"ok": True, "profile": clean_profile_payload(key, users[key])}

@app.route("/api/auth/register", methods=["POST"])
def api_clean_register():
    data = request.get_json(force=True, silent=True) or {}
    if data.get("password", "") != data.get("password2", ""):
        return {"ok": False, "msg": "Şifreler aynı değil."}
    return clean_register_user(data.get("username", ""), data.get("email", ""), data.get("password", ""), data.get("gender", ""))

@app.route("/api/auth/login", methods=["POST"])
def api_clean_login():
    data = request.get_json(force=True, silent=True) or {}
    return clean_login_user(data.get("username", ""), data.get("password", ""))

@app.route("/api/auth/profile")
def api_clean_profile():
    return clean_get_profile(request.args.get("username", ""))

@socketio.on("register_account")
def compat_register_account_clean(data):
    p1 = data.get("password", "")
    p2 = data.get("password2", p1)
    if p1 != p2:
        emit("register_result", {"ok": False, "msg": "Şifreler aynı değil."})
        return
    emit("register_result", clean_register_user(data.get("username", ""), data.get("email", ""), p1, data.get("gender", "")))

@socketio.on("login_account")
def compat_login_account_clean(data):
    emit("login_result", clean_login_user(data.get("username", ""), data.get("password", "")))

@socketio.on("request_profile")
def compat_request_profile_clean(data):
    username = data.get("username", "") or data.get("account", "")
    result = clean_get_profile(username)
    if result.get("ok"):
        emit("profile_data", {"profile": result["profile"], **result["profile"]})
        emit("profile_loaded", {"profile": result["profile"], **result["profile"]})
    else:
        emit("profile_data", result)
        emit("profile_loaded", result)




# =========================
# Londres ONLINE MATRIX SYSTEM
# =========================
ONLINE_USERS = {}

def online_symbol_for(data):
    gender = (data or {}).get("gender", "").lower()
    if gender in ["female", "femme", "kadin", "kadın", "woman", "girl"]:
        return "♠️"
    if gender in ["male", "homme", "erkek", "man", "boy"]:
        return "♣️"
    return "♣️"

def online_payload():
    items = []
    for sid, data in ONLINE_USERS.items():
        username = data.get("username", "").strip()
        if username:
            items.append({"username": username, "gender": data.get("gender", ""), "symbol": online_symbol_for(data)})
    dedup = {}
    for item in items:
        dedup[item["username"].lower()] = item
    return list(dedup.values())

@socketio.on("montenoir_user_online")
def montenoir_user_online(data):
    username = (data or {}).get("username", "").strip()
    gender = (data or {}).get("gender", "").strip()
    if not username:
        return
    was_new = request.sid not in ONLINE_USERS or ONLINE_USERS.get(request.sid, {}).get("username", "").lower() != username.lower()
    ONLINE_USERS[request.sid] = {"username": username, "gender": gender, "time": int(time.time())}
    if was_new:
        joined = {"username": username, "gender": gender, "symbol": online_symbol_for({"username": username, "gender": gender})}
        emit("montenoir_online_update", {"users": online_payload(), "joined": joined}, broadcast=True)
    else:
        emit("montenoir_online_update", {"users": online_payload()}, broadcast=True)

@socketio.on("montenoir_get_online")
def montenoir_get_online():
    emit("montenoir_online_update", {"users": online_payload()})

@socketio.on("disconnect")
def montenoir_online_disconnect():
    if request.sid in ONLINE_USERS:
        ONLINE_USERS.pop(request.sid, None)
        emit("montenoir_online_update", {"users": online_payload()}, broadcast=True)


HOME_HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏛️ LOCA - Londres VIP</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
*{box-sizing:border-box}
html,body{margin:0;width:100%;min-height:100%;font-family:Arial,Helvetica,sans-serif;background:#030303;color:#fff;overflow-x:hidden}
.home{position:relative;min-height:100vh;width:100%;background:linear-gradient(180deg,rgba(0,0,0,.34),rgba(0,0,0,.05) 40%,rgba(0,0,0,.42)),url('/static/montenoir_home.png') center top / 100% 100% no-repeat}
.topbar{position:absolute;top:0;left:0;right:0;z-index:80;height:92px;display:flex;align-items:center;justify-content:space-between;padding:18px 28px;background:linear-gradient(180deg,rgba(0,0,0,.85),rgba(0,0,0,.18));border-bottom:1px solid rgba(212,175,55,.22)}
.menuTop{width:140px;height:58px;border:1px solid #d4af37;border-radius:14px;background:linear-gradient(180deg,rgba(10,8,3,.85),rgba(0,0,0,.55));color:#d4af37;font-size:19px;font-weight:900;letter-spacing:.5px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:12px;box-shadow:0 0 16px rgba(212,175,55,.26),inset 0 0 12px rgba(212,175,55,.05)}
.menuTop:hover{background:#d4af37;color:#050505}
.topRight{display:flex;align-items:center;gap:14px}
.topBtn{display:none;height:58px;min-width:190px;border-radius:14px;border:1px solid rgba(212,175,55,.82);background:linear-gradient(180deg,rgba(0,0,0,.76),rgba(0,0,0,.48));color:#fff;font-size:17px;font-weight:900;cursor:pointer;letter-spacing:.3px;box-shadow:0 0 15px rgba(0,0,0,.45), inset 0 0 12px rgba(212,175,55,.05)}
.topBtn.premium{display:none;background:linear-gradient(180deg,#f0c366,#916015);border-color:#ffd882;color:#fff;box-shadow:0 0 22px rgba(212,175,55,.45), inset 0 1px 0 rgba(255,255,255,.25)}
.userBlock{display:none;align-items:center;gap:10px;color:#fff;font-weight:900;border:1px solid rgba(212,175,55,.52);border-radius:28px;padding:6px 12px;background:rgba(0,0,0,.55)}
.userBlock.show{display:flex}
.userCircle{width:42px;height:42px;border-radius:50%;border:1px solid #d4af37;display:grid;place-items:center;background:#090909;color:#d4af37}
.userBlock small{display:block;color:#d4af37;margin-top:3px}
.bottomMain{position:absolute;z-index:20;left:50%;bottom:88px;transform:translateX(-50%);display:flex;gap:18px;align-items:center;justify-content:center;width:min(760px,92vw)}
.bigAction{width:360px;max-width:45vw;height:70px;border-radius:14px;border:1px solid #d4af37;background:linear-gradient(180deg,rgba(20,17,10,.86),rgba(0,0,0,.72));color:#fff;font-size:22px;font-weight:900;letter-spacing:.6px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:16px;box-shadow:0 0 20px rgba(0,0,0,.55), inset 0 0 18px rgba(212,175,55,.05)}
.bigAction i{font-style:normal;font-size:34px;color:#d4af37}
.bigAction.gold{background:linear-gradient(180deg,#f6d782,#ad741f);color:#fff;border-color:#ffe09a;text-shadow:0 2px 4px #000;box-shadow:0 0 28px rgba(212,175,55,.55), inset 0 1px 0 rgba(255,255,255,.30)}
.sidePanel{display:none;position:fixed;left:18px;top:104px;bottom:24px;z-index:90;width:min(395px,94vw);overflow:auto;border:1px solid rgba(212,175,55,.62);border-radius:12px;background:linear-gradient(180deg,rgba(12,9,4,.92),rgba(3,3,3,.88));backdrop-filter:blur(7px);box-shadow:0 0 42px rgba(0,0,0,.76),inset 0 0 24px rgba(212,175,55,.05)}
.sidePanel.show{display:block}
.panelSection{padding:24px;border-bottom:1px solid rgba(212,175,55,.25)}
.panelTitle{font-size:23px;font-weight:900;color:#d4af37;margin-bottom:14px}
.panelLink{display:flex;align-items:center;gap:14px;min-height:58px;padding:13px 15px;color:#fff;text-decoration:none;border:1px solid rgba(212,175,55,.28);border-bottom:0;background:rgba(255,255,255,.04);font-size:16px;font-weight:900;text-shadow:0 2px 3px #000}
.panelLink:first-of-type{border-radius:8px 8px 0 0}.panelLink:last-of-type{border-bottom:1px solid rgba(212,175,55,.28);border-radius:0 0 8px 8px}
.panelLink b{font-size:25px;color:#d4af37;min-width:30px;text-align:center}
.setting{border:1px solid rgba(212,175,55,.28);background:rgba(255,255,255,.04);border-radius:8px;padding:13px;margin-bottom:10px;color:#ddd}
.setting h3{margin:0 0 8px;font-size:18px;color:#fff}.setting p{margin:0;font-size:14px;line-height:1.35}
.setting select{width:100%;padding:10px;margin-top:7px;border:1px solid #d4af37;border-radius:10px;background:#0b0b0b;color:#f6d777}
.bottomCards{position:absolute;left:28px;right:28px;bottom:12px;z-index:15;display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.card{height:66px;border:1px solid rgba(212,175,55,.32);border-radius:11px;background:linear-gradient(180deg,rgba(20,18,14,.82),rgba(5,5,5,.78));display:flex;align-items:center;gap:12px;padding:10px 16px;box-shadow:0 0 18px rgba(0,0,0,.5),inset 0 0 12px rgba(212,175,55,.04)}
.cardIcon{font-size:30px;color:#d4af37}.cardText{font-size:14px;font-weight:900;color:#fff;line-height:1.1}.cardText small{display:block;color:#d7c28a;font-size:11px;font-weight:500;margin-top:5px}
.card button{margin-left:auto;border:1px solid #d4af37;border-radius:18px;background:linear-gradient(180deg,#c99d45,#5a3608);color:#fff;padding:7px 14px;font-weight:900;cursor:pointer}
.gamesPanel{display:none;position:fixed;z-index:95;left:50%;bottom:174px;transform:translateX(-50%);width:min(620px,92vw);border:1px solid #d4af37;border-radius:14px;background:rgba(5,5,5,.92);padding:22px;box-shadow:0 0 35px rgba(0,0,0,.85)}
.gamesPanel.show{display:block}
.gameGrid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.gameGrid a{border:1px solid rgba(212,175,55,.35);border-radius:12px;padding:14px;color:#fff;text-decoration:none;font-weight:900;background:rgba(255,255,255,.04)}
.modal{display:none;position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.78);align-items:center;justify-content:center;padding:18px}
.modalBox{width:min(460px,94vw);border:1px solid #d4af37;border-radius:18px;background:linear-gradient(145deg,#050505,#1b1205);box-shadow:0 0 40px rgba(212,175,55,.45);padding:22px;color:#f6d777}.modalBox h2{text-align:center;color:#d4af37}.modalBox input{width:100%;margin:7px 0;padding:12px;border-radius:12px;border:1px solid #d4af37;background:#090909;color:#fff}.modalBox button{margin:5px;padding:10px 14px;border-radius:12px;border:1px solid #d4af37;background:#111;color:#f6d777;font-weight:bold;cursor:pointer}.closeBtn{float:right}

/* REAL 3D CUBE DICE */
.diceBox{
  position:absolute;
  left:50%;
  top:50%;
  transform:translate(-50%,-50%);
  z-index:80;
  perspective:1000px;
  width:120px;
  height:120px;
  pointer-events:none;
}
.realDice{
  width:96px;
  height:96px;
  position:absolute;
  left:50%;
  top:50%;
  margin-left:-48px;
  margin-top:-48px;
  transform-style:preserve-3d;
  transform:rotateX(-18deg) rotateY(24deg);
  transition:transform .55s cubic-bezier(.2,.8,.2,1);
  filter:drop-shadow(0 24px 18px rgba(0,0,0,.95)) drop-shadow(0 0 12px rgba(255,255,255,.25));
}
.realDice.rolling{
  animation:realDiceRoll .85s linear infinite;
}
@keyframes realDiceRoll{
  0%{transform:rotateX(0deg) rotateY(0deg) rotateZ(0deg)}
  100%{transform:rotateX(720deg) rotateY(540deg) rotateZ(360deg)}
}
.diceFace{
  position:absolute;
  width:96px;
  height:96px;
  border-radius:18px;
  background:
    radial-gradient(circle at 30% 22%,rgba(255,255,255,.95),transparent 26%),
    linear-gradient(145deg,#ffffff 0%,#e8e8e8 52%,#8d8d8d 100%);
  border:3px solid #ffffff;
  box-shadow:
    inset -12px -12px 22px rgba(0,0,0,.24),
    inset 9px 9px 18px rgba(255,255,255,.82),
    0 0 16px rgba(255,255,255,.18);
  transform-style:preserve-3d;
}
.diceFace.front{transform:translateZ(48px)}
.diceFace.back{transform:rotateY(180deg) translateZ(48px)}
.diceFace.right{transform:rotateY(90deg) translateZ(48px)}
.diceFace.left{transform:rotateY(-90deg) translateZ(48px)}
.diceFace.top{transform:rotateX(90deg) translateZ(48px)}
.diceFace.bottom{transform:rotateX(-90deg) translateZ(48px)}
.pip{
  position:absolute;
  width:16px;
  height:16px;
  border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#444 0%,#050505 70%);
  box-shadow:inset 2px 2px 3px rgba(255,255,255,.13),0 2px 3px rgba(0,0,0,.55);
}
.pip.tl{left:20px;top:20px}
.pip.tr{right:20px;top:20px}
.pip.bl{left:20px;bottom:20px}
.pip.br{right:20px;bottom:20px}
.pip.center{left:50%;top:50%;transform:translate(-50%,-50%)}
.pip.ml{left:20px;top:50%;transform:translateY(-50%)}
.pip.mr{right:20px;top:50%;transform:translateY(-50%)}
.realDice.show-1{transform:rotateX(-18deg) rotateY(24deg)}
.realDice.show-2{transform:rotateX(72deg) rotateY(24deg)}
.realDice.show-3{transform:rotateX(-18deg) rotateY(204deg)}
.realDice.show-4{transform:rotateX(-18deg) rotateY(-66deg)}
.realDice.show-5{transform:rotateX(-108deg) rotateY(24deg)}
.realDice.show-6{transform:rotateX(72deg) rotateY(24deg)}


.ownerMark{
  position:absolute;
  width:42px;
  height:16px;
  border-radius:9px;
  border:1px solid rgba(255,255,255,.75);
  box-shadow:0 0 12px rgba(0,0,0,.85),0 0 10px currentColor;
  z-index:7;
}
.ownerIcon{
  position:absolute;
  width:25px;
  height:25px;
  border-radius:50%;
  display:grid;
  place-items:center;
  font-size:16px;
  background:rgba(0,0,0,.82);
  border:1px solid #ffe39b;
  box-shadow:0 0 9px rgba(212,175,55,.65);
  z-index:8;
}
.house.ownerHouse{
  border-radius:7px;
  padding:1px 3px;
}


/* Masadaki eski görselin içinde kalan çift zar + 7 ve eski 1EV/2EV panelini kapatır */
.imageMask{
  position:absolute;
  background:
    radial-gradient(circle at center,rgba(40,24,5,.72),rgba(0,0,0,.94) 68%),
    linear-gradient(135deg,rgba(16,16,16,.98),rgba(0,0,0,.98));
  border:1px solid rgba(212,175,55,.22);
  box-shadow:inset 0 0 18px rgba(212,175,55,.06);
  z-index:18;
  pointer-events:none;
}
.diceMask{
  left:38.8%;
  top:42.2%;
  width:24%;
  height:16%;
  border-radius:50%;
}
.buildMarketMask{
  left:49.5%;
  bottom:2.5%;
  width:44%;
  height:10.5%;
  border-radius:14px;
}


.moneyToast{
  position:absolute;
  left:50%;
  top:34%;
  transform:translate(-50%,-50%);
  min-width:260px;
  max-width:520px;
  padding:14px 22px;
  border-radius:18px;
  border:1px solid #d4af37;
  background:rgba(0,0,0,.86);
  color:#00ff66;
  font-size:20px;
  font-weight:900;
  text-align:center;
  text-shadow:0 0 10px rgba(0,255,102,.65);
  box-shadow:0 0 28px rgba(212,175,55,.38), inset 0 0 14px rgba(0,255,102,.08);
  z-index:90;
  opacity:0;
  pointer-events:none;
  transition:opacity .25s ease, transform .25s ease;
}
.moneyToast.show{
  opacity:1;
  transform:translate(-50%,-50%) scale(1.04);
}
.moneyPlus{color:#00ff66}
.moneyMinus{color:#ff4d4d}


.rollButtonOnBoard{
  position:absolute;
  left:50%;
  bottom:1.8%;
  transform:translateX(-50%);
  width:230px;
  padding:13px 22px;
  border-radius:18px;
  border:1px solid #ffe39b;
  background:linear-gradient(180deg,#ffe39b,#b87912 55%,#5a3203);
  color:#1b0d00;
  font-size:22px;
  font-weight:900;
  letter-spacing:1px;
  text-shadow:0 1px 0 rgba(255,255,255,.45);
  box-shadow:0 0 24px rgba(212,175,55,.45),0 10px 20px rgba(0,0,0,.8);
  z-index:95;
  cursor:pointer;
}
.rollButtonOnBoard:hover{
  filter:brightness(1.13);
  transform:translateX(-50%) scale(1.03);
}

@media(max-width:900px){.home{background-size:cover;background-position:center top}.topbar{height:auto;gap:10px}.topRight{flex-wrap:wrap;justify-content:flex-end}.topBtn{display:none;min-width:145px;font-size:14px}.bottomCards{display:none}.bottomMain{bottom:86px;gap:10px}.bigAction{height:58px;font-size:16px;max-width:46vw}.sidePanel{left:8px;top:84px}}




.homeCenterButtons{
  position:absolute!important;
  left:50%!important;
  top:70%!important;
  transform:translate(-50%,-50%)!important;
  z-index:45!important;
  display:flex!important;
  flex-direction:column!important;
  align-items:center!important;
  gap:12px!important;
  width:min(390px,88vw)!important;
}
.homeCenterButtons .mainGoldBtn,
.homeCenterButtons .mainDarkBtn{
  width:100%!important;
  height:58px!important;
  border-radius:32px!important;
  border:1px solid rgba(212,175,55,.78)!important;
  color:#fff!important;
  font-size:21px!important;
  font-weight:900!important;
  letter-spacing:.4px!important;
  cursor:pointer!important;
  text-shadow:0 2px 5px #000!important;
  transition:.22s!important;
}
.homeCenterButtons .mainGoldBtn{
  background:linear-gradient(180deg,#f4d47d 0%,#c08b31 45%,#80500e 78%,#3d2203 100%)!important;
  border-color:rgba(255,226,151,.95)!important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.38),
    inset 0 -10px 18px rgba(0,0,0,.24),
    0 0 24px rgba(212,175,55,.42)!important;
}
.homeCenterButtons .mainDarkBtn{
  background:
    radial-gradient(circle at 50% 0%,rgba(212,175,55,.15),transparent 48%),
    linear-gradient(180deg,rgba(18,18,18,.98) 0%,rgba(6,6,6,.96) 72%,rgba(0,0,0,.98) 100%)!important;
  border-color:rgba(212,175,55,.70)!important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.08),
    inset 0 0 20px rgba(212,175,55,.05),
    0 0 18px rgba(0,0,0,.72)!important;
}
.homeCenterButtons .mainGoldBtn:hover,
.homeCenterButtons .mainDarkBtn:hover{
  transform:translateY(-2px)!important;
  box-shadow:
    0 0 30px rgba(212,175,55,.62),
    inset 0 0 18px rgba(212,175,55,.10)!important;
}

/* REAL 3D CUBE DICE */
.diceBox{
  position:absolute;
  left:50%;
  top:50%;
  transform:translate(-50%,-50%);
  z-index:80;
  perspective:1000px;
  width:120px;
  height:120px;
  pointer-events:none;
}
.realDice{
  width:96px;
  height:96px;
  position:absolute;
  left:50%;
  top:50%;
  margin-left:-48px;
  margin-top:-48px;
  transform-style:preserve-3d;
  transform:rotateX(-18deg) rotateY(24deg);
  transition:transform .55s cubic-bezier(.2,.8,.2,1);
  filter:drop-shadow(0 24px 18px rgba(0,0,0,.95)) drop-shadow(0 0 12px rgba(255,255,255,.25));
}
.realDice.rolling{
  animation:realDiceRoll .85s linear infinite;
}
@keyframes realDiceRoll{
  0%{transform:rotateX(0deg) rotateY(0deg) rotateZ(0deg)}
  100%{transform:rotateX(720deg) rotateY(540deg) rotateZ(360deg)}
}
.diceFace{
  position:absolute;
  width:96px;
  height:96px;
  border-radius:18px;
  background:
    radial-gradient(circle at 30% 22%,rgba(255,255,255,.95),transparent 26%),
    linear-gradient(145deg,#ffffff 0%,#e8e8e8 52%,#8d8d8d 100%);
  border:3px solid #ffffff;
  box-shadow:
    inset -12px -12px 22px rgba(0,0,0,.24),
    inset 9px 9px 18px rgba(255,255,255,.82),
    0 0 16px rgba(255,255,255,.18);
  transform-style:preserve-3d;
}
.diceFace.front{transform:translateZ(48px)}
.diceFace.back{transform:rotateY(180deg) translateZ(48px)}
.diceFace.right{transform:rotateY(90deg) translateZ(48px)}
.diceFace.left{transform:rotateY(-90deg) translateZ(48px)}
.diceFace.top{transform:rotateX(90deg) translateZ(48px)}
.diceFace.bottom{transform:rotateX(-90deg) translateZ(48px)}
.pip{
  position:absolute;
  width:16px;
  height:16px;
  border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#444 0%,#050505 70%);
  box-shadow:inset 2px 2px 3px rgba(255,255,255,.13),0 2px 3px rgba(0,0,0,.55);
}
.pip.tl{left:20px;top:20px}
.pip.tr{right:20px;top:20px}
.pip.bl{left:20px;bottom:20px}
.pip.br{right:20px;bottom:20px}
.pip.center{left:50%;top:50%;transform:translate(-50%,-50%)}
.pip.ml{left:20px;top:50%;transform:translateY(-50%)}
.pip.mr{right:20px;top:50%;transform:translateY(-50%)}
.realDice.show-1{transform:rotateX(-18deg) rotateY(24deg)}
.realDice.show-2{transform:rotateX(72deg) rotateY(24deg)}
.realDice.show-3{transform:rotateX(-18deg) rotateY(204deg)}
.realDice.show-4{transform:rotateX(-18deg) rotateY(-66deg)}
.realDice.show-5{transform:rotateX(-108deg) rotateY(24deg)}
.realDice.show-6{transform:rotateX(72deg) rotateY(24deg)}


.ownerMark{
  position:absolute;
  width:42px;
  height:16px;
  border-radius:9px;
  border:1px solid rgba(255,255,255,.75);
  box-shadow:0 0 12px rgba(0,0,0,.85),0 0 10px currentColor;
  z-index:7;
}
.ownerIcon{
  position:absolute;
  width:25px;
  height:25px;
  border-radius:50%;
  display:grid;
  place-items:center;
  font-size:16px;
  background:rgba(0,0,0,.82);
  border:1px solid #ffe39b;
  box-shadow:0 0 9px rgba(212,175,55,.65);
  z-index:8;
}
.house.ownerHouse{
  border-radius:7px;
  padding:1px 3px;
}


/* Masadaki eski görselin içinde kalan çift zar + 7 ve eski 1EV/2EV panelini kapatır */
.imageMask{
  position:absolute;
  background:
    radial-gradient(circle at center,rgba(40,24,5,.72),rgba(0,0,0,.94) 68%),
    linear-gradient(135deg,rgba(16,16,16,.98),rgba(0,0,0,.98));
  border:1px solid rgba(212,175,55,.22);
  box-shadow:inset 0 0 18px rgba(212,175,55,.06);
  z-index:18;
  pointer-events:none;
}
.diceMask{
  left:38.8%;
  top:42.2%;
  width:24%;
  height:16%;
  border-radius:50%;
}
.buildMarketMask{
  left:49.5%;
  bottom:2.5%;
  width:44%;
  height:10.5%;
  border-radius:14px;
}


.moneyToast{
  position:absolute;
  left:50%;
  top:34%;
  transform:translate(-50%,-50%);
  min-width:260px;
  max-width:520px;
  padding:14px 22px;
  border-radius:18px;
  border:1px solid #d4af37;
  background:rgba(0,0,0,.86);
  color:#00ff66;
  font-size:20px;
  font-weight:900;
  text-align:center;
  text-shadow:0 0 10px rgba(0,255,102,.65);
  box-shadow:0 0 28px rgba(212,175,55,.38), inset 0 0 14px rgba(0,255,102,.08);
  z-index:90;
  opacity:0;
  pointer-events:none;
  transition:opacity .25s ease, transform .25s ease;
}
.moneyToast.show{
  opacity:1;
  transform:translate(-50%,-50%) scale(1.04);
}
.moneyPlus{color:#00ff66}
.moneyMinus{color:#ff4d4d}


.rollButtonOnBoard{
  position:absolute;
  left:50%;
  bottom:1.8%;
  transform:translateX(-50%);
  width:230px;
  padding:13px 22px;
  border-radius:18px;
  border:1px solid #ffe39b;
  background:linear-gradient(180deg,#ffe39b,#b87912 55%,#5a3203);
  color:#1b0d00;
  font-size:22px;
  font-weight:900;
  letter-spacing:1px;
  text-shadow:0 1px 0 rgba(255,255,255,.45);
  box-shadow:0 0 24px rgba(212,175,55,.45),0 10px 20px rgba(0,0,0,.8);
  z-index:95;
  cursor:pointer;
}
.rollButtonOnBoard:hover{
  filter:brightness(1.13);
  transform:translateX(-50%) scale(1.03);
}

@media(max-width:900px){
  .homeCenterButtons{top:70%!important;width:min(340px,86vw)!important}
  .homeCenterButtons .mainGoldBtn,.homeCenterButtons .mainDarkBtn{height:52px!important;font-size:17px!important}
}


.homeCenterButtons .mainGoldBtn,
.homeCenterButtons .mainDarkBtn{
  height:52px!important;
  font-size:18px!important;
}
.homeCenterButtons{
  gap:9px!important;
}


.wheelWrap{position:relative;width:230px;height:230px;margin:12px auto}
.wheelPointer{position:absolute;left:50%;top:-8px;transform:translateX(-50%);color:#d4af37;font-size:26px;z-index:2;text-shadow:0 0 8px #000}
.dailyWheel{
  width:230px;height:230px;border-radius:50%;border:4px solid #d4af37;position:relative;overflow:hidden;
  background:conic-gradient(#1a1a1a 0 60deg,#4a3009 60deg 120deg,#111 120deg 180deg,#7a4d09 180deg 240deg,#191919 240deg 300deg,#b78b29 300deg 360deg);
  box-shadow:0 0 25px rgba(212,175,55,.45), inset 0 0 20px rgba(0,0,0,.6);
  transition:transform 3.2s cubic-bezier(.12,.77,.17,1);
}
.slice{position:absolute;color:#fff;font-weight:900;text-shadow:0 2px 4px #000;font-size:18px}
.s1{left:145px;top:38px}.s2{left:165px;top:108px}.s3{left:122px;top:170px}.s4{left:48px;top:166px}.s5{left:22px;top:98px}.s6{left:65px;top:36px}
.spinBtn{width:180px;margin:10px auto;display:block}
.locaBtn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  border:1px solid #d4af37;border-radius:12px;background:rgba(0,0,0,.62);color:#d4af37;
  padding:10px 14px;font-weight:900;text-decoration:none;box-shadow:0 0 14px rgba(212,175,55,.22)
}


.homeCenterButtons{
  top:70%!important;
  gap:8px!important;
}
.homeCenterButtons .mainGoldBtn,
.homeCenterButtons .mainDarkBtn{
  height:50px!important;
  font-size:17px!important;
}

/* FINAL_REAL_CENTER_BUTTONS */

.homeCenterButtons{
  position:absolute!important;
  left:50%!important;
  top:70%!important;
  transform:translate(-50%,-50%)!important;
  z-index:45!important;
  display:flex!important;
  flex-direction:column!important;
  align-items:center!important;
  gap:8px!important;
  width:min(390px,88vw)!important;
}
.homeCenterButtons .mainGoldBtn,
.homeCenterButtons .mainDarkBtn{
  width:100%!important;
  height:50px!important;
  border-radius:32px!important;
  border:1px solid rgba(212,175,55,.78)!important;
  color:#fff!important;
  font-size:17px!important;
  font-weight:900!important;
  cursor:pointer!important;
  text-shadow:0 2px 5px #000!important;
}
.homeCenterButtons .mainGoldBtn{
  background:linear-gradient(180deg,#f4d47d 0%,#c08b31 45%,#80500e 78%,#3d2203 100%)!important;
  border-color:rgba(255,226,151,.95)!important;
}
.homeCenterButtons .mainDarkBtn{
  background:radial-gradient(circle at 50% 0%,rgba(212,175,55,.15),transparent 48%),linear-gradient(180deg,rgba(18,18,18,.98) 0%,rgba(6,6,6,.96) 72%,rgba(0,0,0,.98) 100%)!important;
}

</style>
</head>
<body>
<div class="home">
  <header class="topbar">
    <button class="menuTop" onclick="toggleMenu()"><span data-i18n="menu">☰ MENU</span></button>
    <div class="topRight">
      <button class="topBtn" onclick="openAuthHome()"><span data-i18n="login">👤 ÜYELİK / GİRİŞ</span></button>
      <button class="topBtn premium" onclick="location.href='/premium'"><span data-i18n="premium">♛ PREMIUM ÜYELİK</span></button>
  </header>

  <div class="homeCenterButtons">
    <button class="mainGoldBtn" onclick="toggleGames()">OYUNLAR</button>
    <button class="mainDarkBtn" onclick="location.href='/tarot'">🔮 TAROT & RİTÜEL</button>
    <button class="mainDarkBtn" onclick="openAuthHome()">👤 ÜYELİK / GİRİŞ</button>
    <button class="mainDarkBtn" onclick="location.href='/premium'">💎 PREMIUM ÜYELİK</button>
  </div>


  

  <aside id="sidePanel" class="sidePanel">
    <div class="panelSection">
      <div class="panelTitle">MENU</div>
      <a class="panelLink" href="/ai-tarot-premium"><b>💎</b><span data-i18n="ai">AI TAROT PREMIUM</span></a>
      <a class="panelLink" href="/turnuvalar"><b>🏆</b><span data-i18n="tournaments">TURNUVALAR</span></a>
      <a class="panelLink" href="/arkadaslar"><b>👥</b><span data-i18n="friends">ARKADAŞLAR</span></a>
      <a class="panelLink" href="#" onclick="openSettingsPanel();return false;"><b>⚙️</b><span data-i18n="settings">AYARLAR</span></a>
      <a class="panelLink" href="/kasa"><b>🪙</b><span data-i18n="cashier">Londres KASASI</span></a>
      <a class="panelLink" href="/oyun-kurallari"><b>📜</b><span data-i18n="rules">OYUN KURALLARI</span></a>
      <a class="panelLink" href="/sandiklar"><b>🎁</b><span data-i18n="chests">SANDIK SİSTEMİ</span></a>
      <a class="panelLink" href="/profil-magazasi"><b>🎨</b><span data-i18n="custom">PROFİL ÖZELLEŞTİRME</span></a>
      <a class="panelLink" href="#" onclick="openProfileHome();return false;"><b>🏆</b><span data-i18n="profile">PROFİL / XP</span></a>
    <a class="panelLink" href="#" onclick="openAvatarModal();return false;"><b>🖼️</b>AVATAR FOTOĞRAFI</a>
</div>
    <div class="panelSection" id="settingsPart">
      <div class="panelTitle"><span data-i18n="settings">AYARLAR</span></div>
      <div class="setting"><h3><span data-i18n="language">🌍 Dil</span></h3><select id="montenoirLangSelect" onchange="setMontenoirLang(this.value)"><option value="tr">🇹🇷 Türkçe</option><option value="fr">🇫🇷 Français</option><option value="en">🇬🇧 English</option><option value="es">🇪🇸 Español</option><option value="de">🇩🇪 Deutsch</option><option value="it">🇮🇹 Italiano</option><option value="pt">🇵🇹 Português</option><option value="nl">🇳🇱 Nederlands</option><option value="ro">🇷🇴 Română</option><option value="ar">🇸🇦 العربية</option><option value="ru">🇷🇺 Русский</option></select></div>
      <div class="setting"><h3><span data-i18n="rulesTitle">📜 Kurallar</span></h3><p><span data-i18n="rulesText">Saygılı oyun, hile yasak, uygunsuz davranış yasak.</span></p></div>
      <div class="setting"><h3><span data-i18n="theme">🎨 Tema</span></h3><p><span data-i18n="themeText">Siyah & altın Londres teması aktif.</span></p></div>
      <div class="setting"><h3><span data-i18n="notifications">🔔 Bildirimler</span></h3><p><span data-i18n="notificationsText">Turnuva, sandık, özel mesaj ve davet bildirimleri yakında.</span></p></div>
      <div class="setting"><h3><span data-i18n="privacy">🔐 Gizlilik</span></h3><p><span data-i18n="privacyText">Email diğer oyunculara gösterilmez.</span></p></div>
      <div class="setting"><h3><span data-i18n="help">❓ Yardım</span></h3><p><span data-i18n="helpText">Oyun kuralları ve destek bölümü yakında.</span></p></div>
    </div>
  </aside>

  <section id="gamesPanel" class="gamesPanel">
    <div class="panelTitle">🎮 <span data-i18n="games">OYUNLAR</span></div>
    <div class="gameGrid">
      <a href="/codenames">👑 Codenames VIP</a><a href="/coming-soon/Poker">♠️ Poker</a>
      <a href="/coming-soon/Tavla">🎲 Tavla</a><a href="/coming-soon/Okey">🀄 Okey</a>
      <a href="/coming-soon/101">💎 101</a><a href="/monopoly">🏙️ Monopoly</a>
      <a href="/coming-soon/Ludo">🔴 Ludo</a><a href="/coming-soon/Bowling">🎳 Bowling</a>
    </div>
  </section>

  <div class="bottomCards">
    <div class="card"><div class="cardIcon">🎁</div><div class="cardText"><span data-i18n="daily">GÜNLÜK ÖDÜL</span><small><span data-i18n="dailyText">Hediyeni almayı unutma!</span></small></div><button onclick="openDailyWheel()">AL</button></div>
    <div class="card"><div class="cardIcon">🏆</div><div class="cardText"><span data-i18n="active">AKTİF TURNUVA</span><small><span data-i18n="activeText">Haftalık Codenames Turnuvası</span></small></div><button onclick="location.href='/turnuvalar'"><span data-i18n="join">KATIL</span></button></div>
    <div class="card"><div class="cardIcon">⭐</div><div class="cardText"><span data-i18n="vipPoints">VIP PUANIN</span><small>12.450</small></div><button onclick="openProfileHome()"><span data-i18n="details">DETAYLAR</span></button></div>
  </div>
</div>

<div id="homeAuthModal" class="modal"><div class="modalBox"><button class="closeBtn" onclick="closeHomeModals()">X</button><h2>👤 Üyelik</h2><h3>📝 Kayıt Ol</h3><input id="hRegUsername" placeholder="Kullanıcı adı"><input id="hRegEmail" type="email" placeholder="Email"><select id="hRegGender" style="width:100%;margin:7px 0;padding:12px;border-radius:12px;border:1px solid #d4af37;background:#090909;color:#fff"><option value="">Cinsiyet seç</option><option value="female">♠️ Kadın</option><option value="male">♣️ Erkek</option></select><input id="hRegPassword" type="password" placeholder="Şifre"><input id="hRegPassword2" type="password" placeholder="Şifre tekrar"><button onclick="homeRegister()">Kayıt Ol</button><hr><h3>🔐 Giriş Yap</h3><input id="hLoginUsername" placeholder="Kullanıcı adı"><input id="hLoginPassword" type="password" placeholder="Şifre"><button onclick="homeLogin()">Giriş Yap</button><button onclick="homeLogout()">Çıkış Yap</button><div id="homeAuthStatus">Henüz giriş yapılmadı.</div></div></div>
<div id="homeProfileModal" class="modal"><div class="modalBox"><button class="closeBtn" onclick="closeHomeModals()">X</button><h2>🏆 Profil / XP</h2><div id="homeProfileBox">Giriş yapmadın.</div><button onclick="location.href='/codenames'">🎮 Codenames VIP’e Git</button></div></div>

<script>
function getSavedUser(){return localStorage.getItem("montenoirUser") || localStorage.getItem("codenamesAccount") || localStorage.getItem("loggedUser") || ""}
function saveUserProfile(profile){if(!profile||!profile.username)return;localStorage.setItem("montenoirUser",profile.username);localStorage.setItem("codenamesAccount",profile.username);localStorage.setItem("loggedUser",profile.username);localStorage.setItem("loggedIn","true");localStorage.setItem("montenoirProfile",JSON.stringify(profile));localStorage.setItem("codenamesProfile",JSON.stringify(profile));renderUserTop(profile)}
function renderUserTop(profile){if(profile&&profile.username){document.getElementById("miniUser") && (miniUser.innerText=profile.username);document.getElementById("userBlock") && userBlock.classList.add("show")}else{document.getElementById("miniUser") && (miniUser.innerText="Üye");document.getElementById("userBlock") && userBlock.classList.remove("show")}}
function loadSavedProfile(){let raw=localStorage.getItem("montenoirProfile")||localStorage.getItem("codenamesProfile");if(raw){try{renderUserTop(JSON.parse(raw))}catch(e){}}let u=getSavedUser();if(u){fetch("/api/auth/profile?username="+encodeURIComponent(u)).then(r=>r.json()).then(d=>{if(d.ok&&d.profile)saveUserProfile(d.profile);else renderUserTop(null)}).catch(()=>{})}else renderUserTop(null)}
function toggleMenu(){sidePanel.classList.toggle('show');gamesPanel.classList.remove('show')}
function openSettingsPanel(){sidePanel.classList.add('show');setTimeout(()=>settingsPart.scrollIntoView({behavior:'smooth'}),100)}
function toggleGames(){gamesPanel.classList.toggle('show');sidePanel.classList.remove('show')}
function closeHomeModals(){homeAuthModal.style.display='none';homeProfileModal.style.display='none'}
function openAuthHome(){homeAuthModal.style.display='flex';let u=getSavedUser();homeAuthStatus.innerHTML=u?"Aktif kullanıcı: "+u:"Henüz giriş yapılmadı."}
function openProfileHome(){homeProfileModal.style.display='flex';let u=getSavedUser();if(!u){homeProfileBox.innerHTML='Giriş yapmadın. Önce üyelik/giriş yap.';return}homeProfileBox.innerHTML='Profil yükleniyor...';fetch("/api/auth/profile?username="+encodeURIComponent(u)).then(r=>r.json()).then(d=>{if(d.ok&&d.profile){saveUserProfile(d.profile);let p=d.profile;homeProfileBox.innerHTML='<b>👤 '+p.username+'</b><br>⭐ Seviye: '+(p.level||1)+'<br>🏆 XP: '+(p.xp||0)+'<br>🪙 Jeton: '+(p.chips||0)+'<br>🎖️ Rozet: '+(p.membershipLabel||'Yok')}else homeProfileBox.innerHTML=d.msg||"Profil bulunamadı."})}
function homeRegister(){let u=hRegUsername.value.trim(),e=hRegEmail.value.trim(),p=hRegPassword.value,p2=hRegPassword2.value;if(!u||!e||!p||!p2){alert('Tüm alanları doldur.');return}fetch("/api/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u,email:e,password:p,password2:p2,gender:(document.getElementById("hRegGender")?hRegGender.value:"")})}).then(r=>r.json()).then(d=>{homeAuthStatus.innerHTML=d.msg||JSON.stringify(d);if(d.ok&&d.profile){saveUserProfile(d.profile);closeHomeModals()}})}
function homeLogin(){let u=hLoginUsername.value.trim(),p=hLoginPassword.value;if(!u||!p){alert('Kullanıcı adı ve şifre yaz.');return}fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u,password:p})}).then(r=>r.json()).then(d=>{homeAuthStatus.innerHTML=d.msg||JSON.stringify(d);if(d.ok&&d.profile){saveUserProfile(d.profile);closeHomeModals()}})}
function homeLogout(){localStorage.removeItem("montenoirUser");localStorage.removeItem("montenoirProfile");localStorage.removeItem("codenamesAccount");localStorage.removeItem("loggedUser");localStorage.removeItem("loggedIn");localStorage.removeItem("codenamesProfile");renderUserTop(null);homeAuthStatus.innerHTML='Çıkış yapıldı.'}
document.addEventListener("DOMContentLoaded",loadSavedProfile);setTimeout(loadSavedProfile,250)
</script>

<script>
(function(){
const I18N = {
tr:{
menu:"☰ MENU", login:"👤 ÜYELİK / GİRİŞ", premium:"♛ PREMIUM ÜYELİK",
games:"OYUNLAR", tarot:"TAROT & RİTÜEL", ai:"AI TAROT PREMIUM", tournaments:"TURNUVALAR",
friends:"ARKADAŞLAR", settings:"AYARLAR", cashier:"Londres KASASI", rules:"OYUN KURALLARI",
chests:"SANDIK SİSTEMİ", custom:"PROFİL ÖZELLEŞTİRME", profile:"PROFİL / XP",
language:"🌍 Dil", rulesTitle:"📜 Kurallar", rulesText:"Saygılı oyun, hile yasak, uygunsuz davranış yasak.",
theme:"🎨 Tema", themeText:"Siyah & altın Londres teması aktif.",
notifications:"🔔 Bildirimler", notificationsText:"Turnuva, sandık, özel mesaj ve davet bildirimleri yakında.",
privacy:"🔐 Gizlilik", privacyText:"Email diğer oyunculara gösterilmez.",
help:"❓ Yardım", helpText:"Oyun kuralları ve destek bölümü yakında.",
daily:"GÜNLÜK ÖDÜL", dailyText:"Hediyeni almayı unutma!", active:"AKTİF TURNUVA",
activeText:"Haftalık Codenames Turnuvası", vipPoints:"VIP PUANIN", take:"AL", join:"KATIL", details:"DETAYLAR",
register:"📝 Kayıt Ol", username:"Kullanıcı adı", email:"Email", password:"Şifre", password2:"Şifre tekrar",
registerBtn:"Kayıt Ol", loginTitle:"🔐 Giriş Yap", loginBtn:"Giriş Yap", logoutBtn:"Çıkış Yap",
notLogged:"Henüz giriş yapılmadı.", notLoggedProfile:"Giriş yapmadın. Önce üyelik/giriş yap.", profileLoading:"Profil yükleniyor..."
},
fr:{
menu:"☰ MENU", login:"👤 ABONNEMENT / CONNEXION", premium:"♛ ABONNEMENT PREMIUM",
games:"JEUX", tarot:"TAROT & RITUEL", ai:"TAROT IA PREMIUM", tournaments:"TOURNOIS",
friends:"AMIS", settings:"PARAMÈTRES", cashier:"CAISSE Londres", rules:"RÈGLES DU JEU",
chests:"SYSTÈME DE COFFRES", custom:"PERSONNALISATION DU PROFIL", profile:"PROFIL / XP",
language:"🌍 Langue", rulesTitle:"📜 Règles", rulesText:"Jeu respectueux, triche interdite, comportement abusif interdit.",
theme:"🎨 Thème", themeText:"Le thème noir et or Londres est actif.",
notifications:"🔔 Notifications", notificationsText:"Notifications de tournois, coffres, messages privés et invitations bientôt.",
privacy:"🔐 Confidentialité", privacyText:"L’e-mail n’est pas affiché aux autres joueurs.",
help:"❓ Aide", helpText:"Règles du jeu et assistance bientôt disponibles.",
daily:"RÉCOMPENSE QUOTIDIENNE", dailyText:"N’oublie pas de récupérer ton cadeau !", active:"TOURNOI ACTIF",
activeText:"Tournoi Codenames hebdomadaire", vipPoints:"TES POINTS VIP", take:"PRENDRE", join:"PARTICIPER", details:"DÉTAILS",
register:"📝 Inscription", username:"Nom d’utilisateur", email:"Email", password:"Mot de passe", password2:"Confirmer le mot de passe",
registerBtn:"S’inscrire", loginTitle:"🔐 Connexion", loginBtn:"Se connecter", logoutBtn:"Déconnexion",
notLogged:"Aucune connexion pour le moment.", notLoggedProfile:"Tu n’es pas connecté. Connecte-toi d’abord.", profileLoading:"Chargement du profil..."
},
en:{
menu:"☰ MENU", login:"👤 MEMBERSHIP / LOGIN", premium:"♛ PREMIUM MEMBERSHIP",
games:"GAMES", tarot:"TAROT & RITUAL", ai:"PREMIUM AI TAROT", tournaments:"TOURNAMENTS",
friends:"FRIENDS", settings:"SETTINGS", cashier:"Londres CASHIER", rules:"GAME RULES",
chests:"CHEST SYSTEM", custom:"PROFILE CUSTOMIZATION", profile:"PROFILE / XP",
language:"🌍 Language", rulesTitle:"📜 Rules", rulesText:"Respectful play, no cheating, no abusive behavior.",
theme:"🎨 Theme", themeText:"The black and gold Londres theme is active.",
notifications:"🔔 Notifications", notificationsText:"Tournament, chest, private message and invite notifications coming soon.",
privacy:"🔐 Privacy", privacyText:"Email is not shown to other players.",
help:"❓ Help", helpText:"Game rules and support coming soon.",
daily:"DAILY REWARD", dailyText:"Don’t forget to claim your gift!", active:"ACTIVE TOURNAMENT",
activeText:"Weekly Codenames Tournament", vipPoints:"YOUR VIP POINTS", take:"CLAIM", join:"JOIN", details:"DETAILS",
register:"📝 Register", username:"Username", email:"Email", password:"Password", password2:"Confirm password",
registerBtn:"Register", loginTitle:"🔐 Login", loginBtn:"Login", logoutBtn:"Logout",
notLogged:"Not logged in yet.", notLoggedProfile:"You are not logged in. Please log in first.", profileLoading:"Loading profile..."
},
es:{
menu:"☰ MENÚ", login:"👤 MEMBRESÍA / ENTRAR", premium:"♛ MEMBRESÍA PREMIUM",
games:"JUEGOS", tarot:"TAROT Y RITUAL", ai:"TAROT IA PREMIUM", tournaments:"TORNEOS",
friends:"AMIGOS", settings:"AJUSTES", cashier:"CAJA Londres", rules:"REGLAS DEL JUEGO",
chests:"SISTEMA DE COFRES", custom:"PERSONALIZACIÓN DEL PERFIL", profile:"PERFIL / XP",
language:"🌍 Idioma", rulesTitle:"📜 Reglas", rulesText:"Juego respetuoso, trampas prohibidas, comportamiento abusivo prohibido.",
theme:"🎨 Tema", themeText:"El tema negro y dorado Londres está activo.",
notifications:"🔔 Notificaciones", notificationsText:"Notificaciones de torneos, cofres, mensajes privados e invitaciones próximamente.",
privacy:"🔐 Privacidad", privacyText:"El email no se muestra a otros jugadores.",
help:"❓ Ayuda", helpText:"Reglas del juego y soporte próximamente.",
daily:"RECOMPENSA DIARIA", dailyText:"¡No olvides reclamar tu regalo!", active:"TORNEO ACTIVO",
activeText:"Torneo semanal de Codenames", vipPoints:"TUS PUNTOS VIP", take:"RECLAMAR", join:"UNIRSE", details:"DETALLES",
register:"📝 Registro", username:"Nombre de usuario", email:"Email", password:"Contraseña", password2:"Confirmar contraseña",
registerBtn:"Registrarse", loginTitle:"🔐 Entrar", loginBtn:"Entrar", logoutBtn:"Salir",
notLogged:"Aún no has iniciado sesión.", notLoggedProfile:"No has iniciado sesión. Entra primero.", profileLoading:"Cargando perfil..."
},
de:{
menu:"☰ MENU", login:"👤 MITGLIEDSCHAFT / LOGIN", premium:"♛ PREMIUM-MITGLIEDSCHAFT",
games:"SPIELE", tarot:"TAROT & RITUAL", ai:"PREMIUM KI-TAROT", tournaments:"TURNIERE",
friends:"FREUNDE", settings:"EINSTELLUNGEN", cashier:"Londres KASSE", rules:"SPIELREGELN",
chests:"TRUHENSYSTEM", custom:"PROFIL ANPASSEN", profile:"PROFIL / XP",
language:"🌍 Sprache", rulesTitle:"📜 Regeln", rulesText:"Respektvolles Spielen, Betrug verboten, beleidigendes Verhalten verboten.",
theme:"🎨 Thema", themeText:"Das schwarz-goldene Londres-Theme ist aktiv.",
notifications:"🔔 Benachrichtigungen", notificationsText:"Turnier-, Truhen-, Privatnachrichten- und Einladungsbenachrichtigungen folgen bald.",
privacy:"🔐 Datenschutz", privacyText:"Die E-Mail wird anderen Spielern nicht angezeigt.",
help:"❓ Hilfe", helpText:"Spielregeln und Support folgen bald.",
daily:"TÄGLICHE BELOHNUNG", dailyText:"Vergiss nicht, dein Geschenk abzuholen!", active:"AKTIVES TURNIER",
activeText:"Wöchentliches Codenames-Turnier", vipPoints:"DEINE VIP-PUNKTE", take:"ABHOLEN", join:"TEILNEHMEN", details:"DETAILS",
register:"📝 Registrieren", username:"Benutzername", email:"Email", password:"Passwort", password2:"Passwort bestätigen",
registerBtn:"Registrieren", loginTitle:"🔐 Login", loginBtn:"Einloggen", logoutBtn:"Ausloggen",
notLogged:"Noch nicht eingeloggt.", notLoggedProfile:"Du bist nicht eingeloggt. Bitte zuerst einloggen.", profileLoading:"Profil wird geladen..."
},
it:{
menu:"☰ MENU", login:"👤 ABBONAMENTO / LOGIN", premium:"♛ ABBONAMENTO PREMIUM",
games:"GIOCHI", tarot:"TAROCCHI & RITUALE", ai:"TAROCCHI IA PREMIUM", tournaments:"TORNEI",
friends:"AMICI", settings:"IMPOSTAZIONI", cashier:"CASSA Londres", rules:"REGOLE DEL GIOCO",
chests:"SISTEMA FORZIERI", custom:"PERSONALIZZA PROFILO", profile:"PROFILO / XP",
language:"🌍 Lingua", rulesTitle:"📜 Regole", rulesText:"Gioco rispettoso, trucchi vietati, comportamento abusivo vietato.",
theme:"🎨 Tema", themeText:"Il tema nero e oro Londres è attivo.",
notifications:"🔔 Notifiche", notificationsText:"Notifiche per tornei, forzieri, messaggi privati e inviti presto disponibili.",
privacy:"🔐 Privacy", privacyText:"L’email non viene mostrata agli altri giocatori.",
help:"❓ Aiuto", helpText:"Regole del gioco e supporto presto disponibili.",
daily:"RICOMPENSA GIORNALIERA", dailyText:"Non dimenticare di ritirare il regalo!", active:"TORNEO ATTIVO",
activeText:"Torneo Codenames settimanale", vipPoints:"I TUOI PUNTI VIP", take:"RITIRA", join:"PARTECIPA", details:"DETTAGLI",
register:"📝 Registrazione", username:"Nome utente", email:"Email", password:"Password", password2:"Conferma password",
registerBtn:"Registrati", loginTitle:"🔐 Login", loginBtn:"Accedi", logoutBtn:"Esci",
notLogged:"Non hai ancora effettuato l’accesso.", notLoggedProfile:"Non hai effettuato l’accesso. Accedi prima.", profileLoading:"Caricamento profilo..."
},
pt:{
menu:"☰ MENU", login:"👤 ADESÃO / LOGIN", premium:"♛ ADESÃO PREMIUM",
games:"JOGOS", tarot:"TAROT & RITUAL", ai:"TAROT IA PREMIUM", tournaments:"TORNEIOS",
friends:"AMIGOS", settings:"DEFINIÇÕES", cashier:"CAIXA Londres", rules:"REGRAS DO JOGO",
chests:"SISTEMA DE BAÚS", custom:"PERSONALIZAR PERFIL", profile:"PERFIL / XP",
language:"🌍 Idioma", rulesTitle:"📜 Regras", rulesText:"Jogo respeitoso, batota proibida, comportamento abusivo proibido.",
theme:"🎨 Tema", themeText:"O tema preto e dourado Londres está ativo.",
notifications:"🔔 Notificações", notificationsText:"Notificações de torneios, baús, mensagens privadas e convites em breve.",
privacy:"🔐 Privacidade", privacyText:"O email não é mostrado a outros jogadores.",
help:"❓ Ajuda", helpText:"Regras do jogo e suporte em breve.",
daily:"RECOMPENSA DIÁRIA", dailyText:"Não te esqueças de reclamar o teu presente!", active:"TORNEIO ATIVO",
activeText:"Torneio semanal de Codenames", vipPoints:"OS TEUS PONTOS VIP", take:"RECLAMAR", join:"PARTICIPAR", details:"DETALHES",
register:"📝 Registo", username:"Nome de utilizador", email:"Email", password:"Palavra-passe", password2:"Confirmar palavra-passe",
registerBtn:"Registar", loginTitle:"🔐 Login", loginBtn:"Entrar", logoutBtn:"Sair",
notLogged:"Ainda não tens sessão iniciada.", notLoggedProfile:"Não tens sessão iniciada. Entra primeiro.", profileLoading:"A carregar perfil..."
},
nl:{
menu:"☰ MENU", login:"👤 LIDMAATSCHAP / LOGIN", premium:"♛ PREMIUM LIDMAATSCHAP",
games:"SPELLEN", tarot:"TAROT & RITUEEL", ai:"PREMIUM AI TAROT", tournaments:"TOERNOOIEN",
friends:"VRIENDEN", settings:"INSTELLINGEN", cashier:"Londres KASSA", rules:"SPELREGELS",
chests:"KISTENSYSTEEM", custom:"PROFIEL AANPASSEN", profile:"PROFIEL / XP",
language:"🌍 Taal", rulesTitle:"📜 Regels", rulesText:"Respectvol spelen, vals spelen verboden, beledigend gedrag verboden.",
theme:"🎨 Thema", themeText:"Het zwart-gouden Londres-thema is actief.",
notifications:"🔔 Meldingen", notificationsText:"Meldingen voor toernooien, kisten, privéberichten en uitnodigingen komen binnenkort.",
privacy:"🔐 Privacy", privacyText:"E-mail wordt niet getoond aan andere spelers.",
help:"❓ Hulp", helpText:"Spelregels en ondersteuning binnenkort beschikbaar.",
daily:"DAGELIJKSE BELONING", dailyText:"Vergeet je cadeau niet te claimen!", active:"ACTIEF TOERNOOI",
activeText:"Wekelijks Codenames-toernooi", vipPoints:"JOUW VIP-PUNTEN", take:"CLAIM", join:"MEEDOEN", details:"DETAILS",
register:"📝 Registreren", username:"Gebruikersnaam", email:"Email", password:"Wachtwoord", password2:"Wachtwoord bevestigen",
registerBtn:"Registreren", loginTitle:"🔐 Login", loginBtn:"Inloggen", logoutBtn:"Uitloggen",
notLogged:"Nog niet ingelogd.", notLoggedProfile:"Je bent niet ingelogd. Log eerst in.", profileLoading:"Profiel laden..."
},
ro:{
menu:"☰ MENIU", login:"👤 ABONAMENT / LOGIN", premium:"♛ ABONAMENT PREMIUM",
games:"JOCURI", tarot:"TAROT & RITUAL", ai:"TAROT AI PREMIUM", tournaments:"TURNEE",
friends:"PRIETENI", settings:"SETĂRI", cashier:"CASIERIA Londres", rules:"REGULILE JOCULUI",
chests:"SISTEM DE CUFERE", custom:"PERSONALIZARE PROFIL", profile:"PROFIL / XP",
language:"🌍 Limbă", rulesTitle:"📜 Reguli", rulesText:"Joc respectuos, trișatul este interzis, comportamentul abuziv este interzis.",
theme:"🎨 Temă", themeText:"Tema negru și auriu Londres este activă.",
notifications:"🔔 Notificări", notificationsText:"Notificările pentru turnee, cufere, mesaje private și invitații vin curând.",
privacy:"🔐 Confidențialitate", privacyText:"Emailul nu este afișat altor jucători.",
help:"❓ Ajutor", helpText:"Regulile jocului și suportul vor fi disponibile curând.",
daily:"RECOMPENSĂ ZILNICĂ", dailyText:"Nu uita să-ți revendici cadoul!", active:"TURNEU ACTIV",
activeText:"Turneu Codenames săptămânal", vipPoints:"PUNCTELE TALE VIP", take:"REVENDICĂ", join:"PARTICIPĂ", details:"DETALII",
register:"📝 Înregistrare", username:"Nume utilizator", email:"Email", password:"Parolă", password2:"Confirmă parola",
registerBtn:"Înregistrează-te", loginTitle:"🔐 Login", loginBtn:"Intră", logoutBtn:"Ieși",
notLogged:"Nu ești conectat încă.", notLoggedProfile:"Nu ești conectat. Conectează-te mai întâi.", profileLoading:"Se încarcă profilul..."
},
ar:{
menu:"☰ القائمة", login:"👤 العضوية / الدخول", premium:"♛ عضوية بريميوم",
games:"الألعاب", tarot:"التاروت والطقوس", ai:"تاروت AI بريميوم", tournaments:"البطولات",
friends:"الأصدقاء", settings:"الإعدادات", cashier:"خزينة مونتينوار", rules:"قواعد اللعبة",
chests:"نظام الصناديق", custom:"تخصيص الملف", profile:"الملف / XP",
language:"🌍 اللغة", rulesTitle:"📜 القواعد", rulesText:"اللعب باحترام، الغش ممنوع، والسلوك المسيء ممنوع.",
theme:"🎨 المظهر", themeText:"سمة Londres السوداء والذهبية مفعلة.",
notifications:"🔔 الإشعارات", notificationsText:"إشعارات البطولات والصناديق والرسائل الخاصة والدعوات قريباً.",
privacy:"🔐 الخصوصية", privacyText:"لا يتم عرض البريد الإلكتروني للاعبين الآخرين.",
help:"❓ المساعدة", helpText:"قواعد اللعبة والدعم قريباً.",
daily:"مكافأة يومية", dailyText:"لا تنسَ المطالبة بهديتك!", active:"بطولة نشطة",
activeText:"بطولة Codenames الأسبوعية", vipPoints:"نقاط VIP الخاصة بك", take:"استلام", join:"انضمام", details:"تفاصيل",
register:"📝 تسجيل", username:"اسم المستخدم", email:"البريد الإلكتروني", password:"كلمة المرور", password2:"تأكيد كلمة المرور",
registerBtn:"تسجيل", loginTitle:"🔐 دخول", loginBtn:"دخول", logoutBtn:"خروج",
notLogged:"لم يتم تسجيل الدخول بعد.", notLoggedProfile:"أنت غير متصل. سجّل الدخول أولاً.", profileLoading:"تحميل الملف..."
},
ru:{
menu:"☰ МЕНЮ", login:"👤 ПОДПИСКА / ВХОД", premium:"♛ ПРЕМИУМ-ПОДПИСКА",
games:"ИГРЫ", tarot:"ТАРО И РИТУАЛ", ai:"ПРЕМИУМ AI ТАРО", tournaments:"ТУРНИРЫ",
friends:"ДРУЗЬЯ", settings:"НАСТРОЙКИ", cashier:"КАССА Londres", rules:"ПРАВИЛА ИГРЫ",
chests:"СИСТЕМА СУНДУКОВ", custom:"НАСТРОЙКА ПРОФИЛЯ", profile:"ПРОФИЛЬ / XP",
language:"🌍 Язык", rulesTitle:"📜 Правила", rulesText:"Уважительная игра, мошенничество запрещено, оскорбительное поведение запрещено.",
theme:"🎨 Тема", themeText:"Чёрно-золотая тема Londres активна.",
notifications:"🔔 Уведомления", notificationsText:"Уведомления о турнирах, сундуках, личных сообщениях и приглашениях скоро.",
privacy:"🔐 Конфиденциальность", privacyText:"Email не показывается другим игрокам.",
help:"❓ Помощь", helpText:"Правила игры и поддержка скоро будут доступны.",
daily:"ЕЖЕДНЕВНАЯ НАГРАДА", dailyText:"Не забудь забрать подарок!", active:"АКТИВНЫЙ ТУРНИР",
activeText:"Еженедельный турнир Codenames", vipPoints:"ТВОИ VIP-ОЧКИ", take:"ЗАБРАТЬ", join:"УЧАСТВОВАТЬ", details:"ДЕТАЛИ",
register:"📝 Регистрация", username:"Имя пользователя", email:"Email", password:"Пароль", password2:"Подтвердить пароль",
registerBtn:"Зарегистрироваться", loginTitle:"🔐 Вход", loginBtn:"Войти", logoutBtn:"Выйти",
notLogged:"Вход ещё не выполнен.", notLoggedProfile:"Ты не вошёл. Сначала войди.", profileLoading:"Загрузка профиля..."
}
};
function lang(){return localStorage.getItem("montenoirLang")||"tr"}
function t(k){return (I18N[lang()]||I18N.tr)[k]||I18N.tr[k]||k}
function applyI18n(){
 document.documentElement.lang=lang();
 document.documentElement.dir=lang()==="ar"?"rtl":"ltr";
 document.querySelectorAll("[data-i18n]").forEach(el=>{el.innerText=t(el.dataset.i18n)});
 document.querySelectorAll("[data-i18n-placeholder]").forEach(el=>{el.placeholder=t(el.dataset.i18nPlaceholder)});
 const sel=document.getElementById("montenoirLangSelect"); if(sel) sel.value=lang();
}
window.setMontenoirLang=function(v){localStorage.setItem("montenoirLang",v);applyI18n()}
document.addEventListener("DOMContentLoaded",applyI18n);
setTimeout(applyI18n,300);
})();
</script>

<style>
#montenoirOnlineBox{position:fixed;right:25px;bottom:135px;width:148px;height:92px;z-index:9997;background:rgba(0,0,0,.86);border:1px solid rgba(212,175,55,.75);border-radius:8px;box-shadow:0 0 14px rgba(0,255,90,.22),0 0 18px rgba(212,175,55,.22);overflow:hidden;font-family:Consolas,"Courier New",monospace;color:#00ff66;font-size:10.5px;line-height:17px}
#montenoirOnlineHeader{height:20px;display:flex;align-items:center;justify-content:center;color:#d4af37;font-size:10px;font-weight:bold;letter-spacing:1px;background:rgba(212,175,55,.08);border-bottom:1px solid rgba(212,175,55,.25);text-shadow:0 0 5px rgba(212,175,55,.8)}
#montenoirOnlineViewport{height:70px;overflow:hidden;position:relative}
#montenoirOnlineTrack{position:absolute;left:0;top:0;width:100%;animation:montenoirMatrixScroll 8s linear infinite}
.montenoirOnlineUser{white-space:nowrap;padding:0 8px;color:#00ff66;text-shadow:0 0 6px #00ff66}
@keyframes montenoirMatrixScroll{0%{transform:translateY(0)}100%{transform:translateY(-50%)}}
#montenoirLoginToastWrap{position:fixed;right:12px;bottom:18px;z-index:9999;display:flex;flex-direction:column;gap:8px}
.montenoirLoginToast{min-width:180px;max-width:260px;padding:10px 14px;border-radius:10px;background:rgba(0,0,0,.88);border:1px solid #d4af37;color:#00ff66;font-family:Consolas,"Courier New",monospace;font-size:13px;box-shadow:0 0 18px rgba(0,255,90,.25),0 0 16px rgba(212,175,55,.25);text-shadow:0 0 5px #00ff66;animation:montenoirToastIn .22s ease-out}
@keyframes montenoirToastIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:translateX(0)}}
@media(max-width:700px){#montenoirOnlineBox{width:118px;height:76px;font-size:9px;line-height:15px;right:20px;bottom:125px}#montenoirOnlineHeader{height:18px;font-size:9px}#montenoirOnlineViewport{height:56px}}
</style>
<div id="montenoirOnlineBox"><div id="montenoirOnlineHeader">ONLINE</div><div id="montenoirOnlineViewport"><div id="montenoirOnlineTrack"></div></div></div>
<div id="montenoirLoginToastWrap"></div>
<script>
(function(){
  var onlineSocket=null;
  try{onlineSocket=(typeof io!=="undefined")?io():null;}catch(e){onlineSocket=null;}
  function savedUser(){return localStorage.getItem("montenoirUser")||localStorage.getItem("codenamesAccount")||localStorage.getItem("loggedUser")||""}
  function savedGender(){return localStorage.getItem("montenoirGender")||localStorage.getItem("gender")||""}
  function symbolFor(gender){gender=(gender||"").toLowerCase();if(["female","femme","kadin","kadın","woman","girl"].indexOf(gender)>=0)return"♠️";if(["male","homme","erkek","man","boy"].indexOf(gender)>=0)return"♣️";return"♣️";}
  function renderOnline(users){var track=document.getElementById("montenoirOnlineTrack");if(!track)return;users=users||[];if(!users.length){track.innerHTML='<div class="montenoirOnlineUser">— bekleniyor —</div>';return;}var html=users.map(function(u){var sym=u.symbol||symbolFor(u.gender);var name=(u.username||"").replace(/[<>&]/g,"");return'<div class="montenoirOnlineUser">'+sym+' '+name+'</div>';}).join("");track.innerHTML=html+html;}
  function showToast(user){
    if(!user||!user.username)return;
    var current=(localStorage.getItem("montenoirUser")||localStorage.getItem("codenamesAccount")||localStorage.getItem("loggedUser")||"").toLowerCase();
    var uname=(user.username||"").toLowerCase();
    if(current && uname===current)return;
    window.__montenoirToastSeen=window.__montenoirToastSeen||{};
    var now=Date.now();
    if(window.__montenoirToastSeen[uname] && now-window.__montenoirToastSeen[uname]<6000)return;
    window.__montenoirToastSeen[uname]=now;
    var wrap=document.getElementById("montenoirLoginToastWrap");
    if(!wrap)return;
    var toast=document.createElement("div");
    toast.className="montenoirLoginToast";
    toast.textContent=(user.symbol||symbolFor(user.gender,user.username))+" "+user.username+" giriş yaptı";
    wrap.appendChild(toast);
    setTimeout(function(){toast.remove()},5000);
  }
  function announceOnline(){if(!onlineSocket)return;var u=savedUser();if(u){onlineSocket.emit("montenoir_user_online",{username:u,gender:savedGender()});}else{onlineSocket.emit("montenoir_get_online");}}
  if(onlineSocket){onlineSocket.on("connect",announceOnline);onlineSocket.on("montenoir_online_update",function(data){renderOnline((data&&data.users)||[]);if(data&&data.joined)showToast(data.joined);});}
  document.addEventListener("DOMContentLoaded",function(){
var p=(location.pathname||"/");
if(p!=="/"){
 var b=document.getElementById("montenoirOnlineBox");
 if(b) b.style.display="none";
}
announceOnline();
});setTimeout(announceOnline,500);setInterval(announceOnline,30000);
  var oldSave=window.saveUserProfile;window.saveUserProfile=function(profile){if(oldSave)oldSave(profile);if(profile&&profile.username){localStorage.setItem("montenoirUser",profile.username);if(profile.gender)localStorage.setItem("montenoirGender",profile.gender);setTimeout(announceOnline,100);}};
})();
</script>


<div id="dailyWheelModal" class="modal">
  <div class="modalBox">
    <button class="closeBtn" onclick="closeDailyWheel()">X</button>
    <h2>🎁 Günlük Ödül Çarkı</h2>
    <div class="wheelWrap">
      <div class="wheelPointer">▼</div>
      <div id="dailyWheel" class="dailyWheel">
        <div class="slice s1">30</div><div class="slice s2">50</div><div class="slice s3">100</div>
        <div class="slice s4">300</div><div class="slice s5">1000</div><div class="slice s6">2000</div>
      </div>
    </div>
    <button class="spinBtn" onclick="spinDailyWheel()">ÇEVİR</button>
    <div id="wheelResult" class="status"></div>
  </div>
</div>

<div id="avatarModal" class="modal">
  <div class="modalBox">
    <button class="closeBtn" onclick="closeAvatarModal()">X</button>
    <h2>🖼️ Avatar Fotoğrafı</h2>
    <input id="avatarFile" type="file" accept=".jpg,.jpeg,.png,.webp">
    <button onclick="uploadAvatar()">Avatarı Yükle</button>
    <div id="avatarStatus" class="status"></div>
  </div>
</div>








<script>
function currentMontenoirUser(){return localStorage.getItem("montenoirUser")||localStorage.getItem("codenamesAccount")||localStorage.getItem("loggedUser")||""}
function openDailyWheel(){dailyWheelModal.style.display="flex";wheelResult.innerHTML=""}
function closeDailyWheel(){dailyWheelModal.style.display="none"}
function spinDailyWheel(){
  const u=currentMontenoirUser();
  if(!u){wheelResult.innerHTML="Önce giriş yap.";return;}
  wheelResult.innerHTML="Çark dönüyor...";
  fetch("/api/reward/daily",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:u})})
  .then(r=>r.json()).then(d=>{
    if(!d.ok){wheelResult.innerHTML=d.msg||"Hata";return;}
    const prize=d.prize||30;
    // Her rakamın kendi diliminin merkezine denk gelen açı.
    const angleByPrize={30:330,50:270,100:210,300:150,1000:90,2000:30};
    const deg=1800+(angleByPrize[prize]||330);
    dailyWheel.style.transform="rotate("+deg+"deg)";
    setTimeout(()=>{wheelResult.innerHTML="🎉 "+prize+" jeton kazandın!";},3300);
  }).catch(()=>wheelResult.innerHTML="Bağlantı hatası.");
}
function openAvatarModal(){avatarModal.style.display="flex";avatarStatus.innerHTML=""}
function closeAvatarModal(){avatarModal.style.display="none"}
function uploadAvatar(){const u=currentMontenoirUser();if(!u){avatarStatus.innerHTML="Önce giriş yap.";return;}if(!avatarFile.files[0]){avatarStatus.innerHTML="Dosya seç.";return;}const fd=new FormData();fd.append("username",u);fd.append("avatar",avatarFile.files[0]);fetch("/api/profile/avatar",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{avatarStatus.innerHTML=d.msg||JSON.stringify(d);}).catch(()=>avatarStatus.innerHTML="Yükleme hatası.")} 
</script>

</body>
</html>
"""





COMING_SOON_HTML = r'''
<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Yakında</title><style>body{margin:0;min-height:100vh;background:radial-gradient(circle,#2c2108,#000 65%);color:#f6d777;font-family:Arial;text-align:center;display:flex;align-items:center;justify-content:center}.box{border:2px solid #d4af37;border-radius:28px;padding:45px;max-width:620px;background:rgba(0,0,0,.72);box-shadow:0 0 45px rgba(212,175,55,.45)}h1{font-family:Georgia,serif;font-size:48px}a{display:inline-block;margin-top:18px;padding:14px 20px;border-radius:14px;background:#111;border:1px solid #d4af37;color:#f6d777;text-decoration:none;font-weight:bold}
/* Londres VIP: oyun içinde üyelik/tarot/shop yok; sadece profil + XP */
#tarotTopBtn,#menuAuthBtn,#menuShopBtn{display:none!important;}
.vipProfileChip .xpMini{color:#9fffbf;font-weight:900;margin-left:6px;}
</style></head><body><div class="box"><h1>👑 {{ game }}</h1><h2>Yakında geliyor</h2><p>Bu oyun daha sonra kurallarına göre ayrı ayrı kodlanacak.</p><a href="/">⬅ Ana sayfaya dön</a></div></body></html>
'''

HTML = r'''
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CODENAMES VIP</title><script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
body{
margin:0;
background:
radial-gradient(circle at top,#241633,#050505 70%);
color:white;
font-family:Arial,sans-serif;
text-align:center;
overflow-x:hidden;
}
body::before{
content:'♠  A      ♥  K      ♣  Q      ♦  J';
position:fixed;
left:-5%;
top:0;
width:110%;
height:100%;
font-size:120px;
font-weight:900;
color:#d4af37;
opacity:.04;
display:flex;
align-items:center;
justify-content:space-between;
pointer-events:none;
z-index:0;
}
body::after{
content:'♠ ♥ ♣ ♦';
position:fixed;
right:-40px;
top:50%;
transform:translateY(-50%) rotate(-90deg);
font-size:180px;
font-weight:900;
color:#d4af37;
opacity:.035;
pointer-events:none;
z-index:0;
}
h1{color:#f5d77b;text-shadow:0 0 10px #d4af37,0 0 45px #d4af37;letter-spacing:4px;font-size:50px;margin:25px 0 5px;font-weight:900}.subtitle{color:#d4af37;letter-spacing:3px}button{background:linear-gradient(135deg,#111,#333);color:#f5d77b;border:1px solid #d4af37;border-radius:14px;padding:8px 10px;margin:4px;font-weight:bold;cursor:pointer;font-size:13px}button:hover{box-shadow:0 0 15px #d4af37;transform:scale(1.03)}input,select{padding:10px;border-radius:10px;border:1px solid #d4af37;background:#111;color:white;margin:4px}.panel{margin:15px auto;padding:15px;max-width:1050px;border:1px solid rgba(212,175,55,.45);border-radius:22px;background:rgba(255,255,255,.06)}.hidden{display:none}.topLeftFixed{position:fixed;top:15px;left:15px;z-index:999999;display:flex;gap:8px;flex-wrap:wrap;max-width:58%}.topRightFixed{position:fixed;top:15px;right:15px;z-index:999999;display:flex;align-items:center;gap:8px;border:2px solid #d4af37;border-radius:20px;padding:8px 12px;background:rgba(0,0,0,.65)}.micStatus{color:#ffd700;font-weight:bold}.tableSeat{display:inline-block;width:260px;min-height:140px;margin:10px;padding:12px;border-radius:22px;border:2px solid #d4af37;background:radial-gradient(circle at center,#0f6b3a,#06351f);box-shadow:0 0 20px #00ff99,inset 0 0 25px #001f12;vertical-align:top}.lockedSeat{opacity:.45;filter:grayscale(40%)}.avatarImg{width:42px;height:42px;border-radius:50%;object-fit:cover;border:3px solid #d4af37;box-shadow:0 0 10px #d4af37}.femaleFrame{border:3px solid #ff4fd8!important;box-shadow:0 0 15px #ff4fd8!important}.maleFrame{border:3px solid #111!important;box-shadow:0 0 15px #000!important}.mainLayout{display:grid;grid-template-columns:1fr 330px;gap:15px;max-width:1320px;margin:0 auto}.sidePanel{margin:15px;padding:12px;border-radius:22px;border:2px solid #d4af37;background:linear-gradient(180deg,rgba(18,12,30,.95),rgba(0,0,0,.92));box-shadow:0 0 25px rgba(212,175,55,.5);min-height:400px}.profileCard{margin:6px 0;padding:8px;border-radius:12px;border:1px solid #d4af37;background:linear-gradient(135deg,rgba(60,40,90,.85),rgba(15,10,25,.95));text-align:left;font-size:12px}.profileCard b{font-size:15px;color:white}.adminBadge{color:#ffd700;text-shadow:0 0 10px #d4af37;font-weight:bold}.adminActions button{font-size:11px;padding:5px 7px}.teams{display:flex;justify-content:center;gap:15px;margin:15px;flex-wrap:wrap}.team{padding:15px;width:280px;border-radius:18px;font-weight:bold}.blueTeam{background:linear-gradient(135deg,#0055ff,#00d4ff)}.redTeam{background:linear-gradient(135deg,#ff1f1f,#ff7a00)}.teamCount{display:block;margin-top:8px;font-size:20px;color:white}.scoreBox{font-size:20px;color:#ffd700;text-shadow:0 0 10px #d4af37}.playerList{margin-top:8px;font-size:13px;text-align:left}.statusBox{font-size:21px;color:#ffd700;text-shadow:0 0 15px #d4af37}.board{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;max-width:900px;margin:20px auto;padding:10px;perspective:1200px}.card{
background:
linear-gradient(120deg,rgba(255,255,255,.18) 0%,rgba(255,255,255,0) 22%),
radial-gradient(circle at top left,rgba(255,255,255,.25),transparent 20%),
linear-gradient(145deg,#050505,#111,#000)!important;
color:#f8d878!important;
min-height:90px;
border-radius:26px;
display:flex;
align-items:center;
justify-content:center;
font-weight:900;
letter-spacing:1px;
cursor:pointer;
border:4px solid #d4af37;
box-shadow:
0 0 12px #d4af37,
0 0 28px rgba(212,175,55,.95),
0 0 60px rgba(212,175,55,.55),
inset 0 0 28px rgba(212,175,55,.25);
transition:.35s;
position:relative;
overflow:hidden;
transform-style:preserve-3d;
}
.card::before{
content:'';
position:absolute;
top:-150%;
left:-60%;
width:55%;
height:400%;
transform:rotate(25deg);
background:linear-gradient(to right,transparent,rgba(255,255,255,.25),transparent);
pointer-events:none;
animation:luxShine 5s infinite;
}
@keyframes luxShine{
0%{left:-80%;}
100%{left:180%;}
}.card::after{content:"♠ ♦ ♣ ♥";position:absolute;top:8px;right:10px;color:#d4af37;font-size:12px;text-shadow:0 0 10px #d4af37}.card:hover{transform:translateY(-8px) rotateX(14deg) scale(1.06);box-shadow:0 0 25px #ffd700,0 0 55px rgba(212,175,55,.8)}.card.guessed{outline:5px solid #00ff99!important;box-shadow:0 0 25px #00ff99,0 0 50px rgba(0,255,153,.8)!important}.guessName{position:absolute;bottom:5px;left:8px;right:8px;font-size:11px;color:#003300;background:rgba(0,255,153,.75);border-radius:8px;padding:2px}.revealBtn,.guessBtn{position:absolute;background:linear-gradient(145deg,#000,#2b2108,#000);color:#ffd700;border:2px solid #d4af37;border-radius:12px;padding:4px 8px;font-size:12px;font-weight:900;z-index:5;box-shadow:0 0 14px #d4af37}.revealBtn{top:5px;left:7px}.guessBtn{top:5px;right:7px}.card.open{animation:cardFlip .7s ease}@keyframes cardFlip{0%{transform:perspective(1000px) rotateY(0deg) scale(1)}50%{transform:perspective(1000px) rotateY(180deg) scale(1.15)}100%{transform:perspective(1000px) rotateY(360deg) scale(1.06)}}.blueCard{background:linear-gradient(145deg,#001a66,#0066ff,#00eaff)!important;color:white!important}.redCard{background:linear-gradient(145deg,#6b0000,#ff1f1f,#ff9a00)!important;color:white!important}.neutralCard{background:linear-gradient(145deg,#777,#e5e5e5,#fff)!important;color:black!important}.assassinCard{background:linear-gradient(145deg,#000,#141414,#3a0000)!important;color:white!important}#winnerOverlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.88);display:none;justify-content:center;align-items:center;z-index:9999}#winnerText{font-size:72px;font-weight:900;color:#ffd700;text-shadow:0 0 20px #d4af37,0 0 50px #d4af37}#messages{height:100px;overflow-y:auto;text-align:left;padding:10px;background:#080808;border-radius:10px;margin-bottom:8px}#historyPanel{font-size:18px;color:white;text-shadow:0 0 10px white}#clueLog{margin-top:10px;color:#ffd700;font-weight:bold;line-height:1.5}.modal{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;justify-content:center;align-items:center;z-index:1000000}.modalContent{width:min(760px,92vw);max-height:82vh;overflow:auto;background:linear-gradient(180deg,#20152d,#070707);border:2px solid #d4af37;border-radius:24px;padding:20px;box-shadow:0 0 40px #d4af37;text-align:left}.modalContent h2{text-align:center;color:#ffd700}.closeBtn{float:right}.betBox,.spectatorBox{padding:10px;border:1px solid #d4af37;border-radius:14px;margin:8px 0}.spectatorBox{border-style:dashed;font-size:12px}
.card{
    text-transform:uppercase!important;
    text-align:center!important;
    font-size:18px!important;
    font-weight:900!important;
    line-height:1.05!important;
    word-break:normal!important;
    overflow-wrap:anywhere!important;
    padding:18px 10px 10px 10px!important;
    min-height:125px!important;
    box-sizing:border-box!important;
}
.board{
    max-width:1100px!important;
    gap:16px!important;
}

.card.dealCard{
    opacity:0;
    transform:translateY(-80px) scale(.65) rotate(-8deg);
    animation:dealIn .55s ease forwards;
}
@keyframes dealIn{
    0%{opacity:0;transform:translateY(-120px) scale(.55) rotate(-15deg);}
    65%{opacity:1;transform:translateY(8px) scale(1.05) rotate(3deg);}
    100%{opacity:1;transform:translateY(0) scale(1) rotate(0);}
}
.card.correctFlash{
    animation:correctPulse .8s ease;
}
@keyframes correctPulse{
    0%{box-shadow:0 0 15px #00ff99;}
    50%{box-shadow:0 0 30px #00ff99,0 0 70px #00ff99;}
    100%{box-shadow:0 0 15px #00ff99;}
}
.card.assassinBoom{
    animation:assassinBoom .9s ease;
}
@keyframes assassinBoom{
    0%{transform:scale(1);filter:brightness(1);}
    35%{transform:scale(1.18) rotate(2deg);filter:brightness(2);}
    70%{transform:scale(.95) rotate(-2deg);filter:brightness(.6);}
    100%{transform:scale(1);filter:brightness(1);}
}

.card .wordText{
    display:flex;
    align-items:center;
    justify-content:center;
    width:100%;
    height:100%;
    padding:12px 4px 4px 4px;
}
.avatarWrap{
    position:relative;
    display:inline-block;
}
.micBadge{
    position:absolute;
    top:-7px;
    right:-9px;
    font-size:13px;
    background:rgba(0,0,0,.75);
    border:1px solid #d4af37;
    border-radius:50%;
    width:24px;
    height:24px;
    display:flex;
    align-items:center;
    justify-content:center;
    z-index:10;
}
.speakingAvatar{
    box-shadow:0 0 12px #00ff66,0 0 25px #00ff66,0 0 45px #00ff66!important;
}
.speakingName{
    color:#00ff66!important;
    text-shadow:0 0 10px #00ff66,0 0 20px #00ff66!important;
}


.frame-none{}
.frame-gold img{border:4px solid #ffd700!important;box-shadow:0 0 12px #ffd700,0 0 28px #ffd700!important;}
.frame-vip img{border:4px solid #b56cff!important;box-shadow:0 0 12px #b56cff,0 0 32px #ff4fd8!important;}
.frame-legendary img{border:4px solid #00fff0!important;box-shadow:0 0 12px #00fff0,0 0 32px #ffd700,0 0 50px #ff4fd8!important;}
.name-default{}
.name-red{color:#ff4f4f!important;text-shadow:0 0 10px #ff4f4f!important;}
.name-blue{color:#4fb3ff!important;text-shadow:0 0 10px #4fb3ff!important;}
.name-purple{color:#c77dff!important;text-shadow:0 0 10px #c77dff!important;}
.name-green{color:#00ff66!important;text-shadow:0 0 10px #00ff66,0 0 22px #00ff66!important;}
.name-rainbow{
    background:linear-gradient(90deg,#ff004c,#ffcc00,#00ff99,#00d4ff,#b56cff);
    -webkit-background-clip:text;
    color:transparent!important;
    font-weight:900;
}
.shopItem{
    border:1px solid #d4af37;
    border-radius:14px;
    padding:10px;
    margin:8px 0;
    background:rgba(255,255,255,.05);
}


.vipProfileChip{
position:fixed;
top:15px;
right:15px;
z-index:999999;
border:3px solid #d4af37;
border-radius:999px;
padding:14px 24px;
background:rgba(0,0,0,.85);
box-shadow:0 0 25px rgba(212,175,55,.85), inset 0 0 18px rgba(212,175,55,.18);
color:#ffd700;
font-weight:900;
font-size:22px;
cursor:pointer;
display:flex;
align-items:center;
gap:10px;
min-height:60px;
}
.vipCasinoMarks{
position:fixed;
inset:0;
pointer-events:none;
z-index:0;
overflow:hidden;
}
.vipCasinoMarks span{
position:absolute;
font-weight:900;
color:#d4af37;
opacity:.085;
text-shadow:0 0 18px rgba(212,175,55,.8);
}
.vipCasinoMarks .m1{left:2%;top:18%;font-size:150px;}
.vipCasinoMarks .m2{right:3%;top:16%;font-size:145px;}
.vipCasinoMarks .m3{left:5%;bottom:8%;font-size:135px;}
.vipCasinoMarks .m4{right:6%;bottom:10%;font-size:135px;}
.vipCasinoMarks .m5{left:46%;top:8%;font-size:110px;opacity:.055;}
.vipCasinoMarks .m6{left:42%;bottom:5%;font-size:120px;opacity:.055;}


.readyBadge{
display:inline-block;
padding:4px 8px;
border-radius:12px;
border:1px solid #d4af37;
background:rgba(0,0,0,.55);
color:#ffd700;
font-size:12px;
margin-left:4px;
}
.readyYes{color:#00ff99;text-shadow:0 0 10px #00ff99;}
.readyNo{color:#ff5c5c;text-shadow:0 0 10px #ff5c5c;}
.chatTabs button{font-size:12px;padding:6px 8px;}
#endGameModal .modalContent{
text-align:center;
background:radial-gradient(circle at top,#3b224e,#050505 70%);
}
#endGameTitle{
font-size:42px;
color:#ffd700;
text-shadow:0 0 20px #d4af37,0 0 50px #d4af37;
}
.emojiBtn{font-size:18px;padding:6px 8px;}

@media(max-width:800px){h1{font-size:30px}.mainLayout{display:block}.card{min-height:60px;font-size:11px}#winnerText{font-size:38px}.topLeftFixed,.topRightFixed{position:static;justify-content:center;max-width:100%;margin:8px}}

/* === MOBILE FIX: les cartes ne se chevauchent pas sur téléphone === */
@media(max-width:800px){
    body{padding-bottom:20px;}
    .topLeftFixed{
        position:static!important;
        justify-content:center!important;
        max-width:100%!important;
        margin:8px!important;
    }
    .vipProfileChip{
        position:sticky!important;
        top:0!important;
        right:auto!important;
        margin:8px auto!important;
        width:fit-content!important;
        z-index:1000000!important;
    }
    .board{
        grid-template-columns:repeat(2, minmax(0,1fr))!important;
        gap:10px!important;
        max-width:96vw!important;
        padding:6px!important;
    }
    .card{
        min-height:112px!important;
        font-size:15px!important;
        border-radius:18px!important;
        padding:26px 6px 14px 6px!important;
    }
    .card .wordText{
        padding:14px 2px 4px 2px!important;
        line-height:1.05!important;
    }
    .revealBtn,.guessBtn{
        font-size:10px!important;
        padding:3px 5px!important;
    }
    .revealBtn{top:4px!important;left:4px!important;}
    .guessBtn{top:4px!important;right:4px!important;}
}
@media(max-width:420px){
    .board{
        grid-template-columns:repeat(2, minmax(0,1fr))!important;
    }
    .card{
        min-height:105px!important;
        font-size:13px!important;
    }
}


.vipBadgeSmall{
    display:inline-block;
    margin-left:5px;
    padding:2px 6px;
    border-radius:999px;
    border:1px solid #ffd700;
    background:rgba(212,175,55,.18);
    color:#ffd700;
    font-size:11px;
    font-weight:900;
    box-shadow:0 0 10px rgba(255,215,0,.75);
}
.paymentDemoBox{
    border:1px solid #d4af37;
    border-radius:14px;
    padding:10px;
    margin:8px 0;
    background:rgba(255,255,255,.06);
}
.paymentDemoBox b{color:#ffd700;}


/* Compact active players panel */
.sidePanel{
    width:260px!important;
    max-width:260px!important;
    padding:8px!important;
}
.mainLayout{
    grid-template-columns:1fr 280px!important;
}
.profileCard{
    padding:5px 6px!important;
    margin:4px 0!important;
    font-size:10px!important;
    line-height:1.15!important;
}
.profileCard b{
    font-size:12px!important;
}
.profileCard .avatarImg, .sidePanel .avatarImg{
    width:30px!important;
    height:30px!important;
}
.adminActions button{
    font-size:9px!important;
    padding:3px 4px!important;
    margin:2px!important;
}
.vipProfileChip{
    padding:6px 11px!important;
    font-size:13px!important;
    min-height:42px!important;
    gap:6px!important;
    max-width:230px!important;
}
.vipProfileChip img{
    width:34px!important;
    height:34px!important;
}


/* === PATCH: neon oyun bandı + cinsiyet isim renkleri + masa kapatma === */
.clueNeon{
    display:block;
    margin:5px 0;
    padding:7px 10px;
    border-radius:12px;
    background:rgba(0,45,20,.88);
    border:1px solid #00ff88;
    color:#b8ffd8;
    font-weight:900;
    text-shadow:0 0 8px #00ff88,0 0 18px #00ff88;
    box-shadow:0 0 12px rgba(0,255,136,.55), inset 0 0 14px rgba(0,255,136,.18);
}
.genderFemaleName{
    color:#ff63d8!important;
    text-shadow:0 0 8px #ff63d8,0 0 16px #ff63d8!important;
    font-weight:900!important;
}
.genderMaleName{
    color:#050505!important;
    text-shadow:0 0 2px #ffffff,0 0 7px #d4af37!important;
    font-weight:900!important;
}
.closeTableBtn{
    background:linear-gradient(135deg,#3a0000,#900,#260000)!important;
    color:#fff!important;
    border:2px solid #ff5757!important;
    box-shadow:0 0 14px rgba(255,50,50,.75)!important;
}


/* === PATCH: open cards always visible === */
.card.open{
    color:white!important;
    text-shadow:0 0 8px #000,0 0 16px #000!important;
    opacity:1!important;
}
.card.open .wordText{
    display:flex!important;
    color:inherit!important;
    opacity:1!important;
    visibility:visible!important;
}
.card.open.blueCard{
    background:linear-gradient(145deg,#001a66,#0066ff,#00eaff)!important;
    border-color:#00d4ff!important;
    box-shadow:0 0 22px #00d4ff,0 0 50px rgba(0,212,255,.85)!important;
}
.card.open.redCard{
    background:linear-gradient(145deg,#6b0000,#ff1f1f,#ff9a00)!important;
    border-color:#ff5757!important;
    box-shadow:0 0 22px #ff5757,0 0 50px rgba(255,80,80,.85)!important;
}
.card.open.neutralCard{
    background:linear-gradient(145deg,#777,#e5e5e5,#fff)!important;
    color:#111!important;
    text-shadow:none!important;
    border-color:#eee!important;
}
.card.open.assassinCard{
    background:linear-gradient(145deg,#000,#141414,#3a0000)!important;
    border-color:#111!important;
    box-shadow:0 0 25px #000,0 0 55px #900!important;
}
.vipProfileChip .genderFemaleName{
    color:#ff63d8!important;
    text-shadow:0 0 8px #ff63d8,0 0 16px #ff63d8!important;
}
.vipProfileChip .genderMaleName{
    color:#050505!important;
    text-shadow:0 0 2px #ffffff,0 0 7px #d4af37!important;
}


/* === PATCH V4: team neon clues + leave table === */
.clueNeon.blueClue{
    background:rgba(0,22,70,.92)!important;
    border:1px solid #00c8ff!important;
    color:#d8f8ff!important;
    text-shadow:0 0 8px #00c8ff,0 0 18px #00c8ff!important;
    box-shadow:0 0 14px rgba(0,200,255,.7), inset 0 0 16px rgba(0,200,255,.2)!important;
}
.clueNeon.redClue{
    background:rgba(75,0,0,.92)!important;
    border:1px solid #ff3048!important;
    color:#ffe1e6!important;
    text-shadow:0 0 8px #ff3048,0 0 18px #ff3048!important;
    box-shadow:0 0 14px rgba(255,48,72,.75), inset 0 0 16px rgba(255,48,72,.22)!important;
}
.leaveSeatBtn{
    background:linear-gradient(135deg,#211200,#6d4500,#211200)!important;
    border:2px solid #ffd36b!important;
    box-shadow:0 0 12px rgba(255,211,107,.7)!important;
}


/* === TAROT PORTAL WINDOW ON CODENAMES HOME === */
.tarotPortalPanel{position:relative;max-width:980px;margin:22px auto;padding:26px;border-radius:30px;border:2px solid #d4af37;background:radial-gradient(circle at top,rgba(212,175,55,.18),transparent 35%),linear-gradient(145deg,rgba(0,0,0,.92),rgba(18,10,0,.94),rgba(0,0,0,.96));box-shadow:0 0 18px rgba(212,175,55,.85),0 0 45px rgba(212,175,55,.42),inset 0 0 30px rgba(212,175,55,.14);overflow:hidden;cursor:pointer;}
.tarotPortalPanel:before{content:"THE MOON   ✦   THE STAR   ✦   THE LOVERS   ✦   THE HIGH PRIESTESS";position:absolute;left:-8%;top:42%;width:120%;color:#d4af37;opacity:.11;font-size:42px;font-weight:900;letter-spacing:12px;transform:rotate(-6deg);pointer-events:none;}
.tarotPortalPanel:after{content:"";position:absolute;inset:-35%;background:radial-gradient(circle,rgba(255,255,255,.11),transparent 30%),radial-gradient(circle at 75% 30%,rgba(212,175,55,.12),transparent 22%);filter:blur(22px);opacity:.45;animation:tarotFogMove 8s ease-in-out infinite alternate;pointer-events:none;}
@keyframes tarotFogMove{from{transform:translateX(-4%) translateY(1%)}to{transform:translateX(5%) translateY(-2%)}}
.tarotPortalInner{position:relative;z-index:2;display:grid;grid-template-columns:120px 1fr 120px;gap:18px;align-items:center;}
.tarotMiniCard{height:165px;border:1px solid #d4af37;border-radius:18px;background:linear-gradient(145deg,#050505,#1b1200,#050505);box-shadow:0 0 18px rgba(212,175,55,.55),inset 0 0 18px rgba(212,175,55,.16);display:flex;align-items:center;justify-content:center;color:#d4af37;font-size:42px;opacity:.78;animation:tarotCardFloat 3s ease-in-out infinite alternate;}
.tarotMiniCard:nth-child(3){animation-delay:.8s}@keyframes tarotCardFloat{from{transform:translateY(0) rotate(-2deg)}to{transform:translateY(-8px) rotate(2deg)}}
.tarotPortalTitle{font-size:40px;font-weight:900;color:#d4af37;text-shadow:0 0 12px #d4af37,0 0 36px rgba(212,175,55,.9);letter-spacing:3px;}
.tarotPortalSub{color:#f7e4a3;font-size:15px;letter-spacing:2px;margin-top:8px;}
.tarotPortalBtn{margin-top:18px;display:inline-block;padding:14px 28px;border-radius:999px;border:2px solid #d4af37;background:linear-gradient(145deg,#000,#2a1b00,#000);color:#d4af37;font-weight:900;box-shadow:0 0 16px #d4af37,0 0 42px rgba(212,175,55,.58);text-shadow:0 0 10px #d4af37;}
.tarotCandleLine{margin-top:10px;font-size:30px;filter:drop-shadow(0 0 14px #d4af37);animation:tarotCandle 1.6s infinite alternate ease-in-out;}
@keyframes tarotCandle{from{opacity:.72;transform:scale(.99)}to{opacity:1;transform:scale(1.03)}}
.tarotBtnMain{background:linear-gradient(145deg,#000,#1b1300,#000)!important;color:#d4af37!important;border:2px solid #d4af37!important;box-shadow:0 0 14px #d4af37,0 0 35px rgba(212,175,55,.55)!important;text-shadow:0 0 10px #d4af37!important;}
@media(max-width:800px){.tarotPortalInner{grid-template-columns:1fr}.tarotMiniCard{display:none}.tarotPortalTitle{font-size:28px}}

/* === CLEAN TAROT TOP-RIGHT BUTTON: no central portal === */
.tarotTopBtn{
    position:fixed;
    top:64px;
    right:15px;
    z-index:999999;
    background:linear-gradient(145deg,#000,#1b1300,#000)!important;
    color:#d4af37!important;
    border:2px solid #d4af37!important;
    border-radius:16px!important;
    padding:10px 15px!important;
    font-size:13px!important;
    font-weight:900!important;
    box-shadow:0 0 14px #d4af37,0 0 35px rgba(212,175,55,.55), inset 0 0 12px rgba(212,175,55,.15)!important;
    text-shadow:0 0 10px #d4af37!important;
}
.tarotTopBtn:hover{
    transform:scale(1.04);
    box-shadow:0 0 22px #ffd700,0 0 52px rgba(212,175,55,.75)!important;
}
.tarotPortalPanel{display:none!important;}
@media(max-width:800px){
    .tarotTopBtn{
        position:sticky!important;
        top:48px!important;
        right:auto!important;
        margin:6px auto!important;
        display:block!important;
        width:fit-content!important;
    }
}

.ownerLuxuryName{color:#d4af37!important;font-weight:900!important;letter-spacing:2px;text-shadow:0 0 8px #d4af37,0 0 22px #000,0 0 36px #ffd700!important;border:1px solid #d4af37;border-radius:999px;padding:2px 8px;background:linear-gradient(145deg,#000,#1b1200,#000);box-shadow:0 0 14px #d4af37,inset 0 0 12px rgba(212,175,55,.25);}
.ownerOnlyPanel{border:2px solid #d4af37;border-radius:20px;padding:12px;margin:10px 0;background:linear-gradient(145deg,rgba(0,0,0,.95),rgba(35,22,0,.9));box-shadow:0 0 18px rgba(212,175,55,.6);}
.ownerOnlyPanel h3{color:#ffd700;text-align:center;}
#tarotTopBtn.tarotTopBtn{position:static!important;left:auto!important;right:auto!important;top:auto!important;}
.name-green{color:#00ff66!important;text-shadow:0 0 10px #00ff66,0 0 22px #00ff66!important;}

.ownerLuxuryName{
    color:#d4af37!important;
    font-weight:900!important;
    letter-spacing:2px!important;
    text-transform:uppercase;
    text-shadow:0 0 7px #d4af37,0 0 18px #000,0 0 34px #ffd700,0 0 48px #d4af37!important;
    border:2px double #d4af37!important;
    border-radius:999px!important;
    padding:3px 10px!important;
    background:
      radial-gradient(circle at top,#3a2700,#000 62%),
      linear-gradient(145deg,#000,#1b1200,#000)!important;
    box-shadow:0 0 14px #d4af37,0 0 32px rgba(212,175,55,.65), inset 0 0 18px rgba(212,175,55,.35)!important;
}
.baroqueOwnerFrame img, .baroque-owner img{
    border:4px double #d4af37!important;
    box-shadow:0 0 16px #d4af37,0 0 38px #000,0 0 48px rgba(255,215,0,.7)!important;
}
.ownerCrownBadge{
    display:inline-block;
    margin-left:6px;
    padding:2px 7px;
    border:1px solid #d4af37;
    border-radius:999px;
    color:#d4af37;
    background:#000;
    box-shadow:0 0 12px #d4af37;
    font-size:11px;
}
.tarotTopBtn{
    position:static!important;
    display:inline-block!important;
    max-width:210px!important;
    white-space:normal!important;
    line-height:1.15!important;
    background:linear-gradient(145deg,#000,#1b1300,#000)!important;
    color:#d4af37!important;
    border:2px solid #d4af37!important;
    box-shadow:0 0 14px #d4af37,0 0 35px rgba(212,175,55,.55), inset 0 0 12px rgba(212,175,55,.15)!important;
    text-shadow:0 0 10px #d4af37!important;
}

/* === FINAL BUGFIX OWNER + TAROT === */
@import url('https://fonts.googleapis.com/css2?family=UnifrakturCook:wght@700&family=Cinzel:wght@400;700;900&display=swap');
.ownerLuxuryName{
    color:#d4af37!important;
    font-family:'Cinzel',Georgia,serif!important;
    font-weight:900!important;
    letter-spacing:2px!important;
    text-transform:uppercase;
    text-shadow:0 0 7px #d4af37,0 0 18px #000,0 0 34px #ffd700,0 0 48px #d4af37!important;
    border:2px double #d4af37!important;
    border-radius:999px!important;
    padding:3px 10px!important;
    background:radial-gradient(circle at top,#3a2700,#000 62%)!important;
    box-shadow:0 0 14px #d4af37,0 0 32px rgba(212,175,55,.65), inset 0 0 18px rgba(212,175,55,.35)!important;
}
.ownerCrownBadge{
    display:inline-block;
    margin-left:6px;
    padding:2px 7px;
    border:1px solid #d4af37;
    border-radius:999px;
    color:#d4af37;
    background:#000;
    box-shadow:0 0 12px #d4af37;
    font-size:11px;
}
.baroque-owner img,.baroqueOwnerFrame img{
    border:4px double #d4af37!important;
    box-shadow:0 0 16px #d4af37,0 0 38px #000,0 0 48px rgba(255,215,0,.7)!important;
}
.ownerOnlyPanel{
    border:2px solid #d4af37;
    border-radius:20px;
    padding:12px;
    margin:10px 0;
    background:linear-gradient(145deg,rgba(0,0,0,.95),rgba(35,22,0,.9));
    box-shadow:0 0 18px rgba(212,175,55,.6);
}
.ownerOnlyPanel h3{color:#ffd700;text-align:center;}
.tarotTopBtn{
    position:static!important;
    display:block!important;
    width:178px!important;
    max-width:178px!important;
    white-space:normal!important;
    line-height:1.05!important;
    font-size:10px!important;
    padding:7px 8px!important;
    margin:4px!important;
    background:linear-gradient(145deg,#000,#1b1300,#000)!important;
    color:#d4af37!important;
    border:2px solid #d4af37!important;
    border-radius:14px!important;
    box-shadow:0 0 14px #d4af37,0 0 35px rgba(212,175,55,.55), inset 0 0 12px rgba(212,175,55,.15)!important;
    text-shadow:0 0 10px #d4af37!important;
}
.name-green{color:#00ff66!important;text-shadow:0 0 10px #00ff66,0 0 22px #00ff66!important;}

/* === COMPACT TOP MENU FIX === */
.topLeftFixed{
    align-items:flex-start!important;
}
.mainTopBtn{
    display:inline-block!important;
}
.compactMenuWrap{
    position:relative;
    display:inline-block;
}
.menuToggleBtn{
    background:linear-gradient(135deg,#000,#222,#000)!important;
    color:#ffd700!important;
    border:2px solid #d4af37!important;
    box-shadow:0 0 12px rgba(212,175,55,.75)!important;
}
.compactMenu{
    display:none;
    position:absolute;
    top:42px;
    left:0;
    min-width:190px;
    padding:8px;
    border:2px solid #d4af37;
    border-radius:18px;
    background:rgba(0,0,0,.94);
    box-shadow:0 0 22px rgba(212,175,55,.85);
    z-index:1000001;
}
.compactMenu.show{
    display:block;
}
.compactMenu button{
    display:block!important;
    width:100%!important;
    text-align:left!important;
    margin:4px 0!important;
    font-size:12px!important;
}
.tarotTopBtn{
    position:static!important;
    display:inline-block!important;
    max-width:210px!important;
    white-space:normal!important;
    line-height:1.1!important;
    font-size:11px!important;
    padding:8px 10px!important;
    margin:4px!important;
    background:linear-gradient(145deg,#000,#1b1300,#000)!important;
    color:#d4af37!important;
    border:2px solid #d4af37!important;
    border-radius:14px!important;
    box-shadow:0 0 14px #d4af37,0 0 35px rgba(212,175,55,.55), inset 0 0 12px rgba(212,175,55,.15)!important;
    text-shadow:0 0 10px #d4af37!important;
}
@media(max-width:800px){
    .compactMenu{
        position:fixed;
        top:70px;
        left:10px;
        right:10px;
        width:auto;
    }
}

/* === REAL CLICKABLE LEFT MENU FIX === */
.topLeftFixed{
    position:fixed!important;
    top:15px!important;
    left:15px!important;
    z-index:1000002!important;
    display:flex!important;
    flex-direction:column!important;
    align-items:flex-start!important;
    gap:6px!important;
    max-width:210px!important;
    pointer-events:auto!important;
}
.topLeftFixed button{
    width:190px!important;
    min-height:34px!important;
    pointer-events:auto!important;
}
.compactMenuWrap{
    width:190px!important;
    position:relative!important;
    z-index:1000003!important;
}
.compactMenu{
    display:none;
    position:absolute!important;
    top:40px!important;
    left:0!important;
    min-width:190px!important;
    padding:8px!important;
    border:2px solid #d4af37!important;
    border-radius:18px!important;
    background:rgba(0,0,0,.96)!important;
    box-shadow:0 0 22px rgba(212,175,55,.85)!important;
    z-index:1000004!important;
    pointer-events:auto!important;
}
.compactMenu.show{display:block!important;}
.compactMenu button{
    display:block!important;
    width:100%!important;
    text-align:left!important;
    margin:4px 0!important;
    font-size:12px!important;
}
.tarotTopBtn{
    position:static!important;
    display:block!important;
    width:190px!important;
    max-width:190px!important;
    white-space:normal!important;
    line-height:1.05!important;
    font-size:10px!important;
    padding:7px 8px!important;
}

/* === HARD CLICK CSS FIX === */
.topLeftFixed,.topLeftFixed *{
    pointer-events:auto!important;
}
.vipCasinoMarks, body::before, body::after{
    pointer-events:none!important;
}
.topLeftFixed{
    z-index:2147483000!important;
}
.compactMenu{
    z-index:2147483001!important;
}

/* === MAIN MENU REAL FIX === */
.topLeftFixed{
    position:fixed!important;
    top:15px!important;
    left:15px!important;
    z-index:2147483000!important;
    display:flex!important;
    flex-direction:column!important;
    align-items:flex-start!important;
    gap:6px!important;
    max-width:210px!important;
    pointer-events:auto!important;
}
.topLeftFixed *{pointer-events:auto!important;}
.topLeftFixed button{width:190px!important;min-height:34px!important;}
.compactMenuWrap{width:190px!important;position:relative!important;z-index:2147483001!important;}
.compactMenu{
    display:none;
    position:absolute!important;
    top:40px!important;
    left:0!important;
    min-width:190px!important;
    padding:8px!important;
    border:2px solid #d4af37!important;
    border-radius:18px!important;
    background:rgba(0,0,0,.96)!important;
    box-shadow:0 0 22px rgba(212,175,55,.85)!important;
    z-index:2147483002!important;
}
.compactMenu.show{display:block!important;}
.compactMenu button{display:block!important;width:100%!important;text-align:left!important;margin:4px 0!important;font-size:12px!important;}
.tarotTopBtn{position:static!important;display:block!important;width:190px!important;max-width:190px!important;white-space:normal!important;line-height:1.05!important;font-size:10px!important;padding:7px 8px!important;}
.vipCasinoMarks,.casinoMarks,body::before,body::after{pointer-events:none!important;}
</style></head><body>
<div class="vipCasinoMarks"><span class="m1">A♠</span><span class="m2">K♥</span><span class="m3">Q♣</span><span class="m4">J♦</span><span class="m5">♠♥♣♦</span><span class="m6">A K Q J</span></div><div id="profileChip" class="vipProfileChip" onclick="openProfile()">👤 Profil</div><div class="topLeftFixed">

<div class="compactMenuWrap">
<button id="menuToggleBtn" class="menuToggleBtn" type="button">☰ MENU</button>
<div id="mainCompactMenu" class="compactMenu">
<button id="menuAuthBtn" type="button">👤 Üyelik</button>
<button id="menuProfileBtn" type="button">🏆 Profil</button>
<button id="menuRankingBtn" type="button">📊 Classement</button>
<button id="menuSettingsBtn" type="button">⚙️ Ayarlar</button>
<button id="menuWordsBtn" type="button">📚 Kelimeler</button>
<button id="menuBetBtn" type="button">🎰 Bahis</button>

<button id="ownerPanelBtn" type="button" style="display:none;">👑 Owner Panel</button>
</div>
</div>
<button id="btnTimerTop" class="mainTopBtn" type="button">⏱ Süre</button>
<button id="btnNewGameTop" class="mainTopBtn" type="button">🎲 Yeni Oyun</button>
<button id="btnLobbyTop" class="mainTopBtn" type="button">🚪 Lobi</button>
</div>

<div id="ownerPanelModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button>
<h2>👑 OWNER PANEL — YOHANNA</h2>
<p style="color:#ffd700;text-align:center;">Sadece Yohanna görebilir ve kullanabilir.</p>
<div class="ownerOnlyPanel"><h3>👥 Kullanıcı Yönetimi</h3><input id="ownerTargetUser" placeholder="Kullanıcı adı"><button onclick="ownerLoadPanel()">Listeyi Yenile</button><button onclick="ownerUserAction('freeze')">Hesabı Dondur</button><button onclick="ownerUserAction('unfreeze')">Dondurmayı Kaldır</button><button onclick="ownerUserAction('delete')">Hesabı Sil</button><button onclick="ownerUserAction('reset_avatar')">Avatar Sıfırla</button><button onclick="ownerUserAction('reset_password_link')">Şifre Reset Token</button></div>
<div class="ownerOnlyPanel"><h3>💎 Üyelik Yönetimi</h3><select id="ownerMembershipLevel"><option value="bronze">🥉 Bronz</option><option value="silver">🥈 Gümüş</option><option value="gold">🥇 Altın</option><option value="diamond">💎 Elmas</option><option value="none">Üyeliği Kaldır</option></select><select id="ownerMembershipDuration"><option value="forever">Süresiz</option><option value="30">30 gün</option><option value="90">90 gün</option></select><button onclick="ownerSetMembership()">Üyeliği Uygula</button></div>
<div class="ownerOnlyPanel"><h3>🪙 Jeton Yönetimi</h3><button onclick="ownerChip(100)">+100</button><button onclick="ownerChip(500)">+500</button><button onclick="ownerChip(1000)">+1000</button><button onclick="ownerChip(5000)">+5000</button><button onclick="ownerChip(10000)">+10000</button><br><button onclick="ownerChip(-100)">-100</button><button onclick="ownerChip(-500)">-500</button><button onclick="ownerChip(-1000)">-1000</button></div>
<div class="ownerOnlyPanel"><h3>🎡 Şans Çarkı Ayarları</h3><select id="ownerWheelLimit"><option value="1">Günlük 1 kez</option><option value="2">Günlük 2 kez</option><option value="0">Devre dışı</option></select><p>10=%25 · 20=%20 · 30=%18 · 50=%15 · 100=%10 · 200=%8 · 300=%4</p><button onclick="ownerSaveWheel()">Kaydet</button></div>
<div class="ownerOnlyPanel"><h3>🔮 Tarot Talepleri</h3><input id="ownerReqId" placeholder="Talep ID"><select id="ownerReqStatus"><option>Bekliyor</option><option>İşlemde</option><option>Tamamlandı</option><option>İptal</option></select><textarea id="ownerReqResult" placeholder="Sonuç / PDF içeriği"></textarea><button onclick="ownerUpdateRequest()">Talebi Güncelle</button></div>
<div class="ownerOnlyPanel"><h3>💬 Canlı Sohbet</h3><button onclick="messages.innerHTML=''">Sohbeti Temizle</button><p>Yazılı + mikrofonlu sohbet yönetimi Owner yetkisinde.</p></div>
<div class="ownerOnlyPanel"><h3>💳 Ödeme Yönetimi</h3><div id="ownerPayments">Stripe: Bugün 0 £ · Bu ay 0 £ · Toplam 0 £<br>PayPal: Son işlemler / iadeler hazırlanacak.</div></div>
<div class="ownerOnlyPanel"><h3>📊 İstatistikler</h3><div id="ownerStats">Yükleniyor...</div></div>
<div class="ownerOnlyPanel"><h3>⚙️ Site Ayarları</h3><label><input type="checkbox" id="setMaintenance"> Bakım modu</label><br><label><input type="checkbox" id="setRegistrations" checked> Yeni kayıtlar</label><br><label><input type="checkbox" id="setWheel" checked> Şans çarkı</label><br><label><input type="checkbox" id="setTarot" checked> Tarot</label><br><label><input type="checkbox" id="setRitual" checked> Ritüel</label><br><button onclick="ownerSaveSiteSettings()">Kaydet</button></div>
<div id="ownerPanelResult" style="color:#ffd700;"></div><div id="ownerUserList"></div>
</div></div>
<div id="winnerOverlay"><div id="winnerText"></div></div>
<div id="settingsModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2 data-i18n='settings'>⚙️ Ayarlar</h2><h3>Kurallar</h3><p>Spymaster ipucu vermeden kart açılamaz. Sadece sırası olan takım tahmin yapar ve kart açar. Seyirciler sadece izler ve sanal jetonla bahis yapabilir.</p><p>Doğru takım rengi açılırsa takım devam eder. Rakip renk veya nötr açılırsa sıra geçer. Suikastçı açılırsa açan takım kaybeder.</p><h3>Varsayılan Diller</h3><select id="languageSelect"><option>Türkçe</option><option>English</option><option>Français</option><option>Русский</option><option>Nederlands</option></select></div></div>
<div id="wordsModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>📚 Kelime Serileri</h2><p>Yeni seri seçince yeni oyun başlatılır.</p><button onclick="setCategory('default')">📁 CodeNames8.txt</button><button onclick="setCategory('animals')">🐾 Hayvanlar Serisi</button><button onclick="setCategory('adult')">🔞 18+ Serisi</button></div></div>
<div id="shopModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🎰 Boutique VIP & Jetons</h2><p><b>Mode sécurisé :</b> Stripe/PayPal sont en mode démo. Aucun paiement réel n’est encaissé dans cette version.</p><p>Bakiyen: <b id="shopChips">1000</b> 🪙</p><h3>🪙 Jeton Al - Démo</h3><div class="paymentDemoBox"><b>Stripe Démo</b><br><button onclick="demoBuyChips(1000,\'Stripe\')">Stripe: +1000 🪙</button><button onclick="demoBuyChips(5000,\'Stripe\')">Stripe: +5000 🪙</button><button onclick="demoBuyChips(20000,\'Stripe\')">Stripe: +20000 🪙</button></div><div class="paymentDemoBox"><b>PayPal Démo</b><br><button onclick="demoBuyChips(1000,\'PayPal\')">PayPal: +1000 🪙</button><button onclick="demoBuyChips(5000,\'PayPal\')">PayPal: +5000 🪙</button><button onclick="demoBuyChips(20000,\'PayPal\')">PayPal: +20000 🪙</button></div><hr><h3>👑 VIP Ol</h3><div class="shopItem">VIP Bronze — 3000 🪙 / 7 gün <button onclick="buyVipWithChips(\'vip-bronze\')">VIP Al</button></div><div class="shopItem">VIP Gold — 9000 🪙 / 30 gün <button onclick="buyVipWithChips(\'vip-gold\')">VIP Al</button></div><div class="shopItem">VIP Diamond — 25000 🪙 / 90 gün <button onclick="buyVipWithChips(\'vip-diamond\')">VIP Al</button></div><hr><h3>🪙 Jeton Bonus</h3><button onclick="buyVirtualChips(1000)">Bonus +1000 🪙</button><button onclick="buyVirtualChips(5000)">Bonus +5000 🪙</button><button onclick="buyVirtualChips(20000)">Bonus +20000 🪙</button><button onclick="buyVirtualChips(75000)">Bonus +75000 🪙</button><hr><h3>🖼️ Avatar Cadres</h3><div class="shopItem">Altın Çerçeve — 1000 🪙 <button onclick="buyCosmetic('frame-gold')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('frame-gold')">Kullan</button></div><div class="shopItem">VIP Çerçeve — 5000 🪙 <button onclick="buyCosmetic('frame-vip')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('frame-vip')">Kullan</button></div><div class="shopItem">Efsanevi Çerçeve — 15000 🪙 <button onclick="buyCosmetic('frame-legendary')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('frame-legendary')">Kullan</button></div><hr><h3>🌈 İsim Renkleri</h3><div class="shopItem">Kırmızı İsim — 500 🪙 <button onclick="buyCosmetic('name-red')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('name-red')">Kullan</button></div><div class="shopItem">Mavi İsim — 500 🪙 <button onclick="buyCosmetic('name-blue')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('name-blue')">Kullan</button></div><div class="shopItem">Mor İsim — 1000 🪙 <button onclick="buyCosmetic('name-purple')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('name-purple')">Kullan</button></div><div class="shopItem">Yeşil İsim — 3000 🪙 <button onclick="buyCosmetic('name-green')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('name-green')">Kullan</button></div><div class="shopItem">Rainbow İsim — 10000 🪙 <button onclick="buyCosmetic('name-rainbow')">Satın Al</button> <button data-base-label='Satın Al' onclick="equipCosmetic('name-rainbow')">Kullan</button></div></div></div>
<div id="betModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🎰 Sanal Bahis</h2><p>Bakiyen: <b id="betChips">1000</b> 🪙</p><div class="betBox"><label>Takım:</label><select id="betTeam"><option value="blue">🔵 Mavi Takım</option><option value="red">🔴 Kırmızı Takım</option></select><label>Miktar:</label><input id="betAmount" type="number" value="100" min="1"><button onclick="placeBet()">Bahis Yap</button></div><div id="betInfo">Henüz bahis yok.</div></div></div>

<div id="authModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>👤 Üyelik</h2><h3>📝 Kayıt Ol</h3><input id="regUsername" placeholder="Kullanıcı adı"><input id="regEmail" type="email" placeholder="Email"><input id="regPassword" type="password" placeholder="Şifre"><input id="regPassword2" type="password" placeholder="Şifre tekrar"><button onclick="registerAccount()">Kayıt Ol</button><hr><h3>🔐 Giriş Yap</h3><input id="loginUsername" placeholder="Kullanıcı adı"><input id="loginPassword" type="password" placeholder="Şifre"><button onclick="loginAccount()">Giriş Yap</button><button onclick="openForgotPassword()">Şifremi Unuttum</button><hr><button onclick="logoutAccount()">🚪 Çıkış Yap</button><p id="authStatus">Henüz giriş yapılmadı.</p></div></div>
<div id="forgotModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🔑 Şifre Yenileme</h2><p>Email adresini yaz. Sistem sana şifre yenileme linki göndermeye çalışır.</p><input id="forgotEmail" type="email" placeholder="Email"><button onclick="requestPasswordReset()">Link Gönder</button><div id="resetLinkBox" style="margin-top:10px;color:#ffd700;font-size:13px;"></div><hr><h3>Yeni Şifre</h3><input id="resetToken" placeholder="Reset token"><input id="newPassword" type="password" placeholder="Yeni şifre"><button onclick="confirmPasswordReset()">Şifreyi Yenile</button></div></div>
<div id="profileModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🏆 Profil</h2><div id="profileInfo">Giriş yapmadın.</div><hr><h3>🎨 Avatar Yükle</h3><input id="avatarUploadInput" type="file" accept="image/png,image/jpeg,image/webp"><button onclick="uploadAvatar()">Avatarı Kaydet</button><button onclick="deleteAvatar()">Avatarı Sil</button><p style="font-size:12px;color:#d4af37;">PNG/JPG/WebP kullan. Çok büyük dosya seçme.</p></div></div>
<div id="rankingModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>📊 Classement</h2><div id="rankingInfo">Yükleniyor...</div></div></div>

<div id="endGameModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2 id="endGameTitle">🏆 Fin de partie</h2><div id="endGameInfo"></div><button onclick="newGame();closeModals()">🎲 Nouvelle manche</button><button onclick="goLobby();closeModals()">🚪 Retour lobby</button></div></div>
<h1>♠️ CODENAMES VIP ♦️</h1><p class="subtitle">Luxury Online Multiplayer Edition</p>

<div id="lobby" class="panel"><h2>🎰 Oda Sistemi</h2><button onclick="createRoom()">Oda Oluştur</button><br><input id="roomInput" placeholder="Oda kodu"><input id="roomPassword" placeholder="Oda şifresi"><button onclick="joinExistingRoom()">Odaya Katıl</button><h3 id="roomText">Oda: -</h3><hr><h3>Profil Oluştur / Masaya Otur</h3><input id="playerName" placeholder="Oyuncu adı"><select id="avatarChoice"><option value="woman.png">Kadın</option><option value="man.png">Erkek</option></select><select id="teamChoice"><option value="blue">🔵 Mavi Masa</option><option value="red">🔴 Kırmızı Masa</option><option value="spectator">👀 Seyirci</option></select><select id="roleChoice"><option value="player">Saha Ajanı</option><option value="blueSpy">Mavi Spymaster</option><option value="redSpy">Kırmızı Spymaster</option><option value="spectator">Seyirci</option></select><br><button onclick="sitAtTable()">Masaya Otur</button><button onclick="toggleReady()">✅ Hazırım</button><button class="leaveSeatBtn" onclick="leaveTable()">🚪 Masadan Ayrıl / Değiştir</button><button class="closeTableBtn" onclick="closeCurrentTable()">❌ Masayı Kapat</button><button onclick="startGame()">🚀 Oyunu Başlat</button><div id="readyInfo" style="color:#ffd700;margin-top:8px;">Hazır durumu: -</div><div><div class="tableSeat" id="blueSeatBox"><div>🔵 MAVİ MASA <span id="blueLockText"></span></div><div id="blueLobby"></div></div><div class="tableSeat" id="redSeatBox"><div>🔴 KIRMIZI MASA <span id="redLockText"></span></div><div id="redLobby"></div></div><div class="tableSeat" id="spectatorSeatBox"><div>👀 SEYİRCİLER</div><div id="spectatorLobby"></div></div></div></div>
<div id="gameScreen" class="hidden"><div class="panel"><button class="closeTableBtn" onclick="closeCurrentTable()">❌ Bu Masayı Kapat / Yeni Oda Aç</button></div><div class="mainLayout"><div><div class="panel"><button onclick="startTimer()">▶ Süre Başlat</button><button onclick="pauseTimer()">⏸ Durdur</button><button onclick="setTimer(60)">1 dk</button><button onclick="setTimer(180)">3 dk</button><button onclick="setTimer(300)">5 dk</button><button onclick="setTimer(600)">10 dk</button><br>⏱ <span id="timer">05:00</span></div><div class="panel"><h3>🎙 Oda Mikrofonu</h3><button onclick="startMic()">🎙 Aç</button><button onclick="stopMic()">🔇 Kapat</button><span id="micStatus" class="micStatus">Kapalı</span><p style="font-size:12px;color:#d4af37;">Mikrofon sadece oda içinde çalışır. Konuşan kişinin ikonu yeşil yanar.</p></div><div class="panel"><p id="roundText" class="scoreBox">🎮 Tur: 1</p><p id="roleText">Rol: -</p><p id="phaseText" class="statusBox">🎰 Oyun bekliyor...</p><p id="scoreText" class="scoreBox">🏆 Mavi: 0 | Kırmızı: 0</p><p id="chipsText" class="scoreBox">🪙 Jeton: 1000</p></div><div class="teams"><div class="team blueTeam">🔵 MAVİ TAKIM<span class="teamCount">Kalan kelime: <span id="blueCount">9</span></span><div id="bluePlayers" class="playerList"></div></div><div class="team redTeam">🔴 KIRMIZI TAKIM<span class="teamCount">Kalan kelime: <span id="redCount">8</span></span><div id="redPlayers" class="playerList"></div></div></div><div class="panel"><input id="clueText" placeholder="İpucu yaz"><select id="clueNumber"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option><option value="7">7</option><option value="8">8</option><option value="9">9</option><option value="∞">♾️</option></select><button onclick="sendClue()">İpucu Ver</button><button onclick="endTurn()" style="background:#008f4c;color:white;">✅ Sırayı Bitir</button><h2 id="clueDisplay">İpucu: -</h2><div id="clueLog">📜 Oyun bandı: Henüz ipucu yok.</div><h2 id="turnDisplay">Sıra: Belirlenmedi</h2></div><div class="board" id="board"></div><div class="panel"><h3>💬 Chat</h3><div class="chatTabs"><button onclick="setChatMode('global')">🌍 Genel</button><button onclick="setChatMode('team')">🔒 Takım</button><button onclick="setChatMode('dm')">📩 DM</button></div><div id="messages"></div><select id="dmTarget"><option value="">DM oyuncu seç</option></select><br><input id="chatInput" placeholder="Mesaj yaz"><button onclick="sendMessage()">Gönder</button><br><button class="emojiBtn" onclick="addEmoji('😂')">😂</button><button class="emojiBtn" onclick="addEmoji('🔥')">🔥</button><button class="emojiBtn" onclick="addEmoji('💀')">💀</button><button class="emojiBtn" onclick="addEmoji('👑')">👑</button><button class="emojiBtn" onclick="addEmoji('❤️')">❤️</button><button class="emojiBtn" onclick="addEmoji('😈')">😈</button><small id="chatModeText" style="color:#ffd700;">Mode: Genel</small></div></div><div class="sidePanel"><h3>👥 Bağlanan Oyuncular</h3><div id="onlinePlayers"></div><div class="spectatorBox"><h3>👀 Seyirciler</h3><div id="spectatorList">-</div></div><hr><h3>🔁 Join Team</h3><button onclick="joinTeam('blue','player')">🔵 Mavi Saha Ajanı</button><button onclick="joinTeam('blue','blueSpy')">🕵️ Mavi Spymaster</button><button onclick="joinTeam('red','player')">🔴 Kırmızı Saha Ajanı</button><button onclick="joinTeam('red','redSpy')">🕵️ Kırmızı Spymaster</button><button onclick="joinTeam('spectator','spectator')">👀 Seyirci</button><hr><h3>👑 Admin Paneli</h3><small>Admin sadece Codenames oyununu yönetir. Bahis, turnuva, jeton, üyelik, ödeme ve tarot yetkisi yoktur.</small><div id="adminPanel"><button onclick="toggleTeamLock('blue')">🔒 Mavi Kilitle</button><button onclick="toggleTeamLock('red')">🔒 Kırmızı Kilitle</button><button onclick="adminNewGame()">🎲 Yeni Oyun</button><button onclick="adminRevealAll()">🃏 Kartları Aç</button><button onclick="adminResetStats()">🏆 Skoru Sıfırla</button></div><hr><h3>🏆 Kazananlar / Oyun Kaydı</h3><div id="historyPanel"></div></div></div></div>
<script>
const socket=io();let roomCode='',myName='',myRole='',myTeam='',mySid='',joined=false,isAdmin=false,currentChips=1000;let seconds=300,timerRunning=false,timerInterval=null,micStream=null;let voicePeers={},voiceStarted=false,currentMicStates={},lastPlayers=[],lastLocks={blue:false,red:false},audioContext=null,speakingInterval=null,mySpeaking=false,currentAccount=null,currentProfile=null,pendingAutoSit=false;let lastOpenedStates=[],lastWinner='',dealSoundPlayed=false,chatMode='global',currentReady={};
function chipKey(n){return 'codenamesChips_'+(n||'guest')}function getSavedChips(n){let v=localStorage.getItem(chipKey(n));if(v===null)return 1000;let x=parseInt(v);return isNaN(x)?1000:x}function setSavedChips(n,a){localStorage.setItem(chipKey(n),String(a))}function saveLocalProfile(){localStorage.setItem('codenamesRoom',roomCode);localStorage.setItem('codenamesName',myName);localStorage.setItem('codenamesRole',myRole);localStorage.setItem('codenamesTeam',myTeam);localStorage.setItem('codenamesPassword',roomPassword.value||'')}function restoreLocalFields(){let r=localStorage.getItem('codenamesRoom')||'',n=localStorage.getItem('codenamesName')||'',ro=localStorage.getItem('codenamesRole')||'',t=localStorage.getItem('codenamesTeam')||'';if(r)roomInput.value=r;if(n)playerName.value=n;if(ro)roleChoice.value=ro;if(t)teamChoice.value=t}
function avatarClass(f){return f==='woman.png'?'avatarImg femaleFrame':'avatarImg maleFrame'}function roleLabel(r){if(r==='player')return'Saha Ajanı';if(r==='blueSpy')return'Mavi Spymaster';if(r==='redSpy')return'Kırmızı Spymaster';if(r==='spectator')return'Seyirci';return r}function teamLabel(t){if(t==='blue')return'🔵 Mavi';if(t==='red')return'🔴 Kırmızı';return'👀 Seyirci'}
function playerNameClass(p){
    return p.nameColor || 'name-default';
}
function playerGenderClass(p){
    return (p && p.avatar === 'man.png') ? 'genderMaleName' : 'genderFemaleName';
}
function playerFrameClass(p){
    return p.avatarFrame || 'frame-none';
}
function defaultAvatarData(avatar){
    const isMan = avatar === 'man.png';
    const bg = isMan ? '#111111' : '#ff4fd8';
    const emoji = isMan ? '👤' : '👩';
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><defs><radialGradient id="g" cx="50%" cy="35%" r="70%"><stop offset="0%" stop-color="#ffe680"/><stop offset="100%" stop-color="${bg}"/></radialGradient></defs><circle cx="60" cy="60" r="56" fill="url(#g)" stroke="#d4af37" stroke-width="6"/><text x="60" y="78" font-size="58" text-anchor="middle">${emoji}</text></svg>`;
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}
function playerAvatarSrc(p){
    if(p && p.avatarData) return p.avatarData;
    return defaultAvatarData((p && p.avatar) || 'woman.png');
}
function emitMicState(micOpen, speaking){
    socket.emit('voice_mic_state',{room:roomCode,mic:micOpen,speaking:!!speaking});
}

function startSpeakingDetection(){
    if(!micStream) return;
    if(audioContext) audioContext.close();
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(micStream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);

    if(speakingInterval) clearInterval(speakingInterval);

    speakingInterval = setInterval(()=>{
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for(let i=0;i<data.length;i++) sum += data[i];
        const avg = sum / data.length;
        const nowSpeaking = avg > 18;

        if(nowSpeaking !== mySpeaking){
            mySpeaking = nowSpeaking;
            socket.emit('voice_speaking',{room:roomCode,speaking:mySpeaking});
        }
    },180);
}

async function startMic(){
    if(!roomCode){
        alert('Mikrofon sadece oda içinde çalışır. Önce oda oluştur veya odaya katıl.');
        return;
    }
    try{
        micStream = await navigator.mediaDevices.getUserMedia({audio:true});
        voiceStarted = true;
        mySpeaking = false;
        micStatus.innerHTML = 'Açık 🎤';
        emitMicState(true,false);
        startSpeakingDetection();
        socket.emit('voice_join',{room:roomCode});
    }catch(e){
        alert('Mikrofon izni verilmedi.');
    }
}

function stopMic(){
    voiceStarted = false;
    mySpeaking = false;

    if(speakingInterval){
        clearInterval(speakingInterval);
        speakingInterval = null;
    }
    if(audioContext){
        audioContext.close();
        audioContext = null;
    }
    if(micStream){
        micStream.getTracks().forEach(t=>t.stop());
        micStream = null;
    }

    Object.values(voicePeers).forEach(pc=>pc.close());
    voicePeers = {};
    micStatus.innerHTML = 'Kapalı 🚫🎤';
    emitMicState(false,false);
    socket.emit('voice_leave',{room:roomCode});
}

function createPeer(peerSid, initiator){
    if(voicePeers[peerSid]) return voicePeers[peerSid];

    const pc = new RTCPeerConnection({
        iceServers:[{urls:'stun:stun.l.google.com:19302'}]
    });

    voicePeers[peerSid] = pc;

    if(micStream){
        micStream.getTracks().forEach(track=>pc.addTrack(track,micStream));
    }

    pc.onicecandidate = e=>{
        if(e.candidate){
            socket.emit('voice_signal',{
                room:roomCode,
                to:peerSid,
                data:{candidate:e.candidate}
            });
        }
    };

    pc.ontrack = e=>{
        let audio=document.getElementById('audio_'+peerSid);
        if(!audio){
            audio=document.createElement('audio');
            audio.id='audio_'+peerSid;
            audio.autoplay=true;
            audio.controls=false;
            document.body.appendChild(audio);
        }
        audio.srcObject=e.streams[0];
    };

    if(initiator){
        pc.createOffer()
        .then(offer=>pc.setLocalDescription(offer))
        .then(()=>{
            socket.emit('voice_signal',{
                room:roomCode,
                to:peerSid,
                data:{sdp:pc.localDescription}
            });
        });
    }

    return pc;
}

function safeCall(fn){
    try{
        if(typeof window[fn]==='function'){ window[fn](); return; }
        console.log(fn+' bulunamadı');
    }catch(e){ console.error(e); }
}
function safeOpenAuth(){safeCall('openAuth');closeMainMenu();}
function safeOpenProfile(){safeCall('openProfile');closeMainMenu();}
function safeOpenRanking(){safeCall('openRanking');closeMainMenu();}
function safeOpenSettings(){safeCall('openSettings');closeMainMenu();}
function safeOpenWords(){safeCall('openWords');closeMainMenu();}
function safeOpenBet(){safeCall('openBet');closeMainMenu();}
function safeOpenShop(){safeCall('openShop');closeMainMenu();}
function safeStartTimer(){safeCall('startTimer');}
function safeNewGame(){safeCall('newGame');}
function safeGoLobby(){safeCall('goLobby');}

function toggleMainMenu(e){
    if(e)e.stopPropagation();
    const m=document.getElementById('mainCompactMenu');
    if(m)m.classList.toggle('show');
}
function closeMainMenu(){
    const m=document.getElementById('mainCompactMenu');
    if(m)m.classList.remove('show');
}
document.addEventListener('click',function(e){
    const m=document.getElementById('mainCompactMenu');
    const w=document.querySelector('.compactMenuWrap');
    if(m && w && !w.contains(e.target)) m.classList.remove('show');
});


function openSettings(){settingsModal.style.display='flex'}function openWords(){wordsModal.style.display='flex'}function openShop(){shopChips.innerHTML=currentChips;shopModal.style.display='flex'}function openBet(){betChips.innerHTML=currentChips;betModal.style.display='flex'}function closeModals(){document.querySelectorAll('.modal').forEach(m=>m.style.display='none')}

function loadLocalUsers(){
    try{return JSON.parse(localStorage.getItem('codenamesLocalUsers')||'{}')}catch(e){return {}}
}
function saveLocalUser(profile, password){
    if(!profile || !profile.username) return;
    const users=loadLocalUsers();
    users[profile.username.toLowerCase()]={
        profile:profile,
        password:password || (users[profile.username.toLowerCase()]&&users[profile.username.toLowerCase()].password) || ''
    };
    localStorage.setItem('codenamesLocalUsers',JSON.stringify(users));
}
function applyLoggedProfile(profile){
    currentAccount=profile.username;
    currentProfile=profile;
    if((profile.username||'').toLowerCase()==='yohanna'){currentProfile.vip=true;currentProfile.vipLevel='OWNER';currentProfile.membershipLabel='👑 OWNER';currentProfile.avatarFrame='baroque-owner';currentProfile.nameColor='owner';}
    currentChips=profile.chips || 1000;
    localStorage.setItem('codenamesAccount',currentAccount);
    localStorage.setItem('loggedUser',currentAccount);
    localStorage.setItem('loggedIn','true');
    localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
    if(playerName) playerName.value=currentAccount;
    if(authStatus) authStatus.innerHTML='Connecté : '+currentAccount;
    updateProfileChip(); refreshOwnerButton();
}
function localLoginFallback(username,password){
    const users=loadLocalUsers();
    const rec=users[(username||'').trim().toLowerCase()];
    if(rec && rec.password===password && rec.profile){
        applyLoggedProfile(rec.profile);
        requestFreshProfile();alert('Giriş yapıldı.');
        return true;
    }
    return false;
}
function requestFreshProfile(){
    if(currentAccount){
        socket.emit('request_profile',{account:currentAccount});
    }
}
function openAuth(){
    authModal.style.display='flex';
    authStatus.innerHTML = currentAccount ? 'Connecté : '+currentAccount : 'Henüz giriş yapılmadı.';
}
function updateProfileChip(){
    if(currentAccount){
        const avatarSrc = (currentProfile && currentProfile.avatarData) ? currentProfile.avatarData : defaultAvatarData((currentProfile && currentProfile.avatar) || 'woman.png');
        const isOwner = (currentAccount || '').toLowerCase() === 'yohanna';
        const vip = isOwner ? '<span class="ownerCrownBadge">👑 OWNER</span>' : (currentProfile && currentProfile.vip ? '<span class="vipBadgeSmall">VIP</span>' : '');
        const genderCls = isOwner ? 'ownerLuxuryName' : (((currentProfile && currentProfile.avatar) === 'man.png') ? 'genderMaleName' : 'genderFemaleName');
        const imgBorder = isOwner ? '4px double #d4af37' : '2px solid #d4af37';
        const imgShadow = isOwner ? '0 0 16px #d4af37,0 0 34px #000,0 0 48px rgba(255,215,0,.7)' : '0 0 10px #d4af37';
        const chipsText = isOwner ? '∞' : currentChips;
        const xpText = ((currentProfile && currentProfile.wins)||0)*100 + ((currentProfile && currentProfile.games)||0)*10;
        profileChip.innerHTML = '<img src="'+avatarSrc+'" style="width:36px;height:36px;border-radius:50%;object-fit:cover;border:'+imgBorder+';box-shadow:'+imgShadow+';"> <span class="'+genderCls+'">'+currentAccount+'</span>'+vip+' <span class="xpMini">🏆 XP '+xpText+'</span> <span>🪙 '+chipsText+'</span>';
    }else{
        profileChip.innerHTML='👤 Profil';
    }
    if(typeof refreshOwnerButton === 'function') refreshOwnerButton();
}


function restoreLoggedAccount(){
    let saved = localStorage.getItem('codenamesAccount') || localStorage.getItem('loggedUser') || '';
    let prof = localStorage.getItem('codenamesProfile');

    if(!saved && playerName && playerName.value.trim()){
        saved = playerName.value.trim();
    }

    if(saved){
        currentAccount = saved;
        localStorage.setItem('codenamesAccount', saved);
        localStorage.setItem('loggedUser', saved);
        localStorage.setItem('loggedIn', 'true');

        if(!currentProfile){
            try{ currentProfile = prof ? JSON.parse(prof) : null; }catch(e){ currentProfile = null; }
        }
        if(!currentProfile){
            currentProfile = {username:saved, chips:getSavedChips(saved), wins:0, games:0};
        }
        currentChips = currentProfile.chips || getSavedChips(saved) || 1000;
        if(playerName && !playerName.value.trim()) playerName.value = saved;
        if(authStatus) authStatus.innerHTML = 'Connecté : '+saved;
        updateProfileChip();
        requestFreshProfile();
        return true;
    }
    return false;
}

function requireLogin(){
    if(!currentAccount){
        restoreLoggedAccount();
    }

    // Sécurité : si l'interface affiche déjà un profil connecté,
    // on le réinjecte dans les vraies variables utilisées par le jeu.
    if(!currentAccount){
        const saved = localStorage.getItem('codenamesAccount') || localStorage.getItem('loggedUser') || (playerName && playerName.value.trim()) || '';
        if(saved){
            currentAccount = saved.trim();
        }
    }

    if(!currentAccount){
        alert('Önce giriş yapmalısın.');
        openAuth();
        return false;
    }
    if(!currentProfile){
        let prof = localStorage.getItem('codenamesProfile');
        try{ currentProfile = prof ? JSON.parse(prof) : null; }catch(e){ currentProfile = null; }
    }
    if(!currentProfile){
        currentProfile = {username:currentAccount, chips:getSavedChips(currentAccount), wins:0, games:0, avatar:'woman.png'};
    }
    if(!currentProfile.username) currentProfile.username = currentAccount;
    currentChips = currentProfile.chips || getSavedChips(currentAccount) || 1000;
    localStorage.setItem('codenamesAccount', currentAccount);
    localStorage.setItem('loggedUser', currentAccount);
    localStorage.setItem('loggedIn', 'true');
    localStorage.setItem('codenamesProfile', JSON.stringify(currentProfile));
    if(playerName && !playerName.value.trim()) playerName.value = currentAccount;
    if(authStatus) authStatus.innerHTML = 'Connecté : '+currentAccount;
    updateProfileChip();
    return true;
}
function openForgotPassword(){
    closeModals();
    forgotModal.style.display='flex';
}
function requestPasswordReset(){
    let e=forgotEmail.value.trim();
    if(!e){alert('Email yaz.');return}
    socket.emit('request_password_reset',{email:e});
}
function confirmPasswordReset(){
    let t=resetToken.value.trim(), p=newPassword.value;
    if(!t||!p){alert('Token ve yeni şifre gerekli.');return}
    socket.emit('confirm_password_reset',{token:t,newPassword:p});
}
function openProfile(){
    profileModal.style.display='flex';
    if(!currentProfile){
        profileInfo.innerHTML='Giriş yapmadın.';
        return;
    }
    const avatarSrc = currentProfile.avatarData || defaultAvatarData(currentProfile.avatar || 'woman.png');
    profileInfo.innerHTML =
        '<div style="text-align:center;margin-bottom:10px;"><img src="'+avatarSrc+'" style="width:95px;height:95px;border-radius:50%;object-fit:cover;border:4px solid #d4af37;box-shadow:0 0 18px #d4af37;"></div>'+
        '<b>Kullanıcı:</b> '+currentProfile.username+'<br><b>Email:</b> '+(currentProfile.email||'-')+
        '<br><b>Jeton:</b> 🪙 '+currentProfile.chips+
        '<br><b>Victoires:</b> '+currentProfile.wins+
        '<br><b>Parties:</b> '+currentProfile.games+
        '<br><b>Cadre:</b> '+(currentProfile.avatarFrame||'none')+
        '<br><b>Couleur:</b> '+(currentProfile.nameColor||'default')+
        '<br><b>Üyelik:</b> '+(((currentAccount||'').toLowerCase()==='yohanna')?'👑 OWNER':(currentProfile.membershipLabel||'Üyelik yok'))+
        '<br><b>VIP:</b> '+(currentProfile.vip ? (currentProfile.vipLevel||'VIP') : 'Non')+
        '<br><b>Inventaire:</b> '+((currentProfile.inventory||[]).join(', ')||'-');
}
function openRanking(){
    rankingModal.style.display='flex';
    socket.emit('get_ranking');
}

function isOwnerAccount(){return (currentAccount||'').toLowerCase()==='yohanna'}
function refreshOwnerButton(){const b=document.getElementById('ownerPanelBtn');if(b)b.style.display = isOwnerAccount() ? 'block' : 'none';}
function openOwnerPanel(){ if(!isOwnerAccount()){alert('Bu panel sadece Yohanna içindir.');return} ownerPanelModal.style.display='flex'; ownerLoadPanel(); }
function ownerLoadPanel(){ socket.emit('owner_get_panel',{owner:currentAccount}); }
function ownerTarget(){ return ownerTargetUser.value.trim(); }
function ownerPickUser(u){ ownerTargetUser.value=u; ownerPanelResult.innerHTML='Kullanıcı seçildi: '+u; }
function ownerUserAction(action){ const t=ownerTarget(); if(!t){alert('Önce kullanıcı seç veya kullanıcı adını yaz.');return} socket.emit('owner_manage_user',{owner:currentAccount,target:t,action}); }
function ownerChip(amount){ const t=ownerTarget(); if(!t){alert('Önce kullanıcı seç veya kullanıcı adını yaz.');return} socket.emit('owner_manage_user',{owner:currentAccount,target:t,action: amount>0?'add_chips':'remove_chips',amount:Math.abs(amount)}); }
function ownerSetMembership(level){ const t=ownerTarget(); if(!t){alert('Önce kullanıcı seç veya kullanıcı adını yaz.');return} socket.emit('owner_set_membership',{owner:currentAccount,target:t,level:level||ownerMembershipLevel.value,duration:ownerMembershipDuration.value}); }
function ownerSaveWheel(){ const limit=parseInt(ownerWheelLimit.value); socket.emit('owner_update_settings',{owner:currentAccount,wheel:limit!==0,wheelDailyLimit:limit===0?1:limit}); }
function ownerUpdateRequest(){ socket.emit('owner_update_request',{owner:currentAccount,id:ownerReqId.value,status:ownerReqStatus.value,result:ownerReqResult.value}); }
function ownerSaveSiteSettings(){ socket.emit('owner_update_settings',{owner:currentAccount,maintenance:setMaintenance.checked,registrations:setRegistrations.checked,wheel:setWheel.checked,tarot:setTarot.checked,ritual:setRitual.checked}); }
socket.on('owner_panel_data',d=>{
    if(!d.ok){alert(d.msg);return}
    ownerStats.innerHTML='Toplam kullanıcı: '+d.stats.totalUsers+'<br>Online kullanıcı: '+d.stats.onlineUsers+'<br>Bugünkü kayıt: '+d.stats.todayUsers+'<br>Satılan jeton: '+d.stats.soldChips+'<br>Tamamlanan tarot: '+d.stats.completedTarot+'<br>Tamamlanan ritüel: '+d.stats.completedRitual;
    ownerUserList.innerHTML='<h3>👥 Kullanıcılar</h3>'+d.users.map(u=>{
        const q = JSON.stringify(u.username);
        return `<div class="profileCard"><b>${u.username}</b> · 🪙 ${u.chips} · ${u.membershipLabel||'Üyelik yok'}<br>
        <button onclick='ownerPickUser(${q})'>Seç</button>
        <button onclick='ownerPickUser(${q});ownerSetMembership("bronze")'>🥉 Bronz ver</button>
        <button onclick='ownerPickUser(${q});ownerSetMembership("silver")'>🥈 Gümüş ver</button>
        <button onclick='ownerPickUser(${q});ownerSetMembership("none")'>Kaldır</button></div>`;
    }).join('');
    if(d.settings){setMaintenance.checked=!!d.settings.maintenance;setRegistrations.checked=!!d.settings.registrations;setWheel.checked=!!d.settings.wheel;setTarot.checked=!!d.settings.tarot;setRitual.checked=!!d.settings.ritual;ownerWheelLimit.value=String(d.settings.wheel?d.settings.wheelDailyLimit||1:0);}
});
socket.on('owner_action_result',d=>{ownerPanelResult.innerHTML=d.msg;if(!d.ok)alert(d.msg);ownerLoadPanel();});
function registerAccount(){
    let u=regUsername.value.trim(), e=regEmail.value.trim(), p=regPassword.value, p2=regPassword2.value;
    if(!u||!e||!p||!p2){alert('Kullanıcı adı, email ve 2 şifre alanını doldur.');return}
    if(p!==p2){alert('Şifreler aynı değil.');return}
    socket.emit('register_account',{username:u,email:e,password:p,avatar:avatarChoice.value});
}
function loginAccount(){
    let u=loginUsername.value.trim(), p=loginPassword.value;
    if(!u||!p){alert('Kullanıcı adı ve şifre yaz.');return}
    socket.emit('login_account',{username:u,password:p});
}
function logoutAccount(){
    currentAccount=null; currentProfile=null;
    localStorage.removeItem('codenamesAccount');
    localStorage.removeItem('loggedUser');
    localStorage.removeItem('loggedIn');
    localStorage.removeItem('codenamesProfile');
    localStorage.removeItem('codenamesRoom');
    localStorage.removeItem('codenamesName');
    authStatus.innerHTML='Çıkış yapıldı.';
    updateProfileChip();alert('Çıkış yapıldı.');
}

function createRoom(){if(!requireLogin())return;myName=currentAccount;playerName.value=currentAccount;localStorage.setItem('codenamesName',currentAccount);socket.emit('create_room',{password:roomPassword.value.trim(),account:currentAccount})}function joinExistingRoom(){if(!requireLogin())return;myName=currentAccount;playerName.value=currentAccount;localStorage.setItem('codenamesName',currentAccount);let c=roomInput.value.trim().toUpperCase();if(!c){alert('Oda kodu yaz.');return}socket.emit('join_room_code',{room:c,password:roomPassword.value.trim(),account:currentAccount})}function sitAtTable(){if(!requireLogin())return;if(!roomCode){alert('Önce oda oluştur veya odaya katıl.');return}let n=playerName.value.trim();if(!n){alert('Oyuncu adı yaz.');return}myName=n;myRole=roleChoice.value;myTeam=teamChoice.value;currentChips=currentProfile?currentProfile.chips:getSavedChips(myName);joined=true;saveLocalProfile();socket.emit('sit',{room:roomCode,name:n,avatar:avatarChoice.value,avatarData:(currentProfile&&currentProfile.avatarData)||'',nameColor:(currentProfile&&currentProfile.nameColor)||'default',avatarFrame:(currentProfile&&currentProfile.avatarFrame)||'none',team:myTeam,role:myRole,chips:currentChips,account:currentAccount})}function startGame(){if(!requireLogin())return;if(!joined){alert('Önce masaya otur.');return}socket.emit('start_game',{room:roomCode})}function newGame(){dealSoundPlayed=false;lastOpenedStates=[];lastOpenedMeta=[];lastWinner='';socket.emit('new_game',{room:roomCode})}function goLobby(){gameScreen.classList.add('hidden');lobby.classList.remove('hidden')}function joinTeam(t,r){if(!requireLogin())return;myTeam=t;myRole=r;saveLocalProfile();socket.emit('join_team',{room:roomCode,team:t,role:r})}function toggleGuess(i){unlockSfx();socket.emit('toggle_guess',{room:roomCode,index:i})}function revealCard(i,e){if(e)e.stopPropagation();unlockSfx();playTone(740,.045,'triangle',.035);socket.emit('reveal_card',{room:roomCode,index:i})}function showGuesses(i,e){if(e)e.stopPropagation();socket.emit('show_guesses',{room:roomCode,index:i})}function sendClue(){let c=clueText.value.trim(),n=clueNumber.value;if(!c){alert('İpucu yaz.');return}socket.emit('send_clue',{room:roomCode,clue:c,number:n,name:myName})}function endTurn(){socket.emit('end_turn',{room:roomCode})}function setCategory(c){socket.emit('set_category',{room:roomCode,category:c});closeModals()}function buyVirtualChips(a){if(!myName){alert('Önce profil oluştur.');return}socket.emit('buy_virtual_chips',{room:roomCode,amount:a});closeModals()}
function demoBuyChips(amount, provider){
    if(!currentAccount){alert('Önce giriş yap.');openAuth();return}
    if(!confirm(provider+' démo ile '+amount+' jeton eklensin mi?')) return;
    socket.emit('buy_virtual_chips',{room:roomCode,amount:amount});
}
function buyVipWithChips(pack){
    if(!currentAccount){alert('Önce giriş yap.');openAuth();return}
    socket.emit('buy_vip_with_chips',{room:roomCode,pack:pack,account:currentAccount});
}

function buyCosmetic(item){
    if(!currentAccount){alert('Önce giriş yap.');return}
    socket.emit('buy_cosmetic',{item:item,room:roomCode,account:currentAccount});
}
function equipCosmetic(item){
    if(!currentAccount){alert('Önce giriş yap.');return}
    socket.emit('equip_cosmetic',{item:item,room:roomCode,account:currentAccount});
}
function deleteAvatar(){ if(!currentAccount){alert('Önce giriş yap.');return} socket.emit('delete_avatar',{room:roomCode,account:currentAccount}); }
function uploadAvatar(){
    if(!currentAccount){alert('Önce giriş yap.');return}
    const file = avatarUploadInput.files[0];
    if(!file){alert('Resim seç.');return}
    if(file.size > 1800000){
        alert('Resim çok büyük. 1.8 MB altında bir resim seç.');
        return;
    }
    const reader = new FileReader();
    reader.onload = function(){
        socket.emit('upload_avatar',{room:roomCode,account:currentAccount,avatarData:reader.result});
    };
    reader.readAsDataURL(file);
}

function toggleReady(){
    if(!requireLogin())return;
    if(!roomCode){alert('Önce oda oluştur veya odaya katıl.');return}
    if(!joined){alert('Önce masaya otur.');return}
    socket.emit('toggle_ready',{room:roomCode});
}
function renderReady(players, ready){
    let total=players.filter(p=>p.team!=='spectator').length;
    let ok=players.filter(p=>p.team!=='spectator' && ready[p.sid]).length;
    readyInfo.innerHTML='Hazır: '+ok+' / '+total;
}
function setChatMode(m){
    chatMode=m;
    chatModeText.innerHTML='Mode: '+(m==='global'?'Genel':m==='team'?'Takım':'DM');
}
function addEmoji(e){
    chatInput.value += e;
    chatInput.focus();
}
function refreshDmTargets(players){
    if(!dmTarget) return;
    let current=dmTarget.value;
    dmTarget.innerHTML='<option value="">DM oyuncu seç</option>';
    players.forEach(p=>{
        if(p.sid!==mySid){
            dmTarget.innerHTML+=`<option value="${p.sid}">${p.name}</option>`;
        }
    });
    dmTarget.value=current;
}
function placeBet(){let a=parseInt(betAmount.value);if(!a||a<=0){alert('Geçerli jeton miktarı yaz.');return}socket.emit('place_bet',{room:roomCode,team:betTeam.value,amount:a})}function toggleTeamLock(t){socket.emit('toggle_lock',{room:roomCode,team:t})}function adminNewGame(){socket.emit('admin_new_game',{room:roomCode})}function adminRevealAll(){socket.emit('admin_reveal_all',{room:roomCode})}function adminResetStats(){socket.emit('admin_reset_stats',{room:roomCode})}function kickPlayer(s){socket.emit('kick_player',{room:roomCode,sid:s})}function makeSpectator(s){socket.emit('admin_move_player',{room:roomCode,sid:s,team:'spectator',role:'spectator'})}function movePlayer(s,t){socket.emit('admin_move_player',{room:roomCode,sid:s,team:t,role:'player'})}function makeAdmin(s){socket.emit('make_admin',{room:roomCode,sid:s})}function sendMessage(){
let m=chatInput.value.trim();if(!m)return;
if(chatMode==='team'){
    socket.emit('team_chat',{room:roomCode,name:myName||'Oyuncu',team:myTeam,msg:m});
}else if(chatMode==='dm'){
    if(!dmTarget.value){alert('DM için oyuncu seç.');return}
    socket.emit('dm_chat',{room:roomCode,name:myName||'Oyuncu',to:dmTarget.value,msg:m});
}else{
    socket.emit('chat',{room:roomCode,name:myName||'Oyuncu',msg:m});
}
chatInput.value='';
}function canSeeRole(){return myRole==='blueSpy'||myRole==='redSpy'||myRole==='spectator'}
function renderPlayers(players,locks){
    lastPlayers = players;
    refreshDmTargets(players);
    lastLocks = locks;

    blueLobby.innerHTML = '';
    redLobby.innerHTML = '';
    spectatorLobby.innerHTML = '';
    bluePlayers.innerHTML = '';
    redPlayers.innerHTML = '';
    onlinePlayers.innerHTML = '';
    spectatorList.innerHTML = '';

    blueSeatBox.classList.toggle('lockedSeat',locks.blue);
    redSeatBox.classList.toggle('lockedSeat',locks.red);
    blueLockText.innerHTML = locks.blue ? '🔒' : '';
    redLockText.innerHTML = locks.red ? '🔒' : '';

    let ba=[],ra=[],bs=[],rs=[],sp=[];

    function micHtml(p){
        const st = currentMicStates[p.sid] || {mic:false,speaking:false};
        const badge = st.mic ? '🎤' : '🚫🎤';
        const speakingClass = st.speaking ? ' speakingAvatar' : '';
        const isOwnerPlayer=((p.account||p.name||'').toLowerCase()==='yohanna'); const nameClass = (st.speaking ? ' speakingName ' : ' ') + playerNameClass(p) + ' ' + playerGenderClass(p) + (isOwnerPlayer?' ownerLuxuryName':'');
        const frameClass = playerFrameClass(p);
        const av = `<span class="avatarWrap ${frameClass}"><img src="${playerAvatarSrc(p)}" class="${avatarClass(p.avatar)}${speakingClass}"><span class="micBadge">${badge}</span></span>`;
        return {av,nameClass};
    }

    players.forEach(p=>{
        let crown=p.isAdmin?' 👑':'';
        let chips=p.chips||1000;
        let readyMark=(currentReady&&currentReady[p.sid])?'<span class="readyBadge readyYes">Hazır</span>':'<span class="readyBadge readyNo">Bekliyor</span>';
        let mh=micHtml(p);
        let av=mh.av;

        if(p.team==='blue'){
            blueLobby.innerHTML+=`<div>${av}<br><span class="${mh.nameClass}">${p.name}</span>${crown} ${readyMark}</div>`;
            bluePlayers.innerHTML+=`${av} <span class="${mh.nameClass}">${p.name}</span>${crown} — ${roleLabel(p.role)} — 🪙 ${chips}<br>`;
        }else if(p.team==='red'){
            redLobby.innerHTML+=`<div>${av}<br><span class="${mh.nameClass}">${p.name}</span>${crown} ${readyMark}</div>`;
            redPlayers.innerHTML+=`${av} <span class="${mh.nameClass}">${p.name}</span>${crown} — ${roleLabel(p.role)} — 🪙 ${chips}<br>`;
        }else{
            spectatorLobby.innerHTML+=`<div>${av}<br><span class="${mh.nameClass}">${p.name}</span>${crown} ${readyMark}</div>`;
            sp.push(`${p.name} 🪙 ${chips}`);
        }

        if(p.role==='blueSpy') bs.push(p.name);
        else if(p.role==='redSpy') rs.push(p.name);
        else if(p.team==='blue') ba.push(p.name);
        else if(p.team==='red') ra.push(p.name);

        let adm='';
        if(isAdmin&&p.sid!==mySid){
            adm=`<div class="adminActions"><button onclick="makeAdmin('${p.sid}')">👑 Admin Yap</button><button onclick="movePlayer('${p.sid}','blue')">🔵 Maviye Al</button><button onclick="movePlayer('${p.sid}','red')">🔴 Kırmızıya Al</button><button onclick="makeSpectator('${p.sid}')">👀 Seyirci</button><button onclick="kickPlayer('${p.sid}')">🚫 At</button></div>`;
        }

        onlinePlayers.innerHTML+=`<div class="profileCard">${av} <b class="${mh.nameClass}">${p.name}</b>${crown}<br>${teamLabel(p.team)}<br>${roleLabel(p.role)}<br>🪙 ${chips}${adm}</div>`;
    });

    spectatorList.innerHTML=sp.length?sp.join('<br>'):'-';
    bluePlayers.innerHTML+=`<hr>🕵️ Mavi Spymaster: ${bs.join(', ')||'-'}<br>👤 Mavi Saha Ajanı: ${ba.join(', ')||'-'}`;
    redPlayers.innerHTML+=`<hr>🕵️ Kırmızı Spymaster: ${rs.join(', ')||'-'}<br>👤 Kırmızı Saha Ajanı: ${ra.join(', ')||'-'}`;
}
function renderStats(st){scoreText.innerHTML='🏆 Mavi: '+st.blueWins+' | Kırmızı: '+st.redWins;let h=st.history.length?st.history.slice(-8).reverse().map(w=>'🏆 '+w).join('<br>'):'Henüz kazanan yok.';if(st.betHistory&&st.betHistory.length)h+='<hr><b>🎰 Bahis Kaydı</b><br>'+st.betHistory.slice(-8).reverse().join('<br>');if(st.wordHistory&&st.wordHistory.length){h+='<hr><b>📝 Oyun Kaydı / Kelimeler</b><br>';st.wordHistory.slice(-5).reverse().forEach(g=>{h+=`<br><b>Parti ${g.gameNo}</b> — ${g.winner}<br><small>${g.words.join(', ')}</small><br>`})}historyPanel.innerHTML=h}function renderBets(b){let l=Object.values(b||{});betInfo.innerHTML=l.length?l.map(x=>`🎰 ${x.name}: ${x.amount} 🪙 → ${x.team==='blue'?'Mavi':'Kırmızı'}`).join('<br>'):'Henüz bahis yok.'}

let sfxCtx=null;
let sfxUnlocked=false;
let lastOpenedMeta=[];

function unlockSfx(){
    try{
        if(!sfxCtx) sfxCtx = new (window.AudioContext || window.webkitAudioContext)();
        if(sfxCtx.state === 'suspended') sfxCtx.resume();
        sfxUnlocked = true;
    }catch(e){}
}
document.addEventListener('click', unlockSfx, {once:false});
document.addEventListener('touchstart', unlockSfx, {once:false});

function playTone(freq,duration,type='sine',volume=.08,delay=0){
    try{
        unlockSfx();
        if(!sfxCtx) return;
        const now=sfxCtx.currentTime+delay;
        const osc = sfxCtx.createOscillator();
        const gain = sfxCtx.createGain();
        osc.type = type;
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(volume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        osc.connect(gain);
        gain.connect(sfxCtx.destination);
        osc.start(now);
        osc.stop(now + duration);
    }catch(e){}
}
function soundBlueTeamCard(){
    playTone(520,.11,'triangle',.09,0);
    playTone(700,.10,'sine',.075,.09);
    playTone(920,.08,'triangle',.055,.17);
}
function soundRedTeamCard(){
    playTone(360,.12,'sawtooth',.08,0);
    playTone(520,.11,'triangle',.07,.10);
    playTone(690,.09,'sine',.055,.19);
}
function soundOwnTeam(role){
    if(role==='blue') soundBlueTeamCard();
    else if(role==='red') soundRedTeamCard();
    else soundCorrect();
}
function soundOpponentTeam(role){
    if(role==='blue'){
        playTone(260,.12,'square',.075,0);
        playTone(180,.14,'sawtooth',.06,.11);
    }else if(role==='red'){
        playTone(300,.12,'square',.075,0);
        playTone(210,.14,'sawtooth',.06,.11);
    }else{
        soundWrong();
    }
}
function soundNeutral(){
    playTone(440,.09,'sine',.055,0);
    playTone(440,.09,'sine',.045,.13);
    playTone(390,.12,'triangle',.04,.26);
}
function soundAssassin(){
    playTone(80,.38,'sawtooth',.13,0);
    playTone(45,.50,'sawtooth',.11,.13);
    playTone(120,.20,'square',.07,.28);
}
function soundWin(team){
    if(team==='blue'){
        [520,660,880,1180].forEach((f,i)=>playTone(f,.14,'triangle',.09,i*.11));
    }else{
        [430,610,760,980].forEach((f,i)=>playTone(f,.14,'sine',.09,i*.11));
    }
}
function soundLose(team){
    if(team==='blue'){
        [300,240,190,130].forEach((f,i)=>playTone(f,.20,'sawtooth',.07,i*.12));
    }else{
        [340,260,200,150].forEach((f,i)=>playTone(f,.20,'square',.065,i*.12));
    }
}
function soundDeal(i){
    setTimeout(()=>playTone(220+(i%5)*35,.08,'triangle',.035), i*45);
}
function soundCorrect(){ soundOwnTeam(myTeam); }
function soundWrong(){ soundOpponentTeam(myTeam==='blue'?'red':'blue'); }
function cardRoleClass(role){
    if(role==='blue') return 'blueCard';
    if(role==='red') return 'redCard';
    if(role==='neutral') return 'neutralCard';
    if(role==='assassin') return 'assassinCard';
    return '';
}
function formatClueLog(logs){
    if(!logs || !logs.length) return '📜 Oyun bandı: Henüz ipucu yok.';
    return '📜 Oyun bandı:<br>' + logs.slice(-8).reverse().map(x=>{
        let cls = x.includes('Mavi Takım') ? 'blueClue' : (x.includes('Kırmızı Takım') ? 'redClue' : '');
        return '<span class="clueNeon '+cls+'">💡 '+x+'</span>';
    }).join('');
}
function leaveTable(){ lastOpenedMeta=[]; lastWinner='';
    if(!roomCode){return;}
    joined=false;
    myTeam='spectator';
    myRole='spectator';
    localStorage.removeItem('codenamesTeam');
    localStorage.removeItem('codenamesRole');
    socket.emit('leave_table',{room:roomCode});
    if(gameScreen) gameScreen.classList.add('hidden');
    if(lobby) lobby.classList.remove('hidden');
}
function closeCurrentTable(){ lastOpenedMeta=[]; lastWinner='';
    try{ stopMic(); }catch(e){}
    roomCode='';
    joined=false;
    myTeam='';
    myRole='';
    localStorage.removeItem('codenamesRoom');
    if(roomInput) roomInput.value='';
    if(roomText) roomText.innerHTML='Oda: -';
    if(board) board.innerHTML='';
    if(gameScreen) gameScreen.classList.add('hidden');
    if(lobby) lobby.classList.remove('hidden');
    alert('Masa kapatıldı. Yeni oda açabilirsin.');
}

function detectCardSounds(g){
    if(!g || !g.cards) return;

    // Première image du plateau : on mémorise seulement, sans son d'ouverture.
    if(!lastOpenedMeta || !lastOpenedMeta.length){
        lastOpenedMeta = g.cards.map(c=>({open:!!c.open, role:c.role}));
        if(g.winner) lastWinner = g.winner;
        return;
    }

    let openedSomething = false;

    g.cards.forEach((c,i)=>{
        const old = lastOpenedMeta[i] || {open:false, role:c.role};
        if(c.open && !old.open){
            openedSomething = true;

            if(c.role === 'assassin'){
                soundAssassin();
            }else if(c.role === 'neutral'){
                soundNeutral();
            }else if(c.role === myTeam){
                soundOwnTeam(c.role);
            }else if(c.role === 'blue' || c.role === 'red'){
                soundOpponentTeam(c.role);
            }else{
                soundNeutral();
            }
        }
    });

    lastOpenedMeta = g.cards.map(c=>({open:!!c.open, role:c.role}));

    if(g.winner && g.winner !== lastWinner){
        let winTeam = '';
        const upper = String(g.winner).toUpperCase();
        if(upper.includes('MAVİ')) winTeam = 'blue';
        if(upper.includes('KIRMIZI')) winTeam = 'red';

        if(winTeam){
            soundWin(winTeam);
            setTimeout(()=>soundLose(winTeam === 'blue' ? 'red' : 'blue'), 650);
        }else{
            soundWin('blue');
        }

        lastWinner = g.winner;
    }
}
function renderGame(g){board.innerHTML='';roundText.innerHTML='🎮 Tur: '+(g.roundNo||1);blueCount.innerHTML=g.blueCount;redCount.innerHTML=g.redCount;phaseText.innerHTML=g.phase+((g.guessLimit&&g.guessLimit>0)?'<br>🎯 Tahmin hakkı: '+g.guessesMade+' / '+g.guessLimit:'');clueDisplay.innerHTML=g.clue;turnDisplay.innerHTML=g.turn==='blue'?'🔵 Sıra Mavi Takımda':'🔴 Sıra Kırmızı Takımda';clueLog.innerHTML=formatClueLog(g.clueLog);if(g.moveLog&&g.moveLog.length)clueLog.innerHTML+='<hr>🃏 Kart kaydı:<br>'+g.moveLog.slice(-8).reverse().join('<br>');g.cards.forEach((c,i)=>{let cls='card dealCard';if(c.guessed)cls+=' guessed';if(c.open||canSeeRole()||g.winner)cls+=' open '+c.role+'Card';let names=(c.guessedBy||[]).join(', '),gb=names?`<div class='guessName'>🎯 ${names}</div>`:'';board.innerHTML+=`<div id="card_${i}" class="${cls}" style="animation-delay:${i*45}ms" onclick="toggleGuess(${i})"><button class="revealBtn" onclick="revealCard(${i}, event)">A♠</button><button class="guessBtn" onclick="showGuesses(${i}, event)">Tahmin</button><span class="wordText">${c.word}</span>${gb}</div>`;if(!dealSoundPlayed)soundDeal(i)});if(!dealSoundPlayed)dealSoundPlayed=true;setTimeout(()=>detectCardSounds(g),80);if(g.winner){showWinner(g.winner);showEndGame(g)}}function showWinner(t){winnerText.innerHTML=t;winnerOverlay.style.display='flex';setTimeout(()=>winnerOverlay.style.display='none',5000)}function showEndGame(g){endGameTitle.innerHTML=g.winner;endGameInfo.innerHTML='🎮 Tur: '+(g.roundNo||1)+'<br>🔵 Kalan: '+g.blueCount+' | 🔴 Kalan: '+g.redCount+'<br><br>Yeni manche başlatabilir veya lobbyye dönebilirsin.';endGameModal.style.display='flex'}function updateTimerDisplay(){let m=Math.floor(seconds/60),s=seconds%60;timer.innerHTML=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')}function startTimer(){if(timerRunning)return;timerRunning=true;timerInterval=setInterval(()=>{if(seconds>0){seconds--;updateTimerDisplay()}},1000)}function pauseTimer(){timerRunning=false;clearInterval(timerInterval)}function setTimer(v){pauseTimer();seconds=v;updateTimerDisplay()}
socket.on('register_result',d=>{
    if(!d.ok){alert(d.msg);return}
    applyLoggedProfile(d.profile);
    saveLocalUser(currentProfile, regPassword.value);
    closeModals();
    alert('Hesap oluşturuldu.');
});

socket.on('login_result',d=>{
    if(!d.ok){
        if(localLoginFallback(loginUsername.value.trim(), loginPassword.value)){
            closeModals();
            return;
        }
        alert(d.msg);return
    }
    applyLoggedProfile(d.profile);
    saveLocalUser(currentProfile, loginPassword.value);
    closeModals();
    requestFreshProfile();alert('Giriş yapıldı.');
});

socket.on('profile_fresh',p=>{
    applyLoggedProfile(p);
    saveLocalUser(currentProfile);
});

socket.on('cosmetic_result',d=>{
    if(!d.ok){alert(d.msg);return}
    currentProfile=d.profile;
    currentAccount=d.profile.username || currentAccount;
    currentChips=d.profile.chips || 1000;
    localStorage.setItem('codenamesAccount',currentAccount);
    localStorage.setItem('loggedUser',currentAccount);
    localStorage.setItem('loggedIn','true');
    localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
    shopChips.innerHTML=currentChips;
    chipsText.innerHTML='🪙 Jeton: '+currentChips;
    updateProfileChip();
    alert(d.msg);
});
socket.on('avatar_upload_result',d=>{
    if(!d.ok){alert(d.msg);return}
    currentProfile=d.profile;
    currentAccount=d.profile.username || currentAccount;
    currentChips=d.profile.chips || currentChips || 1000;
    localStorage.setItem('codenamesAccount',currentAccount);
    localStorage.setItem('loggedUser',currentAccount);
    localStorage.setItem('loggedIn','true');
    localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
    saveLocalUser(currentProfile);
    updateProfileChip(); refreshOwnerButton();
    if(avatarChoice && currentProfile.avatar) avatarChoice.value=currentProfile.avatar;
    openProfile();
    alert('Avatar kaydedildi ve sisteme kaydedildi.');
});
socket.on('password_reset_requested',d=>{
    if(d.sent){
        resetLinkBox.innerHTML='Email gönderildi. Mail kutunu kontrol et.';
        alert('Şifre yenileme linki emailine gönderildi.');
    }else{
        resetLinkBox.innerHTML='Email sistemi ayarlı değil. Test linki: <br><b>'+d.link+'</b><br>Token: <b>'+d.token+'</b>';
        alert('Email sistemi Render üzerinde ayarlı değil. Test linki ekranda gösterildi.');
    }
});
socket.on('password_reset_confirmed',d=>{
    if(!d.ok){alert(d.msg);return}
    alert('Şifre yenilendi. Yeni şifreyle giriş yapabilirsin.');
    closeModals();
});
socket.on('ranking_result',d=>{
    if(!d.users||!d.users.length){
        rankingInfo.innerHTML='Henüz sıralama yok.';
        return;
    }
    rankingInfo.innerHTML=d.users.map((u,i)=>`${i+1}. <b>${u.username}</b> — 🪙 ${u.chips} — 🏆 ${u.wins} — 🎮 ${u.games}`).join('<br>');
});

socket.on('connect',()=>{
    mySid=socket.id;
    refreshOwnerButton();restoreLocalFields();
    const params=new URLSearchParams(window.location.search);if(params.get('reset')){openForgotPassword();resetToken.value=params.get('reset');}
    let a=localStorage.getItem('codenamesAccount') || localStorage.getItem('loggedUser');
    let prof=localStorage.getItem('codenamesProfile');
    if(a){
        currentAccount=a;
        try{currentProfile=prof?JSON.parse(prof):null;}catch(e){currentProfile=null;}
        if(!currentProfile){currentProfile={username:a,chips:getSavedChips(a),wins:0,games:0};}
        currentChips=currentProfile.chips || getSavedChips(a);
        playerName.value=a;
        authStatus.innerHTML='Connecté : '+a;
        updateProfileChip();
    }
    let savedRoom=localStorage.getItem('codenamesRoom')||'';
    let savedName=localStorage.getItem('codenamesName')||'';
    let savedPassword=localStorage.getItem('codenamesPassword')||'';
    if(savedRoom && savedName){
        pendingAutoSit=true;
        if(currentAccount){socket.emit('join_room_code',{room:savedRoom,password:savedPassword,account:currentAccount});}
    }
});socket.on('room_created',d=>{roomCode=d.room;isAdmin=true;roomText.innerHTML='Oda: '+roomCode+' 👑 Admin sensin';saveLocalProfile()});socket.on('room_joined',d=>{roomCode=d.room;isAdmin=false;roomText.innerHTML='Oda: '+roomCode;saveLocalProfile();if(pendingAutoSit){pendingAutoSit=false;setTimeout(()=>sitAtTable(),250)}});socket.on('error_msg',d=>alert(d.msg));socket.on('players_update',d=>{if(d.micStates) currentMicStates=d.micStates;if(d.ready) currentReady=d.ready;renderReady(d.players,d.ready||{});renderPlayers(d.players,d.locks)});socket.on('game_update',d=>{
    currentMicStates=d.micStates||currentMicStates||{};
    currentReady=d.ready||currentReady||{};
    let me=d.players.find(p=>p.sid===mySid||p.name===myName);
    if(me){
        myName=me.name;myTeam=me.team;myRole=me.role;isAdmin=me.isAdmin;currentChips=me.chips||1000;
        setSavedChips(myName,currentChips);
        if(currentProfile){
            currentProfile.chips=currentChips;
            currentProfile.avatarData = me.avatarData || currentProfile.avatarData || '';
            currentProfile.avatar = me.avatar || currentProfile.avatar || 'woman.png';
            currentProfile.nameColor = me.nameColor || currentProfile.nameColor || 'default';
            currentProfile.avatarFrame = me.avatarFrame || currentProfile.avatarFrame || 'none';
            localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
        }
        saveLocalProfile();
    }
    roleText.innerHTML='Bu cihazda: '+myName+' · Rol: '+roleLabel(myRole);
    chipsText.innerHTML='🪙 Jeton: '+currentChips;
    betChips.innerHTML=currentChips;
    shopChips.innerHTML=currentChips;
    updateProfileChip();
    renderReady(d.players,d.ready||{});
    renderPlayers(d.players,d.locks);
    renderStats(d.stats);
    renderBets(d.bets);
    if(d.game && d.game.started){
        lobby.classList.add('hidden');
        gameScreen.classList.remove('hidden');
        renderGame(d.game);
    }else{
        gameScreen.classList.add('hidden');
        lobby.classList.remove('hidden');
    }
});socket.on('chat_update',d=>{messages.innerHTML+='<b>🌍 '+d.name+':</b> '+d.msg+'<br>'});socket.on('team_chat_update',d=>{messages.innerHTML+='<b>🔒 '+d.name+':</b> '+d.msg+'<br>'});socket.on('dm_chat_update',d=>{messages.innerHTML+='<b>📩 '+d.name+':</b> '+d.msg+'<br>'});socket.on('kicked',()=>{alert('Odadan çıkarıldın.');localStorage.clear();location.reload()});socket.on('made_spectator',()=>{myRole='spectator';myTeam='spectator';saveLocalProfile();alert('Seyirci moduna alındın.')});socket.on('guess_names',d=>{alert('Bu kartı tahmin edenler: '+((d.names&&d.names.length)?d.names.join(', '):'Henüz tahmin yok.'))});

socket.on('voice_existing_users',d=>{
    if(!voiceStarted) return;
    (d.users||[]).forEach(sid=>{
        if(sid!==mySid) createPeer(sid,true);
    });
});

socket.on('voice_user_joined',d=>{
    if(!voiceStarted) return;
    if(d.sid!==mySid) createPeer(d.sid,false);
});

socket.on('voice_user_left',d=>{
    if(voicePeers[d.sid]){
        voicePeers[d.sid].close();
        delete voicePeers[d.sid];
    }
    const audio=document.getElementById('audio_'+d.sid);
    if(audio) audio.remove();
});

socket.on('voice_signal',async d=>{
    if(!voiceStarted) return;
    const pc=createPeer(d.from,false);

    if(d.data.sdp){
        await pc.setRemoteDescription(new RTCSessionDescription(d.data.sdp));
        if(d.data.sdp.type==='offer'){
            const answer=await pc.createAnswer();
            await pc.setLocalDescription(answer);
            socket.emit('voice_signal',{
                room:roomCode,
                to:d.from,
                data:{sdp:pc.localDescription}
            });
        }
    }

    if(d.data.candidate){
        try{await pc.addIceCandidate(new RTCIceCandidate(d.data.candidate));}catch(e){}
    }
});

socket.on('mic_state_update',d=>{
    currentMicStates=d.micStates||{};
    if(lastPlayers.length) renderPlayers(lastPlayers,lastLocks);
});

updateTimerDisplay();

/* === MAIN HARD BUTTON CLICK FIX === */
function closeMainMenu(){
    const m=document.getElementById('mainCompactMenu');
    if(m)m.classList.remove('show');
}
function hardBindMainButtons(){
    const bind=(id,fn)=>{
        const el=document.getElementById(id);
        if(!el)return;
        el.onclick=function(e){
            e.preventDefault();
            e.stopPropagation();
            try{fn();}catch(err){console.error('button '+id,err);alert('Buton hatası: '+id+' / '+err.message);}
            return false;
        };
    };
    bind('menuToggleBtn',()=>{const m=document.getElementById('mainCompactMenu');if(m)m.classList.toggle('show');});
    bind('btnTimerTop',()=>{startTimer();});
    bind('btnNewGameTop',()=>{newGame();});
    bind('btnLobbyTop',()=>{goLobby();});
    bind('menuAuthBtn',()=>{openAuth();closeMainMenu();});
    bind('menuProfileBtn',()=>{openProfile();closeMainMenu();});
    bind('menuRankingBtn',()=>{openRanking();closeMainMenu();});
    bind('menuSettingsBtn',()=>{openSettings();closeMainMenu();});
    bind('menuWordsBtn',()=>{openWords();closeMainMenu();});
    bind('menuBetBtn',()=>{openBet();closeMainMenu();});
    bind('ownerPanelBtn',()=>{openOwnerPanel();closeMainMenu();});
}
document.addEventListener('DOMContentLoaded',hardBindMainButtons);
setTimeout(hardBindMainButtons,300);
setTimeout(hardBindMainButtons,1200);
document.addEventListener('click',function(e){
    const w=document.querySelector('.compactMenuWrap');
    const m=document.getElementById('mainCompactMenu');
    if(w&&m&&!w.contains(e.target))m.classList.remove('show');
});
</script></body></html>
'''

@app.route('/old-home-disabled')
def home():
    return HOME_HTML

@app.route('/codenames')
def index():
    return render_template_string(HTML)

@app.route('/coming-soon/<game>')
def coming_soon(game):
    return render_template_string(COMING_SOON_HTML, game=game)



@socketio.on('request_profile')
def request_profile(data):
    account = ensure_user_account(data.get('account'))
    users = load_users()
    if account and account in users:
        emit('profile_fresh', private_profile(account, users[account]))

@socketio.on('register_account')
def register_account(data):
    username = data.get('username','').strip()
    email = data.get('email','').strip().lower()
    password = data.get('password','')
    avatar = data.get('avatar','woman.png')

    if not username or not email or not password:
        emit('register_result', {'ok': False, 'msg': 'Kullanıcı adı, email ve şifre gerekli.'})
        return

    if '@' not in email or '.' not in email:
        emit('register_result', {'ok': False, 'msg': 'Geçerli bir email yaz.'})
        return

    users = load_users()
    if find_user_key(users, username):
        emit('register_result', {'ok': False, 'msg': 'Bu kullanıcı adı zaten var.'})
        return

    for udata in users.values():
        if udata.get('email','').lower() == email:
            emit('register_result', {'ok': False, 'msg': 'Bu email zaten kayıtlı.'})
            return

    users[username] = {
        'email': email,
        'password_hash': hash_password(password),
        'chips': 1000,
        'wins': 0,
        'games': 0,
        'avatar': avatar,
        'avatarData': '',
        'nameColor': 'default',
        'avatarFrame': 'none',
        'inventory': [],
        'createdAt': str(int(time.time()))
    }
    save_users(users)
    emit('register_result', {'ok': True, 'profile': private_profile(username, users[username])})


@socketio.on('login_account')
def login_account(data):
    username = data.get('username','').strip()
    password = data.get('password','')

    users = load_users()
    user_key = find_user_key(users, username)
    if not user_key or not verify_password(users[user_key], password):
        emit('login_result', {'ok': False, 'msg': 'Kullanıcı adı veya şifre yanlış.', 'username': username})
        return

    # Si un ancien compte en texte brut a été migré, on sauvegarde le hash.
    save_users(users)
    emit('login_result', {'ok': True, 'profile': private_profile(user_key, users[user_key])})


@socketio.on('get_ranking')
def get_ranking():
    users = load_users()
    ranking = [public_profile(u, d) for u, d in users.items()]
    ranking.sort(key=lambda x: (int(x.get('wins',0)), int(x.get('chips',0))), reverse=True)
    emit('ranking_result', {'users': ranking[:20]})


@socketio.on('request_password_reset')
def request_password_reset(data):
    email = data.get('email','').strip().lower()
    users = load_users()
    found_user = None
    for username, udata in users.items():
        if udata.get('email','').lower() == email:
            found_user = username
            break

    # Réponse neutre pour ne pas révéler les emails enregistrés.
    if not found_user:
        emit('password_reset_requested', {'sent': True})
        return

    token = ''.join(random.choices(string.ascii_letters + string.digits, k=42))
    users[found_user]['resetToken'] = token
    users[found_user]['resetExpires'] = int(time.time()) + 3600
    save_users(users)

    base_url = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
    if not base_url:
        base_url = 'https://codenames-vip.onrender.com'
    reset_link = base_url + '/?reset=' + token

    sent = send_reset_email(email, reset_link)
    emit('password_reset_requested', {'sent': sent, 'link': reset_link, 'token': token})


@socketio.on('confirm_password_reset')
def confirm_password_reset(data):
    token = data.get('token','').strip()
    new_password = data.get('newPassword','')

    if not token or not new_password:
        emit('password_reset_confirmed', {'ok': False, 'msg': 'Token ve yeni şifre gerekli.'})
        return

    users = load_users()
    for username, udata in users.items():
        if udata.get('resetToken') == token and int(udata.get('resetExpires', 0)) >= int(time.time()):
            users[username]['password_hash'] = hash_password(new_password)
            users[username].pop('resetToken', None)
            users[username].pop('resetExpires', None)
            save_users(users)
            emit('password_reset_confirmed', {'ok': True})
            return

    emit('password_reset_confirmed', {'ok': False, 'msg': 'Token geçersiz veya süresi dolmuş.'})


@socketio.on('create_room')
def create_room(data):
    account = ensure_user_account(data.get('account'))
    if not account:
        emit('error_msg', {'msg':'Oda oluşturmak için önce giriş yapmalısın.'})
        return
    code = room_code(); password = data.get('password','')
    rooms[code] = {'players': [], 'game': new_game('default'), 'stats': {'blueWins':0,'redWins':0,'history':[],'wordHistory':[],'betHistory':[],'gameNo':0}, 'locks': {'blue':False,'red':False}, 'password': password, 'adminSid': request.sid, 'bets': {}, 'micStates': {}, 'ready': {}, 'teamChat': {'blue': [], 'red': []}, 'dm': {}, 'category': 'default'}
    join_room(code); emit('room_created', {'room': code})

@socketio.on('join_room_code')
def join_room_code(data):
    account = ensure_user_account(data.get('account'))
    if not account:
        emit('error_msg', {'msg':'Odaya katılmak için önce giriş yapmalısın.'})
        return
    code = data['room']; password = data.get('password','')
    if code not in rooms: emit('error_msg', {'msg':'Oda bulunamadı.'}); return
    if rooms[code]['password'] and rooms[code]['password'] != password: emit('error_msg', {'msg':'Oda şifresi yanlış.'}); return
    join_room(code); emit('room_joined', {'room': code}); emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks'], 'micStates': rooms[code].get('micStates', {}), 'ready': rooms[code].get('ready', {})})

@socketio.on('sit')
def sit(data):
    account = ensure_user_account(data.get('account'))
    if not account:
        emit('error_msg', {'msg':'Oynamak için önce giriş yapmalısın.'})
        return
    data['account'] = account
    code = data['room']
    if code not in rooms: return
    old = by_name(code, data['name'])
    if len(rooms[code]['players']) >= MAX_PLAYERS and not old: emit('error_msg', {'msg':'Oda dolu. En fazla 10 oyuncu girebilir.'}); return
    if data['team'] in ['blue','red'] and rooms[code]['locks'][data['team']]: emit('error_msg', {'msg':'Bu takım kilitli.'}); return
    chips = int(data.get('chips', 1000))
    if old:
        old.update({'sid':request.sid,'team':data['team'],'role':data['role'],'avatar':data['avatar'],'chips':chips,'account':data.get('account'),'avatarData':data.get('avatarData', old.get('avatarData','')),'nameColor':data.get('nameColor', old.get('nameColor','default')),'avatarFrame':data.get('avatarFrame', old.get('avatarFrame','none'))})
        acc=data.get('account')
        if acc:
            users=load_users()
            if acc in users:
                old['avatarData']=users[acc].get('avatarData','')
                old['nameColor']=users[acc].get('nameColor','default')
                old['avatarFrame']=users[acc].get('avatarFrame','none')
    else:
        player_data={'sid':request.sid,'name':data['name'],'avatar':data['avatar'],'team':data['team'],'role':data['role'],'chips':chips,'isAdmin':rooms[code]['adminSid']==request.sid,'account':data.get('account'),'avatarData':data.get('avatarData',''),'nameColor':data.get('nameColor','default'),'avatarFrame':data.get('avatarFrame','none')}
        acc=data.get('account')
        if acc:
            users=load_users()
            if acc in users:
                player_data['avatarData']=users[acc].get('avatarData','')
                player_data['nameColor']=users[acc].get('nameColor','default')
                player_data['avatarFrame']=users[acc].get('avatarFrame','none')
        rooms[code]['players'].append(player_data)
    save_player_to_user(old if old else rooms[code]['players'][-1]); join_room(code); emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks'],'micStates':rooms[code].get('micStates', {})}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('start_game')
def start_game(data):
    code = data.get('room')
    if code not in rooms:
        return
    active_players = [p for p in rooms[code]['players'] if p.get('team') != 'spectator']
    if active_players and not all(rooms[code].get('ready', {}).get(p['sid']) for p in active_players):
        emit('error_msg', {'msg':'Herkes hazır değil.'})
        return
    rooms[code]['game']['started'] = True
    emit('game_update', pdata(code), to=code)

@socketio.on('new_game')
def new_game_event(data):
    code = data['room']
    if code in rooms:
        rooms[code]['game'] = new_game(rooms[code].get('category','default')); rooms[code]['stats']['gameNo'] = int(rooms[code]['stats'].get('gameNo',0)) + 1; rooms[code]['game']['roundNo'] = rooms[code]['stats']['gameNo']; rooms[code]['bets'] = {}; rooms[code]['ready'] = {}; emit('game_update', pdata(code), to=code)

@socketio.on('set_category')
def set_category(data):
    code = data['room']; cat = data.get('category','default')
    if code in rooms:
        rooms[code]['category'] = cat; rooms[code]['game'] = new_game(cat); rooms[code]['bets'] = {}; emit('game_update', pdata(code), to=code)

@socketio.on('join_team')
def join_team(data):
    code=data['room']; team=data['team']; role=data.get('role','player')
    if code not in rooms: return
    if team in ['blue','red'] and rooms[code]['locks'][team]: emit('error_msg', {'msg':'Bu takım kilitli.'}); return
    p=by_sid(code, request.sid)
    if not p: return
    p['team']=team; p['role']='spectator' if team=='spectator' else role
    emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks'],'micStates':rooms[code].get('micStates', {})}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('toggle_guess')
def toggle_guess(data):
    code=data['room']; idx=data['index']
    if code not in rooms: return
    p=by_sid(code, request.sid); g=rooms[code]['game']
    if not p: return
    if p['team']=='spectator' or p['role']=='spectator': emit('error_msg', {'msg':'Seyirci tahmin yapamaz.'}); return
    if not g['clueActive']: emit('error_msg', {'msg':'Spymaster ipucu vermeden tahmin yapılamaz.'}); return
    if p['team'] != g['turn']: emit('error_msg', {'msg':'Sıra senin takımında değil.'}); return
    card = g['cards'][idx]; names = card.get('guessedBy', [])
    if p['name'] in names: names.remove(p['name'])
    else: names.append(p['name'])
    card['guessedBy'] = names; card['guessed'] = bool(names); card['guessedTeam'] = p['team'] if names else ''
    emit('game_update', pdata(code), to=code)

@socketio.on('show_guesses')
def show_guesses(data):
    code=data['room']; idx=data['index']
    if code in rooms: emit('guess_names', {'names': rooms[code]['game']['cards'][idx].get('guessedBy', [])})

@socketio.on('reveal_card')
def reveal_card(data):
    code=data['room']; idx=data['index']
    if code not in rooms: return
    p=by_sid(code, request.sid); g=rooms[code]['game']
    if not p: return
    if p['team']=='spectator' or p['role']=='spectator': emit('error_msg', {'msg':'Seyirci kart açamaz.'}); return
    if not g['clueActive']: emit('error_msg', {'msg':'Spymaster ipucu vermeden kart açılamaz.'}); return
    if p['team'] != g['turn']: emit('error_msg', {'msg':'Sıra senin takımında değil.'}); return
    if g['winner']: return
    c=g['cards'][idx]
    if c['open']: return
    c['open']=True; c['guessed']=False; c['guessedBy']=[]; c['guessedTeam']=''
    cur=g['turn']; g['guessesMade'] += 1; team_name='Mavi Takım' if cur=='blue' else 'Kırmızı Takım'; g['moveLog'].append(f"{team_name} - {p['name']} açtı: {c['word']} ({c['role']})")
    def finish(wteam, text):
        g['winner']=text; update_winner(code,text); save_history(code,text); settle_bets(code,wteam)
        for cc in g['cards']: cc['open']=True
    if c['role']=='assassin': finish('red' if cur=='blue' else 'blue', '🏆 KIRMIZI TAKIM KAZANDI' if cur=='blue' else '🏆 MAVİ TAKIM KAZANDI')
    elif c['role']=='blue':
        g['blueCount']-=1
        if cur=='red': switch_turn(g)
        elif g['guessesMade']>=g['guessLimit']: switch_turn(g)
        if g['blueCount']==0: finish('blue','🏆 MAVİ TAKIM KAZANDI')
    elif c['role']=='red':
        g['redCount']-=1
        if cur=='blue': switch_turn(g)
        elif g['guessesMade']>=g['guessLimit']: switch_turn(g)
        if g['redCount']==0: finish('red','🏆 KIRMIZI TAKIM KAZANDI')
    else: switch_turn(g)
    emit('game_update', pdata(code), to=code)

@socketio.on('send_clue')
def send_clue(data):
    code=data['room']; name=data.get('name','')
    if code not in rooms: return
    g=rooms[code]['game']; p=by_name(code, name)
    if not can_clue(p,g): emit('error_msg', {'msg':"İpucunu sadece sıradaki takımın Spymaster'ı verebilir."}); return
    g['clue']='İpucu: '+data['clue']+' / '+data['number']; g['clueActive']=True; g['guessesMade']=0
    g['guessLimit'] = 99 if data['number']=='∞' else int(data['number'])+1
    tname='Mavi Takım' if g['turn']=='blue' else 'Kırmızı Takım'; g['clueLog'].append(f"{tname} - {p['name']}: {data['clue']} {data['number']}")
    g['phase']='🎯 Mavi takım ajanları tahmin yapıyor...' if g['turn']=='blue' else '🎯 Kırmızı takım ajanları tahmin yapıyor...'
    emit('game_update', pdata(code), to=code)

@socketio.on('end_turn')
def end_turn(data):
    code=data['room']
    if code not in rooms: return
    g=rooms[code]['game']; p=by_sid(code, request.sid)
    if not p: emit('error_msg', {'msg':'Oyuncu bulunamadı.'}); return
    if p['team']=='spectator' or p['role']=='spectator': emit('error_msg', {'msg':'Seyirci sırayı değiştiremez.'}); return
    if p['team'] != g['turn']: emit('error_msg', {'msg':'Sıra senin takımında değil.'}); return
    switch_turn(g); emit('game_update', pdata(code), to=code)



def _account_from_data_or_sid(data):
    account = (data.get('account') or '').strip()
    if account:
        return account
    code = data.get('room')
    if code in rooms:
        p = by_sid(code, request.sid)
        if p and p.get('account'):
            return p.get('account')
    return ''

@socketio.on('upload_avatar')
def upload_avatar(data):
    account = _account_from_data_or_sid(data)
    avatar_data = data.get('avatarData', '')
    code = data.get('room')

    if not account:
        emit('avatar_upload_result', {'ok': False, 'msg': 'Avatar yüklemek için önce giriş yapmalısın.'})
        return
    if not isinstance(avatar_data, str) or not avatar_data.startswith('data:image/'):
        emit('avatar_upload_result', {'ok': False, 'msg': 'Geçerli bir PNG/JPG/WebP resmi seç.'})
        return
    if len(avatar_data) > 2500000:
        emit('avatar_upload_result', {'ok': False, 'msg': 'Resim çok büyük. 1.8 MB altında bir avatar seç.'})
        return

    users = load_users()
    user_key = find_user_key(users, account)
    if not user_key:
        user_key = ensure_user_account(account)
        users = load_users()

    users[user_key]['avatarData'] = avatar_data
    users[user_key]['avatar'] = users[user_key].get('avatar', 'woman.png')
    save_users(users)

    if code in rooms:
        for p in rooms[code].get('players', []):
            if (p.get('account','').lower() == user_key.lower()) or p.get('sid') == request.sid:
                p['avatarData'] = avatar_data
                p['avatar'] = users[user_key].get('avatar', p.get('avatar', 'woman.png'))
                p['account'] = user_key
        emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks'], 'micStates': rooms[code].get('micStates', {}), 'ready': rooms[code].get('ready', {})}, to=code)
        emit('game_update', pdata(code), to=code)

    emit('avatar_upload_result', {'ok': True, 'profile': private_profile(user_key, users[user_key])})



@socketio.on('delete_avatar')
def delete_avatar(data):
    account = _account_from_data_or_sid(data) if "_account_from_data_or_sid" in globals() else data.get("account")
    users = load_users()
    user_key = find_user_key(users, account)
    if not user_key:
        emit('avatar_upload_result', {'ok': False, 'msg': 'Kullanıcı bulunamadı.'})
        return
    users[user_key]['avatarData'] = ''
    users[user_key]['avatar'] = 'woman.png'
    save_users(users)
    emit('avatar_upload_result', {'ok': True, 'profile': private_profile(user_key, users[user_key])})
@socketio.on('buy_vip_with_chips')
def buy_vip_with_chips(data):
    code = data.get('room', '')
    pack = data.get('pack', '')
    username = data.get('account', '')
    if pack not in VIP_PACKAGES:
        emit('error_msg', {'msg': 'VIP paketi bulunamadı.'})
        return

    pkg = VIP_PACKAGES[pack]
    player = by_sid(code, request.sid) if code in rooms else None
    users = load_users()
    key = find_user_key(users, username)

    if not key:
        emit('error_msg', {'msg': 'Önce giriş yapmalısın.'})
        return

    chips = int(users[key].get('chips', 1000))
    if player:
        chips = int(player.get('chips', chips))

    if chips < pkg['price']:
        emit('error_msg', {'msg': 'Yeterli jeton yok.'})
        return

    chips -= pkg['price']
    until = int(time.time()) + int(pkg['days']) * 86400

    users[key]['chips'] = chips
    users[key]['vip'] = True
    users[key]['vipLevel'] = pkg['label']
    users[key]['vipUntil'] = until

    if pack == 'vip-bronze':
        users[key]['avatarFrame'] = users[key].get('avatarFrame', 'frame-gold') or 'frame-gold'
        users[key]['nameColor'] = users[key].get('nameColor', 'name-green') or 'name-green'
    elif pack == 'vip-gold':
        users[key]['avatarFrame'] = 'frame-vip'
        users[key]['nameColor'] = 'name-green'
    elif pack == 'vip-diamond':
        users[key]['avatarFrame'] = 'frame-legendary'
        users[key]['nameColor'] = 'name-rainbow'

    save_users(users)

    if player:
        player['chips'] = chips
        player['vip'] = True
        player['vipLevel'] = pkg['label']
        player['vipUntil'] = until
        player['avatarFrame'] = users[key].get('avatarFrame', player.get('avatarFrame','none'))
        player['nameColor'] = users[key].get('nameColor', player.get('nameColor','default'))

    emit('profile_updated', private_profile(key, users[key]))
    if code in rooms:
        emit('game_update', pdata(code), to=code)
    emit('error_msg', {'msg': pkg['label'] + ' aktif edildi.'})

@socketio.on('buy_cosmetic')
def buy_cosmetic(data):
    account = _account_from_data_or_sid(data)
    item = data.get('item')
    code = data.get('room')
    if item not in COSMETIC_PRICES:
        emit('cosmetic_result', {'ok': False, 'msg': 'Ürün bulunamadı.'})
        return
    users = load_users()
    if not account or account not in users:
        emit('cosmetic_result', {'ok': False, 'msg': 'Satın almak için önce giriş yapmalısın.'})
        return
    inv = users[account].setdefault('inventory', [])
    if item in inv:
        emit('cosmetic_result', {'ok': True, 'msg': 'Bu ürün zaten sende.', 'profile': private_profile(account, users[account])})
        return
    price = COSMETIC_PRICES[item]
    if int(users[account].get('chips', 1000)) < price:
        emit('cosmetic_result', {'ok': False, 'msg': 'Yeterli jeton yok.'})
        return
    users[account]['chips'] = int(users[account].get('chips', 1000)) - price
    inv.append(item)
    save_users(users)
    if code in rooms:
        for p in rooms[code].get('players', []):
            if p.get('account') == account or p.get('sid') == request.sid:
                p['chips'] = users[account]['chips']
        emit('game_update', pdata(code), to=code)
    emit('cosmetic_result', {'ok': True, 'msg': 'Satın alındı.', 'profile': private_profile(account, users[account])})

@socketio.on('equip_cosmetic')
def equip_cosmetic(data):
    account = _account_from_data_or_sid(data)
    item = data.get('item')
    code = data.get('room')
    users = load_users()
    if not account or account not in users:
        emit('cosmetic_result', {'ok': False, 'msg': 'Kullanmak için önce giriş yapmalısın.'})
        return
    if item not in users[account].get('inventory', []) and item not in ['frame-none', 'name-default']:
        emit('cosmetic_result', {'ok': False, 'msg': 'Bu ürün envanterinde yok.'})
        return
    if item.startswith('frame-'):
        users[account]['avatarFrame'] = item
    elif item.startswith('name-'):
        users[account]['nameColor'] = item
    else:
        emit('cosmetic_result', {'ok': False, 'msg': 'Ürün tipi bilinmiyor.'})
        return
    save_users(users)
    if code in rooms:
        for p in rooms[code].get('players', []):
            if p.get('account') == account or p.get('sid') == request.sid:
                p['avatarFrame'] = users[account].get('avatarFrame', 'none')
                p['nameColor'] = users[account].get('nameColor', 'default')
                p['chips'] = users[account].get('chips', p.get('chips', 1000))
        emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks'], 'micStates': rooms[code].get('micStates', {}), 'ready': rooms[code].get('ready', {})}, to=code)
        emit('game_update', pdata(code), to=code)
    emit('cosmetic_result', {'ok': True, 'msg': 'Kozmetik aktif edildi.', 'profile': private_profile(account, users[account])})

@socketio.on('buy_virtual_chips')
def buy_virtual_chips(data):
    code = data.get('room', '')
    amount = int(data.get('amount', 0))
    if amount <= 0:
        return

    player = by_sid(code, request.sid) if code in rooms else None

    if player:
        player['chips'] = int(player.get('chips', 1000)) + amount
        save_player_to_user(player)
        if player.get('account'):
            users = load_users()
            key = find_user_key(users, player.get('account'))
            if key:
                emit('profile_updated', private_profile(key, users[key]))
    else:
        emit('error_msg', {'msg': 'Önce odaya gir veya masaya otur.'})
        return

    if code in rooms:
        emit('game_update', pdata(code), to=code)


@socketio.on('place_bet')
def place_bet(data):
    code=data['room']; team=data['team']; amount=int(data.get('amount',0))
    if code not in rooms or team not in ['blue','red']: return
    p=by_sid(code, request.sid)
    if not p: return
    if amount<=0: emit('error_msg', {'msg':'Geçerli jeton miktarı yaz.'}); return
    if int(p.get('chips',1000))<amount: emit('error_msg', {'msg':'Yeterli jeton yok.'}); return
    old=rooms[code]['bets'].get(request.sid)
    if old: p['chips'] += old['amount']
    p['chips'] -= amount; rooms[code]['bets'][request.sid]={'name':p['name'],'team':team,'amount':amount}; save_player_to_user(p)
    emit('game_update', pdata(code), to=code)

@socketio.on('admin_new_game')
def admin_new_game(data): new_game_event(data)

@socketio.on('admin_reveal_all')
def admin_reveal_all(data):
    code=data['room']
    if code not in rooms or not is_admin(code): return
    for c in rooms[code]['game']['cards']: c['open']=True
    emit('game_update', pdata(code), to=code)

@socketio.on('admin_reset_stats')
def admin_reset_stats(data):
    code=data['room']
    if code not in rooms or not is_admin(code): return
    rooms[code]['stats']={'blueWins':0,'redWins':0,'history':[],'wordHistory':[],'betHistory':[],'gameNo':0}; rooms[code]['bets']={}
    emit('game_update', pdata(code), to=code)

@socketio.on('toggle_lock')
def toggle_lock(data):
    code=data['room']; team=data['team']
    if code not in rooms or not is_admin(code): return
    rooms[code]['locks'][team]=not rooms[code]['locks'][team]; emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks'],'micStates':rooms[code].get('micStates', {})}, to=code)

@socketio.on('admin_move_player')
def admin_move_player(data):
    code=data['room']
    if code not in rooms or not is_admin(code): return
    p=by_sid(code, data['sid'])
    if p:
        p['team']=data['team']; p['role']='spectator' if data['team']=='spectator' else data['role']
        if data['team']=='spectator': emit('made_spectator', to=data['sid'])
    emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks'],'micStates':rooms[code].get('micStates', {})}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('make_admin')
def make_admin(data):
    code=data['room']
    if code not in rooms or not is_admin(code): return
    p=by_sid(code, data['sid'])
    if p: p['isAdmin']=True
    emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks'],'micStates':rooms[code].get('micStates', {})}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('kick_player')
def kick_player(data):
    code=data['room']; sid=data['sid']
    if code not in rooms or not is_admin(code): return
    rooms[code]['players']=[p for p in rooms[code]['players'] if p['sid']!=sid]
    if sid in rooms[code]['bets']: del rooms[code]['bets'][sid]
    emit('kicked', to=sid); emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks'],'micStates':rooms[code].get('micStates', {})}, to=code); emit('game_update', pdata(code), to=code)



@socketio.on('leave_table')
def leave_table(data):
    code = data.get('room')
    if code not in rooms:
        return
    p = by_sid(code, request.sid)
    if not p:
        return
    p['team'] = 'spectator'
    p['role'] = 'spectator'
    rooms[code].setdefault('ready', {})
    rooms[code]['ready'].pop(request.sid, None)
    emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks'], 'micStates': rooms[code].get('micStates', {}), 'ready': rooms[code].get('ready', {})}, to=code)
    emit('game_update', pdata(code), to=code)

@socketio.on('toggle_ready')
def toggle_ready(data):
    code = data.get('room')
    if code not in rooms:
        return
    p = by_sid(code, request.sid)
    if not p:
        return
    rooms[code].setdefault('ready', {})
    rooms[code]['ready'][request.sid] = not rooms[code]['ready'].get(request.sid, False)
    emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks'], 'micStates': rooms[code].get('micStates', {}), 'ready': rooms[code].get('ready', {})}, to=code)
    emit('game_update', pdata(code), to=code)


@socketio.on('team_chat')
def team_chat(data):
    code = data.get('room')
    team = data.get('team')
    if code not in rooms or team not in ['blue','red']:
        return
    p = by_sid(code, request.sid)
    if not p or p.get('team') != team:
        emit('error_msg', {'msg':'Takım sohbetini sadece kendi takımın görebilir.'})
        return
    for player in rooms[code]['players']:
        if player.get('team') == team:
            emit('team_chat_update', {'name': data.get('name','Oyuncu'), 'msg': data.get('msg','')}, to=player.get('sid'))


@socketio.on('dm_chat')
def dm_chat(data):
    target = data.get('to')
    msg = data.get('msg','')
    sender_name = data.get('name','Oyuncu')
    if not target or not msg:
        return
    emit('dm_chat_update', {'name': sender_name + ' → toi', 'msg': msg}, to=target)
    emit('dm_chat_update', {'name': 'Toi → DM', 'msg': msg})

@socketio.on('chat')
def chat(data):
    code=data['room']
    if code in rooms: emit('chat_update', {'name':data['name'],'msg':data['msg']}, to=code)

@socketio.on('voice_join')
def voice_join(data):
    code = data.get('room')
    if not code or code not in rooms:
        return

    join_room(code)

    rooms[code].setdefault('micStates', {})
    rooms[code]['micStates'][request.sid] = {'mic': True, 'speaking': False}

    existing = [p.get('sid') for p in rooms[code]['players'] if p.get('sid') != request.sid]

    emit('voice_existing_users', {'users': existing})
    emit('voice_user_joined', {'sid': request.sid}, to=code, include_self=False)
    emit('mic_state_update', {'micStates': rooms[code]['micStates']}, to=code)


@socketio.on('voice_leave')
def voice_leave(data):
    code = data.get('room')
    if not code or code not in rooms:
        return

    rooms[code].setdefault('micStates', {})
    rooms[code]['micStates'][request.sid] = {'mic': False, 'speaking': False}

    emit('voice_user_left', {'sid': request.sid}, to=code, include_self=False)
    emit('mic_state_update', {'micStates': rooms[code]['micStates']}, to=code)


@socketio.on('voice_mic_state')
def voice_mic_state(data):
    code = data.get('room')
    if not code or code not in rooms:
        return

    rooms[code].setdefault('micStates', {})
    rooms[code]['micStates'][request.sid] = {
        'mic': bool(data.get('mic')),
        'speaking': bool(data.get('speaking'))
    }

    emit('mic_state_update', {'micStates': rooms[code]['micStates']}, to=code)


@socketio.on('voice_speaking')
def voice_speaking(data):
    code = data.get('room')
    if not code or code not in rooms:
        return

    rooms[code].setdefault('micStates', {})
    state = rooms[code]['micStates'].get(request.sid, {'mic': True, 'speaking': False})
    state['mic'] = True
    state['speaking'] = bool(data.get('speaking'))
    rooms[code]['micStates'][request.sid] = state

    emit('mic_state_update', {'micStates': rooms[code]['micStates']}, to=code)


@socketio.on('voice_signal')
def voice_signal(data):
    target = data.get('to')
    if not target:
        return

    emit('voice_signal', {
        'from': request.sid,
        'data': data.get('data')
    }, to=target)




# =========================
# Londres VIP EXTRA FEATURES
# =========================


FEATURES_HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏛️ Londres VIP MENU</title>
<style>
body{margin:0;min-height:100vh;background:radial-gradient(circle at top,#30220a,#050505 55%,#000);color:#f6d777;font-family:Arial,Helvetica,sans-serif;text-align:center}
.wrap{max-width:1050px;margin:auto;padding:35px 18px}
h1{font-family:Georgia,serif;font-size:46px;text-shadow:0 0 18px #d4af37;margin-bottom:8px}
.sub{color:#f4dfb0;margin-bottom:25px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px;margin-top:20px}
.card{border:1px solid #d4af37;border-radius:24px;background:rgba(0,0,0,.72);padding:22px;box-shadow:0 0 22px rgba(212,175,55,.25);min-height:145px}
.card h2{font-size:22px;margin:5px 0 12px}
.card p{color:#f4dfb0;line-height:1.45;font-size:14px;min-height:38px}
.btn{display:inline-block;margin-top:10px;padding:12px 18px;border:1px solid #d4af37;border-radius:14px;color:#000;background:linear-gradient(135deg,#d4af37,#fff0a8,#9b7419);text-decoration:none;font-weight:900}
.back{margin-bottom:20px;display:inline-block;color:#d4af37;text-decoration:none}
</style>
</head>
<body>
<div class="wrap">
<a class="back" href="/">← Ana sayfa</a>
<h1>☰ Londres VIP MENU</h1>
<div class="sub">Tüm ek sistemler tek yerde.</div>
<div class="grid">
<div class="card"><h2>🎟️ Turnuvalar</h2><p>Turnuvalar ve ödüller.</p><a class="btn" href="/turnuvalar">Aç</a></div>
<div class="card"><h2>🎨 Profil Özelleştirme</h2><p>Çerçeve, renk ve profil stilleri.</p><a class="btn" href="/profil-magazasi">Aç</a></div>
<div class="card"><h2>🎁 Sandık Sistemi</h2><p>Sandıklar ve ödüller.</p><a class="btn" href="/sandiklar">Aç</a></div>
<div class="card"><h2>🏆 Başarımlar</h2><p>Profil başarımları.</p><a class="btn" href="/basarimlar">Aç</a></div>
<div class="card"><h2>👥 Arkadaş Sistemi</h2><p>Arkadaşlar ve özel mesajlar.</p><a class="btn" href="/arkadaslar">Aç</a></div>
<div class="card"><h2>🤖 AI Tarot Premium</h2><p>Premium kişisel tarot yorumu.</p><a class="btn" href="/ai-tarot-premium">Aç</a></div>
<div class="card"><h2>📜 Oyun Kuralları</h2><p>Codenames, Poker, Tavla, Okey, 101, Monopoly, Ludo ve Bowling kuralları.</p><a class="btn" href="/oyun-kurallari">Aç</a></div>
<div class="card"><h2 data-i18n='settings'>⚙️ Ayarlar</h2><p>Dil, tema, bildirimler ve gizlilik.</p><a class="btn" href="/ayarlar">Aç</a></div>
</div>
</div>
</body></html>
"""


KASA_HTML = r"""
<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>🪙 Londres Kasası</title>
<style>body{margin:0;min-height:100vh;background:radial-gradient(circle at top,#2b1d05,#000);color:#f6d777;font-family:Arial;text-align:center}.wrap{max-width:1000px;margin:auto;padding:35px 18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:18px}.pack{border:1px solid #d4af37;border-radius:22px;background:rgba(0,0,0,.75);padding:22px;box-shadow:0 0 22px rgba(212,175,55,.3)}.price{font-size:26px;color:#fff0a8}.btn{padding:12px 18px;border-radius:14px;border:1px solid #d4af37;background:#d4af37;color:#000;font-weight:900;cursor:pointer}.back{color:#d4af37}</style></head><body><div class="wrap"><a class="back" href="/">← Ana sayfa</a><h1>🪙 <span data-i18n="cashier">Londres KASASI</span></h1><div class="grid">
<div class="pack"><h2>Başlangıç</h2><div class="price">🪙 200</div><p>4,99 €</p><button class="btn">Satın Al</button></div>
<div class="pack"><h2>Gümüş</h2><div class="price">🪙 500</div><p>9,99 €</p><button data-base-label='Satın Al' class="btn">Satın Al</button></div>
<div class="pack"><h2>Altın</h2><div class="price">🪙 1.200</div><p>19,99 €</p><button data-base-label='Satın Al' class="btn">Satın Al</button></div>
<div class="pack"><h2>VIP</h2><div class="price">🪙 3€</div><p>39,99 €</p><button data-base-label='Satın Al' class="btn">Satın Al</button></div>
<div class="pack"><h2>Elmas</h2><div class="price">🪙 8€</div><p>89,99 €</p><button data-base-label='Satın Al' class="btn">Satın Al</button></div>
</div><p style="color:#f4dfb0">Stripe/PayPal bağlandığında butonlar gerçek ödeme alacak.</p></div></body></html>
"""



def montenoir_page(title, content):
    return f"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
body{{margin:0;min-height:100vh;background:radial-gradient(circle at top,#30220a,#000);color:#f6d777;font-family:Arial,Helvetica,sans-serif;text-align:center}}
.wrap{{max-width:1000px;margin:auto;padding:35px 18px}}
h1{{font-family:Georgia,serif;text-shadow:0 0 18px #d4af37}}
.box{{border:1px solid #d4af37;border-radius:24px;background:rgba(0,0,0,.75);padding:24px;margin:18px auto;box-shadow:0 0 22px rgba(212,175,55,.3)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.item{{border:1px solid rgba(212,175,55,.6);border-radius:18px;padding:18px;background:rgba(255,255,255,.04);min-height:80px}}
a{{color:#d4af37;text-decoration:none}}
.btn{{display:inline-block;margin:8px;padding:10px 14px;border:1px solid #d4af37;border-radius:12px;background:#111;color:#f6d777;font-weight:bold;cursor:pointer}}
select{{padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37}}
</style>
</head>
<body><div class="wrap"><a href="/">← Ana sayfa</a><h1>{title}</h1><div class="box">{content}</div></div></body></html>
"""

@app.route("/features")
@app.route("/menu")
def menu_center():
    return render_template_string(FEATURES_HTML + Londres_I18N_SCRIPT)

@app.route("/turnuvalar_old_disabled_236840")
def tournaments_page():
    content = r"""<div class='grid'><div class='item'><h2>👑 <span data-i18n="activeText">Haftalık Codenames Turnuvası</span></h2><p>Giriş: 100 jeton</p><p>Ödül: 5€ jeton</p><button data-base-label='Satın Al' class='btn' onclick="joinTournament('weekly-codenames')">Katıl</button></div><div class='item'><h2>♠️ Poker Turnuvası</h2><p>Yakında</p></div></div><div id='result'></div><script>function user(){return localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||''}function joinTournament(tournament){fetch('/api/join_tournament',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),tournament})}).then(r=>r.json()).then(d=>{result.innerText=d.msg;});}</script>"""
    return montenoir_page("🎟️ Turnuvalar", content)

@app.route("/profil-magazasi_old_disabled_237693")
def profile_shop_page():
    content = r"""<div class='grid'><div class='item'>🟡 Altın Çerçeve<br>1000 jeton<br><button class='btn' onclick="buyCosmetic('gold-frame')">Satın Al</button></div><div class='item'>💎 Elmas Çerçeve<br>5000 jeton<br><button data-base-label='Satın Al' class='btn' onclick="buyCosmetic('diamond-frame')">Satın Al</button></div><div class='item'>🏛️ Barok Çerçeve<br>7500 jeton<br><button data-base-label='Satın Al' class='btn' onclick="buyCosmetic('baroque-frame')">Satın Al</button></div><div class='item'>🌈 İsim Rengi<br>3000 jeton<br><button data-base-label='Satın Al' class='btn' onclick="buyCosmetic('rainbow-name')">Satın Al</button></div><div class='item'>✨ Animasyonlu Profil<br>10000 jeton<br><button data-base-label='Satın Al' class='btn' onclick="buyCosmetic('animated-profile')">Satın Al</button></div></div><div id='result'></div><script>function user(){return localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||''}function buyCosmetic(item){fetch('/api/buy_cosmetic',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),item})}).then(r=>r.json()).then(d=>{result.innerText=d.msg||JSON.stringify(d);});}</script>"""
    return montenoir_page("🎨 Profil Özelleştirme", content)

@app.route("/sandiklar_old_disabled_239000")
def chests_page():
    content = r"""<div class='grid'><div class='item'>🥉 Bronz Sandık<br>100 jeton<br><button data-base-label='Aç' class='btn' onclick="openChest('bronze')">Aç</button></div><div class='item'>🥈 Gümüş Sandık<br>300 jeton<br><button data-base-label='Aç' class='btn' onclick="openChest('silver')">Aç</button></div><div class='item'>🥇 Altın Sandık<br>800 jeton<br><button data-base-label='Aç' class='btn' onclick="openChest('gold')">Aç</button></div><div class='item'>💎 Elmas Sandık<br>2000 jeton<br><button data-base-label='Aç' class='btn' onclick="openChest('diamond')">Aç</button></div></div><div id='result'></div><script>function user(){return localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||''}function openChest(chest){fetch('/api/open_chest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),chest})}).then(r=>r.json()).then(d=>{result.innerText=d.msg||JSON.stringify(d);});}</script>"""
    return montenoir_page("🎁 Sandık Sistemi", content)

@app.route("/basarimlar")
def achievements_page():
    content = r"""<div id='achievements'>Yükleniyor...</div><script>function user(){return localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||''}fetch('/api/monte_profile?u='+encodeURIComponent(user())).then(r=>r.json()).then(d=>{if(!d.ok){achievements.innerText=d.msg;return}let a=d.profile.achievements||[];achievements.innerHTML=a.length?a.map(x=>'<div class="item">'+x+'</div>').join(''):'Henüz başarım yok.';});</script>"""
    return montenoir_page("🏆 Başarımlar", content)

@app.route("/arkadaslar_old_disabled_240619")
def friends_page():
    content = r"""<input id='target' placeholder='Arkadaş kullanıcı adı' style='padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37'><button data-base-label='Arkadaş Ekle' class='btn' onclick='addFriend()'>Arkadaş Ekle</button><br><input id='msgTarget' placeholder='Mesaj gönderilecek kullanıcı' style='padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37'><input id='msgText' placeholder='Mesaj' style='padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37'><button data-base-label='Özel Mesaj Gönder' class='btn' onclick='sendMsg()'>Özel Mesaj Gönder</button><div id='friendsBox'></div><div id='result'></div><script>function user(){return localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||''}function load(){fetch('/api/monte_profile?u='+encodeURIComponent(user())).then(r=>r.json()).then(d=>{if(!d.ok){friendsBox.innerText=d.msg;return}friendsBox.innerHTML='<h3>Arkadaşlar</h3>'+((d.profile.friends||[]).join('<br>')||'Yok')+'<h3>İstekler</h3>'+((d.profile.friendRequests||[]).map(x=>x+' <button data-base-label='Kabul Et' onclick="acceptFriend(\''+x+'\')">Kabul Et</button>').join('<br>')||'Yok');});}function addFriend(){fetch('/api/friend_request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),target:target.value})}).then(r=>r.json()).then(d=>{result.innerText=d.msg;load();});}function acceptFriend(rq){fetch('/api/accept_friend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),requester:rq})}).then(r=>r.json()).then(d=>{result.innerText=d.msg;load();});}function sendMsg(){fetch('/api/send_private_message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),target:msgTarget.value,msg:msgText.value})}).then(r=>r.json()).then(d=>{result.innerText=d.msg;});}load();</script>"""
    return montenoir_page("👥 Arkadaş Sistemi", content)

@app.route("/ai-tarot-premium_old_disabled_242731")
def ai_tarot_premium_page():
    content = r"""<p>Premium yorum: 1500 jeton</p><input id='birthDate' placeholder='Doğum tarihi' style='padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37'><br><textarea id='question' placeholder='Sorunu yaz' style='width:90%;height:90px;padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37'></textarea><br><input id='photoNote' placeholder='Fotoğraf / enerji notu' style='padding:12px;border-radius:12px;background:#060606;color:#f6d777;border:1px solid #d4af37'><br><button data-base-label='Premium Yorumu Al' class='btn' onclick='premiumTarot()'>Premium Yorumu Al</button><pre id='result' style='white-space:pre-wrap;text-align:left;color:#fff0a8'></pre><script>function user(){return localStorage.getItem('codenamesAccount')||localStorage.getItem('loggedUser')||''}function premiumTarot(){fetch('/api/premium_tarot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user(),birthDate:birthDate.value,question:question.value,photoNote:photoNote.value})}).then(r=>r.json()).then(d=>{result.innerText=d.msg;});}</script>"""
    return montenoir_page("🤖 AI Tarot Premium", content)

@app.route("/ayarlar")
def settings_page():
    content = """
    <h2 data-i18n='settings'>⚙️ Ayarlar</h2>
    <div class='grid'>
      <div class='item'><h3><span data-i18n="language">🌍 Dil</span></h3><p>Seçim tarayıcıda kaydedilir.</p>
        <select id="montenoirLangSelect" onchange="setMontenoirLang(this.value);alert('Dil değiştirildi.')">
          <option value='fr'>🇫🇷 Français</option>
          <option value='tr'>🇹🇷 Türkçe</option>
          <option value='en'>🇬🇧 English</option>
          <option value='es'>🇪🇸 Español</option>
          <option value='de'>🇩🇪 Deutsch</option>
          <option value='it'>🇮🇹 Italiano</option>
          <option value='pt'>🇵🇹 Português</option>
          <option value='nl'>🇳🇱 Nederlands</option>
          <option value='ro'>🇷🇴 Română</option>
          <option value='ar'>🇸🇦 العربية</option>
          <option value='ru'>🇷🇺 Русский</option>
        </select>
      </div>
      <div class='item'><h3 data-i18n='rules'><span data-i18n="rulesTitle">📜 Kurallar</span></h3><p><span data-i18n="rulesText">Saygılı oyun, hile yasak, uygunsuz davranış yasak.</span></p></div>
      <div class='item'><h3><span data-i18n="theme">🎨 Tema</span></h3><p><span data-i18n="themeText">Siyah & altın Londres teması aktif.</span></p></div>
      <div class='item'><h3><span data-i18n="notifications">🔔 Bildirimler</span></h3><p>Turnuva, sandık ve özel mesaj bildirimleri yakında.</p></div>
      <div class='item'><h3><span data-i18n="privacy">🔐 Gizlilik</span></h3><p><span data-i18n="privacyText">Email diğer oyunculara gösterilmez.</span></p></div>
      <div class='item'><h3><span data-i18n="help">❓ Yardım</span></h3><p><span data-i18n="helpText">Oyun kuralları ve destek bölümü yakında.</span></p></div>
    </div>
    """
    return montenoir_page("⚙️ Ayarlar", content)




r"""
<script>
(function(){
const D={
tr:["🎮 <span data-i18n="games">OYUNLAR</span>","🔮 <span data-i18n="tarot">TAROT & RİTÜEL</span>","<span data-i18n="login">👤 ÜYELİK / GİRİŞ</span>","🏆 <span data-i18n="profile">PROFİL / XP</span>","🪙 <span data-i18n="cashier">Londres KASASI</span>","☰ MENU","⚙️ <span data-i18n="settings">AYARLAR</span>","🎟️ Turnuvalar","🎨 Profil Özelleştirme","🎁 Sandık Sistemi","🏆 Başarımlar","👥 Arkadaş Sistemi","🤖 AI Tarot Premium","📜 Oyun Kuralları","Satın Al","Aç","← Ana sayfa"],
fr:["🎮 JEUX","🔮 TAROT & RITUEL","👤 ABONNEMENT / CONNEXION","🏆 PROFIL / XP","🪙 CAISSE Londres","☰ MENU","⚙️ PARAMÈTRES","🎟️ Tournois","🎨 Personnalisation profil","🎁 Coffres","🏆 Succès","👥 Amis","🤖 Tarot IA Premium","📜 Règles des jeux","Acheter","Ouvrir","🚪 LOCA"],
en:["🎮 GAMES","🔮 TAROT & RITUAL","👤 MEMBERSHIP / LOGIN","🏆 PROFILE / XP","🪙 Londres CASHIER","☰ MENU","⚙️ SETTINGS","🎟️ Tournaments","🎨 Profile customization","🎁 Chests","🏆 Achievements","👥 Friends","🤖 Premium AI Tarot","📜 Game rules","Buy","Open","← Home"],
es:["🎮 JUEGOS","🔮 TAROT Y RITUAL","👤 MEMBRESÍA / ENTRAR","🏆 PERFIL / XP","🪙 CAJA Londres","☰ MENU","⚙️ AJUSTES","🎟️ Torneos","🎨 Personalización perfil","🎁 Cofres","🏆 Logros","👥 Amigos","🤖 Tarot IA Premium","📜 Reglas de juego","Comprar","Abrir","← Inicio"],
de:["🎮 SPIELE","🔮 TAROT & RITUAL","👤 MITGLIEDSCHAFT / LOGIN","🏆 PROFIL / XP","🪙 Londres KASSE","☰ MENU","⚙️ EINSTELLUNGEN","🎟️ Turniere","🎨 Profil anpassen","🎁 Truhen","🏆 Erfolge","👥 Freunde","🤖 Premium KI-Tarot","📜 Spielregeln","Kaufen","Öffnen","← Startseite"],
it:["🎮 GIOCHI","🔮 TAROCCHI & RITUALE","👤 ABBONAMENTO / LOGIN","🏆 PROFILO / XP","🪙 CASSA Londres","☰ MENU","⚙️ IMPOSTAZIONI","🎟️ Tornei","🎨 Personalizza profilo","🎁 Forzieri","🏆 Obiettivi","👥 Amici","🤖 Tarocchi IA Premium","📜 Regole dei giochi","Acquista","Apri","← Home"],
pt:["🎮 JOGOS","🔮 TAROT & RITUAL","👤 ADESÃO / LOGIN","🏆 PERFIL / XP","🪙 CAIXA Londres","☰ MENU","⚙️ DEFINIÇÕES","🎟️ Torneios","🎨 Personalizar perfil","🎁 Baús","🏆 Conquistas","👥 Amigos","🤖 Tarot IA Premium","📜 Regras dos jogos","Comprar","Abrir","← Início"],
nl:["🎮 SPELLEN","🔮 TAROT & RITUEEL","👤 LIDMAATSCHAP / LOGIN","🏆 PROFIEL / XP","🪙 Londres KASSA","☰ MENU","⚙️ INSTELLINGEN","🎟️ Toernooien","🎨 Profiel aanpassen","🎁 Kisten","🏆 Prestaties","👥 Vrienden","🤖 Premium AI Tarot","📜 Spelregels","Kopen","Openen","← Home"],
ro:["🎮 JOCURI","🔮 TAROT & RITUAL","👤 ABONAMENT / LOGIN","🏆 PROFIL / XP","🪙 CASIERIA Londres","☰ MENU","⚙️ SETĂRI","🎟️ Turnee","🎨 Personalizare profil","🎁 Cufere","🏆 Realizări","👥 Prieteni","🤖 Tarot AI Premium","📜 Regulile jocurilor","Cumpără","Deschide","← Acasă"],
ar:["🎮 الألعاب","🔮 التاروت والطقوس","👤 العضوية / الدخول","🏆 الملف / XP","🪙 خزينة مونتينوار","☰ القائمة","⚙️ الإعدادات","🎟️ البطولات","🎨 تخصيص الملف","🎁 الصناديق","🏆 الإنجازات","👥 الأصدقاء","🤖 تاروت AI بريميوم","📜 قواعد الألعاب","شراء","فتح","← الرئيسية"],
ru:["🎮 ИГРЫ","🔮 ТАРО И РИТУАЛ","👤 ПОДПИСКА / ВХОД","🏆 ПРОФИЛЬ / XP","🪙 КАССА Londres","☰ МЕНЮ","⚙️ НАСТРОЙКИ","🎟️ Турниры","🎨 Настройка профиля","🎁 Сундуки","🏆 Достижения","👥 Друзья","🤖 Премиум AI Таро","📜 Правила игр","Купить","Открыть","← Главная"]
};
const base=D.tr;
function getLang(){return localStorage.getItem("montenoirLang")||"tr";}
function applyLang(){
 const l=getLang(), arr=D[l]||D.tr;
 document.documentElement.lang=l;
 document.documentElement.dir=(l==="ar")?"rtl":"ltr";
 document.querySelectorAll("button,a,h1,h2,h3,p,div,span").forEach(el=>{
   if(el.children.length>0 && !el.classList.contains("royalBtn") && !el.classList.contains("btn") && !el.classList.contains("gameItem")) return;
   let t=(el.textContent||"").trim();
   for(let i=0;i<base.length;i++){
     if(t===base[i] || Object.values(D).some(v=>v[i]===t)){
       el.textContent=arr[i]; break;
     }
   }
 });
 const s=document.getElementById("montenoirLangSelect");
 if(s) s.value=l;
}
window.setMontenoirLang=function(v){localStorage.setItem("montenoirLang",v);applyLang();};
document.addEventListener("DOMContentLoaded",applyLang);
setTimeout(applyLang,200);
setTimeout(applyLang,700);
})();
</script>
"""



@app.route("/oyun-kurallari_old_disabled_249844")
def game_rules_page():
    content = """
    <div class='grid'>
      <div class='item'>
        <h2>👑 Codenames VIP</h2>
        <p>İki takım yarışır. Spymaster tek kelimelik ipucu verir. Saha ajanları doğru kelimeleri bulmaya çalışır. Suikastçı karta basan takım kaybeder.</p>
      </div>
      <div class='item'>
        <h2>♠️ Poker</h2>
        <p>Texas Hold'em mantığıyla oynanır. Her oyuncuya 2 kapalı kart, masaya 5 ortak kart gelir. En güçlü 5'li eli yapan kazanır.</p>
      </div>
      <div class='item'>
        <h2>🎲 Tavla</h2>
        <p>Oyuncular pullarını zarla ilerletir. Amaç tüm pulları kendi bölgesine toplamak ve rakipten önce dışarı almaktır.</p>
      </div>
      <div class='item'>
        <h2>🀄 Okey</h2>
        <p>Oyuncular taşlarla seri veya per oluşturur. Elini tamamlayan oyuncu taşı ortaya atarak oyunu bitirir.</p>
      </div>
      <div class='item'>
        <h2>💎 101</h2>
        <p>Oyuncular en az 101 toplam değerle açılır. Amaç eldeki taşları bitirmek ve en az ceza puanıyla oyunu tamamlamaktır.</p>
      </div>
      <div class='item'>
        <h2>🏙️ Monopoly</h2>
        <p>Oyuncular zar atarak ilerler, mülk satın alır, kira toplar. Amaç diğer oyuncuları iflasa sürüklemektir.</p>
      </div>
      <div class='item'>
        <h2>🔴 Ludo</h2>
        <p>Her oyuncu taşlarını zarla başlangıçtan hedef alanına taşır. Tüm taşlarını önce bitiren kazanır.</p>
      </div>
      <div class='item'>
        <h2>🎳 Bowling</h2>
        <p>Oyuncular lobutları devirmeye çalışır. Strike ve spare bonuslarıyla en yüksek puanı alan kazanır.</p>
      </div>
    </div>
    """
    return montenoir_page("📜 Oyun Kuralları", content)




# =========================
# Londres SAFE SYSTEMS ROUTES V1
# =========================
@app.route("/api/monte_profile")
def api_monte_profile():
    users, key = monte_find_or_create_user(request.args.get("u", ""))
    if not key:
        return {"ok": False, "msg": "Giriş gerekli."}
    monte_unlock_achievements(users, key)
    save_users(users)
    return {"ok": True, "profile": monte_public_payload(key, users[key])}

@app.route("/api/open_chest", methods=["POST"])
def api_open_chest():
    data = request.get_json(force=True, silent=True) or {}
    users, key = monte_find_or_create_user(data.get("u", ""))
    if not key:
        return {"ok": False, "msg": "Giriş gerekli."}
    chest = data.get("chest", "bronze")
    prices = {"bronze": 100, "silver": 300, "gold": 800, "diamond": 2000}
    rewards = {"bronze": [("chips", 50), ("chips", 100), ("badge", "🥉 Bronz Şans")],
               "silver": [("chips", 150), ("chips", 300), ("color", "silver")],
               "gold": [("chips", 500), ("frame", "gold"), ("badge", "🥇 Altın Şans")],
               "diamond": [("chips", 1500), ("frame", "diamond"), ("badge", "💎 Elmas Şans"), ("color", "rainbow")]}
    price = prices.get(chest, 100)
    if not is_owner_name(key) and int(users[key].get("chips", 0)) < price:
        return {"ok": False, "msg": "Yeterli jeton yok."}
    if not is_owner_name(key):
        users[key]["chips"] = int(users[key].get("chips", 0)) - price
    kind, value = random.choice(rewards.get(chest, rewards["bronze"]))
    if kind == "chips":
        users[key]["chips"] = int(users[key].get("chips", 0)) + int(value); msg = f"🪙 {value} jeton kazandın!"
    elif kind == "frame":
        users[key].setdefault("ownedFrames", [])
        if value not in users[key]["ownedFrames"]: users[key]["ownedFrames"].append(value)
        msg = f"🎨 {value} çerçeve kazandın!"
    elif kind == "color":
        users[key].setdefault("ownedNameColors", [])
        if value not in users[key]["ownedNameColors"]: users[key]["ownedNameColors"].append(value)
        msg = f"🌈 {value} isim rengi kazandın!"
    else:
        users[key].setdefault("ownedBadges", [])
        if value not in users[key]["ownedBadges"]: users[key]["ownedBadges"].append(value)
        msg = f"🎖️ {value} rozeti kazandın!"
    users[key]["openedChests"] = int(users[key].get("openedChests", 0)) + 1
    monte_add_xp(users, key, 25)
    save_users(users)
    return {"ok": True, "msg": msg, "profile": monte_public_payload(key, users[key])}

@app.route("/api/buy_cosmetic", methods=["POST"])
def api_buy_cosmetic():
    data = request.get_json(force=True, silent=True) or {}
    users, key = monte_find_or_create_user(data.get("u", ""))
    if not key: return {"ok": False, "msg": "Giriş gerekli."}
    item = data.get("item", "gold-frame")
    items = {"gold-frame": ("ownedFrames", "gold", 1000), "diamond-frame": ("ownedFrames", "diamond", 5000),
             "baroque-frame": ("ownedFrames", "baroque", 7500), "rainbow-name": ("ownedNameColors", "rainbow", 3000),
             "animated-profile": ("ownedBadges", "✨ Animasyonlu Profil", 10000)}
    group, value, price = items.get(item, items["gold-frame"])
    if not is_owner_name(key) and int(users[key].get("chips", 0)) < price:
        return {"ok": False, "msg": "Yeterli jeton yok."}
    if not is_owner_name(key):
        users[key]["chips"] = int(users[key].get("chips", 0)) - price
    users[key].setdefault(group, [])
    if value not in users[key][group]: users[key][group].append(value)
    monte_add_xp(users, key, 20)
    save_users(users)
    return {"ok": True, "msg": "Satın alındı.", "profile": monte_public_payload(key, users[key])}

@app.route("/api/friend_request", methods=["POST"])
def api_friend_request():
    data = request.get_json(force=True, silent=True) or {}
    users = load_users()
    key = find_user_key(users, data.get("u", ""))
    tkey = find_user_key(users, data.get("target", ""))
    if not key or not tkey: return {"ok": False, "msg": "Kullanıcı bulunamadı."}
    monte_ensure_user_defaults(users[key]); monte_ensure_user_defaults(users[tkey])
    if key == tkey: return {"ok": False, "msg": "Kendini ekleyemezsin."}
    if key not in users[tkey].setdefault("friendRequests", []): users[tkey]["friendRequests"].append(key)
    save_users(users)
    return {"ok": True, "msg": "Arkadaş isteği gönderildi."}

@app.route("/api/accept_friend", methods=["POST"])
def api_accept_friend():
    data = request.get_json(force=True, silent=True) or {}
    users = load_users()
    key = find_user_key(users, data.get("u", ""))
    rkey = find_user_key(users, data.get("requester", ""))
    if not key or not rkey: return {"ok": False, "msg": "Kullanıcı bulunamadı."}
    monte_ensure_user_defaults(users[key]); monte_ensure_user_defaults(users[rkey])
    if rkey in users[key].get("friendRequests", []): users[key]["friendRequests"].remove(rkey)
    if rkey not in users[key]["friends"]: users[key]["friends"].append(rkey)
    if key not in users[rkey]["friends"]: users[rkey]["friends"].append(key)
    save_users(users)
    return {"ok": True, "msg": "Arkadaş eklendi."}

@app.route("/api/send_private_message", methods=["POST"])
def api_send_private_message():
    data = request.get_json(force=True, silent=True) or {}
    users = load_users()
    key = find_user_key(users, data.get("u", ""))
    tkey = find_user_key(users, data.get("target", ""))
    msg = (data.get("msg") or "").strip()
    if not key or not tkey or not msg: return {"ok": False, "msg": "Eksik bilgi."}
    monte_ensure_user_defaults(users[tkey])
    users[tkey].setdefault("messages", []).insert(0, {"from": key, "msg": msg, "time": int(time.time())})
    users[tkey]["messages"] = users[tkey]["messages"][:50]
    save_users(users)
    return {"ok": True, "msg": "Mesaj gönderildi."}

@app.route("/api/join_tournament", methods=["POST"])
def api_join_tournament():
    data = request.get_json(force=True, silent=True) or {}
    users, key = monte_find_or_create_user(data.get("u", ""))
    if not key: return {"ok": False, "msg": "Giriş gerekli."}
    tournament = data.get("tournament", "weekly-codenames")
    if tournament in users[key].get("tournaments", []): return {"ok": False, "msg": "Zaten kayıtlısın."}
    if not is_owner_name(key) and int(users[key].get("chips", 0)) < 100: return {"ok": False, "msg": "Yeterli jeton yok."}
    if not is_owner_name(key): users[key]["chips"] = int(users[key].get("chips", 0)) - 100
    users[key].setdefault("tournaments", []).append(tournament)
    monte_add_xp(users, key, 50)
    save_users(users)
    return {"ok": True, "msg": "Turnuvaya katıldın. 100 jeton kesildi."}

@app.route("/api/premium_tarot", methods=["POST"])
def api_premium_tarot():
    data = request.get_json(force=True, silent=True) or {}
    users, key = monte_find_or_create_user(data.get("u", ""))
    if not key: return {"ok": False, "msg": "Giriş gerekli."}
    if not is_owner_name(key) and int(users[key].get("chips", 0)) < 1500: return {"ok": False, "msg": "Yeterli jeton yok."}
    if not is_owner_name(key): users[key]["chips"] = int(users[key].get("chips", 0)) - 1500
    q = (data.get("question") or "").strip()
    birth = (data.get("birthDate") or "").strip()
    photo = (data.get("photoNote") or "").strip()
    result = f"🤖 AI Tarot Premium Yorumu\\n\\nDoğum tarihi: {birth or '-'}\\nSoru: {q or '-'}\\nFotoğraf notu: {photo or '-'}\\n\\nKartların enerjisi dönüşüm, karar ve içsel netleşme dönemini gösteriyor. Sezgilerini dinle, acele karar verme ve niyetini netleştir."
    users[key].setdefault("premiumTarotRequests", []).insert(0, {"time": int(time.time()), "question": q, "birthDate": birth, "photoNote": photo, "result": result})
    monte_add_xp(users, key, 75)
    save_users(users)
    return {"ok": True, "msg": result}




@app.route("/premium_old_disabled_259292")
def premium_page():
    content = """<div class='grid'><div class='item'><h2>💎 Premium Üyelik</h2><p>Premium üyelik sistemi yakında aktif olacak.</p></div></div>"""
    return montenoir_page("💎 Premium Üyelik", content)



@app.route("/tarot_old_disabled")
def tarot_page_new_bg():
    return """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tarot & Ritüel - Londres VIP</title>
<style>
*{box-sizing:border-box}
html,body{
  margin:0;
  min-height:100%;
  background:#050505;
  color:#f6d777;
  font-family:Arial,Helvetica,sans-serif;
}
.tarot-page{
  min-height:100vh;
  width:100%;
  background:
    linear-gradient(180deg,rgba(0,0,0,.10),rgba(0,0,0,.62)),
    url('/static/tarot_home.png') center top / cover no-repeat fixed;
  position:relative;
  padding:28px;
}
.back{
  position:fixed;
  top:18px;
  left:18px;
  z-index:5;
  text-decoration:none;
  color:#d4af37;
  border:1px solid rgba(212,175,55,.65);
  background:rgba(0,0,0,.55);
  border-radius:14px;
  padding:12px 18px;
  font-weight:900;
  box-shadow:0 0 18px rgba(212,175,55,.25);
}
.tarot-actions{
  position:absolute;
  left:50%;
  bottom:52px;
  transform:translateX(-50%);
  display:grid;
  grid-template-columns:repeat(4, minmax(150px, 1fr));
  gap:16px;
  width:min(900px,92vw);
}
.tarot-card{
  min-height:98px;
  border:1px solid rgba(212,175,55,.52);
  border-radius:16px;
  background:linear-gradient(180deg,rgba(0,0,0,.72),rgba(0,0,0,.50));
  color:#fff;
  text-decoration:none;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:8px;
  text-align:center;
  box-shadow:0 0 20px rgba(0,0,0,.5), inset 0 0 18px rgba(212,175,55,.05);
}
.tarot-card b{
  color:#d4af37;
  font-size:18px;
}
.tarot-card span{
  font-size:28px;
}
.tarot-card:hover{
  transform:translateY(-2px);
  box-shadow:0 0 28px rgba(212,175,55,.42);
}
@media(max-width:760px){
  .tarot-actions{grid-template-columns:1fr 1fr;bottom:30px}
  .tarot-page{background-position:center top}
}
</style>
</head>
<body>
<div class="tarot-page">
  <a class="back" href="/">🚪 LOCA</a>

  <div class="tarot-actions">
    <a class="tarot-card" href="/coming-soon/Gunluk-Tarot"><span>🃏</span><b>Günlük Tarot</b></a>
    <a class="tarot-card" href="/coming-soon/Ritueller"><span>🕯️</span><b>Ritüeller</b></a>
    <a class="tarot-card" href="/coming-soon/Ask-Fali"><span>❤️</span><b>Aşk Falı</b></a>
    <a class="tarot-card" href="/coming-soon/Dogum-Haritasi"><span>🌙</span><b>Doğum Haritası</b></a>
  </div>
</div>
</body>
</html>
"""


# ===== TAROT REQUESTS + OWNER PANEL =====
TAROT_REQUESTS_FILE = os.path.join(os.environ.get("DATA_DIR","."), "tarot_requests.json")
ALLOWED_TAROT_EXT = {"pdf","jpg","jpeg","png"}

def _allowed_file(fn):
    return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_TAROT_EXT

def _tarot_db_on():
    return bool(os.environ.get("DATABASE_URL")) and ("psycopg2" in globals()) and psycopg2 is not None

def init_tarot_db():
    if not _tarot_db_on(): return
    conn=get_db_conn()
    cur=conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS tarot_requests (id TEXT PRIMARY KEY, data JSONB NOT NULL, created_at TIMESTAMP DEFAULT NOW())")
    conn.commit(); cur.close(); conn.close()

def load_tarot_requests():
    if _tarot_db_on():
        try:
            init_tarot_db()
            conn=get_db_conn(); cur=conn.cursor()
            cur.execute("SELECT data FROM tarot_requests ORDER BY created_at DESC")
            rows=cur.fetchall(); cur.close(); conn.close()
            return [r[0] if isinstance(r[0],dict) else json.loads(r[0]) for r in rows]
        except Exception as e:
            print("tarot db load error",e,flush=True)
    try:
        with open(TAROT_REQUESTS_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except Exception:
        return []

def save_tarot_request(item):
    if _tarot_db_on():
        try:
            init_tarot_db()
            conn=get_db_conn(); cur=conn.cursor()
            cur.execute("INSERT INTO tarot_requests (id,data) VALUES (%s,%s::jsonb) ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data",
                        (item["id"], json.dumps(item,ensure_ascii=False)))
            conn.commit(); cur.close(); conn.close(); return
        except Exception as e:
            print("tarot db save error",e,flush=True)
    items=load_tarot_requests(); items.insert(0,item)
    with open(TAROT_REQUESTS_FILE,"w",encoding="utf-8") as f: json.dump(items,f,ensure_ascii=False,indent=2)

def owner_ok(key):
    secret=os.environ.get("OWNER_SECRET","").strip() or os.environ.get("ADMIN_PASSWORD","").strip()
    if secret: return str(key)==secret
    return str(key).strip().lower() in ["yohanna","yohannaa","yohannaaaaa"]

@app.route("/api/tarot/request", methods=["POST"])
def api_tarot_request():
    rid=str(uuid.uuid4())[:8]
    file_url=""; file_name=""
    f=request.files.get("file")
    if f and f.filename:
        if not _allowed_file(f.filename): return {"ok":False,"msg":"Sadece PDF/JPG/PNG yüklenebilir."}
        file_name=secure_filename(f.filename)
        ext=file_name.rsplit(".",1)[1].lower()
        saved=f"{rid}_{int(time.time())}.{ext}"
        folder=os.path.join(app.root_path,"static","uploads")
        os.makedirs(folder,exist_ok=True)
        f.save(os.path.join(folder,saved))
        file_url="/static/uploads/"+saved
    item={
      "id":rid, "createdAt":time.strftime("%Y-%m-%d %H:%M:%S"), "status":"Yeni talep",
      "category":request.form.get("category",""), "service":request.form.get("service",""),
      "duration":request.form.get("duration",""), "price":request.form.get("price",""),
      "name":request.form.get("name",""), "motherName":request.form.get("motherName",""),
      "birthDate":request.form.get("birthDate",""), "email":request.form.get("email",""),
      "question":request.form.get("question",""), "fileUrl":file_url, "fileName":file_name
    }
    save_tarot_request(item)
    return {"ok":True,"msg":"Talep owner paneline gönderildi.","id":rid}

@app.route("/api/owner/requests")
def api_owner_requests():
    if not owner_ok(request.args.get("key","")): return {"ok":False,"msg":"Yetkisiz erişim."},403
    return {"ok":True,"requests":load_tarot_requests()}

@app.route("/owner-panel")
def owner_panel():
    key=request.args.get("key","")
    if not owner_ok(key):
        return """<!doctype html><html><head><meta charset='utf-8'><style>body{background:#050505;color:#d4af37;font-family:Arial;display:grid;place-items:center;height:100vh}input,button{padding:12px;border:1px solid #d4af37;background:#111;color:#fff;border-radius:10px;margin:5px}</style></head><body><form><h2>🔐 Owner Panel</h2><input name='key' type='password' placeholder='Owner şifresi'><button>Giriş</button></form></body></html>"""
    return """<!doctype html><html><head><meta charset='utf-8'><title>Owner Panel</title><style>body{background:#050505;color:#fff;font-family:Arial;margin:0}header{padding:18px 24px;color:#d4af37;border-bottom:1px solid #d4af37;background:#090909;font-weight:900}.card{border:1px solid rgba(212,175,55,.5);border-radius:14px;background:#0d0d0d;margin:16px;padding:16px}.row{display:grid;grid-template-columns:150px 1fr;gap:8px;margin:5px 0}.l{color:#d4af37;font-weight:bold}a{color:#00ff66}.mail{display:inline-block;margin-top:10px;border:1px solid #d4af37;border-radius:10px;padding:9px 12px;color:#d4af37;text-decoration:none}</style></head><body><header>👑 Londres VIP — OWNER PANEL</header><main id='list'>Yükleniyor...</main><script>
const key=new URLSearchParams(location.search).get('key')||'';
fetch('/api/owner/requests?key='+encodeURIComponent(key)).then(r=>r.json()).then(d=>{
 const box=document.getElementById('list');
 if(!d.ok){box.innerHTML='Yetkisiz erişim';return}
 if(!d.requests.length){box.innerHTML='<div class=card>Henüz talep yok.</div>';return}
 box.innerHTML=d.requests.map(x=>{
  const subj=encodeURIComponent('Londres VIP - Tarot / Ritüel Cevabı');
  const body=encodeURIComponent('Merhaba '+(x.name||'')+',\\n\\nTalebinle ilgili cevabım:\\n\\n');
  return `<div class="card"><h3>🆔 ${x.id} — ${x.category||''} / ${x.service||''}</h3>
  <div class=row><div class=l>Tarih</div><div>${x.createdAt||''}</div></div>
  <div class=row><div class=l>Email</div><div>${x.email||''}</div></div>
  <div class=row><div class=l>İsim</div><div>${x.name||''}</div></div>
  <div class=row><div class=l>Anne adı</div><div>${x.motherName||''}</div></div>
  <div class=row><div class=l>Doğum tarihi</div><div>${x.birthDate||''}</div></div>
  <div class=row><div class=l>Süre/Fiyat</div><div>${x.duration||''} — ${x.price||''}</div></div>
  <div class=row><div class=l>Randevu tipi</div><div>${x.appointmentType||''}</div></div><div class=row><div class=l>Randevu tarihi</div><div>${x.appointmentDate||''}</div></div><div class=row><div class=l>Soru</div><div>${(x.question||'').replace(/</g,'&lt;')}</div></div>
  <div class=row><div class=l>Dosya</div><div>${x.fileUrl?`<a target=_blank href="${x.fileUrl}">${x.fileName||'Dosyayı aç'}</a>`:'Yok'}</div></div>
  ${x.email?`<a class=mail href="mailto:${x.email}?subject=${subj}&body=${body}">📧 Mail ile cevapla</a>`:''}</div>`
 }).join('')
});
</script></body></html>"""

@app.route("/tarot")
def tarot_page():
    return """<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Tarot & Ritüel</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#050505;color:#fff;font-family:Arial}
.page{
 min-height:100vh;padding:24px;
 background:linear-gradient(180deg,rgba(0,0,0,.08),rgba(0,0,0,.72)),url('/static/tarot_home.png') center top/cover no-repeat fixed
}
.back{position:fixed;top:16px;left:16px;color:#d4af37;text-decoration:none;border:1px solid #d4af37;border-radius:12px;background:rgba(0,0,0,.62);padding:10px 14px;font-weight:bold;z-index:10}
.wrap{max-width:1120px;margin:80px auto 40px;display:grid;gap:18px}
.menuButtons{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.bigBtn{
 border:1px solid rgba(212,175,55,.75);border-radius:18px;
 background:linear-gradient(180deg,rgba(0,0,0,.74),rgba(0,0,0,.52));
 color:#fff;padding:20px 14px;font-weight:900;font-size:17px;cursor:pointer;
 box-shadow:0 0 20px rgba(212,175,55,.18), inset 0 0 16px rgba(212,175,55,.05)
}
.bigBtn:hover{background:linear-gradient(180deg,#d4af37,#714507);box-shadow:0 0 28px rgba(212,175,55,.42)}
.panel{display:none;border:1px solid rgba(212,175,55,.55);border-radius:16px;background:rgba(0,0,0,.70);padding:18px;box-shadow:0 0 22px rgba(0,0,0,.55)}
.panel.show{display:block}
.formPanel{display:block}
h2{color:#d4af37;margin-top:0}
table{width:100%;border-collapse:collapse}
td,th{padding:10px;border-bottom:1px solid rgba(212,175,55,.22);text-align:left}
button{border:1px solid #d4af37;border-radius:10px;background:linear-gradient(180deg,#d4af37,#7a4d09);color:white;padding:9px 12px;font-weight:900;cursor:pointer}
.formGrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
input,textarea,select{width:100%;padding:11px;border-radius:10px;border:1px solid #d4af37;background:#080808;color:white}
textarea{min-height:100px;grid-column:1/-1}
.full{grid-column:1/-1}
.status{color:#00ff66;margin-top:10px}
.trustBox{border:1px solid rgba(0,255,102,.35);background:rgba(0,0,0,.55);border-radius:14px;padding:14px;color:#d8ffd8}
.trustBox b{color:#00ff66}

/* REAL 3D CUBE DICE */
.diceBox{
  position:absolute;
  left:50%;
  top:50%;
  transform:translate(-50%,-50%);
  z-index:80;
  perspective:1000px;
  width:120px;
  height:120px;
  pointer-events:none;
}
.realDice{
  width:96px;
  height:96px;
  position:absolute;
  left:50%;
  top:50%;
  margin-left:-48px;
  margin-top:-48px;
  transform-style:preserve-3d;
  transform:rotateX(-18deg) rotateY(24deg);
  transition:transform .55s cubic-bezier(.2,.8,.2,1);
  filter:drop-shadow(0 24px 18px rgba(0,0,0,.95)) drop-shadow(0 0 12px rgba(255,255,255,.25));
}
.realDice.rolling{
  animation:realDiceRoll .85s linear infinite;
}
@keyframes realDiceRoll{
  0%{transform:rotateX(0deg) rotateY(0deg) rotateZ(0deg)}
  100%{transform:rotateX(720deg) rotateY(540deg) rotateZ(360deg)}
}
.diceFace{
  position:absolute;
  width:96px;
  height:96px;
  border-radius:18px;
  background:
    radial-gradient(circle at 30% 22%,rgba(255,255,255,.95),transparent 26%),
    linear-gradient(145deg,#ffffff 0%,#e8e8e8 52%,#8d8d8d 100%);
  border:3px solid #ffffff;
  box-shadow:
    inset -12px -12px 22px rgba(0,0,0,.24),
    inset 9px 9px 18px rgba(255,255,255,.82),
    0 0 16px rgba(255,255,255,.18);
  transform-style:preserve-3d;
}
.diceFace.front{transform:translateZ(48px)}
.diceFace.back{transform:rotateY(180deg) translateZ(48px)}
.diceFace.right{transform:rotateY(90deg) translateZ(48px)}
.diceFace.left{transform:rotateY(-90deg) translateZ(48px)}
.diceFace.top{transform:rotateX(90deg) translateZ(48px)}
.diceFace.bottom{transform:rotateX(-90deg) translateZ(48px)}
.pip{
  position:absolute;
  width:16px;
  height:16px;
  border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#444 0%,#050505 70%);
  box-shadow:inset 2px 2px 3px rgba(255,255,255,.13),0 2px 3px rgba(0,0,0,.55);
}
.pip.tl{left:20px;top:20px}
.pip.tr{right:20px;top:20px}
.pip.bl{left:20px;bottom:20px}
.pip.br{right:20px;bottom:20px}
.pip.center{left:50%;top:50%;transform:translate(-50%,-50%)}
.pip.ml{left:20px;top:50%;transform:translateY(-50%)}
.pip.mr{right:20px;top:50%;transform:translateY(-50%)}
.realDice.show-1{transform:rotateX(-18deg) rotateY(24deg)}
.realDice.show-2{transform:rotateX(72deg) rotateY(24deg)}
.realDice.show-3{transform:rotateX(-18deg) rotateY(204deg)}
.realDice.show-4{transform:rotateX(-18deg) rotateY(-66deg)}
.realDice.show-5{transform:rotateX(-108deg) rotateY(24deg)}
.realDice.show-6{transform:rotateX(72deg) rotateY(24deg)}


.ownerMark{
  position:absolute;
  width:42px;
  height:16px;
  border-radius:9px;
  border:1px solid rgba(255,255,255,.75);
  box-shadow:0 0 12px rgba(0,0,0,.85),0 0 10px currentColor;
  z-index:7;
}
.ownerIcon{
  position:absolute;
  width:25px;
  height:25px;
  border-radius:50%;
  display:grid;
  place-items:center;
  font-size:16px;
  background:rgba(0,0,0,.82);
  border:1px solid #ffe39b;
  box-shadow:0 0 9px rgba(212,175,55,.65);
  z-index:8;
}
.house.ownerHouse{
  border-radius:7px;
  padding:1px 3px;
}


/* Masadaki eski görselin içinde kalan çift zar + 7 ve eski 1EV/2EV panelini kapatır */
.imageMask{
  position:absolute;
  background:
    radial-gradient(circle at center,rgba(40,24,5,.72),rgba(0,0,0,.94) 68%),
    linear-gradient(135deg,rgba(16,16,16,.98),rgba(0,0,0,.98));
  border:1px solid rgba(212,175,55,.22);
  box-shadow:inset 0 0 18px rgba(212,175,55,.06);
  z-index:18;
  pointer-events:none;
}
.diceMask{
  left:38.8%;
  top:42.2%;
  width:24%;
  height:16%;
  border-radius:50%;
}
.buildMarketMask{
  left:49.5%;
  bottom:2.5%;
  width:44%;
  height:10.5%;
  border-radius:14px;
}


.moneyToast{
  position:absolute;
  left:50%;
  top:34%;
  transform:translate(-50%,-50%);
  min-width:260px;
  max-width:520px;
  padding:14px 22px;
  border-radius:18px;
  border:1px solid #d4af37;
  background:rgba(0,0,0,.86);
  color:#00ff66;
  font-size:20px;
  font-weight:900;
  text-align:center;
  text-shadow:0 0 10px rgba(0,255,102,.65);
  box-shadow:0 0 28px rgba(212,175,55,.38), inset 0 0 14px rgba(0,255,102,.08);
  z-index:90;
  opacity:0;
  pointer-events:none;
  transition:opacity .25s ease, transform .25s ease;
}
.moneyToast.show{
  opacity:1;
  transform:translate(-50%,-50%) scale(1.04);
}
.moneyPlus{color:#00ff66}
.moneyMinus{color:#ff4d4d}


.rollButtonOnBoard{
  position:absolute;
  left:50%;
  bottom:1.8%;
  transform:translateX(-50%);
  width:230px;
  padding:13px 22px;
  border-radius:18px;
  border:1px solid #ffe39b;
  background:linear-gradient(180deg,#ffe39b,#b87912 55%,#5a3203);
  color:#1b0d00;
  font-size:22px;
  font-weight:900;
  letter-spacing:1px;
  text-shadow:0 1px 0 rgba(255,255,255,.45);
  box-shadow:0 0 24px rgba(212,175,55,.45),0 10px 20px rgba(0,0,0,.8);
  z-index:95;
  cursor:pointer;
}
.rollButtonOnBoard:hover{
  filter:brightness(1.13);
  transform:translateX(-50%) scale(1.03);
}

@media(max-width:900px){.menuButtons{grid-template-columns:1fr 1fr}.formGrid{grid-template-columns:1fr}.wrap{margin-top:70px}}
</style>
</head>
<body>
<div class='page'>
<a class='back' href='/'>🚪 LOCA</a>
<div class='wrap'>

<div class='trustBox'>
<b>Güven sistemi:</b> önce talep gönderilir, owner paneline düşer, Yohanna onaylar, randevu/sesli bakım planlanır. İstersen cevap mail ile de gönderilir.
</div>

<div class='menuButtons'>
<button class='bigBtn' onclick="openPanel('tarotReadings')">🔮 Tarot Bakımları Hizmet</button>
<button class='bigBtn' onclick="openPanel('rituals')">✨ Ritüeller</button>
<button class='bigBtn' onclick="openPanel('instantAi')">🤖 Anında Tarot Yorumu</button>
<button class='bigBtn' onclick="openPanel('coinPacks')">🪙 Jeton Paketleri Paket Fiyat</button>
</div>

<div id='tarotReadings' class='panel'>
<h2>🔮 Tarot Bakımları Hizmet</h2>
<table>
<tr><th>Hizmet</th><th>Süre</th><th>Fiyat</th><th></th></tr>
<tr><td>Tek Soru Bakımı</td><td>5 dk</td><td>🪙 300 jeton</td><td><button onclick="fillService('Tarot Bakımı','Tek Soru Bakımı','5 dk','300 jeton')">Randevu / Jeton Yükle</button></td></tr>
<tr><td>3 Soru Bakımı</td><td>10 dk</td><td>🪙 700 jeton</td><td><button onclick="fillService('Tarot Bakımı','3 Soru Bakımı','10 dk','700 jeton')">Randevu / Jeton Yükle</button></td></tr>
<tr><td>Aşk Açılımı</td><td>20 dk</td><td>🪙 1000 jeton</td><td><button onclick="fillService('Tarot Bakımı','Aşk Açılımı','20 dk','1000 jeton')">Randevu / Jeton Yükle</button></td></tr>
<tr><td>Genel Bakım</td><td>30 dk</td><td>🪙 1500 jeton</td><td><button onclick="fillService('Tarot Bakımı','Genel Bakım','30 dk','1500 jeton')">Randevu / Jeton Yükle</button></td></tr>
</table>
</div>

<div id='rituals' class='panel'>
<h2>✨ Ritüeller Ritüel Fiyat</h2>
<table>
<tr><th>Ritüel</th><th>Fiyat</th><th></th></tr>
<tr><td>❤️ Aşk ve İlişki</td><td>🪙 800 jeton</td><td><button onclick="fillService('Ritüel','Aşk ve İlişki','','800 jeton')">Talep / Jeton Yükle</button></td></tr>
<tr><td>💖 Öz Güven ve Çekim Gücü</td><td>🪙 800 jeton</td><td><button onclick="fillService('Ritüel','Öz Güven ve Çekim Gücü','','800 jeton')">Talep / Jeton Yükle</button></td></tr>
<tr><td>🍀 Şans ve Bolluk</td><td>🪙 800 jeton</td><td><button onclick="fillService('Ritüel','Şans ve Bolluk','','800 jeton')">Talep / Jeton Yükle</button></td></tr>
<tr><td>💼 Kariyer ve Başarı</td><td>🪙 800 jeton</td><td><button onclick="fillService('Ritüel','Kariyer ve Başarı','','800 jeton')">Talep / Jeton Yükle</button></td></tr>
<tr><td>🕊️ Negatif Enerjiden Arınma</td><td>🪙 800 jeton</td><td><button onclick="fillService('Ritüel','Negatif Enerjiden Arınma','','800 jeton')">Talep / Jeton Yükle</button></td></tr>
<tr><td>🌙 Kişisel Niyet Ritüeli</td><td>🪙 1500 jeton</td><td><button onclick="fillService('Ritüel','Kişisel Niyet Ritüeli','','1500 jeton')">Talep / Jeton Yükle</button></td></tr>
</table>
</div>

<div id='instantAi' class='panel'>
<h2>🤖 Anında Tarot Yorumu</h2>
<p>Rastgele Kart Açılımı — 🪙 100 jeton</p>
<button onclick='instantTarot()'>🤖 AI yorum al</button>
<div id='aiResult' class='status'></div>
</div>

<div id='coinPacks' class='panel'>
<h2>🪙 Jeton Paketleri Paket Fiyat</h2>
<table>
<tr><td>200 jeton</td><td>£4.99</td></tr>
<tr><td>500 jeton</td><td>£9.99</td></tr>
<tr><td>1200 jeton</td><td>£19.99</td></tr>
<tr><td>3000 jeton</td><td>£39.99</td></tr>
<tr><td>8000 jeton</td><td>£89.99</td></tr>
</table>
</div>

<div class='panel formPanel'>
<h2>✍️ Sorunu Yaz</h2>
<form id='tarotForm' enctype='multipart/form-data'>
<input type='hidden' name='category' id='category' value='Serbest Soru'>
<input type='hidden' name='service' id='service' value='Sorunu Yaz'>
<input type='hidden' name='price' id='price'>
<input type='hidden' name='duration' id='duration'>
<div class='formGrid'>
<input name='name' placeholder='İsim' required>
<input name='motherName' placeholder='Anne adı'>
<input name='birthDate' type='date'>
<input name='email' type='email' placeholder='E-posta' required>
<select name='appointmentType'>
<option value='mail'>Mail ile cevap istiyorum</option>
<option value='voice'>Mikrofonlu / sesli randevu istiyorum</option>
<option value='pdf'>PDF cevap istiyorum</option>
</select>
<input name='appointmentDate' type='datetime-local' title='Randevu tarihi'>
<textarea name='question' placeholder='Sorunu yaz' required></textarea>
<input class='full' name='file' type='file' accept='.pdf,.jpg,.jpeg,.png'>
<button class='full'>🪙 Jeton Yükle / Talep Gönder</button>
</div>
<div id='formStatus' class='status'></div>
</form>
</div>

</div></div>
<script>
function openPanel(id){
 document.querySelectorAll('.panel:not(.formPanel)').forEach(p=>p.classList.remove('show'));
 document.getElementById(id).classList.add('show');
 document.getElementById(id).scrollIntoView({behavior:'smooth',block:'center'});
}
function fillService(c,s,d,p){
 category.value=c;service.value=s;duration.value=d;price.value=p;
 tarotForm.scrollIntoView({behavior:'smooth'});
 formStatus.textContent='Seçilen hizmet: '+c+' / '+s+' / '+p;
}
function instantTarot(){
 const cards=['Aşıklar','Ay','Güneş','Kule','Yıldız','İmparatoriçe'];
 const c=cards[Math.floor(Math.random()*cards.length)];
 aiResult.textContent='Seçilen kart: '+c+' — Kısa yorum: Enerjin dönüşüm ve sezgi alanında yoğunlaşıyor.';
}
tarotForm.addEventListener('submit',e=>{
 e.preventDefault();
 const fd=new FormData(tarotForm);
 formStatus.textContent='Gönderiliyor...';
 fetch('/api/tarot/request',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
   formStatus.textContent=d.msg||JSON.stringify(d);
   if(d.ok) tarotForm.reset();
 }).catch(()=>formStatus.textContent='Gönderim hatası.');
});
</script>
</body></html>"""



# ===== Londres OWNER / REWARDS / AVATAR =====
def is_owner_username(username):
    return str(username or "").strip().lower() in ["yohanna", "yohannaa", "yohannaaaaa"]

def ensure_owner_user():
    try:
        users = load_users()
        key = None
        for k in users:
            if is_owner_username(k):
                key = k
                break
        if not key:
            key = "Yohanna"
            users[key] = {}
        users[key].update({
            "username": key,
            "chips": 999999999,
            "xp": 999999,
            "level": 999,
            "membershipLabel": "OWNER",
            "membershipLevel": "owner",
            "isAdmin": True,
            "isOwner": True,
            "avatarFrame": "diamond",
            "nameColor": "gold"
        })
        save_users(users)
    except Exception as e:
        print("owner init error", e, flush=True)


@app.route("/api/profile/avatar", methods=["POST"])
def api_profile_avatar():
    username = request.form.get("username", "").strip()
    if not username:
        return {"ok": False, "msg": "Önce giriş yap."}

    f = request.files.get("avatar")
    if not f or not f.filename:
        return {"ok": False, "msg": "Avatar dosyası seçilmedi."}

    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        return {"ok": False, "msg": "Sadece JPG, PNG veya WEBP yüklenebilir."}

    users = load_users()
    key = next((k for k in users if k.lower() == username.lower()), None)
    if not key:
        return {"ok": False, "msg": "Kullanıcı bulunamadı."}

    folder = os.path.join(app.root_path, "static", "avatars")
    os.makedirs(folder, exist_ok=True)

    filename = secure_filename(f"{key}_{int(time.time())}.{ext}")
    f.save(os.path.join(folder, filename))

    avatar_url = "/static/avatars/" + filename
    users[key]["avatar"] = avatar_url
    users[key]["avatarData"] = avatar_url
    save_users(users)

    return {"ok": True, "msg": "Avatar güncellendi.", "avatar": avatar_url}


@app.route("/api/reward/daily", methods=["POST"])
def api_daily_reward():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username", "").strip()
    if not username:
        return {"ok": False, "msg": "Önce giriş yap."}

    users = load_users()
    key = next((k for k in users if k.lower() == username.lower()), None)
    if not key:
        return {"ok": False, "msg": "Kullanıcı bulunamadı."}

    today = time.strftime("%Y-%m-%d")

    if not is_owner_username(key) and users[key].get("lastDailyRewardDate") == today:
        return {"ok": False, "msg": "Günlük ödülünü bugün aldın. Yarın tekrar çevir."}

    # 30/50/100 sık, 1000+2000 toplam %5
    prizes = [30, 50, 100, 300, 1000, 2000]
    weights = [40, 30, 18, 7, 3, 2]
    prize = random.choices(prizes, weights=weights, k=1)[0]

    if is_owner_username(key):
        prize = 2000

    users[key]["chips"] = int(users[key].get("chips", 0)) + prize
    users[key]["lastDailyReward"] = str(int(time.time()))
    users[key]["lastDailyRewardDate"] = today
    save_users(users)

    return {"ok": True, "prize": prize, "chips": users[key]["chips"], "msg": f"{prize} jeton kazandın!"}


@app.route("/premium")
def premium_page_dup2():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>💎 Premium Üyelik</h1><p>Premium üyelik sistemi yakında aktif olacak.</p></body></html>"""

@app.route("/kasa")
def kasa_page():
    return """<html><head><meta charset='utf-8'><style>body{background:#050505;color:#fff;font-family:Arial;padding:30px}.locaBtn{display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;color:#d4af37;border:1px solid #d4af37;padding:10px 14px;border-radius:12px;text-decoration:none;background:rgba(0,0,0,.70)}</style></head><body><a class='locaBtn' href='/'>🚪 LOCA</a><h1>🪙 Londres Kasası</h1><p>Jeton paketleri ve ödeme sistemi burada olacak.</p></body></html>"""

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




@app.route("/coming-soon/Monopoly")
def monopoly_redirect():
    return redirect("/monopoly")













MONOPOLY_ROOMS={}

# name, type, price, base_rent, group
# Règles adaptées aux villes de ton plateau.
MONOPOLY_CELLS=[
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

MONOPOLY_GROUPS={}
for i,c in enumerate(MONOPOLY_CELLS):
    if c[1]=="property":
        MONOPOLY_GROUPS.setdefault(c[4],[]).append(i)

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
        if c not in MONOPOLY_ROOMS:
            return c

def active_names(room):
    return [n for n,p in room["players"].items() if not p.get("bankrupt")]

def player_owns_full_group(room, username, group):
    group_cells=MONOPOLY_GROUPS.get(group,[])
    return bool(group_cells) and all(room["owners"].get(str(i))==username for i in group_cells)

def group_building_counts(room, group):
    vals=[]
    for i in MONOPOLY_GROUPS.get(group,[]):
        vals.append(int(room["houses"].get(str(i),0)) + (5 if room.get("hotels",{}).get(str(i)) else 0))
    return vals

def can_build_house(room, username, cell_index):
    name,typ,price,base,group=MONOPOLY_CELLS[cell_index]
    if typ!="property":
        return False,"Sadece şehirlerin üzerine ev kurulabilir."
    if room["owners"].get(str(cell_index))!=username:
        return False,"Bu şehir senin değil."
    if not player_owns_full_group(room, username, group):
        return False,"Bu renkteki tüm şehirleri almalısın."
    if any(room.get("mortgages",{}).get(str(i)) for i in MONOPOLY_GROUPS.get(group,[])):
        return False,"Bu renk grubunda ipotekli mülk varken bina kurulamaz."
    if room.get("hotels",{}).get(str(cell_index)):
        return False,"Otelli arsaya ev kurulamaz."
    current=int(room["houses"].get(str(cell_index),0))
    if current>=4:
        return False,"Bu arsada zaten 4 ev var. Otel kurabilirsin."
    # dengeli ev kuralı: bir arsaya ikinci ev koymadan önce gruptaki herkes en az bir ev almalı
    counts=[int(room["houses"].get(str(i),0)) for i in MONOPOLY_GROUPS.get(group,[]) if not room.get("hotels",{}).get(str(i))]
    if counts and current>min(counts):
        return False,"Evler dengeli kurulmalı: önce aynı renkteki diğer şehirlere ev koy."
    return True,"OK"

def can_build_hotel(room, username, cell_index):
    name,typ,price,base,group=MONOPOLY_CELLS[cell_index]
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
    name,typ,price,base,group=MONOPOLY_CELLS[cell_index]
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
    count=sum(1 for i,c in enumerate(MONOPOLY_CELLS) if c[1]=="transport" and room["owners"].get(str(i))==owner and not room.get("mortgages",{}).get(str(i)))
    return {1:25,2:50,3:100,4:200}.get(count,25)

def utility_rent(room, owner, dice):
    count=sum(1 for i,c in enumerate(MONOPOLY_CELLS) if c[1]=="utility" and room["owners"].get(str(i))==owner and not room.get("mortgages",{}).get(str(i)))
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
    MONOPOLY_ROOMS[c]=r
    join_room(c)
    colors=["#34c759","#ff3b30","#007aff","#ffd60a","#bf5af2","#ff9500"]; color=colors[(len(r["players"]))%len(colors)]; r["players"][u]={"name":u,"token":t,"color":color,"money":START_MONEY,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odayı kurdu."
    emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_join_room")
def mj(data):
    u=(data or {}).get("username","Misafir").strip() or "Misafir"
    t=(data or {}).get("token","🎩")
    c=((data or {}).get("code","") or "").strip().upper()
    if c not in MONOPOLY_ROOMS:
        emit("monopoly_error",{"msg":"Oda bulunamadı."}); return
    r=MONOPOLY_ROOMS[c]
    join_room(c)
    if u not in r["players"]:
        colors=["#34c759","#ff3b30","#007aff","#ffd60a","#bf5af2","#ff9500"]; color=colors[(len(r["players"]))%len(colors)]; r["players"][u]={"name":u,"token":t,"color":color,"money":START_MONEY,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odaya girdi."
    emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_start_game")
def ms(data):
    c=((data or {}).get("code","") or "").strip().upper()
    r=MONOPOLY_ROOMS.get(c)
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
    r=MONOPOLY_ROOMS.get(c)
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
    new=(old+d)%len(MONOPOLY_CELLS)
    if new<old:
        p["money"]+=PASS_START_BONUS
    p["position"]=new
    name,typ,price,base,group=MONOPOLY_CELLS[new]
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
    r=MONOPOLY_ROOMS.get(c)
    if not r or u not in r["players"]:
        return
    p=r["players"][u]
    pos=p["position"]
    name,typ,price,base,group=MONOPOLY_CELLS[pos]
    if typ not in ["property","transport","utility"] or str(pos) in r["owners"] or p["money"]<price:
        emit("monopoly_error",{"msg":"Satın alınamaz."}); return
    p["money"]-=price
    r["owners"][str(pos)]=u
    r["lastLog"]=f"{u}, {name} mülkünü {price}€ karşılığı satın aldı."
    emit("monopoly_room_state",m_public(r),room=c)



@socketio.on("monopoly_end_turn")
def me(data):
    c=((data or {}).get("code","") or "").strip().upper()
    r=MONOPOLY_ROOMS.get(c)
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
    c=m_code(); r=m_room(c,u); MONOPOLY_ROOMS[c]=r; join_room(c)
    r["players"][u]={"name":u,"token":t,"money":1000,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odayı kurdu."; emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_join_room")
def mj(data):
    u=(data or {}).get("username","Misafir").strip() or "Misafir"; t=(data or {}).get("token","🎩"); c=((data or {}).get("code","") or "").strip().upper()
    if c not in MONOPOLY_ROOMS: emit("monopoly_error",{"msg":"Oda bulunamadı."}); return
    r=MONOPOLY_ROOMS[c]; join_room(c)
    if u not in r["players"]:
        r["players"][u]={"name":u,"token":t,"money":1000,"position":0,"jailed":0,"bankrupt":False,"hasRolled":False}
    r["lastLog"]=u+" odaya girdi."; emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_start_game")
def ms(data):
    c=((data or {}).get("code","") or "").strip().upper(); r=MONOPOLY_ROOMS.get(c)
    if r: r["started"]=True; r["lastLog"]="Oyun başladı."; emit("monopoly_room_state",m_public(r),room=c)

@socketio.on("monopoly_roll_dice")
def mr(data):
    c=((data or {}).get("code","") or "").strip().upper(); u=(data or {}).get("username","").strip(); r=MONOPOLY_ROOMS.get(c)
    if not r or u not in r["players"]: emit("monopoly_error",{"msg":"Oda/oyuncu yok."}); return
    names=[n for n,p in r["players"].items() if not p.get("bankrupt")]
    if u!=names[r["turnIndex"]%len(names)]: emit("monopoly_error",{"msg":"Sıra sende değil."}); return
    p=r["players"][u]; d=random.randint(1,6); old=p["position"]; new=(old+d)%len(MONOPOLY_CELLS)
    if new<old: p["money"]+=200
    p["position"]=new; name,typ,price,rent,grp=MONOPOLY_CELLS[new]; log=f"{u} zar: {d}. {name}."
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
    c=((data or {}).get("code","") or "").strip().upper(); u=(data or {}).get("username","").strip(); r=MONOPOLY_ROOMS.get(c)
    if not r or u not in r["players"]: return
    p=r["players"][u]; pos=p["position"]; name,typ,price,rent,grp=MONOPOLY_CELLS[pos]
    if typ not in ["property","transport","utility"] or str(pos) in r["owners"] or p["money"]<price: emit("monopoly_error",{"msg":"Satın alınamaz."}); return
    p["money"]-=price; r["owners"][str(pos)]=u; r["lastLog"]=f"{u}, {name} aldı."; emit("monopoly_room_state",m_public(r),room=c)


@socketio.on("monopoly_end_turn")
def me(data):
    c=((data or {}).get("code","") or "").strip().upper(); r=MONOPOLY_ROOMS.get(c)
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
    r=MONOPOLY_ROOMS.get(c)
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
    r=MONOPOLY_ROOMS.get(c)
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







@app.route("/")
def home_page():
    return render_template("index.html")

@app.route("/metropoly")
@app.route("/monopoly")
def metropoly_page():
    return render_template("metropoly.html")

if __name__ == "__main__":
    import os, uuid, uuid, uuid, sys, traceback
    try:
        if "init_db" in globals():
            init_db()
        if "bootstrap_admin_user" in globals():
            bootstrap_admin_user()
        if "ensure_owner_user" in globals():
            ensure_owner_user()
    except Exception:
        traceback.print_exc()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Londres VIP starting on port {port}", flush=True)
    try:
        socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        raise
