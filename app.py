from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import random, string, os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'codenamesvip'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
rooms = {}
MAX_PLAYERS = 10

ANIMALS = ['ASLAN','KAPLAN','KEDİ','KÖPEK','KURT','TİLKİ','AYI','YILAN','KARTAL','ŞAHİN','BALİNA','YUNUS','AHTAPOT','KAPLUMBAĞA','TAVŞAN','GEYİK','ZÜRAFA','FİL','GORİL','MAYMUN','PANDA','KOALA','KANGURU','PENGUEN','BAYKUŞ','KARGA','AT','EŞEK','İNEK','KEÇİ','KOYUN','DEVE','YARASA','KARINCA','ARI','KELEBEK','AKREP','ÖRÜMCEK','KURBAĞA','TİMSAH','PAPAĞAN']
ADULT = ['GECE','PARTİ','BAR','KULÜP','FLÖRT','GİZEM','TUTKU','ÇEKİM','BAKIŞ','ÖPÜCÜK','DANS','ŞAMPANYA','KIRMIZI','SİYAH','KADİFE','RUJ','PARFÜM','AŞK','MACERA','SIR','MASKELİ','CASINO','VIP','LÜKS','IŞIK','MÜZİK','ROMANTİK','ATEŞ','FANTEZİ','GÜNAH','ÇEKİCİ','YAKINLIK','GÜLÜMSEME','KISKANÇLIK','BÜYÜ','ODA']
FALLBACK = ['ASLAN','KEDİ','UZAY','AY','ROBOT','ORMAN','DENİZ','KALE','ELMAS','TAVŞAN','KORSAN','PİRAMİT','DRAGON','YILDIZ','GEZEGEN','ARABA','TELEFON','MÜZİK','KÖPEK','BALIK','KRAL','GÜNEŞ','KALEM','OKYANUS','MAYMUN']

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
        'guessLimit': 0, 'guessesMade': 0, 'clueActive': False, 'category': category
    }

def pdata(code):
    r = rooms[code]
    return {'players': r['players'], 'game': r['game'], 'stats': r['stats'], 'locks': r['locks'], 'bets': r['bets'], 'room': code}

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
    if 'MAVİ' in text:
        st['blueWins'] += 1; st['history'].append('Mavi Takım')
    if 'KIRMIZI' in text:
        st['redWins'] += 1; st['history'].append('Kırmızı Takım')

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

