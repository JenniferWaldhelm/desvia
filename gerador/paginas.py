"""Página inicial (busca única, estilo agregador) e guias por tipo de resíduo."""
import json
from sinonimos import SINONIMOS
from html import escape as _esc

import guias as G
import hub

WHATSAPP = hub.WHATSAPP
PREFEITURA = WHATSAPP + "?text=" + "Ol%C3%A1!%20Sou%20de%20uma%20prefeitura%20e%20quero%20saber%20mais%20sobre%20o%20Desvia."
CADASTRO = "https://docs.google.com/forms/d/e/1FAIpQLSdV7aBhtu6Lx6uHXM5MxB13WXaX9or0uAkJa9rJz395m_Rj4Q/viewform"  # formulário Google (cadastro de empresa / incluir cidade / correção)


def esc(t):
    return _esc(t or "", quote=True)


def home(pontos, cidades, nomes, cats_ordem, contagens, ctx, hoje):
    total = len(pontos)
    n_lic = sum(1 for p in pontos if p["_status"] in ("valida", "vencendo"))
    opcoes_cidade = "".join(f'<option value="{s}">{esc(c)}</option>' for s, c in cidades.items())
    chips = "".join(
        f'<button type="button" class="chip" data-cat="{s}" aria-pressed="false">{esc(nomes[s][1])} <span class="n">{n}</span></button>'
        for s, n in cats_ordem)
    atalhos = ["pilhas-e-baterias", "eletronicos", "oleo-de-cozinha", "entulho", "lampadas", "pneus", "medicamentos", "moveis-e-volumosos"]
    atalhos_html = "".join(f'<button type="button" data-atalho="{s}">{esc(nomes[s][1])}</button>'
                           for s in atalhos if s in dict(cats_ordem))
    guias_html = "".join(
        f'<li><a href="guias/{s}/"><span>{esc(nomes[s][1])}</span><small>{esc(G.GUIAS[s]["intro"][:80].rsplit(" ", 1)[0])}…</small></a></li>'
        for s in atalhos if s in G.GUIAS and s in dict(cats_ordem))
    cidades_html = "".join(
        f'<li><a href="residuos/{s}/"><span>{esc(c)}</span><small>{len(contagens[s])} tipos de resíduo</small></a></li>'
        for s, c in cidades.items())
    opcoes_tipo = "".join(f'<option value="{s}">{esc(nomes[s][1])}</option>' for s, _ in cats_ordem)
    cats_js = json.dumps({s: nomes[s][1] for s, _ in cats_ordem}, ensure_ascii=False)
    faq = [
        ("De onde vêm os dados?", "De dados públicos do IAT (licenciamento ambiental), do Cadastro Técnico Federal do IBAMA e das prefeituras municipais. Cada empresa mostra a fonte e a data da consulta."),
        ("Por que aparecem empresas sem licença?", "Porque elas operam e as pessoas encontram essas empresas de qualquer forma. O Desvia mostra todas, com a situação da licença bem visível: válida, vencida ou não localizada nas bases consultadas. Antes de contratar, peça a licença atual."),
        ("Sou empresa de coleta ou destinação. Como apareço com licença verificada?", "Mande sua licença pelo WhatsApp. Conferimos no órgão ambiental e atualizamos seu cadastro."),
        ("O Desvia é da prefeitura?", "Não. É um projeto independente que reúne informações públicas de várias fontes. Em cada cidade, as regras oficiais são as da prefeitura e do órgão ambiental."),
    ]
    faq_html = "".join(f'<details><summary>{esc(q)}</summary><p>{esc(r)}</p></details>' for q, r in faq)
    tiles = "".join(f'<li><button type="button" data-atalho="{s}">{esc(nomes[s][1])}</button></li>'
                    for s in atalhos if s in dict(cats_ordem))
    corpo = f"""<section class="abre">
 <div class="abre-texto">
  <h1>Onde levar o que você não usa mais</h1>
  <p class="abre-sub">Doar, vender, reciclar ou descartar. Pontos de entrega, brechós, cooperativas e empresas da sua cidade, com a licença ambiental conferida.</p>
  <form class="busca" id="busca" role="search" toolname="buscar_onde_descartar_formulario" tooldescription="Busca onde descartar um resíduo em uma cidade, com a licença ambiental de cada empresa.">
    <label class="campo"><span>O que você tem?</span><input id="q" name="q" type="search" toolparamdescription="Resíduo a descartar, por exemplo pilha, óleo, entulho" placeholder="sofá, roupa, pilha, remédio, entulho…" autocomplete="off"></label>
    <label class="campo campo-cidade"><span>Cidade</span><select id="cidade" name="cidade" toolparamdescription="Cidade"><option value="">Todas as cidades</option>{opcoes_cidade}</select></label>
    <button type="submit">Buscar</button>
    <details class="mais-filtros mf-home" id="maisFiltros"><summary>Filtros <span class="n-filtros" id="nFiltros"></span></summary><div class="busca-filtros">
      <label class="filtro"><span>O que você quer fazer</span><select id="fQuem" name="quem">
        <option value="todos">Tudo</option><option value="doar">Doar</option><option value="vender">Vender ou trocar</option>
        <option value="reciclar">Reciclar</option><option value="descartar">Descartar com segurança</option>
        <option value="empresa">Empresas: coleta e destinação</option></select></label>
      <label class="filtro"><span>Tipo de resíduo</span><select id="fTipo" name="tipo"><option value="">Todos os tipos</option>{opcoes_tipo}</select></label>
      <label class="filtro-lic"><input type="checkbox" id="fLic"> Esconder licença vencida ou não localizada</label>
    </div></details>
  </form>
  <p class="abre-nota"><button type="button" class="link-ajuda btn-perto" data-perto>Perto de mim</button> <button type="button" class="link-ajuda" data-ajuda>Não sei o que fazer</button></p>
 </div>
 <div class="abre-tipos">
  <h2>Mais procurados</h2>
  <ul class="tipos">{tiles}</ul>
 </div>
</section>

<section class="ferramenta" id="resultados" aria-label="Resultados">
  <aside class="painel">
    <div class="listhead"><span><b id="count">0</b> resultados</span><button type="button" class="limpar" id="limpar">Limpar filtros</button></div>
    <div class="lista-js" id="lista" aria-live="polite"></div>
  </aside>
  <div class="mapa-wrap"><div id="mapa" role="region" aria-label="Mapa"></div>
    <div class="legenda" role="group" aria-label="Filtrar pela situação da licença"><b>Situação</b><button type="button" data-st="valida" aria-pressed="true"><i style="background:#2A7A2A"></i>Válida</button><button type="button" data-st="vencida" aria-pressed="true"><i style="background:#C77700"></i>Vencendo ou vencida</button><button type="button" data-st="publico" aria-pressed="true"><i style="background:#1A3A8F"></i>Serviço público</button><button type="button" data-st="entrega" aria-pressed="true"><i style="background:#2B7A8C"></i>Ponto de entrega</button><button type="button" data-st="nao_localizada" aria-pressed="true"><i style="background:#7A7F8C"></i>Não localizada</button></div>
  </div>
</section>

<section class="faixa-empresas" id="empresas">
 <div class="fe-texto">
  <h2>Empresa responde pelo destino do próprio resíduo</h2>
  <p>Se quem coleta ou recebe não tem licença, a responsabilidade volta para quem gerou. O Desvia mostra a licença de cada empresa, com a fonte e a data da consulta: IAT, CTF/IBAMA e prefeitura.</p>
 </div>
 <ul class="fe-links">
  <li><a href="empresas/"><b>Sua empresa está em dia?</b></a></li>
  <li><a href="{CADASTRO}" target="_blank" rel="noopener"><b>Cadastrar minha empresa</b></a></li>
  <li><a href="{PREFEITURA}" target="_blank" rel="noopener"><b>Sou da prefeitura</b></a></li>
 </ul>
</section>

<div class="duas">
<section class="lista-sec">
  <h2>Guias de descarte</h2>
  <ul class="linhas">{guias_html}</ul>
  <p><a href="guias/">Todos os guias</a></p>
</section>
<section class="lista-sec">
  <h2>Cidades</h2>
  <ul class="linhas">{cidades_html}</ul>
  {pedir_cidade()}
  <p class="nota">Mandaguari tem um guia completo, com coleta por bairro: <a href="mandaguari.html">abrir</a>.</p>
</section>
</div>

<section class="faq"><h2>Perguntas frequentes</h2>{faq_html}</section>

<script>
var PONTOS = {hub.dados_js(pontos, "", ctx)};
var CATS = {cats_js};
var SINONIMOS = {json.dumps(SINONIMOS, ensure_ascii=False)};
var DESVIA_FORM = "{CADASTRO}";
var GRUPOS = {json.dumps(hub.grupos(ctx), ensure_ascii=False)};
var DESVIA_CIDADES = {json.dumps(cidades, ensure_ascii=False)};
</script>
<script src="residuos/hub.js" defer></script>
<script src="residuos/webmcp.js" defer></script>"""
    jsonld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "Desvia",
               "url": ctx["base"] + "/",
               "potentialAction": {"@type": "SearchAction", "target": ctx["base"] + "/?q={search_term_string}",
                                   "query-input": "required name=search_term_string"}},
              {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                  {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in faq]}]
    return corpo, jsonld


