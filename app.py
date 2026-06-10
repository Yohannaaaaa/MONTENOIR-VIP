from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import random
import string
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "codenamesvip"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

rooms = {}
MAX_PLAYERS = 10


def kelimeleri_yukle():
    try:
        with open("CodeNames8.txt", "r", encoding="utf-8-sig") as dosya:
            kelimeler = [s.strip() for s in dosya if s.strip()]
            kelimeler = list(dict.fromkeys(kelimeler))
            if len(kelimeler) >= 25:
                print("Kelime sayısı:", len(kelimeler))
                return kelimeler
    except Exception as e:
        print("Kelime dosyası okunamadı:", e)

    return [
        "ASLAN","KEDİ","UZAY","AY","ROBOT","ORMAN","DENİZ","KALE","ELMAS","TAVŞAN",
        "KORSAN","PİRAMİT","DRAGON","YILDIZ","GEZEGEN","ARABA","TELEFON","MÜZİK",
        "KÖPEK","BALIK","KRAL","GÜNEŞ","KALEM","OKYANUS","MAYMUN"
    ]


def oda_kodu():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))


def yeni_oyun():
    kelimeler = random.sample(kelimeleri_yukle(), 25)
    roller = ["blue"] * 9 + ["red"] * 8 + ["neutral"] * 7 + ["assassin"]
    random.shuffle(roller)

    return {
        "cards": [
            {
                "word": kelimeler[i],
                "role": roller[i],
                "open": False,
                "guessed": False,
                "guessedBy": "",
                "guessedTeam": ""
            }
            for i in range(25)
        ],
        "blueCount": 9,
        "redCount": 8,
        "turn": "blue",
        "winner": "",
        "phase": "🧠 Mavi takımın Spymaster'ı ipucu düşünüyor...",
        "clue": "İpucu: -",
        "clueLog": []
    }


def public_room_data(code):
    return {
        "players": rooms[code]["players"],
        "game": rooms[code]["game"],
        "stats": rooms[code]["stats"],
        "locks": rooms[code]["locks"],
        "room": code
    }


def find_player_by_sid(code, sid):
    for p in rooms[code]["players"]:
        if p["sid"] == sid:
            return p
    return None


def find_player_by_name(code, name):
    for p in rooms[code]["players"]:
        if p["name"].lower() == name.lower():
            return p
    return None


def is_admin_room(code):
    if code not in rooms:
        return False

    player = find_player_by_sid(code, request.sid)

    if player and player.get("isAdmin", False):
        return True

    return rooms[code]["adminSid"] == request.sid


def switch_turn(game):
    if game["turn"] == "blue":
        game["turn"] = "red"
        game["phase"] = "🧠 Kırmızı takımın Spymaster'ı ipucu düşünüyor..."
    else:
        game["turn"] = "blue"
        game["phase"] = "🧠 Mavi takımın Spymaster'ı ipucu düşünüyor..."


def update_stats_for_winner(code, winner_text):
    stats = rooms[code]["stats"]

    if "MAVİ" in winner_text:
        stats["blueWins"] += 1
        stats["history"].append("Mavi Takım")
    elif "KIRMIZI" in winner_text:
        stats["redWins"] += 1
        stats["history"].append("Kırmızı Takım")


def save_game_history(code, winner_text):
    game = rooms[code]["game"]
    stats = rooms[code]["stats"]

    stats["gameNo"] += 1

    words = [c["word"] + "(" + c["role"] + ")" for c in game["cards"]]

    stats["wordHistory"].append({
        "gameNo": stats["gameNo"],
        "winner": winner_text,
        "words": words
    })


