#!/usr/bin/env python3
"""Gera as páginas "Onde descartar <resíduo> em <cidade>" do Desvia.

Lê dados/pontos.csv (exportado da aba Pontos da planilha Desvia - Base Mestra)
e escreve em residuos/:
  residuos/index.html                          lista de cidades
  residuos/<cidade>/index.html                 resíduos da cidade
  residuos/<cidade>/<residuo>/index.html       uma página por combinação
Também reescreve sitemap.xml mantendo as páginas fixas do site.

Uso: python3 gerador/gerar.py
"""
import csv
import html
import json
import re
import shutil
import unicodedata
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "dados" / "pontos.csv"
SAIDA = RAIZ / "residuos"
BASE_URL = "https://jenniferwaldhelm.github.io/desvia"
HOJE = date.today()

# Cidades publicadas (status "Verificado" ou "Publicado" na Fila de cidades).
# Uma cidade só entra aqui quando a Jen aprova a lista dela.
CIDADES = {
    "londrina": "Londrina",
    "mandaguari": "Mandaguari",
}
UF = "PR"

# Páginas fixas do site que continuam no sitemap.
PAGINAS_FIXAS = [("", "1.0"), ("mapa-pev.html", "0.8")]

# slug, nome na frase ("Onde descartar ..."), nome curto, palavras-chave
CATEGORIAS = [
    ("pneus", "pneus", "Pneus", ["pneu"]),
    ("eletronicos", "eletrônicos", "Eletrônicos", ["eletro", "eletronic", "lixo tecnologic"]),
    ("lampadas", "lâmpadas", "Lâmpadas", ["lampad"]),
    ("pilhas-e-baterias", "pilhas e baterias", "Pilhas e baterias", ["pilha", "bateria", "acumulador"]),
    ("oleo-de-cozinha", "óleo de cozinha", "Óleo de cozinha", ["oleo vegetal", "oleo de cozinha", "oleo de fritura"]),
    ("oleo-lubrificante", "óleo lubrificante", "Óleo lubrificante", ["oleo lubrificante"]),
    ("entulho", "entulho e resíduos de construção", "Entulho (RCC)", ["entulho", "rcc", "construcao civil", "cacamba", "construtora"]),
    ("moveis-e-volumosos", "móveis, colchões e volumosos", "Móveis e volumosos", ["movei", "volumoso", "colch", "sofa"]),
    ("poda-e-galhos", "poda e galhos", "Poda e galhos", ["poda", "galho"]),
    ("madeira", "madeira", "Madeira", ["madeira"]),
    ("medicamentos", "medicamentos vencidos", "Medicamentos", ["medicament"]),
    ("residuos-de-saude", "resíduos de serviços de saúde", "Resíduos de saúde", ["saude", "hospitalar", "raio-x"]),
    ("reciclaveis", "recicláveis (papel, plástico, metal e vidro)", "Recicláveis", ["reciclav", "papel", "plastic", "vidro", "isopor"]),
    ("sucata-metalica", "sucata metálica", "Sucata metálica", ["sucata", "metai", "metal", "ferro", "alumin"]),
    ("organicos", "resíduos orgânicos", "Orgânicos", ["organic", "compostag", "alimento", "sebo"]),
    ("texteis", "resíduos têxteis", "Têxteis", ["textil", "texteis", "estopa"]),
    ("tintas-e-solventes", "tintas e solventes", "Tintas e solventes", ["tinta", "solvente", "thinner"]),
    ("limpa-fossa", "esgoto de fossa e efluentes", "Fossa e efluentes", ["fossa", "esgoto", "efluente", "despejo", "banheiros quimicos"]),
    ("embalagens-de-agrotoxico", "embalagens de agrotóxico", "Embalagens de agrotóxico", ["defensivo", "agrotox"]),
    ("residuos-perigosos", "resíduos perigosos (Classe I)", "Perigosos (Classe I)", ["perigos", "tanques", "oleos/solventes", "coprocess"]),
    ("residuos-classe-ii", "resíduos industriais não perigosos (Classe II)", "Industriais (Classe II)", ["nao perigos", "embalagens industriais", "transbordo"]),
]