def guia(slug, nomes, contagens, cidades):
    g = G.GUIAS[slug]
    frase, curto = nomes[slug]
    casa = "".join(f"<li>{esc(x)}</li>" for x in g["casa"])
    lei = "".join(f"<li>{esc(x)}</li>" for x in g["lei"])
    onde = "".join(
        f'<li><a href="../../residuos/{c}/{slug}/"><span>{esc(nome)}</span><small>{contagens[c][slug]} {"opção" if contagens[c][slug] == 1 else "opções"}</small></a></li>'
        for c, nome in cidades.items() if slug in contagens[c])
    faq = g["faq"]
    faq_html = "".join(f'<details><summary>{esc(q)}</summary><p>{esc(r)}</p></details>' for q, r in faq)
    corpo = f"""<nav class="trilha" aria-label="Você está em"><a href="../../">Início</a> › <a href="../">Guias</a> › {esc(curto)}</nav>
<article class="guia">
<h1>Como descartar {esc(frase)}</h1>
<p class="resposta">{esc(g['intro'])}</p>
<nav class="sumario" aria-label="Neste guia"><a href="#casa">Em casa</a><a href="#empresa">Na empresa</a><a href="#lei">O que diz a lei</a><a href="#onde">Onde levar</a><a href="#duvidas">Dúvidas</a></nav>
<h2 id="casa">Em casa</h2><ul>{casa}</ul>
<h2 id="empresa">Na empresa</h2><p>{esc(g['empresa'])}</p>
<h2 id="lei">O que diz a lei</h2><ul>{lei}</ul>
<h2 id="onde">Onde levar</h2>
{f'<ul class="grade">{onde}</ul>' if onde else '<p>Ainda não temos pontos cadastrados para este resíduo nas cidades atendidas.</p>'}
<div class="cta-inline"><p><b>Precisa de ajuda com o PGRS ou com a destinação da sua empresa?</b> O Projeto Desvia orienta gratuitamente.</p><a href="{WHATSAPP}" target="_blank" rel="noopener">Falar no WhatsApp</a></div>
<h2 id="duvidas">Perguntas frequentes</h2>
<section class="faq">{faq_html}</section>
</article>"""
    jsonld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": f"Como descartar {frase}",
         "author": {"@type": "Organization", "name": "Projeto Desvia"}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in faq]},
    ]
    titulo = f"Como descartar {frase}: em casa, na empresa e onde levar | Desvia"
    descricao = f"Guia completo para descartar {frase}: passo a passo em casa, obrigações da empresa, o que diz a lei e pontos de entrega por cidade."
    return titulo, descricao, corpo, jsonld


