#!/usr/bin/env python3
"""Baixa do GoatCounter as visitas e buscas do mês anterior (ou do mês passado como argumento AAAA-MM)
e grava metricas/AAAA-MM/goatcounter.csv (caminho, título, evento, contagem) e um resumo .md.
Precisa do segredo GOATCOUNTER_TOKEN (permissão "Read statistics")."""
import csv
import json
import os
import sys
import urllib.parse
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

SITE = "https://projetodesvia.goatcounter.com"
TOKEN = os.environ.get("GOATCOUNTER_TOKEN", "")
if not TOKEN:
    sys.exit("Falta o segredo GOATCOUNTER_TOKEN.")

if len(sys.argv) > 1:
    ano, mes = map(int, sys.argv[1].split("-"))
    inicio = date(ano, mes, 1)
else:
    inicio = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def api(caminho, tolera_404=False, **params):
    url = f"{SITE}/api/v0/{caminho}?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404 and tolera_404:
            return {}
        sys.exit(f"GoatCounter respondeu {e.code} em {caminho}: {e.read()[:300]!r}")


# O GoatCounter às vezes devolve 404 quando o último dia ainda não foi processado: recua até 3 dias
ate = min(fim, date.today())
for _ in range(4):
    if api("stats/hits", tolera_404=True, start=f"{inicio}", end=f"{ate}", limit=1):
        break
    ate -= timedelta(days=1)
else:
    sys.exit("GoatCounter sem dados para o período (404). Nada foi alterado.")

hits, excluir = [], []
while True:
    # a API devolve 404 quando a página seguinte não existe: fim da lista
    d = api("stats/hits", tolera_404=bool(excluir), start=f"{inicio}", end=f"{ate}", limit=100, exclude_paths=excluir)
    for h in d.get("hits", []):
        hits.append(h)
        excluir.append(h.get("path_id"))
    if not d.get("more"):
        break

pasta = Path(__file__).resolve().parent / f"{inicio:%Y-%m}"
pasta.mkdir(parents=True, exist_ok=True)
with open(pasta / "goatcounter.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["caminho", "titulo", "evento", "contagem"])
    for h in sorted(hits, key=lambda h: -h.get("count", 0)):
        w.writerow([h.get("path"), h.get("title"), h.get("event"), h.get("count")])

pag = [h for h in hits if not h.get("event")]
sem = [h for h in hits if str(h.get("path", "")).startswith("busca-sem-resultado/")]
com = [h for h in hits if str(h.get("path", "")).startswith("busca/")]
ass = [h for h in hits if str(h.get("path", "")).startswith("assistente/")]
top = lambda lst, n=15: [f"- {h['path']}: {h['count']}" for h in sorted(lst, key=lambda h: -h["count"])[:n]]
linhas = [f"# Métricas do Desvia: {inicio:%m/%Y}", "",
          f"- Visitas (páginas vistas): {sum(h['count'] for h in pag)}",
          f"- Buscas com resultado: {sum(h['count'] for h in com)}",
          f"- Buscas sem resultado: {sum(h['count'] for h in sem)}", "",
          "## Páginas mais vistas", *top(pag), "",
          "## Buscas sem resultado (o que falta na base)", *top(sem, 30), "",
          "## Buscas mais feitas", *top(com), "",
          "## Escolhas no assistente", *top(ass)]
(pasta / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("\n".join(linhas))