def player_can_give_clue(player, game):
    if not player:
        return False

    if game["turn"] == "blue" and player["role"] == "blueSpy":
        return True

    if game["turn"] == "red" and player["role"] == "redSpy":
        return True

    return False


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CODENAMES VIP</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
body{
    margin:0;
    background:radial-gradient(circle at top,#241633,#050505 70%);
    color:white;
    font-family:Arial,sans-serif;
    text-align:center;
}

h1{
    color:#f5d77b;
    text-shadow:0 0 10px #d4af37,0 0 20px #d4af37,0 0 45px #d4af37;
    letter-spacing:4px;
    font-size:52px;
    margin-top:25px;
    margin-bottom:5px;
    font-weight:900;
}

.subtitle{
    color:#d4af37;
    letter-spacing:3px;
    margin-bottom:18px;
}

button{
    background:linear-gradient(135deg,#111,#333);
    color:#f5d77b;
    border:1px solid #d4af37;
    border-radius:14px;
    padding:8px 10px;
    margin:4px;
    font-weight:bold;
    cursor:pointer;
    font-size:13px;
}

button:hover{
    box-shadow:0 0 15px #d4af37;
    transform:scale(1.03);
}

input,select{
    padding:10px;
    border-radius:10px;
    border:1px solid #d4af37;
    background:#111;
    color:white;
    margin:4px;
}

.panel{
    margin:15px auto;
    padding:15px;
    max-width:1050px;
    border:1px solid rgba(212,175,55,.45);
    border-radius:22px;
    background:rgba(255,255,255,.06);
}

.hidden{
    display:none;
}

.topLeftFixed{
    position:fixed;
    top:15px;
    left:15px;
    z-index:999999;
    display:flex;
    gap:8px;
}

.topRightFixed{
    position:fixed;
    top:15px;
    right:15px;
    z-index:999999;
    display:flex;
    align-items:center;
    gap:8px;
    border:2px solid #d4af37;
    border-radius:20px;
    padding:8px 12px;
    background:rgba(0,0,0,.65);
}

.micStatus{
    color:#ffd700;
    font-weight:bold;
}

.tableSeat{
    display:inline-block;
    width:260px;
    min-height:140px;
    margin:10px;
    padding:12px;
    border-radius:22px;
    border:2px solid #d4af37;
    background:radial-gradient(circle at center,#0f6b3a,#06351f);
    box-shadow:0 0 20px #00ff99, inset 0 0 25px #001f12;
    vertical-align:top;
}

.lockedSeat{
    opacity:.45;
    filter:grayscale(40%);
}

.avatarImg{
    width:42px;
    height:42px;
    border-radius:50%;
    object-fit:cover;
    border:3px solid #d4af37;
    box-shadow:0 0 10px #d4af37;
}

.femaleFrame{
    border:3px solid #ff4fd8!important;
    box-shadow:0 0 15px #ff4fd8!important;
}

.maleFrame{
    border:3px solid #111!important;
    box-shadow:0 0 15px #000!important;
}

.mainLayout{
    display:grid;
    grid-template-columns:1fr 330px;
    gap:15px;
    max-width:1320px;
    margin:0 auto;
}
.sidePanel{
    margin:15px;
    padding:12px;
    border-radius:22px;
    border:2px solid #d4af37;
    background:linear-gradient(180deg,rgba(18,12,30,.95),rgba(0,0,0,.92));
    box-shadow:0 0 25px rgba(212,175,55,.5);
    min-height:400px;
}

.profileCard{
    margin:6px 0;
    padding:8px;
    border-radius:12px;
    border:1px solid #d4af37;
    background:linear-gradient(135deg,rgba(60,40,90,.85),rgba(15,10,25,.95));
    text-align:left;
    font-size:12px;
}

.profileCard b{
    font-size:15px;
    color:white;
}

.adminBadge{
    color:#ffd700;
    text-shadow:0 0 10px #d4af37;
    font-weight:bold;
}

.adminActions button{
    font-size:11px;
    padding:5px 7px;
}

.teams{
    display:flex;
    justify-content:center;
    gap:15px;
    margin:15px;
    flex-wrap:wrap;
}

.team{
    padding:15px;
    width:280px;
    border-radius:18px;
    font-weight:bold;
}

.blueTeam{
    background:linear-gradient(135deg,#0055ff,#00d4ff);
}

.redTeam{
    background:linear-gradient(135deg,#ff1f1f,#ff7a00);
}

.teamCount{
    display:block;
    margin-top:8px;
    font-size:20px;
    color:white;
}

.scoreBox{
    font-size:20px;
    color:#ffd700;
    text-shadow:0 0 10px #d4af37;
}

.playerList{
    margin-top:8px;
    font-size:13px;
    text-align:left;
}

.statusBox{
    font-size:21px;
    color:#ffd700;
    text-shadow:0 0 15px #d4af37;
}

.board{
    display:grid;
    grid-template-columns:repeat(5,1fr);
    gap:12px;
    max-width:900px;
    margin:20px auto;
    padding:10px;
    perspective:1200px;
}
.card{
    background:
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

    border:4px double #d4af37;

    box-shadow:
        0 0 18px rgba(212,175,55,.9),
        inset 0 0 28px rgba(212,175,55,.25);

    transition:.35s;
    position:relative;
    overflow:hidden;
    transform-style:preserve-3d;
}

.card::after{
    content:"♠ ♦ ♣ ♥";
    position:absolute;
    top:8px;
    right:10px;
    color:#d4af37;
    font-size:12px;
    text-shadow:0 0 10px #d4af37;
}

.card:hover{
    transform:translateY(-8px) rotateX(14deg) scale(1.06);
    box-shadow:
        0 0 25px #ffd700,
        0 0 55px rgba(212,175,55,.8);
}

.card.guessed{
    outline:5px solid #00ff99!important;
    box-shadow:
        0 0 25px #00ff99,
        0 0 50px rgba(0,255,153,.8)!important;
}

.guessName{
    position:absolute;
    bottom:5px;
    left:8px;
    right:8px;

    font-size:11px;
    color:#003300;

    background:rgba(0,255,153,.75);

    border-radius:8px;
    padding:2px;
}

.revealBtn{
    position:absolute;
    top:5px;
    left:7px;

    background:linear-gradient(145deg,#000,#2b2108,#000);

    color:#ffd700;

    border:2px solid #d4af37;
    border-radius:12px;

    padding:4px 8px;

    font-size:15px;
    font-weight:900;

    z-index:5;

    box-shadow:0 0 14px #d4af37;
}

.card.open{
    animation:cardFlip .7s ease;
}

@keyframes cardFlip{
    0%{
        transform:perspective(1000px) rotateY(0deg) scale(1);
    }

    50%{
        transform:perspective(1000px) rotateY(180deg) scale(1.15);
    }

    100%{
        transform:perspective(1000px) rotateY(360deg) scale(1.06);
    }
}

.blueCard{
    background:linear-gradient(
        145deg,
        #001a66,
        #0066ff,
        #00eaff
    )!important;

    color:white!important;
}

.redCard{
    background:linear-gradient(
        145deg,
        #6b0000,
        #ff1f1f,
        #ff9a00
    )!important;

    color:white!important;
}
.neutralCard{
    background:linear-gradient(
        145deg,
        #777,
        #e5e5e5,
        #ffffff
    )!important;

    color:black!important;
}

.assassinCard{
    background:linear-gradient(
        145deg,
        #000,
        #141414,
        #3a0000
    )!important;

    color:white!important;
}

#winnerOverlay{
    position:fixed;
    top:0;
    left:0;

    width:100%;
    height:100%;

    background:rgba(0,0,0,.88);

    display:none;
    justify-content:center;
    align-items:center;

    z-index:9999;
}

#winnerText{
    font-size:72px;
    font-weight:900;

    color:#ffd700;

    text-shadow:
        0 0 20px #d4af37,
        0 0 50px #d4af37;
}

#messages{
    height:100px;
    overflow-y:auto;

    text-align:left;

    padding:10px;

    background:#080808;

    border-radius:10px;
    margin-bottom:8px;
}

#historyPanel{
    font-size:18px;
    color:white;
    text-shadow:0 0 10px white;
}

#clueLog{
    margin-top:10px;
    color:#ffd700;
    font-weight:bold;
    line-height:1.5;
}

@media(max-width:800px){

    h1{
        font-size:30px;
    }

    .mainLayout{
        display:block;
    }

    .card{
        min-height:60px;
        font-size:11px;
    }

    #winnerText{
        font-size:38px;
    }
}

