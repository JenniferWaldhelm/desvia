#!/usr/bin/env python3
"""Baixa do GoatCounter as buscas SEM resultado dos últimos 7 dias e acrescenta em
metricas/buscas-sem-resultado.csv (semana, termo, cidade, contagem). A revisão semanal lê daqui
e propõe sinônimos para a Jen aprovar. Precisa do segredo GOATCOUNTER_TOKEN."""
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

SITE = "https://projetodesvia.goatcounter.com"
TOKEN = os.environ.get("GOATCOUNTER_TOKEN", "") or sys.exit("Falta o segredo GOATCOUNTER_TOKEN.")
fim = date.today() - timedelta(days=1)
inicio = fim - timedelta(days=6)


def api(caminho, **params):
    url = f"{SITE}/api/v0/{caminho}?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        sys.exit(f"GoatCounter respondeu {e.code}: {e.read()[:300]!r}")


hits, excluir = [], []
while True:
    d = api("stats/hits", start=f"{inicio}", end=f"{fim}", limit=100, exclude_paths=excluir)
    for h in d.get("hits", []):
        hits.append(h)
        excluir.append(h.get("path_id"))
    if not d.get("more"):
        break

arq = Path(__file__).resolve().parent / "buscas-sem-resultado.csv"
semana = f"{inicio:%d/%m/%Y}-{fim:%d/%m/%Y}"
ja = set()
if arq.exists():
    with open(arq, encoding="utf-8") as f:
        ja = {r["semana"] for r in csv.DictReader(f)}
novas = []
for h in hits:
    partes = str(h.get("path", "")).split("/", 2)  # busca-sem-resultado/<cidade>/<termo>
    if partes[0] == "busca-sem-resultado" and len(partes) == 3:
        novas.append([semana, urllib.parse.unquote(partes[2]).replace("-", " "), partes[1], h.get("count", 0)])
if semana in ja:
    sys.exit(f"Semana {semana} já registrada.")
novo = not arq.exists()
with open(arq, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if novo:
        w.writerow(["semana", "termo", "cidade", "contagem"])
    for r in sorted(novas, key=lambda r: -r[3]):
        w.writerow(r)
print(f"Semana {semana}: {len(novas)} buscas sem resultado.")
for r in sorted(novas, key=lambda r: -r[3])[:30]:
    print(f"- {r[1]} ({r[2]}): {r[3]}")
