/* Fullscreen pick-page logic: click stations to set origin/destination,
   show floating fare card, route highlights on the map.
   Card collapses to a floating ball when idle. */
const floatCard = document.querySelector('#map-result');
const floatContent = floatCard.querySelector('.float-content');
const floatBall = floatCard.querySelector('.float-ball');
const floatClose = floatCard.querySelector('.float-close');
const backBtn = document.querySelector('#map-back');
const hint = document.querySelector('#map-hint');

let groupsData = [];
try { groupsData = JSON.parse(document.querySelector('#groups-data').textContent); } catch (e) {}

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
    </div>`;
}

function setHint(picks) {
  if (picks.origin && picks.destination) hint.textContent = '已选好起终点，可再次点击站点重新开始';
  else if (picks.origin) hint.textContent = `起点：${picks.origin.name}，请点击终点`;
  else hint.textContent = '点击站点：第一次=起点，第二次=终点';
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
