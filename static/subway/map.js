/* Fullscreen pick-page logic: click stations to set origin/destination,
   show floating fare card, route highlights on the map.
   Card collapses to a floating ball when idle. */
const floatCard = document.querySelector('#map-result');
const floatContent = floatCard.querySelector('.float-content');
const floatBall = floatCard.querySelector('.float-ball');
const floatClose = floatCard.querySelector('.float-close');
const backBtn = document.querySelector('#map-back');
const hint = document.querySelector('#map-hint');
const quickSelect = document.querySelector('#map-quick');

let groupsData = [];
try { groupsData = JSON.parse(document.querySelector('#groups-data').textContent); } catch (e) {}

const LS_RECENT = 'metrocount_recent';
const LS_SAVED = 'metrocount_saved';

function readLS(key) {
  try { return JSON.parse(localStorage.getItem(key)) || []; }
  catch (e) { return []; }
}
function writeLS(key, arr) {
  try { localStorage.setItem(key, JSON.stringify(arr)); } catch (e) { /* storage unavailable */ }
}
function cleanName(label) {
  return String(label || '').replace(/（.*）/g, '');
}
function stationLabel(id) {
  for (const g of groupsData) {
    const s = g.stations.find((x) => String(x.id) === String(id));
    if (s) return s.label;
  }
  return '';
}
function lineOfStation(id) {
  for (const g of groupsData) {
    for (const s of g.stations) {
      if (String(s.id) === String(id)) return g.line;
    }
  }
  return '';
}
function isSaved(oid, did) {
  return readLS(LS_SAVED).some((x) => String(x.oid) === String(oid) && String(x.did) === String(did));
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
function chipTextColor(bg) {
  const m = /#([0-9a-f]{2})([0-9a-f]{2})/i.exec(bg || '');
  if (!m) return '#fff';
  const lum = 0.299 * parseInt(m[1], 16) + 0.587 * parseInt(m[2], 16) + 0.114 * parseInt(m[3], 16);
  return lum > 160 ? '#1f2328' : '#fff';
}

function minimizeFloat() { floatCard.classList.add('minimized'); }
function maximizeFloat() { floatCard.classList.remove('minimized'); }

function renderResult(data) {
  if (!data.trip) {
    floatContent.innerHTML = '<div class="float-empty">请在地图上选择起点和终点</div>';
    return;
  }
  const t = data.trip;
  const alts = data.alternatives || [];
  const picks = MetroMap.getPicks();
  const savedFlag = picks.origin && picks.destination && isSaved(picks.origin.id, picks.destination.id);
  const segs = (t.segments || []).map((s) => {
    const bg = s.color || '#666';
    const fg = chipTextColor(bg);
    return `<div class="seg"><span class="seg-line" style="background:${bg};color:${fg}">${esc(s.line)}</span><span class="seg-route">${esc(s.from)} → ${esc(s.to)}</span><span class="seg-stops">${esc(s.stopCount)} 站</span></div>`;
  }).join('');
  floatContent.innerHTML = `
    <div class="float-card-inner">
      <div class="float-head">
        <span class="float-fare">¥${t.fare}</span>
        <span class="float-meta">${esc(t.distance_km)} km · 约 ${esc(t.minutes)} 分钟 · ${t.transfers === 0 ? '直达' : '换乘 ' + esc(t.transfers) + ' 次'}</span>
      </div>
      <div class="float-route">${esc(t.origin)} → ${esc(t.destination)}</div>
      <div class="float-segs">${segs}</div>
      ${alts.map((a) => `
        <details class="alt-plan">
          <summary>备选 · ${a.maglev ? '磁悬浮' : '机场线'}（${a.minutes} min · ¥${a.fare}）</summary>
          <div class="float-segs">${(a.segments || []).map((s) => {
            const bg = s.color || '#666';
            const fg = chipTextColor(bg);
            return `<div class="seg"><span class="seg-line" style="background:${bg};color:${fg}">${esc(s.line)}</span><span class="seg-route">${esc(s.from)} → ${esc(s.to)}</span></div>`;
          }).join('')}</div>
        </details>`).join('')}
      <div class="float-actions">
        <button type="button" class="float-btn ${savedFlag ? 'saved' : ''}" id="fa-save">${savedFlag ? '★ 已收藏' : '☆ 收藏'}</button>
        <button type="button" class="float-btn" id="fa-swap" title="互换起点与终点">⇄ 互换</button>
        <button type="button" class="float-btn" id="fa-share" title="复制分享链接">复制链接</button>
      </div>
    </div>`;

  const saveBtn = floatContent.querySelector('#fa-save');
  if (saveBtn) saveBtn.addEventListener('click', () => {
    const saved = toggleSavedRoute(picks.origin.id, picks.destination.id);
    saveBtn.textContent = saved ? '★ 已收藏' : '☆ 收藏';
    saveBtn.classList.toggle('saved', saved);
  });
  const swapBtn = floatContent.querySelector('#fa-swap');
  if (swapBtn) swapBtn.addEventListener('click', swapPicks);
  const shareBtn = floatContent.querySelector('#fa-share');
  if (shareBtn) shareBtn.addEventListener('click', (e) => copyShareLink(picks.origin.id, picks.destination.id, e.target));
}

function setHint(picks) {
  if (picks.origin && picks.destination) hint.textContent = '已选好起终点，可再次点击站点重新开始';
  else if (picks.origin) hint.textContent = `起点：${picks.origin.name}，请点击终点`;
  else hint.textContent = '点击站点：第一次=起点，第二次=终点';
}

/* ---- 常用路线 / 最近查询 ---- */
function toggleSavedRoute(oid, did) {
  let arr = readLS(LS_SAVED);
  const saved = isSaved(oid, did);
  if (saved) {
    arr = arr.filter((x) => !(String(x.oid) === String(oid) && String(x.did) === String(did)));
  } else {
    const picks = MetroMap.getPicks();
    if (!picks.origin || !picks.destination) return false;
    arr.unshift({
      oid: String(oid), oline: picks.origin.line, oname: stationLabel(oid),
      did: String(did), dline: picks.destination.line, dname: stationLabel(did),
      ts: Date.now(),
    });
    arr = arr.slice(0, 10);
  }
  writeLS(LS_SAVED, arr);
  renderQuickSelect();
  return isSaved(oid, did);
}

function recordRecent(oid, did) {
  const oname = stationLabel(oid);
  const dname = stationLabel(did);
  if (!oname || !dname) return;
  const arr = readLS(LS_RECENT)
    .filter((x) => !(String(x.oid) === String(oid) && String(x.did) === String(did)));
  arr.unshift({
    oid: String(oid), oline: lineOfStation(oid), oname,
    did: String(did), dline: lineOfStation(did), dname,
    ts: Date.now(),
  });
  writeLS(LS_RECENT, arr.slice(0, 10));
  renderQuickSelect();
}

function renderQuickSelect() {
  if (!quickSelect) return;
  const saved = readLS(LS_SAVED);
  const recent = readLS(LS_RECENT);
  quickSelect.innerHTML = '<option value="">常用 / 最近</option>';
  const addGroup = (label, items, kind) => {
    if (!items.length) return;
    const og = document.createElement('optgroup');
    og.label = label;
    items.forEach((x, i) => {
      const o = document.createElement('option');
      o.value = `${kind}:${i}`;
      o.textContent = `${cleanName(x.oname)} → ${cleanName(x.dname)}`;
      og.appendChild(o);
    });
    quickSelect.appendChild(og);
  };
  addGroup('常用路线', saved, 'saved');
  addGroup('最近查询', recent, 'recent');
}

function applyQuickItem(item) {
  if (!item) return;
  MetroMap.clearPicks();
  MetroMap.setPick('origin', item.oline, item.oid);
  MetroMap.setPick('destination', item.dline, item.did);
  const picks = MetroMap.getPicks();
  setHint(picks);
  fetchFares(picks.origin, picks.destination);
}

quickSelect.addEventListener('change', () => {
  const v = quickSelect.value;
  quickSelect.value = '';
  if (!v) return;
  const parts = v.split(':');
  const kind = parts[0];
  const idx = parseInt(parts[1], 10);
  const item = (kind === 'saved' ? readLS(LS_SAVED) : readLS(LS_RECENT))[idx];
  applyQuickItem(item);
});

/* ---- 互换 ---- */
function swapPicks() {
  const picks = MetroMap.getPicks();
  if (!picks.origin || !picks.destination) return;
  const o = picks.origin;
  const d = picks.destination;
  MetroMap.clearPicks();
  MetroMap.setPick('origin', d.line, d.id);
  MetroMap.setPick('destination', o.line, o.id);
  const np = MetroMap.getPicks();
  setHint(np);
  fetchFares(np.origin, np.destination);
}

/* ---- 复制分享链接 ---- */
function copyShareLink(oid, did, btn) {
  const url = `${location.origin}/map/?origin=${oid}&destination=${did}`;
  const done = () => {
    if (btn) {
      const old = btn.textContent;
      btn.textContent = '已复制 ✓';
      setTimeout(() => { btn.textContent = old; }, 1600);
    }
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(done).catch(() => fallbackCopy(url, done));
  } else {
    fallbackCopy(url, done);
  }
}

function fallbackCopy(text, done) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); done(); }
  catch (e) { window.prompt('请手动复制分享链接：', text); }
  document.body.removeChild(ta);
}

