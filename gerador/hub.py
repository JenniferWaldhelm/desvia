"""Página da cidade: mapa com filtros (estilo da ferramenta de Londrina) + obrigações das empresas."""
import json
import re
from sinonimos import SINONIMOS
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
        "licenciador": "Em Londrina o licenciamento é municipalizado: a SEMA licencia as atividades de impacto local e o IAT (Instituto Água e Terra) as demais.",
        "licenca": ("🏛️", "Licença — SEMA ou IAT", "Licença ambiental (SEMA Londrina ou IAT)",
                    "Londrina tem licenciamento ambiental municipalizado. Atividades de impacto local são licenciadas pela SEMA; as de impacto maior, pelo IAT. Gerar, transportar ou tratar resíduos perigosos costuma exigir licença ou autorização antes de operar.",
                    ["Licença Prévia (LP), de Instalação (LI) e de Operação (LO), ou licença simplificada",
                     "Confira na SEMA se a atividade é de impacto local; se não for, o processo é no IAT",
                     "Operar sem licença é crime ambiental (Lei 9.605/1998)"],
                    ("Licenciamento ambiental municipal (SEMA)", "https://portal.londrina.pr.gov.br/licenciamento-ambiental-municipal")),
    },
    "maringa": {
        "licenciador": "Em Maringá o licenciamento é municipalizado: o município licencia as atividades de impacto local e o IAT (Instituto Água e Terra) as demais.",
        "licenca": ("🏛️", "Licença — Município ou IAT", "Licença ambiental (Prefeitura de Maringá ou IAT)",
                    "Maringá tem licenciamento ambiental municipalizado. Atividades de impacto local são licenciadas pela Prefeitura; as de impacto maior, pelo IAT. Gerar, transportar ou tratar resíduos perigosos costuma exigir licença ou autorização antes de operar.",
                    ["Licença Prévia (LP), de Instalação (LI) e de Operação (LO), ou licença simplificada",
                     "Confira na Secretaria Municipal de Meio Ambiente se a atividade é de impacto local; se não for, o processo é no IAT",
                     "Operar sem licença é crime ambiental (Lei 9.605/1998)"],
                    ("Licenciamento ambiental (Prefeitura de Maringá)", "https://www3.maringa.pr.gov.br/meioambiente/?cod=licenciamento")),
        "extra": [
            ("♻️", "Recicláveis", "Ecopontos Ecolix",
             "Os ecopontos Ecolix, espalhados pela cidade, recebem recicláveis separados (papel, plástico, metal e vidro). Leve limpos e secos.",
             [], None),
        ],
    },
    "ibipora": {
        "extra": [
            ("🧱", "Entulho e construção", "Entulho de pequenos geradores",
             "A Central de RCC da Prefeitura (estrada antiga para Jataizinho, lote 66) recebe entulho, volumosos, poda e limpeza de quintal de pequenos geradores, até 3 m³. Acima disso, contrate caçamba ou transportadora licenciada.",
             ["Base legal: Resolução CONAMA 307/2002 e PMGIRS de Ibiporã (2023)"], None),
            ("🫙", "Óleo de cozinha", "Óleo de fritura usado",
             "O SAMAE recebe óleo de cozinha usado na sede (Av. Santos Dumont, 565) e nas escolas municipais. Leve frio, em garrafa PET bem fechada. Nunca despeje na pia ou no esgoto.",
             [], None),
        ],
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
    if loc.get("licenca"):
        itens = [loc["licenca"] if i[2].startswith("Licença ambiental") else i for i in itens]
    licenciador = loc.get("licenciador", "O órgão estadual é o IAT (Instituto Água e Terra).")
    orgao = loc.get("orgao", f"Secretaria de Meio Ambiente de {cidade}")
    cards = "".join(cartao_obrigacao(i) for i in itens)
    return f"""<section class="empresas" id="empresas">
<h2>Sua empresa tem obrigações com os resíduos que gera</h2>
<p class="resposta">A Lei Federal 12.305/2010 (Política Nacional de Resíduos Sólidos) define responsabilidades claras para empresas. Quem descumpre pode receber multa, ter a atividade embargada e responder criminalmente.</p>
<p class="regra">Isto é obrigação legal, não recomendação. Vale para comércios, indústrias, prestadores de serviço e construtoras em {esc(cidade)}. {esc(licenciador)} Dúvidas sobre o que se aplica à sua empresa: {esc(orgao)}.</p>
<div class="obr-grade">{cards}
<article class="obr obr-cta"><span class="obr-tag">💬 Precisa de orientação?</span><h3>Não sabe por onde começar?</h3><p>O Projeto Desvia ajuda a entender o que se aplica ao seu caso. Mande uma mensagem.</p><a href="{WHATSAPP}" target="_blank" rel="noopener">Chamar no WhatsApp →</a></article>
</div>
</section>"""


DESCARTE_SEGURO = {"medicamentos", "pilhas-e-baterias", "lampadas", "eletronicos", "pneus", "entulho", "oleo-de-cozinha",
                   "oleo-lubrificante", "moveis-e-volumosos", "poda-e-galhos", "madeira", "residuos-de-saude",
                   "tintas-e-solventes", "embalagens-de-agrotoxico", "limpa-fossa"}
RECICLA = {"reciclaveis", "sucata-metalica", "organicos", "escovas-e-esponjas"}


def acoes(p, norm):
    """O que a pessoa pode fazer neste ponto: doar, vender, reciclar, descartar ou (empresas) contratar."""
    tp, sv = p["Tipo de ponto"], p["Serviço"]
    txt = norm(" ".join([p["Nome"], p["Resíduos aceitos"]]))
    obs = norm(p.get("Obs", ""))
    cats = set(p.get("_cats", []))
    a = []
    if re.search(r"\bdoac|\bong\b|bazar", txt) or obs.startswith("recebe doac"):
        a.append("doar")
    if re.search(r"brecho|\bcompra|ferro velho|consigna", txt) or sv == "Compra de recicláveis":
        a.append("vender")
    publico = tp in ("PEV público", "PEV privado", "Cooperativa/associação", "Programa logística reversa")
    if (cats & RECICLA or tp == "Cooperativa/associação" or "recicl" in txt) and (publico or sv == "Compra de recicláveis"):
        a.append("reciclar")
    if (publico or sv == "Recebimento") and cats & DESCARTE_SEGURO:
        a.append("descartar")
    if tp in ("Tratamento/destinação final", "Coleta e transporte") and sv != "Compra de recicláveis":
        a.append("empresa")
    if not a:
        a.append("descartar" if publico else "empresa")
    return a


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
            "pp": acoes(p, norm), "cs": sorted(p["_cidades"]),
        })
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def grupos(ctx):
    """Grupos e canais de doação por cidade (dados/grupos.csv), chave = slug da cidade."""
    import csv
    from pathlib import Path
    arq = Path(__file__).resolve().parent.parent / "dados" / "grupos.csv"
    out = {}
    if arq.exists():
        for g in csv.DictReader(open(arq, encoding="utf-8")):
            out.setdefault(ctx["norm"](g["Cidade"]).replace(" ", "-"), []).append({"n": g["Nome"], "l": g["Link"], "t": g["Tipo"]})
    return out


