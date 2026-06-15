const socket = io();

let roomCode = "";
let myName = "";
let currentState = null;
let lastCell = null;

const cells = [
  "ALLEZ","Banque","New York","Monaco","Aéroport","Londres","Varsovie",
  "Zurich","Prison","Paris","Amsterdam","Eaux","Moscou","?","Rome",
  "Madrid","Impôts","Sofia","Belgrad","Gare","Istanbul","Prague",
  "Lisbonne","Enchères","Dubaï","Pékin","Électricité","Tokyo"
];

const prices = [0,0,420,400,380,360,260,260,0,300,280,0,260,0,260,250,0,180,190,0,200,220,240,0,420,420,0,450];

const coords = [
  [82.5,51.7],[79.3,68.9],[70.2,68.4],[60.9,68.1],[51.3,68.2],
  [42.1,68.3],[32.7,68.6],[23.5,68.7],[14.8,68.5],[18.3,57.4],
  [18.7,50.5],[19.1,43.4],[19.6,34.0],[19.9,29.2],[20.2,24.2],
  [20.4,17.7],[26.7,8.2],[34.8,8.2],[43.0,8.2],[51.1,8.1],
  [58.9,8.1],[66.8,8.1],[74.7,8.1],[82.7,8.1],[83.1,18.0],
  [83.3,28.0],[83.7,39.6],[84.2,50.2]
];

const tokenAsset = {
  horse: "pawn_horse.png",
  jackpot: "pawn_jackpot.png",
  boat: "pawn_boat.png",
  car: "pawn_car.png",
  hat: "pawn_hat.png",
  cat: "pawn_cat.png"
};

const colorGroups = {
  green:[2,3,5],
  brown:[6,7],
  orange:[9,10],
  purple:[12,14,15],
  yellow:[17,18,20],
  blue:[21,22],
  red:[24,25,27]
};

function name(){
  return (document.getElementById("username").value || localStorage.getItem("metropolyUser") || "Joueur").trim();
}

function boardRect(){
  return document.getElementById("boardImg").getBoundingClientRect();
}

function point(i, off=0){
  const r = boardRect();
  const p = coords[i] || coords[0];
  return {
    x: p[0] / 100 * r.width + off,
    y: p[1] / 100 * r.height + off
  };
}

function safeId(n){
  return "tok_" + String(n).replace(/[^a-zA-Z0-9_-]/g,"_");
}

function createRoom(){
  myName = name();
  localStorage.setItem("metropolyUser", myName);
  socket.emit("monopoly_create_room", {
    username: myName,
    token: document.getElementById("tokenSelect").value
  });
}

function joinRoom(){
  myName = name();
  localStorage.setItem("metropolyUser", myName);
  socket.emit("monopoly_join_room", {
    username: myName,
    token: document.getElementById("tokenSelect").value,
    code: document.getElementById("roomCodeInput").value.trim().toUpperCase()
  });
}

function startGame(){
  if(!roomCode){
    alert("Önce oda oluştur veya odaya gir.");
    return;
  }
  socket.emit("monopoly_start_game", {code: roomCode});
}

function rollDice(){
  if(!roomCode || !myName){
    alert("Önce odaya gir.");
    return;
  }
  hideBuy();
  socket.emit("monopoly_roll_dice", {
    code: roomCode,
    username: myName
  });
}

function buyProperty(){
  socket.emit("monopoly_buy_property", {
    code: roomCode,
    username: myName
  });
  hideBuy();
}

function hideBuy(){
  document.getElementById("buyPanel").style.display = "none";
}

function getGroup(cell){
  cell = Number(cell);
  for(const [g, arr] of Object.entries(colorGroups)){
    if(arr.includes(cell)) return g;
  }
  return null;
}

function ownsFullGroup(st, player, cell){
  const g = getGroup(cell);
  if(!g) return false;
  return colorGroups[g].every(c => (st.owners || {})[String(c)] === player);
}

function canBuildHouseOn(cell){
  if(!currentState || !myName) return false;
  const c = String(cell);
  if((currentState.owners || {})[c] !== myName) return false;
  if(!ownsFullGroup(currentState, myName, Number(cell))) return false;
  if((currentState.hotels || {})[c]) return false;
  return Number((currentState.houses || {})[c] || 0) < 4;
}

function canBuildHotelOn(cell){
  if(!currentState || !myName) return false;
  const c = String(cell);
  if((currentState.owners || {})[c] !== myName) return false;
  if(!ownsFullGroup(currentState, myName, Number(cell))) return false;
  if((currentState.hotels || {})[c]) return false;
  return Number((currentState.houses || {})[c] || 0) >= 4;
}

function getBuildCell(){
  if(!currentState || !myName) return null;
  const p = currentState.players[myName];
  if(!p) return null;
  const c = String(p.position);
  if((currentState.owners || {})[c] === myName) return Number(p.position);
  return null;
}

function buildHouse(){
  const c = getBuildCell();
  if(c === null || !canBuildHouseOn(c)){
    alert("Ev almak için aynı renk serisinin tamamı sende olmalı ve kendi mülkünde olmalısın.");
    return;
  }
  socket.emit("monopoly_add_house", {code: roomCode, username: myName, cell: c});
}

function buildHotel(){
  const c = getBuildCell();
  if(c === null || !canBuildHotelOn(c)){
    alert("Otel almak için bu mülkte önce 4 ev olmalı.");
    return;
  }
  socket.emit("monopoly_add_hotel", {code: roomCode, username: myName, cell: c});
}

