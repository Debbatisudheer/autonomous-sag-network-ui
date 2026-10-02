const $ = (id) => document.getElementById(id);
let source = null;
let events = [];
let current = null;
let lastTopology = null;
let summary = null;
let mapView = "ops";
let worldMapImage = null;
let showOrbit = true;
let candidateCacheKey = "";
let activeWorkspace = "overview";

function setWorkspace(view){
  activeWorkspace = view;
  document.querySelectorAll(".nav[data-view]").forEach(n => n.classList.toggle("active", n.dataset.view === view));
  const hero = document.querySelector(".hero-grid");
  const triple = document.querySelector(".triple-grid");
  const analytics = document.querySelector(".analytics-grid");
  const bottom = document.querySelector(".bottom-grid");
  const telemetryView = $("view-telemetry");
  const decisionView = $("view-decision");
  const autonomyView = $("view-autonomy");
  const resilience = $("resilience");
  const overview = view === "overview";
  const show = (el, yes, display = "block") => { if (el) el.style.display = yes ? display : "none"; };

  show(hero, overview || view === "network", "grid");
  show(triple, overview, "grid");
  show(analytics, overview, "grid");
  show(bottom, overview, "grid");
  show(telemetryView, view === "telemetry");
  show(decisionView, view === "decision");
  show(autonomyView, view === "autonomy");
  show(resilience, overview || view === "resilience");

  if (view === "network" || overview) {
    requestAnimationFrame(() => { if (lastTopology) drawGlobe(lastTopology, current); });
  }
  if (view === "telemetry") requestAnimationFrame(drawTelemetryLarge);
}


