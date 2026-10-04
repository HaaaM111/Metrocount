/* Home page panel logic. Map interactions are handled by map-core.js (window.MetroMap). */
const originLineSelect = document.querySelector('#origin-line-select');
const destinationLineSelect = document.querySelector('#destination-line-select');
const originSelect = document.querySelector('#origin-select');
const destinationSelect = document.querySelector('#destination-select');
const results = document.querySelector('#fare-results');
const resultCount = document.querySelector('#result-count');
const resetButton = document.querySelector('#reset-button');
const searchInput = document.querySelector('#station-search');
const searchResults = document.querySelector('#search-results');

let groupsData = [];
let searchData = [];
try {
  groupsData = JSON.parse(document.querySelector('#groups-data').textContent);
  searchData = JSON.parse(document.querySelector('#search-data').textContent);
} catch (e) { /* data missing */ }

function chipTextColor(bg) {
  const m = /#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i.exec(bg || '');
  if (!m) return '#fff';
  const lum = 0.299 * parseInt(m[1], 16) + 0.587 * parseInt(m[2], 16) + 0.114 * parseInt(m[3], 16);
  return lum > 160 ? '#1f2328' : '#fff';
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

let currentMainSegments = null;

function renderTrip(t, alternatives) {
  const meta = [];
  if (t.distance_km != null) meta.push(`全程约 ${esc(t.distance_km)} 公里`);
  if (t.minutes != null) meta.push(`约 ${esc(t.minutes)} 分钟`);
  if (t.transfers != null) meta.push(t.transfers === 0 ? '直达' : `换乘 ${esc(t.transfers)} 次`);
  const segHtml = (segs) => (segs || []).map((seg) => {
    const bg = seg.color || '#666';
    const fg = chipTextColor(bg);
    return `
    <div class="seg">
      <span class="seg-line" style="background:${bg};color:${fg}">${esc(seg.line)}</span>
      <span class="seg-route">${esc(seg.from)} → ${esc(seg.to)}</span>
      <span class="seg-stops">${esc(seg.stopCount)} 站</span>
    </div>`;
  }).join('');
  const segmentsHtml = segHtml(t.segments);
  currentMainSegments = t.segments || null;

  resultCount.textContent = '行程票价';
  results.className = 'fare-results trip-view';
  results.innerHTML = `
    <div class="trip-card">
      <div class="trip-route">
        <div class="trip-endpoint"><span class="trip-label">出发</span><strong>${esc(t.origin)}</strong></div>
        <div class="trip-arrow">→</div>
        <div class="trip-endpoint"><span class="trip-label">到达</span><strong>${esc(t.destination)}</strong></div>
      </div>
      <div class="trip-meta">${meta.join(' · ')}</div>
      <div class="trip-detail">
        <span class="trip-fare">¥${t.fare}</span>
      </div>
      ${segmentsHtml ? `<div class="trip-segments"><div class="trip-segments-title">乘坐方案</div>${segmentsHtml}</div>` : ''}
    </div>`;
  if (t.segments && t.segments.length) MetroMap.showRoute(t.segments);

  (alternatives || []).forEach((alt) => {
    const fastNames = [];
    (alt.segments || []).forEach((s) => {
      if (s.line === '磁悬浮') fastNames.push('磁悬浮');
      else if (s.line === '市域机场线') fastNames.push('机场线');
    });
    const fastLabel = fastNames.length ? [...new Set(fastNames)].join(' / ') : '更快';
    results.insertAdjacentHTML('beforeend', `
      <details class="alt-plan">
        <summary>备选方案 · ${fastLabel}（约 ${alt.minutes} 分钟 · ¥${alt.fare}，更快）</summary>
        <div class="trip-segments"><div class="trip-segments-title">备选乘坐方案</div>${segHtml(alt.segments)}</div>
      </details>`);
    results.querySelector('.alt-plan:last-of-type').addEventListener('toggle', (e) => {
      MetroMap.showRoute(e.target.open ? alt.segments : currentMainSegments);
    });
  });
}

function renderFares(data) {
  if (data.trip) {
    renderTrip(data.trip, data.alternatives || []);
    return;
  }
  MetroMap.clearRoute();
  resultCount.textContent = `从 ${data.origin.name} 出发 · ${data.fares.length} 个可达站点`;
  if (!data.fares.length) {
    results.className = 'fare-results empty-state';
    results.textContent = '当前组合暂无可用线路数据。';
    return;
  }
  results.className = 'fare-results fare-grid';
  results.innerHTML = data.fares.map((item) => `
    <div class="fare-card">
      <span class="fare-price">¥${esc(item.fare)}</span>
      <strong>${esc(item.name)}</strong>
      <span>${esc(item.line)} · ${esc(item.distance_km)} km</span>
    </div>`).join('');
}

/* ---- two-level selectors ---- */
function populateStations(lineSelect, stationSelect) {
  const line = lineSelect.value;
  stationSelect.innerHTML = '<option value="">' + (stationSelect === originSelect ? '请选择站点' : '请选择终点') + '</option>';
  if (!line) return;
  const group = groupsData.find((g) => g.line === line);
  if (!group) return;
  group.stations.forEach((s) => {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.label;
    stationSelect.appendChild(opt);
  });
}

function setStation(side, lineName, stationId) {
  const lineSel = side === 'origin' ? originLineSelect : destinationLineSelect;
  const stSel = side === 'origin' ? originSelect : destinationSelect;
  lineSel.value = lineName;
  populateStations(lineSel, stSel);
  stSel.value = String(stationId);
  if (MetroMap.setPick) MetroMap.setPick(side, lineName, stationId);
  loadFares();
}

let fareReqSeq = 0;

function loadFares() {
  const origin = originSelect.value;
  const destination = destinationSelect.value;
  if (!origin) {
    resultCount.textContent = '请选择起点和终点';
    results.className = 'fare-results empty-state';
    results.textContent = '选择起点和终点后，显示参考票价与乘坐方案。';
    return;
  }
  if (!destination) {
    resultCount.textContent = '请选择终点';
    results.className = 'fare-results empty-state';
    results.textContent = '选择终点后，显示参考票价与乘坐方案。';
    return;
  }
  results.className = 'fare-results empty-state';
  results.textContent = '正在计算参考票价…';
  const seq = ++fareReqSeq;
  fetch(`/api/stations/${origin}/fares/?destination=${destination}`)
    .then((response) => response.json())
    .then((data) => {
      if (seq !== fareReqSeq) return;
      renderFares(data);
    })
    .catch(() => {
      if (seq !== fareReqSeq) return;
      resultCount.textContent = '加载失败';
      results.textContent = '无法加载票价，请确认 Django 服务正在运行。';
    });
}

function resetAll() {
  originLineSelect.value = '';
  destinationLineSelect.value = '';
  populateStations(originLineSelect, originSelect);
  populateStations(destinationLineSelect, destinationSelect);
  searchInput.value = '';
  closeSearch();
  MetroMap.clearPicks();
  MetroMap.clearRoute();
  loadFares();
}

/* ---- search ---- */
function closeSearch() {
  searchResults.hidden = true;
  searchResults.innerHTML = '';
}

function renderSearch(keyword) {
  const kw = keyword.trim();
  if (!kw) { closeSearch(); return; }
  const hits = searchData.filter((s) => s.name.includes(kw)).slice(0, 15);
  if (!hits.length) {
    searchResults.hidden = false;
    searchResults.innerHTML = '<div class="search-empty">未找到匹配站点</div>';
    return;
  }
  searchResults.hidden = false;
  searchResults.innerHTML = hits.map((s) => {
    const firstId = s.ids[s.lines[0]];
    const chips = s.lines.map((l) =>
      `<span class="si-line" data-line="${esc(l)}" data-id="${esc(s.ids[l])}">${esc(l)}</span>`).join('');
    return `
      <div class="search-item">
        <div class="si-top">
          <span class="si-name">${esc(s.name)}</span>
          <span class="si-chips">${chips}</span>
        </div>
        <div class="si-actions">
          <button type="button" class="si-btn si-origin" data-line="${esc(s.lines[0])}" data-id="${esc(firstId)}">设为起点</button>
          <button type="button" class="si-btn si-dest" data-line="${esc(s.lines[0])}" data-id="${esc(firstId)}">设为终点</button>
        </div>
      </div>`;
  }).join('');

  searchResults.querySelectorAll('.si-origin').forEach((b) =>
    b.addEventListener('click', () => { setStation('origin', b.dataset.line, b.dataset.id); closeSearch(); }));
  searchResults.querySelectorAll('.si-dest').forEach((b) =>
    b.addEventListener('click', () => { setStation('destination', b.dataset.line, b.dataset.id); closeSearch(); }));
  searchResults.querySelectorAll('.si-line').forEach((c) =>
    c.addEventListener('click', () => { setStation('origin', c.dataset.line, c.dataset.id); closeSearch(); }));
}

searchInput.addEventListener('input', () => renderSearch(searchInput.value));
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const first = searchResults.querySelector('.si-origin');
    if (first) { first.click(); e.preventDefault(); }
  }
  if (e.key === 'Escape') { searchInput.value = ''; closeSearch(); }
});
document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-box')) closeSearch();
});