# Orientação curta por categoria (aparece no topo e no FAQ).
DICAS = {
    "pneus": "Pneus inservíveis têm logística reversa obrigatória: fabricantes e importadores precisam recolher. Não descarte em terreno baldio nem na coleta comum, porque acumulam água e viram criadouro do Aedes aegypti.",
    "eletronicos": "Eletrônicos e eletrodomésticos têm logística reversa obrigatória. Leve inteiros, sem desmontar, porque placas e baterias internas contêm metais pesados.",
    "lampadas": "Lâmpadas fluorescentes contêm mercúrio. Entregue inteiras, embaladas na caixa original ou em jornal, para não quebrar no transporte.",
    "pilhas-e-baterias": "Pilhas e baterias têm logística reversa obrigatória e não podem ir para o lixo comum. Baterias de carro e moto voltam para a loja que vende a nova.",
    "oleo-de-cozinha": "Espere o óleo esfriar, coe e guarde em garrafa PET bem fechada. Nunca jogue na pia: um litro de óleo contamina milhares de litros de água.",
    "oleo-lubrificante": "Óleo lubrificante usado é resíduo perigoso e deve ir para rerrefino. A troca de óleo em oficina já inclui a destinação; peça o comprovante.",
    "entulho": "Pequenas reformas podem usar os PEVs públicos dentro do limite da prefeitura. Obras maiores precisam contratar caçamba ou transportadora licenciada.",
    "moveis-e-volumosos": "Móveis, colchões e sofás não vão na coleta comum. Use o serviço da prefeitura ou o PEV dentro do limite permitido.",
    "poda-e-galhos": "Galhos e poda podem ir para os PEVs públicos ou coleta específica da prefeitura. Corte em pedaços menores para facilitar o transporte.",
    "madeira": "Madeira limpa (paletes, sobras) pode ser reaproveitada. Madeira tratada ou pintada exige destinação específica.",
    "medicamentos": "Medicamentos vencidos ou sem uso devem voltar para farmácias com ponto de coleta. Não jogue no lixo comum nem no vaso sanitário.",
    "residuos-de-saude": "Resíduos de serviços de saúde (clínicas, consultórios, farmácias) exigem empresa licenciada para coleta e tratamento e plano de gerenciamento (PGRSS).",
    "reciclaveis": "Separe recicláveis limpos e secos. Cooperativas e associações de catadores dão destino aos materiais e geram renda local.",
    "sucata-metalica": "Sucata metálica tem valor de mercado. Para empresas, exija nota e comprovante de destinação do comprador.",
    "organicos": "Restos de alimentos e poda podem virar adubo por compostagem. Empresas geradoras de grande volume precisam de destinação licenciada.",
    "texteis": "Roupas em bom estado podem ser doadas. Retalhos e estopas industriais vão para empresas de reaproveitamento.",
    "tintas-e-solventes": "Tintas, thinner e solventes são resíduos perigosos. Guarde na embalagem original fechada e destine com empresa licenciada.",
    "limpa-fossa": "Fossas e caixas de gordura devem ser esvaziadas por empresa licenciada, que leva o efluente para tratamento.",
    "embalagens-de-agrotoxico": "Embalagens vazias de agrotóxico devem passar pela tríplice lavagem e voltar para a central indicada na nota fiscal de compra.",
    "residuos-perigosos": "Resíduos Classe I (perigosos) exigem transportador e destinador licenciados, Manifesto de Transporte de Resíduos (MTR) e Certificado de Destinação Final (CDF).",
    "residuos-classe-ii": "Resíduos industriais não perigosos (Classe II) também exigem transportador e destinador licenciados, MTR e CDF.",
}

