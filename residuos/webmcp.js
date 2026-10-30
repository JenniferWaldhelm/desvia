/* WebMCP: expõe a busca do Desvia como ferramentas para assistentes de IA no navegador
   (navigator.modelContext). Usa os dados já carregados na página (PONTOS e CATS).
   Em navegadores sem WebMCP, não faz nada. */
(function () {
  var mc = navigator.modelContext;
  if (!mc || typeof mc.registerTool !== 'function' || typeof PONTOS === 'undefined') return;

  var BASE = 'https://jenniferwaldhelm.github.io/desvia/';
  var CIDADES = window.DESVIA_CIDADES || {};
  var STATUS = { valida: 'licença válida', vencendo: 'licença vencendo', vencida: 'licença vencida', publico: 'serviço público', nao_localizada: 'licença não localizada nas bases consultadas' };

  function norm(t) { return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function resposta(obj) { return { content: [{ type: 'text', text: JSON.stringify(obj) }] }; }

  function acharCategoria(txt) {
    if (!txt) return null;
    var n = norm(txt);
    if (CATS[n]) return n;
    for (var k in CATS) if (norm(CATS[k]).indexOf(n) >= 0 || n.indexOf(norm(CATS[k])) >= 0) return k;
    return null;
  }
  function acharCidade(txt) {
    if (!txt) return null;
    var n = norm(txt).replace(/\s+/g, '-');
    for (var k in CIDADES) if (k === n || norm(CIDADES[k]) === norm(txt)) return k;
    return null;
  }

  var tipos = Object.keys(CATS);
  var cidades = Object.keys(CIDADES);

  mc.registerTool({
    name: 'buscar_onde_descartar',
    description: 'Busca pontos de entrega, cooperativas e empresas que coletam, transportam ou recebem um tipo de resíduo em uma cidade, com a situação da licença ambiental de cada uma. Fontes: IAT, IBAMA, Receita Federal e prefeituras.',
    inputSchema: {
      type: 'object',
      properties: {
        residuo: { type: 'string', description: 'Tipo de resíduo. Valores aceitos: ' + tipos.join(', ') + '. Também aceita texto livre como "pilha" ou "sofá".' },
        cidade: { type: 'string', description: 'Cidade. Valores aceitos: ' + cidades.join(', ') + '.' },
        quem: { type: 'string', enum: ['todos', 'entrega', 'recebe', 'transporta'], description: 'entrega = ponto de entrega para a população; recebe = recebe ou dá destinação final; transporta = coleta ou transporta.' },
        so_licenca_valida: { type: 'boolean', description: 'Se verdadeiro, retorna só quem tem licença ambiental válida localizada.' },
        limite: { type: 'integer', minimum: 1, maximum: 50, description: 'Número máximo de resultados (padrão 15).' }
      }
    },
    annotations: { readOnlyHint: true },
    execute: function (args) {
      args = args || {};
      var cat = acharCategoria(args.residuo);
      var cid = acharCidade(args.cidade);
      var termo = !cat && args.residuo ? norm(args.residuo) : '';
      var ordem = { valida: 0, vencendo: 1, publico: 2, vencida: 3, nao_localizada: 4 };
      var lista = PONTOS.filter(function (p) {
        if (cat && p.c.indexOf(cat) < 0) return false;
        if (cid && p.cs.indexOf(cid) < 0) return false;
        if (termo && norm([p.n, p.r].join(' ')).indexOf(termo) < 0) return false;
        if (args.quem && args.quem !== 'todos' && p.pp.indexOf(args.quem) < 0) return false;
        if (args.so_licenca_valida && !(p.st === 'valida' || p.st === 'vencendo')) return false;
        return true;
      }).sort(function (a, b) { return ordem[a.st] - ordem[b.st]; });
      var limite = Math.min(Math.max(args.limite || 15, 1), 50);
      return resposta({
        total: lista.length,
        filtros: { residuo: cat || args.residuo || null, cidade: cid || null },
        pagina: BASE + (cid ? 'residuos/' + cid + '/' + (cat ? cat + '/' : '') : ''),
        resultados: lista.slice(0, limite).map(function (p) {
          return {
            nome: p.n, tipo: p.t, servico: p.sv, residuos: p.r,
            endereco: [p.e, p.m].filter(Boolean).join(', '), telefone: p.tel || null,
            licenca: p.lic, situacao_licenca: STATUS[p.st], aviso_cnpj: p.cnpj || null,
            mapa: p.a != null ? 'https://www.google.com/maps/search/?api=1&query=' + p.a + ',' + p.o : null
          };
        }),
        aviso: 'Situação da licença conforme as bases públicas na data indicada. Antes de contratar, peça a licença atual à empresa.'
      });
    }
  });

  mc.registerTool({
    name: 'listar_residuos_e_cidades',
    description: 'Lista os tipos de resíduo e as cidades atendidas pelo Desvia, com links para os guias de descarte.',
    inputSchema: { type: 'object', properties: {} },
    annotations: { readOnlyHint: true },
    execute: function () {
      return resposta({
        cidades: cidades.map(function (k) { return { id: k, nome: CIDADES[k], pagina: BASE + 'residuos/' + k + '/' }; }),
        residuos: tipos.map(function (k) { return { id: k, nome: CATS[k], guia: BASE + 'guias/' + k + '/' }; })
      });
    }
  });
})();
