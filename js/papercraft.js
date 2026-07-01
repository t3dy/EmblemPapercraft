// papercraft.js — render an Atalanta Fugiens emblem as a layered paper pop-up.
//
// Each extracted figure cutout becomes a flat "paper" card, staged at its source
// position and an inferred depth in front of the full-plate backing page. The
// trick that sells papercraft is SHADOW: every card casts its own cut shape onto
// the layers behind it (via an alpha-tested customDepthMaterial), so the scene
// reads as stacked paper even though each piece keeps the original engraving.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x171310);
scene.fog = new THREE.Fog(0x171310, 16, 34);

const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(2.7, 1.5, 9);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.enablePan = false;
controls.minDistance = 5;
controls.maxDistance = 16;
controls.maxPolarAngle = Math.PI * 0.62;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.5;
controls.target.set(0, 0.15, 0.25);

// ── Lighting — a warm raking key throws the paper shadows; soft fill keeps the
//    engraving readable in shadow (paper shadows are light, not black).
scene.add(new THREE.HemisphereLight(0xfff2e0, 0x2a2018, 0.42));
scene.add(new THREE.AmbientLight(0xffffff, 0.24));

const key = new THREE.DirectionalLight(0xfff0d8, 2.7);
key.position.set(-4.5, 6.5, 5.5);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -5; key.shadow.camera.right = 5;
key.shadow.camera.top = 6;   key.shadow.camera.bottom = -6;
key.shadow.camera.near = 0.5; key.shadow.camera.far = 32;
key.shadow.bias = -0.0006;
key.shadow.radius = 4;
scene.add(key);

const fill = new THREE.DirectionalLight(0xbcd0ff, 0.35);
fill.position.set(5, 2, 3);
scene.add(fill);

// ── Page + table geometry ────────────────────────────────────────────────────
const W = 4.4, H = 5.25;             // page size (~woodcut portrait aspect)
const PAPER = 0xf3ecdb;              // warm paper tint
const loader = new THREE.TextureLoader();
const maxAniso = renderer.capabilities.getMaxAnisotropy?.() || 4;

// The table the paper model stands on (catches the whole model's shadow)
{
  const tg = new THREE.PlaneGeometry(60, 60);
  const tm = new THREE.MeshStandardMaterial({ color: 0x241e17, roughness: 0.96 });
  const table = new THREE.Mesh(tg, tm);
  table.rotation.x = -Math.PI / 2;
  table.position.y = -H / 2 - 0.04;
  table.receiveShadow = true;
  scene.add(table);
}

// ── Emblem state ─────────────────────────────────────────────────────────────
let emblems = [];
let layersByNum = {};
let idx = 0;
let group = null;                    // current emblem's Object3D group
let currentCards = [];               // { mesh, depth } for the pop-depth slider
let depthMult = 1;
let backingMode = 'dim';             // 'plate' | 'dim' | 'blank'

function plateURL(n) { return `images/emblems/emblem-${String(n).padStart(2, '0')}.jpg`; }

function disposeObj(o) {
  o.traverse(n => {
    if (n.geometry) n.geometry.dispose();
    if (n.material) {
      if (n.material.map) n.material.map.dispose();
      n.material.dispose();
    }
    if (n.customDepthMaterial) n.customDepthMaterial.dispose();
  });
}

function clearGroup() {
  if (!group) return;
  disposeObj(group);
  scene.remove(group);
  group = null;
  currentCards = [];
}