# Regras locais por cidade e categoria.
REGRAS_LOCAIS = {
    ("mandaguari", "entulho"): "Em Mandaguari, caçambas podem ficar no máximo 72 horas na via pública (Lei Municipal nº 450/1999). Grandes geradores de RCC precisam de PGRCC.",
    ("mandaguari", "*"): "Em Mandaguari, empresas obrigadas a ter PGRS precisam apresentá-lo para obter alvará e certidões municipais (Lei Municipal nº 4.419/2025, art. 17 e 18).",
    ("londrina", "entulho"): "Em Londrina, os PEVs públicos recebem até 1 m³ por pessoa por mês de entulho, poda e madeira.",
    ("londrina", "poda-e-galhos"): "Em Londrina, os PEVs públicos recebem até 1 m³ por pessoa por mês de poda, madeira e entulho.",
}

ORDEM_STATUS = {"valida": 0, "vencendo": 1, "publico": 2, "vencida": 3, "nao_localizada": 4}
EMPRESA_TOKENS = ["ltda", " me", "eireli", "s/a", " sa", "epp", "coop", "associa", "ong ", "programa", "pev ",
                  "cmtu", "prefeitura", "projeto", "central", "ambiental", "comerc", "industr", "recicla",
                  "estopa", "catador", "supermercado", "farmacia", "magazine", "eletro", "vigilancia", "almoxarifado"]


def norm(txt):
    txt = unicodedata.normalize("NFD", txt or "")
    return "".join(c for c in txt if unicodedata.category(c) != "Mn").lower()


def esc(txt):
    return html.escape(txt or "", quote=True)


def data_br(txt):
    try:
        return datetime.strptime(txt.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


def categorias_do_ponto(p):
    texto = norm(p["Resíduos aceitos"])
    achadas = []
    for slug, _, _, chaves in CATEGORIAS:
        if any(c in texto for c in chaves):
            achadas.append(slug)
    # Classe I (sem confundir com Classe II)
    classe = norm(p["Classe NBR 10004"] + " " + p["Resíduos aceitos"])
    if p["Tipo de ponto"] not in ("Coleta e transporte", "Tratamento/destinação final"):
        return achadas
    if re.search(r"classes? i\b(?! ?i)|classe i a|classes i e|hospitalar", classe) and "residuos-perigosos" not in achadas:
        achadas.append("residuos-perigosos")
    if re.search(r"classes? ii|classe ii", classe) and "residuos-classe-ii" not in achadas:
        achadas.append("residuos-classe-ii")
    return achadas


def status_licenca(p):
    tipo_ponto = p["Tipo de ponto"]
    validade = data_br(p["Validade licença"])
    if validade:
        if validade < HOJE:
            return "vencida", validade
        if (validade - HOJE).days < 60:
            return "vencendo", validade
        return "valida", validade
    if tipo_ponto in ("PEV público", "Programa logística reversa"):
        return "publico", None
    return "nao_localizada", None


def pessoa_fisica(p):
    if p["CNPJ"].strip():
        return False
    nome = " " + norm(p["Nome"]) + " "
    return not any(t in nome for t in EMPRESA_TOKENS)


def selo_licenca(p):
    st, validade = status_licenca(p)
    verif = p["Data verificação"].strip() or "data não registrada"
    tipo = p["Tipo licença"].strip()
    num = p["Nº licença"].strip()
    orgao = p["Órgão licença"].strip().replace("SEMA- Londrina", "SEMA Londrina")
    ident = " ".join(x for x in [tipo, num] if x)
    if orgao:
        ident = f"{ident} ({orgao})" if ident else orgao
    aviso_lp = " Licença prévia ou de instalação: não autoriza a operação." if tipo.upper() in ("LP", "LI", "LI-A") else ""
    if st == "valida":
        return "ok", f"Licença {ident} válida até {validade:%d/%m/%Y}.{aviso_lp}"
    if st == "vencendo":
        return "alerta", f"Licença {ident} vence em {validade:%d/%m/%Y}.{aviso_lp}"
    if st == "vencida":
        return "alerta", f"Licença {ident} com validade até {validade:%d/%m/%Y}. Renovação não localizada nas bases consultadas em {verif}."
    if st == "publico":
        if p["Tipo de ponto"] == "Programa logística reversa":
            return "neutro", "Programa de logística reversa."
        return "neutro", "Serviço público municipal."
    return "aviso", f"Licença não localizada nas bases consultadas em {verif}."


def aviso_cnpj(p):
    obs = norm(p["Obs"])
    m = re.search(r"cnpj (inapto|baixado) na receita(?: federal)? desde (\d{2}/\d{2}/\d{4})", obs)
    if m:
        return f"CNPJ {m.group(1)} na Receita Federal desde {m.group(2)}."
    return ""


def obs_publica(p):
    if p["Tipo de ponto"] in ("PEV público", "PEV privado", "Cooperativa/associação", "Programa logística reversa"):
        o = p["Obs"].strip()
        bloqueios = ["só no ctf", "pedir licença", "sem licença", "cnpj", "divergente", "confirm"]
        if o and not any(b in norm(o) for b in bloqueios):
            return o
    return ""


def carregar():
    with open(CSV, newline="", encoding="utf-8") as f:
        pontos = list(csv.DictReader(f))
    for p in pontos:
        for k in p:
            p[k] = (p[k] or "").strip()
        p["_cats"] = categorias_do_ponto(p)
        p["_cidades"] = {norm(c).strip().replace(" ", "-") for c in p["Municípios atendidos"].split(";") if c.strip()}
        p["_status"] = status_licenca(p)[0]
        try:
            p["_lat"], p["_lng"] = float(p["Lat"].replace(",", ".")), float(p["Lng"].replace(",", "."))
        except ValueError:
            p["_lat"] = p["_lng"] = None
    return pontos


CSS_LINK = '<link rel="stylesheet" href="{raiz}residuos/estilo.css">'
FONTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
          '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">')


