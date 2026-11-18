#!/usr/bin/env python3
"""Diagnóstico (temporário): baixa as páginas dos localizadores e guarda um recorte em coleta/diag/
para mapear como cada um entrega os dados. Roda na ação "Diagnóstico dos localizadores"."""
import re, sys, json, urllib.request, urllib.parse, ssl
from pathlib import Path
OUT = Path(__file__).resolve().parent / "diag"; OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (compatible; Desvia/1.0; +https://desvia.eco.br/)"}
ctx = ssl.create_default_context()

def get(name, url, data=None, headers=None, limit=250000):
    try:
        body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
        req = urllib.request.Request(url, data=body, headers={**UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            raw = r.read(); st = r.status; ct = r.headers.get("Content-Type", "")
    except Exception as e:
        raw, st, ct = str(e).encode(), "ERRO", ""
    txt = raw.decode("utf-8", "ignore")
    (OUT / f"{name}.txt").write_text(f"# {url}\n# status {st} {ct} {len(raw)} bytes\n" + txt[:limit], encoding="utf-8")
    links = sorted(set(re.findall(r"""["'(]((?:https?:)?/?[\w./-]*(?:ajax|api|\.php|json|wp-json|admin-ajax|busca|pontos|search)[\w./?=&%-]*)""", txt)))[:200]
    (OUT / f"{name}.links.txt").write_text("\n".join(links), encoding="utf-8")
    print(name, st, len(raw))
    return txt

import sys as _s
if len(_s.argv) > 1 and _s.argv[1] == "2":
    t = get("jl_pevs_full", "https://www.joguelimpo.org.br/institucional/pevs.php", limit=10**7)
    for src in re.findall(r"<script[^>]+src=['\"]([^'\"]+)['\"]", t):
        if "jquery" in src or "bootstrap" in src or "http" in src and "joguelimpo" not in src: continue
        u = urllib.parse.urljoin("https://www.joguelimpo.org.br/institucional/pevs.php", src)
        get("jl_js_" + re.sub(r"\W", "_", src)[-40:], u, limit=10**6)
    for uf in ("PR",):
        for path in ("pevs_estado.php", "ajax/pevs.php", "pevs.php?uf=PR"):
            get("jl_try_" + re.sub(r"\W", "_", path), "https://www.joguelimpo.org.br/institucional/" + path, data={"uf": uf, "estado": uf})
    get("reciclus_full", "https://reciclus.org.br/lista-pontos-entrega/", limit=10**7)
    get("reciclus_types", "https://reciclus.org.br/wp-json/wp/v2/types", limit=10**6)
    get("reciclus_tax", "https://reciclus.org.br/wp-json/wp/v2/taxonomies", limit=10**6)
    get("prolata_pev", "https://www.prolata.com.br/mercados-de-atuacao/pontos-de-entrega-voluntaria/", limit=10**6)
    get("anp_lub", "https://www.gov.br/anp/pt-br/assuntos/distribuicao-e-revenda/lubrificantes", limit=10**6)
    get("green_pilhas_pr", "https://sistema.reciclelog.com.br/info/green?search_state=PR&search_city=&button=", limit=10**7)
    q = '[out:json][timeout:90];(nwr["amenity"="recycling"](-23.8,-52.2,-23.0,-50.9););out center tags;'
    get("overpass_reg", "https://overpass-api.de/api/interpreter", data={"data": q}, limit=10**7)
    get("overpass_reg2", "https://overpass.kumi.systems/api/interpreter", data={"data": q}, limit=10**7)
    _s.exit()

for dom in ["www.reciclanip.org.br", "reciclus.org.br", "sistema.reciclelog.com.br", "greeneletron.org.br", "green.care-br.com",
            "www.joguelimpo.org.br", "www.prolata.com.br", "www.sistemacampolimpo.org.br", "ecomed.eco.br", "mapaosc.ipea.gov.br",
            "www.gov.br", "overpass-api.de", "abree.org.br"]:
    get("robots_" + dom, f"https://{dom}/robots.txt", limit=4000)

get("reciclanip_pagina", "https://www.reciclanip.org.br/pontos-de-coleta/coleta-no-brasil/")
for k in ("uf", "estado", "state"):
    get(f"reciclanip_ajax_{k}", "https://www.reciclanip.org.br/ajax/pontos.php", data={k: "PR"}, headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://www.reciclanip.org.br/pontos-de-coleta/coleta-no-brasil/"})
get("reciclus_pagina", "https://reciclus.org.br/lista-pontos-entrega/")
get("green_pilhas", "https://sistema.reciclelog.com.br/info/green?search_state=PR&search_city=LONDRINA&button=")
get("green_pilhas_form", "https://sistema.reciclelog.com.br/info/green")
get("green_eletro_pagina", "https://greeneletron.org.br/onde-descartar/")
get("green_eletro_busca", "https://green.care-br.com/busca_empresa.php", data={"lat": "-23.3045", "lng": "-51.1696", "latitude": "-23.3045", "longitude": "-51.1696"})
get("joguelimpo_pevs", "https://www.joguelimpo.org.br/institucional/pevs.php")
get("joguelimpo_centrais", "https://www.joguelimpo.org.br/institucional/centrais.php")
get("prolata", "https://www.prolata.com.br/rota-da-reciclagem/")
get("inpev", "https://www.sistemacampolimpo.org.br/logistica-reversa/unidades-recebimento/")
get("ecomed_cidades", "https://ecomed.eco.br/api/geo/cidades?q=Londrina")
get("ecomed_mapa", "https://ecomed.eco.br/mapa")
get("abree", "https://abree.org.br/pontos-de-recebimento")
get("anp_dados_abertos", "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos")
get("anp_lubrificantes", "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/autorizacoes-de-exercicio-de-atividade-aea")
get("mapaosc_base", "https://mapaosc.ipea.gov.br/base-dados")
q = '[out:json][timeout:120];area["ISO3166-2"="BR-PR"]->.a;(nwr["amenity"="recycling"](area.a););out center tags;'
get("overpass_pr", "https://overpass-api.de/api/interpreter", data={"data": q}, limit=400000)
