/* Caixa "Em que dia passa a coleta na sua rua?": acha o setor da coleta comum e da seletiva pelo ponto
   (localização do celular ou toque no mapa). Os setores vêm do mapa oficial da prefeitura (setores.geojson). */
(function () {
  var box = document.getElementById('dia-coleta');
  if (!box) return;
  var res = document.getElementById('dc-res'), mapaEl = document.getElementById('dc-mapa');
  var SET = null, mapa = null, pino = null;
  var NOMES = { '2ª': 'segunda', '3ª': 'terça', '4ª': 'quarta', '5ª': 'quinta', '6ª': 'sexta', 'sábado': 'sábado' };
  function dias(t) {
    var p = t.replace(/\s+e\s+/g, ', ').split(/,\s*/).map(function (d) { d = d.trim(); return NOMES[d.toLowerCase()] || NOMES[d] || d; });
    return p.length > 1 ? p.slice(0, -1).join(', ') + ' e ' + p[p.length - 1] : p[0];
  }
  function dentro(x, y, anel) {
    var ok = false;
    for (var i = 0, j = anel.length - 1; i < anel.length; j = i++) {
      var xi = anel[i][0], yi = anel[i][1], xj = anel[j][0], yj = anel[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) ok = !ok;
    }
    return ok;
  }
  // distância em metros do ponto até a borda do polígono (o mapa da prefeitura deixa frestas nas ruas entre setores)
  function distBorda(lat, lng, anel) {
    var kx = 111320 * Math.cos(lat * Math.PI / 180), ky = 110540, min = Infinity;
    for (var i = 0, j = anel.length - 1; i < anel.length; j = i++) {
      var ax = (anel[j][0] - lng) * kx, ay = (anel[j][1] - lat) * ky, bx = (anel[i][0] - lng) * kx, by = (anel[i][1] - lat) * ky;
      var dx = bx - ax, dy = by - ay, t = (dx || dy) ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) : 0;
      min = Math.min(min, Math.hypot(ax + t * dx, ay + t * dy));
    }
    return min;
  }
  function acha(lat, lng) {
    var out = { comum: [], seletiva: [] }, perto = { comum: null, seletiva: null };
    SET.features.forEach(function (f) {
      var g = f.geometry, polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates, t = f.properties.tipo;
      if (polys.some(function (p) { return dentro(lng, lat, p[0]); })) out[t].push(f.properties);
      else polys.forEach(function (p) { var d = distBorda(lat, lng, p[0]); if (d < 80 && (!perto[t] || d < perto[t].d)) perto[t] = { d: d, p: f.properties }; });
    });
    ['comum', 'seletiva'].forEach(function (t) { if (!out[t].length && perto[t]) out[t].push(perto[t].p); });
    return out;
  }
  function linha(lista, rotulo) {
    if (!lista.length) return '<p><b>' + rotulo + ':</b> não achamos este ponto nos setores do mapa da prefeitura. Confirme o dia com a prefeitura ou com os vizinhos.</p>';
    var vistos = {};
    return lista.filter(function (p) { var k = p.dias + p.turno; if (vistos[k]) return false; return (vistos[k] = true); })
      .map(function (p) { return '<p><b>' + rotulo + ':</b> ' + dias(p.dias) + (p.turno ? ' (' + p.turno + ')' : '') + '.</p>'; }).join('');
  }
  function mostra(lat, lng) {
    var r = acha(lat, lng);
    res.innerHTML = linha(r.comum, 'Coleta comum (orgânico e rejeito)') + linha(r.seletiva, 'Coleta seletiva (recicláveis)') +
      '<p class="nota">Coloque o lixo para fora pouco antes do horário da coleta. Se mora perto do limite de um setor, confirme com os vizinhos ou com a prefeitura.</p>';
    res.hidden = false;
    if (mapa) { if (pino) pino.setLatLng([lat, lng]); else pino = L.marker([lat, lng]).addTo(mapa); mapa.setView([lat, lng], 15); }
  }
  function carrega(cb) {
    if (SET) return cb();
    fetch(box.dataset.setores).then(function (r) { return r.json(); }).then(function (j) { SET = j; cb(); })
      .catch(function () { res.hidden = false; res.textContent = 'Não foi possível carregar o mapa dos setores. Tente de novo.'; });
  }
  function abreMapa() {
    if (mapa || !window.L) return;
    mapaEl.hidden = false;
    document.getElementById('dc-mapa-btn').hidden = true;
    mapa = L.map(mapaEl).setView([+box.dataset.lat, +box.dataset.lng], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(mapa);
    mapa.on('click', function (e) { carrega(function () { mostra(e.latlng.lat, e.latlng.lng); }); });
  }
  function leaflet(cb) {
    if (window.L) return cb();
    var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.appendChild(css);
    var s = document.createElement('script'); s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; s.onload = cb; document.head.appendChild(s);
  }
  document.getElementById('dc-gps').addEventListener('click', function () {
    if (!navigator.geolocation) { res.hidden = false; res.textContent = 'Seu navegador não informa a localização. Toque no mapa.'; return; }
    res.hidden = false; res.textContent = 'Procurando sua localização…';
    navigator.geolocation.getCurrentPosition(function (pos) {
      var la = pos.coords.latitude, lo = pos.coords.longitude;
      carrega(function () { mostra(la, lo); });          // a resposta não depende do mapa carregar
      leaflet(function () { abreMapa(); if (SET) mostra(la, lo); });
    }, function () { res.textContent = 'Não foi possível usar sua localização. Toque no seu endereço no mapa.'; leaflet(abreMapa); }, { enableHighAccuracy: true, timeout: 10000 });
  });
  document.getElementById('dc-mapa-btn').addEventListener('click', function () { leaflet(abreMapa); this.hidden = true; });
})();