def pagina(titulo, descricao, url, raiz, corpo, jsonld, mapa=False):
    leaflet = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'
               '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" defer></script>') if mapa else ""
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in jsonld)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descricao)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descricao)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="pt_BR">
{FONTES}
{CSS_LINK.format(raiz=raiz)}
{leaflet}
{ld}
</head>
<body>
<header><nav><a class="logo" href="{raiz}">Des<span>via</span></a><a class="nav-link" href="{raiz}residuos/">Onde descartar</a></nav></header>
<main>
{corpo}
</main>
<footer><p>Desvia reúne, em uma só busca, dados de licenças do IAT, cadastros do IBAMA, listas das prefeituras e da Receita Federal. As informações de licença refletem as bases públicas na data indicada e não substituem a consulta ao órgão ambiental.</p>
<p><a href="{raiz}">Desvia</a> · <a href="{raiz}residuos/">Todas as cidades</a></p></footer>
</body>
</html>
"""


def cartao(p, cidade_slug):
    cls, texto_lic = selo_licenca(p)
    partes = [f'<article class="ponto" id="{esc(p["ID"].lower())}">',
              f'<h3>{esc(p["Nome"])}</h3>',
              f'<p class="tipo">{esc(p["Tipo de ponto"])} · {esc(p["Serviço"])}</p>',
              f'<p class="residuos">{esc(p["Resíduos aceitos"])}</p>']
    local = p["Município sede"]
    if p["Endereço"] and not pessoa_fisica(p) and not p["Endereço"].startswith("www."):
        local = f'{p["Endereço"]}, {local}' if local else p["Endereço"]
    if local:
        fora = "" if norm(p["Município sede"]).replace(" ", "-") == cidade_slug or not p["Município sede"] else " (atende a cidade)"
        partes.append(f'<p class="local">{esc(local)}{fora}</p>')
    contatos = []
    if p["Telefone"]:
        tel1 = p["Telefone"].split("/")[0].strip()
        digitos = re.sub(r"\D", "", tel1)
        contatos.append(f'<a href="tel:+55{digitos}">{esc(p["Telefone"])}</a>' if len(digitos) >= 10 else esc(p["Telefone"]))
    site = p["Site/rede"] or (p["Endereço"] if p["Endereço"].startswith("www.") else "")
    if site:
        href = site if site.startswith("http") else ("mailto:" + site if "@" in site else "https://" + site)
        contatos.append(f'<a href="{esc(href)}" rel="nofollow noopener" target="_blank">{esc(site)}</a>')
    if contatos:
        partes.append(f'<p class="contato">{" · ".join(contatos)}</p>')
    partes.append(f'<p class="licenca {cls}">{esc(texto_lic)}</p>')
    cnpj = aviso_cnpj(p)
    if cnpj:
        partes.append(f'<p class="licenca aviso">{esc(cnpj)}</p>')
    o = obs_publica(p)
    if o:
        partes.append(f'<p class="obs">{esc(o)}</p>')
    partes.append("</article>")
    return "\n".join(partes)


def jsonld_negocio(p):
    item = {"@type": "LocalBusiness", "name": p["Nome"]}
    if p["Telefone"]:
        item["telephone"] = p["Telefone"].split("/")[0].strip()
    if not pessoa_fisica(p) and p["Endereço"] and not p["Endereço"].startswith("www."):
        item["address"] = {"@type": "PostalAddress", "streetAddress": p["Endereço"],
                           "addressLocality": p["Município sede"], "addressCountry": "BR"}
    if p["_lat"] is not None:
        item["geo"] = {"@type": "GeoCoordinates", "latitude": p["_lat"], "longitude": p["_lng"]}
    return item


def faq_categoria(cat_slug, frase, cidade, pts):
    validos = sum(1 for p in pts if p["_status"] in ("valida", "vencendo"))
    publicos = sum(1 for p in pts if p["Tipo de ponto"] in ("PEV público", "PEV privado", "Cooperativa/associação"))
    perguntas = [
        (f"Onde descartar {frase} em {cidade}?",
         f"O Desvia encontrou {len(pts)} {'opção' if len(pts) == 1 else 'opções'} para {frase} em {cidade}, "
         f"sendo {publicos} {'ponto de entrega' if publicos == 1 else 'pontos de entrega'} para a população e "
         f"{validos} com licença ambiental válida localizada. {DICAS.get(cat_slug, '')}"),
        ("Como saber se a empresa tem licença ambiental?",
         "Cada empresa mostra o tipo, o número e a validade da licença localizada nas bases do IAT, da prefeitura ou do IBAMA. "
         "Quando nada foi encontrado, o Desvia indica que a licença não foi localizada nas bases consultadas e a data da consulta. "
         "Antes de contratar, peça a licença atual à empresa."),
        ("Sou empresa. O que preciso exigir de quem leva meu resíduo?",
         "Transportador e destinador precisam de licença ambiental válida para o tipo de resíduo. Cada envio exige o Manifesto de "
         "Transporte de Resíduos (MTR, no sistema do SINIR) e, depois, o Certificado de Destinação Final (CDF). Guarde os dois."),
    ]
    return perguntas


def mapa_js(pts):
    dados = [{"n": p["Nome"], "a": p["_lat"], "o": p["_lng"], "id": p["ID"].lower(), "s": p["_status"]}
             for p in pts if p["_lat"] is not None]
    if not dados:
        return ""
    return f"""<div id="mapa" role="region" aria-label="Mapa dos pontos"></div>
