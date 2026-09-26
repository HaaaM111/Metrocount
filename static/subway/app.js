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
  const meta = [];  if (t.distance_km != null) meta.push(`全程约 ${esc(t.distance_km)} 公里`);
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
  if (t.segments && t.segments.length) highlightRoute(t.segments);

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
      highlightRoute(e.target.open ? alt.segments : currentMainSegments);
    });
  });
}

function renderFares(data) {
  if (data.trip) {
    renderTrip(data.trip, data.alternatives || []);
    return;
  }
  clearRouteHighlight();
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

/* ---- Two-level: line select then station select ---- */
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
  loadFares();
}

let fareReqSeq = 0;   // 竞态防护：只渲染最后一次请求的结果

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
      if (seq !== fareReqSeq) return;   // 已有更新的请求，丢弃过期响应
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
  clearRouteHighlight();
  loadFares();
}

function normalize(name) {
  return String(name || '').replace(/[（(].*?[)）]/g, '').trim();
}

/* ---- route highlight on the network map ----
   after a trip plan is shown, fade everything outside the ridden route;
   each ridden segment is drawn in its line's color, transfer stations stand out */

/* 预构建站名索引：站名(规范化) -> {cx, cy, 元素列表}，避免高亮时反复全量扫描 SVG */
const stationIndex = (() => {
  const svg = document.querySelector('.map-wrap svg');
  const idx = new Map();
  if (!svg) return idx;
  svg.querySelectorAll('[data-name]').forEach((el) => {
    const n = normalize(el.getAttribute('data-name'));
    if (!idx.has(n)) idx.set(n, { cx: null, cy: null, els: [] });
    const rec = idx.get(n);
    rec.els.push(el);
    if ((el.tagName === 'circle' || el.tagName === 'ellipse') && rec.cx === null) {
      rec.cx = parseFloat(el.getAttribute('cx'));
      rec.cy = parseFloat(el.getAttribute('cy'));
    }
  });
  return idx;
})();
function clearRouteHighlight() {
  const svg = document.querySelector('.map-wrap svg');
  if (!svg) return;
  const hl = svg.querySelector('g[data-role="route-highlight"]');
  if (!hl) return;   // 无高亮时不触碰任何元素，避免无谓全量遍历
  hl.remove();
  svg.querySelectorAll('path, ellipse, circle, text').forEach((el) => {
    el.style.opacity = '';
  });
}

function nearestLenOnPath(path, coord) {
  const total = path.getTotalLength();
  let bestLen = 0, bestDist = Infinity;
  const steps = Math.max(80, Math.floor(total / 8));
  for (let i = 0; i <= steps; i++) {
    const d = total * i / steps;
    const pt = path.getPointAtLength(d);
    const dist = Math.hypot(pt.x - coord[0], pt.y - coord[1]);
    if (dist < bestDist) { bestDist = dist; bestLen = d; }
  }
  return bestDist < 60 ? bestLen : null;
}

