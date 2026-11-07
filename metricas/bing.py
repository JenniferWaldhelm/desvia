#!/usr/bin/env python3
"""Baixa do Bing Webmaster as buscas e páginas do mês (AAAA-MM; vazio = mês anterior)
e grava metricas/AAAA-MM/bing_consultas.csv, bing_paginas.csv e bing.md.
Precisa do segredo BING_API_KEY (Bing Webmaster › Configurações › Acesso à API)."""
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CHAVE = os.environ.get("BING_API_KEY", "")
if not CHAVE:
    sys.exit("Falta o segredo BING_API_KEY.")
SITES = ["https://desvia.eco.br/", "https://jenniferwaldhelm.github.io/desvia/"]
API = "https://ssl.bing.com/webmaster/api.svc/json/"

if len(sys.argv) > 1 and sys.argv[1]:
    ano, mes = map(int, sys.argv[1].split("-"))
    inicio = date(ano, mes, 1)
else:
    inicio = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def chamar(metodo, site):
    url = API + metodo + "?" + urllib.parse.urlencode({"siteUrl": site, "apikey": CHAVE})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=60) as r:
            return json.load(r).get("d") or []
    except urllib.error.HTTPError as e:
        print(f"Bing respondeu {e.code} em {metodo} ({site}): {e.read()[:200]!r}")
        return None


def data_bing(v):
    m = re.search(r"/Date\((\d+)", str(v))
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date() if m else None


def agrega(linhas, chave):
    soma = defaultdict(lambda: {"cliques": 0, "impressoes": 0, "pos": 0.0})
    for l in linhas:
        d = data_bing(l.get("Date"))
        if not d or not (inicio <= d <= fim):
            continue
        s = soma[l.get(chave, "")]
        imp = int(l.get("Impressions") or 0)
        s["cliques"] += int(l.get("Clicks") or 0)
        s["impressoes"] += imp
        s["pos"] += float(l.get("AvgImpressionPosition") or 0) * imp
    return sorted(((k, v["cliques"], v["impressoes"], round(v["pos"] / v["impressoes"], 1) if v["impressoes"] else "")
                   for k, v in soma.items()), key=lambda x: (-x[2], -x[1]))


consultas = paginas = None
usado = None
for site in SITES:
    c = chamar("GetQueryStats", site)
    if c is None:
        continue
    p = chamar("GetPageStats", site) or []
    consultas, paginas, usado = agrega(c, "Query"), agrega(p, "Query"), site
    if consultas or paginas:
        break

if usado is None:
    sys.exit("Nenhum site do Desvia respondeu no Bing. Confira se o site está cadastrado e se a chave é da mesma conta.")

pasta = Path(__file__).resolve().parent / f"{inicio:%Y-%m}"
pasta.mkdir(parents=True, exist_ok=True)
for nome, dados, col in (("bing_consultas.csv", consultas, "consulta"), ("bing_paginas.csv", paginas, "pagina")):
    with open(pasta / nome, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([col, "cliques", "impressoes", "posicao_media"])
        w.writerows(dados)

top = lambda lst: [f"- {k}: {c} cliques, {i} impressões, posição {p}" for k, c, i, p in lst[:15]]
linhas = [f"# Bing: {inicio:%m/%Y} ({usado})", "",
          f"- Cliques: {sum(x[1] for x in consultas)}", f"- Impressões: {sum(x[2] for x in consultas)}", "",
          "## Buscas", *top(consultas), "", "## Páginas", *top(paginas)]
(pasta / "bing.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("\n".join(linhas))