originLineSelect.addEventListener('change', () => {
  populateStations(originLineSelect, originSelect);
  MetroMap.setPick('origin', '', '');
});
destinationLineSelect.addEventListener('change', () => {
  populateStations(destinationLineSelect, destinationSelect);
  MetroMap.setPick('destination', '', '');
});
originSelect.addEventListener('change', () => {
  MetroMap.setPick('origin', originLineSelect.value, originSelect.value);
  loadFares();
});
destinationSelect.addEventListener('change', () => {
  MetroMap.setPick('destination', destinationLineSelect.value, destinationSelect.value);
  loadFares();
});
resetButton.addEventListener('click', resetAll);

/* ---- init MetroMap (home: display-only, no station picking) ---- */
MetroMap.init({ interactive: false });

/* ---- URL params: ?origin=<id>&destination=<id> auto-fill ---- */
(function initFromURL() {
  const params = new URLSearchParams(location.search);
  const oid = params.get('origin');
  const did = params.get('destination');
  if (!oid || !did) return;
  // find station meta by id across groups
  let oLine = null, dLine = null;
  for (const g of groupsData) {
    if (g.stations.some((s) => String(s.id) === String(oid))) oLine = g.line;
    if (g.stations.some((s) => String(s.id) === String(did))) dLine = g.line;
  }
  if (oLine) setStation('origin', oLine, oid);
  if (dLine) setStation('destination', dLine, did);
})();