function highlightRoute(segments) {
  const svg = document.querySelector('.map-wrap svg');
  if (!svg || !segments || !segments.length) return;
  clearRouteHighlight();
  const NS = 'http://www.w3.org/2000/svg';

  // line name -> Baidu map color
  const lineColor = {};
  groupsData.forEach((g) => { if (g.color) lineColor[g.line] = g.color; });

  // fade everything by default
  svg.querySelectorAll('path').forEach((p) => { p.style.opacity = '0.10'; });
  svg.querySelectorAll('ellipse').forEach((e) => { e.style.opacity = '0.22'; });
  svg.querySelectorAll('circle[data-name], .line-badge circle').forEach((c) => { c.style.opacity = '0.22'; });
  svg.querySelectorAll('text').forEach((t) => { t.style.opacity = '0.30'; });

  const g = document.createElementNS(NS, 'g');
  g.setAttribute('data-role', 'route-highlight');
  g.style.pointerEvents = 'none';
  svg.appendChild(g);

  const coordOf = (name) => {
    const rec = stationIndex.get(normalize(name));
    return rec && rec.cx !== null ? [rec.cx, rec.cy] : null;
  };
  const restoreStation = (name) => {
    const rec = stationIndex.get(normalize(name));
    if (rec) rec.els.forEach((el) => { el.style.opacity = '1'; });
  };

  // 不新画直线，直接把乘坐线路已有的 metro-line path 高亮（沿真实走向）
  const rideColors = new Set();
  segments.forEach((seg) => {
    const c = lineColor[seg.line];
    if (c) rideColors.add(String(c).toUpperCase());
    (seg.stations || []).forEach((n) => restoreStation(n));
  });
  


segments.forEach((seg, si) => {
  const col = lineColor[seg.line];
  const startC = coordOf(seg.stations[0]);
  const endC   = coordOf(seg.stations[seg.stations.length - 1]);
  if (!startC || !endC) return;

  // 找该线路所有同色 path
  svg.querySelectorAll('path.metro-line').forEach((p) => {
    if ((p.getAttribute('stroke') || '').toUpperCase() !== String(col).toUpperCase()) return;
    const total = p.getTotalLength();
    const sLen = nearestLenOnPath(p, startC);
    const eLen = nearestLenOnPath(p, endC);
    if (sLen == null || eLen == null) return;       // 这段 path 不经过这两个站
    let a = sLen < eLen ? sLen : eLen;
    let b = sLen < eLen ? eLen : sLen;
    const forward = b - a;
    const backward = total - forward;

    const clone = p.cloneNode(true);
    clone.style.opacity = '1';
    clone.setAttribute('stroke-width', '12');
    if(backward < forward){
      clone.style.strokeDasharray = `${backward} ${forward}`;
      clone.style.strokeDashoffset = `${-b}`;
    }else{
      clone.style.strokeDasharray = `${forward} ${backward}`;
      clone.style.strokeDashoffset = `${-a}`;
    }
    g.appendChild(clone);
  });

  // 换乘站高亮：黑圈 + 当前线路色芯
  if (si < segments.length - 1) {
    const tName = seg.stations[seg.stations.length - 1];
    const tCoord = coordOf(tName);
    if (tCoord) {
      restoreStation(tName);
      const ring = document.createElementNS(NS, 'circle');
      ring.setAttribute('cx', tCoord[0]); ring.setAttribute('cy', tCoord[1]);
      ring.setAttribute('r', '16'); ring.setAttribute('fill', '#ffffff');
      ring.setAttribute('stroke', '#1f2328'); ring.setAttribute('stroke-width', '3');
      g.appendChild(ring);
      const dot = document.createElementNS(NS, 'circle');
      dot.setAttribute('cx', tCoord[0]); dot.setAttribute('cy', tCoord[1]);
      dot.setAttribute('r', '7'); dot.setAttribute('fill', col);
      g.appendChild(dot);
    }
  }
});

}

/* ---- Search system ---- */
function closeSearch() {
  searchResults.hidden = true;
  searchResults.innerHTML = '';
}

function renderSearch(keyword) {
  const kw = keyword.trim();
  if (!kw) { closeSearch(); return; }
  const hits = searchData
    .filter((s) => s.name.includes(kw))
    .slice(0, 15);
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
  // Clicking a line chip sets that line's station as origin
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
    if (window.syncMapHighlight) syncMapHighlight('origin', '', '');
  });
destinationLineSelect.addEventListener('change', () => {
    populateStations(destinationLineSelect, destinationSelect);
    if (window.syncMapHighlight) syncMapHighlight('destination', '', '');
  });
originSelect.addEventListener('change', () => {
    if (window.syncMapHighlight) syncMapHighlight('origin', originLineSelect.value, originSelect.value);
    loadFares();
  });
destinationSelect.addEventListener('change', () => {
    if (window.syncMapHighlight) syncMapHighlight('destination', destinationLineSelect.value, destinationSelect.value);
    loadFares();
  });
resetButton.addEventListener('click', resetAll);

/* ---- network map zoom (density-aware) ----
   default: fit whole network; only major hubs and line badges are labelled.
   zooming in reveals transfer-station names, then every station name;
   wheel zooms toward cursor; double-click / 全图 resets to the full network. */