let reqSeq = 0;
function fetchFares(origin, destination) {
  maximizeFloat();
  floatContent.innerHTML = '<div class="float-empty">查询中…</div>';
  const seq = ++reqSeq;
  fetch(`/api/stations/${origin.id}/fares/?destination=${destination.id}`)
    .then((r) => r.json())
    .then((data) => {
      if (seq !== reqSeq) return;
      renderResult(data);
      if (data.trip && data.trip.segments) MetroMap.showRoute(data.trip.segments);
      if (data.trip) recordRecent(origin.id, destination.id);
    })
    .catch(() => {
      if (seq !== reqSeq) return;
      floatContent.innerHTML = '<div class="float-empty">查询失败，请重试</div>';
    });
}

MetroMap.init({
  interactive: true,
  onPick(side, hit) {
    MetroMap.setPick(side, hit.line, hit.id);
    const picks = MetroMap.getPicks();
    setHint(picks);
    if (picks.origin && picks.destination) {
      fetchFares(picks.origin, picks.destination);
    } else {
      MetroMap.clearRoute();
      maximizeFloat();
      floatContent.innerHTML = '<div class="float-empty">请点击终点</div>';
    }
  },
  onReset() {
    MetroMap.clearRoute();
    floatContent.innerHTML = '<div class="float-empty">请在地图上选择起点和终点</div>';
    setHint({ origin: null, destination: null });
    minimizeFloat();
  },
});

