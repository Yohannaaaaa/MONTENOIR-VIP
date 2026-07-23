// ---- Board data: 20 cases (simplified square, 6x6 grid perimeter) ----
const COLORS = {
  brown:'#7a5230', lightblue:'#8fc7e8', pink:'#c76fa0',
  orange:'#d98a3d', red:'#a4453b', yellow:'#d9c23d',
  green:'#3a7d63', blue:'#3a5a8c'
};

const board = [
  {name:'DÉPART', type:'corner'},
  {name:'Rue Voltaire', type:'prop', price:60, color:'brown', rent:2},
  {name:'Rue Hugo', type:'prop', price:60, color:'brown', rent:4},
  {name:'Gare du Nord', type:'station', price:200, rent:25},
  {name:'Avenue Camus', type:'prop', price:100, color:'lightblue', rent:6},
  {name:'Avenue Zola', type:'prop', price:100, color:'lightblue', rent:6},
  {name:'PRISON', type:'corner'},
  {name:'Boulevard Molière', type:'prop', price:140, color:'pink', rent:10},
  {name:'Boulevard Racine', type:'prop', price:140, color:'pink', rent:10},
  {name:'Gare Centrale', type:'station', price:200, rent:25},
  {name:'Place Rimbaud', type:'prop', price:180, color:'orange', rent:14},
  {name:'PARC GRATUIT', type:'corner'},
  {name:'Cours Balzac', type:'prop', price:220, color:'red', rent:18},
  {name:'Cours Flaubert', type:'prop', price:220, color:'red', rent:18},
  {name:'Gare du Sud', type:'station', price:200, rent:25},
  {name:'Impasse Verlaine', type:'prop', price:260, color:'yellow', rent:22},
  {name:'ALLEZ EN PRISON', type:'corner'},
  {name:'Quai Baudelaire', type:'prop', price:300, color:'green', rent:26},
  {name:'Quai Rimbaud', type:'prop', price:300, color:'green', rent:26},
  {name:'Avenue Métropole', type:'prop', price:400, color:'blue', rent:50}
];

const N = board.length;

// build cells around perimeter of 6x6 grid, skip center 4x4 (occupied by .center spanning 2/6,2/6)
const gridPositions = [
  [6,6],[6,5],[6,4],[6,3],[6,2],[6,1],
  [5,1],[4,1],[3,1],[2,1],[1,1],
  [1,2],[1,3],[1,4],[1,5],[1,6],
  [2,6],[3,6],[4,6],[5,6]
];

const boardEl = document.getElementById('board');
const centerEl = document.querySelector('.center');

board.forEach((cell, i)=>{
  const div = document.createElement('div');
  div.className = 'cell' + (cell.type==='corner' ? ' corner' : '');
  div.style.gridColumn = gridPositions[i][1];
  div.style.gridRow = gridPositions[i][0];
  div.id = 'cell-'+i;

  if(cell.type==='prop'){
    const band = document.createElement('div');
    band.className='colorband';
    band.style.background = COLORS[cell.color];
    div.appendChild(band);
  }
  const nameEl = document.createElement('div');
  nameEl.className='name';
  nameEl.textContent = cell.name;
  div.appendChild(nameEl);

  if(cell.price){
    const priceEl = document.createElement('div');
    priceEl.className='price';
    priceEl.textContent = cell.price+'€';
    div.appendChild(priceEl);
  }
  if(cell.type!=='corner'){
    const houses = document.createElement('div');
    houses.className='houses';
    houses.id = 'houses-'+i;
    div.appendChild(houses);
  }
  boardEl.insertBefore(div, centerEl);
});

// skyline decoration
const sky = document.getElementById('skyline');
[14,22,10,28,16,20,12].forEach(h=>{
  const bar = document.createElement('div');
  bar.style.height = h+'px';
  sky.appendChild(bar);
});

// token
const token = document.createElement('div');
token.className='token';
document.getElementById('cell-0').appendChild(token);

// ---- Game state ----
let position = 0;
let cash = 1500;
let owned = {}; // index -> {houses:0}
let rolling = false;