(function () {
  const wrap = document.querySelector('.map-wrap');
  if (!wrap) return;
  const svg = wrap.querySelector('svg');
  if (!svg) return;
  svg.style.willChange = 'transform';
  const vb = svg.viewBox.baseVal;
  const vbW = vb.width || 4405;
  const vbH = vb.height || 5921;
  const vbX = vb.x || 118, vbY = vb.y || 42;
  const CITY = [2475.6, 2543.6];   // 人民广场（路网实际中心）
  const FONT = 22;                 // 与 gen_baidu_map.py 的站名用户字号一致
  let zoom = 1;
  let mode = 'fill';
  let centeredCity = false;

  function render() {
    if (mode === 'fit' || mode === 'fill') {
      svg.style.width = '100%';
      svg.style.height = '100%';
      wrap.scrollLeft = 0;
      wrap.scrollTop = 0;
      svg.setAttribute('preserveAspectRatio', mode === 'fill' ? 'xMidYMid slice' : 'xMidYMid meet');
    } else {
      svg.style.width = (100 * zoom) + '%';
      svg.style.height = 'auto';
      svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    }
    // s = 1 用户单位对应的屏幕 px；fill 为 slice 填满（取宽高较大者），fit 为 meet 全图（取较小者）
    const sByW = svg.clientWidth / vbW;
    const s = mode === 'fill' ? Math.max(sByW, svg.clientHeight / vbH) : Math.min(sByW, svg.clientHeight / vbH);
    const f = FONT * s;
    const density = 'high';             // 全部站名常显，不突出枢纽
    svg.dataset.density = density;
    const lblScale = Math.max(1, 10 / f);
    svg.style.setProperty('--lbl-scale', lblScale.toFixed(3));
    svg.style.setProperty('--badge-scale', (9 / (20 * s)).toFixed(3));
    svg.style.setProperty('--dot-scale', density === 'low' ? '0.62' : '1');
  }

  // 整图首次放大时，把市中心（人民广场）放到视口中央
  function centerCity() {
    if (centeredCity) return;
    centeredCity = true;
    const s = svg.clientWidth / vbW;
    const px = (CITY[0] - vbX) * s;
    const py = (CITY[1] - vbY) * s;
    wrap.scrollLeft = Math.max(0, px - wrap.clientWidth / 2);
    wrap.scrollTop = Math.max(0, py - wrap.clientHeight / 2);
  }

  function zoomAt(prevZoom, mx, my, vx, vy) {
    wrap.scrollLeft = mx * (zoom / prevZoom) - vx;
    wrap.scrollTop = my * (zoom / prevZoom) - vy;
  }

  wrap.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const mx = e.clientX - rect.left + wrap.scrollLeft;
    const my = e.clientY - rect.top + wrap.scrollTop;
    const vx = e.clientX - rect.left;
    const vy = e.clientY - rect.top;
    const prevZoom = zoom;
    if (e.deltaY < 0) {
      const wasFit = mode === 'fit' || mode === 'fill';
      if (wasFit) { mode = 'full'; zoom = 1.05; }
      else zoom = Math.min(8, zoom * 1.08);
      render();
      if (wasFit) centerCity();
      else zoomAt(prevZoom, mx, my, vx, vy);
    } else if (mode === 'full') {
      zoom = zoom / 1.08;
      if (zoom <= 1) { mode = 'fill'; zoom = 1; render(); }
      else { render(); zoomAt(prevZoom, mx, my, vx, vy); }
    }
  }, { passive: false });

  wrap.addEventListener('dblclick', () => {
    mode = 'fit';
    zoom = 1;
    centeredCity = false;
    render();
  });

  const zoomIn = document.getElementById('map-zoom-in');
  const zoomOut = document.getElementById('map-zoom-out');
  const zoomFit = document.getElementById('map-fit');
  if (zoomIn) zoomIn.addEventListener('click', () => {
    const wasFit = mode === 'fit' || mode === 'fill';
    const rect = wrap.getBoundingClientRect();
    const mx = rect.width / 2 + wrap.scrollLeft;
    const my = rect.height / 2 + wrap.scrollTop;
    const prevZoom = zoom;
    if (wasFit) { mode = 'full'; zoom = 1.05; render(); centerCity(); }
    else { zoom = Math.min(8, zoom * 1.25); render(); zoomAt(prevZoom, mx, my, rect.width / 2, rect.height / 2); }
  });
  if (zoomOut) zoomOut.addEventListener('click', () => {
    if (mode !== 'full') return;
    const rect = wrap.getBoundingClientRect();
    const mx = rect.width / 2 + wrap.scrollLeft;
    const my = rect.height / 2 + wrap.scrollTop;
    const prevZoom = zoom;
    zoom = zoom / 1.25;
    if (zoom <= 1) { mode = 'fill'; zoom = 1; render(); }
    else { render(); zoomAt(prevZoom, mx, my, rect.width / 2, rect.height / 2); }
  });
  if (zoomFit) zoomFit.addEventListener('click', () => {
    mode = 'fit';
    zoom = 1;
    centeredCity = false;
    render();
  });

  window.addEventListener('resize', () => render());

  render();
})();

/* ---- click map station to pick origin / destination ----
   1st click on a station -> origin; 2nd click -> destination;
   clicking a non-station area resets the counter and clears selection */
