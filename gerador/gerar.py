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

import hub
import paginas as site_desvia

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "dados" / "pontos.csv"
SAIDA = RAIZ / "residuos"
BASE_URL = "https://desvia.eco.br"
HOJE = date.today()

# Cidades publicadas (status "Verificado" ou "Publicado" na Fila de cidades).
# Uma cidade só entra aqui quando a Jen aprova a lista dela.
def _cidades():
    """Cidades publicadas: aba "Fila de cidades" da planilha (dados/cidades.csv), coluna Publicar = Sim."""
    import csv as _csv
    import unicodedata as _ud
    arq = Path(__file__).resolve().parent.parent / "dados" / "cidades.csv"
    out = {}
    for c in _csv.DictReader(open(arq, encoding="utf-8")):
        nome = (c.get("Município") or "").strip()
        if nome and (c.get("Publicar") or "").strip().lower() in ("sim", "s", "x", "true"):
            slug = _ud.normalize("NFD", nome).encode("ascii", "ignore").decode().lower().replace(" ", "-")
            out[slug] = nome
    return out


CIDADES = _cidades()
UF = "PR"

# Token do teste de origem do WebMCP no Chrome (deixe vazio até cadastrar o site).
ORIGIN_TRIAL = ""
# Contador de visitas GoatCounter (gratuito, sem cookies). Ex.: "desvia" para desvia.goatcounter.com
GOATCOUNTER = "projetodesvia"
# Google Analytics 4 (ID de medição). Vazio desliga.
GA4 = "G-2SCQNPX98Z"

# Páginas fixas do site que continuam no sitemap.
PAGINAS_FIXAS = [("", "1.0"), ("mandaguari.html", "0.8"), ("mapa-pev.html", "0.6")]

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
    ("texteis", "roupas e resíduos têxteis", "Roupas e têxteis", ["textil", "texteis", "estopa", "roupa", "brecho"]),
    ("tintas-e-solventes", "tintas e solventes", "Tintas e solventes", ["tinta", "solvente", "thinner"]),
    ("limpa-fossa", "esgoto de fossa e efluentes", "Fossa e efluentes", ["fossa", "esgoto", "efluente", "despejo", "banheiros quimicos"]),
    ("embalagens-de-agrotoxico", "embalagens de agrotóxico", "Embalagens de agrotóxico", ["defensivo", "agrotox"]),
    ("escovas-e-esponjas", "escovas de dente e esponjas", "Escovas e esponjas", ["escova", "esponja"]),
    ("residuos-perigosos", "resíduos perigosos (Classe I)", "Perigosos (Classe I)", ["perigos", "tanques", "oleos/solventes", "coprocess"]),
    ("residuos-classe-ii", "resíduos industriais não perigosos (Classe II)", "Industriais (Classe II)", ["nao perigos", "embalagens industriais", "transbordo"]),
]

# Serviços (quem vem buscar ou compra): slug, nome, aviso no topo, regra sobre o ponto
def _txt(p):
    return norm(" ".join(p.get(k, "") for k in ("Nome", "Resíduos aceitos", "Obs", "Serviço", "Tipo de ponto")))
EMPRESA = ("Coleta e transporte", "Tratamento/destinação final")
SERVICOS = [
    ("cacamba-de-entulho", "Caçamba de entulho",
     "Quem gera o entulho responde pelo destino dele. Prefira empresa com licença válida e peça o comprovante de onde a caçamba foi descarregada.",
     lambda p: (p["Tipo de ponto"] == "Coleta e transporte" and "entulho" in p["_cats"]) or any(k in norm(p["Nome"]) for k in ("cacamba", "disk entulho"))),
    ("limpa-fossa-e-desentupidora", "Limpa-fossa e desentupidora",
     "O caminhão precisa levar o esgoto para uma estação de tratamento licenciada. Peça o comprovante de descarte.",
     lambda p: p["Tipo de ponto"] in EMPRESA and ("limpa-fossa" in p["_cats"] or "desentup" in _txt(p))),
    ("coleta-de-residuos-para-empresas", "Coleta de resíduos para empresas",
     "Empresa que contrata coleta continua responsável pelo resíduo até a destinação final. Confira a licença, emita o MTR e guarde o CDF.",
     lambda p: p["Tipo de ponto"] == "Coleta e transporte" or (p["Tipo de ponto"] in EMPRESA and p["Serviço"] in ("Coleta", "Transporte", "Coleta + destinação"))),
    ("brecho-e-consignacao", "Brechós e consignação",
     "Roupas, calçados e acessórios em bom estado podem ser vendidos, trocados ou deixados em consignação antes de virar resíduo.",
     lambda p: any(k in _txt(p) for k in ("brecho", "consign"))),
    ("compra-de-sucata-e-reciclaveis", "Compra de sucata e recicláveis",
     "Sucata e recicláveis têm valor. Para empresas, exija nota e comprovante de destinação de quem compra.",
     lambda p: p["Serviço"] == "Compra de recicláveis" or p["Tipo de ponto"] == "Comprador informal" or any(k in norm(p["Nome"]) for k in ("sucata", "ferro velho", "ferro-velho", "aparas"))),
]

