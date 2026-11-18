#!/usr/bin/env python3
"""Etapa 5 do levantamento (coleta/LEIA-ME.md): lê os localizadores de logística reversa e outras
fontes abertas para o Paraná e grava coleta/localizadores-pr.csv (uma linha por ponto).

Fontes lidas aqui (sem navegador, uma vez por mês, respeitando o robots.txt de cada site):
  Reciclanip (pneus), Green Eletron pilhas (Ambipar/reciclelog), Green Eletron eletroeletrônicos
  (inclui ABREE), Reciclus (lâmpadas), Jogue Limpo (embalagens de óleo lubrificante),
  OpenStreetMap (ecopontos e contêineres de reciclagem) e Mapa das OSCs do Ipea (entidades que
  podem receber doação).
Fora daqui: LogMed (PDF que a Jen baixa; coleta/logmed_pdf.py), EcoMed (robots.txt proíbe /api:
só pelo navegador da Jen), inpEV (unidade regional em Maringá; certificado do site incompleto).

Uso: python3 coleta/localizadores.py [cidade ...]   (sem cidade: as cidades da lista CIDADES)
Saída: coleta/localizadores-pr.csv e coleta/localizadores-pr-resumo.md
"""
import csv
import gzip
import html
import io
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIAG = RAIZ / "coleta" / "diag"
UA = {"User-Agent": "Desvia/1.0 (+https://desvia.eco.br/; levantamento mensal de pontos de descarte)"}
HOJE = date.today().strftime("%d/%m/%Y")
CIDADES = ["Londrina", "Maringá", "Apucarana", "Arapongas", "Rolândia", "Cambé", "Cambira", "Ibiporã",
           "Mandaguari", "Jandaia do Sul", "Marialva", "Sarandi"]
CAMPOS = ["Programa", "Resíduo", "Nome", "Endereço", "Bairro", "Cidade", "CEP", "Telefone", "Lat", "Lng", "Obs", "CNPJ", "Fonte"]
STATUS = []