<script>
window.addEventListener('load', function () {{
  var pts = {json.dumps(dados, ensure_ascii=False)};
  var cores = {{valida: '#2A7A2A', vencendo: '#C77700', publico: '#1A3A8F', vencida: '#C77700', nao_localizada: '#7A7F8C'}};
  var mapa = L.map('mapa', {{scrollWheelZoom: false}});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 18, attribution: '&copy; OpenStreetMap'}}).addTo(mapa);
  var grupo = L.featureGroup();
  pts.forEach(function (p) {{
    L.circleMarker([p.a, p.o], {{radius: 8, color: '#fff', weight: 2, fillColor: cores[p.s] || '#7A7F8C', fillOpacity: 0.95}})
      .bindPopup('<a href="#' + p.id + '">' + p.n.replace(/</g, '&lt;') + '</a>').addTo(grupo);
  }});
  grupo.addTo(mapa);
  mapa.fitBounds(grupo.getBounds().pad(0.15), {{maxZoom: 15}});
}});
</script>"""


def gerar():
    pontos = carregar()
    if SAIDA.exists():
        for item in SAIDA.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
    SAIDA.mkdir(exist_ok=True)
    shutil.copy(Path(__file__).with_name("estilo.css"), SAIDA / "estilo.css")
    urls = [(f"{BASE_URL}/{u}", pr) for u, pr in PAGINAS_FIXAS]
    nomes = {s: (f, c) for s, f, c, _ in CATEGORIAS}
    resumo_cidades = []

    for cid_slug, cidade in CIDADES.items():
        do_lugar = [p for p in pontos if cid_slug in p["_cidades"]]
        por_cat = {}
        for p in do_lugar:
            for c in p["_cats"]:
                por_cat.setdefault(c, []).append(p)
        cats_ordem = [s for s, _, _, _ in CATEGORIAS if s in por_cat]
        resumo_cidades.append((cid_slug, cidade, len(do_lugar), len(cats_ordem)))

        for cat in cats_ordem:
            frase, curto = nomes[cat]
            pts = sorted(por_cat[cat], key=lambda p: (ORDEM_STATUS[p["_status"]],
                                                     norm(p["Município sede"]).replace(" ", "-") != cid_slug,
                                                     norm(p["Nome"])))
            url = f"{BASE_URL}/residuos/{cid_slug}/{cat}/"
            titulo = f"Onde descartar {frase} em {cidade}-{UF} | Desvia"
            n_val = sum(1 for p in pts if p["_status"] in ("valida", "vencendo"))
            descricao = (f"{len(pts)} {'opção' if len(pts) == 1 else 'opções'} para descartar {frase} em {cidade}: "
                         f"pontos de entrega e empresas, com a situação da licença ambiental de cada uma.")
            regra = REGRAS_LOCAIS.get((cid_slug, cat)) or REGRAS_LOCAIS.get((cid_slug, "*"), "")
            faq = faq_categoria(cat, frase, cidade, pts)
            outras = "".join(f'<li><a href="../{s}/">{esc(nomes[s][1])}</a></li>' for s in cats_ordem if s != cat)
            corpo = f"""<nav class="trilha" aria-label="Você está em"><a href="../../">Cidades</a> › <a href="../">{esc(cidade)}</a> › {esc(curto)}</nav>
