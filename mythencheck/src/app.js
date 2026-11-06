(function(){
'use strict';

var TOPICS = [].concat(TOPICS_1, TOPICS_2, TOPICS_3);
var CAT_ORDER = ['natur','gesundheit','geschichte','staat','maechte'];
var CATS = {
  natur:{name:'Wissenschaft & Natur', icon:'globe'},
  gesundheit:{name:'Gesundheit & Medizin', icon:'pulse'},
  geschichte:{name:'Geschichte & NS-Revisionismus', icon:'book'},
  staat:{name:'Staat & Demokratie', icon:'columns'},
  maechte:{name:'Geheime Mächte', icon:'eye'}
};
var byId = {};
TOPICS.forEach(function(t, i){ t.index = i; byId[t.id] = t; });

var SVG = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
var ICONS = {
  globe:'<svg '+SVG+'><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="3.8" ry="9"/><path d="M3.6 9h16.8M3.6 15h16.8"/></svg>',
  pulse:'<svg '+SVG+'><path d="M3 12h4l2.5-6 5 12 2.5-6H21"/></svg>',
  book:'<svg '+SVG+'><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5z"/><path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5z"/></svg>',
  columns:'<svg '+SVG+'><path d="M3 9.5 12 4l9 5.5"/><path d="M5.5 10.5v7M9.8 10.5v7M14.2 10.5v7M18.5 10.5v7"/><path d="M3 20h18"/></svg>',
  eye:'<svg '+SVG+'><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>'
};
var I = {
  chev:'<svg class="chev" viewBox="0 0 10 16" aria-hidden="true"><path d="M2.5 2l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  close:'<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  x:'<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M3.5 3.5l7 7M10.5 3.5l-7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
  ext:'<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5h5v5M9.5 2.5 3 9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  bulb:'<svg '+SVG+'><path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1.1 2V16h5v-.2c.1-.8.5-1.5 1.1-2A6 6 0 0 0 12 3z"/></svg>',
  info:'<svg '+SVG+'><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.6v.4"/></svg>',
  ok:'<svg '+SVG+'><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16 9.5"/></svg>',
  no:'<svg '+SVG+'><circle cx="12" cy="12" r="9"/><path d="M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6"/></svg>'
};

function $(s, r){ return (r || document).querySelector(s); }
function $$(s, r){ return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
function esc(s){ return String(s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function catStyle(cat){ return '--c1:var(--' + cat + '-1);--c2:var(--' + cat + '-2)'; }
function norm(s){ return String(s).toLowerCase().replace(/ß/g, 'ss').normalize('NFD').replace(/[̀-ͯ]/g, ''); }
function shuffle(a){ a = a.slice(); for (var i = a.length - 1; i > 0; i--){ var j = Math.floor(Math.random() * (i + 1)); var x = a[i]; a[i] = a[j]; a[j] = x; } return a; }
function host(u){ try { return new URL(u).hostname.replace(/^www\./, ''); } catch(e){ return u; } }
function num(n){ return n.toLocaleString('de-DE'); }

TOPICS.forEach(function(t){
  t._s = norm([t.title, t.short, t.claim, (t.tags || []).join(' '), CATS[t.cat].name].join(' '));
});
var TOTAL_Q = TOPICS.reduce(function(a, t){ return a + t.quiz.length; }, 0);
var TOTAL_SRC = TOPICS.reduce(function(a, t){ return a + t.sources.length; }, 0);

/* Fortschritt: nur im Browser dieser Person */
var STORE_KEY = 'mythencheck-v1';
var store = {topics:{}};
try {
  var raw = localStorage.getItem(STORE_KEY);
  if (raw){ var parsed = JSON.parse(raw); if (parsed && typeof parsed === 'object' && parsed.topics) store = parsed; }
} catch(e){}
function persist(){ try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); } catch(e){} }
function best(id){ var v = store.topics[id]; return typeof v === 'number' ? v : null; }
function isMastered(t){ return best(t.id) === t.quiz.length; }
function record(id, score){ var b = best(id); if (b === null || score > b){ store.topics[id] = score; persist(); } refreshProgress(); }

function ring(frac, size, stroke, color){
  var r = (size - stroke) / 2, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(1, frac)));
  return '<svg class="ring" viewBox="0 0 ' + size + ' ' + size + '" aria-hidden="true">' +
    '<circle cx="' + size/2 + '" cy="' + size/2 + '" r="' + r + '" fill="none" style="stroke:var(--seg-bg)" stroke-width="' + stroke + '"/>' +
    '<circle cx="' + size/2 + '" cy="' + size/2 + '" r="' + r + '" fill="none" style="stroke:' + color + ';transition:stroke-dashoffset .8s cubic-bezier(.2,.8,.2,1)" stroke-width="' + stroke + '" stroke-linecap="round" stroke-dasharray="' + c.toFixed(2) + '" stroke-dashoffset="' + off.toFixed(2) + '" transform="rotate(-90 ' + size/2 + ' ' + size/2 + ')"/></svg>';
}

/* Raster */
var view = {cat:'alle', q:''};
var grid = $('#grid'), chips = $('#chips'), resultLine = $('#result-line'), search = $('#search');

function countCat(cat){ return TOPICS.filter(function(t){ return t.cat === cat; }).length; }
function renderChips(){
  var list = [['alle', 'Alle Themen', TOPICS.length]].concat(CAT_ORDER.map(function(k){ return [k, CATS[k].name, countCat(k)]; }));
  chips.innerHTML = list.map(function(c){
    return '<button class="chip" type="button" data-cat="' + c[0] + '" aria-pressed="' + (view.cat === c[0]) + '"' + (c[0] !== 'alle' ? ' style="' + catStyle(c[0]) + '"' : '') + '>' +
      (c[0] !== 'alle' ? '<span class="dot"></span>' : '') + esc(c[1]) + ' <span class="cnt">' + c[2] + '</span></button>';
  }).join('');
}
function filtered(){
  var terms = norm(view.q.trim()).split(/\s+/).filter(Boolean);
  return TOPICS.filter(function(t){
    return (view.cat === 'alle' || t.cat === view.cat) && terms.every(function(w){ return t._s.indexOf(w) >= 0; });
  });
}
function badge(t){
  var b = best(t.id);
  if (b === null) return '';
  if (b === t.quiz.length) return '<span class="badge done">Gemeistert</span>';
  return '<span class="badge part">' + b + ' von ' + t.quiz.length + '</span>';
}
function card(t){
  var c = CATS[t.cat];
  return '<button class="card" type="button" data-open="' + t.id + '" style="' + catStyle(t.cat) + '" aria-label="Faktencheck: ' + esc(t.title) + '">' +
    '<span class="card-top"><span class="cat-icon">' + ICONS[c.icon] + '</span><span class="card-cat">' + esc(c.name) + '</span>' + badge(t) + '</span>' +
    '<span class="card-title">' + esc(t.title) + '</span>' +
    '<span class="card-short">' + esc(t.short) + '</span>' +
    '<span class="card-cta">Zum Faktencheck ' + I.chev + '</span></button>';
}
function renderGrid(){
  var list = filtered();
  grid.innerHTML = list.length ? list.map(card).join('') :
    '<div class="empty"><b>Keine Treffer</b>Versuch es mit einem anderen Begriff oder wähle „Alle Themen“.</div>';
  var q = view.q.trim();
  var where = view.cat !== 'alle' ? ' in „' + CATS[view.cat].name + '“' : '';
  resultLine.textContent = q ? list.length + (list.length === 1 ? ' Treffer' : ' Treffer') + ' für „' + q + '“' + where
                             : list.length + ' Mythen' + where;
}
chips.addEventListener('click', function(e){
  var b = e.target.closest('[data-cat]'); if (!b) return;
  view.cat = b.getAttribute('data-cat'); renderChips(); renderGrid();
});
search.addEventListener('input', function(){ view.q = search.value; renderGrid(); });
search.addEventListener('keydown', function(e){ if (e.key === 'Escape'){ search.value = ''; view.q = ''; renderGrid(); } });

/* Kennzahlen und Fortschritt */
function renderStats(){
  $('#stat-topics').textContent = TOPICS.length;
  $('#stat-q').textContent = TOTAL_Q;
  $('#stat-src').textContent = TOTAL_SRC;
  $('#stat-cats').textContent = CAT_ORDER.length;
  $('#lead-count').textContent = TOPICS.length;
}
function refreshProgress(){
  var done = TOPICS.filter(isMastered).length;
  $('#nav-progress-ring').innerHTML = ring(done / TOPICS.length, 20, 3.2, 'var(--ok)');
  $('#nav-progress-text').textContent = done + ' von ' + TOPICS.length + ' gemeistert';
  $('#progress-ring').innerHTML = ring(done / TOPICS.length, 112, 10, 'var(--ok)');
  $('#progress-done').textContent = done + ' von ' + TOPICS.length;
  $('#progress-bars').innerHTML = CAT_ORDER.map(function(k){
    var all = TOPICS.filter(function(t){ return t.cat === k; });
    var d = all.filter(isMastered).length;
    return '<div class="bar-row" style="' + catStyle(k) + '"><span>' + esc(CATS[k].name) + '</span><span>' + d + ' / ' + all.length + '</span>' +
      '<div class="bar" role="progressbar" aria-label="' + esc(CATS[k].name) + '" aria-valuemin="0" aria-valuemax="' + all.length + '" aria-valuenow="' + d + '"><i style="width:' + (d / all.length * 100) + '%"></i></div></div>';
  }).join('');
  renderGrid();
}
var resetArea = $('#reset-area');
function renderReset(confirming){
  resetArea.innerHTML = confirming ?
    '<div class="reset-confirm"><span>Gesamten Fortschritt löschen?</span><button class="btn btn-sm btn-ghost" type="button" data-reset="yes">Ja, löschen</button><button class="btn btn-sm btn-ghost" type="button" data-reset="no">Abbrechen</button></div>' :
    '<button class="reset" type="button" data-reset="ask">Fortschritt zurücksetzen</button>';
}
resetArea.addEventListener('click', function(e){
  var b = e.target.closest('[data-reset]'); if (!b) return;
  var a = b.getAttribute('data-reset');
  if (a === 'ask'){ renderReset(true); $('[data-reset="no"]', resetArea).focus(); }
  else if (a === 'yes'){ store = {topics:{}}; persist(); refreshProgress(); renderReset(false); }
  else { renderReset(false); }
});

/* Ticker im Hero */
var TICK = [
  ['flache-erde','Die Erde ist eine Scheibe.'],
  ['mondlandung','Die Mondlandung war inszeniert.'],
  ['impf-autismus','Impfungen verursachen Autismus.'],
  ['reichsbuerger','Die BRD ist eine GmbH.'],
  ['chemtrails','Flugzeuge versprühen heimlich Gift.'],
  ['klima','Der Klimawandel ist natürlich.'],
  ['holocaust','Den Holocaust hat es nie gegeben.']
];
var ticker = $('#ticker'), tickClaim = $('#ticker-claim'), tickDots = $('#ticker-dots'), tickIdx = 0, tickTimer = null, tickPaused = false;
var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function renderTick(){
  tickClaim.innerHTML = '<span>„' + esc(TICK[tickIdx][1]) + '“</span>';
  tickDots.innerHTML = TICK.map(function(_, i){ return '<i class="' + (i === tickIdx ? 'on' : '') + '"></i>'; }).join('');
  ticker.setAttribute('aria-label', 'Behauptung: ' + TICK[tickIdx][1] + ' Widerlegt. Zum Faktencheck.');
}
function stepTick(){
  if (tickPaused || !root.hidden || document.hidden) return;
  ticker.classList.add('fade');
  setTimeout(function(){
    tickIdx = (tickIdx + 1) % TICK.length;
    ticker.classList.remove('struck');
    renderTick();
    ticker.classList.remove('fade');
    setTimeout(function(){ ticker.classList.add('struck'); }, 60);
  }, 360);
}
renderTick();
setTimeout(function(){ ticker.classList.add('struck'); }, reduceMotion ? 0 : 500);
if (!reduceMotion){ tickTimer = setInterval(stepTick, 3800); }
ticker.addEventListener('mouseenter', function(){ tickPaused = true; });
ticker.addEventListener('mouseleave', function(){ tickPaused = false; });
ticker.addEventListener('focus', function(){ tickPaused = true; });
ticker.addEventListener('blur', function(){ tickPaused = false; });
ticker.addEventListener('click', function(){ openTopic(TICK[tickIdx][0]); });

/* Sheet */
var root = $('#sheet-root'), sheet = $('#sheet'), lastFocus = null, lastFocusId = null, current = null;
function show(){
  if (root.hidden){ lastFocus = document.activeElement; lastFocusId = lastFocus && lastFocus.getAttribute ? lastFocus.getAttribute('data-open') : null; }
  root.hidden = false;
  document.documentElement.style.overflow = 'hidden';
  var sc = $('.sheet-scroll', sheet); if (sc) sc.scrollTop = 0;
  var c = $('[data-close]', sheet); if (c) c.focus({preventScroll:true});
}
function closeSheet(){
  if (root.hidden) return;
  root.hidden = true; sheet.innerHTML = ''; current = null;
  document.documentElement.style.overflow = '';
  clearHash();
  var target = (lastFocus && document.contains(lastFocus)) ? lastFocus : (lastFocusId ? $('#grid [data-open="' + lastFocusId + '"]') : null);
  if (target && target.focus) target.focus({preventScroll:true});
}
function setHash(h){
  if (location.hash === '#' + h) return;
  try { history.replaceState(null, '', '#' + h); } catch(e){ try { location.hash = h; } catch(e2){} }
}
function clearHash(){
  if (!location.hash) return;
  try { history.replaceState(null, '', location.pathname + location.search); } catch(e){}
}
function sheetBar(cat, label){
  var icon = cat ? '<span class="cat-icon" style="' + catStyle(cat) + '">' + ICONS[CATS[cat].icon] + '</span>' : '';
  return '<div class="sheet-bar"><span class="card-cat">' + icon + esc(label) + '</span>' +
    '<button class="icon-btn" type="button" data-close aria-label="Schließen">' + I.close + '</button></div>';
}

var TABS = [['ueberblick','Überblick'],['fakten','Fakten'],['quellen','Quellen'],['quiz','Quiz']];
function openTopic(id, tab){
  var t = byId[id]; if (!t) return;
  current = {type:'topic', id:id, tab:'ueberblick'};
  var prev = TOPICS[(t.index - 1 + TOPICS.length) % TOPICS.length], next = TOPICS[(t.index + 1) % TOPICS.length];
  sheet.innerHTML = sheetBar(t.cat, CATS[t.cat].name) +
    '<div class="sheet-scroll"><div class="sheet-body">' +
      '<header class="topic-head"><span class="verdict">' + I.x + ' Widerlegt</span>' +
        '<h2 id="sheet-title">' + esc(t.title) + '</h2><p class="lede">' + esc(t.short) + '</p></header>' +
      '<div class="seg" role="tablist" aria-label="Abschnitte">' + TABS.map(function(x){
        return '<button type="button" role="tab" id="tab-' + x[0] + '" aria-controls="panel" data-tab="' + x[0] + '" aria-selected="false" tabindex="-1">' + x[1] + '</button>';
      }).join('') + '</div>' +
      '<div class="panel" id="panel" role="tabpanel"></div>' +
      '<nav class="topic-nav" aria-label="Weitere Themen">' +
        '<button type="button" data-open="' + prev.id + '"><svg class="chev chev-l" viewBox="0 0 10 16" aria-hidden="true"><path d="M2.5 2l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span><small>Vorheriges Thema</small>' + esc(prev.title) + '</span></button>' +
        '<button type="button" data-open="' + next.id + '"><span><small>Nächstes Thema</small>' + esc(next.title) + '</span>' + I.chev + '</button>' +
      '</nav>' +
    '</div></div>';
  show();
  setTab(tab || 'ueberblick', false);
  setHash(id);
}
function setTab(key, focusTab){
  var t = byId[current.id]; current.tab = key;
  $$('[role="tab"]', sheet).forEach(function(b){
    var on = b.getAttribute('data-tab') === key;
    b.setAttribute('aria-selected', on); b.tabIndex = on ? 0 : -1;
    if (on && focusTab) b.focus();
  });
  var panel = $('#panel', sheet);
  panel.setAttribute('aria-labelledby', 'tab-' + key);
  if (key === 'ueberblick') panel.innerHTML = overview(t);
  else if (key === 'fakten') panel.innerHTML = factsView(t);
  else if (key === 'quellen') panel.innerHTML = sourcesView(t);
  else if (key === 'quiz') runQuiz(panel, t.quiz.map(function(q){ return {t:t, q:q}; }), {mode:'topic', topic:t});
}
function overview(t){
  return '<div class="claim"><span class="label">' + I.x.replace('viewBox', 'width="12" height="12" viewBox') + 'Die Behauptung</span><p>' + esc(t.claim) + '</p></div>' +
    '<h3>Woher der Mythos kommt</h3><div class="prose">' + t.origin.map(function(p){ return '<p>' + esc(p) + '</p>'; }).join('') + '</div>' +
    (t.kernel ? '<div class="box box-kern">' + I.bulb + '<div><b>Der wahre Kern</b><p>' + esc(t.kernel) + '</p></div></div>' : '') +
    (t.note ? '<div class="box box-note">' + I.info + '<div><b>Gut zu wissen</b><p>' + esc(t.note) + '</p></div></div>' : '') +
    '<div><button class="btn btn-primary" type="button" data-tab="fakten">Was die Belege zeigen ' + I.chev + '</button></div>';
}
function factsView(t){
  return '<h3>Was die Belege zeigen</h3><ul class="facts">' + t.facts.map(function(f){
    return '<li class="fact"><b>' + esc(f[0]) + '</b><p>' + esc(f[1]) + '</p></li>';
  }).join('') + '</ul>' +
  '<div class="hero-actions" style="justify-content:flex-start;margin-top:0"><button class="btn btn-primary" type="button" data-tab="quiz">Wissen testen ' + I.chev + '</button><button class="link-cta" type="button" data-tab="quellen">Alle ' + t.sources.length + ' Quellen ' + I.chev + '</button></div>';
}
function sourcesView(t){
  return '<h3>Quellen</h3><p class="src-note">Studien, Behörden, Gerichte, Fachbücher und Qualitätsmedien. Links öffnen in einem neuen Tab.</p>' +
    '<ol class="sources">' + t.sources.map(function(s){
      return '<li class="src"><span class="src-type">' + esc(s[0]) + '</span><span class="src-text">' + esc(s[1]) + '</span>' +
        (s[2] ? '<a class="src-link" href="' + esc(s[2]) + '" target="_blank" rel="noopener noreferrer">' + esc(host(s[2])) + ' ' + I.ext + '</a>' : '') + '</li>';
    }).join('') + '</ol>';
}

/* Quiz */
function runQuiz(el, questions, opts){
  var i = 0, score = 0, wrong = [], answered = false;
  function renderQ(){
    answered = false;
    var Q = questions[i], order = shuffle([0, 1, 2, 3]);
    el.innerHTML = '<div class="quiz">' +
      '<div class="q-meta"><span>Frage ' + (i + 1) + ' von ' + questions.length + '</span><span id="q-score">' + score + ' richtig</span></div>' +
      '<div class="q-track" aria-hidden="true"><i style="width:' + (i / questions.length * 100) + '%"></i></div>' +
      (opts.mode === 'mix' ? '<div class="q-from" style="' + catStyle(Q.t.cat) + '"><span class="cat-icon">' + ICONS[CATS[Q.t.cat].icon] + '</span>' + esc(Q.t.title) + '</div>' : '') +
      '<p class="q-text" id="q-text">' + esc(Q.q[0]) + '</p>' +
      '<div class="opts" role="group" aria-labelledby="q-text">' + order.map(function(k, n){
        return '<button class="opt" type="button" data-k="' + k + '"><span class="key" aria-hidden="true">' + 'ABCD'.charAt(n) + '</span><span>' + esc(Q.q[1][k]) + '</span></button>';
      }).join('') + '</div>' +
      '<div class="q-fb" aria-live="polite"></div><div class="q-actions"></div></div>';
    $$('.opt', el).forEach(function(b){ b.addEventListener('click', function(){ answer(+b.getAttribute('data-k')); }); });
  }
  function answer(k){
    if (answered) return; answered = true;
    var Q = questions[i], ok = k === 0;
    if (ok) score++; else wrong.push(Q);
    $$('.opt', el).forEach(function(b){
      var kk = +b.getAttribute('data-k'); b.disabled = true;
      if (kk === 0){ b.classList.add('correct'); b.setAttribute('aria-label', 'Richtige Antwort: ' + Q.q[1][0]); }
      else if (kk === k) b.classList.add('wrong');
      else b.classList.add('dim');
    });
    $('#q-score', el).textContent = score + ' richtig';
    $('.q-fb', el).innerHTML = '<div class="feedback ' + (ok ? 'ok' : 'no') + '">' + (ok ? I.ok : I.no) + '<div><b>' + (ok ? 'Richtig.' : 'Nicht ganz.') + '</b>' +
      '<p>' + (ok ? '' : 'Richtig ist: „' + esc(Q.q[1][0]) + '“. ') + esc(Q.q[2]) + '</p>' +
      (opts.mode === 'mix' ? '<p class="more"><button class="link-cta" type="button" data-open="' + Q.t.id + '" data-tab="fakten">Mehr zu „' + esc(Q.t.title) + '“ ' + I.chev + '</button></p>' : '') +
      '</div></div>';
    var last = i === questions.length - 1;
    $('.q-actions', el).innerHTML = '<button class="btn btn-primary" type="button" data-q="next">' + (last ? 'Zur Auswertung' : 'Nächste Frage') + '</button>';
    var nb = $('[data-q="next"]', el);
    nb.addEventListener('click', function(){ i++; if (i < questions.length){ renderQ(); focusFirstOpt(); } else finish(); });
    nb.focus({preventScroll:true});
    nb.scrollIntoView({block:'nearest', behavior: reduceMotion ? 'auto' : 'smooth'});
  }
  function focusFirstOpt(){ var f = $('.opt', el); if (f) f.focus({preventScroll:true}); var sc = el.closest('.sheet-scroll'); var qt = $('.q-text', el); if (sc && qt){ qt.scrollIntoView({block:'nearest'}); } }
  function finish(){
    var n = questions.length, frac = score / n;
    var msg = frac === 1 ? (opts.mode === 'topic' ? 'Thema gemeistert. Du kennst die Fakten und kannst sie erklären.' : 'Alles richtig. Stark, du kennst die Fakten.')
            : frac >= 0.6 ? 'Gut gemacht. Ein Blick in die Fakten schließt die letzten Lücken.'
            : 'Kein Problem, genau so funktioniert Lernen. Lies die Fakten nach und versuch es noch einmal.';
    var html = '<div class="result">' + ring(frac, 132, 11, frac === 1 ? 'var(--ok)' : 'var(--accent)') +
      '<h3>' + score + ' von ' + n + ' richtig</h3><p>' + msg + '</p><div class="row">';
    if (opts.mode === 'topic'){
      var nextT = TOPICS[(opts.topic.index + 1) % TOPICS.length];
      html += '<button class="btn btn-primary" type="button" data-q="again">Noch einmal</button>' +
              '<button class="btn btn-secondary" type="button" data-tab="fakten">Fakten nachlesen</button>' +
              '<button class="btn btn-secondary" type="button" data-open="' + nextT.id + '">Nächstes Thema</button></div>';
    } else {
      html += '<button class="btn btn-primary" type="button" data-q="new">Neues Schnellquiz</button></div>';
      var seen = {}, rev = wrong.filter(function(Q){ if (seen[Q.t.id]) return false; seen[Q.t.id] = 1; return true; });
      if (rev.length){
        html += '<div class="review"><h4>Diese Themen lohnen einen zweiten Blick</h4>' + rev.map(function(Q){
          return '<button type="button" data-open="' + Q.t.id + '" data-tab="fakten" style="' + catStyle(Q.t.cat) + '"><span class="cat-icon">' + ICONS[CATS[Q.t.cat].icon] + '</span><span class="rv-title">' + esc(Q.t.title) + '</span>' + I.chev + '</button>';
        }).join('') + '</div>';
      }
    }
    html += '</div>';
    el.innerHTML = html;
    var again = $('[data-q="again"]', el);
    if (again) again.addEventListener('click', function(){ i = 0; score = 0; wrong = []; renderQ(); focusFirstOpt(); });
    var nw = $('[data-q="new"]', el);
    if (nw) nw.addEventListener('click', function(){ renderSetup(quizCat); });
    if (opts.mode === 'topic') record(opts.topic.id, score);
    var first = $('.result .btn', el); if (first) first.focus({preventScroll:true});
    var sc = el.closest('.sheet-scroll'); if (sc) sc.scrollTop = Math.max(0, el.offsetTop - 80);
  }
  renderQ();
}

/* Schnellquiz */
var quizCat = 'alle';
function openQuiz(cat){
  if (cat) quizCat = cat;
  current = {type:'quiz'};
  sheet.innerHTML = sheetBar(null, 'Schnellquiz') +
    '<div class="sheet-scroll"><div class="sheet-body">' +
      '<header class="topic-head"><h2 id="sheet-title">Schnellquiz</h2><p class="lede">Zehn Fragen aus verschiedenen Themen. Jede Antwort wird sofort erklärt.</p></header>' +
      '<div class="panel" id="panel"></div>' +
    '</div></div>';
  show();
  renderSetup(quizCat);
  setHash('schnellquiz');
}
function renderSetup(sel){
  quizCat = sel;
  var panel = $('#panel', sheet); if (!panel) return;
  var opts = [['alle', 'Alle Themen']].concat(CAT_ORDER.map(function(k){ return [k, CATS[k].name]; }));
  panel.innerHTML = '<div class="setup"><span class="label" id="setup-label">Themenfeld wählen</span>' +
    '<div class="chips" role="group" aria-labelledby="setup-label">' + opts.map(function(o){
      return '<button class="chip" type="button" data-qcat="' + o[0] + '" aria-pressed="' + (sel === o[0]) + '"' + (o[0] !== 'alle' ? ' style="' + catStyle(o[0]) + '"' : '') + '>' + (o[0] !== 'alle' ? '<span class="dot"></span>' : '') + esc(o[1]) + '</button>';
    }).join('') + '</div>' +
    '<div><button class="btn btn-primary" type="button" data-q="go">Quiz starten ' + I.chev + '</button></div></div>';
  $$('[data-qcat]', panel).forEach(function(b){ b.addEventListener('click', function(){ renderSetup(b.getAttribute('data-qcat')); $('[data-qcat="' + quizCat + '"]', panel).focus(); }); });
  $('[data-q="go"]', panel).addEventListener('click', function(){ startQuiz(quizCat); });
}
function startQuiz(cat){
  var pool = TOPICS.filter(function(t){ return cat === 'alle' || t.cat === cat; });
  var picked = [], used = {};
  shuffle(pool).forEach(function(t){ if (picked.length < 10){ var k = Math.floor(Math.random() * t.quiz.length); picked.push({t:t, q:t.quiz[k]}); used[t.id + k] = 1; } });
  if (picked.length < 10){
    var rest = [];
    pool.forEach(function(t){ t.quiz.forEach(function(q, k){ if (!used[t.id + k]) rest.push({t:t, q:q}); }); });
    picked = picked.concat(shuffle(rest).slice(0, 10 - picked.length));
  }
  picked = shuffle(picked);
  var panel = $('#panel', sheet);
  runQuiz(panel, picked, {mode:'mix'});
  var f = $('.opt', panel); if (f) f.focus({preventScroll:true});
}

/* Ereignisse im Sheet */
sheet.addEventListener('click', function(e){
  var o = e.target.closest('[data-open]');
  if (o){ openTopic(o.getAttribute('data-open'), o.getAttribute('data-tab') || null); return; }
  var tb = e.target.closest('[data-tab]');
  if (tb && current && current.type === 'topic'){
    setTab(tb.getAttribute('data-tab'), tb.getAttribute('role') === 'tab');
    if (tb.getAttribute('role') !== 'tab'){ var sc = $('.sheet-scroll', sheet), seg = $('.seg', sheet); if (sc && seg) sc.scrollTop = Math.max(0, seg.offsetTop - 16); var st = $('[role="tab"][aria-selected="true"]', sheet); if (st) st.focus({preventScroll:true}); }
    return;
  }
  if (e.target.closest('[data-close]')) closeSheet();
});
root.addEventListener('click', function(e){ if (e.target.classList.contains('scrim')) closeSheet(); });
root.addEventListener('keydown', function(e){
  if (e.key === 'Escape'){ e.preventDefault(); closeSheet(); return; }
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft'){
    var tab = e.target.closest('[role="tab"]');
    if (tab){
      e.preventDefault();
      var idx = TABS.map(function(x){ return x[0]; }).indexOf(tab.getAttribute('data-tab'));
      idx = (idx + (e.key === 'ArrowRight' ? 1 : -1) + TABS.length) % TABS.length;
      setTab(TABS[idx][0], true);
    }
    return;
  }
  if (e.key === 'Tab'){
    var f = $$('button:not([disabled]), a[href], input, [tabindex]:not([tabindex="-1"])', sheet).filter(function(x){ return x.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
  }
});

/* Seitenweite Klicks */
document.addEventListener('click', function(e){
  if (sheet.contains(e.target)) return;
  var o = e.target.closest('[data-open]');
  if (o){ openTopic(o.getAttribute('data-open'), o.getAttribute('data-tab') || null); return; }
  var q = e.target.closest('[data-quiz]');
  if (q){ openQuiz(q.getAttribute('data-quiz') || 'alle'); return; }
});
$('#random-topic').addEventListener('click', function(){ openTopic(TOPICS[Math.floor(Math.random() * TOPICS.length)].id); });
$('#nav-progress').addEventListener('click', function(){ var q = $('#quiz'); q.scrollIntoView({behavior: reduceMotion ? 'auto' : 'smooth'}); });
$('#brand').addEventListener('click', function(){ window.scrollTo({top:0, behavior: reduceMotion ? 'auto' : 'smooth'}); });

/* Links per Hash: #<thema> öffnet ein Thema, #schnellquiz das Quiz */
function route(){
  var h = decodeURIComponent((location.hash || '').slice(1));
  if (byId[h]){ if (!(current && current.id === h)) openTopic(h); }
  else if (h === 'schnellquiz'){ if (!(current && current.type === 'quiz')) openQuiz(); }
}
window.addEventListener('hashchange', route);

renderStats();
renderChips();
refreshProgress();
renderReset(false);
route();
})();