def indice_guias(nomes, cats_ordem):
    itens = "".join(
        f'<li><a href="{s}/"><span>{esc(nomes[s][1])}</span><small>{esc(G.GUIAS[s]["intro"][:90].rsplit(" ", 1)[0])}…</small></a></li>'
        for s, _ in cats_ordem if s in G.GUIAS)
    return f"""<nav class="trilha" aria-label="Você está em"><a href="../">Início</a> › Guias</nav>
<h1>Guias de descarte</h1>
<p class="resposta">Como descartar cada tipo de resíduo em casa e na empresa, o que diz a lei e onde levar em cada cidade.</p>
<ul class="grade">{itens}</ul>"""


# ── Página para empresas: checklist + calendário + serviços técnicos ──
MAWE = "https://wa.me/5543920024725"
PERGUNTAS = [
    ("licenca", "Sua empresa tem licença ambiental válida (ou dispensa) para a atividade que exerce?",
     "Licença ambiental", "Sem licença válida, a operação pode ser embargada e multada (Lei 9.605/1998). A renovação deve ser pedida até 120 dias antes do vencimento (LC 140/2011)."),
    ("pgrs", "Tem um PGRS (Plano de Gerenciamento de Resíduos Sólidos) atualizado?",
     "PGRS", "Obrigatório para indústrias, serviços de saúde, construtoras, grandes geradores e quem gera resíduo perigoso (Lei 12.305/2010, art. 20). Muitos municípios exigem o PGRS para alvará."),
    ("mtr", "Emite o MTR (Manifesto de Transporte de Resíduos) no SINIR sempre que um resíduo sai da empresa?",
     "MTR", "O MTR acompanha cada transporte de resíduo e é obrigatório em todo o país desde 2021 (Portaria MMA 280/2020)."),
    ("cdf", "Destina só para empresas licenciadas e guarda os CDFs (Certificados de Destinação Final)?",
     "Destinação e CDF", "O gerador continua responsável pelo resíduo até a destinação final correta. O CDF é a prova de que ele chegou a um destino licenciado."),
    ("relatorios", "Entrega as declarações periódicas (DMR no SINIR e, se tiver CTF, o RAPP do IBAMA até 31 de março)?",
     "Declarações e relatórios", "A falta das declarações gera pendência no CTF/IBAMA e no SINIR, e pode impedir certidões e renovações."),
    ("equipe", "A equipe sabe separar, armazenar e registrar os resíduos?",
     "Treinamento da equipe", "Separação e armazenamento errados contaminam recicláveis, aumentam o custo da destinação e geram autuação em fiscalização."),
]