/* ball expands, close button collapses */
floatBall.addEventListener('click', maximizeFloat);
floatClose.addEventListener('click', minimizeFloat);

/* back button carries current selection */
backBtn.addEventListener('click', (e) => {
  const picks = MetroMap.getPicks();
  if (picks.origin && picks.destination) {
    e.preventDefault();
    location.href = `/?origin=${picks.origin.id}&destination=${picks.destination.id}`;
  }
});

/* URL params: preselect stations */
(function initFromURL() {
  const params = new URLSearchParams(location.search);
  const oid = params.get('origin');
  const did = params.get('destination');
  if (!oid) return;
  let oLine = null, dLine = null, oName = null, dName = null;
  for (const g of groupsData) {
    const os = g.stations.find((s) => String(s.id) === String(oid));
    if (os) { oLine = g.line; oName = os.label; }
    const ds = g.stations.find((s) => String(s.id) === String(did));
    if (ds) { dLine = g.line; dName = ds.label; }
  }
  if (oLine) MetroMap.setPick('origin', oLine, oid);
  if (oLine && dLine && oid && did) {
    MetroMap.setPick('destination', dLine, did);
    setHint({ origin: { name: oName }, destination: { name: dName } });
    fetchFares({ id: oid }, { id: did });
  }
})();

renderQuickSelect();