<h1>Onde descartar {esc(frase)} em {esc(cidade)}</h1>
<p class="resposta"><strong>{len(pts)} {'opção' if len(pts) == 1 else 'opções'}</strong> em {esc(cidade)} e região, {n_val} com licença ambiental válida localizada. {esc(DICAS.get(cat, ''))}</p>
{f'<p class="regra">{esc(regra)}</p>' if regra else ''}
<p class="atualizado">Dados atualizados em {HOJE:%d/%m/%Y}. Licença válida aparece primeiro.</p>
{mapa_js(pts)}
<section class="lista">
{''.join(cartao(p, cid_slug) for p in pts)}
</section>
<section class="faq"><h2>Perguntas frequentes</h2>
{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(r)}</p></details>' for q, r in faq)}
</section>
<section class="outras"><h2>Outros resíduos em {esc(cidade)}</h2><ul>{outras}</ul></section>"""
            jsonld = [
                {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Cidades", "item": f"{BASE_URL}/residuos/"},
                    {"@type": "ListItem", "position": 2, "name": cidade, "item": f"{BASE_URL}/residuos/{cid_slug}/"},
                    {"@type": "ListItem", "position": 3, "name": curto, "item": url}]},
                {"@context": "https://schema.org", "@type": "ItemList", "name": f"Onde descartar {frase} em {cidade}",
                 "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": jsonld_negocio(p)} for i, p in enumerate(pts)]},
                {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in faq]},
            ]
            destino = SAIDA / cid_slug / cat / "index.html"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(pagina(titulo, descricao, url, "../../../", corpo, jsonld, mapa=True), encoding="utf-8")
            urls.append((url, "0.7"))

        # página da cidade
        url = f"{BASE_URL}/residuos/{cid_slug}/"
        itens = "".join(f'<li><a href="{s}/"><span>{esc(nomes[s][1])}</span><small>{len(por_cat[s])} {"opção" if len(por_cat[s]) == 1 else "opções"}</small></a></li>'
                        for s in cats_ordem)
        corpo = f"""<nav class="trilha" aria-label="Você está em"><a href="../">Cidades</a> › {esc(cidade)}</nav>
