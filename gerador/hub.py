"""Página da cidade: mapa com filtros (estilo da ferramenta de Londrina) + obrigações das empresas."""
import json
from html import escape as _esc


def esc(t):
    return _esc(t or "", quote=True)


WHATSAPP = "https://wa.me/5544999054535"

# Conteúdo "Para empresas". Partes comuns valem para qualquer cidade do PR;
# LOCAL acrescenta o que é específico de cada município.
COMUM = [
    ("📋", "MTR — Obrigatório", "Manifesto de Transporte de Resíduos",
     "Toda movimentação de resíduo da sua empresa para fora do estabelecimento precisa de MTR. Ele registra o tipo de resíduo, a quantidade, o transportador e o destino final.",
     ["Obrigatório para resíduos Classe I (perigosos) e Classe II",
      "Emitido no sistema MTR Online do SINIR",
      "Transportador e destinador também assinam o MTR",
      "Guarde os MTRs por no mínimo 5 anos"],
     ("Acessar MTR Online (SINIR)", "https://mtr.sinir.gov.br/")),
    ("📊", "Inventário — Anual", "Inventário Anual de Resíduos Sólidos",
     "Empresas geradoras de resíduos perigosos declaram todo ano no SINIR quais resíduos geraram, quanto e para onde foram destinados.",
     ["Prazo: geralmente até 31 de março do ano seguinte",
      "Feito no sistema SINIR",
      "Inclui resíduos industriais, de saúde e perigosos"],
     ("Acessar SINIR", "https://sinir.gov.br/")),
    ("🏛️", "Licença — IAT/PR", "Licença ambiental (IAT)",
     "Algumas atividades exigem licença ou autorização do IAT antes de operar, como gerar, transportar ou tratar resíduos perigosos.",
     ["Licença Prévia (LP), de Instalação (LI) e de Operação (LO)",
      "Transportadoras de resíduos perigosos precisam de autorização do IAT",
      "Operar sem licença é crime ambiental (Lei 9.605/1998)"],
     ("Portal do IAT", "https://www.iat.pr.gov.br/")),
    ("♻️", "Logística reversa", "Devolução obrigatória após o uso",
     "Fabricantes, importadores, distribuidores e comerciantes são obrigados a receber de volta estes produtos depois do uso.",
     ["Pilhas, baterias e acumuladores", "Lâmpadas fluorescentes, de vapor e LED",
      "Óleos lubrificantes e embalagens", "Medicamentos e embalagens",
      "Eletrônicos e eletrodomésticos", "Pneus", "Embalagens de agrotóxicos"],
     ("Ver acordos setoriais no SINIR", "https://sinir.gov.br/")),
    ("🏭", "Destinação final", "Aterro ou empresa licenciada",
     "O que não tem reciclagem viável vai para aterro licenciado ou empresa de tratamento autorizada. O gerador continua responsável pelo destino final.",
     ["Aterro Classe I: resíduos perigosos", "Aterro Classe II: resíduos não perigosos",
      "Exija sempre o Certificado de Destinação Final (CDF) e guarde-o: ele prova que você cumpriu a lei"],
     None),
]

PGRS_GERAL = ("📁", "PGRS — Obrigatório", "Plano de Gerenciamento de Resíduos Sólidos",
              "O PGRS descreve como a empresa gera, separa, armazena e destina seus resíduos (Lei 12.305/2010, art. 20).",
              ["Indústrias, serviços de saúde e mineração",
               "Construtoras (PGRCC)",
               "Empresas que geram resíduos perigosos",
               "Comércios e serviços com resíduos que não se equiparam aos domiciliares"],
              None)