</style>
</head>

<body>

<div class="topLeftFixed">
    <button onclick="startTimer()">⏱ Süre</button>
    <button onclick="newGame()">🎲 Yeni Oyun</button>
    <button onclick="goLobby()">🚪 Lobi</button>
</div>

<div class="topRightFixed">
    <button onclick="startMic()">🎙 Aç</button>
    <button onclick="stopMic()">🔇 Kapat</button>
    <span id="micStatus" class="micStatus">Kapalı</span>
</div>

<div id="winnerOverlay">
    <div id="winnerText"></div>
</div>

<h1>♠️ CODENAMES VIP ♦️</h1>

<p class="subtitle">
Luxury Online Multiplayer Edition
</p>
<div id="lobby" class="panel">
    <h2>🎰 Oda Sistemi</h2>

    <button onclick="createRoom()">Oda Oluştur</button>
    <br>

    <input id="roomInput" placeholder="Oda kodu">
    <input id="roomPassword" placeholder="Oda şifresi">
    <button onclick="joinExistingRoom()">Odaya Katıl</button>

    <h3 id="roomText">Oda: -</h3>

    <hr>

    <h3>Profil Oluştur / Masaya Otur</h3>

    <input id="playerName" placeholder="Oyuncu adı">

    <select id="avatarChoice">
        <option value="woman.png">Kadın</option>
        <option value="man.png">Erkek</option>
    </select>

    <select id="teamChoice">
        <option value="blue">🔵 Mavi Masa</option>
        <option value="red">🔴 Kırmızı Masa</option>
        <option value="spectator">👀 Seyirci</option>
    </select>

    <select id="roleChoice">
        <option value="player">Saha Ajanı</option>
        <option value="blueSpy">Mavi Spymaster</option>
        <option value="redSpy">Kırmızı Spymaster</option>
        <option value="spectator">Seyirci</option>
    </select>

    <br>

    <button onclick="sitAtTable()">Masaya Otur</button>
    <button onclick="startGame()">Oyunu Başlat</button>

    <div>
        <div class="tableSeat" id="blueSeatBox">
            <div>🔵 MAVİ MASA <span id="blueLockText"></span></div>
            <div id="blueLobby"></div>
        </div>

        <div class="tableSeat" id="redSeatBox">
            <div>🔴 KIRMIZI MASA <span id="redLockText"></span></div>
            <div id="redLobby"></div>
        </div>

        <div class="tableSeat" id="spectatorSeatBox">
            <div>👀 SEYİRCİLER</div>
            <div id="spectatorLobby"></div>
        </div>
    </div>
</div>

