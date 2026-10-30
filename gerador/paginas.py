"""Página inicial (busca única, estilo agregador) e guias por tipo de resíduo."""
import json
from html import escape as _esc

import guias as G
import hub

WHATSAPP = hub.WHATSAPP
CADASTRO = WHATSAPP + "?text=" + "Ol%C3%A1!%20Quero%20cadastrar%20minha%20empresa%20no%20Desvia."


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
    cats_js = json.dumps({s: nomes[s][1] for s, _ in cats_ordem}, ensure_ascii=False)
    faq = [
        ("De onde vêm os dados?", "Do licenciamento do IAT (base GeoPR e consulta SGA), do Cadastro Técnico Federal do IBAMA, da Receita Federal e das listas e páginas das prefeituras. Cada empresa mostra de onde veio a licença e a data da consulta."),
        ("Por que aparecem empresas sem licença?", "Porque elas operam e as pessoas encontram essas empresas de qualquer forma. O Desvia mostra todas, com a situação da licença bem visível: válida, vencida ou não localizada nas bases consultadas. Antes de contratar, peça a licença atual."),
        ("Sou empresa de coleta ou destinação. Como apareço com licença verificada?", "Mande sua licença pelo WhatsApp. Conferimos no órgão ambiental e atualizamos seu cadastro."),
        ("O Desvia é da prefeitura?", "Não. É um projeto independente que reúne informações públicas de várias fontes. Em cada cidade, as regras oficiais são as da prefeitura e do órgão ambiental."),
    ]
    faq_html = "".join(f'<details><summary>{esc(q)}</summary><p>{esc(r)}</p></details>' for q, r in faq)
    corpo = f"""<section class="hero-busca">
  <h1>Onde descartar cada resíduo.<br><em>Várias fontes, uma só busca.</em></h1>
  <p>Pontos de entrega, cooperativas e empresas de coleta e destinação, com a situação da licença ambiental de cada uma.</p>
  <form class="busca" id="busca" role="search">
    <label class="campo"><span>O que você quer descartar?</span><input id="q" type="search" placeholder="pilha, óleo, entulho, sofá, lâmpada…" autocomplete="off"></label>
    <label class="campo campo-cidade"><span>Cidade</span><select id="cidade"><option value="">Todas as cidades</option>{opcoes_cidade}</select></label>
    <button type="submit">Buscar</button>
  </form>
  <div class="atalhos" aria-label="Buscas comuns">{atalhos_html}</div>
  <ul class="numeros"><li><b>{total}</b> pontos e empresas</li><li><b>{n_lic}</b> com licença válida</li><li><b>{len(cidades)}</b> cidades</li><li><b>4</b> fontes oficiais</li></ul>
</section>

<section class="ferramenta" id="resultados" aria-label="Resultados">
  <aside class="painel">
    <div class="filtros">
      <div>
        <div class="flabel">Quem você procura</div>
        <div class="seg" role="group" aria-label="Tipo de atendimento" id="seg">
          <button type="button" data-p="todos" aria-pressed="true">Todos</button>
          <button type="button" data-p="entrega" aria-pressed="false">Ponto de entrega</button>
          <button type="button" data-p="recebe" aria-pressed="false">Recebe / destina</button>
          <button type="button" data-p="transporta" aria-pressed="false">Coleta / transporta</button>
        </div>
      </div>
      <div><div class="flabel">Tipo de resíduo</div><div class="chips" id="chips">{chips}</div></div>
      <div class="checks"><label><input type="checkbox" id="fLic"> Só com licença válida</label></div>
    </div>
    <div class="listhead"><span><b id="count">0</b> resultados</span><button type="button" class="limpar" id="limpar">Limpar filtros</button></div>
    <div class="lista-js" id="lista" aria-live="polite"></div>
  </aside>
  <div class="mapa-wrap"><div id="mapa" role="region" aria-label="Mapa"></div>
    <div class="legenda" aria-hidden="true"><span><i style="background:#2A7A2A"></i>Licença válida</span><span><i style="background:#C77700"></i>Vencendo ou vencida</span><span><i style="background:#1A3A8F"></i>Serviço público</span><span><i style="background:#7A7F8C"></i>Licença não localizada</span></div>
  </div>
</section>

<section class="passos" id="como-funciona">
  <h2>Como funciona</h2>
  <ol>
    <li><b>Reunimos as fontes</b><span>Licenças do IAT, cadastro do IBAMA, Receita Federal e listas das prefeituras, que hoje ficam em sites separados.</span></li>
    <li><b>Conferimos a licença</b><span>Cada empresa mostra se a licença está válida, vencida ou não foi localizada, com a data da consulta.</span></li>
    <li><b>Você escolhe com segurança</b><span>Filtre pelo resíduo e pela cidade, veja no mapa e fale direto com quem recebe.</span></li>
  </ol>
</section>

<section class="blocos">
  <div><h2>Guias de descarte</h2><p class="sub">Como descartar cada resíduo em casa e na empresa, o que diz a lei e onde levar.</p><ul class="grade">{guias_html}</ul><p><a href="guias/">Ver todos os guias →</a></p></div>
</section>

<section class="blocos">
  <div><h2>Cidades</h2><ul class="grade">{cidades_html}</ul>
  <p class="sub">Guia completo de Mandaguari, com coleta por bairro e regras municipais: <a href="mandaguari.html">abrir</a>.</p></div>
</section>

<section class="cta-dupla" id="empresas">
  <div class="cta"><h2>Para empresas que geram resíduos</h2><p>MTR, PGRS, inventário anual e logística reversa: veja o que a lei exige e encontre transportadores e destinadores licenciados.</p><a href="residuos/londrina/#empresas">Ver obrigações</a></div>
  <div class="cta cta-escura"><h2>Coleta, transporta ou recebe resíduos?</h2><p>Cadastre sua empresa e apareça com a licença verificada para quem procura.</p><a href="{CADASTRO}" target="_blank" rel="noopener">Cadastrar minha empresa</a></div>
</section>

<section class="faq"><h2>Perguntas frequentes</h2>{faq_html}</section>

<script>
var PONTOS = {hub.dados_js(pontos, "", ctx)};
var CATS = {cats_js};
</script>
<script src="residuos/hub.js" defer></script>"""
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