LOCAL = {
    "mandaguari": {
        "pgrs": ("📁", "PGRS — Obrigatório", "Plano de Gerenciamento de Resíduos Sólidos",
                 "Em Mandaguari, apresentar o PGRS é condição para obter alvará e certidões municipais (Lei Municipal 4.419/2025, art. 18).",
                 ["Indústrias, serviços de saúde e mineração, independente do volume",
                  "Comércios e serviços que geram resíduos perigosos (Classe I)",
                  "Grandes geradores: mais de 300 L/dia de resíduos equiparados aos domiciliares",
                  "Condomínios não residenciais acima de 1.000 L/dia",
                  "Construtoras: PGRCC para grandes geradores de RCC",
                  "Microempresas e EPP sem resíduo perigoso têm procedimento simplificado"],
                 None),
        "extra": [
            ("🧱", "Entulho e construção", "Descarte de entulho de obras",
             "Grandes geradores (acima de 1 m³/mês) contratam transportadora licenciada e garantem destinação em local licenciado. Mandaguari não tem usina de reciclagem de RCD própria: a destinação pode ser feita em municípios vizinhos. Resíduos Classe A (concreto, cerâmica) podem ser doados à prefeitura mediante laudo técnico e termo de doação junto à SMDEMAT.",
             ["Base legal: Lei Municipal 4.419/2025 e Resolução CONAMA 307/2002",
              "Caçambas: no máximo 72 horas na via pública (Lei Municipal 450/1999)"], None),
            ("🫙", "Óleo de cozinha", "Óleo de fritura usado",
             "A ACAMAN recebe óleo de fritura de residências e estabelecimentos em Mandaguari. Nunca despeje na pia ou no esgoto.",
             [], None),
        ],
        "orgao": "Secretaria de Meio Ambiente de Mandaguari",
    },
    "londrina": {
        "extra": [
            ("🧱", "Entulho e construção", "Descarte de entulho de obras",
             "Os PEVs públicos recebem até 1 m³ por pessoa por mês. Obras maiores contratam caçamba ou transportadora licenciada e garantem destinação em local licenciado.",
             ["Base legal: Resolução CONAMA 307/2002"], None),
            ("🫙", "Óleo de cozinha", "Óleo de fritura usado",
             "O Projeto Óleo Solidário, da Cáritas Arquidiocesana, e empresas licenciadas recebem óleo de fritura. Nunca despeje na pia ou no esgoto.",
             [], None),
        ],
        "orgao": "Secretaria Municipal do Ambiente (SEMA) de Londrina",
    },
}


def cartao_obrigacao(item):
    icone, tag, titulo, texto, lista, link = item
    ul = "".join(f"<li>{esc(x)}</li>" for x in lista)
    a = f'<a href="{esc(link[1])}" target="_blank" rel="noopener">{esc(link[0])} →</a>' if link else ""
    return (f'<article class="obr"><span class="obr-tag">{icone} {esc(tag)}</span><h3>{esc(titulo)}</h3>'
            f'<p>{esc(texto)}</p>{f"<ul>{ul}</ul>" if ul else ""}{a}</article>')


def secao_empresas(cid_slug, cidade):
    loc = LOCAL.get(cid_slug, {})
    itens = COMUM[:3] + [loc.get("pgrs", PGRS_GERAL)] + COMUM[3:] + loc.get("extra", [])
    orgao = loc.get("orgao", f"Secretaria de Meio Ambiente de {cidade}")
    cards = "".join(cartao_obrigacao(i) for i in itens)
    return f"""<section class="empresas" id="empresas">
<h2>Sua empresa tem obrigações com os resíduos que gera</h2>
<p class="resposta">A Lei Federal 12.305/2010 (Política Nacional de Resíduos Sólidos) define responsabilidades claras para empresas. Quem descumpre pode receber multa, ter a atividade embargada e responder criminalmente.</p>
<p class="regra">Isto é obrigação legal, não recomendação. Vale para comércios, indústrias, prestadores de serviço e construtoras em {esc(cidade)}. O órgão estadual é o IAT (Instituto Água e Terra). Dúvidas sobre o que se aplica à sua empresa: {esc(orgao)}.</p>
<div class="obr-grade">{cards}
<article class="obr obr-cta"><span class="obr-tag">💬 Precisa de orientação?</span><h3>Não sabe por onde começar?</h3><p>O Projeto Desvia ajuda a entender o que se aplica ao seu caso. Mande uma mensagem.</p><a href="{WHATSAPP}" target="_blank" rel="noopener">Chamar no WhatsApp →</a></article>
</div>
</section>"""


def papel(p):
    sv, tp = p["Serviço"], p["Tipo de ponto"]
    if tp in ("PEV público", "PEV privado", "Cooperativa/associação") and sv in ("Recebimento", "Triagem", "Coleta"):
        return ["entrega"]
    if tp == "Programa logística reversa":
        return ["entrega"]
    r = []
    if sv in ("Coleta", "Transporte", "Coleta + destinação"):
        r.append("transporta")
    if sv in ("Destinação final", "Tratamento", "Triagem", "Compra de recicláveis", "Coleta + destinação", "Recebimento"):
        r.append("recebe")
    if tp == "Cooperativa/associação":
        r.append("entrega")
    return r or ["recebe"]


