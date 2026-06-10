from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import random, string, os, json, hashlib, time, smtplib, ssl

app = Flask(__name__)
app.config['SECRET_KEY'] = 'codenamesvip'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
rooms = {}
MAX_PLAYERS = 10

USERS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "users.json")

def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
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

def public_profile(username, data):
    # Profil public : email caché aux autres joueurs.
    return {
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
        "vipUntil": data.get("vipUntil", 0)
    }

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
    "name-gold": 3000,
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
        'guessLimit': 0, 'guessesMade': 0, 'clueActive': False, 'category': category, 'roundNo': 1
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
        users[account]['games'] = int(users[account].get('games', 0)) + 1
        users[account]['chips'] = int(p.get('chips', users[account].get('chips', 1000)))
        if winning_team and p.get('team') == winning_team:
            users[account]['wins'] = int(users[account].get('wins', 0)) + 1
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
h1{color:#f5d77b;text-shadow:0 0 10px #d4af37,0 0 45px #d4af37;letter-spacing:4px;font-size:50px;margin:25px 0 5px;font-weight:900}.subtitle{color:#d4af37;letter-spacing:3px}button{background:linear-gradient(135deg,#111,#333);color:#f5d77b;border:1px solid #d4af37;border-radius:14px;padding:8px 10px;margin:4px;font-weight:bold;cursor:pointer;font-size:13px}button:hover{box-shadow:0 0 15px #d4af37;transform:scale(1.03)}input,select{padding:10px;border-radius:10px;border:1px solid #d4af37;background:#111;color:white;margin:4px}.panel{margin:15px auto;padding:15px;max-width:1050px;border:1px solid rgba(212,175,55,.45);border-radius:22px;background:rgba(255,255,255,.06)}.hidden{display:none}.topLeftFixed{position:fixed;top:15px;left:15px;z-index:999999;display:flex;gap:8px;flex-wrap:wrap;max-width:58%}.topRightFixed{position:fixed;top:15px;right:15px;z-index:999999;display:flex;align-items:center;gap:8px;border:2px solid #d4af37;border-radius:20px;padding:8px 12px;background:rgba(0,0,0,.65)}.micStatus{color:#ffd700;font-weight:bold}.tableSeat{display:inline-block;width:260px;min-height:140px;margin:10px;padding:12px;border-radius:22px;border:2px solid #d4af37;background:radial-gradient(circle at center,#0f6b3a,#06351f);box-shadow:0 0 20px #00ff99,inset 0 0 25px #001f12;vertical-align:top}.lockedSeat{opacity:.45;filter:grayscale(40%)}.avatarImg{width:42px;height:42px;border-radius:50%;object-fit:cover;border:3px solid #d4af37;box-shadow:0 0 10px #d4af37}.femaleFrame{border:3px solid #ff4fd8!important;box-shadow:0 0 15px #ff4fd8!important}.maleFrame{border:3px solid #111!important;box-shadow:0 0 15px #000!important}.mainLayout{display:grid;grid-template-columns:1fr 330px;gap:15px;max-width:1320px;margin:0 auto}.sidePanel{margin:15px;padding:12px;border-radius:22px;border:2px solid #d4af37;background:linear-gradient(180deg,rgba(18,12,30,.95),rgba(0,0,0,.92));box-shadow:0 0 25px rgba(212,175,55,.5);min-height:400px}.profileCard{margin:6px 0;padding:8px;border-radius:12px;border:1px solid #d4af37;background:linear-gradient(135deg,rgba(60,40,90,.85),rgba(15,10,25,.95));text-align:left;font-size:12px}.profileCard b{font-size:15px;color:white}.adminBadge{color:#ffd700;text-shadow:0 0 10px #d4af37;font-weight:bold}.adminActions button{font-size:11px;padding:5px 7px}.teams{display:flex;justify-content:center;gap:15px;margin:15px;flex-wrap:wrap}.team{padding:15px;width:280px;border-radius:18px;font-weight:bold}.blueTeam{background:linear-gradient(135deg,#0055ff,#00d4ff)}.redTeam{background:linear-gradient(135deg,#ff1f1f,#ff7a00)}.teamCount{display:block;margin-top:8px;font-size:20px;color:white}.scoreBox{font-size:20px;color:#ffd700;text-shadow:0 0 10px #d4af37}.playerList{margin-top:8px;font-size:13px;text-align:left}.statusBox{font-size:21px;color:#ffd700;text-shadow:0 0 15px #d4af37}.board{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;max-width:900px;margin:20px auto;padding:10px;perspective:1200px}.card{
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
.name-gold{color:#ffd700!important;text-shadow:0 0 10px #ffd700,0 0 22px #d4af37!important;}
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
        gap:12px!important;
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

</style></head><body>
<div class="vipCasinoMarks"><span class="m1">A♠</span><span class="m2">K♥</span><span class="m3">Q♣</span><span class="m4">J♦</span><span class="m5">♠♥♣♦</span><span class="m6">A K Q J</span></div><div id="profileChip" class="vipProfileChip" onclick="openProfile()">👤 Profil</div><div class="topLeftFixed"><button onclick="startTimer()">⏱ Süre</button><button onclick="newGame()">🎲 Yeni Oyun</button><button onclick="goLobby()">🚪 Lobi</button><button onclick="openAuth()">👤 Üyelik</button><button onclick="openProfile()">🏆 Profil</button><button onclick="openRanking()">📊 Classement</button><button onclick="openSettings()">⚙️ Ayarlar</button><button onclick="openWords()">📚 Kelimeler</button><button onclick="openBet()">🎰 Bahis</button><button onclick="openShop()">🪙 Jeton Al</button></div>

<div id="winnerOverlay"><div id="winnerText"></div></div>
<div id="settingsModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>⚙️ Ayarlar</h2><h3>Kurallar</h3><p>Spymaster ipucu vermeden kart açılamaz. Sadece sırası olan takım tahmin yapar ve kart açar. Seyirciler sadece izler ve sanal jetonla bahis yapabilir.</p><p>Doğru takım rengi açılırsa takım devam eder. Rakip renk veya nötr açılırsa sıra geçer. Suikastçı açılırsa açan takım kaybeder.</p><h3>Varsayılan Diller</h3><select id="languageSelect"><option>Türkçe</option><option>English</option><option>Français</option><option>Русский</option><option>Nederlands</option></select></div></div>
<div id="wordsModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>📚 Kelime Serileri</h2><p>Yeni seri seçince yeni oyun başlatılır.</p><button onclick="setCategory('default')">📁 CodeNames8.txt</button><button onclick="setCategory('animals')">🐾 Hayvanlar Serisi</button><button onclick="setCategory('adult')">🔞 18+ Serisi</button></div></div>
<div id="shopModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🎰 Boutique VIP & Jetons</h2><p><b>Mode sécurisé :</b> Stripe/PayPal sont en mode démo. Aucun paiement réel n’est encaissé dans cette version.</p><p>Bakiyen: <b id="shopChips">1000</b> 🪙</p><h3>🪙 Jeton Al - Démo</h3><div class="paymentDemoBox"><b>Stripe Démo</b><br><button onclick="demoBuyChips(1000,\'Stripe\')">Stripe: +1000 🪙</button><button onclick="demoBuyChips(5000,\'Stripe\')">Stripe: +5000 🪙</button><button onclick="demoBuyChips(20000,\'Stripe\')">Stripe: +20000 🪙</button></div><div class="paymentDemoBox"><b>PayPal Démo</b><br><button onclick="demoBuyChips(1000,\'PayPal\')">PayPal: +1000 🪙</button><button onclick="demoBuyChips(5000,\'PayPal\')">PayPal: +5000 🪙</button><button onclick="demoBuyChips(20000,\'PayPal\')">PayPal: +20000 🪙</button></div><hr><h3>👑 VIP Ol</h3><div class="shopItem">VIP Bronze — 3000 🪙 / 7 gün <button onclick="buyVipWithChips(\'vip-bronze\')">VIP Al</button></div><div class="shopItem">VIP Gold — 9000 🪙 / 30 gün <button onclick="buyVipWithChips(\'vip-gold\')">VIP Al</button></div><div class="shopItem">VIP Diamond — 25000 🪙 / 90 gün <button onclick="buyVipWithChips(\'vip-diamond\')">VIP Al</button></div><hr><h3>🪙 Jeton Bonus</h3><button onclick="buyVirtualChips(1000)">Bonus +1000 🪙</button><button onclick="buyVirtualChips(5000)">Bonus +5000 🪙</button><button onclick="buyVirtualChips(20000)">Bonus +20000 🪙</button><button onclick="buyVirtualChips(75000)">Bonus +75000 🪙</button><hr><h3>🖼️ Avatar Cadres</h3><div class="shopItem">Altın Çerçeve — 1000 🪙 <button onclick="buyCosmetic('frame-gold')">Satın Al</button> <button onclick="equipCosmetic('frame-gold')">Kullan</button></div><div class="shopItem">VIP Çerçeve — 5000 🪙 <button onclick="buyCosmetic('frame-vip')">Satın Al</button> <button onclick="equipCosmetic('frame-vip')">Kullan</button></div><div class="shopItem">Efsanevi Çerçeve — 15000 🪙 <button onclick="buyCosmetic('frame-legendary')">Satın Al</button> <button onclick="equipCosmetic('frame-legendary')">Kullan</button></div><hr><h3>🌈 İsim Renkleri</h3><div class="shopItem">Kırmızı İsim — 500 🪙 <button onclick="buyCosmetic('name-red')">Satın Al</button> <button onclick="equipCosmetic('name-red')">Kullan</button></div><div class="shopItem">Mavi İsim — 500 🪙 <button onclick="buyCosmetic('name-blue')">Satın Al</button> <button onclick="equipCosmetic('name-blue')">Kullan</button></div><div class="shopItem">Mor İsim — 1000 🪙 <button onclick="buyCosmetic('name-purple')">Satın Al</button> <button onclick="equipCosmetic('name-purple')">Kullan</button></div><div class="shopItem">Altın İsim — 3000 🪙 <button onclick="buyCosmetic('name-gold')">Satın Al</button> <button onclick="equipCosmetic('name-gold')">Kullan</button></div><div class="shopItem">Rainbow İsim — 10000 🪙 <button onclick="buyCosmetic('name-rainbow')">Satın Al</button> <button onclick="equipCosmetic('name-rainbow')">Kullan</button></div></div></div>
<div id="betModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🎰 Sanal Bahis</h2><p>Bakiyen: <b id="betChips">1000</b> 🪙</p><div class="betBox"><label>Takım:</label><select id="betTeam"><option value="blue">🔵 Mavi Takım</option><option value="red">🔴 Kırmızı Takım</option></select><label>Miktar:</label><input id="betAmount" type="number" value="100" min="1"><button onclick="placeBet()">Bahis Yap</button></div><div id="betInfo">Henüz bahis yok.</div></div></div>

<div id="authModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>👤 Üyelik</h2><h3>📝 Kayıt Ol</h3><input id="regUsername" placeholder="Kullanıcı adı"><input id="regEmail" type="email" placeholder="Email"><input id="regPassword" type="password" placeholder="Şifre"><input id="regPassword2" type="password" placeholder="Şifre tekrar"><button onclick="registerAccount()">Kayıt Ol</button><hr><h3>🔐 Giriş Yap</h3><input id="loginUsername" placeholder="Kullanıcı adı"><input id="loginPassword" type="password" placeholder="Şifre"><button onclick="loginAccount()">Giriş Yap</button><button onclick="openForgotPassword()">Şifremi Unuttum</button><hr><button onclick="logoutAccount()">🚪 Çıkış Yap</button><p id="authStatus">Henüz giriş yapılmadı.</p></div></div>
<div id="forgotModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🔑 Şifre Yenileme</h2><p>Email adresini yaz. Sistem sana şifre yenileme linki göndermeye çalışır.</p><input id="forgotEmail" type="email" placeholder="Email"><button onclick="requestPasswordReset()">Link Gönder</button><div id="resetLinkBox" style="margin-top:10px;color:#ffd700;font-size:13px;"></div><hr><h3>Yeni Şifre</h3><input id="resetToken" placeholder="Reset token"><input id="newPassword" type="password" placeholder="Yeni şifre"><button onclick="confirmPasswordReset()">Şifreyi Yenile</button></div></div>
<div id="profileModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🏆 Profil</h2><div id="profileInfo">Giriş yapmadın.</div><hr><h3>🎨 Avatar Yükle</h3><input id="avatarUploadInput" type="file" accept="image/png,image/jpeg,image/webp"><button onclick="uploadAvatar()">Avatarı Kaydet</button><p style="font-size:12px;color:#d4af37;">PNG/JPG/WebP kullan. Çok büyük dosya seçme.</p></div></div>
<div id="rankingModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>📊 Classement</h2><div id="rankingInfo">Yükleniyor...</div></div></div>

<div id="endGameModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2 id="endGameTitle">🏆 Fin de partie</h2><div id="endGameInfo"></div><button onclick="newGame();closeModals()">🎲 Nouvelle manche</button><button onclick="goLobby();closeModals()">🚪 Retour lobby</button></div></div>
<h1>♠️ CODENAMES VIP ♦️</h1><p class="subtitle">Luxury Online Multiplayer Edition</p>
<div id="lobby" class="panel"><h2>🎰 Oda Sistemi</h2><button onclick="createRoom()">Oda Oluştur</button><br><input id="roomInput" placeholder="Oda kodu"><input id="roomPassword" placeholder="Oda şifresi"><button onclick="joinExistingRoom()">Odaya Katıl</button><h3 id="roomText">Oda: -</h3><hr><h3>Profil Oluştur / Masaya Otur</h3><input id="playerName" placeholder="Oyuncu adı"><select id="avatarChoice"><option value="woman.png">Kadın</option><option value="man.png">Erkek</option></select><select id="teamChoice"><option value="blue">🔵 Mavi Masa</option><option value="red">🔴 Kırmızı Masa</option><option value="spectator">👀 Seyirci</option></select><select id="roleChoice"><option value="player">Saha Ajanı</option><option value="blueSpy">Mavi Spymaster</option><option value="redSpy">Kırmızı Spymaster</option><option value="spectator">Seyirci</option></select><br><button onclick="sitAtTable()">Masaya Otur</button><button onclick="toggleReady()">✅ Hazırım</button><button onclick="startGame()">🚀 Oyunu Başlat</button><div id="readyInfo" style="color:#ffd700;margin-top:8px;">Hazır durumu: -</div><div><div class="tableSeat" id="blueSeatBox"><div>🔵 MAVİ MASA <span id="blueLockText"></span></div><div id="blueLobby"></div></div><div class="tableSeat" id="redSeatBox"><div>🔴 KIRMIZI MASA <span id="redLockText"></span></div><div id="redLobby"></div></div><div class="tableSeat" id="spectatorSeatBox"><div>👀 SEYİRCİLER</div><div id="spectatorLobby"></div></div></div></div>
<div id="gameScreen" class="hidden"><div class="mainLayout"><div><div class="panel"><button onclick="startTimer()">▶ Süre Başlat</button><button onclick="pauseTimer()">⏸ Durdur</button><button onclick="setTimer(60)">1 dk</button><button onclick="setTimer(180)">3 dk</button><button onclick="setTimer(300)">5 dk</button><button onclick="setTimer(600)">10 dk</button><br>⏱ <span id="timer">05:00</span></div><div class="panel"><h3>🎙 Oda Mikrofonu</h3><button onclick="startMic()">🎙 Aç</button><button onclick="stopMic()">🔇 Kapat</button><span id="micStatus" class="micStatus">Kapalı</span><p style="font-size:12px;color:#d4af37;">Mikrofon sadece oda içinde çalışır. Konuşan kişinin ikonu yeşil yanar.</p></div><div class="panel"><p id="roundText" class="scoreBox">🎮 Tur: 1</p><p id="roleText">Rol: -</p><p id="phaseText" class="statusBox">🎰 Oyun bekliyor...</p><p id="scoreText" class="scoreBox">🏆 Mavi: 0 | Kırmızı: 0</p><p id="chipsText" class="scoreBox">🪙 Jeton: 1000</p></div><div class="teams"><div class="team blueTeam">🔵 MAVİ TAKIM<span class="teamCount">Kalan kelime: <span id="blueCount">9</span></span><div id="bluePlayers" class="playerList"></div></div><div class="team redTeam">🔴 KIRMIZI TAKIM<span class="teamCount">Kalan kelime: <span id="redCount">8</span></span><div id="redPlayers" class="playerList"></div></div></div><div class="panel"><input id="clueText" placeholder="İpucu yaz"><select id="clueNumber"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option><option value="7">7</option><option value="8">8</option><option value="9">9</option><option value="∞">♾️</option></select><button onclick="sendClue()">İpucu Ver</button><button onclick="endTurn()" style="background:#008f4c;color:white;">✅ Sırayı Bitir</button><h2 id="clueDisplay">İpucu: -</h2><div id="clueLog">📜 Oyun bandı: Henüz ipucu yok.</div><h2 id="turnDisplay">Sıra: Belirlenmedi</h2></div><div class="board" id="board"></div><div class="panel"><h3>💬 Chat</h3><div class="chatTabs"><button onclick="setChatMode('global')">🌍 Genel</button><button onclick="setChatMode('team')">🔒 Takım</button><button onclick="setChatMode('dm')">📩 DM</button></div><div id="messages"></div><select id="dmTarget"><option value="">DM oyuncu seç</option></select><br><input id="chatInput" placeholder="Mesaj yaz"><button onclick="sendMessage()">Gönder</button><br><button class="emojiBtn" onclick="addEmoji('😂')">😂</button><button class="emojiBtn" onclick="addEmoji('🔥')">🔥</button><button class="emojiBtn" onclick="addEmoji('💀')">💀</button><button class="emojiBtn" onclick="addEmoji('👑')">👑</button><button class="emojiBtn" onclick="addEmoji('❤️')">❤️</button><button class="emojiBtn" onclick="addEmoji('😈')">😈</button><small id="chatModeText" style="color:#ffd700;">Mode: Genel</small></div></div><div class="sidePanel"><h3>👥 Bağlanan Oyuncular</h3><div id="onlinePlayers"></div><div class="spectatorBox"><h3>👀 Seyirciler</h3><div id="spectatorList">-</div></div><hr><h3>🔁 Join Team</h3><button onclick="joinTeam('blue','player')">🔵 Mavi Saha Ajanı</button><button onclick="joinTeam('blue','blueSpy')">🕵️ Mavi Spymaster</button><button onclick="joinTeam('red','player')">🔴 Kırmızı Saha Ajanı</button><button onclick="joinTeam('red','redSpy')">🕵️ Kırmızı Spymaster</button><button onclick="joinTeam('spectator','spectator')">👀 Seyirci</button><hr><h3>👑 Admin Paneli</h3><div id="adminPanel"><button onclick="toggleTeamLock('blue')">🔒 Mavi Kilitle</button><button onclick="toggleTeamLock('red')">🔒 Kırmızı Kilitle</button><button onclick="adminNewGame()">🎲 Yeni Oyun</button><button onclick="adminRevealAll()">🃏 Kartları Aç</button><button onclick="adminResetStats()">🏆 Skoru Sıfırla</button></div><hr><h3>🏆 Kazananlar / Oyun Kaydı</h3><div id="historyPanel"></div></div></div></div>
<script>
const socket=io();let roomCode='',myName='',myRole='',myTeam='',mySid='',joined=false,isAdmin=false,currentChips=1000;let seconds=300,timerRunning=false,timerInterval=null,micStream=null;let voicePeers={},voiceStarted=false,currentMicStates={},lastPlayers=[],lastLocks={blue:false,red:false},audioContext=null,speakingInterval=null,mySpeaking=false,currentAccount=null,currentProfile=null,pendingAutoSit=false;let lastOpenedStates=[],lastWinner='',dealSoundPlayed=false,chatMode='global',currentReady={};
function chipKey(n){return 'codenamesChips_'+(n||'guest')}function getSavedChips(n){let v=localStorage.getItem(chipKey(n));if(v===null)return 1000;let x=parseInt(v);return isNaN(x)?1000:x}function setSavedChips(n,a){localStorage.setItem(chipKey(n),String(a))}function saveLocalProfile(){localStorage.setItem('codenamesRoom',roomCode);localStorage.setItem('codenamesName',myName);localStorage.setItem('codenamesRole',myRole);localStorage.setItem('codenamesTeam',myTeam);localStorage.setItem('codenamesPassword',roomPassword.value||'')}function restoreLocalFields(){let r=localStorage.getItem('codenamesRoom')||'',n=localStorage.getItem('codenamesName')||'',ro=localStorage.getItem('codenamesRole')||'',t=localStorage.getItem('codenamesTeam')||'';if(r)roomInput.value=r;if(n)playerName.value=n;if(ro)roleChoice.value=ro;if(t)teamChoice.value=t}
function avatarClass(f){return f==='woman.png'?'avatarImg femaleFrame':'avatarImg maleFrame'}function roleLabel(r){if(r==='player')return'Saha Ajanı';if(r==='blueSpy')return'Mavi Spymaster';if(r==='redSpy')return'Kırmızı Spymaster';if(r==='spectator')return'Seyirci';return r}function teamLabel(t){if(t==='blue')return'🔵 Mavi';if(t==='red')return'🔴 Kırmızı';return'👀 Seyirci'}
function playerNameClass(p){
    return p.nameColor || 'name-default';
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
}function openSettings(){settingsModal.style.display='flex'}function openWords(){wordsModal.style.display='flex'}function openShop(){shopChips.innerHTML=currentChips;shopModal.style.display='flex'}function openBet(){betChips.innerHTML=currentChips;betModal.style.display='flex'}function closeModals(){document.querySelectorAll('.modal').forEach(m=>m.style.display='none')}

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
    currentChips=profile.chips || 1000;
    localStorage.setItem('codenamesAccount',currentAccount);
    localStorage.setItem('loggedUser',currentAccount);
    localStorage.setItem('loggedIn','true');
    localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
    if(playerName) playerName.value=currentAccount;
    if(authStatus) authStatus.innerHTML='Connecté : '+currentAccount;
    updateProfileChip();
}
function localLoginFallback(username,password){
    const users=loadLocalUsers();
    const rec=users[(username||'').trim().toLowerCase()];
    if(rec && rec.password===password && rec.profile){
        applyLoggedProfile(rec.profile);
        alert('Giriş yapıldı.');
        return true;
    }
    return false;
}
function openAuth(){
    authModal.style.display='flex';
    authStatus.innerHTML = currentAccount ? 'Connecté : '+currentAccount : 'Henüz giriş yapılmadı.';
}
function updateProfileChip(){
    if(currentAccount){
        const avatarSrc = (currentProfile && currentProfile.avatarData) ? currentProfile.avatarData : defaultAvatarData((currentProfile && currentProfile.avatar) || 'woman.png');
        const vip = currentProfile && currentProfile.vip ? '<span class="vipBadgeSmall">VIP</span>' : '';
        profileChip.innerHTML='<img src="'+avatarSrc+'" style="width:36px;height:36px;border-radius:50%;object-fit:cover;border:2px solid #d4af37;box-shadow:0 0 10px #d4af37;"> <span>'+currentAccount+'</span>'+vip+' <span>🪙 '+currentChips+'</span>';
    }else{
        profileChip.innerHTML='👤 Profil';
    }
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
        return true;
    }
    return false;
}

function requireLogin(){
    if(!currentAccount){
        restoreLoggedAccount();
    }
    if(!currentAccount){
        alert('Oda oluşturmak için önce giriş yapmalısın.');
        openAuth();
        return false;
    }
    if(!currentProfile){
        currentProfile = {username:currentAccount, chips:getSavedChips(currentAccount), wins:0, games:0};
    }
    currentChips = currentProfile.chips || getSavedChips(currentAccount) || 1000;
    localStorage.setItem('codenamesAccount', currentAccount);
    localStorage.setItem('loggedUser', currentAccount);
    localStorage.setItem('loggedIn', 'true');
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
        '<br><b>VIP:</b> '+(currentProfile.vip ? (currentProfile.vipLevel||'VIP') : 'Non')+
        '<br><b>Inventaire:</b> '+((currentProfile.inventory||[]).join(', ')||'-');
}
function openRanking(){
    rankingModal.style.display='flex';
    socket.emit('get_ranking');
}
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

function createRoom(){if(!requireLogin())return;myName=currentAccount;playerName.value=currentAccount;localStorage.setItem('codenamesName',currentAccount);socket.emit('create_room',{password:roomPassword.value.trim(),account:currentAccount})}function joinExistingRoom(){if(!requireLogin())return;myName=currentAccount;playerName.value=currentAccount;localStorage.setItem('codenamesName',currentAccount);let c=roomInput.value.trim().toUpperCase();if(!c){alert('Oda kodu yaz.');return}socket.emit('join_room_code',{room:c,password:roomPassword.value.trim(),account:currentAccount})}function sitAtTable(){if(!requireLogin())return;if(!roomCode){alert('Önce oda oluştur veya odaya katıl.');return}let n=playerName.value.trim();if(!n){alert('Oyuncu adı yaz.');return}myName=n;myRole=roleChoice.value;myTeam=teamChoice.value;currentChips=currentProfile?currentProfile.chips:getSavedChips(myName);joined=true;saveLocalProfile();socket.emit('sit',{room:roomCode,name:n,avatar:avatarChoice.value,avatarData:(currentProfile&&currentProfile.avatarData)||'',nameColor:(currentProfile&&currentProfile.nameColor)||'default',avatarFrame:(currentProfile&&currentProfile.avatarFrame)||'none',team:myTeam,role:myRole,chips:currentChips,account:currentAccount})}function startGame(){if(!requireLogin())return;if(!joined){alert('Önce masaya otur.');return}socket.emit('start_game',{room:roomCode})}function newGame(){dealSoundPlayed=false;lastOpenedStates=[];lastWinner='';socket.emit('new_game',{room:roomCode})}function goLobby(){gameScreen.classList.add('hidden');lobby.classList.remove('hidden')}function joinTeam(t,r){if(!requireLogin())return;myTeam=t;myRole=r;saveLocalProfile();socket.emit('join_team',{room:roomCode,team:t,role:r})}function toggleGuess(i){socket.emit('toggle_guess',{room:roomCode,index:i})}function revealCard(i,e){if(e)e.stopPropagation();socket.emit('reveal_card',{room:roomCode,index:i})}function showGuesses(i,e){if(e)e.stopPropagation();socket.emit('show_guesses',{room:roomCode,index:i})}function sendClue(){let c=clueText.value.trim(),n=clueNumber.value;if(!c){alert('İpucu yaz.');return}socket.emit('send_clue',{room:roomCode,clue:c,number:n,name:myName})}function endTurn(){socket.emit('end_turn',{room:roomCode})}function setCategory(c){socket.emit('set_category',{room:roomCode,category:c});closeModals()}function buyVirtualChips(a){if(!myName){alert('Önce profil oluştur.');return}socket.emit('buy_virtual_chips',{room:roomCode,amount:a});closeModals()}
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
function uploadAvatar(){
    if(!currentAccount){alert('Önce giriş yap.');return}
    const file = avatarUploadInput.files[0];
    if(!file){alert('Resim seç.');return}
    if(file.size > 450000){
        alert('Resim çok büyük. Daha küçük bir resim seç.');
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
        const nameClass = (st.speaking ? ' speakingName ' : ' ') + playerNameClass(p);
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

function playTone(freq,duration,type='sine',volume=.08){
    try{
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.value = freq;
        gain.gain.value = volume;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc.stop(ctx.currentTime + duration);
    }catch(e){}
}
function soundDeal(i){
    setTimeout(()=>playTone(220+(i%5)*35,.08,'triangle',.035), i*45);
}
function soundCorrect(){
    playTone(660,.12,'sine',.08);
    setTimeout(()=>playTone(880,.10,'sine',.06),90);
}
function soundWrong(){
    playTone(220,.18,'sawtooth',.06);
}
function soundAssassin(){
    playTone(80,.35,'sawtooth',.12);
    setTimeout(()=>playTone(45,.45,'sawtooth',.10),130);
}
function soundWin(){
    [523,659,784,1046].forEach((f,i)=>setTimeout(()=>playTone(f,.18,'triangle',.08),i*120));
}
function soundLose(){
    [330,260,196,130].forEach((f,i)=>setTimeout(()=>playTone(f,.22,'sawtooth',.06),i*130));
}
function detectCardSounds(g){
    if(!lastOpenedStates.length){
        lastOpenedStates = g.cards.map(c=>c.open);
        return;
    }

    g.cards.forEach((c,i)=>{
        if(c.open && !lastOpenedStates[i]){
            const cardEl = document.getElementById('card_'+i);
            if(c.role === 'assassin'){
                if(cardEl) cardEl.classList.add('assassinBoom');
                soundAssassin();
            }else if(c.role === g.turn){
                if(cardEl) cardEl.classList.add('correctFlash');
                soundCorrect();
            }else{
                soundWrong();
            }
        }
    });

    if(g.winner && g.winner !== lastWinner){
        if((g.winner.includes('MAVİ') && myTeam === 'blue') || (g.winner.includes('KIRMIZI') && myTeam === 'red')){
            soundWin();
        }else{
            soundLose();
        }
    }

    lastOpenedStates = g.cards.map(c=>c.open);
    lastWinner = g.winner || '';
}

function renderGame(g){board.innerHTML='';roundText.innerHTML='🎮 Tur: '+(g.roundNo||1);blueCount.innerHTML=g.blueCount;redCount.innerHTML=g.redCount;phaseText.innerHTML=g.phase+((g.guessLimit&&g.guessLimit>0)?'<br>🎯 Tahmin hakkı: '+g.guessesMade+' / '+g.guessLimit:'');clueDisplay.innerHTML=g.clue;turnDisplay.innerHTML=g.turn==='blue'?'🔵 Sıra Mavi Takımda':'🔴 Sıra Kırmızı Takımda';clueLog.innerHTML=(g.clueLog&&g.clueLog.length)?'📜 Oyun bandı:<br>'+g.clueLog.slice(-8).reverse().join('<br>'):'📜 Oyun bandı: Henüz ipucu yok.';if(g.moveLog&&g.moveLog.length)clueLog.innerHTML+='<hr>🃏 Kart kaydı:<br>'+g.moveLog.slice(-8).reverse().join('<br>');g.cards.forEach((c,i)=>{let cls='card dealCard';if(c.guessed)cls+=' guessed';if(c.open||canSeeRole()||g.winner)cls+=' open '+c.role+'Card';let names=(c.guessedBy||[]).join(', '),gb=names?`<div class='guessName'>🎯 ${names}</div>`:'';board.innerHTML+=`<div id="card_${i}" class="${cls}" style="animation-delay:${i*45}ms" onclick="toggleGuess(${i})"><button class="revealBtn" onclick="revealCard(${i}, event)">A♠</button><button class="guessBtn" onclick="showGuesses(${i}, event)">Tahmin</button><span class="wordText">${c.word}</span>${gb}</div>`;if(!dealSoundPlayed)soundDeal(i)});if(!dealSoundPlayed)dealSoundPlayed=true;setTimeout(()=>detectCardSounds(g),80);if(g.winner){showWinner(g.winner);showEndGame(g)}}function showWinner(t){winnerText.innerHTML=t;winnerOverlay.style.display='flex';setTimeout(()=>winnerOverlay.style.display='none',5000)}function showEndGame(g){endGameTitle.innerHTML=g.winner;endGameInfo.innerHTML='🎮 Tur: '+(g.roundNo||1)+'<br>🔵 Kalan: '+g.blueCount+' | 🔴 Kalan: '+g.redCount+'<br><br>Yeni manche başlatabilir veya lobbyye dönebilirsin.';endGameModal.style.display='flex'}function updateTimerDisplay(){let m=Math.floor(seconds/60),s=seconds%60;timer.innerHTML=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')}function startTimer(){if(timerRunning)return;timerRunning=true;timerInterval=setInterval(()=>{if(seconds>0){seconds--;updateTimerDisplay()}},1000)}function pauseTimer(){timerRunning=false;clearInterval(timerInterval)}function setTimer(v){pauseTimer();seconds=v;updateTimerDisplay()}
socket.on('register_result',d=>{
    if(!d.ok){alert(d.msg);return}
    currentAccount=d.profile.username;
    currentProfile=d.profile;
    localStorage.setItem('codenamesAccount',currentAccount);
    localStorage.setItem('loggedUser',currentAccount);
    localStorage.setItem('loggedIn','true');
    localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
    playerName.value=currentAccount;
    currentChips=d.profile.chips || 1000;
    authStatus.innerHTML='Compte créé : '+currentAccount;
    saveLocalUser(currentProfile, regPassword.value);
    updateProfileChip();alert('Hesap oluşturuldu.');
});

socket.on('login_result',d=>{
    if(!d.ok){
        if(localLoginFallback(loginUsername.value.trim(), loginPassword.value)) return;
        alert(d.msg);return
    }
    currentAccount=d.profile.username;
    currentProfile=d.profile;
    localStorage.setItem('codenamesAccount',currentAccount);
    localStorage.setItem('loggedUser',currentAccount);
    localStorage.setItem('loggedIn','true');
    localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));
    playerName.value=currentAccount;
    currentChips=d.profile.chips || 1000;
    authStatus.innerHTML='Connecté : '+currentAccount;
    saveLocalUser(currentProfile, loginPassword.value);
    updateProfileChip();alert('Giriş yapıldı.');
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
    updateProfileChip();
    openProfile();
    alert('Avatar kaydedildi.');
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
    restoreLocalFields();
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
});socket.on('room_created',d=>{roomCode=d.room;isAdmin=true;roomText.innerHTML='Oda: '+roomCode+' 👑 Admin sensin';saveLocalProfile()});socket.on('room_joined',d=>{roomCode=d.room;isAdmin=false;roomText.innerHTML='Oda: '+roomCode;saveLocalProfile();if(pendingAutoSit){pendingAutoSit=false;setTimeout(()=>sitAtTable(),250)}});socket.on('error_msg',d=>alert(d.msg));socket.on('players_update',d=>{if(d.micStates) currentMicStates=d.micStates;if(d.ready) currentReady=d.ready;renderReady(d.players,d.ready||{});renderPlayers(d.players,d.locks)});socket.on('game_update',d=>{currentMicStates=d.micStates||currentMicStates||{};currentReady=d.ready||currentReady||{};let me=d.players.find(p=>p.sid===mySid||p.name===myName);if(me){myName=me.name;myTeam=me.team;myRole=me.role;isAdmin=me.isAdmin;currentChips=me.chips||1000;setSavedChips(myName,currentChips);if(currentProfile){currentProfile.chips=currentChips;localStorage.setItem('codenamesProfile',JSON.stringify(currentProfile));}saveLocalProfile()}lobby.classList.add('hidden');gameScreen.classList.remove('hidden');roleText.innerHTML='Bu cihazda: '+myName+' · Rol: '+roleLabel(myRole);chipsText.innerHTML='🪙 Jeton: '+currentChips;betChips.innerHTML=currentChips;shopChips.innerHTML=currentChips;updateProfileChip();renderReady(d.players,d.ready||{});renderPlayers(d.players,d.locks);renderStats(d.stats);renderBets(d.bets);renderGame(d.game)});socket.on('chat_update',d=>{messages.innerHTML+='<b>🌍 '+d.name+':</b> '+d.msg+'<br>'});socket.on('team_chat_update',d=>{messages.innerHTML+='<b>🔒 '+d.name+':</b> '+d.msg+'<br>'});socket.on('dm_chat_update',d=>{messages.innerHTML+='<b>📩 '+d.name+':</b> '+d.msg+'<br>'});socket.on('kicked',()=>{alert('Odadan çıkarıldın.');localStorage.clear();location.reload()});socket.on('made_spectator',()=>{myRole='spectator';myTeam='spectator';saveLocalProfile();alert('Seyirci moduna alındın.')});socket.on('guess_names',d=>{alert('Bu kartı tahmin edenler: '+((d.names&&d.names.length)?d.names.join(', '):'Henüz tahmin yok.'))});

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
</script></body></html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)


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
    account = data.get('account')
    users = load_users()
    if not account or account not in users:
        emit('error_msg', {'msg':'Oda oluşturmak için önce giriş yapmalısın.'})
        return
    code = room_code(); password = data.get('password','')
    rooms[code] = {'players': [], 'game': new_game('default'), 'stats': {'blueWins':0,'redWins':0,'history':[],'wordHistory':[],'betHistory':[],'gameNo':0}, 'locks': {'blue':False,'red':False}, 'password': password, 'adminSid': request.sid, 'bets': {}, 'micStates': {}, 'ready': {}, 'teamChat': {'blue': [], 'red': []}, 'dm': {}, 'category': 'default'}
    join_room(code); emit('room_created', {'room': code})

@socketio.on('join_room_code')
def join_room_code(data):
    account = data.get('account')
    users = load_users()
    if not account or account not in users:
        emit('error_msg', {'msg':'Odaya katılmak için önce giriş yapmalısın.'})
        return
    code = data['room']; password = data.get('password','')
    if code not in rooms: emit('error_msg', {'msg':'Oda bulunamadı.'}); return
    if rooms[code]['password'] and rooms[code]['password'] != password: emit('error_msg', {'msg':'Oda şifresi yanlış.'}); return
    join_room(code); emit('room_joined', {'room': code}); emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks'], 'micStates': rooms[code].get('micStates', {}), 'ready': rooms[code].get('ready', {})})

@socketio.on('sit')
def sit(data):
    account = data.get('account')
    users = load_users()
    if not account or account not in users:
        emit('error_msg', {'msg':'Oynamak için önce giriş yapmalısın.'})
        return
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
    if len(avatar_data) > 700000:
        emit('avatar_upload_result', {'ok': False, 'msg': 'Resim çok büyük. Daha küçük bir avatar seç.'})
        return

    users = load_users()
    user_key = find_user_key(users, account)
    if not user_key:
        emit('avatar_upload_result', {'ok': False, 'msg': 'Kullanıcı bulunamadı. Yeniden giriş yap.'})
        return

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
        users[key]['nameColor'] = users[key].get('nameColor', 'name-gold') or 'name-gold'
    elif pack == 'vip-gold':
        users[key]['avatarFrame'] = 'frame-vip'
        users[key]['nameColor'] = 'name-gold'
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


if __name__ == '__main__':
    port=int(os.environ.get('PORT',5000)); socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
