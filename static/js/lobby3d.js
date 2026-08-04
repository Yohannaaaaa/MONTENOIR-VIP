import * as THREE from 'three';

function pipTexture(n) {
  const W = 128, H = 128;
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#f5efe0'; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#d4af37'; ctx.lineWidth = 4; ctx.strokeRect(2, 2, W - 4, H - 4);
  const layout = { 1: [[64, 64]], 2: [[38, 38], [90, 90]], 3: [[38, 38], [64, 64], [90, 90]],
    4: [[38, 38], [90, 38], [38, 90], [90, 90]], 5: [[38, 38], [90, 38], [64, 64], [38, 90], [90, 90]],
    6: [[38, 32], [90, 32], [38, 64], [90, 64], [38, 96], [90, 96]] };
  ctx.fillStyle = '#1a1a1a';
  (layout[n] || []).forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x, y, 11, 0, Math.PI * 2); ctx.fill(); });
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function chipTexture() {
  const W = 128, H = 128;
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const ctx = c.getContext('2d');
  const grad = ctx.createRadialGradient(64, 64, 10, 64, 64, 62);
  grad.addColorStop(0, '#3a0f10'); grad.addColorStop(1, '#7a1c1c');
  ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(64, 64, 62, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#d4af37'; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(64, 64, 50, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = '#d4af37'; ctx.font = 'bold 20px Georgia'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('VIP', 64, 66);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function cardBackTexture() {
  const W = 90, H = 130;
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#5a1414'; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#d4af37'; ctx.lineWidth = 4; ctx.strokeRect(3, 3, W - 6, H - 6);
  for (let i = -H; i < W + H; i += 10) {
    ctx.strokeStyle = '#7a1c1c'; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i + H, H); ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeDie(scale) {
  const faces = [1, 2, 3, 4, 5, 6].map(n => new THREE.MeshStandardMaterial({ map: pipTexture(n), roughness: 0.4 }));
  return new THREE.Mesh(new THREE.BoxGeometry(scale, scale, scale), faces);
}
function makeChip(scale) {
  return new THREE.Mesh(
    new THREE.CylinderGeometry(scale * 0.55, scale * 0.55, scale * 0.14, 32),
    new THREE.MeshStandardMaterial({ map: chipTexture(), roughness: 0.5, metalness: 0.1 })
  );
}
function makeCard(scale) {
  const backMat = new THREE.MeshStandardMaterial({ map: cardBackTexture(), roughness: 0.6 });
  const edgeMat = new THREE.MeshStandardMaterial({ color: 0xf5efe0, roughness: 0.6 });
  return new THREE.Mesh(
    new THREE.BoxGeometry(scale * 0.7, scale * 0.03, scale),
    [edgeMat, edgeMat, backMat, backMat, edgeMat, edgeMat]
  );
}

export function initLobbyScene(canvasId, opts) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  opts = opts || {};
  const count = opts.count || 10;
  const spread = opts.spread || 3;
  const cameraZ = opts.cameraZ || 4.5;
  const scale = opts.scale || 0.55;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;

  const scene = new THREE.Scene();
  scene.background = null;

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 50);
  camera.position.set(0, 0, cameraZ);
  camera.lookAt(0, 0, 0);

  scene.add(new THREE.AmbientLight(0x9a8f80, 0.9));
  const key = new THREE.DirectionalLight(0xfff4d6, 1.8);
  key.position.set(2, 3, 3);
  scene.add(key);
  const fill = new THREE.PointLight(0xffe6b0, 4, 10);
  fill.position.set(-2, -1, 2);
  scene.add(fill);

  const builders = [makeDie, makeChip, makeCard];
  const props = [];
  for (let i = 0; i < count; i++) {
    const build = builders[i % builders.length];
    const mesh = build(scale * (0.8 + Math.random() * 0.5));
    mesh.position.set((Math.random() - 0.5) * spread * 2, (Math.random() - 0.5) * spread, (Math.random() - 0.5) * spread * 1.2 - 1);
    mesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
    scene.add(mesh);
    props.push({
      mesh,
      spinX: (Math.random() - 0.5) * 0.4,
      spinY: (Math.random() - 0.5) * 0.4,
      bobAmp: 0.15 + Math.random() * 0.15,
      bobSpeed: 0.4 + Math.random() * 0.5,
      bobPhase: Math.random() * Math.PI * 2,
      baseY: mesh.position.y
    });
  }

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    renderer.setSize(rect.width, rect.height, false);
    camera.aspect = rect.width / rect.height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas.parentElement);
  resize();

  let running = true;
  function animate() {
    if (!running) return;
    requestAnimationFrame(animate);
    const t = performance.now() / 1000;
    props.forEach(p => {
      p.mesh.rotation.x += p.spinX * 0.016;
      p.mesh.rotation.y += p.spinY * 0.016;
      p.mesh.position.y = p.baseY + Math.sin(t * p.bobSpeed + p.bobPhase) * p.bobAmp;
    });
    renderer.render(scene, camera);
  }
  animate();

  return { stop() { running = false; }, renderer, scene, camera };
}
