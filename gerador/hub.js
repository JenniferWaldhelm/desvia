/* Mapa com filtros da página de cada cidade. Dados em PONTOS e CATS (definidos na página). */
(function () {
  var CORES = { valida: '#2A7A2A', vencendo: '#C77700', vencida: '#C77700', publico: '#1A3A8F', nao_localizada: '#7A7F8C' };
  var ORDEM = { valida: 0, vencendo: 1, publico: 2, vencida: 3, nao_localizada: 4 };
  var estado = { q: '', p: 'todos', cat: null, lic: false, loc: false, cid: '', fora: {} };
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
    if (estado.lic && !(p.st === 'valida' || p.st === 'vencendo' || p.st === 'publico')) return false;
    if (estado.loc && !p.loc) return false;
    if (estado.fora[p.st === 'vencendo' ? 'vencida' : p.st]) return false;
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
    if (window.DESVIA_FORM) acoes.push('<a class="informar" href="' + DESVIA_FORM + '" target="_blank" rel="noopener" title="Fechou, mudou de endereço ou não recebe mais? Avise o Desvia">Informar problema</a>');
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

  // Registra o que as pessoas buscam (e o que não acham) no contador de visitas, se estiver ligado
  var tBusca;
  function registrar(caminho) {
    try { if (window.goatcounter && goatcounter.count) goatcounter.count({ path: caminho, title: caminho, event: true }); } catch (e) {}
  }
  function registrarBusca(n) {
    clearTimeout(tBusca);
    var q = norm(estado.q || '').trim();
    if (q.length < 3) return;
    tBusca = setTimeout(function () {
      registrar((n ? 'busca/' : 'busca-sem-resultado/') + (estado.cid || 'todas') + '/' + q.replace(/\s+/g, '-'));
    }, 1500);
  }
  var POR_PAGINA = 20, limite = POR_PAGINA, visAtual = [];
  function render(mais) {
    if (!mais) limite = POR_PAGINA;
    estado.qcats = catsDaBusca(estado.q || '');
    var vis = PONTOS.filter(passa).sort(function (a, b) {
      return (ORDEM[a.st] - ORDEM[b.st]) || ((a.loc ? 0 : 1) - (b.loc ? 0 : 1)) || a.n.localeCompare(b.n, 'pt-BR');
    });
    contador.textContent = vis.length;
    visAtual = vis;
    if (!mais) registrarBusca(vis.length);
    var resto = vis.length - limite;
    lista.innerHTML = vis.length ? vis.slice(0, limite).map(cartao).join('') +
      (resto > 0 ? '<button type="button" class="mais" data-mais="1">Mostrar mais ' + Math.min(resto, POR_PAGINA) + ' (faltam ' + resto + ')</button>' : '') : sugestoes();
    document.querySelectorAll('#chips .chip').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.cat === estado.cat ? 'true' : 'false'); });
    document.querySelectorAll('.legenda [data-st]').forEach(function (b) { b.setAttribute('aria-pressed', estado.fora[b.dataset.st] ? 'false' : 'true'); });
    document.querySelectorAll('#seg button').forEach(function (x) { x.setAttribute('aria-pressed', x.dataset.p === estado.p ? 'true' : 'false'); });
    var fq = document.getElementById('fQuem'), ft = document.getElementById('fTipo');
    if (fq) fq.value = estado.p; if (ft) ft.value = estado.cat || '';
    if (mapa && !mais) desenhar(vis);
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
    if (!card) {  // cartão ainda não exibido: abre a lista até ele
      var pos = visAtual.map(function (p) { return p.id; }).indexOf(id);
      if (pos >= limite) { limite = pos + 1; var y = window.scrollY; render(true); window.scrollTo(0, y); card = document.getElementById('p-' + id); }
    }
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
    campoQ.value = ''; estado.q = ''; estado.cat = null; mostraX(); caixa.hidden = true; render(); campoQ.focus();
  });
  mostraX();
  // Sugestões enquanto digita (tipos de resíduo e empresas)
  var caixa = document.createElement('div'); caixa.className = 'sugere'; caixa.hidden = true;
  caixa.setAttribute('role', 'listbox'); envolve.appendChild(caixa);
  var ativoSug = -1;
  function contaCat(c) {
    return PONTOS.filter(function (p) { return p.c.indexOf(c) >= 0 && (!estado.cid || p.cs.indexOf(estado.cid) >= 0); }).length;
  }
  function sugerir() {
    var t = norm(campoQ.value).trim(); ativoSug = -1;
    if (t.length < 2) { caixa.hidden = true; return; }
    var itens = [];
    var porNome = Object.keys(CATS).filter(function (c) { return norm(CATS[c]).indexOf(t) >= 0; });
    var cats = porNome.concat(catsDaBusca(campoQ.value).filter(function (c) { return porNome.indexOf(c) < 0; }));
    cats.slice(0, 4).forEach(function (c) {
      var n = contaCat(c); itens.push({ tipo: 'cat', v: c, txt: CATS[c], n: n ? n + (n > 1 ? ' locais' : ' local') : 'nenhum local nesta cidade' });
    });
    // Nome de estabelecimento só aparece quando o que foi digitado não é um tipo de resíduo
    // (a pergunta é "O que você tem?": primeiro o material, o local vem depois)
    var vistos = {};
    if (!itens.length && t.length >= 3) PONTOS.forEach(function (p) {
      if (itens.length >= 5 || vistos[p.n]) return;
      if ((!estado.cid || p.cs.indexOf(estado.cid) >= 0) && norm(p.n).indexOf(t) >= 0) { vistos[p.n] = 1; itens.push({ tipo: 'emp', v: p.n, txt: p.n, n: p.m }); }
    });
    if (!itens.length) { caixa.hidden = true; return; }
    caixa.innerHTML = (itens[0].tipo === 'emp' ? '<div class="sug-titulo">Locais com esse nome</div>' : '') + itens.map(function (it, i) {
      return '<button type="button" role="option" data-i="' + i + '" data-tipo="' + it.tipo + '" data-v="' + esc(it.v) + '">' +
        '<span>' + (it.tipo === 'cat' ? '♻ ' : '🏢 ') + esc(it.txt) + '</span><small>' + esc(it.n) + '</small></button>';
    }).join('');
    caixa.hidden = false;
  }
  function escolher(b) {
    if (b.dataset.tipo === 'cat') { estado.cat = b.dataset.v; estado.q = ''; campoQ.value = ''; }
    else { estado.cat = null; estado.q = b.dataset.v; campoQ.value = b.dataset.v; }
    caixa.hidden = true; mostraX(); render();
    var r = document.getElementById('resultados'); if (r && r.scrollIntoView) r.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  caixa.addEventListener('mousedown', function (e) { e.preventDefault(); });
  caixa.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) escolher(b); });
  campoQ.addEventListener('keydown', function (e) {
    var bs = caixa.hidden ? [] : caixa.querySelectorAll('button');
    if (!bs.length) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault(); ativoSug = (ativoSug + (e.key === 'ArrowDown' ? 1 : -1) + bs.length) % bs.length;
      bs.forEach(function (b, i) { b.classList.toggle('ativo', i === ativoSug); });
    } else if (e.key === 'Enter' && ativoSug >= 0) { e.preventDefault(); escolher(bs[ativoSug]); }
    else if (e.key === 'Escape') caixa.hidden = true;
  });
  campoQ.addEventListener('blur', function () { setTimeout(function () { caixa.hidden = true; }, 150); });
  campoQ.addEventListener('focus', sugerir);
  campoQ.addEventListener('input', function (e) {
    estado.q = e.target.value; estado.cat = null;  // digitar troca a busca, não soma com o tipo escolhido antes
    mostraX(); sugerir(); render();
  });
  var segEl = document.getElementById('seg') || document.createElement('div');
  var chipsEl = document.getElementById('chips') || document.createElement('div');
  var leg = document.querySelector('.legenda');
  if (leg) leg.addEventListener('click', function (e) {
    var b = e.target.closest('[data-st]'); if (!b) return;
    var st = b.dataset.st, ligados = Object.keys(estado.fora).length;
    if (!estado.fora[st] && ligados === 0) {  // primeiro toque: mostra só esta
      ['valida', 'vencida', 'publico', 'nao_localizada'].forEach(function (x) { if (x !== st) estado.fora[x] = true; });
    } else if (estado.fora[st]) { delete estado.fora[st]; }
    else { estado.fora[st] = true; if (Object.keys(estado.fora).length === 4) estado.fora = {}; }
    render();
  });
  var fQuem = document.getElementById('fQuem'), fTipo = document.getElementById('fTipo');
  if (fQuem) fQuem.addEventListener('change', function (e) { estado.p = e.target.value; render(); });
  if (fTipo) fTipo.addEventListener('change', function (e) { estado.cat = e.target.value || null; render(); });
  segEl.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    estado.p = b.dataset.p;
    this.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    render();
  });
  chipsEl.addEventListener('click', function (e) {
    var b = e.target.closest('.chip'); if (!b) return;
    estado.cat = estado.cat === b.dataset.cat ? null : b.dataset.cat;
    render();
  });
  document.getElementById('fLic').addEventListener('change', function (e) { estado.lic = e.target.checked; render(); });
  if (fLoc) fLoc.addEventListener('change', function (e) { estado.loc = e.target.checked; render(); });
  if (selCidade) selCidade.addEventListener('change', function (e) { estado.cid = e.target.value; render(); });
  var form = document.getElementById('busca');
  if (form) form.addEventListener('submit', function (e) {
    e.preventDefault(); caixa.hidden = true; render();
    document.getElementById('resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.querySelectorAll('[data-atalho]').forEach(function (b) {
    b.addEventListener('click', function () {
      estado.cat = b.dataset.atalho; render();
      document.getElementById('resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // ── Assistente "Me ajude a decidir" ──
  var REUSO = ['eletronicos', 'moveis-e-volumosos', 'texteis', 'madeira', 'sucata-metalica'];
  var PERIGO = ['medicamentos', 'pilhas-e-baterias', 'lampadas', 'oleo-de-cozinha', 'oleo-lubrificante', 'pneus', 'entulho',
    'residuos-de-saude', 'tintas-e-solventes', 'embalagens-de-agrotoxico', 'limpa-fossa', 'residuos-perigosos', 'poda-e-galhos'];
  var NOME_ACAO = { doar: 'doar', vender: 'vender ou trocar', reciclar: 'reciclar', descartar: 'descartar com segurança', empresa: 'contratar coleta' };
  var dlg = document.createElement('dialog'); dlg.className = 'ajuda'; document.body.appendChild(dlg);
  function contaAcao(cat, ac) {
    return PONTOS.filter(function (p) { return p.c.indexOf(cat) >= 0 && (!ac || p.pp.indexOf(ac) >= 0) && (!estado.cid || p.cs.indexOf(estado.cid) >= 0); }).length;
  }
  function tela(html) { dlg.innerHTML = '<button type="button" class="ajuda-x" data-fechar aria-label="Fechar">×</button>' + html; if (!dlg.open) { try { dlg.showModal(); } catch (e) { dlg.setAttribute('open', ''); } } }
  function botoesAcao(cat, lista) {
    var b = lista.map(function (ac) { var n = contaAcao(cat, ac); return n ? '<button type="button" class="ajuda-ok" data-ir="' + cat + '|' + ac + '">Ver onde ' + NOME_ACAO[ac] + ' (' + n + ')</button>' : ''; }).join('');
    if (!b) { var t = contaAcao(cat, null); b = t ? '<button type="button" class="ajuda-ok" data-ir="' + cat + '|todos">Ver todos os lugares (' + t + ')</button>' : '<p>Ainda não temos lugares para isso nesta cidade. Fale com a prefeitura ou mande uma mensagem para o Desvia.</p>'; }
    return '<div class="ajuda-acoes">' + b + '</div>';
  }
  function linksGrupos() {
    var G = window.GRUPOS || {}, cid = estado.cid || (Object.keys(window.DESVIA_CIDADES || {}).length === 1 ? Object.keys(DESVIA_CIDADES)[0] : '');
    var cids = cid ? [cid] : Object.keys(G);
    var h = cids.filter(function (c) { return G[c]; }).map(function (c) {
      return '<p class="ajuda-grupos">' + (cid ? '' : '<b>' + esc((window.DESVIA_CIDADES || {})[c] || c) + ':</b> ') +
        G[c].map(function (g) { return '<a href="' + esc(g.l) + '" target="_blank" rel="noopener nofollow">' + esc(g.n) + ' ↗</a>'; }).join(' · ') + '</p>';
    }).join('');
    return h ? '<div class="ajuda-doar">' + h + '</div>' : '';
  }
  function passo1() {
    var cats = Object.keys(CATS).filter(function (c) { return contaAcao(c, null) > 0; });
    tela('<h2>O que você tem?</h2><input type="search" class="ajuda-q" placeholder="Digite: sofá, celular, remédio…" autocomplete="off">' +
      '<div class="ajuda-cats">' + cats.map(function (c) { return '<button type="button" class="chip" data-c="' + c + '">' + esc(CATS[c]) + '</button>'; }).join('') + '</div>');
    var q = dlg.querySelector('.ajuda-q'); q.focus();
    q.addEventListener('input', function () {
      var achou = catsDaBusca(q.value), t = norm(q.value);
      dlg.querySelectorAll('.ajuda-cats .chip').forEach(function (b) {
        b.hidden = !!t && achou.indexOf(b.dataset.c) < 0 && norm(b.textContent).indexOf(t) < 0;
      });
    });
  }
  function passo2(cat) {
    if (REUSO.indexOf(cat) >= 0) {
      tela('<h2>' + esc(CATS[cat]) + '</h2><p>Ainda funciona ou está em bom estado?</p><div class="ajuda-acoes">' +
        '<button type="button" class="ajuda-ok" data-estado="' + cat + '|bom">Sim, ainda dá para usar</button>' +
        '<button type="button" class="ajuda-ok ajuda-sec" data-estado="' + cat + '|ruim">Não, está quebrado ou gasto</button></div>');
    } else if (PERIGO.indexOf(cat) >= 0) {
      tela('<h2>' + esc(CATS[cat]) + '</h2><p><b>Isso não pode ir para o lixo comum.</b> Leve a um ponto de descarte seguro. Se for empresa ou volume grande, contrate coleta licenciada.</p>' + botoesAcao(cat, ['descartar', 'reciclar', 'empresa']));
    } else {
      tela('<h2>' + esc(CATS[cat]) + '</h2><p>Separe, limpe se precisar, e leve para reciclar. Há quem compre alguns materiais.</p>' + botoesAcao(cat, ['reciclar', 'vender', 'descartar', 'empresa']));
    }
  }
  function passo3(cat, bom) {
    if (bom) {
      var temReuso = contaAcao(cat, 'doar') + contaAcao(cat, 'vender') > 0;
      tela('<h2>Ótimo: dá para continuar sendo usado</h2><p>Doar ou vender evita que vire lixo e ajuda alguém.' +
        (temReuso ? ' Veja quem recebe:' : ' Ainda não temos aqui lugares que recebem doação disso, mas dá para anunciar em grupos de doação do bairro, no Marketplace ou na OLX, ou oferecer para instituições e vizinhos. Se não der certo:') +
        '</p>' + linksGrupos() + botoesAcao(cat, temReuso ? ['doar', 'vender'] : ['reciclar', 'descartar']));
    }
    else tela('<h2>Então o melhor é reciclar ou descartar com segurança</h2><p>Muitas peças ainda viram matéria-prima. Veja onde levar:</p>' + botoesAcao(cat, ['reciclar', 'descartar', 'vender', 'empresa']));
  }
  dlg.addEventListener('click', function (e) {
    var t = e.target;
    if (t === dlg || t.closest('[data-fechar]')) { dlg.close ? dlg.close() : dlg.removeAttribute('open'); return; }
    var c = t.closest('[data-c]'); if (c) { registrar('assistente/' + c.dataset.c); return passo2(c.dataset.c); }
    var es = t.closest('[data-estado]'); if (es) { var x = es.dataset.estado.split('|'); return passo3(x[0], x[1] === 'bom'); }
    var ir = t.closest('[data-ir]');
    if (ir) {
      var y = ir.dataset.ir.split('|');
      estado.q = ''; campoQ.value = ''; mostraX(); estado.cat = y[0]; estado.p = y[1];
      dlg.close ? dlg.close() : dlg.removeAttribute('open'); render();
      var r = document.getElementById('resultados') || document.querySelector('.ferramenta');
      if (r) r.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
  document.querySelectorAll('[data-ajuda]').forEach(function (b) { b.addEventListener('click', passo1); });

  document.getElementById('limpar').addEventListener('click', function () {
    estado = { q: '', p: 'todos', cat: null, lic: false, loc: false, cid: '', fora: {} };
    document.getElementById('q').value = ''; mostraX();
    document.getElementById('fLic').checked = false;
    if (fLoc) fLoc.checked = false;
    if (selCidade) selCidade.value = '';
    document.querySelectorAll('#seg button').forEach(function (x) { x.setAttribute('aria-pressed', x.dataset.p === 'todos' ? 'true' : 'false'); });
    render();
  });
  lista.addEventListener('click', function (e) {
    if (e.target.closest('[data-mais]')) { limite += POR_PAGINA; render(true); return; }
    var sg = e.target.closest('[data-sug]');
    if (sg) { estado.q = ''; document.getElementById('q').value = ''; estado.cat = sg.dataset.sug; render(); return; }
    var b = e.target.closest('[data-ver]'); if (b) destacar(b.dataset.ver, true);
  });

  function iniciarMapa() {
    if (!window.L) return;
    mapa = L.map('mapa', { scrollWheelZoom: false });
    // Ctrl (ou Cmd) + rolagem dá zoom; rolagem sozinha rola a página e mostra o aviso
    var elMapa = document.getElementById('mapa'), aviso = document.createElement('div'), tAviso;
    aviso.className = 'aviso-zoom'; aviso.textContent = /Mac/.test(navigator.platform) ? 'Use ⌘ + rolagem para dar zoom no mapa' : 'Use Ctrl + rolagem para dar zoom no mapa';
    elMapa.parentNode.appendChild(aviso);
    elMapa.addEventListener('wheel', function (e) {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        var pt = mapa.mouseEventToContainerPoint(e);
        mapa.setZoomAround(pt, mapa.getZoom() + (e.deltaY < 0 ? 1 : -1));
        aviso.classList.remove('ver');
      } else {
        aviso.classList.add('ver'); clearTimeout(tAviso);
        tAviso = setTimeout(function () { aviso.classList.remove('ver'); }, 1200);
      }
    }, { passive: false });
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
