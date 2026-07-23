cat > /home/claude/metropoly_three.js << 'JSEOF'
console.log("METROPOLY ENGINE V2 OK");

/* =========================================================
   DONNEES DU PLATEAU (miroir exact de METROPOLY_CELLS coté serveur)
   [nom, type, prix, loyer_base, groupe]
========================================================= */
const MONO_CELLS = [
["ALLEZ","start",0,0,"corner"],
["Banque","bank",0,0,"corner"],
["New York","property",220,24,"green"],
["Monaco","property",200,22,"green"],
["Aéroport International","transport",200,25,"transport"],
["Londres","property",200,22,"green"],
["Varsovie","property",100,12,"brown"],
["Zurich","property",100,12,"brown"],
["Prison","jail",0,0,"corner"],
["Paris","property",160,18,"orange"],
["Milan","property",140,16,"orange"],
["Amsterdam","property",140,16,"orange"],
["Compagnies des Eaux","utility",100,0,"utility"],
["Moscou","property",120,14,"purple"],
["Rome","property",100,12,"purple"],
["Madrid","property",100,12,"purple"],
["Impôts","tax",0,200,"tax"],
["Sofia","property",60,6,"yellow"],
["Belgrad","property",70,8,"yellow"],
["Gare Grande Vitesse","transport",100,25,"transport"],
["Istanbul","property",70,8,"yellow"],
["Prague","property",80,10,"blue"],
["Lisbonne","property",90,12,"blue"],
["Enchères","auction",0,0,"special"],
["Dubaï","property",160,18,"red"],
["Pékin","property",160,18,"red"],
["Compagnie Électrique","utility",150,0,"utility"],
["Tokyo","property",180,20,"red"]
];
const N_CELLS = MONO_CELLS.length; // 28

/* Position (ligne, colonne) de chaque case dans une grille 8x8,
   coins aux index 0, 7, 14, 21, sens horaire. */
function cellRC(i){
    i = ((i % N_CELLS) + N_CELLS) % N_CELLS;
    if(i <= 7)  return {row:7, col:7-i};
    if(i <= 14) return {row:7-(i-7), col:0};
    if(i <= 21) return {row:0, col:i-14};
    return {row:i-21, col:7};
}

const PLAYER_COLORS = ["#ff5555","#55d6ff","#a0ff55","#ffcf40","#ff8fe0","#a870ff","#ff9955","#55ffb0"];

/* =========================================================
   ETAT LOCAL
========================================================= */
let socket = null;
let myUsername = "";
let myToken = "🎩";
let roomCode = "";
let lastState = null;
let colorByPlayer = {};
let tokenEls = {};
let isRolling = false;
let pendingBuyInfo = null;

/* =========================================================
   INIT
========================================================= */
document.addEventListener("DOMContentLoaded", () => {
    try{
        myUsername = localStorage.getItem("loggedUser") || localStorage.getItem("codenamesAccount") || "";
        if(myUsername) document.getElementById("username").value = myUsername;
    }catch(e){}

    buildBoardDOM();
    initDice3D();
    connectSocket();
});

function connectSocket(){
    socket = io();

    socket.on("monopoly_room_state", (state) => {
        applyState(state);
    });

    socket.on("monopoly_animate_move", (data) => {
        animateMove(data);
    });

    socket.on("monopoly_error", (data) => {
        showToast(data.msg || "Erreur.");
    });

    socket.on("monopoly_chat_message", (data) => {
        showToast(data.username + " : " + data.message);
    });
}

/* =========================================================
   ACTIONS JOUEUR (appelées par les boutons HTML)
========================================================= */
function currentUsername(){
    return (document.getElementById("username").value || "").trim();
}

function createRoom(){
    myUsername = currentUsername();
    myToken = document.getElementById("tokenSelect").value;
    if(!myUsername){ showToast("Entre ton nom d'abord."); return; }
    try{ localStorage.setItem("loggedUser", myUsername); }catch(e){}
    socket.emit("monopoly_create_room", {username: myUsername, token: myToken});
}

function joinRoom(){
    myUsername = currentUsername();
    myToken = document.getElementById("tokenSelect").value;
    const code = (document.getElementById("roomCodeInput").value || "").trim().toUpperCase();
    if(!myUsername || !code){ showToast("Entre ton nom et le code de la salle."); return; }
    roomCode = code;
    try{ localStorage.setItem("loggedUser", myUsername); }catch(e){}
    socket.emit("monopoly_join_room", {username: myUsername, token: myToken, code: code});
}

function startGame(){
    if(!roomCode){ showToast("Rejoins ou crée une salle d'abord."); return; }
    socket.emit("monopoly_start_game", {code: roomCode});
}

function rollDice(){
    if(!roomCode){ showToast("Pas de salle."); return; }
    if(isRolling){ return; }
    socket.emit("monopoly_roll_dice", {code: roomCode, username: myUsername});
}

function endTurn(){
    if(!roomCode) return;
    socket.emit("monopoly_end_turn", {code: roomCode});
}

function buyProperty(){
    socket.emit("monopoly_buy_property", {code: roomCode, username: myUsername});
    hideBuy();
}

