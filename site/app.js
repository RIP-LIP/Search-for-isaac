/* 以撒的结合 · 控制台指令速查 —— 前端 */

const $ = (s) => document.querySelector(s);
const grid = $('#grid');
const q = $('#q');
const clearBtn = $('#clearBtn');
const countEl = $('#count');
const toastEl = $('#toast');
const tabsEl = $('#tabs');

const CATS = [
  { id: '', label: '全部' },
  { id: 'C', label: '道具 C' },
  { id: 'T', label: '饰品 T' },
  { id: 'K', label: '卡牌 K' },
  { id: 'P', label: '胶囊 P' },
  { id: 'D', label: '掉落物 D' },
];

let ALL = [];
let filtered = [];
let cat = '';

/* ---------- 工具 ---------- */

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );

function hl(text, needle) {
  const t = esc(text);
  if (!needle) return t;
  const i = t.toLowerCase().indexOf(needle);
  if (i < 0) return t;
  // 只在标签外的高亮文本上插入，转义后的 &lt; 不会被误切
  return t.slice(0, i) + '<mark>' + t.slice(i, i + needle.length) + '</mark>' + t.slice(i + needle.length);
}

let toastTimer;
function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toastEl.hidden = true), 1400);
}

async function copy(text) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch { /* 忽略 */ }
    ta.remove();
  }
  toast('已复制 ' + text);
}

/* ---------- 搜索 ---------- */

// 打分：越小越靠前；0 表示不匹配
function score(item, n) {
  const code = item.code.toLowerCase();
  if (code === n) return 1;
  if (item.zh === n) return 2;
  if (item.en.toLowerCase() === n) return 3;

  if (code.startsWith(n)) return 10;
  if (item.py && item.py.startsWith(n)) return 11;
  if (item.enpy && item.enpy.startsWith(n)) return 12;
  if (item.zh.includes(n)) return 20;
  if (item.en.toLowerCase().includes(n)) return 21;
  if (item.py && item.py.includes(n)) return 22;
  if (item.enpy && item.enpy.includes(n)) return 23;
  if (String(item.id) === n) return 30;
  return 0;
}

function apply() {
  const raw = q.value.trim().toLowerCase();
  clearBtn.hidden = !raw;
  // 只有「类别字母 + 纯编号」才额外再按裸编号匹配一次。
  // 无条件剥掉首字母的话，tso 会被拆成 t + so，把一堆无关条目带出来。
  const alt = raw.match(/^([ctkp])(\d+)$/)?.[2] ?? null;

  if (!raw && !cat) {
    filtered = ALL;
  } else {
    filtered = [];
    for (const it of ALL) {
      if (cat && it.cat !== cat) continue;
      if (raw) {
        const s = score(it, raw) || (alt !== null ? score(it, alt) : 0);
        if (!s) continue;
        it._s = s;
      } else {
        it._s = 0;
      }
      filtered.push(it);
    }
    filtered.sort((a, b) => (a._s - b._s) || (a.cat === b.cat ? a.id - b.id : 0));
  }
  render();
}

/* ---------- 渲染 ---------- */

// 一屏铺 1000+ 卡片会让首屏绘制和 DOM 查询都很重，改为分批追加。
const PAGE = 60;
let shown = 0;
let needle = '';

const sentinel = document.createElement('div');
sentinel.className = 'sentinel';
grid.after(sentinel);

// 补齐可见区域：一直追加到哨兵被推出视口（或列表到底）为止。
//
// 不能只靠 IntersectionObserver 的回调。IO 只在「相交状态变化」时通知：首批渲染完，
// 哨兵被新增内容往下顶，如果它仍留在扩展视口（视口高 + rootMargin）里，相交状态没变，
// 事件不会再触发一次 —— 窗口越宽首批越高，越容易卡住。实测宽屏下首批 60 条之后
// 列表再也不增长，只能靠搜索找到后面的条目。
function fillViewport() {
  while (shown < filtered.length) {
    if (sentinel.getBoundingClientRect().top > window.innerHeight + 600) break;
    showMore();
  }
  updateCount();
}

// 计数统一在这里写：没加载完就说「已显示 N / M」，加载完才说「匹配数 / 总数」。
// 之前只有 showMore() 在全部加载完时改一次文本，列表中途加载的状态一律显示成
// 「匹配数 / 总数」，看上去像是已经列全了，其实后面还有几百条。
let lastCountText = '';
function updateCount() {
  if (!ALL.length) return;
  const txt =
    shown >= filtered.length
      ? `${filtered.length} / ${ALL.length} 条`
      : `已显示 ${shown} / ${filtered.length} 条`;
  if (txt !== lastCountText) {
    countEl.textContent = txt;
    lastCountText = txt;
  }
}

