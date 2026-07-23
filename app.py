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
      <a href="/coming-soon/101">💎 101</a><a href="/monopoly">🏙️ Metropoly</a>
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
activeText:"Torneo Codenames settimanale", vipPoints:"I TUOI PUNTI VIP", take:"RITIRA", join:"PARTECIPA", details:"DETT