def norm(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper().strip()


def get(url, data=None, headers=None, timeout=90, enc=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers={**UA, "Accept": "*/*", **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                cs = enc or r.headers.get_content_charset() or "utf-8"
                return raw.decode(cs, "ignore")
        except Exception as e:  # noqa: BLE001
            if tentativa == 2:
                raise
            time.sleep(5 * (tentativa + 1))


def guardar_diag(nome, texto):
    DIAG.mkdir(exist_ok=True)
    (DIAG / f"loc_{nome}.txt").write_text(texto[:300000], encoding="utf-8")


def limpa(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip(" ,-")


def fonte(nome, func, cidades):
    t0 = time.time()
    try:
        linhas = func(cidades)
        STATUS.append(f"- {nome}: {len(linhas)} pontos no PR ({time.time() - t0:.0f} s)")
        return linhas
    except Exception as e:  # noqa: BLE001
        STATUS.append(f"- {nome}: FALHOU ({e})")
        return []


# ── Reciclanip (pneus): POST /ajax/pontos.php com uf=PR devolve JSON do estado ─────────────
def reciclanip(cidades):
    t = get("https://www.reciclanip.org.br/ajax/pontos.php", {"uf": "PR"},
            {"X-Requested-With": "XMLHttpRequest", "Referer": "https://www.reciclanip.org.br/pontos-de-coleta/coleta-no-brasil/"})
    out = []
    for p in json.loads(t):
        if str(p.get("ativo", "1")) != "1":
            continue
        out.append({"Programa": "Reciclanip", "Resíduo": "Pneus", "Nome": p.get("nome_comercial") or p.get("razao_social"),
                    "Endereço": p.get("endereco"), "Cidade": p.get("cidade"), "CEP": p.get("cep"),
                    "Telefone": p.get("telefone_formatado") or p.get("telefone"),
                    "Obs": "Ponto de coleta de pneus inservíveis da Reciclanip.",
                    "Fonte": "Reciclanip (pontos de coleta)"})
    return out


# ── Green Eletron pilhas e baterias (sistema da Ambipar): tabela HTML por cidade ───────────
def green_pilhas(cidades):
    out = []
    for c in cidades:
        t = get("https://sistema.reciclelog.com.br/info/green?" + urllib.parse.urlencode(
            {"search_state": "PR", "search_city": norm(c), "button": ""}))
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            tds = [limpa(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) >= 4 and tds[0] and norm(tds[3]) == norm(c):
                out.append({"Programa": "Green Eletron", "Resíduo": "Pilhas e baterias", "Nome": tds[0], "Endereço": tds[1],
                            "Bairro": tds[2], "Cidade": tds[3], "Obs": "Ponto de entrega de pilhas e baterias portáteis.",
                            "Fonte": "Green Eletron (pontos de entrega de pilhas)"})
        time.sleep(1)
    return out


# ── Green Eletron eletroeletrônicos (inclui ABREE): POST devolve o Brasil inteiro em JSON ──
def green_eletro(cidades):
    t = get("https://green.care-br.com/busca_empresa.php", {"lat": "-23.3045", "lng": "-51.1696"}, enc="latin-1", timeout=180)
    d = json.loads(t)
    out = []
    for p in d.get("msg", []):
        end = p.get("end") or ""
        m = re.search(r"CEP:\s*([\d-]+)\.\s*(.+?)-([A-Z]{2})\s*$", end)
        if not m or m.group(3) != "PR":
            continue
        rua = end.split(". CEP:")[0]
        partes = [x.strip() for x in rua.split(".") if x.strip() and x.strip() != "Não Informado"]
        abree = (p.get("coleta_abree") == "S") or "abree" in (p.get("name") or "").lower()
        obs = limpa(p.get("info") or "")
        if p.get("descricao_local"):
            obs = (obs + " " + limpa(p["descricao_local"])).strip()
        out.append({"Programa": "ABREE" if abree else "Green Eletron", "Resíduo": "Eletroeletrônicos",
                    "Nome": p.get("name"), "Endereço": ", ".join(partes[:2]), "Bairro": partes[2] if len(partes) > 2 else "",
                    "Cidade": m.group(2), "CEP": m.group(1), "Lat": p.get("lat"), "Lng": p.get("lng"), "Obs": obs[:300],
                    "Fonte": "ABREE (pontos de recebimento)" if abree else "Green Eletron (pontos de entrega)"})
    return out


# ── Reciclus (lâmpadas): listagem JetEngine filtrada por estado (PR = 11), página a página ─
def reciclus(cidades):
    out, vistos = [], set()
    for pg in range(1, 80):
        url = "https://reciclus.org.br/lista-pontos-entrega/?" + urllib.parse.urlencode(
            {"jsf": "jet-engine:pontos-entrega-lista", "tax": "estado:11", "pagenum": pg})
        t = get(url)
        if pg == 1:
            guardar_diag("reciclus", t)
        itens = re.findall(r'<div class="jet-listing-grid__item[^"]*"[^>]*data-post-id="(\d+)"(.*?)(?=<div class="jet-listing-grid__item|</div>\s*</div>\s*</div>\s*</div>\s*</div>\s*$)', t, re.S)
        novos = 0
        for pid, bloco in itens:
            if pid in vistos:
                continue
            vistos.add(pid)
            novos += 1
            txt = [limpa(x) for x in re.findall(r'<div class="jet-listing-dynamic-field__content"[^>]*>(.*?)</div>', bloco, re.S)]
            txt = [x for x in txt if x]
            if not txt:
                continue
            nome, resto = txt[0], txt[1:]
            cidade = next((x for x in resto if norm(x) in {norm(c) for c in CIDADES} or re.search(r"[-/]\s*PR\b", x)), "")
            out.append({"Programa": "Reciclus", "Resíduo": "Lâmpadas", "Nome": nome, "Endereço": "; ".join(resto)[:250],
                        "Cidade": re.sub(r"\s*[-/]\s*PR\b.*", "", cidade), "Obs": "Ponto de entrega de lâmpadas da Reciclus.",
                        "Fonte": "Reciclus (pontos de entrega)"})
        if not novos:
            break
        time.sleep(1)
    return out


# ── Jogue Limpo (embalagens plásticas de óleo lubrificante): POST pevs_tratar.php ──────────
def jogue_limpo(cidades):
    out = []
    for pagina, tipo in (("pevs_tratar.php", "PEV"), ("centrais_tratar.php", "Central")):
        try:
            t = get("https://www.joguelimpo.org.br/institucional/" + pagina, {"estado": "PR"},
                    {"X-Requested-With": "XMLHttpRequest", "Referer": "https://www.joguelimpo.org.br/institucional/pevs.php"})
        except Exception:  # noqa: BLE001
            continue
        guardar_diag("joguelimpo_" + tipo, t)
        for bloco in re.split(r"<(?:div|li|tr)[^>]*class=['\"][^'\"]*(?:card|item|pev|central)[^'\"]*['\"][^>]*>", t)[1:]:
            linhas = [limpa(x) for x in re.split(r"<br\s*/?>|</p>|</h\d>|</div>|</td>", bloco) if limpa(x)]
            if len(linhas) < 2:
                continue
            cidade = next((re.sub(r"\s*[-/]\s*PR.*", "", x) for x in linhas if re.search(r"[-/]\s*PR\b", x)), "")
            fone = next((x for x in linhas if re.search(r"\(\d{2}\)\s*\d", x)), "")
            out.append({"Programa": "Jogue Limpo", "Resíduo": "Embalagens de óleo lubrificante",
                        "Nome": linhas[0], "Endereço": "; ".join(x for x in linhas[1:4] if x != fone)[:250], "Cidade": cidade,
                        "Telefone": fone, "Obs": f"{tipo} do Jogue Limpo: embalagens plásticas de óleo lubrificante, escorridas e tampadas.",
                        "Fonte": "Jogue Limpo (pontos de entrega)"})
    return out


# ── OpenStreetMap: ecopontos e contêineres de reciclagem na região (Overpass) ──────────────
def osm(cidades):
    q = ('[out:json][timeout:120];(nwr["amenity"="recycling"](-23.85,-52.25,-22.95,-50.85);'
         'nwr["amenity"="waste_transfer_station"](-23.85,-52.25,-22.95,-50.85););out center tags;')
    d = None
    for ep in ("https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
               "https://maps.mail.ru/osm/tools/overpass/api/interpreter"):
        try:
            d = json.loads(get(ep, {"data": q}, {"Content-Type": "application/x-www-form-urlencoded"}, timeout=180))
            break
        except Exception as e:  # noqa: BLE001
            STATUS.append(f"  (Overpass {ep.split('/')[2]}: {e})")
    if not d:
        raise RuntimeError("Overpass indisponível")
    out = []
    for e in d.get("elements", []):
        tg = e.get("tags", {})
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lng = e.get("lon") or (e.get("center") or {}).get("lon")
        tipos = [k.split(":", 1)[1].replace("_", " ") for k, v in tg.items() if k.startswith("recycling:") and v == "yes"]
        nome = tg.get("name") or ("Ecoponto" if tg.get("recycling_type") == "centre" else "Contêiner de reciclagem")
        end = ", ".join(x for x in [tg.get("addr:street"), tg.get("addr:housenumber")] if x)
        out.append({"Programa": "OpenStreetMap", "Resíduo": ", ".join(tipos) or "Recicláveis", "Nome": nome, "Endereço": end,
                    "Cidade": tg.get("addr:city", ""), "Lat": lat, "Lng": lng, "Telefone": tg.get("phone", ""),
                    "Obs": ("Tipo: " + tg.get("recycling_type", tg.get("amenity", ""))) + (f". Operador: {tg['operator']}" if tg.get("operator") else ""),
                    "Fonte": "OpenStreetMap (© colaboradores do OpenStreetMap)"})
    return out


# ── Mapa das OSCs (Ipea): entidades que podem receber doação ───────────────────────────────
DOACAO = re.compile(r"BAZAR|BRECH|RECICL|CATADOR|REAPROVEIT|CARITAS|EXERCITO DA SALVACAO|SOPAO|ROUPA|AGASALHO|"
                    r"MOVEIS|ECOLOG|AMBIENT|LIXO|RESIDUO|APAE|LAR |ASILO|ALBERGUE|BANCO DE ALIMENTOS|SOLIDARI", re.I)


def mapa_oscs(cidades):
    t = get("https://mapaosc.ipea.gov.br/base-dados")
    m = re.search(r'href="(/download/[^"]*baseDivulgacao[^"]*\.csv)"', t)
    if not m:
        raise RuntimeError("link da base não achado")
    url = "https://mapaosc.ipea.gov.br" + m.group(1)
    req = urllib.request.Request(url, headers=UA)
    alvo = {norm(c) for c in cidades}
    out, cab = [], None
    with urllib.request.urlopen(req, timeout=600) as r:
        texto = io.TextIOWrapper(r, encoding="utf-8", errors="ignore", newline="")
        primeira = texto.readline()
        sep = ";" if primeira.count(";") > primeira.count(",") else ","
        cab = next(csv.reader([primeira], delimiter=sep))
        STATUS.append("  (Mapa das OSCs, colunas: " + ", ".join(cab[:40]) + ")")
        idx = {norm(c): i for i, c in enumerate(cab)}

        def col(*nomes):
            for n in nomes:
                for k, i in idx.items():
                    if n in k:
                        return i
            return None
        i_uf, i_mun = col("UF", "SG_UF", "ESTADO"), col("MUNICIPIO", "MUN")
        i_nome = col("FANTASIA", "NOME", "RAZAO")
        i_cnpj, i_end = col("CNPJ"), col("ENDERECO", "LOGRADOURO")
        i_area = col("AREA_ATUACAO", "AREA")
        i_lat, i_lng = col("LATITUDE", "LAT"), col("LONGITUDE", "LON")
        for linha in csv.reader(texto, delimiter=sep):
            try:
                if i_uf is not None and norm(linha[i_uf]) not in ("PR", "PARANA", "41"):
                    continue
                if i_mun is None or norm(linha[i_mun]) not in alvo:
                    continue
                nome = linha[i_nome] if i_nome is not None else ""
                area = linha[i_area] if i_area is not None else ""
                if not DOACAO.search(norm(nome) + " " + norm(area)):
                    continue
                out.append({"Programa": "Mapa das OSCs", "Resíduo": "Doação (conferir o que aceita)", "Nome": nome,
                            "Endereço": linha[i_end] if i_end is not None else "", "Cidade": linha[i_mun],
                            "CNPJ": linha[i_cnpj] if i_cnpj is not None else "",
                            "Lat": linha[i_lat] if i_lat is not None else "", "Lng": linha[i_lng] if i_lng is not None else "",
                            "Obs": ("Área: " + area)[:200], "Fonte": "Mapa das Organizações da Sociedade Civil (Ipea)"})
            except IndexError:
                continue
    return out


def main():
    cidades = sys.argv[1:] or CIDADES
    todos = []
    todos += fonte("Reciclanip", reciclanip, cidades)
    todos += fonte("Green Eletron pilhas", green_pilhas, cidades)
    todos += fonte("Green Eletron eletroeletrônicos e ABREE", green_eletro, cidades)
    todos += fonte("Reciclus", reciclus, cidades)
    todos += fonte("Jogue Limpo", jogue_limpo, cidades)
    todos += fonte("OpenStreetMap", osm, cidades)
    todos += fonte("Mapa das OSCs", mapa_oscs, cidades)
    arq = RAIZ / "coleta" / "localizadores-pr.csv"
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        for l in todos:
            w.writerow({k: ("" if l.get(k) is None else str(l.get(k)).strip()) for k in CAMPOS})
    alvo = {norm(c) for c in cidades}
    por = {}
    for l in todos:
        if norm(l.get("Cidade")) in alvo:
            por.setdefault(l["Programa"], {}).setdefault(l["Cidade"].title(), 0)
            por[l["Programa"]][l["Cidade"].title()] += 1
    resumo = [f"# Localizadores: Paraná ({HOJE})", "", *STATUS, "", "## Nas cidades do Desvia", ""]
    for prog, cs in por.items():
        resumo.append(f"- {prog}: " + ", ".join(f"{c} {n}" for c, n in sorted(cs.items())))
    (RAIZ / "coleta" / "localizadores-pr-resumo.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    print("\n".join(resumo))


if __name__ == "__main__":
    main()