<div id="gameScreen" class="hidden">
    <div class="mainLayout">
        <div>

            <div class="panel">
                <button onclick="startTimer()">▶ Süre Başlat</button>
                <button onclick="pauseTimer()">⏸ Durdur</button>
                <button onclick="setTimer(60)">1 dk</button>
                <button onclick="setTimer(180)">3 dk</button>
                <button onclick="setTimer(300)">5 dk</button>
                <button onclick="setTimer(600)">10 dk</button>
                <br>
                ⏱ <span id="timer">05:00</span>
            </div>

            <div class="panel">
                <p id="roleText">Rol: -</p>
                <p id="phaseText" class="statusBox">🎰 Oyun bekliyor...</p>
                <p id="scoreText" class="scoreBox">🏆 Mavi: 0 | Kırmızı: 0</p>
            </div>

            <div class="teams">
                <div class="team blueTeam">
                    🔵 MAVİ TAKIM
                    <span class="teamCount">Kalan kelime: <span id="blueCount">9</span></span>
                    <div id="bluePlayers" class="playerList"></div>
                </div>

                <div class="team redTeam">
                    🔴 KIRMIZI TAKIM
                    <span class="teamCount">Kalan kelime: <span id="redCount">8</span></span>
                    <div id="redPlayers" class="playerList"></div>
                </div>
            </div>

            <div class="panel">
                <input id="clueText" placeholder="İpucu yaz">

                <select id="clueNumber">
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                    <option value="5">5</option>
                    <option value="6">6</option>
                    <option value="7">7</option>
                    <option value="8">8</option>
                    <option value="9">9</option>
                    <option value="∞">♾️</option>
                </select>

                <button onclick="sendClue()">İpucu Ver</button>
                <button onclick="endTurn()" style="background:#008f4c;color:white;">✅ Sırayı Bitir</button>

                <h2 id="clueDisplay">İpucu: -</h2>
                <div id="clueLog">📜 Oyun bandı: Henüz ipucu yok.</div>
                <h2 id="turnDisplay">Sıra: Belirlenmedi</h2>
            </div>

            <div class="board" id="board"></div>

            <div class="panel">
                <h3>💬 Chat</h3>
                <div id="messages"></div>
                <input id="chatInput" placeholder="Mesaj yaz">
                <button onclick="sendMessage()">Gönder</button>
            </div>

        </div>

        <div class="sidePanel">
            <h3>👥 Bağlanan Oyuncular</h3>
            <div id="onlinePlayers"></div>

            <hr>

            <h3>🔁 Join Team</h3>
            <button onclick="joinTeam('blue','player')">🔵 Mavi Saha Ajanı</button>
            <button onclick="joinTeam('blue','blueSpy')">🕵️ Mavi Spymaster</button>
            <button onclick="joinTeam('red','player')">🔴 Kırmızı Saha Ajanı</button>
            <button onclick="joinTeam('red','redSpy')">🕵️ Kırmızı Spymaster</button>
            <button onclick="joinTeam('spectator','spectator')">👀 Seyirci</button>

            <hr>

            <h3>👑 Admin Paneli</h3>
            <div id="adminPanel">
                <button onclick="toggleTeamLock('blue')">🔒 Mavi Kilitle</button>
                <button onclick="toggleTeamLock('red')">🔒 Kırmızı Kilitle</button>
                <button onclick="adminNewGame()">🎲 Yeni Oyun</button>
                <button onclick="adminRevealAll()">🃏 Kartları Aç</button>
                <button onclick="adminResetStats()">🏆 Skoru Sıfırla</button>
            </div>

            <hr>

            <h3>🏆 Kazananlar / Oyun Kaydı</h3>
            <div id="historyPanel"></div>
        </div>
    </div>
</div>

<script>
const socket = io();

let roomCode = "";
let myName = "";
let myRole = "";
let myTeam = "";
let mySid = "";
let joined = false;
let isAdmin = false;

let seconds = 300;
let timerRunning = false;
let timerInterval = null;
let micStream = null;
function saveLocalProfile(){
    localStorage.setItem("codenamesRoom", roomCode);
    localStorage.setItem("codenamesName", myName);
    localStorage.setItem("codenamesRole", myRole);
    localStorage.setItem("codenamesTeam", myTeam);
}

function restoreLocalFields(){
    const savedRoom = localStorage.getItem("codenamesRoom") || "";
    const savedName = localStorage.getItem("codenamesName") || "";
    const savedRole = localStorage.getItem("codenamesRole") || "";
    const savedTeam = localStorage.getItem("codenamesTeam") || "";

    if(savedRoom !== "") document.getElementById("roomInput").value = savedRoom;
    if(savedName !== "") document.getElementById("playerName").value = savedName;
    if(savedRole !== "") document.getElementById("roleChoice").value = savedRole;
    if(savedTeam !== "") document.getElementById("teamChoice").value = savedTeam;
}

function avatarClass(file){
    return file === "woman.png" ? "avatarImg femaleFrame" : "avatarImg maleFrame";
}

function roleLabel(role){
    if(role === "player") return "Saha Ajanı";
    if(role === "blueSpy") return "Mavi Spymaster";
    if(role === "redSpy") return "Kırmızı Spymaster";
    if(role === "spectator") return "Seyirci";
    return role;
}

function teamLabel(team){
    if(team === "blue") return "🔵 Mavi";
    if(team === "red") return "🔴 Kırmızı";
    return "👀 Seyirci";
}

async function startMic(){
    try{
        micStream = await navigator.mediaDevices.getUserMedia({audio:true});
        document.getElementById("micStatus").innerHTML = "Açık";
    }catch(e){
        alert("Mikrofon izni verilmedi.");
    }
}

function stopMic(){
    if(micStream){
        micStream.getTracks().forEach(track => track.stop());
        micStream = null;
    }
    document.getElementById("micStatus").innerHTML = "Kapalı";
}

function createRoom(){
    const password = document.getElementById("roomPassword").value.trim();
    socket.emit("create_room", {password: password});
}

function joinExistingRoom(){
    const code = document.getElementById("roomInput").value.trim().toUpperCase();
    const password = document.getElementById("roomPassword").value.trim();

    if(code === ""){
        alert("Oda kodu yaz.");
        return;
    }

    socket.emit("join_room_code", {room: code, password: password});
}

function sitAtTable(){
    if(roomCode === ""){
        alert("Önce oda oluştur veya odaya katıl.");
        return;
    }

    const name = document.getElementById("playerName").value.trim();
    const avatar = document.getElementById("avatarChoice").value;
    const team = document.getElementById("teamChoice").value;
    const role = document.getElementById("roleChoice").value;

    if(name === ""){
        alert("Oyuncu adı yaz.");
        return;
    }

    myName = name;
    myRole = role;
    myTeam = team;
    joined = true;
    saveLocalProfile();

    socket.emit("sit", {
        room: roomCode,
        name: name,
        avatar: avatar,
        team: team,
        role: role
    });
}