HTML = r'''@app.route("/")
def index():
    return render_template_string(HTML)
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CODENAMES VIP</title><script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
body{margin:0;background:radial-gradient(circle at top,#241633,#050505 70%);color:white;font-family:Arial,sans-serif;text-align:center}h1{color:#f5d77b;text-shadow:0 0 10px #d4af37,0 0 45px #d4af37;letter-spacing:4px;font-size:50px;margin:25px 0 5px;font-weight:900}.subtitle{color:#d4af37;letter-spacing:3px}button{background:linear-gradient(135deg,#111,#333);color:#f5d77b;border:1px solid #d4af37;border-radius:14px;padding:8px 10px;margin:4px;font-weight:bold;cursor:pointer;font-size:13px}button:hover{box-shadow:0 0 15px #d4af37;transform:scale(1.03)}input,select{padding:10px;border-radius:10px;border:1px solid #d4af37;background:#111;color:white;margin:4px}.panel{margin:15px auto;padding:15px;max-width:1050px;border:1px solid rgba(212,175,55,.45);border-radius:22px;background:rgba(255,255,255,.06)}.hidden{display:none}.topLeftFixed{position:fixed;top:15px;left:15px;z-index:999999;display:flex;gap:8px;flex-wrap:wrap;max-width:58%}.topRightFixed{position:fixed;top:15px;right:15px;z-index:999999;display:flex;align-items:center;gap:8px;border:2px solid #d4af37;border-radius:20px;padding:8px 12px;background:rgba(0,0,0,.65)}.micStatus{color:#ffd700;font-weight:bold}.tableSeat{display:inline-block;width:260px;min-height:140px;margin:10px;padding:12px;border-radius:22px;border:2px solid #d4af37;background:radial-gradient(circle at center,#0f6b3a,#06351f);box-shadow:0 0 20px #00ff99,inset 0 0 25px #001f12;vertical-align:top}.lockedSeat{opacity:.45;filter:grayscale(40%)}.avatarImg{width:42px;height:42px;border-radius:50%;object-fit:cover;border:3px solid #d4af37;box-shadow:0 0 10px #d4af37}.femaleFrame{border:3px solid #ff4fd8!important;box-shadow:0 0 15px #ff4fd8!important}.maleFrame{border:3px solid #111!important;box-shadow:0 0 15px #000!important}.mainLayout{display:grid;grid-template-columns:1fr 330px;gap:15px;max-width:1320px;margin:0 auto}.sidePanel{margin:15px;padding:12px;border-radius:22px;border:2px solid #d4af37;background:linear-gradient(180deg,rgba(18,12,30,.95),rgba(0,0,0,.92));box-shadow:0 0 25px rgba(212,175,55,.5);min-height:400px}.profileCard{margin:6px 0;padding:8px;border-radius:12px;border:1px solid #d4af37;background:linear-gradient(135deg,rgba(60,40,90,.85),rgba(15,10,25,.95));text-align:left;font-size:12px}.profileCard b{font-size:15px;color:white}.adminBadge{color:#ffd700;text-shadow:0 0 10px #d4af37;font-weight:bold}.adminActions button{font-size:11px;padding:5px 7px}.teams{display:flex;justify-content:center;gap:15px;margin:15px;flex-wrap:wrap}.team{padding:15px;width:280px;border-radius:18px;font-weight:bold}.blueTeam{background:linear-gradient(135deg,#0055ff,#00d4ff)}.redTeam{background:linear-gradient(135deg,#ff1f1f,#ff7a00)}.teamCount{display:block;margin-top:8px;font-size:20px;color:white}.scoreBox{font-size:20px;color:#ffd700;text-shadow:0 0 10px #d4af37}.playerList{margin-top:8px;font-size:13px;text-align:left}.statusBox{font-size:21px;color:#ffd700;text-shadow:0 0 15px #d4af37}.board{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;max-width:900px;margin:20px auto;padding:10px;perspective:1200px}.card{background:radial-gradient(circle at top left,rgba(255,255,255,.25),transparent 20%),linear-gradient(145deg,#050505,#111,#000)!important;color:#f8d878!important;min-height:90px;border-radius:26px;display:flex;align-items:center;justify-content:center;font-weight:900;letter-spacing:1px;cursor:pointer;border:4px double #d4af37;box-shadow:0 0 18px rgba(212,175,55,.9),inset 0 0 28px rgba(212,175,55,.25);transition:.35s;position:relative;overflow:hidden;transform-style:preserve-3d}.card::after{content:"♠ ♦ ♣ ♥";position:absolute;top:8px;right:10px;color:#d4af37;font-size:12px;text-shadow:0 0 10px #d4af37}.card:hover{transform:translateY(-8px) rotateX(14deg) scale(1.06);box-shadow:0 0 25px #ffd700,0 0 55px rgba(212,175,55,.8)}.card.guessed{outline:5px solid #00ff99!important;box-shadow:0 0 25px #00ff99,0 0 50px rgba(0,255,153,.8)!important}.guessName{position:absolute;bottom:5px;left:8px;right:8px;font-size:11px;color:#003300;background:rgba(0,255,153,.75);border-radius:8px;padding:2px}.revealBtn,.guessBtn{position:absolute;background:linear-gradient(145deg,#000,#2b2108,#000);color:#ffd700;border:2px solid #d4af37;border-radius:12px;padding:4px 8px;font-size:12px;font-weight:900;z-index:5;box-shadow:0 0 14px #d4af37}.revealBtn{top:5px;left:7px}.guessBtn{top:5px;right:7px}.card.open{animation:cardFlip .7s ease}@keyframes cardFlip{0%{transform:perspective(1000px) rotateY(0deg) scale(1)}50%{transform:perspective(1000px) rotateY(180deg) scale(1.15)}100%{transform:perspective(1000px) rotateY(360deg) scale(1.06)}}.blueCard{background:linear-gradient(145deg,#001a66,#0066ff,#00eaff)!important;color:white!important}.redCard{background:linear-gradient(145deg,#6b0000,#ff1f1f,#ff9a00)!important;color:white!important}.neutralCard{background:linear-gradient(145deg,#777,#e5e5e5,#fff)!important;color:black!important}.assassinCard{background:linear-gradient(145deg,#000,#141414,#3a0000)!important;color:white!important}#winnerOverlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.88);display:none;justify-content:center;align-items:center;z-index:9999}#winnerText{font-size:72px;font-weight:900;color:#ffd700;text-shadow:0 0 20px #d4af37,0 0 50px #d4af37}#messages{height:100px;overflow-y:auto;text-align:left;padding:10px;background:#080808;border-radius:10px;margin-bottom:8px}#historyPanel{font-size:18px;color:white;text-shadow:0 0 10px white}#clueLog{margin-top:10px;color:#ffd700;font-weight:bold;line-height:1.5}.modal{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;justify-content:center;align-items:center;z-index:1000000}.modalContent{width:min(760px,92vw);max-height:82vh;overflow:auto;background:linear-gradient(180deg,#20152d,#070707);border:2px solid #d4af37;border-radius:24px;padding:20px;box-shadow:0 0 40px #d4af37;text-align:left}.modalContent h2{text-align:center;color:#ffd700}.closeBtn{float:right}.betBox,.spectatorBox{padding:10px;border:1px solid #d4af37;border-radius:14px;margin:8px 0}.spectatorBox{border-style:dashed;font-size:12px}@media(max-width:800px){h1{font-size:30px}.mainLayout{display:block}.card{min-height:60px;font-size:11px}#winnerText{font-size:38px}.topLeftFixed,.topRightFixed{position:static;justify-content:center;max-width:100%;margin:8px}}
</style></head><body>
<div class="topLeftFixed"><button onclick="startTimer()">⏱ Süre</button><button onclick="newGame()">🎲 Yeni Oyun</button><button onclick="goLobby()">🚪 Lobi</button><button onclick="openSettings()">⚙️ Ayarlar</button><button onclick="openWords()">📚 Kelimeler</button><button onclick="openBet()">🎰 Bahis</button><button onclick="openShop()">🪙 Jeton Al</button></div>
<div class="topRightFixed"><button onclick="startMic()">🎙 Aç</button><button onclick="stopMic()">🔇 Kapat</button><span id="micStatus" class="micStatus">Kapalı</span></div>
<div id="winnerOverlay"><div id="winnerText"></div></div>
<div id="settingsModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>⚙️ Ayarlar</h2><h3>Kurallar</h3><p>Spymaster ipucu vermeden kart açılamaz. Sadece sırası olan takım tahmin yapar ve kart açar. Seyirciler sadece izler ve sanal jetonla bahis yapabilir.</p><p>Doğru takım rengi açılırsa takım devam eder. Rakip renk veya nötr açılırsa sıra geçer. Suikastçı açılırsa açan takım kaybeder.</p><h3>Varsayılan Diller</h3><select id="languageSelect"><option>Türkçe</option><option>English</option><option>Français</option><option>Русский</option><option>Nederlands</option></select></div></div>
<div id="wordsModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>📚 Kelime Serileri</h2><p>Yeni seri seçince yeni oyun başlatılır.</p><button onclick="setCategory('default')">📁 CodeNames8.txt</button><button onclick="setCategory('animals')">🐾 Hayvanlar Serisi</button><button onclick="setCategory('adult')">🔞 18+ Serisi</button></div></div>
<div id="shopModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🪙 Jeton Al</h2><p><b>Not:</b> Bu sürümde jetonlar sanaldır; gerçek ödeme yoktur.</p><p>Bakiyen: <b id="shopChips">1000</b> 🪙</p><button onclick="buyVirtualChips(1000)">Bronze +1000 🪙</button><button onclick="buyVirtualChips(5000)">Silver +5000 🪙</button><button onclick="buyVirtualChips(20000)">Gold +20000 🪙</button><button onclick="buyVirtualChips(75000)">Diamond +75000 🪙</button></div></div>
<div id="betModal" class="modal"><div class="modalContent"><button class="closeBtn" onclick="closeModals()">X</button><h2>🎰 Sanal Bahis</h2><p>Bakiyen: <b id="betChips">1000</b> 🪙</p><div class="betBox"><label>Takım:</label><select id="betTeam"><option value="blue">🔵 Mavi Takım</option><option value="red">🔴 Kırmızı Takım</option></select><label>Miktar:</label><input id="betAmount" type="number" value="100" min="1"><button onclick="placeBet()">Bahis Yap</button></div><div id="betInfo">Henüz bahis yok.</div></div></div>
<h1>♠️ CODENAMES VIP ♦️</h1><p class="subtitle">Luxury Online Multiplayer Edition</p>
<div id="lobby" class="panel"><h2>🎰 Oda Sistemi</h2><button onclick="createRoom()">Oda Oluştur</button><br><input id="roomInput" placeholder="Oda kodu"><input id="roomPassword" placeholder="Oda şifresi"><button onclick="joinExistingRoom()">Odaya Katıl</button><h3 id="roomText">Oda: -</h3><hr><h3>Profil Oluştur / Masaya Otur</h3><input id="playerName" placeholder="Oyuncu adı"><select id="avatarChoice"><option value="woman.png">Kadın</option><option value="man.png">Erkek</option></select><select id="teamChoice"><option value="blue">🔵 Mavi Masa</option><option value="red">🔴 Kırmızı Masa</option><option value="spectator">👀 Seyirci</option></select><select id="roleChoice"><option value="player">Saha Ajanı</option><option value="blueSpy">Mavi Spymaster</option><option value="redSpy">Kırmızı Spymaster</option><option value="spectator">Seyirci</option></select><br><button onclick="sitAtTable()">Masaya Otur</button><button onclick="startGame()">Oyunu Başlat</button><div><div class="tableSeat" id="blueSeatBox"><div>🔵 MAVİ MASA <span id="blueLockText"></span></div><div id="blueLobby"></div></div><div class="tableSeat" id="redSeatBox"><div>🔴 KIRMIZI MASA <span id="redLockText"></span></div><div id="redLobby"></div></div><div class="tableSeat" id="spectatorSeatBox"><div>👀 SEYİRCİLER</div><div id="spectatorLobby"></div></div></div></div>
<div id="gameScreen" class="hidden"><div class="mainLayout"><div><div class="panel"><button onclick="startTimer()">▶ Süre Başlat</button><button onclick="pauseTimer()">⏸ Durdur</button><button onclick="setTimer(60)">1 dk</button><button onclick="setTimer(180)">3 dk</button><button onclick="setTimer(300)">5 dk</button><button onclick="setTimer(600)">10 dk</button><br>⏱ <span id="timer">05:00</span></div><div class="panel"><p id="roleText">Rol: -</p><p id="phaseText" class="statusBox">🎰 Oyun bekliyor...</p><p id="scoreText" class="scoreBox">🏆 Mavi: 0 | Kırmızı: 0</p><p id="chipsText" class="scoreBox">🪙 Jeton: 1000</p></div><div class="teams"><div class="team blueTeam">🔵 MAVİ TAKIM<span class="teamCount">Kalan kelime: <span id="blueCount">9</span></span><div id="bluePlayers" class="playerList"></div></div><div class="team redTeam">🔴 KIRMIZI TAKIM<span class="teamCount">Kalan kelime: <span id="redCount">8</span></span><div id="redPlayers" class="playerList"></div></div></div><div class="panel"><input id="clueText" placeholder="İpucu yaz"><select id="clueNumber"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option><option value="7">7</option><option value="8">8</option><option value="9">9</option><option value="∞">♾️</option></select><button onclick="sendClue()">İpucu Ver</button><button onclick="endTurn()" style="background:#008f4c;color:white;">✅ Sırayı Bitir</button><h2 id="clueDisplay">İpucu: -</h2><div id="clueLog">📜 Oyun bandı: Henüz ipucu yok.</div><h2 id="turnDisplay">Sıra: Belirlenmedi</h2></div><div class="board" id="board"></div><div class="panel"><h3>💬 Chat</h3><div id="messages"></div><input id="chatInput" placeholder="Mesaj yaz"><button onclick="sendMessage()">Gönder</button></div></div><div class="sidePanel"><h3>👥 Bağlanan Oyuncular</h3><div id="onlinePlayers"></div><div class="spectatorBox"><h3>👀 Seyirciler</h3><div id="spectatorList">-</div></div><hr><h3>🔁 Join Team</h3><button onclick="joinTeam('blue','player')">🔵 Mavi Saha Ajanı</button><button onclick="joinTeam('blue','blueSpy')">🕵️ Mavi Spymaster</button><button onclick="joinTeam('red','player')">🔴 Kırmızı Saha Ajanı</button><button onclick="joinTeam('red','redSpy')">🕵️ Kırmızı Spymaster</button><button onclick="joinTeam('spectator','spectator')">👀 Seyirci</button><hr><h3>👑 Admin Paneli</h3><div id="adminPanel"><button onclick="toggleTeamLock('blue')">🔒 Mavi Kilitle</button><button onclick="toggleTeamLock('red')">🔒 Kırmızı Kilitle</button><button onclick="adminNewGame()">🎲 Yeni Oyun</button><button onclick="adminRevealAll()">🃏 Kartları Aç</button><button onclick="adminResetStats()">🏆 Skoru Sıfırla</button></div><hr><h3>🏆 Kazananlar / Oyun Kaydı</h3><div id="historyPanel"></div></div></div></div>
<script>
const socket=io();let roomCode='',myName='',myRole='',myTeam='',mySid='',joined=false,isAdmin=false,currentChips=1000;let seconds=300,timerRunning=false,timerInterval=null,micStream=null;
function chipKey(n){return 'codenamesChips_'+(n||'guest')}function getSavedChips(n){let v=localStorage.getItem(chipKey(n));if(v===null)return 1000;let x=parseInt(v);return isNaN(x)?1000:x}function setSavedChips(n,a){localStorage.setItem(chipKey(n),String(a))}function saveLocalProfile(){localStorage.setItem('codenamesRoom',roomCode);localStorage.setItem('codenamesName',myName);localStorage.setItem('codenamesRole',myRole);localStorage.setItem('codenamesTeam',myTeam)}function restoreLocalFields(){let r=localStorage.getItem('codenamesRoom')||'',n=localStorage.getItem('codenamesName')||'',ro=localStorage.getItem('codenamesRole')||'',t=localStorage.getItem('codenamesTeam')||'';if(r)roomInput.value=r;if(n)playerName.value=n;if(ro)roleChoice.value=ro;if(t)teamChoice.value=t}
function avatarClass(f){return f==='woman.png'?'avatarImg femaleFrame':'avatarImg maleFrame'}function roleLabel(r){if(r==='player')return'Saha Ajanı';if(r==='blueSpy')return'Mavi Spymaster';if(r==='redSpy')return'Kırmızı Spymaster';if(r==='spectator')return'Seyirci';return r}function teamLabel(t){if(t==='blue')return'🔵 Mavi';if(t==='red')return'🔴 Kırmızı';return'👀 Seyirci'}async function startMic(){try{micStream=await navigator.mediaDevices.getUserMedia({audio:true});micStatus.innerHTML='Açık'}catch(e){alert('Mikrofon izni verilmedi.')}}function stopMic(){if(micStream){micStream.getTracks().forEach(t=>t.stop());micStream=null}micStatus.innerHTML='Kapalı'}function openSettings(){settingsModal.style.display='flex'}function openWords(){wordsModal.style.display='flex'}function openShop(){shopChips.innerHTML=currentChips;shopModal.style.display='flex'}function openBet(){betChips.innerHTML=currentChips;betModal.style.display='flex'}function closeModals(){document.querySelectorAll('.modal').forEach(m=>m.style.display='none')}
function createRoom(){socket.emit('create_room',{password:roomPassword.value.trim()})}function joinExistingRoom(){let c=roomInput.value.trim().toUpperCase();if(!c){alert('Oda kodu yaz.');return}socket.emit('join_room_code',{room:c,password:roomPassword.value.trim()})}function sitAtTable(){if(!roomCode){alert('Önce oda oluştur veya odaya katıl.');return}let n=playerName.value.trim();if(!n){alert('Oyuncu adı yaz.');return}myName=n;myRole=roleChoice.value;myTeam=teamChoice.value;currentChips=getSavedChips(myName);joined=true;saveLocalProfile();socket.emit('sit',{room:roomCode,name:n,avatar:avatarChoice.value,team:myTeam,role:myRole,chips:currentChips})}function startGame(){if(!joined){alert('Önce masaya otur.');return}socket.emit('start_game',{room:roomCode})}function newGame(){socket.emit('new_game',{room:roomCode})}function goLobby(){gameScreen.classList.add('hidden');lobby.classList.remove('hidden')}function joinTeam(t,r){myTeam=t;myRole=r;saveLocalProfile();socket.emit('join_team',{room:roomCode,team:t,role:r})}function toggleGuess(i){socket.emit('toggle_guess',{room:roomCode,index:i})}function revealCard(i,e){if(e)e.stopPropagation();socket.emit('reveal_card',{room:roomCode,index:i})}function showGuesses(i,e){if(e)e.stopPropagation();socket.emit('show_guesses',{room:roomCode,index:i})}function sendClue(){let c=clueText.value.trim(),n=clueNumber.value;if(!c){alert('İpucu yaz.');return}socket.emit('send_clue',{room:roomCode,clue:c,number:n,name:myName})}function endTurn(){socket.emit('end_turn',{room:roomCode})}function setCategory(c){socket.emit('set_category',{room:roomCode,category:c});closeModals()}function buyVirtualChips(a){if(!myName){alert('Önce profil oluştur.');return}socket.emit('buy_virtual_chips',{room:roomCode,amount:a});closeModals()}function placeBet(){let a=parseInt(betAmount.value);if(!a||a<=0){alert('Geçerli jeton miktarı yaz.');return}socket.emit('place_bet',{room:roomCode,team:betTeam.value,amount:a})}function toggleTeamLock(t){socket.emit('toggle_lock',{room:roomCode,team:t})}function adminNewGame(){socket.emit('admin_new_game',{room:roomCode})}function adminRevealAll(){socket.emit('admin_reveal_all',{room:roomCode})}function adminResetStats(){socket.emit('admin_reset_stats',{room:roomCode})}function kickPlayer(s){socket.emit('kick_player',{room:roomCode,sid:s})}function makeSpectator(s){socket.emit('admin_move_player',{room:roomCode,sid:s,team:'spectator',role:'spectator'})}function movePlayer(s,t){socket.emit('admin_move_player',{room:roomCode,sid:s,team:t,role:'player'})}function makeAdmin(s){socket.emit('make_admin',{room:roomCode,sid:s})}function sendMessage(){let m=chatInput.value.trim();if(!m)return;socket.emit('chat',{room:roomCode,name:myName||'Oyuncu',msg:m});chatInput.value=''}function canSeeRole(){return myRole==='blueSpy'||myRole==='redSpy'||myRole==='spectator'}
function renderPlayers(players,locks){blueLobby.innerHTML=redLobby.innerHTML=spectatorLobby.innerHTML=bluePlayers.innerHTML=redPlayers.innerHTML=onlinePlayers.innerHTML=spectatorList.innerHTML='';blueSeatBox.classList.toggle('lockedSeat',locks.blue);redSeatBox.classList.toggle('lockedSeat',locks.red);blueLockText.innerHTML=locks.blue?'🔒':'';redLockText.innerHTML=locks.red?'🔒':'';let ba=[],ra=[],bs=[],rs=[],sp=[];players.forEach(p=>{let crown=p.isAdmin?' 👑':'',av=`<img src="/static/${p.avatar}" class="${avatarClass(p.avatar)}">`,chips=p.chips||1000;if(p.team==='blue'){blueLobby.innerHTML+=`<div>${av}<br>${p.name}${crown}</div>`;bluePlayers.innerHTML+=`${av} ${p.name}${crown} — ${roleLabel(p.role)} — 🪙 ${chips}<br>`}else if(p.team==='red'){redLobby.innerHTML+=`<div>${av}<br>${p.name}${crown}</div>`;redPlayers.innerHTML+=`${av} ${p.name}${crown} — ${roleLabel(p.role)} — 🪙 ${chips}<br>`}else{spectatorLobby.innerHTML+=`<div>${av}<br>${p.name}${crown}</div>`;sp.push(`${p.name} 🪙 ${chips}`)}if(p.role==='blueSpy')bs.push(p.name);else if(p.role==='redSpy')rs.push(p.name);else if(p.team==='blue')ba.push(p.name);else if(p.team==='red')ra.push(p.name);let adm='';if(isAdmin&&p.sid!==mySid){adm=`<div class="adminActions"><button onclick="makeAdmin('${p.sid}')">👑 Admin Yap</button><button onclick="movePlayer('${p.sid}','blue')">🔵 Maviye Al</button><button onclick="movePlayer('${p.sid}','red')">🔴 Kırmızıya Al</button><button onclick="makeSpectator('${p.sid}')">👀 Seyirci</button><button onclick="kickPlayer('${p.sid}')">🚫 At</button></div>`}onlinePlayers.innerHTML+=`<div class="profileCard">${av} <b>${p.name}</b>${crown}<br>${teamLabel(p.team)}<br>${roleLabel(p.role)}<br>🪙 ${chips}${adm}</div>`});spectatorList.innerHTML=sp.length?sp.join('<br>'):'-';bluePlayers.innerHTML+=`<hr>🕵️ Mavi Spymaster: ${bs.join(', ')||'-'}<br>👤 Mavi Saha Ajanı: ${ba.join(', ')||'-'}`;redPlayers.innerHTML+=`<hr>🕵️ Kırmızı Spymaster: ${rs.join(', ')||'-'}<br>👤 Kırmızı Saha Ajanı: ${ra.join(', ')||'-'}`}
function renderStats(st){scoreText.innerHTML='🏆 Mavi: '+st.blueWins+' | Kırmızı: '+st.redWins;let h=st.history.length?st.history.slice(-8).reverse().map(w=>'🏆 '+w).join('<br>'):'Henüz kazanan yok.';if(st.betHistory&&st.betHistory.length)h+='<hr><b>🎰 Bahis Kaydı</b><br>'+st.betHistory.slice(-8).reverse().join('<br>');if(st.wordHistory&&st.wordHistory.length){h+='<hr><b>📝 Oyun Kaydı / Kelimeler</b><br>';st.wordHistory.slice(-5).reverse().forEach(g=>{h+=`<br><b>Parti ${g.gameNo}</b> — ${g.winner}<br><small>${g.words.join(', ')}</small><br>`})}historyPanel.innerHTML=h}function renderBets(b){let l=Object.values(b||{});betInfo.innerHTML=l.length?l.map(x=>`🎰 ${x.name}: ${x.amount} 🪙 → ${x.team==='blue'?'Mavi':'Kırmızı'}`).join('<br>'):'Henüz bahis yok.'}
function renderGame(g){board.innerHTML='';blueCount.innerHTML=g.blueCount;redCount.innerHTML=g.redCount;phaseText.innerHTML=g.phase+((g.guessLimit&&g.guessLimit>0)?'<br>🎯 Tahmin hakkı: '+g.guessesMade+' / '+g.guessLimit:'');clueDisplay.innerHTML=g.clue;turnDisplay.innerHTML=g.turn==='blue'?'🔵 Sıra Mavi Takımda':'🔴 Sıra Kırmızı Takımda';clueLog.innerHTML=(g.clueLog&&g.clueLog.length)?'📜 Oyun bandı:<br>'+g.clueLog.slice(-8).reverse().join('<br>'):'📜 Oyun bandı: Henüz ipucu yok.';if(g.moveLog&&g.moveLog.length)clueLog.innerHTML+='<hr>🃏 Kart kaydı:<br>'+g.moveLog.slice(-8).reverse().join('<br>');g.cards.forEach((c,i)=>{let cls='card';if(c.guessed)cls+=' guessed';if(c.open||canSeeRole()||g.winner)cls+=' open '+c.role+'Card';let names=(c.guessedBy||[]).join(', '),gb=names?`<div class='guessName'>🎯 ${names}</div>`:'';board.innerHTML+=`<div class="${cls}" onclick="toggleGuess(${i})"><button class="revealBtn" onclick="revealCard(${i}, event)">A♠</button><button class="guessBtn" onclick="showGuesses(${i}, event)">Tahmin</button>${c.word}${gb}</div>`});if(g.winner)showWinner(g.winner)}function showWinner(t){winnerText.innerHTML=t;winnerOverlay.style.display='flex';setTimeout(()=>winnerOverlay.style.display='none',5000)}function updateTimerDisplay(){let m=Math.floor(seconds/60),s=seconds%60;timer.innerHTML=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')}function startTimer(){if(timerRunning)return;timerRunning=true;timerInterval=setInterval(()=>{if(seconds>0){seconds--;updateTimerDisplay()}},1000)}function pauseTimer(){timerRunning=false;clearInterval(timerInterval)}function setTimer(v){pauseTimer();seconds=v;updateTimerDisplay()}
socket.on('connect',()=>{mySid=socket.id;restoreLocalFields()});socket.on('room_created',d=>{roomCode=d.room;isAdmin=true;roomText.innerHTML='Oda: '+roomCode+' 👑 Admin sensin';saveLocalProfile()});socket.on('room_joined',d=>{roomCode=d.room;isAdmin=false;roomText.innerHTML='Oda: '+roomCode;saveLocalProfile()});socket.on('error_msg',d=>alert(d.msg));socket.on('players_update',d=>renderPlayers(d.players,d.locks));socket.on('game_update',d=>{let me=d.players.find(p=>p.sid===mySid||p.name===myName);if(me){myName=me.name;myTeam=me.team;myRole=me.role;isAdmin=me.isAdmin;currentChips=me.chips||1000;setSavedChips(myName,currentChips);saveLocalProfile()}lobby.classList.add('hidden');gameScreen.classList.remove('hidden');roleText.innerHTML='Bu cihazda: '+myName+' · Rol: '+roleLabel(myRole);chipsText.innerHTML='🪙 Jeton: '+currentChips;betChips.innerHTML=currentChips;shopChips.innerHTML=currentChips;renderPlayers(d.players,d.locks);renderStats(d.stats);renderBets(d.bets);renderGame(d.game)});socket.on('chat_update',d=>{messages.innerHTML+='<b>'+d.name+':</b> '+d.msg+'<br>'});socket.on('kicked',()=>{alert('Odadan çıkarıldın.');localStorage.clear();location.reload()});socket.on('made_spectator',()=>{myRole='spectator';myTeam='spectator';saveLocalProfile();alert('Seyirci moduna alındın.')});socket.on('guess_names',d=>{alert('Bu kartı tahmin edenler: '+((d.names&&d.names.length)?d.names.join(', '):'Henüz tahmin yok.'))});updateTimerDisplay();
</script></body></html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@socketio.on('create_room')
def create_room(data):
    code = room_code(); password = data.get('password','')
    rooms[code] = {'players': [], 'game': new_game('default'), 'stats': {'blueWins':0,'redWins':0,'history':[],'wordHistory':[],'betHistory':[],'gameNo':0}, 'locks': {'blue':False,'red':False}, 'password': password, 'adminSid': request.sid, 'bets': {}, 'category': 'default'}
    join_room(code); emit('room_created', {'room': code})

@socketio.on('join_room_code')
def join_room_code(data):
    code = data['room']; password = data.get('password','')
    if code not in rooms: emit('error_msg', {'msg':'Oda bulunamadı.'}); return
    if rooms[code]['password'] and rooms[code]['password'] != password: emit('error_msg', {'msg':'Oda şifresi yanlış.'}); return
    join_room(code); emit('room_joined', {'room': code}); emit('players_update', {'players': rooms[code]['players'], 'locks': rooms[code]['locks']})

@socketio.on('sit')
def sit(data):
    code = data['room']
    if code not in rooms: return
    old = by_name(code, data['name'])
    if len(rooms[code]['players']) >= MAX_PLAYERS and not old: emit('error_msg', {'msg':'Oda dolu. En fazla 10 oyuncu girebilir.'}); return
    if data['team'] in ['blue','red'] and rooms[code]['locks'][data['team']]: emit('error_msg', {'msg':'Bu takım kilitli.'}); return
    chips = int(data.get('chips', 1000))
    if old:
        old.update({'sid':request.sid,'team':data['team'],'role':data['role'],'avatar':data['avatar'],'chips':chips})
    else:
        rooms[code]['players'].append({'sid':request.sid,'name':data['name'],'avatar':data['avatar'],'team':data['team'],'role':data['role'],'chips':chips,'isAdmin':rooms[code]['adminSid']==request.sid})
    join_room(code); emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks']}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('start_game')
def start_game(data):
    if data['room'] in rooms: emit('game_update', pdata(data['room']), to=data['room'])

@socketio.on('new_game')
def new_game_event(data):
    code = data['room']
    if code in rooms:
        rooms[code]['game'] = new_game(rooms[code].get('category','default')); rooms[code]['bets'] = {}; emit('game_update', pdata(code), to=code)

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
    emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks']}, to=code); emit('game_update', pdata(code), to=code)

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

@socketio.on('buy_virtual_chips')
def buy_virtual_chips(data):
    code=data['room']; amount=int(data.get('amount',0))
    if code not in rooms: return
    p=by_sid(code, request.sid)
    if not p: return
    p['chips']=int(p.get('chips',1000))+amount; emit('game_update', pdata(code), to=code)

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
    p['chips'] -= amount; rooms[code]['bets'][request.sid]={'name':p['name'],'team':team,'amount':amount}
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
    rooms[code]['locks'][team]=not rooms[code]['locks'][team]; emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks']}, to=code)

@socketio.on('admin_move_player')
def admin_move_player(data):
    code=data['room']
    if code not in rooms or not is_admin(code): return
    p=by_sid(code, data['sid'])
    if p:
        p['team']=data['team']; p['role']='spectator' if data['team']=='spectator' else data['role']
        if data['team']=='spectator': emit('made_spectator', to=data['sid'])
    emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks']}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('make_admin')
def make_admin(data):
    code=data['room']
    if code not in rooms or not is_admin(code): return
    p=by_sid(code, data['sid'])
    if p: p['isAdmin']=True
    emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks']}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('kick_player')
def kick_player(data):
    code=data['room']; sid=data['sid']
    if code not in rooms or not is_admin(code): return
    rooms[code]['players']=[p for p in rooms[code]['players'] if p['sid']!=sid]
    if sid in rooms[code]['bets']: del rooms[code]['bets'][sid]
    emit('kicked', to=sid); emit('players_update', {'players':rooms[code]['players'],'locks':rooms[code]['locks']}, to=code); emit('game_update', pdata(code), to=code)

@socketio.on('chat')
def chat(data):
    code=data['room']
    if code in rooms: emit('chat_update', {'name':data['name'],'msg':data['msg']}, to=code)

if __name__ == '__main__':
    port=int(os.environ.get('PORT',5000)); socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