// A single paper cutout: flat card, matte paper material, alpha-tested so it
// keeps its irregular cut shape — and casts that shape as a shadow.
function paperCard(tex, w, h) {
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = maxAniso;
  const geo = new THREE.PlaneGeometry(w, h);
  const mat = new THREE.MeshStandardMaterial({
    map: tex, color: PAPER, alphaTest: 0.5, side: THREE.DoubleSide,
    roughness: 0.96, metalness: 0.0,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  // Cast the cut SHAPE (not the bounding rectangle) — the papercraft essential.
  mesh.customDepthMaterial = new THREE.MeshDepthMaterial({
    depthPacking: THREE.RGBADepthPacking, map: tex, alphaTest: 0.5,
  });
  return mesh;
}

function applyDepth() {
  for (const c of currentCards) {
    c.mesh.position.z = 0.08 + c.depth * 0.7 * depthMult;
  }
}

function buildEmblem(emb) {
  clearGroup();
  group = new THREE.Group();
  scene.add(group);

  // Backing board (behind the page — a real edge when orbited)
  const bg = new THREE.BoxGeometry(W + 0.22, H + 0.22, 0.14);
  const bm = new THREE.MeshStandardMaterial({ color: 0x3a3026, roughness: 0.9, metalness: 0.05 });
  const board = new THREE.Mesh(bg, bm);
  board.position.set(0, 0, -0.1);
  board.castShadow = true;
  board.receiveShadow = true;
  group.add(board);

  // The page — receives the cutouts' shadows. 'plate' shows the full engraving,
  // 'dim' darkens it so the popped cutouts stand out, 'blank' is plain paper.
  if (backingMode === 'blank') {
    const geo = new THREE.PlaneGeometry(W, H);
    const mat = new THREE.MeshStandardMaterial({ color: 0xd9d0b9, roughness: 0.97, metalness: 0.0 });
    const page = new THREE.Mesh(geo, mat);
    page.receiveShadow = true;
    group.add(page);
  } else {
    loader.load(plateURL(emb.number), (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = maxAniso;
      const geo = new THREE.PlaneGeometry(W, H);
      const mat = new THREE.MeshStandardMaterial({
        map: tex, color: backingMode === 'dim' ? 0x5f5849 : 0xe6ddc8,
        roughness: 0.97, metalness: 0.0,
      });
      const page = new THREE.Mesh(geo, mat);
      page.position.set(0, 0, 0);
      page.receiveShadow = true;
      group.add(page);
    });
  }

  // Cutout paper layers, back-to-front
  const layers = layersByNum[emb.number] || [];
  layers.forEach((L) => {
    loader.load(`images/cutouts/${L.file}`, (tex) => {
      const w = Math.max(0.05, L.nw * W);
      const h = Math.max(0.05, L.nh * H);
      const mesh = paperCard(tex, w, h);
      mesh.position.set((L.cx - 0.5) * W, (0.5 - L.cy) * H, 0.08 + L.depth * 0.7 * depthMult);
      group.add(mesh);
      currentCards.push({ mesh, depth: L.depth });
    });
  });
}

// ── Navigation ───────────────────────────────────────────────────────────────
function show(i) {
  idx = ((i % emblems.length) + emblems.length) % emblems.length;
  const emb = emblems[idx];
  buildEmblem(emb);
  const numeral = emb.roman_numeral || (emb.number === 0 ? '—' : emb.number);
  const n = (layersByNum[emb.number] || []).length;
  document.getElementById('label').textContent = `${numeral} · ${emb.label || ('Emblem ' + emb.number)}`;
  document.getElementById('count').textContent =
    `${idx + 1} / ${emblems.length}` + (n >= 2 ? ` · ${n} paper layers` : ' · flat plate');
}

document.getElementById('prev').addEventListener('click', () => show(idx - 1));
document.getElementById('next').addEventListener('click', () => show(idx + 1));
document.getElementById('depth').addEventListener('input', (e) => {
  depthMult = parseFloat(e.target.value);
  applyDepth();
});
const backingBtn = document.getElementById('backing');
function updateBackingLabel() { if (backingBtn) backingBtn.textContent = 'backing: ' + backingMode; }
backingBtn?.addEventListener('click', () => {
  backingMode = backingMode === 'plate' ? 'dim' : backingMode === 'dim' ? 'blank' : 'plate';
  updateBackingLabel();
  show(idx);
});
updateBackingLabel();
window.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') show(idx + 1);
  else if (e.key === 'ArrowLeft') show(idx - 1);
});

// ── Boot ─────────────────────────────────────────────────────────────────────
// Fall back through client size → documentElement → innerWidth → a default, so a
// transient 0-dimension viewport (preview iframes, pre-layout boot) never yields
// a NaN aspect ratio.
function getViewport() {
  const w = canvas.clientWidth  || document.documentElement.clientWidth  || window.innerWidth  || 1280;
  const h = canvas.clientHeight || document.documentElement.clientHeight || window.innerHeight || 720;
  return { w: Math.max(w, 100), h: Math.max(h, 100) };
}
function resize() {
  const { w, h } = getViewport();
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

let _lastW = 0;
function animate() {
  requestAnimationFrame(animate);
  const { w } = getViewport();
  if (w !== _lastW) { _lastW = w; resize(); }  // self-correct once the viewport has size
  controls.update();
  renderer.render(scene, camera);
}

// Debug handle so the view can be driven from the console during development
window._pc = { scene, camera, controls, renderer, key, show: (n) => show(emblems.findIndex(x => x.number === n)) };

Promise.all([
  fetch('data/emblems.json').then(r => r.json()),
  fetch('data/layers.json').then(r => r.json()),
]).then(([e, l]) => {
  emblems = e;
  l.forEach(x => { layersByNum[x.number] = x.layers; });
  // Open on a richly-layered plate so the pop-up reads immediately
  const start = emblems.findIndex(x => x.number === 32);
  resize();
  show(start >= 0 ? start : 0);
  const ld = document.getElementById('loading');
  ld.style.transition = 'opacity .6s'; ld.style.opacity = '0';
  setTimeout(() => { ld.style.display = 'none'; }, 600);
  animate();
}).catch(err => {
  console.error('Papercraft: failed to load data', err);
  document.querySelector('#loading p').textContent = 'Error: ' + err.message;
});
