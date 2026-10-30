/* Mapa com filtros da página de cada cidade. Dados em PONTOS e CATS (definidos na página). */
(function () {
  var CORES = { valida: '#2A7A2A', vencendo: '#C77700', vencida: '#C77700', publico: '#1A3A8F', nao_localizada: '#7A7F8C' };
  var ORDEM = { valida: 0, vencendo: 1, publico: 2, vencida: 3, nao_localizada: 4 };
  var estado = { q: '', p: 'todos', cat: null, lic: false, loc: false };
  var lista = document.getElementById('lista');
  var contador = document.getElementById('count');
  var mapa = null, marcadores = {}, camada = null;

  function norm(t) { return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function esc(t) { return String(t || '').replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  PONTOS.forEach(function (p) {
    p._txt = norm([p.n, p.r, p.t, p.sv, p.m, p.c.map(function (c) { return CATS[c] || ''; }).join(' ')].join(' '));
  });

  // filtro inicial pela URL: ?r=pneus
  var param = new URLSearchParams(location.search).get('r');
  if (param && CATS[param]) estado.cat = param;

  function passa(p) {
    if (estado.cat && p.c.indexOf(estado.cat) < 0) return false;
    if (estado.p !== 'todos' && p.pp.indexOf(estado.p) < 0) return false;
    if (estado.lic && !(p.st === 'valida' || p.st === 'vencendo')) return false;
    if (estado.loc && !p.loc) return false;
    if (estado.q) {
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

  function render() {
    var vis = PONTOS.filter(passa).sort(function (a, b) {
      return (ORDEM[a.st] - ORDEM[b.st]) || ((a.loc ? 0 : 1) - (b.loc ? 0 : 1)) || a.n.localeCompare(b.n, 'pt-BR');
    });
    contador.textContent = vis.length;
    lista.innerHTML = vis.length ? vis.map(cartao).join('') :
      '<p class="vazio">Nenhum resultado com esses filtros. Tente tirar algum filtro ou buscar outra palavra.</p>';
    document.querySelectorAll('#chips .chip').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.cat === estado.cat ? 'true' : 'false'); });
    if (mapa) desenhar(vis);
    var url = new URL(location.href);
    if (estado.cat) url.searchParams.set('r', estado.cat); else url.searchParams.delete('r');
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
  document.getElementById('q').addEventListener('input', function (e) { estado.q = e.target.value; render(); });
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
  document.getElementById('fLoc').addEventListener('change', function (e) { estado.loc = e.target.checked; render(); });
  document.getElementById('limpar').addEventListener('click', function () {
    estado = { q: '', p: 'todos', cat: null, lic: false, loc: false };
    document.getElementById('q').value = '';
    document.getElementById('fLic').checked = false;
    document.getElementById('fLoc').checked = false;
    document.querySelectorAll('#seg button').forEach(function (x) { x.setAttribute('aria-pressed', x.dataset.p === 'todos' ? 'true' : 'false'); });
    render();
  });
  lista.addEventListener('click', function (e) {
    var b = e.target.closest('[data-ver]'); if (b) destacar(b.dataset.ver, true);
  });

  function iniciarMapa() {
    if (!window.L) return;
    mapa = L.map('mapa', { scrollWheelZoom: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap' }).addTo(mapa);
    camada = L.featureGroup().addTo(mapa);
  }

  render();
  if (window.L) { iniciarMapa(); render(); }
  else window.addEventListener('load', function () { iniciarMapa(); if (mapa) render(); });
})();
