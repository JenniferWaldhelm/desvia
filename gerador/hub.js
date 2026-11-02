/* Mapa com filtros da página de cada cidade. Dados em PONTOS e CATS (definidos na página). */
(function () {
  var CORES = { valida: '#2A7A2A', vencendo: '#C77700', vencida: '#C77700', publico: '#1A3A8F', nao_localizada: '#7A7F8C' };
  var ORDEM = { valida: 0, vencendo: 1, publico: 2, vencida: 3, nao_localizada: 4 };
  var estado = { q: '', p: 'todos', cat: null, lic: false, loc: false, cid: '' };
  var selCidade = document.getElementById('cidade');
  var fLoc = document.getElementById('fLoc');
  var lista = document.getElementById('lista');
  var contador = document.getElementById('count');
  var mapa = null, marcadores = {}, camada = null;

  function norm(t) { return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function esc(t) { return String(t || '').replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  PONTOS.forEach(function (p) {
    p._txt = norm([p.n, p.r, p.t, p.sv, p.m, p.c.map(function (c) { return CATS[c] || ''; }).join(' ')].join(' '));
  });

  // filtro inicial pela URL: ?r=pneus
  // Palavras do dia a dia → tipo de resíduo ("cabo usb" → Eletrônicos)
  var SIN = [];
  Object.keys(window.SINONIMOS || {}).forEach(function (cat) {
    if (!CATS[cat]) return;
    SINONIMOS[cat].concat([CATS[cat]]).forEach(function (w) { SIN.push([norm(w), cat]); });
  });
  function parecido(a, b) {  // tolera um erro de digitação em palavras de 5+ letras
    if (a === b) return true;
    if (a.length < 5 || Math.abs(a.length - b.length) > 1) return false;
    var i = 0, j = 0, erros = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { i++; j++; continue; }
      if (++erros > 1) return false;
      if (a.length > b.length) i++; else if (b.length > a.length) j++; else { i++; j++; }
    }
    return erros + (a.length - i) + (b.length - j) <= 1;
  }
  function catsDaBusca(q) {
    var t = norm(q).trim(); if (!t) return [];
    var palavras = t.split(/\s+/).filter(function (w) { return w.length > 1 && ['de', 'da', 'do', 'e', 'o', 'a', 'os', 'as', 'para', 'onde', 'descartar', 'jogar', 'fora'].indexOf(w) < 0; });
    var achou = {};
    SIN.forEach(function (s) {
      var w = s[0], cat = s[1];
      if ((' ' + t + ' ').indexOf(' ' + w + ' ') >= 0 || (w.length >= 6 && t.indexOf(w) >= 0)) { achou[cat] = (achou[cat] || 0) + w.length; return; }
      var ws = w.split(' ');
      palavras.forEach(function (p) {
        ws.forEach(function (x) {
          if (parecido(p, x) || (p.length >= 4 && x.indexOf(p) === 0) || (x.length >= 4 && p.indexOf(x) === 0)) achou[cat] = (achou[cat] || 0) + 1;
        });
      });
    });
    return Object.keys(achou).sort(function (a, b) { return achou[b] - achou[a]; });
  }

  var busca = new URLSearchParams(location.search);
  var param = busca.get('r');
  if (param && CATS[param]) estado.cat = param;
  if (selCidade && busca.get('cidade')) { selCidade.value = busca.get('cidade'); estado.cid = selCidade.value; }
  if (busca.get('q')) { estado.q = busca.get('q'); document.getElementById('q').value = estado.q; }

  function passa(p) {
    if (estado.cid && p.cs.indexOf(estado.cid) < 0) return false;
    if (estado.cat && p.c.indexOf(estado.cat) < 0) return false;
    if (estado.p !== 'todos' && p.pp.indexOf(estado.p) < 0) return false;
    if (estado.lic && !(p.st === 'valida' || p.st === 'vencendo')) return false;
    if (estado.loc && !p.loc) return false;
    if (estado.q) {
      var qc = estado.qcats || [];
      for (var k = 0; k < qc.length; k++) if (p.c.indexOf(qc[k]) >= 0) return true;
      var termos = norm(estado.q).split(/\s+/).filter(Boolean);
      for (var i = 0; i < termos.length; i++) if (p._txt.indexOf(termos[i]) < 0) return false;
    }
    return true;
  }

  function telLink(t) {
    var primeiro = (t || '').split('/')[0].trim();
    var dig = primeiro.replace(/\D/g, '');
    return dig.length >= 10 ? '<a href="tel:+55' + dig + '">' + esc(t) + '</a>' : esc(t);
  }

  function cartao(p) {
    var h = '<article class="ponto" id="p-' + p.id + '" data-id="' + p.id + '">';
    h += '<h3>' + esc(p.n) + '</h3>';
    h += '<p class="tipo">' + esc(p.t) + ' · ' + esc(p.sv) + '</p>';
    h += '<p class="residuos">' + esc(p.r) + '</p>';
    var local = p.e ? p.e + (p.m ? ', ' + p.m : '') : p.m;
    if (local) h += '<p class="local">' + esc(local) + (p.loc || !p.m ? '' : ' (atende a cidade)') + '</p>';
    var cont = [];
    if (p.tel) cont.push(telLink(p.tel));
    if (p.site) {
      var href = /^http/.test(p.site) ? p.site : (p.site.indexOf('@') > 0 ? 'mailto:' + p.site : 'https://' + p.site);
      cont.push('<a href="' + esc(href) + '" target="_blank" rel="nofollow noopener">' + esc(p.site) + '</a>');
    }
    if (cont.length) h += '<p class="contato">' + cont.join(' · ') + '</p>';
    h += '<p class="licenca ' + p.lc + '">' + esc(p.lic) + '</p>';
    if (p.cnpj) h += '<p class="licenca aviso">' + esc(p.cnpj) + '</p>';
    if (p.obs) h += '<p class="obs">' + esc(p.obs) + '</p>';
    var acoes = [];
    if (p.a != null) {
      acoes.push('<button type="button" data-ver="' + p.id + '">Ver no mapa</button>');
      acoes.push('<a href="https://www.google.com/maps/dir/?api=1&destination=' + p.a + ',' + p.o + '" target="_blank" rel="noopener">Como chegar</a>');
    }
    if (acoes.length) h += '<p class="acoes">' + acoes.join('') + '</p>';
    return h + '</article>';
  }

  function sugestoes() {
    var ids = (estado.qcats && estado.qcats.length ? estado.qcats : []).slice(0, 4);
    var html = '<p class="vazio">Não encontramos <b>' + esc(estado.q || 'resultados') + '</b>' +
      (estado.cid || estado.cat || estado.lic || estado.loc || estado.p !== 'todos' ? ' com esses filtros.' : ' nesta cidade.') + '</p>';
    if (ids.length) html += '<p class="vazio">Isso costuma ir para: ' + ids.map(function (c) {
      return '<button type="button" class="chip" data-sug="' + c + '">' + esc(CATS[c]) + '</button>'; }).join(' ') + '</p>';
    html += '<p class="vazio">Veja todos os tipos: ' + Object.keys(CATS).map(function (c) {
      return '<button type="button" class="chip" data-sug="' + c + '">' + esc(CATS[c]) + '</button>'; }).join(' ') + '</p>';
    return html;
  }

  function render() {
    estado.qcats = catsDaBusca(estado.q || '');
    var vis = PONTOS.filter(passa).sort(function (a, b) {
      return (ORDEM[a.st] - ORDEM[b.st]) || ((a.loc ? 0 : 1) - (b.loc ? 0 : 1)) || a.n.localeCompare(b.n, 'pt-BR');
    });
    contador.textContent = vis.length;
    lista.innerHTML = vis.length ? vis.map(cartao).join('') : sugestoes();
    document.querySelectorAll('#chips .chip').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.cat === estado.cat ? 'true' : 'false'); });
    if (mapa) desenhar(vis);
    var url = new URL(location.href);
    if (estado.cat) url.searchParams.set('r', estado.cat); else url.searchParams.delete('r');
    if (estado.cid) url.searchParams.set('cidade', estado.cid); else url.searchParams.delete('cidade');
    history.replaceState(null, '', url);
  }

  function desenhar(vis) {
    camada.clearLayers();
    marcadores = {};
    var locais = [];
    vis.forEach(function (p) {
      if (p.a == null) return;
      var m = L.circleMarker([p.a, p.o], {
        radius: 8, weight: 2, color: '#fff', fillColor: CORES[p.st] || '#7A7F8C', fillOpacity: .95,
        dashArray: p.loc ? null : '3 2'
      }).bindPopup('<strong>' + esc(p.n) + '</strong><br>' + esc(p.r) + '<div class="pop-l">' + esc(p.lic) + '</div>');
      m.on('click', function () { destacar(p.id, false); });
      m.addTo(camada);
      marcadores[p.id] = m;
      if (p.loc) locais.push([p.a, p.o]);
    });
    var pts = locais.length ? locais : vis.filter(function (p) { return p.a != null; }).map(function (p) { return [p.a, p.o]; });
    if (!locais.length && pts.length > 2) {
      // ignora pontos muito distantes (empresas de outros estados) para o mapa abrir na região certa
      var med = function (i) { var v = pts.map(function (x) { return x[i]; }).sort(function (a, b) { return a - b; }); return v[Math.floor(v.length / 2)]; };
      var mLat = med(0), mLng = med(1);
      var perto = pts.filter(function (x) { return Math.abs(x[0] - mLat) < 1 && Math.abs(x[1] - mLng) < 1.2; });
      if (perto.length) pts = perto;
    }
    if (pts.length) mapa.fitBounds(L.latLngBounds(pts).pad(0.15), { maxZoom: 15 });
  }

  function destacar(id, voar) {
    document.querySelectorAll('.ponto.ativo').forEach(function (c) { c.classList.remove('ativo'); });
    var card = document.getElementById('p-' + id);
    if (card) { card.classList.add('ativo'); if (!voar) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
    var m = marcadores[id];
    if (voar && m && mapa) {
      mapa.setView(m.getLatLng(), Math.max(mapa.getZoom(), 14));
      m.openPopup();
      if (window.innerWidth < 860) document.getElementById('mapa').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // eventos
  var campoQ = document.getElementById('q');
  // Botão "×" para limpar a busca
  var envolve = document.createElement('span'); envolve.className = 'campo-q';
  campoQ.parentNode.insertBefore(envolve, campoQ); envolve.appendChild(campoQ);
  var xq = document.createElement('button');
  xq.type = 'button'; xq.className = 'limpar-q'; xq.setAttribute('aria-label', 'Limpar busca'); xq.textContent = '×';
  envolve.appendChild(xq);
  function mostraX() { xq.hidden = !campoQ.value; }
  xq.addEventListener('click', function () {
    campoQ.value = ''; estado.q = ''; estado.cat = null; mostraX(); render(); campoQ.focus();
  });
  mostraX();
  campoQ.addEventListener('input', function (e) { estado.q = e.target.value; mostraX(); render(); });
  document.getElementById('seg').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    estado.p = b.dataset.p;
    this.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    render();
  });
  document.getElementById('chips').addEventListener('click', function (e) {
    var b = e.target.closest('.chip'); if (!b) return;
    estado.cat = estado.cat === b.dataset.cat ? null : b.dataset.cat;
    render();
  });
  document.getElementById('fLic').addEventListener('change', function (e) { estado.lic = e.target.checked; render(); });
  if (fLoc) fLoc.addEventListener('change', function (e) { estado.loc = e.target.checked; render(); });
  if (selCidade) selCidade.addEventListener('change', function (e) { estado.cid = e.target.value; render(); });
  var form = document.getElementById('busca');
  if (form) form.addEventListener('submit', function (e) {
    e.preventDefault(); render();
    document.getElementById('resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.querySelectorAll('[data-atalho]').forEach(function (b) {
    b.addEventListener('click', function () {
      estado.cat = b.dataset.atalho; render();
      document.getElementById('resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
  document.getElementById('limpar').addEventListener('click', function () {
    estado = { q: '', p: 'todos', cat: null, lic: false, loc: false, cid: '' };
    document.getElementById('q').value = ''; mostraX();
    document.getElementById('fLic').checked = false;
    if (fLoc) fLoc.checked = false;
    if (selCidade) selCidade.value = '';
    document.querySelectorAll('#seg button').forEach(function (x) { x.setAttribute('aria-pressed', x.dataset.p === 'todos' ? 'true' : 'false'); });
    render();
  });
  lista.addEventListener('click', function (e) {
    var sg = e.target.closest('[data-sug]');
    if (sg) { estado.q = ''; document.getElementById('q').value = ''; estado.cat = sg.dataset.sug; render(); return; }
    var b = e.target.closest('[data-ver]'); if (b) destacar(b.dataset.ver, true);
  });

  function iniciarMapa() {
    if (!window.L) return;
    mapa = L.map('mapa', { scrollWheelZoom: false });
    var ruas = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(mapa);
    var sat = L.layerGroup([
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: 'Imagens &copy; Esri, Maxar, Earthstar Geographics' }),
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 })
    ]);
    L.control.layers({ 'Mapa': ruas, 'Satélite': sat }, null, { position: 'topright', collapsed: false }).addTo(mapa);
    camada = L.featureGroup().addTo(mapa);
  }

  render();
  if (window.L) { iniciarMapa(); render(); }
  else window.addEventListener('load', function () { iniciarMapa(); if (mapa) render(); });
})();