const io = new IntersectionObserver(() => fillViewport(), { rootMargin: '600px' });
io.observe(sentinel);

// 兜底：滚动时自己判断哨兵位置，不依赖 IO 的状态变化语义
let ticking = false;
window.addEventListener(
  'scroll',
  () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      fillViewport();
    });
  },
  { passive: true }
);

function cardHTML(it, n) {
  const thumb = it.icon
    ? `<img class="thumb" loading="lazy" decoding="async" src="${it.icon}" alt="">`
    : `<div class="ph">${it.catLabel[0]}</div>`;

  // 掉落物只有 spawn，按钮就设为主操作；其余类别「道具」是主操作
  const acts = [];
  if (it.spawn) acts.push(['spawn', '实体', it.give ? '' : 'primary']);
  if (it.give) acts.push(['give', '道具', 'primary']);
  if (it.giveBig) acts.push(['giveBig', '大胶囊', '']);

  const q4 = it.quality != null ? ` q${it.quality}` : '';

  return `<div class="item" data-code="${esc(it.code)}">
    ${thumb}
    <div class="meta">
      <div class="zh">${hl(it.zh || it.en, n)}</div>
      <div class="sub">
        <span class="en">${hl(it.en, n)}</span>
        <span class="code${q4}">${it.code.toUpperCase()}</span>
      </div>
    </div>
    <div class="acts">${acts
      .map(([k, label, cls]) => `<button class="act ${cls}" data-act="${k}">${label}</button>`)
      .join('')}</div>
  </div>`;
}

function render() {
  needle = q.value.trim().toLowerCase();
  const total = ALL.length;
  const c = ALL.reduce((a, i) => ((a[i.cat] = (a[i.cat] || 0) + 1), a), {});
  $('#empty').hidden = filtered.length > 0;

  for (const t of CATS) {
    const el = tabsEl.querySelector(`[data-cat="${t.id}"]`);
    el.querySelector('.n').textContent = t.id ? c[t.id] || 0 : total;
  }

  shown = 0;
  grid.innerHTML = '';
  fillViewport();
}

function showMore() {
  const slice = filtered.slice(shown, shown + PAGE);
  if (!slice.length) return;
  grid.insertAdjacentHTML('beforeend', slice.map((it) => cardHTML(it, needle)).join(''));
  shown += slice.length;
}

function flash(el) {
  if (!el) return;
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 260);
}

/* ---------- 事件 ---------- */

grid.addEventListener('click', (e) => {
  const row = e.target.closest('.item');
  if (!row) return;
  const it = ALL.find((x) => x.code === row.dataset.code);
  if (!it) return;

  const btn = e.target.closest('.act');
  if (btn) {
    const key = btn.dataset.act;
    copy(key === 'spawn' ? it.spawn : it[key]);
    flash(row);
    return;
  }

  // 点卡片本体：给道具；Alt+点击给移除指令。
  // 掉落物没有 giveitem / remove，默认就复制它的 spawn。
  if (e.altKey && it.remove) copy(it.remove);
  else copy(it.give || it.spawn);
  flash(row);
});

let typing;
q.addEventListener('input', () => {
  clearTimeout(typing);
  typing = setTimeout(apply, 90);
});

clearBtn.addEventListener('click', () => {
  q.value = '';
  q.focus();
  apply();
});

tabsEl.addEventListener('click', (e) => {
  const t = e.target.closest('.tab');
  if (!t) return;
  cat = t.dataset.cat;
  for (const el of tabsEl.querySelectorAll('.tab')) {
    el.setAttribute('aria-selected', String(el.dataset.cat === cat));
  }
  apply();
});

document.addEventListener('keydown', (e) => {
  if (e.key === '/' && document.activeElement !== q) {
    e.preventDefault();
    q.focus();
    q.select();
  } else if (e.key === 'Escape' && document.activeElement === q) {
    q.value = '';
    apply();
  }
});

/* ---------- 启动 ---------- */

(async function init() {
  tabsEl.innerHTML = CATS.map(
    (t, i) =>
      `<button class="tab" data-cat="${t.id}" aria-selected="${i === 0}">${t.label}<span class="n"></span></button>`
  ).join('');

  let data;
  try {
    data = await (await fetch('data.json')).json();
  } catch (err) {
    countEl.textContent = 'data.json 载入失败';
    grid.innerHTML =
      '<p class="empty">无法载入 data.json。<br>若直接双击打开 index.html，请改用本地 HTTP 服务访问。</p>';
    return;
  }

  ALL = data.items;
  apply();

  const m = data.meta;
  $('#buildInfo').textContent =
    `构建于 ${m.generated} ｜ 数据源：${m.source} ｜ ${m.game}`;
})();