const esc = (s) => String(s ?? "—").replace(/[&<>"']/g, (m) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]));
const pct = (v) => `${(Number(v ?? 0) * 100).toFixed(1)}%`;
const fmtBps = (v) => v >= 1e9 ? `${(v / 1e9).toFixed(2)} Gbps` : v >= 1e6 ? `${(v / 1e6).toFixed(1)} Mbps` : v >= 1e3 ? `${(v / 1e3).toFixed(1)} Kbps` : `${Number(v ?? 0).toFixed(0)} bps`;
const fmtDist = (m) => m >= 1e6 ? `${(m / 1e6).toFixed(1)} Mm` : `${(m / 1e3).toFixed(1)} km`;
const domainLabel = (d) => d ? `${d[0].toUpperCase()}${d.slice(1)}` : "—";
const mapColors = {ground:"#ffb72f", air:"#41e7a3", space:"#64aaff", user:"#bb8dff"};


function loadWorldMap() {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => { worldMapImage = img; resolve(img); };
    img.onerror = () => resolve(null);
    img.src = "/world_map.png";
  });
}
function projectWorld(lat, lon, w, h) { return {x:(lon+180)/360*w, y:(90-lat)/180*h}; }
function drawWorldBackdrop(ctx,w,h) {
  ctx.save(); ctx.fillStyle="#04101a"; ctx.fillRect(0,0,w,h);
  if(worldMapImage){ctx.globalAlpha=.96;ctx.drawImage(worldMapImage,0,0,w,h);} ctx.globalAlpha=1;
  ctx.strokeStyle="rgba(96,150,182,.12)";ctx.lineWidth=1;
  for(let lat=-60;lat<=60;lat+=30){const y=(90-lat)/180*h;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  for(let lon=-180;lon<=180;lon+=60){const x=(lon+180)/360*w;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
  ctx.restore();
}
function collectServingEvents(){const m=new Map();for(const e of events)m.set(e.user_id,e);return [...m.values()];}
function drawWorldOrbit(ctx,orbit,w,h){if(!showOrbit||!orbit?.length)return;ctx.save();ctx.strokeStyle="rgba(100,170,255,.78)";ctx.lineWidth=1.5;ctx.setLineDash([5,5]);ctx.beginPath();let started=false,prevLon=null;for(const pt of orbit){const lon=Number(pt.lon);const q=projectWorld(pt.lat,pt.lon,w,h);if(prevLon!==null&&Math.abs(lon-prevLon)>180)started=false;if(!started){ctx.moveTo(q.x,q.y);started=true;}else ctx.lineTo(q.x,q.y);prevLon=lon;}ctx.stroke();ctx.setLineDash([]);ctx.restore();}
function labelSize(ctx, text) {
  const m = ctx.measureText(text);
  return { width: m.width + 14, height: 18 };
}

function candidateLabelOffsets(node, labelW, labelH) {
  const p = node;
  return [
    {dx: 10, dy: -12}, {dx: 10, dy: 8}, {dx: -labelW - 10, dy: -12},
    {dx: -labelW - 10, dy: 8}, {dx: 10, dy: -28}, {dx: 10, dy: 24},
    {dx: -labelW - 10, dy: -28}, {dx: -labelW - 10, dy: 24},
    {dx: -labelW/2, dy: -28}, {dx: -labelW/2, dy: 18},
  ];
}

function placeLabels(ctx, labels, w, h, pad=8) {
  const placed = [];
  for (const item of labels) {
    const size = labelSize(ctx, item.text);
    let best = null;
    let bestScore = Infinity;
    for (const off of candidateLabelOffsets(item.point, size.width, size.height)) {
      let x = item.point.x + off.dx;
      let y = item.point.y + off.dy;
      x = Math.max(pad, Math.min(w - size.width - pad, x));
      y = Math.max(size.height + pad, Math.min(h - pad, y));
      const rect = {x, y: y-size.height, w:size.width, h:size.height};
      let score = 0;
      for (const q of placed) {
        const overlapX = Math.max(0, Math.min(rect.x+rect.w, q.x+q.w) - Math.max(rect.x, q.x));
        const overlapY = Math.max(0, Math.min(rect.y+rect.h, q.y+q.h) - Math.max(rect.y, q.y));
        score += overlapX * overlapY * 50;
      }
      const dist = Math.hypot(rect.x-(item.point.x+10), rect.y-(item.point.y-12));
      score += dist * 0.15;
      if (score < bestScore) { bestScore = score; best = {...rect, text:item.text, point:item.point}; }
      if (bestScore === 0) break;
    }
    placed.push(best);
  }
  return placed;
}

function drawNodeMarker(ctx, n, p, active) {
  const col = mapColors[n.domain] || "#fff";
  ctx.save();
  ctx.fillStyle = col;
  ctx.strokeStyle = col;
  ctx.shadowBlur = active ? 18 : 10;
  ctx.shadowColor = col;
  const r = n.domain === "space" ? 6.5 : n.domain === "user" ? 5.5 : 5;
  ctx.beginPath();
  if (n.domain === "ground") {
    ctx.rect(p.x-r, p.y-r, r*2, r*2);
    ctx.fill();
  } else if (n.domain === "air") {
    ctx.moveTo(p.x, p.y-r-1); ctx.lineTo(p.x+r+1, p.y+r); ctx.lineTo(p.x-r-1, p.y+r); ctx.closePath(); ctx.fill();
  } else {
    ctx.arc(p.x,p.y,r,0,Math.PI*2); ctx.fill();
  }
  ctx.shadowBlur=0;
  if (active) {
    ctx.strokeStyle = col + "aa";
    ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(p.x,p.y,r+10,0,Math.PI*2); ctx.stroke();
  }
  ctx.restore();
}

function drawLabeledNodes(ctx, nodes, positions, cycle, w, h, compact=false) {
  const labels = [];
  for (const n of nodes) {
    const p = positions[n.id];
    if (!p) continue;
    labels.push({ text:n.id, point:p, node:n });
    drawNodeMarker(ctx, n, p, n.id===cycle?.selected_resource_id || n.id===cycle?.user_id);
  }
  ctx.save();
  ctx.font = compact ? "9px Segoe UI" : "10px Segoe UI";
  const placed = placeLabels(ctx, labels, w, h, compact ? 5 : 8);
  for (const q of placed) {
    const dx = q.x - q.point.x;
    const dy = q.y - q.point.y;
    if (Math.abs(dx) + Math.abs(dy) > 24) {
      ctx.strokeStyle = "rgba(160,206,227,.32)";
      ctx.lineWidth = .8;
      ctx.beginPath(); ctx.moveTo(q.point.x,q.point.y); ctx.lineTo(q.x+(dx>0?0:q.w),q.y+q.h); ctx.stroke();
    }
    ctx.fillStyle = "rgba(4,14,23,.82)";
    ctx.strokeStyle = "rgba(48,93,119,.55)";
    ctx.lineWidth = .7;
    ctx.beginPath(); ctx.roundRect(q.x, q.y, q.w, q.h, 5); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#d2e4ef";
    ctx.fillText(q.text, q.x+7, q.y+12);
  }
  ctx.restore();
}

function geoDistanceKm(a,b){
  const R=6371;
  const p1=Number(a.lat)*Math.PI/180, p2=Number(b.lat)*Math.PI/180;
  const dLat=(Number(b.lat)-Number(a.lat))*Math.PI/180;
  const dLon=(Number(b.lon)-Number(a.lon))*Math.PI/180;
  const q=Math.sin(dLat/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.min(1,Math.sqrt(q)));
}

function isLocalNode(node,center){
  if(!node || node.domain==="space")return false;
  return geoDistanceKm(node,center)<=250;
}

function drawLocalCluster(ctx,cp,localNodes){
  const counts={ground:0,air:0,user:0};
  for(const n of localNodes) counts[n.domain]=(counts[n.domain]||0)+1;
  const total=localNodes.length;
  ctx.save();
  ctx.strokeStyle="rgba(187,141,255,.40)";ctx.lineWidth=1.2;ctx.setLineDash([4,4]);
  ctx.beginPath();ctx.arc(cp.x,cp.y,23,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
  let dotIndex=0;
  for(const d of ["ground","air","user"]){
    for(let i=0;i<(counts[d]||0);i++){
      const a=dotIndex++*Math.PI*2/Math.max(total,1)-Math.PI/2;
      const x=cp.x+Math.cos(a)*13, y=cp.y+Math.sin(a)*13, col=mapColors[d];
      ctx.fillStyle=col;ctx.shadowBlur=8;ctx.shadowColor=col;ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;
    }
  }
  ctx.fillStyle="#dcebf4";ctx.font="600 10px Segoe UI";ctx.fillText("SAG regional network",cp.x+31,cp.y-8);
  ctx.fillStyle="#7f9bb0";ctx.font="9px Segoe UI";ctx.fillText(`${total} local nodes • ${counts.ground||0} Ground • ${counts.air||0} Air • ${counts.user||0} Users`,cp.x+31,cp.y+8);
  ctx.restore();
}

function drawWorldNodesAndLinks(ctx,topology,cycle,w,h){
  const nodes=topology.nodes||[],positions={};
  for(const n of nodes) positions[n.id]=projectWorld(n.lat,n.lon,w,h);
  const center=topology.center||{lat:17.39,lon:78.4867};
  const localNodes=nodes.filter(n=>isLocalNode(n,center));
  const visibleNodes=nodes.filter(n=>!isLocalNode(n,center));
  const serving=collectServingEvents();
  ctx.save();
  let linkIndex=0;
  for(const e of serving){
    const nu=nodes.find(n=>n.id===e.user_id), nv=nodes.find(n=>n.id===e.selected_resource_id);
    if(nu&&nv&&isLocalNode(nu,center)&&isLocalNode(nv,center))continue;
    const a=positions[e.user_id],b=positions[e.selected_resource_id];
    if(!a||!b)continue;
    const active=e.user_id===cycle?.user_id;
    const bend=((linkIndex++%3)-1)*7;
    ctx.strokeStyle=active?"#41e7a3":"rgba(100,170,255,.42)";ctx.lineWidth=active?2.5:1.1;
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.quadraticCurveTo((a.x+b.x)/2,(a.y+b.y)/2+bend,b.x,b.y);ctx.stroke();
    if(active){ctx.fillStyle="#d9fff1";ctx.shadowBlur=10;ctx.shadowColor="#41e7a3";ctx.beginPath();ctx.arc((a.x+b.x)/2,(a.y+b.y)/2+bend/2,3,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
  }
  ctx.restore();
  drawLabeledNodes(ctx,visibleNodes,positions,cycle,w,h,false);
  const cp=projectWorld(center.lat,center.lon,w,h);
  if(localNodes.length)drawLocalCluster(ctx,cp,localNodes);
  ctx.save();ctx.strokeStyle="rgba(255,203,103,.55)";ctx.setLineDash([4,4]);ctx.beginPath();ctx.arc(cp.x,cp.y,11,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);ctx.restore();
  return positions;
}

function drawRegionalInset(ctx,topology,cycle,x,y,w,h){const nodes=(topology.nodes||[]).filter(n=>n.domain!=="space");if(!nodes.length)return;const lats=nodes.map(n=>Number(n.lat)),lons=nodes.map(n=>Number(n.lon)),padLat=Math.max((Math.max(...lats)-Math.min(...lats))*.9,.04),padLon=Math.max((Math.max(...lons)-Math.min(...lons))*.9,.04),bounds={minLat:Math.min(...lats)-padLat,maxLat:Math.max(...lats)+padLat,minLon:Math.min(...lons)-padLon,maxLon:Math.max(...lons)+padLon};ctx.save();ctx.fillStyle="rgba(4,14,23,.94)";ctx.strokeStyle="#2c607e";ctx.lineWidth=1;ctx.beginPath();ctx.roundRect(x,y,w,h,10);ctx.fill();ctx.stroke();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();const pos={};for(const n of nodes)pos[n.id]={x:x+w*(n.lon-bounds.minLon)/(bounds.maxLon-bounds.minLon),y:y+h*(bounds.maxLat-n.lat)/(bounds.maxLat-bounds.minLat)};for(const e of collectServingEvents()){const a=pos[e.user_id],b=pos[e.selected_resource_id];if(!a||!b)continue;ctx.strokeStyle=e.user_id===cycle?.user_id?"#41e7a3":"rgba(100,170,255,.4)";ctx.lineWidth=e.user_id===cycle?.user_id?2.5:1;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}for(const n of nodes){const p=pos[n.id],col=mapColors[n.domain]||"#fff";ctx.fillStyle=col;ctx.shadowBlur=8;ctx.shadowColor=col;ctx.beginPath();ctx.arc(p.x,p.y,n.domain==="user"?4.5:4,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;ctx.fillStyle="#d1e3ed";ctx.font="9px Segoe UI";ctx.fillText(n.id,p.x+6,p.y+3);}ctx.restore();ctx.save();ctx.fillStyle="#cfe2ee";ctx.font="10px Segoe UI";ctx.fillText("REGIONAL FOCUS • actual project coordinates",x+10,y+16);ctx.restore();}
function drawOperationalMap(topology,cycle,w,h,ctx){ctx.clearRect(0,0,w,h);drawWorldBackdrop(ctx,w,h);drawWorldOrbit(ctx,topology.orbit,w,h);drawWorldNodesAndLinks(ctx,topology,cycle,w,h);drawRegionalInset(ctx,topology,cycle,18,h-198,360,180);ctx.save();ctx.fillStyle="rgba(4,14,23,.86)";ctx.strokeStyle="#23465d";ctx.beginPath();ctx.roundRect(w-280,18,262,78,10);ctx.fill();ctx.stroke();ctx.fillStyle="#8aa7ba";ctx.font="9px Segoe UI";ctx.fillText("LIVE GEOGRAPHIC CONTEXT",w-264,39);ctx.fillStyle="#dcebf4";ctx.font="11px Segoe UI";ctx.fillText(`Network center ${(topology.center?.lat??17.39).toFixed(3)}°N`,w-264,59);ctx.fillStyle="#74b5d7";ctx.fillText(`${(topology.center?.lon??78.4867).toFixed(3)}°E`,w-264,76);ctx.restore();}

function resizeCanvas(canvas) {
  const r = canvas.getBoundingClientRect();
  const d = window.devicePixelRatio || 1;
  const cssW = Math.max(1, Math.floor(r.width));
  const cssH = Math.max(1, Math.floor(r.height));
  const pixelW = Math.max(1, Math.floor(cssW * d));
  const pixelH = Math.max(1, Math.floor(cssH * d));
  if (canvas.width !== pixelW || canvas.height !== pixelH) {
    canvas.width = pixelW;
    canvas.height = pixelH;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(d, 0, 0, d, 0, 0);
  return {ctx, w:cssW, h:cssH};
}

function nodeMap(nodes) {
  const m = {};
  for (const n of nodes || []) m[n.id] = n;
  return m;
}

function geo3d(latDeg, lonDeg, centerLat, centerLon, radius) {
  const lat = latDeg * Math.PI / 180;
  const lon = lonDeg * Math.PI / 180;
  const cLat = centerLat * Math.PI / 180;
  const cLon = centerLon * Math.PI / 180;
  const dLon = lon - cLon;
  const x = Math.cos(lat) * Math.sin(dLon);
  const y = Math.sin(lat) * Math.cos(cLat) - Math.cos(lat) * Math.cos(dLon) * Math.sin(cLat);
  const z = Math.sin(lat) * Math.sin(cLat) + Math.cos(lat) * Math.cos(dLon) * Math.cos(cLat);
  return {x, y, z, sx: radius * x, sy: -radius * y};
}

function drawGrid(ctx, cx, cy, R) {
  ctx.save();
  ctx.strokeStyle = "rgba(93,167,207,.18)";
  ctx.lineWidth = 1;
  for (let i = -60; i <= 60; i += 20) {
    const yy = cy - R * Math.sin(i * Math.PI / 180);
    const rx = R * Math.cos(i * Math.PI / 180);
    ctx.beginPath();
    ctx.ellipse(cx, yy, rx, Math.max(2, R * .085), 0, 0, Math.PI * 2);
    ctx.stroke();
  }
  for (let i = -75; i <= 75; i += 25) {
    const rx = Math.abs(R * Math.cos(i * Math.PI / 180));
    ctx.beginPath();
    ctx.ellipse(cx, cy, Math.max(4, rx), R, 0, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawEarth(ctx, cx, cy, R) {
  const g = ctx.createRadialGradient(cx - R * .28, cy - R * .30, R * .06, cx, cy, R * 1.05);
  g.addColorStop(0, "#1a5577");
  g.addColorStop(.42, "#0e3452");
  g.addColorStop(.78, "#09243a");
  g.addColorStop(1, "#030d16");
  ctx.fillStyle = g;
  ctx.shadowBlur = 34;
  ctx.shadowColor = "rgba(49,188,255,.18)";
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
  ctx.strokeStyle = "#3f98bd"; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();
  drawGrid(ctx, cx, cy, R);
  ctx.fillStyle = "rgba(40,106,136,.20)";
  for (let i = 0; i < 5; i++) {
    ctx.beginPath();
    const y = cy - R * .45 + i * R * .19;
    ctx.ellipse(cx - R * .05, y, R * (.35 - i*.015), R*.055, -.12, 0, Math.PI*2); ctx.fill();
  }
}

function drawOrbit(ctx, orbit, centerLat, centerLon, cx, cy, R) {
  if (!showOrbit || !orbit?.length) return;
  ctx.save();
  ctx.strokeStyle = "rgba(100,170,255,.55)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([5,5]);
  ctx.beginPath();
  let started = false;
  for (const p of orbit) {
    const q = geo3d(p.lat, p.lon, centerLat, centerLon, R * 1.17);
    if (q.z < -0.15) { started = false; continue; }
    const x = cx + q.sx, y = cy + q.sy;
    if (!started) { ctx.moveTo(x,y); started = true; } else ctx.lineTo(x,y);
  }
  ctx.stroke(); ctx.restore();
}

function drawRegionalGrid(ctx, w, h, minLat, maxLat, minLon, maxLon) {
  ctx.save();
  ctx.strokeStyle = "rgba(79,137,173,.13)"; ctx.lineWidth = 1;
  for (let lat = Math.ceil(minLat); lat <= Math.floor(maxLat); lat++) {
    const y = h * (maxLat - lat) / (maxLat - minLat);
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke();
  }
  for (let lon = Math.ceil(minLon); lon <= Math.floor(maxLon); lon++) {
    const x = w * (lon - minLon) / (maxLon - minLon);
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h); ctx.stroke();
  }
  ctx.restore();
}

function projectRegional(lat, lon, bounds, w, h) {
  const pad = 34;
  return {
    x: pad + (w - 2*pad) * (lon - bounds.minLon) / Math.max(bounds.maxLon - bounds.minLon, 1e-9),
    y: pad + (h - 2*pad) * (bounds.maxLat - lat) / Math.max(bounds.maxLat - bounds.minLat, 1e-9),
  };
}

function drawRegional(ctx, topology, cycle, w, h) {
  const nodes = topology.nodes || [];
  const visible = nodes.filter(n => n.domain !== "space");
  const lats = visible.map(n=>n.lat), lons=visible.map(n=>n.lon);
  const padLat = .08, padLon = .10;
  const bounds = {minLat:Math.min(...lats)-padLat,maxLat:Math.max(...lats)+padLat,minLon:Math.min(...lons)-padLon,maxLon:Math.max(...lons)+padLon};
  drawRegionalGrid(ctx,w,h,bounds.minLat,bounds.maxLat,bounds.minLon,bounds.maxLon);
  const positions = {};
  for(const n of nodes) {
    const p=projectRegional(n.lat,n.lon,bounds,w,h); positions[n.id]=p;
  }
  const serving = new Map();
  for (const e of events) serving.set(e.user_id,e);
  ctx.save(); ctx.lineWidth=1.1;
  for(const e of serving.values()){
    const a=positions[e.user_id],b=positions[e.selected_resource_id]; if(!a||!b) continue;
    ctx.strokeStyle=e.user_id===cycle?.user_id?"#41e7a3":"rgba(100,170,255,.32)"; if(e.user_id===cycle?.user_id){ctx.lineWidth=2.5;ctx.shadowBlur=12;ctx.shadowColor="#41e7a3";}
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.shadowBlur=0;
  }
  if(cycle?.previous_resource_id && cycle?.selected_resource_id && cycle.previous_resource_id!==cycle.selected_resource_id){
    const a=positions[cycle.user_id],b=positions[cycle.previous_resource_id],c=positions[cycle.selected_resource_id];
    if(a&&b&&c){ctx.strokeStyle="#ffb72f88";ctx.setLineDash([4,5]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.strokeStyle="#41e7a3";ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(c.x,c.y);ctx.stroke();ctx.setLineDash([]);}
  }
  ctx.restore();
  drawReferenceCities(ctx, topology.reference_cities || [], bounds,w,h);
  drawRegionalNodes(ctx,nodes,positions,cycle);
  return positions;
}

function drawReferenceCities(ctx, refs, bounds,w,h){
  ctx.save();
  for(const r of refs){
    const p=projectRegional(r.lat,r.lon,bounds,w,h);
    ctx.fillStyle="#6d8ba1";ctx.beginPath();ctx.arc(p.x,p.y,2.5,0,Math.PI*2);ctx.fill();
    ctx.font="9px Segoe UI";ctx.fillStyle="#668196";ctx.fillText(r.id.replace("-ref", ""),p.x+5,p.y-4);
  }
  ctx.restore();
}

function drawRegionalNodes(ctx,nodes,positions,cycle){
  const nonSpace = nodes.filter(n=>n.domain!=="space");
  drawLabeledNodes(ctx, nonSpace, positions, cycle, ctx.canvas.clientWidth || 600, ctx.canvas.clientHeight || 420, true);
}

function drawGlobe(topology, cycle) {
  lastTopology=topology;
  const canvas=$("globe"),{ctx,w,h}=resizeCanvas(canvas);
  ctx.clearRect(0,0,w,h);
  const centerLat=topology.center?.lat??17.39, centerLon=topology.center?.lon??78.4867;
  if(mapView==="ops"){drawOperationalMap(topology,cycle,w,h,ctx);$("geographyLabel").textContent=`OPERATIONAL MAP • NETWORK CENTER ${centerLat.toFixed(3)}°N ${centerLon.toFixed(3)}°E`;$("mapModeBadge").textContent="OPERATIONAL MAP";}
  else if(mapView==="regional"){drawRegional(ctx,topology,cycle,w,h);$("geographyLabel").textContent=`REGIONAL VIEW • ${centerLat.toFixed(3)}°N ${centerLon.toFixed(3)}°E`;$("mapModeBadge").textContent="REGIONAL FOCUS";}
  else {
    const cx=w*.5,cy=h*.53,R=Math.min(w,h)*.39;
    drawEarth(ctx,cx,cy,R);
    drawOrbit(ctx,topology.orbit,centerLat,centerLon,cx,cy,R);
    const nodeList=topology.nodes||[],positions={};
    for(const n of nodeList){const q=geo3d(n.lat,n.lon,centerLat,centerLon,R*(n.domain==="space"?1.14:1.01));positions[n.id]={x:cx+q.sx,y:cy+q.sy,z:q.z};}
    const center={lat:centerLat,lon:centerLon};
    const localNodes=nodeList.filter(n=>isLocalNode(n,center));
    const visibleNodes=nodeList.filter(n=>!isLocalNode(n,center));
    const serving=new Map();for(const e of events)serving.set(e.user_id,e);
    for(const e of serving.values()){const nu=nodeList.find(n=>n.id===e.user_id),nv=nodeList.find(n=>n.id===e.selected_resource_id);if(nu&&nv&&isLocalNode(nu,center)&&isLocalNode(nv,center))continue;const a=positions[e.user_id],b=positions[e.selected_resource_id];if(!a||!b)continue;ctx.save();ctx.strokeStyle=e.user_id===cycle?.user_id?"#41e7a3":"rgba(100,170,255,.24)";ctx.lineWidth=e.user_id===cycle?.user_id?2.7:1;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.quadraticCurveTo((a.x+b.x)/2,(a.y+b.y)/2-25,b.x,b.y);ctx.stroke();ctx.restore();}
    const all=[...visibleNodes].sort((a,b)=>(positions[a.id]?.z??0)-(positions[b.id]?.z??0));
    for(const n of all){const p=positions[n.id];if(!p)continue;ctx.save();ctx.globalAlpha=p.z<0?.28:1;drawNodeMarker(ctx,n,p,n.id===cycle?.selected_resource_id||n.id===cycle?.user_id);ctx.restore();}
    ctx.save();ctx.font="10px Segoe UI";for(const q of placeLabels(ctx,all.filter(n=>positions[n.id]).map(n=>({text:n.id,point:positions[n.id],node:n})),w,h,8)){ctx.fillStyle="rgba(4,14,23,.78)";ctx.strokeStyle="rgba(48,93,119,.55)";ctx.beginPath();ctx.roundRect(q.x,q.y,q.w,q.h,5);ctx.fill();ctx.stroke();ctx.fillStyle="#c6d8e5";ctx.fillText(q.text,q.x+7,q.y+12);}ctx.restore();
    if(localNodes.length){const lp=geo3d(centerLat,centerLon,centerLat,centerLon,R*1.01);drawLocalCluster(ctx,{x:cx+lp.sx,y:cy+lp.sy},localNodes);}
    const hd=geo3d(centerLat,centerLon,centerLat,centerLon,R);ctx.save();ctx.strokeStyle="#ffcf67aa";ctx.setLineDash([4,4]);ctx.beginPath();ctx.arc(cx+hd.sx,cy+hd.sy,18,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);ctx.restore();
    $("geographyLabel").textContent=`GLOBAL 3D VIEW • NETWORK CENTER ${centerLat.toFixed(3)}°N ${centerLon.toFixed(3)}°E`;$("mapModeBadge").textContent="3D GLOBE";
  }
  $("mapReadout").textContent=cycle?`${cycle.user_id} • ${cycle.decision_action.toUpperCase()} • t=${Number(cycle.timestamp_s).toFixed(0)}s`:`Actual project topology • t=${Number(topology.timestamp_s??0).toFixed(0)}s • awaiting live execution`;$("mapStateBadge").textContent=cycle?"LIVE RUNTIME STATE":"ACTUAL PROJECT STATE";
}


function drawTelemetryLarge(){
  const canvas = $("telemetryMarginChart");
  if (!canvas) return;
  const {ctx,w,h} = resizeCanvas(canvas);
  ctx.clearRect(0,0,w,h);
  if (!events.length) {
    ctx.fillStyle = "#5d768c"; ctx.font = "11px Segoe UI";
    ctx.fillText("Run the live demo to render actual selected-resource telemetry.", 18, 40);
    return;
  }
  const vals = events.map(e => Number(e.best_link_margin_db ?? 0));
  const max = Math.max(...vals, 1), min = Math.min(...vals, 0);
  ctx.strokeStyle = "#17344a"; ctx.lineWidth = 1;
  for (let i=0;i<5;i++) { const y=20+(h-50)*i/4; ctx.beginPath(); ctx.moveTo(52,y); ctx.lineTo(w-18,y); ctx.stroke(); }
  ctx.strokeStyle = "#41e7a3"; ctx.lineWidth = 2.4; ctx.beginPath();
  vals.forEach((v,i)=>{ const x=52+(w-70)*(i/Math.max(vals.length-1,1)); const y=20+(h-50)*(1-(v-min)/Math.max(max-min,1)); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.stroke();
  ctx.fillStyle="#668196"; ctx.font="9px Segoe UI";
  ctx.fillText(`${max.toFixed(1)} dB`, 7, 24);
  ctx.fillText(`${min.toFixed(1)} dB`, 7, h-27);
  ctx.fillText("actual execution cycle →", w-145, h-9);
}

function drawMarginChart(){
  const canvas=$("marginChart"),{ctx,w,h}=resizeCanvas(canvas);ctx.clearRect(0,0,w,h);
  if(!events.length){ctx.fillStyle="#5d768c";ctx.font="11px Segoe UI";ctx.fillText("Run the demo to render actual selected-resource margin history.",18,40);return}
  const vals=events.map(e=>Number(e.best_link_margin_db||0)), max=Math.max(...vals,1), min=Math.min(...vals,0),pad={l:42,r:18,t:18,b:28};
  ctx.strokeStyle="#17344a";ctx.lineWidth=1;for(let i=0;i<4;i++){const y=pad.t+(h-pad.t-pad.b)*i/3;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke()}
  ctx.strokeStyle="#41e7a3";ctx.lineWidth=2.2;ctx.beginPath();vals.forEach((v,i)=>{const x=pad.l+(w-pad.l-pad.r)*(i/Math.max(vals.length-1,1)),y=pad.t+(h-pad.t-pad.b)*(1-(v-min)/Math.max(max-min,1));i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();
  ctx.fillStyle="#668196";ctx.font="9px Segoe UI";ctx.fillText(`${max.toFixed(0)} dB`,6,19);ctx.fillText(`${min.toFixed(0)} dB`,6,h-pad.b);ctx.fillText("execution cycle →",w-105,h-8);
}

function updatePipeline(c){
  ["s1","s2","s3","s4","s5"].forEach(id=>$(id).className="done");
  $("s3").className="live";
  if(["attach","handover"].includes(c.decision_action))$("s4").className="live";
  if(c.verification_passed)$("s5").className="done";
  $("cycleLabel").textContent=`LIVE • cycle ${events.length}/24 • t=${Number(c.timestamp_s).toFixed(0)}s`;
}

function addEvent(c){
  const div=document.createElement("div");div.className=`event ${c.decision_action}`;
  const t=`t=${Number(c.timestamp_s).toFixed(0)}s`;let text=`${c.user_id}: ${c.decision_action.toUpperCase()} → ${c.selected_resource_id||"NO COVERAGE"}`;if(c.decision_reason)text+=` · ${c.decision_reason}`;if(c.verification_passed)text+=" · verified";
  div.innerHTML=`<span class="time">${t}</span>${esc(text)}`;$("events").prepend(div);while($("events").children.length>14)$("events").lastChild.remove();
}

function updateServing(){
  const map=new Map();events.forEach(e=>map.set(e.user_id,e));let rows="";
  [...map.values()].sort((a,b)=>a.user_id.localeCompare(b.user_id)).forEach(e=>rows+=`<tr><td>${esc(e.user_id)}</td><td>${esc(e.selected_resource_id||"—")}</td><td>${esc(domainLabel(e.selected_domain))}</td><td>${e.best_link_margin_db==null?"—":e.best_link_margin_db.toFixed(1)+" dB"}</td><td class="status">${e.verification_passed?"VERIFIED":"CHECK"}</td></tr>`);
  $("serving").innerHTML=rows;
}

function updateCounts(p){
  const s=p.summary||{};$("candidateCount").textContent=s.total_candidate_count??"15";$("availableCount").textContent=s.available_candidate_count??"—";$("groundCount").textContent=s.ground_candidate_count!=null?Math.round(s.ground_candidate_count/3):"2";$("airCount").textContent=s.air_candidate_count!=null?Math.round(s.air_candidate_count/3):"2";$("spaceCount").textContent=s.space_candidate_count!=null?Math.round(s.space_candidate_count/3):"1";$("userCount").textContent=s.total_user_count??"3";
}

function applyCycle(p){
  const c=p.cycle;current=c;events.push(c);summary=p.summary;
  $("statusChip").textContent=`● LIVE • cycle ${p.index+1}/${p.total_cycles} • t=${Number(p.cycle.timestamp_s).toFixed(0)}s`;$("evidenceChip").textContent=`● ${p.evidence_class}`;
  $("modeChip").textContent=p.mode==="sgp4"?"● Demo — Public SGP4":p.mode==="udp"?"● Demo — Localhost UDP":"● Demo — Deterministic";
  $("action").textContent=c.decision_action.toUpperCase();$("decisionBadge").textContent=c.decision_action.toUpperCase();$("user").textContent=c.user_id;
  $("current").textContent=c.previous_resource_id?`${c.previous_resource_id} (${domainLabel(c.previous_domain)})`:"Initial attach";$("best").textContent=c.selected_resource_id?`${c.selected_resource_id} (${domainLabel(c.selected_domain)})`:"No coverage";$("margin").textContent=c.best_link_margin_db==null?"—":`${c.best_link_margin_db.toFixed(2)} dB`;$("capacity").textContent=fmtBps(c.selected_capacity_bps);$("reason").textContent=c.decision_reason;
  $("candDemand").textContent=fmtBps(c.demand_bps);$("gate").textContent=c.telemetry_gate_open?"OPEN":"BLOCKED";$("gate").className=c.telemetry_gate_open?"ok":"";$("verify").textContent=c.verification_passed?"PASSED":"FAILED";$("verify").className=c.verification_passed?"ok":"";$("simtime").textContent=`${Number(c.timestamp_s).toFixed(0)} s`;$("evAction").textContent=c.handover_event_type||c.decision_action;$("evReason").textContent=c.verification_reason||c.decision_reason;
  $("health").textContent=pct(c.telemetry_health);$("healthbar").style.width=pct(c.telemetry_health);$("demand").textContent=pct(c.demand_satisfied?1:0);$("demandbar").style.width=c.demand_satisfied?"100%":"0%";$("actionRate").textContent=summary?pct(summary.autonomous_action_rate):"—";$("actionbar").style.width=summary?pct(summary.autonomous_action_rate):"0%";
  $("prevNode").textContent=c.previous_resource_id||"Initial";$("selectedNode").textContent=c.selected_resource_id||"No coverage";$("transitionType").textContent=c.decision_action.toUpperCase();$("transitionUser").textContent=c.user_id;
  $("prov").textContent=p.evidence_class;$("prop").textContent=p.propagation_model;$("eph").textContent=p.ephemeris_source;$("fingerprint").textContent=p.fingerprint;$("sourceMode").textContent=p.evidence_class;updateCounts(p);updatePipeline(c);addEvent(c);updateServing();
  $("telemetryHealthLarge") && ($("telemetryHealthLarge").textContent=pct(c.telemetry_health), $("telemetryHealthBarLarge").style.width=pct(c.telemetry_health));
  $("telemetryDemandLarge") && ($("telemetryDemandLarge").textContent=pct(c.demand_satisfied?1:0), $("telemetryDemandBarLarge").style.width=c.demand_satisfied?"100%":"0%");
  $("telemetryActionLarge") && ($("telemetryActionLarge").textContent=summary?pct(summary.autonomous_action_rate):"—", $("telemetryActionBarLarge").style.width=summary?pct(summary.autonomous_action_rate):"0%");
  $("pvCurrent") && ($("pvCurrent").textContent=c.previous_resource_id?`${c.previous_resource_id} (${domainLabel(c.previous_domain)})`:"Initial attach");
  $("pvSelected") && ($("pvSelected").textContent=c.selected_resource_id?`${c.selected_resource_id} (${domainLabel(c.selected_domain)})`:"No coverage");
  $("pvMargin") && ($("pvMargin").textContent=c.best_link_margin_db==null?"—":`${c.best_link_margin_db.toFixed(2)} dB`);
  $("pvCapacity") && ($("pvCapacity").textContent=fmtBps(c.selected_capacity_bps));
  $("pvGate") && ($("pvGate").textContent=c.telemetry_gate_open?"OPEN":"BLOCKED");
  $("pvVerify") && ($("pvVerify").textContent=c.verification_passed?"PASSED":"FAILED");
  if($("avCycle"))$("avCycle").textContent=`cycle ${events.length}/24`;
  ["av1","av2","av3","av4","av5"].forEach(id=>$(id)?.classList.remove("live","done"));
  ["av1","av2","av3","av4","av5"].forEach(id=>$(id)?.classList.add("done"));
  $("av3")?.classList.add("live");
  const av=$("avEvents"); if(av){const d=document.createElement("div");d.className=`event ${c.decision_action}`;d.textContent=`t=${Number(c.timestamp_s).toFixed(0)}s  ${c.user_id}: ${c.decision_action.toUpperCase()} → ${c.selected_resource_id||"NO COVERAGE"}`;av.prepend(d);while(av.children.length>16)av.lastChild.remove();}
  drawGlobe(p.topology,c); drawMarginChart(); drawTelemetryLarge(); loadCandidates(c,p.mode);
}

async function loadCandidates(c,mode){
  const key=`${mode}:${c.timestamp_s}:${c.user_id}`;if(candidateCacheKey===key)return;candidateCacheKey=key;
  $("candidateCaption").textContent=`${c.user_id} • t=${Number(c.timestamp_s).toFixed(0)}s`;$ ("candidateRows").innerHTML="<tr><td colspan='5'>Loading actual Phase 76 candidate set…</td></tr>";
  try{
    const r=await fetch(`/api/candidates?mode=${mode}&time=${encodeURIComponent(c.timestamp_s)}&user=${encodeURIComponent(c.user_id)}`);if(!r.ok)throw new Error(`HTTP ${r.status}`);const d=await r.json();
    const availableForUser=d.candidates.filter(x=>x.available).length;
    $("availableCount").textContent=String(availableForUser);
    $("candidateMetaText").textContent=`${d.candidates.length} actual candidates • ${availableForUser} available for ${c.user_id} • selected: ${d.selected_resource_id||"none"} • demand: ${fmtBps(d.demand_bps)}`;
    $("candidateRows").innerHTML=d.candidates.map(x=>`<tr class="${x.resource_id===d.selected_resource_id?'selected':''}"><td>${esc(x.resource_id)}</td><td>${esc(domainLabel(x.domain))}</td><td class="${x.available?'available':'unavailable'}">${x.available?'AVAILABLE':'UNAVAILABLE'}</td><td>${Number(x.link_margin_db).toFixed(1)} dB</td><td>${fmtBps(x.estimated_capacity_bps??x.shannon_capacity_bps)}</td></tr>`).join("");
    if($("pvCandidateMeta"))$("pvCandidateMeta").textContent=`${d.candidates.length} actual candidates • ${availableForUser} available for ${c.user_id} • selected: ${d.selected_resource_id||"none"} • demand: ${fmtBps(d.demand_bps)}`;
    if($("pvCandidateRows"))$("pvCandidateRows").innerHTML=$("candidateRows").innerHTML;
  }catch(err){$("candidateMetaText").textContent="Actual candidate set unavailable for this cycle.";$("candidateRows").innerHTML=`<tr><td colspan='5'>${esc(err.message)}</td></tr>`;}
}

async function initializeMap(mode = "synthetic") {
  try {
    const r = await fetch(`/api/topology?mode=${encodeURIComponent(mode)}&time=0`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const t = await r.json();
    lastTopology = t;
    drawGlobe(t, current);
    $("mapReadout").textContent = current
      ? `${current.user_id} • ${current.decision_action.toUpperCase()} • t=${Number(current.timestamp_s).toFixed(0)}s`
      : `Actual project topology • t=0s • event-driven live view`;
    $("geographyLabel").textContent = mapView === "regional"
      ? `REGIONAL VIEW • ${(t.center?.lat ?? 17.39).toFixed(3)}°N ${(t.center?.lon ?? 78.49).toFixed(3)}°E`
      : `GLOBAL VIEW • NETWORK CENTER ${(t.center?.lat ?? 17.39).toFixed(3)}°N ${(t.center?.lon ?? 78.49).toFixed(3)}°E`;
  } catch (err) {
    $("mapReadout").textContent = `Topology unavailable: ${err.message}`;
  }
}

function start(){
  if(source)source.close();events=[];current=null;candidateCacheKey="";$("events").innerHTML="";$("candidateRows").innerHTML="";$("runBtn").disabled=true;$("statusChip").textContent="● Starting";
  source=new EventSource(`/api/events?mode=${$("mode").value}`);
  source.onmessage=e=>{const p=JSON.parse(e.data);if(p.type==="start"){summary=p.summary;updateCounts(p);$("statusChip").textContent=`● LIVE • cycle 0/${p.summary?.cycle_count ?? 24}`;$("prov").textContent=p.evidence_class;$("prop").textContent=p.propagation_model;$("eph").textContent=p.ephemeris_source;$("fingerprint").textContent=p.fingerprint;$("sourceMode").textContent=p.evidence_class;$("candidateMetaText").textContent=`${p.summary.total_candidate_count??15} total candidates across ${p.summary.total_user_count??3} users.`;if(p.topology){lastTopology=p.topology;drawGlobe(p.topology,current);}return;}if(p.type==="cycle"){applyCycle(p);return}if(p.type==="complete"){$("statusChip").textContent=`● Complete • ${p.summary?.cycle_count ?? 24} cycles`;$ ("runBtn").disabled=false;source.close()}};
  source.onerror=()=>{$("statusChip").textContent="● Connection ended";$ ("runBtn").disabled=false;if(source)source.close()};
}

async function runResilience(){
  const btn=$("resilienceBtn");if(!btn)return;btn.disabled=true;btn.textContent="⟳ Running actual Phase 78…";const mode=$("mode").value;$("resilienceEvents").innerHTML="";
  try{
    const res=await fetch(`/api/resilience?mode=${mode}`);if(!res.ok)throw new Error(`HTTP ${res.status}`);const report=await res.json();const s=report.summary;
    $("rScenarios").textContent=s.scenario_count;$("rCycles").textContent=s.cycle_count;$("rRecovered").textContent=`${s.recovered_scenario_count}/${s.scenario_count}`;$("rHandovers").textContent=s.handover_count;$("rVerify").textContent=pct(s.verification_success_ratio);$("rDemand").textContent=pct(s.demand_satisfaction_ratio);$("rLatency").textContent=s.mean_recovery_latency_s==null?"—":`${Number(s.mean_recovery_latency_s).toFixed(2)} s`;$("rMaxLatency").textContent=s.max_recovery_latency_s==null?"—":`${Number(s.max_recovery_latency_s).toFixed(0)} s`;
    $("scenarioRows").innerHTML=report.scenarios.map(sc=>`<tr><td>${esc(sc.scenario_id)}</td><td>${esc(sc.failure_mode)}</td><td>${sc.cycle_count}</td><td class="${sc.recovery_observed?'recovered':'warning'}">${sc.recovery_observed?'RECOVERED':'NOT RECOVERED'}</td><td>${sc.verification_pass_count}/${sc.verification_pass_count+sc.verification_fail_count}</td><td>${pct(sc.demand_satisfaction_ratio)}</td></tr>`).join("");
    const all=[];for(const sc of report.scenarios){const first=sc.cycles.find(c=>c.failure_active);if(first)all.push({t:first.timestamp_s,text:`${sc.scenario_id}: fault active · ${sc.failure_mode}`,cls:"fault"});if(sc.handover_count)all.push({t:sc.end_time_s,text:`${sc.scenario_id}: ${sc.handover_count} handover(s) observed`,cls:"info"});all.push({t:sc.recovery_time_s??sc.end_time_s,text:`${sc.scenario_id}: ${sc.recovery_observed?'recovery verified':'recovery not observed'}`,cls:sc.recovery_observed?"recovery":"failure"})}
    all.sort((a,b)=>a.t-b.t).forEach(e=>{const d=document.createElement("div");d.className=`event ${e.cls}`;d.innerHTML=`<span class="time">t=${Number(e.t).toFixed(0)}s</span>${esc(e.text)}`;$("resilienceEvents").appendChild(d)});
    if(lastTopology) drawGlobe(lastTopology, current);
    else await initializeMap(mode);
    $("statusChip").textContent=`● Resilience complete · ${s.recovered_scenario_count}/${s.scenario_count} recovered`;$("evidenceChip").textContent=`● ${report.evidence_class}`;$("prov").textContent=report.evidence_class;$("prop").textContent=report.propagation_model;$("eph").textContent=report.ephemeris_source;$("fingerprint").textContent=report.integration_fingerprint;
  }catch(err){const d=document.createElement("div");d.className="event failure";d.textContent=`Resilience run failed: ${err}`;$("resilienceEvents").appendChild(d)}finally{btn.disabled=false;btn.textContent="▶ Run Resilience Campaign"}
}

$("runBtn").onclick=start;$("resilienceBtn")?.addEventListener("click",runResilience);
document.querySelectorAll(".nav[data-view]").forEach(nav => nav.addEventListener("click", (ev) => { ev.preventDefault(); setWorkspace(nav.dataset.view); }));

$("orbitToggle")?.addEventListener("click",()=>{showOrbit=!showOrbit;$("orbitToggle").classList.toggle("active",showOrbit);if(lastTopology)drawGlobe(lastTopology,current)});
document.querySelectorAll(".view-btn[data-view]").forEach(btn=>btn.addEventListener("click",()=>{mapView=btn.dataset.view;document.querySelectorAll(".view-btn[data-view]").forEach(b=>b.classList.toggle("active",b===btn));if(lastTopology)drawGlobe(lastTopology,current)}));
window.addEventListener("resize",()=>{if(lastTopology && (activeWorkspace==="overview"||activeWorkspace==="network"))drawGlobe(lastTopology,current);drawMarginChart();if(activeWorkspace==="telemetry")drawTelemetryLarge();});
setWorkspace("overview");
drawMarginChart();
loadWorldMap().then(()=>initializeMap($("mode").value));
$("mode").addEventListener("change",()=>{events=[];current=null;candidateCacheKey="";$("events").innerHTML="";$("candidateRows").innerHTML="";$("availableCount").textContent="—";initializeMap($("mode").value);});
