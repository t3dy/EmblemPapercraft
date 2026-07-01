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
      if (n.material.alphaMap) n.material.alphaMap.dispose();
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

// A gently-curled plane. Real paper is never dead flat; subdividing the quad and
// bowing it along Z (a soft cylindrical bend across the width, tapering top/bottom,
// plus a faint corner twist) gives each card a rippling highlight and a slightly
// curved cut-edge shadow — the physicality flat quads can't fake. `spec` carries a
// per-card amplitude/sign so no two cards curl alike.
function curledPlane(w, h, spec) {
  const g = new THREE.PlaneGeometry(w, h, 16, 20);
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const u = pos.getX(i) / w;          // ~[-0.5, 0.5]
    const v = pos.getY(i) / h;
    const bow = spec.amp * Math.cos(u * Math.PI) * (0.6 + 0.4 * Math.cos(v * Math.PI));
    const twist = spec.twist * (u * 2) * (v * 2);
    pos.setZ(i, spec.sign * bow + twist);
  }
  pos.needsUpdate = true;
  g.computeVertexNormals();
  return g;
}

// A paper cutout, built as two coplanar layers so it looks like a real cut piece:
//  · a cream "paper" backing, slightly larger, alpha-tested to the cut shape —
//    it shows a thin margin around the figure and is what casts the shadow;
//  · the engraving itself on top.
// Both alpha-tested so the silhouette (not a rectangle) is what pops and shadows.
// The card is wrapped in a bottom-edge HINGE group: the leaf is lifted +h/2 so the
// group's pivot sits at the card's bottom edge, letting animate() swing it up from
// folded-flat to erect like a pop-up book page (see the open sequence in animate).
function paperCard(tex, w, h) {
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = maxAniso;

  // Per-card curl: amplitude scales with card size but is clamped so small cutouts
  // don't over-bend; random sign/phase keeps the stack from looking machined.
  const spec = {
    amp: Math.min(0.07, Math.max(0.012, 0.03 * h)) * (0.7 + Math.random() * 0.5),
    sign: Math.random() < 0.5 ? -1 : 1,
    twist: (Math.random() - 0.5) * 0.04,
  };

  const leaf = new THREE.Group();

  const paperMat = new THREE.MeshStandardMaterial({
    color: 0xefe6cf, alphaMap: tex, alphaTest: 0.5, side: THREE.DoubleSide,
    roughness: 0.97, metalness: 0.0,
  });
  const paper = new THREE.Mesh(curledPlane(w * 1.035, h * 1.035, spec), paperMat);
  paper.position.z = -0.012;
  paper.castShadow = true;
  paper.receiveShadow = true;
  paper.customDepthMaterial = new THREE.MeshDepthMaterial({
    depthPacking: THREE.RGBADepthPacking, alphaMap: tex, alphaTest: 0.5,
  });
  leaf.add(paper);

  const inkMat = new THREE.MeshStandardMaterial({
    map: tex, color: PAPER, alphaTest: 0.5, side: THREE.DoubleSide,
    roughness: 0.96, metalness: 0.0,
  });
  const ink = new THREE.Mesh(curledPlane(w, h, spec), inkMat);
  ink.receiveShadow = true;
  leaf.add(ink);

  leaf.position.y = h / 2;              // lift so the hinge pivots at the bottom edge
  const hinge = new THREE.Group();
  hinge.add(leaf);
  return hinge;
}

function cardTargetZ(depth) { return 0.08 + depth * 0.7 * depthMult; }

// Pop-up erection easing: a gentle back-overshoot so cards spring up and settle,
// like sprung paper. c1 tuned low to keep the past-vertical overshoot small.
function easeOutBack(x) {
  const c1 = 1.2, c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
}
const FOLD = Math.PI * 0.5 * 0.9;      // folded-flat start angle (~81°, tipped forward)
const OPEN_DUR = 0.8;                  // seconds for one card to erect

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
      const card = paperCard(tex, w, h);
      // Hinge pivots at the card's bottom edge; centre still lands at (cx, cy).
      card.position.set((L.cx - 0.5) * W, (0.5 - L.cy) * H - h / 2, 0.02);
      card.rotation.x = FOLD;                 // start folded flat; animate() erects it
      group.add(card);
      // Stagger erection back-to-front: near-page cards spring first, foreground
      // figures last, so the whole model opens as a cascade rather than in unison.
      currentCards.push({ card, depth: L.depth, delay: L.depth * 0.45, bornAt: clock.getElapsedTime() });
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
  depthMult = parseFloat(e.target.value);  // animate() eases the cards to the new depth
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

const clock = new THREE.Clock();
let _lastW = 0;
function animate() {
  requestAnimationFrame(animate);
  const { w } = getViewport();
  if (w !== _lastW) { _lastW = w; resize(); }  // self-correct once the viewport has size
  const dt = Math.min(clock.getDelta(), 0.05);
  const now = clock.getElapsedTime();
  const k = 1 - Math.pow(0.0028, dt);           // frame-rate-independent ease
  for (const c of currentCards) {
    const target = cardTargetZ(c.depth);
    c.card.position.z += (target - c.card.position.z) * k;
    // Erect the hinge from folded-flat (FOLD) to upright (0) over OPEN_DUR, after
    // the per-card stagger delay; easeOutBack gives a small sprung overshoot.
    const p = Math.min(1, Math.max(0, (now - c.bornAt - c.delay) / OPEN_DUR));
    c.card.rotation.x = FOLD * (1 - easeOutBack(p));
  }
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
  // Deep-link ?emblem=N (from the gallery); else a richly-layered default
  const urlN = new URLSearchParams(location.search).get('emblem');
  let start = urlN !== null ? emblems.findIndex(x => x.number === parseInt(urlN, 10)) : -1;
  if (start < 0) start = emblems.findIndex(x => x.number === 32);
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