CALENDARIO = [
    ("A cada saída de resíduo", "Emitir o MTR no SINIR e receber o resíduo só com transportador licenciado."),
    ("A cada destinação", "Receber e arquivar o CDF do destinador."),
    ("Periodicamente", "Declarar no SINIR a movimentação de resíduos (DMR), no prazo do sistema."),
    ("Até 31 de março", "Entregar o RAPP do IBAMA referente ao ano anterior (empresas com CTF)."),
    ("120 dias antes do vencimento", "Pedir a renovação da licença ambiental, para que ela continue valendo durante a análise."),
    ("Quando mudar o processo", "Atualizar o PGRS e treinar a equipe."),
]

SERVICOS = ["Licenciamento ambiental (IAT e municípios)", "PGRS: elaboração e atualização", "MTR e declarações no SINIR",
            "Inventário e relatórios de resíduos (RAPP/CTF)", "Treinamento de equipes", "Regularização de pendências e renovações"]


def empresas():
    perguntas = "".join(
        f'<li><p>{esc(t)}</p><div class="ck-op" data-q="{k}">'
        f'<label><input type="radio" name="{k}" value="sim"> Sim</label>'
        f'<label><input type="radio" name="{k}" value="nao"> Não</label>'
        f'<label><input type="radio" name="{k}" value="ns"> Não sei</label></div></li>'
        for k, t, _, _ in PERGUNTAS)
    explica = json.dumps({k: [n, e] for k, _, n, e in PERGUNTAS}, ensure_ascii=False)
    cal = "".join(f"<li><b>{esc(q)}</b><span>{esc(o)}</span></li>" for q, o in CALENDARIO)
    serv = "".join(f"<li>{esc(s)}</li>" for s in SERVICOS)
    return f"""<nav class="trilha" aria-label="Você está em"><a href="../">Início</a> › Para empresas</nav>
<h1>Sua empresa está em dia com os resíduos?</h1>
<p class="resposta">Responda 6 perguntas e veja o que falta para cumprir a Política Nacional de Resíduos Sólidos. Leva um minuto e nada é enviado sem você pedir.</p>

<form class="checklist" id="checklist">
<ol>{perguntas}</ol>
<button type="submit">Ver resultado</button>
</form>
<div class="ck-resultado" id="ck-resultado" hidden></div>

<section class="calendario">
<h2>Calendário de obrigações</h2>
<ul class="cal">{cal}</ul>
<p class="sub">Encontre transportadores e destinadores licenciados na sua cidade: <a href="../residuos/">ver cidades</a>.</p>
</section>

<section class="servicos" id="servicos">
<div class="serv-box">
<span class="pq-tag">Serviços técnicos: Mawé Consultoria Ambiental</span>
<h2>Precisa de ajuda para regularizar?</h2>
<p>A equipe técnica por trás do Desvia faz:</p>
<ul class="serv-lista">{serv}</ul>
<a class="pq-btn" href="{MAWE}?text={DIAG_TXT}" target="_blank" rel="noopener">Pedir diagnóstico gratuito</a>
<p class="sub">WhatsApp da Mawé: (43) 92002-4725</p>
<p class="nota">O Desvia é independente: a ordem das empresas e a situação das licenças vêm só de dados públicos (IAT, IBAMA e prefeituras). Contratar serviços técnicos não muda nada na listagem.</p>
</div>
</section>

<script>
(function () {{
  var EXPLICA = {explica};
  var f = document.getElementById('checklist'), out = document.getElementById('ck-resultado');
  f.addEventListener('submit', function (e) {{
    e.preventDefault();
    var falta = [], duvida = [], resp = 0;
    Object.keys(EXPLICA).forEach(function (k) {{
      var v = (f.querySelector('input[name="' + k + '"]:checked') || {{}}).value;
      if (v) resp++;
      if (v === 'nao') falta.push(k); else if (v === 'ns' || !v) duvida.push(k);
    }});
    var ok = Object.keys(EXPLICA).length - falta.length - duvida.length;
    var item = function (k) {{ return '<li><b>' + EXPLICA[k][0] + ':</b> ' + EXPLICA[k][1] + '</li>'; }};
    var txt = 'Olá! Fiz o checklist do Desvia. ' + (falta.length ? 'Pendências: ' + falta.map(function (k) {{ return EXPLICA[k][0]; }}).join(', ') + '. ' : '') +
      (duvida.length ? 'Não sei: ' + duvida.map(function (k) {{ return EXPLICA[k][0]; }}).join(', ') + '. ' : '') + 'Quero um diagnóstico gratuito.';
    out.innerHTML = '<h2>' + (falta.length || duvida.length ? ok + ' de 6 em dia' : 'Tudo em dia. Parabéns!') + '</h2>' +
      (falta.length ? '<h3>O que falta</h3><ul>' + falta.map(item).join('') + '</ul>' : '') +
      (duvida.length ? '<h3>Vale conferir</h3><ul>' + duvida.map(item).join('') + '</ul>' : '') +
      (falta.length || duvida.length ? '<a class="pq-btn" target="_blank" rel="noopener" href="{MAWE}?text=' + encodeURIComponent(txt) + '">Pedir diagnóstico gratuito com estas respostas</a>' : '<p>Mantenha o calendário abaixo em dia.</p>');
    out.hidden = false; out.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }});
}})();
</script>"""