function startGame(){
    if(!joined){
        alert("Önce masaya otur.");
        return;
    }
    socket.emit("start_game", {room: roomCode});
}

function newGame(){
    socket.emit("new_game", {room: roomCode});
}

function goLobby(){
    document.getElementById("gameScreen").classList.add("hidden");
    document.getElementById("lobby").classList.remove("hidden");
}

function joinTeam(team, role){
    myTeam = team;
    myRole = role;
    saveLocalProfile();

    socket.emit("join_team", {
        room: roomCode,
        team: team,
        role: role
    });
}

function toggleGuess(index){
    socket.emit("toggle_guess", {
        room: roomCode,
        index: index
    });
}

function revealCard(index, event){
    if(event) event.stopPropagation();

    socket.emit("reveal_card", {
        room: roomCode,
        index: index
    });
}

function sendClue(){
    const clue = document.getElementById("clueText").value.trim();
    const number = document.getElementById("clueNumber").value;

    if(clue === ""){
        alert("İpucu yaz.");
        return;
    }

    socket.emit("send_clue", {
        room: roomCode,
        clue: clue,
        number: number,
        name: myName
    });
}

function endTurn(){
    socket.emit("end_turn", {room: roomCode});
}

function toggleTeamLock(team){
    socket.emit("toggle_lock", {room: roomCode, team: team});
}

function adminNewGame(){
    socket.emit("admin_new_game", {room: roomCode});
}

function adminRevealAll(){
    socket.emit("admin_reveal_all", {room: roomCode});
}

function adminResetStats(){
    socket.emit("admin_reset_stats", {room: roomCode});
}

function kickPlayer(sid){
    socket.emit("kick_player", {room: roomCode, sid: sid});
}

function makeSpectator(sid){
    socket.emit("admin_move_player", {
        room: roomCode,
        sid: sid,
        team: "spectator",
        role: "spectator"
    });
}

function movePlayer(sid, team){
    socket.emit("admin_move_player", {
        room: roomCode,
        sid: sid,
        team: team,
        role: "player"
    });
}

function makeAdmin(sid){
    socket.emit("make_admin", {
        room: roomCode,
        sid: sid
    });
}

function sendMessage(){
    const msg = document.getElementById("chatInput").value.trim();

    if(msg === "") return;

    socket.emit("chat", {
        room: roomCode,
        name: myName || "Oyuncu",
        msg: msg
    });

    document.getElementById("chatInput").value = "";
}

function canSeeRole(){
    return myRole === "blueSpy" || myRole === "redSpy" || myRole === "spectator";
}
function renderPlayers(players, locks){
    document.getElementById("blueLobby").innerHTML = "";
    document.getElementById("redLobby").innerHTML = "";
    document.getElementById("spectatorLobby").innerHTML = "";
    document.getElementById("bluePlayers").innerHTML = "";
    document.getElementById("redPlayers").innerHTML = "";
    document.getElementById("onlinePlayers").innerHTML = "";

    document.getElementById("blueSeatBox").classList.toggle("lockedSeat", locks.blue);
    document.getElementById("redSeatBox").classList.toggle("lockedSeat", locks.red);

    document.getElementById("blueLockText").innerHTML = locks.blue ? "🔒" : "";
    document.getElementById("redLockText").innerHTML = locks.red ? "🔒" : "";

    let blueAgents = [];
    let redAgents = [];
    let blueSpies = [];
    let redSpies = [];

    players.forEach(p => {
        const crown = p.isAdmin ? " 👑" : "";
        const avatar = `<img src="/static/${p.avatar}" class="${avatarClass(p.avatar)}">`;

        if(p.team === "blue"){
            document.getElementById("blueLobby").innerHTML += `<div>${avatar}<br>${p.name}${crown}</div>`;
            document.getElementById("bluePlayers").innerHTML += `${avatar} ${p.name}${crown} — ${roleLabel(p.role)}<br>`;
        }

        if(p.team === "red"){
            document.getElementById("redLobby").innerHTML += `<div>${avatar}<br>${p.name}${crown}</div>`;
            document.getElementById("redPlayers").innerHTML += `${avatar} ${p.name}${crown} — ${roleLabel(p.role)}<br>`;
        }

        if(p.team === "spectator"){
            document.getElementById("spectatorLobby").innerHTML += `<div>${avatar}<br>${p.name}${crown}</div>`;
        }

        if(p.role === "blueSpy") blueSpies.push(p.name);
        else if(p.role === "redSpy") redSpies.push(p.name);
        else if(p.team === "blue") blueAgents.push(p.name);
        else if(p.team === "red") redAgents.push(p.name);

        let adminActions = "";

        if(isAdmin && p.sid !== mySid){
            adminActions = `
                <div class="adminActions">
                    <button onclick="makeAdmin('${p.sid}')">👑 Admin Yap</button>
                    <button onclick="movePlayer('${p.sid}','blue')">🔵 Maviye Al</button>
                    <button onclick="movePlayer('${p.sid}','red')">🔴 Kırmızıya Al</button>
                    <button onclick="makeSpectator('${p.sid}')">👀 Seyirci</button>
                    <button onclick="kickPlayer('${p.sid}')">🚫 At</button>
                </div>
            `;
        }

        document.getElementById("onlinePlayers").innerHTML += `
            <div class="profileCard">
                ${avatar}
                <b>${p.name}</b>${crown}
                <br>${teamLabel(p.team)}
                <br>${roleLabel(p.role)}
                ${adminActions}
            </div>
        `;
    });

    document.getElementById("bluePlayers").innerHTML +=
        `<hr>🕵️ Mavi Spymaster: ${blueSpies.join(", ") || "-"}
        <br>👤 Mavi Saha Ajanı: ${blueAgents.join(", ") || "-"}`;

    document.getElementById("redPlayers").innerHTML +=
        `<hr>🕵️ Kırmızı Spymaster: ${redSpies.join(", ") || "-"}
        <br>👤 Kırmızı Saha Ajanı: ${redAgents.join(", ") || "-"}`;
}