# Termo mais buscado por tipo de resíduo (Google Keyword Planner, Londrina, out/2025 a set/2026): vai no <title>
TERMO_BUSCA = {
    "eletronicos": "Lixo eletrônico", "entulho": "Descarte de entulho e caçamba", "pilhas-e-baterias": "Descarte de pilhas e baterias",
    "oleo-de-cozinha": "Descarte de óleo de cozinha", "medicamentos": "Descarte de remédios vencidos",
    "moveis-e-volumosos": "Descarte de móveis, sofá e colchão", "lampadas": "Descarte de lâmpadas", "pneus": "Descarte de pneus",
    "reciclaveis": "Coleta seletiva e recicláveis", "texteis": "Doação e descarte de roupas", "poda-e-galhos": "Descarte de galhos e poda",
    "sucata-metalica": "Venda e descarte de sucata", "oleo-lubrificante": "Descarte de óleo lubrificante", "limpa-fossa": "Limpa-fossa e desentupidora",
}

# Localizadores oficiais dos programas nacionais de logística reversa (link, sem copiar os pontos).
LOCALIZADOR = {
    "pneus": ("Ver todos os pontos de coleta da Reciclanip", "https://www.reciclanip.org.br/pontos-de-coleta/coleta-no-brasil/"),
}

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
        t = txt.strip()
        return datetime.strptime(t, "%Y/%m/%d" if re.match(r"^\d{4}/", t) else "%d/%m/%Y").date()
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
    m = re.search(r"cnpj (inapto|inapta|baixado|baixada|suspenso|suspensa) na receita(?: federal)? (desde|em) (\d{2}/\d{2}/\d{4})", obs)
    if m:
        sit = {"inapta": "inapto", "baixada": "baixado", "suspensa": "suspenso"}.get(m.group(1), m.group(1))
        return f"CNPJ {sit} na Receita Federal " + (f"desde {m.group(3)}." if m.group(2) == "desde" else f"(consulta em {m.group(3)}).")
    return ""


def obs_publica(p):
    if p["Tipo de ponto"] in ("PEV público", "PEV privado", "Cooperativa/associação", "Programa logística reversa"):
        o = p["Obs"].strip()
        bloqueios = ["so no ctf", "pedir licenca", "sem licenca", "cnpj", "divergente", "confirm", "conferir", "coordenada"]
        if o and not any(b in norm(o) for b in bloqueios):
            return o
    return ""


def _ajustes():
    """Ajustes automáticos da revisão mensal (dados/ajustes.csv): ocultar, aviso de CNPJ e licença renovada."""
    arq = Path(__file__).resolve().parent.parent / "dados" / "ajustes.csv"
    out = {}
    if arq.exists():
        with open(arq, encoding="utf-8") as f:
            for a in csv.DictReader(f):
                out.setdefault(a["ID"], []).append(a)
    return out