function render(st){
  currentState = st;
  roomCode = st.code;
  document.getElementById("roomCodeInput").value = st.code;

  renderPlayers(st);
  renderTokens(st);
  renderOwners(st);
  renderBuildings(st);
}

function renderPlayers(st){
  const box = document.getElementById("playersList");
  box.innerHTML = "";

  Object.keys(st.players || {}).forEach((n, i) => {
    const p = st.players[n];
    const colors = ["#34c759","#ff3b30","#007aff","#ffd60a","#bf5af2","#ff9500"];
    if(!p.color) p.color = colors[i % colors.length];

    const div = document.createElement("div");
    div.className = "player";
    div.innerHTML = `
      <div class="dot" style="background:${p.color}"></div>
      <b>${n}</b>
      <span class="money">${p.money}€</span>
    `;
    box.appendChild(div);
  });
}

function renderTokens(st){
  Object.keys(st.players || {}).forEach((n, i) => {
    const p = st.players[n];
    let el = document.getElementById(safeId(n));

    if(!el){
      el = document.createElement("img");
      el.id = safeId(n);
      el.className = "tokenImg";
      document.getElementById("tokens").appendChild(el);
    }

    el.src = "/static/assets/metropoly/" + (tokenAsset[p.token] || tokenAsset.horse);

    const pt = point(p.position, i * 7);
    el.style.left = pt.x + "px";
    el.style.top = pt.y + "px";
  });
}

function renderOwners(st){
  const box = document.getElementById("owners");
  box.innerHTML = "";

  Object.entries(st.owners || {}).forEach(([cell, owner]) => {
    const p = st.players[owner];
    if(!p) return;

    const pt = point(Number(cell));
    const dot = document.createElement("div");
    dot.className = "ownerDot";
    dot.style.background = p.color;
    dot.style.color = p.color;
    dot.style.left = pt.x + "px";
    dot.style.top = (pt.y + 34) + "px";
    dot.title = "Propriétaire : " + owner;

    box.appendChild(dot);
  });
}

function renderBuildings(st){
  const box = document.getElementById("buildings");
  box.innerHTML = "";

  Object.entries(st.houses || {}).forEach(([cell, n]) => {
    const pt = point(Number(cell));

    for(let i=0;i<Number(n);i++){
      const h = document.createElement("img");
      h.className = "building house";
      h.src = "/static/assets/metropoly/house_yellow.png";
      h.style.left = (pt.x - 18 + i * 12) + "px";
      h.style.top = (pt.y - 18) + "px";
      box.appendChild(h);
    }
  });

  Object.entries(st.hotels || {}).forEach(([cell, n]) => {
    if(!n) return;
    const pt = point(Number(cell));

    const hotel = document.createElement("img");
    hotel.className = "building hotel";
    hotel.src = "/static/assets/metropoly/hotel_gold.png";
    hotel.style.left = pt.x + "px";
    hotel.style.top = (pt.y - 18) + "px";
    box.appendChild(hotel);
  });
}

function animateDice(done){
  const d = document.getElementById("diceArea");
  if(!d){
    if(done) done();
    return;
  }

  d.classList.remove("rolling");
  void d.offsetWidth;
  d.classList.add("rolling");

  setTimeout(() => {
    d.classList.remove("rolling");
    if(done) done();
  }, 1000);
}

function moveToken(n, from, to, state, done){
  let el = document.getElementById(safeId(n));
  if(!el){
    render(state);
    done();
    return;
  }

  let steps = [];
  let cur = Number(from);
  const dest = Number(to);
  const total = coords.length;

  while(cur !== dest){
    cur = (cur + 1) % total;
    steps.push(cur);
    if(steps.length > total + 2) break;
  }

  const idx = Math.max(0, Object.keys(state.players).indexOf(n));
  let si = 0;

  function one(){
    if(si >= steps.length){
      done();
      return;
    }

    const step = steps[si];
    const a = {
      x: parseFloat(el.style.left) || point(from).x,
      y: parseFloat(el.style.top) || point(from).y
    };
    const b = point(step, idx * 7);

    let t0 = null;
    const duration = 280;
    el.classList.add("tap");

    function frame(ts){
      if(!t0) t0 = ts;

      const t = Math.min(1, (ts - t0) / duration);
      const e = t < .5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2) / 2;
      const arc = Math.sin(Math.PI * t) * 36;

      el.style.left = (a.x + (b.x - a.x) * e) + "px";
      el.style.top = (a.y + (b.y - a.y) * e - arc) + "px";

      if(t < 1){
        requestAnimationFrame(frame);
      }else{
        el.style.left = b.x + "px";
        el.style.top = b.y + "px";
        el.classList.remove("tap");
        si++;
        setTimeout(one, 55);
      }
    }

    requestAnimationFrame(frame);
  }

  one();
}

socket.on("monopoly_room_state", render);

socket.on("monopoly_error", d => {
  alert(d.msg);
});

socket.on("monopoly_animate_move", d => {
  animateDice(() => {
    if(currentState){
      moveToken(d.username, d.from, d.to, d.state, () => {
        render(d.state);

        if(d.pendingBuy && d.state.players[myName]){
          const landed = Number(d.state.players[myName].position);
          lastCell = landed;

          document.getElementById("buyCity").textContent = cells[landed] || "Mülk";
          document.getElementById("buyPrice").textContent = "Fiyat : " + (prices[landed] || 0) + " €";
          document.getElementById("buyPanel").style.display = "block";
        }
      });
    }else{
      render(d.state);
    }
  });
});

window.addEventListener("resize", () => {
  if(currentState) render(currentState);
});