def secao_doar(cid_slug, cidade, ctx):
    gs = grupos(ctx).get(cid_slug, [])
    if not gs:
        return ""
    lis = "".join(f'<li><a href="{esc(g["l"])}" target="_blank" rel="noopener nofollow">{esc(g["n"])} ↗</a></li>' for g in gs)
    return f"""<section class="doar" id="doar">
<h2>Doar ou desapegar em {esc(cidade)}</h2>
<p class="resposta">Móveis, roupas, eletrônicos que funcionam e utensílios em bom estado costumam ir mais rápido por doação direta, em grupos da cidade, do que para um ponto de coleta. Anuncie com foto, bairro e se precisa retirar.</p>
<ul class="doar-links">{lis}</ul>
<p class="sub">Conhece um grupo ou instituição que recebe doações em {esc(cidade)}? <a href="{WHATSAPP}" target="_blank" rel="noopener">Indique para o Desvia</a>.</p>
</section>"""


def corpo_hub(cid_slug, cidade, pts, cats_ordem, nomes, por_cat, ctx):
    chips = "".join(
        f'<button type="button" class="chip" data-cat="{s}" aria-pressed="false">{esc(nomes[s][1])} <span class="n">{len(por_cat[s])}</span></button>'
        for s in cats_ordem)
    paginas = "".join(f'<li><a href="{s}/">Onde descartar {esc(nomes[s][0])}</a></li>' for s in cats_ordem)
    cats_js = json.dumps({s: nomes[s][1] for s in cats_ordem}, ensure_ascii=False)
    return f"""<nav class="trilha" aria-label="Você está em"><a href="../">Cidades</a> › {esc(cidade)}</nav>
<h1>Onde doar, reciclar e descartar em {esc(cidade)}</h1>
<p class="resposta">Antes de jogar fora, veja se dá para doar, vender ou reciclar. Aqui estão os pontos de entrega, brechós, cooperativas e empresas de coleta e destinação de {esc(cidade)} e região, com a situação da licença ambiental de cada uma.</p>
<button type="button" class="btn-ajuda" data-ajuda>🧭 Não sabe o que fazer? Me ajude a decidir</button>

<section class="ferramenta" aria-label="Mapa e lista com filtros">
  <aside class="painel">
    <div class="filtros">
      <input id="q" type="search" placeholder="O que você tem? sofá, roupa, pilha, remédio, nome da empresa…" autocomplete="off" aria-label="Buscar">
      <div>
        <div class="flabel">O que você quer fazer</div>
        <div class="seg" role="group" aria-label="Tipo de atendimento" id="seg">
          <button type="button" data-p="todos" aria-pressed="true">Todos</button>
          <button type="button" data-p="doar" aria-pressed="false">Doar</button>
          <button type="button" data-p="vender" aria-pressed="false">Vender ou trocar</button>
          <button type="button" data-p="reciclar" aria-pressed="false">Reciclar</button>
          <button type="button" data-p="descartar" aria-pressed="false">Descartar com segurança</button>
          <button type="button" data-p="empresa" aria-pressed="false">Empresas: coleta e destinação</button>
        </div>
      </div>
      <div>
        <div class="flabel">Tipo de resíduo</div>
        <div class="chips" id="chips">{chips}</div>
      </div>
      <div class="checks">
        <label><input type="checkbox" id="fLic"> Só com licença válida ou serviço público</label>
        <label><input type="checkbox" id="fLoc"> Só com sede em {esc(cidade)}</label>
      </div>
    </div>
    <div class="listhead"><span><b id="count">0</b> resultados</span><button type="button" class="limpar" id="limpar">Limpar filtros</button></div>
    <div class="lista-js" id="lista" aria-live="polite"></div>
  </aside>
  <div class="mapa-wrap"><div id="mapa" role="region" aria-label="Mapa"></div>
    <div class="legenda" role="group" aria-label="Filtrar pela situação da licença"><b>Licença</b><button type="button" data-st="valida" aria-pressed="true"><i style="background:#2A7A2A"></i>Válida</button><button type="button" data-st="vencida" aria-pressed="true"><i style="background:#C77700"></i>Vencendo ou vencida</button><button type="button" data-st="publico" aria-pressed="true"><i style="background:#1A3A8F"></i>Serviço público</button><button type="button" data-st="nao_localizada" aria-pressed="true"><i style="background:#7A7F8C"></i>Não localizada</button></div>
  </div>
</section>

{secao_doar(cid_slug, cidade, ctx)}

{secao_empresas(cid_slug, cidade)}

<section class="outras"><h2>Páginas por tipo de resíduo</h2><ul>{paginas}</ul></section>

<script>
var PONTOS = {dados_js(pts, cid_slug, ctx)};
var CATS = {cats_js};
var SINONIMOS = {json.dumps(SINONIMOS, ensure_ascii=False)};
var GRUPOS = {json.dumps(grupos(ctx), ensure_ascii=False)};
var DESVIA_CIDADES = {json.dumps({cid_slug: cidade}, ensure_ascii=False)};
</script>
<script src="../hub.js" defer></script>
<script src="../webmcp.js" defer></script>"""