def dados_js(pts, cid_slug, ctx):
    norm, selo, aviso_cnpj, obs_publica, pessoa_fisica = ctx["norm"], ctx["selo"], ctx["aviso_cnpj"], ctx["obs_publica"], ctx["pessoa_fisica"]
    out = []
    for p in pts:
        cls, lic = selo(p)
        end = p["Endereço"]
        if pessoa_fisica(p) or end.startswith("www."):
            end = ""
        site = p["Site/rede"] or (p["Endereço"] if p["Endereço"].startswith("www.") else "")
        out.append({
            "id": p["ID"].lower(), "n": p["Nome"], "t": p["Tipo de ponto"], "sv": p["Serviço"],
            "r": p["Resíduos aceitos"], "c": p["_cats"], "e": end, "m": p["Município sede"],
            "loc": norm(p["Município sede"]).replace(" ", "-") == cid_slug,
            "a": p["_lat"], "o": p["_lng"], "tel": p["Telefone"], "site": site,
            "st": p["_status"], "lic": lic, "lc": cls, "cnpj": aviso_cnpj(p), "obs": obs_publica(p),
            "pp": papel(p), "cs": sorted(p["_cidades"]),
        })
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def corpo_hub(cid_slug, cidade, pts, cats_ordem, nomes, por_cat, ctx):
    chips = "".join(
        f'<button type="button" class="chip" data-cat="{s}" aria-pressed="false">{esc(nomes[s][1])} <span class="n">{len(por_cat[s])}</span></button>'
        for s in cats_ordem)
    paginas = "".join(f'<li><a href="{s}/">Onde descartar {esc(nomes[s][0])}</a></li>' for s in cats_ordem)
    cats_js = json.dumps({s: nomes[s][1] for s in cats_ordem}, ensure_ascii=False)
    return f"""<nav class="trilha" aria-label="Você está em"><a href="../">Cidades</a> › {esc(cidade)}</nav>
<h1>Onde descartar resíduos em {esc(cidade)}</h1>
<p class="resposta">Pontos de entrega, cooperativas e empresas que coletam, transportam e recebem resíduos em {esc(cidade)} e região, com a situação da licença ambiental de cada uma. Filtre pelo tipo de resíduo.</p>

<section class="ferramenta" aria-label="Mapa e lista com filtros">
  <aside class="painel">
    <div class="filtros">
      <input id="q" type="search" placeholder="Buscar: pilha, óleo, caçamba, nome da empresa…" autocomplete="off" aria-label="Buscar">
      <div>
        <div class="flabel">Quem você procura</div>
        <div class="seg" role="group" aria-label="Tipo de atendimento" id="seg">
          <button type="button" data-p="todos" aria-pressed="true">Todos</button>
          <button type="button" data-p="entrega" aria-pressed="false">Ponto de entrega</button>
          <button type="button" data-p="recebe" aria-pressed="false">Recebe / destina</button>
          <button type="button" data-p="transporta" aria-pressed="false">Coleta / transporta</button>
        </div>
      </div>
      <div>
        <div class="flabel">Tipo de resíduo</div>
        <div class="chips" id="chips">{chips}</div>
      </div>
      <div class="checks">
        <label><input type="checkbox" id="fLic"> Só com licença válida</label>
        <label><input type="checkbox" id="fLoc"> Só com sede em {esc(cidade)}</label>
      </div>
    </div>
    <div class="listhead"><span><b id="count">0</b> resultados</span><button type="button" class="limpar" id="limpar">Limpar filtros</button></div>
    <div class="lista-js" id="lista" aria-live="polite"></div>
  </aside>
  <div class="mapa-wrap"><div id="mapa" role="region" aria-label="Mapa"></div>
    <div class="legenda" aria-hidden="true"><span><i style="background:#2A7A2A"></i>Licença válida</span><span><i style="background:#C77700"></i>Vencendo ou vencida</span><span><i style="background:#1A3A8F"></i>Serviço público</span><span><i style="background:#7A7F8C"></i>Licença não localizada</span></div>
  </div>
</section>

{secao_empresas(cid_slug, cidade)}

<section class="outras"><h2>Páginas por tipo de resíduo</h2><ul>{paginas}</ul></section>

<script>
var PONTOS = {dados_js(pts, cid_slug, ctx)};
var CATS = {cats_js};
</script>
<script src="../hub.js" defer></script>"""