function renderStats(stats){
    document.getElementById("scoreText").innerHTML =
        "🏆 Mavi: " + stats.blueWins + " | Kırmızı: " + stats.redWins;

    let html = "";

    if(stats.history.length === 0){
        html = "Henüz kazanan yok.";
    }else{
        stats.history.slice(-8).reverse().forEach(w => {
            html += "🏆 " + w + "<br>";
        });
    }

    if(stats.wordHistory && stats.wordHistory.length > 0){
        html += "<hr><b>📝 Oyun Kaydı / Kelimeler</b><br>";

        stats.wordHistory.slice(-5).reverse().forEach(g => {
            html += "<br><b>Parti " + g.gameNo + "</b> — " + g.winner + "<br>";
            html += "<small>" + g.words.join(", ") + "</small><br>";
        });
    }

    document.getElementById("historyPanel").innerHTML = html;
}

function renderGame(game){
    const board = document.getElementById("board");
    board.innerHTML = "";

    document.getElementById("blueCount").innerHTML = game.blueCount;
    document.getElementById("redCount").innerHTML = game.redCount;
    document.getElementById("phaseText").innerHTML = game.phase;
    document.getElementById("clueDisplay").innerHTML = game.clue;

    document.getElementById("turnDisplay").innerHTML =
        game.turn === "blue" ? "🔵 Sıra Mavi Takımda" : "🔴 Sıra Kırmızı Takımda";

    if(game.clueLog && game.clueLog.length > 0){
        document.getElementById("clueLog").innerHTML =
            "📜 Oyun bandı:<br>" + game.clueLog.slice(-8).reverse().join("<br>");
    }else{
        document.getElementById("clueLog").innerHTML =
            "📜 Oyun bandı: Henüz ipucu yok.";
    }

    game.cards.forEach((card, index) => {
        let cls = "card";

        if(card.guessed){
            cls += " guessed";
        }

        if(card.open || canSeeRole() || game.winner !== ""){
            cls += " open " + card.role + "Card";
        }

        const guessedBy =
            card.guessedBy !== ""
            ? "<div class='guessName'>🎯 " + card.guessedBy + "</div>"
            : "";

        board.innerHTML +=
            "<div class='" + cls + "' onclick='toggleGuess(" + index + ")'>" +
            "<button class='revealBtn' onclick='revealCard(" + index + ", event)'>A♠</button>" +
            card.word +
            guessedBy +
            "</div>";
    });

    if(game.winner !== ""){
        showWinner(game.winner);
    }
}

function showWinner(text){
    document.getElementById("winnerText").innerHTML = text;
    document.getElementById("winnerOverlay").style.display = "flex";

    setTimeout(() => {
        document.getElementById("winnerOverlay").style.display = "none";
    }, 5000);
}

function updateTimerDisplay(){
    let min = Math.floor(seconds / 60);
    let sec = seconds % 60;

    document.getElementById("timer").innerHTML =
        String(min).padStart(2,"0") + ":" + String(sec).padStart(2,"0");
}

function startTimer(){
    if(timerRunning) return;

    timerRunning = true;

    timerInterval = setInterval(() => {
        if(seconds > 0){
            seconds--;
            updateTimerDisplay();
        }
    }, 1000);
}

function pauseTimer(){
    timerRunning = false;
    clearInterval(timerInterval);
}

function setTimer(value){
    pauseTimer();
    seconds = value;
    updateTimerDisplay();
}

socket.on("connect", () => {
    mySid = socket.id;
    restoreLocalFields();
});

socket.on("room_created", data => {
    roomCode = data.room;
    isAdmin = true;

    document.getElementById("roomText").innerHTML =
        "Oda: " + roomCode + " 👑 Admin sensin";

    saveLocalProfile();
});

socket.on("room_joined", data => {
    roomCode = data.room;
    isAdmin = false;

    document.getElementById("roomText").innerHTML =
        "Oda: " + roomCode;

    saveLocalProfile();
});

socket.on("error_msg", data => {
    alert(data.msg);
});

socket.on("players_update", data => {
    renderPlayers(data.players, data.locks);
});