DIAG_TXT = "Ol%C3%A1!%20Vim%20pelo%20Desvia%20e%20quero%20um%20diagn%C3%B3stico%20gratuito%20dos%20res%C3%ADduos%20da%20minha%20empresa."


FORM = CADASTRO


def pedir_cidade():
    link = FORM or (WHATSAPP + "?text=" + "Ol%C3%A1!%20Quero%20pedir%20que%20o%20Desvia%20inclua%20a%20minha%20cidade%3A%20")
    return (f'<p class="pedir-cidade">Sua cidade ainda não está no Desvia? '
            f'<a href="{link}" target="_blank" rel="noopener">Peça para incluir</a>. As mais pedidas entram primeiro.</p>')


def privacidade(hoje):
    return f"""<nav class="trilha" aria-label="Você está em"><a href="../">Início</a> › Cookies e privacidade</nav>
<h1>Política de cookies e privacidade</h1>
<p class="resposta">O Desvia é um site de consulta. Você não precisa se cadastrar nem informar dados pessoais para buscar onde descartar.</p>
<section class="texto">
<h2>O que medimos</h2>
<ul>
<li><b>GoatCounter (sempre ativo, sem cookies):</b> conta visitas, páginas vistas e os termos digitados na busca do site, sem identificar quem visitou. Serve para saber o que as pessoas procuram e não encontram.</li>
<li><b>Google Analytics:</b> só grava cookies se você aceitar. Sem o aceite, o Google recebe apenas um sinal anônimo de visita, sem cookie e sem identificar você. Com o aceite, mede de onde vêm as visitas, quanto tempo ficam e em que aparelho. O Desvia vê esses dados só de forma agregada.</li>
</ul>
<h2>O que não fazemos</h2>
<ul>
<li>Não usamos cookies de anúncios nem de redes sociais.</li>
<li>Não vendemos nem compartilhamos dados de visitantes.</li>
<li>Não guardamos o que você digita na busca junto com nenhum dado seu.</li>
</ul>
<h2>Formulários e contato</h2>
<p>Os formulários de cadastro de empresa e de pedido de cidade são do Google Forms: o que você preencher vai para o Google e para a planilha do Desvia, e é usado só para incluir ou corrigir pontos no site. O contato por WhatsApp segue as regras do próprio WhatsApp.</p>
<h2>Seus direitos</h2>
<p>Pela Lei Geral de Proteção de Dados (Lei 13.709/2018), você pode pedir acesso, correção ou exclusão de dados que tenha enviado. Fale com a gente pelo <a href="{WHATSAPP}" target="_blank" rel="noopener">WhatsApp</a>.</p>
<h2>Mudar sua escolha</h2>
<p>Você pode aceitar ou recusar o Google Analytics a qualquer momento. <a href="#" data-cookies-abrir class="localizador-link">Abrir o aviso de cookies</a></p>
<p class="atualizado">Atualizada em {hoje:%d/%m/%Y}.</p>
</section>"""