def carregar():
    with open(CSV, newline="", encoding="utf-8") as f:
        pontos = [p for p in csv.DictReader(f) if (p.get("ID") or "").strip()]
    aj = _ajustes()
    for p in pontos:
        for a in aj.get(p["ID"], []):
            if a["Campo"] == "ocultar":
                p["_ocultar"] = True
            elif a["Campo"] == "aviso_cnpj":
                if "cnpj" not in (p.get("Obs") or "").lower():
                    p["Obs"] = ((p.get("Obs") or "") + " " + a["Valor"].replace("(consulta em", "em").replace(")", "") + ".").strip()
            elif a["Campo"] in p:
                p[a["Campo"]] = a["Valor"]
    # Obs começando com "Ainda não está em funcionamento" tira o ponto do site até a Jen mudar a planilha
    # Regra da Jen (02/11/2026): CNPJ baixado sai; inapto/suspenso sai depois de 6 meses (data "desde" da Receita)
    for p in pontos:
        m = re.search(r"cnpj (inapt|baixad|suspens)\w* na receita(?: federal)? desde (\d{2}/\d{2}/\d{4})", norm(p.get("Obs") or ""))
        if m:
            desde = data_br(m.group(2))
            if m.group(1) == "baixad" or (desde and (HOJE - desde).days >= 180):
                p["_ocultar"] = True
    pontos = [p for p in pontos if not p.get("_ocultar")
              and not (p.get("Obs") or "").strip().lower().startswith("ainda não está em funcionamento")]
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
            c = COORD_CACHE.get(p["ID"])  # coordenada achada pela ação semanal (dados/coordenadas.csv)
            if c and c.get("Endereço usado") == p["Endereço"]:
                p["_lat"], p["_lng"] = float(c["Lat"]), float(c["Lng"])
    return pontos


def _cache_coord():
    arq = Path(__file__).resolve().parent.parent / "dados" / "coordenadas.csv"
    if not arq.exists():
        return {}
    with open(arq, encoding="utf-8") as f:
        return {r["ID"]: r for r in csv.DictReader(f) if r.get("Lat")}


COORD_CACHE = _cache_coord()


CSS_LINK = '<link rel="stylesheet" href="{raiz}residuos/estilo.css">'
FONTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
          '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">')


def pagina(titulo, descricao, url, raiz, corpo, jsonld, mapa=False):
    leaflet = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">'
               '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin="" defer></script>') if mapa else ""
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in jsonld)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descricao)}">
<link rel="canonical" href="{url}">
<link rel="alternate" type="text/markdown" title="llms.txt" href="{BASE_URL}/llms.txt">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descricao)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="pt_BR">
{f'<meta http-equiv="origin-trial" content="{ORIGIN_TRIAL}">' if ORIGIN_TRIAL else ""}
{FONTES}
{CSS_LINK.format(raiz=raiz)}
{leaflet}
{ld}
{f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}var _ok=false;try{{_ok=localStorage.getItem("desvia-cookies")==="sim"}}catch(e){{}}gtag("consent","default",{{ad_storage:"denied",ad_user_data:"denied",ad_personalization:"denied",analytics_storage:_ok?"granted":"denied"}});gtag("js",new Date());gtag("config","{GA4}");function desviaGA(){{gtag("consent","update",{{analytics_storage:"granted"}})}}</script>' if GA4 else ""}
</head>
<body>
<header><nav><a class="logo" href="{raiz}">♻ Projeto <span>Desvia</span></a><div class="menu"><a href="{raiz}#resultados">Buscar</a><a href="{raiz}guias/">Guias</a><a href="{raiz}residuos/">Cidades</a><a href="{raiz}empresas/">Para empresas</a><a class="menu-cta" href="{site_desvia.CADASTRO}" target="_blank" rel="noopener">Cadastre sua empresa</a></div></nav></header>
<main>
{corpo}
</main>
<footer><p>Desvia reúne, em uma só busca, dados públicos do IAT, do Cadastro Técnico Federal do IBAMA e das prefeituras municipais. As informações de licença refletem as bases públicas na data indicada e não substituem a consulta ao órgão ambiental.</p>
<nav class="rodape-links" aria-label="Rodapé">
  <div><b>Desvia</b><a href="{raiz}">Buscar onde descartar</a><a href="{raiz}guias/">Guias por resíduo</a><a href="{raiz}empresas/">Para empresas</a><a href="{raiz}privacidade/">Cookies e privacidade</a></div>
  <div><b>Cidades</b>{"".join(f'<a href="{raiz}residuos/{c}/">{esc(n)}</a>' for c, n in CIDADES.items())}</div>
  <div><b>Contato</b><a href="{site_desvia.WHATSAPP}" target="_blank" rel="noopener">WhatsApp</a><a href="{site_desvia.CADASTRO}" target="_blank" rel="noopener">Cadastre sua empresa</a></div>