<h1>Onde descartar resíduos em {esc(cidade)}</h1>
<p class="resposta">Escolha o tipo de resíduo para ver pontos de entrega, cooperativas e empresas que atendem {esc(cidade)}, com a situação da licença ambiental de cada uma.</p>
<ul class="grade">{itens}</ul>"""
        jsonld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Cidades", "item": f"{BASE_URL}/residuos/"},
            {"@type": "ListItem", "position": 2, "name": cidade, "item": url}]}]
        (SAIDA / cid_slug / "index.html").write_text(
            pagina(f"Onde descartar resíduos em {cidade}-{UF} | Desvia",
                   f"Pontos de entrega e empresas de coleta e destinação de resíduos em {cidade}, por tipo de resíduo, com a situação da licença ambiental.",
                   url, "../../", corpo, jsonld), encoding="utf-8")
        urls.append((url, "0.8"))

    # índice de cidades
    itens = "".join(f'<li><a href="{s}/"><span>{esc(c)}</span><small>{n} pontos · {k} tipos de resíduo</small></a></li>'
                    for s, c, n, k in resumo_cidades)
    corpo = f"""<h1>Onde descartar resíduos</h1>
<p class="resposta">Pontos de entrega, cooperativas e empresas de coleta e destinação de resíduos, com a situação da licença ambiental, reunidos de várias fontes em uma só busca.</p>
<ul class="grade">{itens}</ul>"""
    (SAIDA / "index.html").write_text(
        pagina("Onde descartar resíduos: cidades | Desvia",
               "Encontre onde descartar cada tipo de resíduo na sua cidade, com a situação da licença ambiental de quem recebe.",
               f"{BASE_URL}/residuos/", "../", corpo, []), encoding="utf-8")
    urls.insert(len(PAGINAS_FIXAS), (f"{BASE_URL}/residuos/", "0.9"))

    linhas = "\n".join(f"  <url><loc>{u}</loc><lastmod>{HOJE.isoformat()}</lastmod><priority>{pr}</priority></url>" for u, pr in urls)
    (RAIZ / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{linhas}\n</urlset>\n',
        encoding="utf-8")
    total = sum(1 for _ in SAIDA.rglob("index.html"))
    print(f"{total} páginas geradas; {len(urls)} URLs no sitemap")
    for s, c, n, k in resumo_cidades:
        print(f"  {c}: {n} pontos, {k} tipos de resíduo")


if __name__ == "__main__":
    gerar()