socket.on("game_update", data => {
    const me = data.players.find(p => p.sid === mySid || p.name === myName);

    if(me){
        myName = me.name;
        myTeam = me.team;
        myRole = me.role;
        isAdmin = me.isAdmin;
        saveLocalProfile();
    }

    document.getElementById("lobby").classList.add("hidden");
    document.getElementById("gameScreen").classList.remove("hidden");

    document.getElementById("roleText").innerHTML =
        "Bu cihazda: " + myName + " · Rol: " + roleLabel(myRole);

    renderPlayers(data.players, data.locks);
    renderStats(data.stats);
    renderGame(data.game);
});

socket.on("chat_update", data => {
    document.getElementById("messages").innerHTML +=
        "<b>" + data.name + ":</b> " + data.msg + "<br>";
});

socket.on("kicked", () => {
    alert("Odadan çıkarıldın.");
    localStorage.clear();
    location.reload();
});

socket.on("made_spectator", () => {
    myRole = "spectator";
    myTeam = "spectator";
    saveLocalProfile();
    alert("Seyirci moduna alındın.");
});

updateTimerDisplay();

</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)
@socketio.on("create_room")
def create_room(data):
    code = oda_kodu()
    password = data.get("password", "")

    rooms[code] = {
        "players": [],
        "game": yeni_oyun(),
        "stats": {
            "blueWins": 0,
            "redWins": 0,
            "history": [],
            "wordHistory": [],
            "gameNo": 0
        },
        "locks": {
            "blue": False,
            "red": False
        },
        "password": password,
        "adminSid": request.sid
    }

    join_room(code)
    emit("room_created", {"room": code})


@socketio.on("join_room_code")
def join_room_code(data):
    code = data["room"]
    password = data.get("password", "")

    if code not in rooms:
        emit("error_msg", {"msg": "Oda bulunamadı."})
        return

    if rooms[code]["password"] != "" and rooms[code]["password"] != password:
        emit("error_msg", {"msg": "Oda şifresi yanlış."})
        return

    join_room(code)
    emit("room_joined", {"room": code})
    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]})


@socketio.on("sit")
def sit(data):
    code = data["room"]

    if code not in rooms:
        return

    old = find_player_by_name(code, data["name"])

    if len(rooms[code]["players"]) >= MAX_PLAYERS and not old:
        emit("error_msg", {"msg": "Oda dolu. En fazla 10 oyuncu girebilir."})
        return

    team = data["team"]

    if team in ["blue", "red"] and rooms[code]["locks"][team]:
        emit("error_msg", {"msg": "Bu takım kilitli."})
        return

    if old:
        old["sid"] = request.sid
        old["team"] = data["team"]
        old["role"] = data["role"]
        old["avatar"] = data["avatar"]
    else:
        rooms[code]["players"].append({
            "sid": request.sid,
            "name": data["name"],
            "avatar": data["avatar"],
            "team": data["team"],
            "role": data["role"],
            "isAdmin": rooms[code]["adminSid"] == request.sid
        })

    join_room(code)

    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]}, to=code)
    emit("game_update", public_room_data(code), to=code)


@socketio.on("start_game")
def start_game(data):
    code = data["room"]

    if code in rooms:
        emit("game_update", public_room_data(code), to=code)


@socketio.on("new_game")
def new_game(data):
    code = data["room"]

    if code in rooms:
        rooms[code]["game"] = yeni_oyun()
        emit("game_update", public_room_data(code), to=code)


@socketio.on("join_team")
def join_team(data):
    code = data["room"]
    team = data["team"]
    role = data.get("role", "player")

    if code not in rooms:
        return

    if team in ["blue", "red"] and rooms[code]["locks"][team]:
        emit("error_msg", {"msg": "Bu takım kilitli."})
        return

    player = find_player_by_sid(code, request.sid)

    if not player:
        return

    player["team"] = team
    player["role"] = role

    if team == "spectator":
        player["role"] = "spectator"

    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]}, to=code)
    emit("game_update", public_room_data(code), to=code)


@socketio.on("toggle_guess")
def toggle_guess(data):
    code = data["room"]
    index = data["index"]

    if code not in rooms:
        return

    player = find_player_by_sid(code, request.sid)
    game = rooms[code]["game"]

    if not player:
        return

    if player["team"] == "spectator" or player["role"] == "spectator":
        emit("error_msg", {"msg": "Seyirci tahmin yapamaz."})
        return

    if player["team"] != game["turn"]:
        emit("error_msg", {"msg": "Sıra senin takımında değil."})
        return

    card = game["cards"][index]
    card["guessed"] = not card["guessed"]
    card["guessedBy"] = player["name"] if card["guessed"] else ""
    card["guessedTeam"] = player["team"] if card["guessed"] else ""

    emit("game_update", public_room_data(code), to=code)