</nav></footer>
{f'''<div id="cookies" class="cookies" hidden role="dialog" aria-label="Aviso de cookies"><p>Usamos cookies só para medir visitas e melhorar o site (Google Analytics). Não usamos para anúncios. <a href="{raiz}privacidade/">Política de cookies</a></p><div class="cookies-bt"><button type="button" data-c="nao">Recusar opcionais</button><button type="button" data-c="sim" class="cookies-ok">Aceitar</button></div></div>
<script>(function(){{var b=document.getElementById("cookies");if(!b)return;var v=null;try{{v=localStorage.getItem("desvia-cookies")}}catch(e){{}}if(!v)b.hidden=false;b.addEventListener("click",function(e){{var c=e.target.getAttribute("data-c");if(!c)return;try{{localStorage.setItem("desvia-cookies",c)}}catch(x){{}}b.hidden=true;if(c==="sim"&&window.desviaGA)desviaGA()}});document.querySelectorAll("[data-cookies-abrir]").forEach(function(a){{a.addEventListener("click",function(ev){{ev.preventDefault();b.hidden=false}})}})}})();</script>''' if GA4 else ""}
{f'<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>' if GOATCOUNTER else ""}
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
    shutil.copy(Path(__file__).with_name("hub.js"), SAIDA / "hub.js")
    shutil.copy(Path(__file__).with_name("webmcp.js"), SAIDA / "webmcp.js")
    urls = [(f"{BASE_URL}/{u}", pr) for u, pr in PAGINAS_FIXAS]
    nomes = {s: (f, c) for s, f, c, _ in CATEGORIAS}
    resumo_cidades = []
    contagens = {}

    for cid_slug, cidade in CIDADES.items():
        do_lugar = [p for p in pontos if cid_slug in p["_cidades"]]
        por_cat = {}
        for p in do_lugar:
            for c in p["_cats"]:
                por_cat.setdefault(c, []).append(p)
        cats_ordem = [s for s, _, _, _ in CATEGORIAS if s in por_cat]
        resumo_cidades.append((cid_slug, cidade, len(do_lugar), len(cats_ordem)))
        contagens[cid_slug] = {c: len(v) for c, v in por_cat.items()}

        for cat in cats_ordem:
            frase, curto = nomes[cat]
            pts = sorted(por_cat[cat], key=lambda p: (ORDEM_STATUS[p["_status"]],
                                                     norm(p["Município sede"]).replace(" ", "-") != cid_slug,
                                                     norm(p["Nome"])))
            url = f"{BASE_URL}/residuos/{cid_slug}/{cat}/"
            titulo = (f"{TERMO_BUSCA[cat]} em {cidade}: onde levar | Desvia" if cat in TERMO_BUSCA
                      else f"Onde descartar {frase} em {cidade}-{UF} | Desvia")
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
{f'<p class="localizador"><a href="{LOCALIZADOR[cat][1]}" target="_blank" rel="noopener">{esc(LOCALIZADOR[cat][0])} ↗</a></p>' if cat in LOCALIZADOR else ''}
<p class="atualizado">Dados atualizados em {HOJE:%d/%m/%Y}. Licença válida aparece primeiro. <a href="../?r={cat}#mapa">Abrir no mapa com filtros</a></p>
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

        # dados do mapa da cidade em JSON (usado pela página antiga de Mandaguari e por quem quiser reaproveitar)
        _js = [{"n": p["Nome"], "a": p["_lat"], "o": p["_lng"], "e": "" if pessoa_fisica(p) else p["Endereço"],
                "r": p["Resíduos aceitos"], "t": p["Telefone"], "s": p["_status"]} for p in do_lugar]
        (SAIDA / cid_slug).mkdir(parents=True, exist_ok=True)
        (SAIDA / cid_slug / "pontos.json").write_text(json.dumps(_js, ensure_ascii=False), encoding="utf-8")
        if cid_slug == "mandaguari":
            _mg = RAIZ / "mandaguari.html"
            if _mg.exists():
                _n = sum(1 for x in _js if x["a"] is not None)
                _t = _mg.read_text(encoding="utf-8")
                _t2 = re.sub(r'(<span class="stat-num">)\d+\+?(</span>\s*<span class="stat-label">Pontos de descarte no mapa)', rf"\g<1>{_n}\2", _t)
                if _t2 != _t:
                    _mg.write_text(_t2, encoding="utf-8")

        # páginas de serviços
        serv_links = []
        _pags = []
        for sv_slug, sv_nome, sv_aviso, sv_regra in SERVICOS:
            pts = [p for p in do_lugar if sv_regra(p)]
            if not pts:
                continue
            pts.sort(key=lambda p: (ORDEM_STATUS[p["_status"]], norm(p["Nome"])))
            serv_links.append((sv_slug, sv_nome, len(pts)))
            url = f"{BASE_URL}/residuos/{cid_slug}/servicos/{sv_slug}/"
            n_val = sum(1 for p in pts if p["_status"] in ("valida", "vencendo"))
            faq = [(f"Como escolher {sv_nome.lower()} em {cidade}?",
                    "Prefira quem tem licença ambiental válida, peça o comprovante de destinação e desconfie de preço muito abaixo do mercado."),
                   ("A licença que aparece aqui é a atual?",
                    f"É a que consta nas bases públicas (IAT, CTF/IBAMA e prefeitura) em {HOJE:%d/%m/%Y}. Antes de contratar, peça a licença à empresa.")]
            corpo = f"""<nav class="trilha" aria-label="Você está em"><a href="../../../">Cidades</a> › <a href="../../">{esc(cidade)}</a> › {esc(sv_nome)}</nav>
<h1>{esc(sv_nome)} em {esc(cidade)}</h1>
<p class="resposta"><strong>{len(pts)} {'opção' if len(pts) == 1 else 'opções'}</strong> em {esc(cidade)}, {n_val} com licença ambiental válida localizada.</p>
<p class="regra">{esc(sv_aviso)}</p>
<p class="atualizado">Dados atualizados em {HOJE:%d/%m/%Y}. Licença válida aparece primeiro.</p>
{mapa_js(pts)}
<section class="lista">
{''.join(cartao(p, cid_slug) for p in pts)}
</section>
<section class="faq"><h2>Perguntas frequentes</h2>
{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(r)}</p></details>' for q, r in faq)}
</section>
@@OUTROS@@"""
            jsonld = [
                {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Cidades", "item": f"{BASE_URL}/residuos/"},
                    {"@type": "ListItem", "position": 2, "name": cidade, "item": f"{BASE_URL}/residuos/{cid_slug}/"},
                    {"@type": "ListItem", "position": 3, "name": sv_nome, "item": url}]},
                {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in faq]},
            ]
            serv_pag = (sv_slug, f"{sv_nome} em {cidade}: empresas e licença ambiental | Desvia",
                        f"{len(pts)} {'opção' if len(pts) == 1 else 'opções'} de {sv_nome.lower()} em {cidade}, com a situação da licença ambiental de cada empresa.",
                        url, corpo, jsonld)
            _pags.append(serv_pag)
        for sv_slug, titulo, descricao, url, corpo, jsonld in _pags:
            outros = "".join(f'<li><a href="../{s}/">{esc(n)}</a></li>' for s, n, _ in serv_links if s != sv_slug)
            corpo = corpo.replace("@@OUTROS@@", f'<section class="outras"><h2>Outros serviços em {esc(cidade)}</h2><ul>{outros}</ul></section>' if outros else "")
            destino = SAIDA / cid_slug / "servicos" / sv_slug / "index.html"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(pagina(titulo, descricao, url, "../../../../", corpo, jsonld, mapa=True), encoding="utf-8")
            urls.append((url, "0.7"))
        servicos_html = ("<section class=\"servicos\"><h2>Serviços em " + esc(cidade) + "</h2><p>Quem vem buscar, compra ou recebe.</p><ul>"
                         + "".join(f'<li><a href="servicos/{s}/">{esc(n)} <span class="n">{k}</span></a></li>' for s, n, k in serv_links)
                         + "</ul></section>") if serv_links else ""

        # página da cidade
        url = f"{BASE_URL}/residuos/{cid_slug}/"
        ctx = {"norm": norm, "selo": selo_licenca, "aviso_cnpj": aviso_cnpj, "obs_publica": obs_publica,
               "pessoa_fisica": pessoa_fisica, "servicos": servicos_html}
        corpo = hub.corpo_hub(cid_slug, cidade, do_lugar, cats_ordem, nomes, por_cat, ctx)
        jsonld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Cidades", "item": f"{BASE_URL}/residuos/"},
            {"@type": "ListItem", "position": 2, "name": cidade, "item": url}]}]
        (SAIDA / cid_slug / "index.html").write_text(
            pagina(f"Coleta e descarte de lixo em {cidade}: onde levar cada coisa | Desvia",
                   f"Onde descartar, doar ou reciclar em {cidade}: lixo eletrônico, entulho, pilhas, remédios, óleo, móveis e recicláveis, com mapa e a licença ambiental de cada empresa.",
                   url, "../../", corpo, jsonld, mapa=True), encoding="utf-8")
        urls.append((url, "0.8"))

    # página "Coleta de lixo: dias e horários" (quando a aba Fila de cidades tem o Link coleta)
    with open(RAIZ / "dados" / "cidades.csv", encoding="utf-8") as f:
        info_cid = {(c.get("Município") or "").strip(): c for c in csv.DictReader(f)}
    for cid_slug, cidade in CIDADES.items():
        c = info_cid.get(cidade, {})
        link, titular = (c.get("Link coleta") or "").strip(), (c.get("Titular coleta") or "").strip() or f"Prefeitura de {cidade}"
        if not link:
            continue
        url = f"{BASE_URL}/residuos/{cid_slug}/coleta-de-lixo/"
        tipo_link = "o cronograma oficial (PDF)" if link.lower().endswith(".pdf") else "o mapa oficial da coleta"
        cats_cid = [s_ for s_ in ("eletronicos", "pilhas-e-baterias", "lampadas", "medicamentos", "oleo-de-cozinha", "entulho", "moveis-e-volumosos", "poda-e-galhos", "pneus")
                    if (SAIDA / cid_slug / s_).exists()]
        nao_vai = "".join(f'<li><a href="../{s_}/">{esc(nomes[s_][1])}</a></li>' for s_ in cats_cid)
        faq = [
            (f"Qual o dia da coleta de lixo no meu bairro em {cidade}?",
             f"Os dias e horários da coleta comum e da coleta seletiva em {cidade} são definidos pelo responsável pelo serviço ({titular}). Consulte {tipo_link}. Eles podem mudar quando há novo contrato (licitação), então confira sempre a fonte oficial."),
            ("O que não pode ir na coleta comum?",
             "Pilhas, baterias, lâmpadas, eletrônicos, remédios, óleo de cozinha, entulho, móveis, pneus e galhos têm destino próprio. Veja onde levar cada um no Desvia."),
            ("A coleta não passou. O que fazer?",
             f"Primeiro, registre a reclamação com {titular} ou na ouvidoria da prefeitura. Se o problema continuar, comunique a agência reguladora que fiscaliza o serviço de limpeza urbana no município (no Paraná, em muitos municípios, a AGEPAR). Ela fiscaliza o titular do serviço, não o morador."),
        ]
        corpo = f"""<nav class="trilha" aria-label="Você está em"><a href="../../">Cidades</a> › <a href="../">{esc(cidade)}</a> › Coleta de lixo</nav>
<h1>Coleta de lixo em {esc(cidade)}: dias e horários por bairro</h1>
<p class="resposta">Os dias e horários da coleta comum e da coleta seletiva em {esc(cidade)} são definidos pelo responsável pelo serviço: <b>{esc(titular)}</b>. Consulte o seu bairro em {tipo_link}:</p>
<p><a class="pq-btn" href="{esc(link)}" target="_blank" rel="noopener">Ver dias e horários da coleta em {esc(cidade)} ↗</a></p>
<p class="regra">Os setores e dias de coleta podem mudar quando há novo contrato do serviço (licitação). Confira sempre a fonte oficial antes de colocar o lixo para fora.</p>

<h2>Dicas para a coleta passar sem problema</h2>
<ul class="lista-texto">
<li>Coloque o lixo para fora perto do horário da coleta, em sacos bem fechados, para não atrair animais.</li>
<li>Separe os recicláveis (papel, plástico, metal e vidro) limpos e secos para a coleta seletiva.</li>
<li>Vidro quebrado e objetos cortantes: embrulhe em jornal ou caixa e avise com um bilhete.</li>
</ul>

<h2>O que não vai na coleta comum</h2>
<p>Estes itens têm destino próprio em {esc(cidade)}:</p>
<ul class="outras">{nao_vai}</ul>

<h2>A coleta não passou?</h2>
<ol class="lista-texto">
<li><b>Reclame com o responsável pelo serviço</b> ({esc(titular)}) ou na ouvidoria da prefeitura. Anote o protocolo.</li>
<li><b>Se não resolver</b>, comunique a agência reguladora que fiscaliza a limpeza urbana no município. No Paraná, muitos municípios são regulados pela <b>AGEPAR</b>. A agência fiscaliza o titular do serviço (prefeitura, autarquia ou empresa contratada).</li>
</ol>

<section class="faq"><h2>Perguntas frequentes</h2>{"".join(f'<details><summary>{esc(q)}</summary><p>{esc(r)}</p></details>' for q, r in faq)}</section>"""
        jsonld = [
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Cidades", "item": f"{BASE_URL}/residuos/"},
                {"@type": "ListItem", "position": 2, "name": cidade, "item": f"{BASE_URL}/residuos/{cid_slug}/"},
                {"@type": "ListItem", "position": 3, "name": "Coleta de lixo", "item": url}]},
            {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in faq]},
        ]
        destino = SAIDA / cid_slug / "coleta-de-lixo" / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(pagina(f"Coleta de lixo em {cidade}: dias e horários por bairro | Desvia",
                                  f"Dia e horário da coleta de lixo e da coleta seletiva em {cidade}: onde consultar o seu bairro, o que não vai na coleta comum e o que fazer se a coleta não passar.",
                                  url, "../../../", corpo, jsonld), encoding="utf-8")
        urls.append((url, "0.8"))

    # índice de cidades
    itens = "".join(f'<li><a href="{s}/"><span>{esc(c)}</span><small>{n} pontos · {k} tipos de resíduo</small></a></li>'
                    for s, c, n, k in resumo_cidades)
    corpo = f"""<h1>Onde descartar resíduos</h1>
<p class="resposta">Pontos de entrega, cooperativas e empresas de coleta e destinação de resíduos, com a situação da licença ambiental, reunidos de várias fontes em uma só busca.</p>
<ul class="grade">{itens}</ul>
{site_desvia.pedir_cidade()}"""
    (SAIDA / "index.html").write_text(
        pagina("Onde descartar resíduos: cidades | Desvia",
               "Encontre onde descartar cada tipo de resíduo na sua cidade, com a situação da licença ambiental de quem recebe.",
               f"{BASE_URL}/residuos/", "../", corpo, []), encoding="utf-8")
    urls.insert(len(PAGINAS_FIXAS), (f"{BASE_URL}/residuos/", "0.9"))

    # guias por resíduo
    pasta_guias = RAIZ / "guias"
    if pasta_guias.exists():
        shutil.rmtree(pasta_guias)
    pasta_guias.mkdir()
    todas = {}
    for p in pontos:
        for c in p["_cats"]:
            todas[c] = todas.get(c, 0) + 1
    cats_geral = [(s, todas[s]) for s, _, _, _ in CATEGORIAS if s in todas]
    for slug, _ in cats_geral:
        if slug not in site_desvia.G.GUIAS:
            continue
        titulo, descricao, corpo, jsonld = site_desvia.guia(slug, nomes, contagens, CIDADES)
        destino = pasta_guias / slug / "index.html"
        destino.parent.mkdir(parents=True)
        destino.write_text(pagina(titulo, descricao, f"{BASE_URL}/guias/{slug}/", "../../", corpo, jsonld), encoding="utf-8")
        urls.append((f"{BASE_URL}/guias/{slug}/", "0.8"))
    (pasta_guias / "index.html").write_text(
        pagina("Guias de descarte de resíduos | Desvia",
               "Como descartar cada tipo de resíduo em casa e na empresa, o que diz a lei e onde levar.",
               f"{BASE_URL}/guias/", "../", site_desvia.indice_guias(nomes, cats_geral), []), encoding="utf-8")
    urls.insert(len(PAGINAS_FIXAS), (f"{BASE_URL}/guias/", "0.9"))

    # política de cookies e privacidade
    pasta_priv = RAIZ / "privacidade"
    pasta_priv.mkdir(exist_ok=True)
    (pasta_priv / "index.html").write_text(
        pagina("Política de cookies e privacidade | Desvia",
               "Quais dados o Desvia coleta, para que usa os cookies do Google Analytics e como mudar sua escolha.",
               f"{BASE_URL}/privacidade/", "../", site_desvia.privacidade(HOJE), []), encoding="utf-8")
    urls.append((f"{BASE_URL}/privacidade/", "0.2"))

    # página para empresas (checklist, calendário, serviços)
    pasta_emp = RAIZ / "empresas"
    pasta_emp.mkdir(exist_ok=True)
    (pasta_emp / "index.html").write_text(
        pagina("Sua empresa está em dia com os resíduos? Checklist gratuito | Desvia",
               "Checklist de 6 perguntas sobre licença ambiental, PGRS, MTR, CDF e declarações, com o calendário de obrigações de resíduos para empresas.",
               f"{BASE_URL}/empresas/", "../", site_desvia.empresas(), []), encoding="utf-8")
    urls.insert(len(PAGINAS_FIXAS), (f"{BASE_URL}/empresas/", "0.8"))

    # página inicial (busca única)
    ctx = {"norm": norm, "selo": selo_licenca, "aviso_cnpj": aviso_cnpj, "obs_publica": obs_publica,
           "pessoa_fisica": pessoa_fisica, "base": BASE_URL}
    publicados = [p for p in pontos if p["_cidades"] & set(CIDADES)]
    corpo, jsonld = site_desvia.home(publicados, CIDADES, nomes, cats_geral, contagens, ctx, HOJE)
    html_home = pagina("Onde descartar entulho e resíduos em Londrina e região | Desvia",
                       "Pontos de entrega, cooperativas e empresas de coleta e destinação de resíduos, com a situação da licença ambiental. Várias fontes, uma só busca.",
                       f"{BASE_URL}/", "", corpo, jsonld, mapa=True)
    (RAIZ / "index.html").write_text(html_home.replace("<main>", '<main class="home">', 1), encoding="utf-8")

    # llms.txt: resumo do site para assistentes de IA
    linhas_llms = [
        "# Desvia",
        "",
        "> Onde descartar cada resíduo no Paraná: pontos de entrega, cooperativas e empresas de coleta, transporte e destinação, "
        "com a situação da licença ambiental de cada uma. Reúne dados públicos do IAT, do Cadastro Técnico Federal do IBAMA "
        "e das prefeituras municipais.",
        "",
        f"Dados atualizados em {HOJE:%d/%m/%Y}. A situação da licença reflete as bases públicas na data da consulta; "
        "\"licença não localizada\" significa que nada foi encontrado nas bases consultadas, não que a empresa seja irregular.",
        "",
        "## Busca",
        f"- [Busca por resíduo e cidade]({BASE_URL}/): mapa e lista com filtros. Aceita ?q=<resíduo>&cidade=<cidade>&r=<tipo>.",
        "",
        "## Cidades",
    ]
    for s_, c_, n_, k_ in resumo_cidades:
        linhas_llms.append(f"- [{c_}]({BASE_URL}/residuos/{s_}/): {n_} pontos e empresas, {k_} tipos de resíduo, obrigações das empresas")
        for cat_ in [s for s, _, _, _ in CATEGORIAS if s in contagens[s_]]:
            linhas_llms.append(f"  - [Onde descartar {nomes[cat_][0]} em {c_}]({BASE_URL}/residuos/{s_}/{cat_}/)")
    linhas_llms += ["", "## Guias de descarte"]
    for slug, _ in cats_geral:
        if slug in site_desvia.G.GUIAS:
            linhas_llms.append(f"- [Como descartar {nomes[slug][0]}]({BASE_URL}/guias/{slug}/): {site_desvia.G.GUIAS[slug]['intro']}")
    linhas_llms += ["", "## Opcional",
                    f"- [Guia de Mandaguari]({BASE_URL}/mandaguari.html): coleta por bairro, regras municipais (Lei 4.419/2025) e PGRS",
                    f"- [Contato]({site_desvia.WHATSAPP}): orientação gratuita e cadastro de empresas", ""]
    (RAIZ / "llms.txt").write_text("\n".join(linhas_llms), encoding="utf-8")

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