(function () {
  const svg = document.querySelector('.map-wrap svg');
  if (!svg) return;
  const NS = 'http://www.w3.org/2000/svg';
  let clickCount = 0;
  let originMark = null, destMark = null;
  const colorToLine = {};
  groupsData.forEach((g) => { if (g.color) colorToLine[g.color] = g.line; });

  function removeMark(mark) {
    if (mark) { mark.ring.remove(); mark.dot.remove(); }
  }
  function clearHighlights() {
    removeMark(originMark); originMark = null;
    removeMark(destMark); destMark = null;
  }
  function placeHighlight(side, el) {
    removeMark(side === 'origin' ? originMark : destMark);
    let cx = null, cy = null;
    const tag = el.tagName;
    if (tag === 'ellipse' || tag === 'circle') {
      cx = parseFloat(el.getAttribute('cx'));
      cy = parseFloat(el.getAttribute('cy'));
    } else {
      // text element: use its station marker coordinates
      const name = el.getAttribute('data-name');
      const marker = svg.querySelector('circle[data-name="' + name + '"], ellipse[data-name="' + name + '"]');
      if (marker) {
        cx = parseFloat(marker.getAttribute('cx'));
        cy = parseFloat(marker.getAttribute('cy'));
      } else {
        cx = parseFloat(el.getAttribute('x'));
        cy = parseFloat(el.getAttribute('y')) - 8;
      }
    }
    if (cx == null || cy == null) return;
    const color = side === 'origin' ? '#FF6B00' : '#00A8FF';
    const ring = document.createElementNS(NS, 'circle');
    ring.setAttribute('cx', cx); ring.setAttribute('cy', cy);
    ring.setAttribute('r', '20'); ring.setAttribute('fill', 'none');
    ring.setAttribute('stroke', color); ring.setAttribute('stroke-width', '5');
    ring.style.pointerEvents = 'none';
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy);
    dot.setAttribute('r', '6'); dot.setAttribute('fill', color);
    dot.style.pointerEvents = 'none';
    svg.appendChild(ring); svg.appendChild(dot);
    const mark = { ring, dot };
    if (side === 'origin') originMark = mark; else destMark = mark;
  }

  function normalize(name) {
    return String(name || '').replace(/[（(].*?[)）]/g, '').trim();
  }

  function findStation(name, color) {
    const norm = normalize(name);
    const lineName = colorToLine[color];
    if (lineName) {
      const g = groupsData.find((x) => x.line === lineName);
      if (g) {
        const st = g.stations.find((s) => normalize(s.label) === norm);
        if (st) return { line: lineName, id: st.id };
      }
    }
    let hits = [];
    groupsData.forEach((g) => g.stations.forEach((s) => {
      if (normalize(s.label) === norm) hits.push({ line: g.line, id: s.id });
    }));
    if (hits.length === 1) return hits[0];
    return null;
  }

  function pick(e, name, color) {
    e.stopPropagation();
    const hit = findStation(name, color);
    if (!hit) return;
    clickCount += 1;
    if (clickCount === 1) {
      setStation('origin', hit.line, hit.id);
      placeHighlight('origin', e.currentTarget);
    } else if (clickCount === 2) {
      setStation('destination', hit.line, hit.id);
      placeHighlight('destination', e.currentTarget);
    } else {
      // 连续第三次点击：先自动重置全部选择，再以本次点击为新起点
      clickCount = 1;
      clearHighlights();
      resetAll();
      setStation('origin', hit.line, hit.id);
      placeHighlight('origin', e.currentTarget);
    }
  }

  function nearestLenOnPath(path, coord){
    const total = path.getTotalLength();
    let bestLen = 0, bestDist = Infinity;
    const steps = Math.max(80, Math.floor(total / 8));
    for (let i = 0; i <= steps; i++){
      const d = total * i / steps;
      const pt = path.getPointAtLength(d);
      const dist = Math.hypot(pt.x - coord[0], pt.y - coord[1]);
      if(dist < bestDist){
        bestDist = dist; bestLen = d;
      }
      return bestDist <60 ? bestLen : null;
    }
  }

  window.syncMapHighlight = function (side, lineName, stationId) {
    const svg = document.querySelector('.map-wrap svg');
    if (!svg) return;
    if (!stationId) {
      if (side === 'origin' && originMark) { removeMark(originMark); originMark = null; }
      if (side === 'destination' && destMark) { removeMark(destMark); destMark = null; }
      return;
    }
    const g = groupsData.find((x) => x.line === lineName);
    const st = g && g.stations.find((s) => String(s.id) === String(stationId));
    if (!st) return;
    const norm = normalize(st.label);
    let el = svg.querySelector('text[data-name="' + st.label + '"], circle[data-name="' + st.label + '"], ellipse[data-name="' + st.label + '"]');
    if (!el) {
      const all = svg.querySelectorAll('ellipse, circle, text');
      for (const n of all) {
        if (n.getAttribute('data-name') && normalize(n.getAttribute('data-name')) === norm) { el = n; break; }
      }
    }
    if (!el) return;
    placeHighlight(side, el);
  };

  svg.querySelectorAll('ellipse, circle, text').forEach((el) => {
    const name = el.getAttribute('data-name');
    if (!name) return;
    el.style.cursor = 'pointer';
    el.addEventListener('click', (e) => pick(e, name, el.getAttribute('data-color')));
  });

  svg.addEventListener('click', (e) => {
    const t = e.target;
    if (t === svg || t.tagName === 'path' || t.tagName === 'rect') {
      clickCount = 0;
      clearHighlights();
      resetAll();
    }
  });

  resetButton.addEventListener('click', clearHighlights);
})();