const pcash = document.getElementById('pcash');
const propDetail = document.getElementById('propDetail');
const buyBtn = document.getElementById('buyBtn');
const rollBtn = document.getElementById('rollBtn');
const logEl = document.getElementById('log');
const scoreBadge = document.getElementById('scoreBadge');
const buildBtns = [1,2,3,4,5].map(n => document.getElementById('build'+n));
const BUILD_COSTS = [100,200,300,400,500];

function log(msg){
  const p = document.createElement('div');
  p.textContent = msg;
  logEl.prepend(p);
}

function updateCash(){
  pcash.textContent = cash + ' €';
}

function currentCell(){ return board[position]; }

function refreshHousesDisplay(idx){
  const el = document.getElementById('houses-'+idx);
  if(!el) return;
  el.innerHTML='';
  const o = owned[idx];
  if(!o) return;
  if(o.houses < 4){
    for(let i=0;i<o.houses;i++){
      const h = document.createElement('div');
      h.className='house-icon';
      el.appendChild(h);
    }
  } else {
    const h = document.createElement('div');
    h.className='hotel-icon';
    el.appendChild(h);
  }
}

function markOwned(idx){
  document.getElementById('cell-'+idx).classList.add('owned');
}

// ---------------- SOUND ENGINE (Web Audio, no external files) ----------------
let audioCtx = null;
function getCtx(){
  if(!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if(audioCtx.state === 'suspended') audioCtx.resume();
  return audioCtx;
}

function tone(freq, start, dur, type, gainPeak){
  const ctx = getCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type || 'sine';
  osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
  gain.gain.setValueAtTime(0, ctx.currentTime + start);
  gain.gain.linearRampToValueAtTime(gainPeak || 0.2, ctx.currentTime + start + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(ctx.currentTime + start);
  osc.stop(ctx.currentTime + start + dur + 0.02);
}

function noiseBurst(start, dur, gainPeak){
  const ctx = getCtx();
  const bufferSize = Math.floor(ctx.sampleRate * dur);
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for(let i=0;i<bufferSize;i++){
    data[i] = (Math.random()*2-1) * (1 - i/bufferSize);
  }
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(gainPeak || 0.15, ctx.currentTime + start);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
  src.connect(gain);
  gain.connect(ctx.destination);
  src.start(ctx.currentTime + start);
}

// dice: a few sharp clicks/rattles while rolling
function playDiceSound(){
  for(let i=0;i<6;i++){
    noiseBurst(i*0.12, 0.09, 0.18);
    tone(300 + Math.random()*400, i*0.12, 0.06, 'square', 0.05);
  }
}

// money coming IN (passing GO, selling): rising two-note chime + coin clinks
function playCashInSound(){
  tone(660, 0, 0.12, 'triangle', 0.18);
  tone(880, 0.1, 0.16, 'triangle', 0.18);
  tone(1320, 0.22, 0.2, 'sine', 0.12);
  noiseBurst(0.05, 0.08, 0.06);
  noiseBurst(0.18, 0.08, 0.06);
}

// money going OUT (buying, building): descending thud + register click
function playCashOutSound(){
  tone(420, 0, 0.14, 'sawtooth', 0.14);
  tone(280, 0.1, 0.18, 'sawtooth', 0.14);
  noiseBurst(0, 0.05, 0.12);
}

// construction: hammer-like knock
function playBuildSound(){
  noiseBurst(0, 0.05, 0.25);
  tone(150, 0, 0.08, 'square', 0.15);
  noiseBurst(0.15, 0.05, 0.2);
  tone(150, 0.15, 0.08, 'square', 0.13);
}

function updateActionButtons(){
  const cell = currentCell();
  buyBtn.disabled = true;
  buildBtns.forEach(b => { b.disabled = true; b.classList.remove('active'); });

  if(cell.type==='prop' || cell.type==='station'){
    if(owned[position] === undefined){
      propDetail.textContent = cell.name + ' — libre, prix ' + cell.price + '€';
      buyBtn.disabled = cash < cell.price;
    } else if(owned[position].owner === 'me'){
      const o = owned[position];
      if(cell.type==='prop'){
        if(o.houses < 5){
          const nextLevel = o.houses; // 0-indexed -> build button index o.houses
          const cost = BUILD_COSTS[nextLevel];
          propDetail.textContent = cell.name + ' — à toi (' + (o.houses<4? o.houses+' maison(s)':'hôtel') + ')';
          const btn = buildBtns[nextLevel];
          btn.disabled = cash < cost;
          btn.classList.add('active');
        } else {
          propDetail.textContent = cell.name + ' — hôtel construit, développement max.';
        }
      } else {
        propDetail.textContent = cell.name + ' — gare à toi.';
      }
    }
  } else {
    propDetail.textContent = cell.name;
  }
}

function movePlayerTo(newPos, passedGo){
  position = newPos;
  const targetCell = document.getElementById('cell-'+position);
  targetCell.appendChild(token);
  if(passedGo){
    cash += 200;
    log('Tu passes par la case DÉPART : +200€');
    updateCash();
    playCashInSound();
  }
  const cell = currentCell();
  if(cell.type==='prop' || cell.type==='station'){
    if(owned[position] && owned[position].owner==='me'){
      log('Tu es sur ta propriété : ' + cell.name);
    } else if(owned[position]===undefined){
      log('Case libre : ' + cell.name + ' (' + cell.price + '€)');
    }
  } else {
    log('Tu arrives sur : ' + cell.name);
  }
  updateActionButtons();
}

function setDieFace(dieEl, value){
  const rotations = {
    1:{x:0,y:0},
    6:{x:0,y:180},
    2:{x:0,y:-90},
    5:{x:0,y:90},
    3:{x:-90,y:0},
    4:{x:90,y:0}
  };
  const r = rotations[value];
  // add extra full spins for animation feel
  const spinX = 360*2 + r.x;
  const spinY = 360*3 + r.y;
  dieEl.style.setProperty('--rx', spinX+'deg');
  dieEl.style.setProperty('--ry', spinY+'deg');
  dieEl.classList.remove('rolling');
  void dieEl.offsetWidth; // reflow to restart animation
  dieEl.classList.add('rolling');
  dieEl.style.transform = 'rotateX('+spinX+'deg) rotateY('+spinY+'deg)';
}

rollBtn.addEventListener('click', ()=>{
  if(rolling) return;
  rolling = true;
  rollBtn.disabled = true;
  buyBtn.disabled = true;
  buildBtns.forEach(b => b.disabled = true);
  scoreBadge.textContent = '–';

  const d1 = 1 + Math.floor(Math.random()*6);
  const d2 = 1 + Math.floor(Math.random()*6);
  setDieFace(document.getElementById('die1'), d1);
  setDieFace(document.getElementById('die2'), d2);
  playDiceSound();

  setTimeout(()=>{
    const total = d1+d2;
    scoreBadge.textContent = total;
    log('Dés : ' + d1 + ' + ' + d2 + ' = ' + total);
    let newPos = position + total;
    let passedGo = false;
    if(newPos >= N){ newPos -= N; passedGo = true; }
    movePlayerTo(newPos, passedGo);
    rolling = false;
    rollBtn.disabled = false;
  }, 1150);
});

buyBtn.addEventListener('click', ()=>{
  const cell = currentCell();
  if(cash < cell.price) return;
  cash -= cell.price;
  owned[position] = {owner:'me', houses:0};
  markOwned(position);
  updateCash();
  playCashOutSound();
  log('Achat : ' + cell.name + ' pour ' + cell.price + '€');
  updateActionButtons();
});

buildBtns.forEach((btn, idx) => {
  btn.addEventListener('click', ()=>{
    const cell = currentCell();
    const o = owned[position];
    if(!o || cell.type!=='prop') return;
    if(o.houses !== idx) return; // must build sequentially
    const cost = BUILD_COSTS[idx];
    if(cash < cost) return;
    cash -= cost;
    o.houses += 1;
    updateCash();
    playBuildSound();
    playCashOutSound();
    refreshHousesDisplay(position);
    log((o.houses<=4 ? 'Maison construite' : 'Hôtel construit') + ' sur ' + cell.name);
    updateActionButtons();
  });
});

updateCash();
updateActionButtons();