function hideBuy(){
    document.getElementById("buyPanel").classList.remove("show");
    pendingBuyInfo = null;
}

function buildHouseOn(cellIndex){
    socket.emit("monopoly_add_house", {code: roomCode, username: myUsername, cell: cellIndex});
}
function buildHotelOn(cellIndex){
    socket.emit("monopoly_add_hotel", {code: roomCode, username: myUsername, cell: cellIndex});
}

/* =========================================================
   CONSTRUCTION DU PLATEAU (DOM)
========================================================= */
function buildBoardDOM(){
    const board = document.getElementById("board");
    board.innerHTML = "";

    for(let i=0;i<N_CELLS;i++){
        const [name, typ, price, rent, grp] = MONO_CELLS[i];
        const {row, col} = cellRC(i);

        const cell = document.createElement("div");
        cell.className = "cell";
        cell.id = "cell-"+i;
        cell.style.gridRow = (row+1);
        cell.style.gridColumn = (col+1);

        const bar = document.createElement("div");
        bar.className = "grpBar grp-"+grp;
        cell.appendChild(bar);

        const nameEl = document.createElement("div");
        nameEl.className = "cName";
        nameEl.textContent = name;
        cell.appendChild(nameEl);

        if(price > 0){
            const priceEl = document.createElement("div");
            priceEl.className = "cPrice";
            priceEl.textContent = price+"€";
            cell.appendChild(priceEl);
        }

        const pipsWrap = document.createElement("div");
        pipsWrap.className = "housePips";
        pipsWrap.id = "pips-"+i;
        cell.appendChild(pipsWrap);

        if(typ === "property" && price > 0){
            cell.onclick = () => showCellInfo(i);
        }

        board.appendChild(cell);
    }

    const center = document.createElement("div");
    center.className = "cell center";
    center.innerHTML = '<div>🏛️ METROPOLY</div><div id="centerTurn" style="font-size:12px;"></div><div id="centerLog"></div>';
    board.appendChild(center);
}

function showCellInfo(i){
    if(!lastState) return;
    const [name, typ, price] = MONO_CELLS[i];
    const owner = lastState.owners ? lastState.owners[String(i)] : null;
    showToast(name + (owner ? (" — possédée par " + owner) : (" — libre, " + price + "€")));
}

/* =========================================================
   APPLICATION DE L'ETAT RECU DU SERVEUR
========================================================= */
function applyState(state){
    lastState = state;
    renderOwnersAndHouses(state);
    renderPlayers(state);
    renderMyProperties(state);
    renderTokens(state, false);

    const centerTurn = document.getElementById("centerTurn");
    if(centerTurn){
        const names = Object.keys(state.players || {}).filter(n => !state.players[n].bankrupt);
        const turnName = names[state.turnIndex % Math.max(names.length,1)] || "-";
        centerTurn.textContent = state.started ? ("Tour de : " + turnName) : "En attente du départ...";
    }
    const centerLog = document.getElementById("centerLog");
    if(centerLog) centerLog.textContent = state.lastLog || "";
    if(state.lastLog) showToast(state.lastLog);
}

function renderOwnersAndHouses(state){
    for(let i=0;i<N_CELLS;i++){
        const cellEl = document.getElementById("cell-"+i);
        if(!cellEl) continue;
        const owner = state.owners ? state.owners[String(i)] : null;
        cellEl.classList.toggle("ownedGlow", !!owner);

        const pips = document.getElementById("pips-"+i);
        if(pips){
            pips.innerHTML = "";
            const hasHotel = state.hotels && state.hotels[String(i)];
            const houses = (state.houses && state.houses[String(i)]) || 0;
            if(hasHotel){
                const h = document.createElement("div");
                h.className = "hotelPip";
                pips.appendChild(h);
            } else {
                for(let h=0; h<houses; h++){
                    const p = document.createElement("div");
                    p.className = "housePip";
                    pips.appendChild(p);
                }
            }
        }
    }
}

function renderPlayers(state){
    const wrap = document.getElementById("playersList");
    wrap.innerHTML = "";
    const players = state.players || {};
    const names = Object.keys(players);
    const activeNames = names.filter(n => !players[n].bankrupt);
    const turnName = activeNames[state.turnIndex % Math.max(activeNames.length,1)];

    names.forEach((name, idx) => {
        if(!colorByPlayer[name]) colorByPlayer[name] = PLAYER_COLORS[idx % PLAYER_COLORS.length];
        const p = players[name];
        const row = document.createElement("div");
        row.className = "playerRow" + (name === turnName && state.started ? " turnActive" : "");
        row.innerHTML =
            '<span class="playerDot" style="background:'+colorByPlayer[name]+'"></span>' +
            '<span class="pname">'+(p.token||"")+" "+name+(p.bankrupt?" 💀":"")+'</span>' +
            '<span>'+p.money+'€</span>';
        wrap.appendChild(row);
    });
}

function renderMyProperties(state){
    const wrap = document.getElementById("myProperties");
    wrap.innerHTML = "";
    if(!s