@socketio.on("reveal_card")
def reveal_card(data):
    code = data["room"]
    index = data["index"]

    if code not in rooms:
        return

    player = find_player_by_sid(code, request.sid)
    game = rooms[code]["game"]

    if not player:
        return

    if player["team"] == "spectator" or player["role"] == "spectator":
        emit("error_msg", {"msg": "Seyirci kart açamaz."})
        return

    if player["team"] != game["turn"]:
        emit("error_msg", {"msg": "Sıra senin takımında değil."})
        return

    if game["winner"]:
        return

    card = game["cards"][index]

    if card["open"]:
        return

    card["open"] = True
    card["guessed"] = False
    card["guessedBy"] = ""
    card["guessedTeam"] = ""

    current_team = game["turn"]

    if card["role"] == "assassin":
        game["winner"] = "🏆 KIRMIZI TAKIM KAZANDI" if current_team == "blue" else "🏆 MAVİ TAKIM KAZANDI"
        update_stats_for_winner(code, game["winner"])
        save_game_history(code, game["winner"])

        for c in game["cards"]:
            c["open"] = True

    elif card["role"] == "blue":
        game["blueCount"] -= 1

        if current_team == "red":
            switch_turn(game)

        if game["blueCount"] == 0:
            game["winner"] = "🏆 MAVİ TAKIM KAZANDI"
            update_stats_for_winner(code, game["winner"])
            save_game_history(code, game["winner"])

            for c in game["cards"]:
                c["open"] = True

    elif card["role"] == "red":
        game["redCount"] -= 1

        if current_team == "blue":
            switch_turn(game)

        if game["redCount"] == 0:
            game["winner"] = "🏆 KIRMIZI TAKIM KAZANDI"
            update_stats_for_winner(code, game["winner"])
            save_game_history(code, game["winner"])

            for c in game["cards"]:
                c["open"] = True

    elif card["role"] == "neutral":
        switch_turn(game)

    emit("game_update", public_room_data(code), to=code)


@socketio.on("send_clue")
def send_clue(data):
    code = data["room"]
    name = data.get("name", "")

    if code not in rooms:
        return

    game = rooms[code]["game"]
    player = find_player_by_name(code, name)

    if not player_can_give_clue(player, game):
        emit("error_msg", {"msg": "İpucunu sadece sıradaki takımın Spymaster'ı verebilir."})
        return

    game["clue"] = "İpucu: " + data["clue"] + " / " + data["number"]

    if "clueLog" not in game:
        game["clueLog"] = []

    team_name = "Mavi Takım" if game["turn"] == "blue" else "Kırmızı Takım"
    player_name = player["name"]

    game["clueLog"].append(
        team_name + " - " + player_name + ": " + data["clue"] + " " + data["number"]
    )

    if game["turn"] == "blue":
        game["phase"] = "🎯 Mavi takım ajanları tahmin yapıyor..."
    else:
        game["phase"] = "🎯 Kırmızı takım ajanları tahmin yapıyor..."

    emit("game_update", public_room_data(code), to=code)


@socketio.on("end_turn")
def end_turn(data):
    code = data["room"]

    if code not in rooms:
        return

    game = rooms[code]["game"]
    player = find_player_by_sid(code, request.sid)

    if not player:
        emit("error_msg", {"msg": "Oyuncu bulunamadı."})
        return

    if player["team"] == "spectator" or player["role"] == "spectator":
        emit("error_msg", {"msg": "Seyirci sırayı değiştiremez."})
        return

    if player["team"] != game["turn"]:
        emit("error_msg", {"msg": "Sıra senin takımında değil."})
        return

    switch_turn(game)
    emit("game_update", public_room_data(code), to=code)


@socketio.on("admin_new_game")
def admin_new_game(data):
    new_game(data)


@socketio.on("admin_reveal_all")
def admin_reveal_all(data):
    code = data["room"]

    if code not in rooms or not is_admin_room(code):
        return

    for card in rooms[code]["game"]["cards"]:
        card["open"] = True

    emit("game_update", public_room_data(code), to=code)


@socketio.on("admin_reset_stats")
def admin_reset_stats(data):
    code = data["room"]

    if code not in rooms or not is_admin_room(code):
        return

    rooms[code]["stats"] = {
        "blueWins": 0,
        "redWins": 0,
        "history": [],
        "wordHistory": [],
        "gameNo": 0
    }

    emit("game_update", public_room_data(code), to=code)


@socketio.on("toggle_lock")
def toggle_lock(data):
    code = data["room"]
    team = data["team"]

    if code not in rooms or not is_admin_room(code):
        return

    rooms[code]["locks"][team] = not rooms[code]["locks"][team]

    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]}, to=code)


@socketio.on("admin_move_player")
def admin_move_player(data):
    code = data["room"]
    sid = data["sid"]
    team = data["team"]
    role = data["role"]

    if code not in rooms or not is_admin_room(code):
        return

    player = find_player_by_sid(code, sid)

    if player:
        player["team"] = team
        player["role"] = role

        if team == "spectator":
            player["role"] = "spectator"
            emit("made_spectator", to=sid)

    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]}, to=code)
    emit("game_update", public_room_data(code), to=code)


@socketio.on("make_admin")
def make_admin(data):
    code = data["room"]
    sid = data["sid"]

    if code not in rooms or not is_admin_room(code):
        return

    player = find_player_by_sid(code, sid)

    if player:
        player["isAdmin"] = True

    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]}, to=code)
    emit("game_update", public_room_data(code), to=code)


@socketio.on("kick_player")
def kick_player(data):
    code = data["room"]
    sid = data["sid"]

    if code not in rooms or not is_admin_room(code):
        return

    rooms[code]["players"] = [
        p for p in rooms[code]["players"]
        if p["sid"] != sid
    ]

    emit("kicked", to=sid)
    emit("players_update", {"players": rooms[code]["players"], "locks": rooms[code]["locks"]}, to=code)
    emit("game_update", public_room_data(code), to=code)


@socketio.on("chat")
def chat(data):
    code = data["room"]

    if code not in rooms:
        return

    emit("chat_update", {"name": data["name"], "msg": data["msg"]}, to=code)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=True,
        allow_unsafe_werkzeug=True
    )
