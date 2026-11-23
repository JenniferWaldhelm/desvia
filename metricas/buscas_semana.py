#!/usr/bin/env python3
"""Baixa do GoatCounter os últimos 7 dias e acrescenta em metricas/: buscas.csv (tudo o que foi
buscado, por cidade), paginas-residuo.csv (visitas a cada página de resíduo) e
buscas-sem-resultado.csv (semana, termo, cidade, contagem). A revisão semanal lê daqui
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
            print(f"GoatCounter 404 em {caminho}: {e.read()[:200]!r}")
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

print(f"GoatCounter: {len(hits)} caminhos no período; exemplos: {[h.get('path') for h in hits[:8]]}")
PASTA = Path(__file__).resolve().parent
semana = f"{inicio:%d/%m/%Y}-{fim:%d/%m/%Y}"


def ja_tem(arq):
    if not arq.exists():
        return False
    with open(arq, encoding="utf-8") as f:
        return any(r["semana"] == semana for r in csv.DictReader(f))


def gravar(arq, cab, linhas):
    if ja_tem(arq):
        print(f"{arq.name}: semana {semana} já registrada.")
        return
    novo = not arq.exists()
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(cab)
        for r in sorted(linhas, key=lambda r: -r[-1]):
            w.writerow(r)


sem, todas, paginas = [], [], []
for h in hits:
    caminho = str(h.get("path", "")).strip("/")
    partes = caminho.split("/", 2)
    n = h.get("count", 0)
    if partes[0] in ("busca", "busca-sem-resultado") and len(partes) == 3:
        termo = urllib.parse.unquote(partes[2]).replace("-", " ")
        achou = "sim" if partes[0] == "busca" else "não"
        todas.append([semana, partes[1], termo, achou, n])
        if achou == "não":
            sem.append([semana, termo, partes[1], n])
    elif partes[0] == "residuos" and len(partes) == 3 and partes[2]:
        paginas.append([semana, partes[1], partes[2].strip("/"), n])

# buscas-sem-resultado.csv continua igual (a revisão semanal de sinônimos lê daqui)
gravar(PASTA / "buscas-sem-resultado.csv", ["semana", "termo", "cidade", "contagem"], sem)
gravar(PASTA / "buscas.csv", ["semana", "cidade", "termo", "achou", "contagem"], todas)
gravar(PASTA / "paginas-residuo.csv", ["semana", "cidade", "residuo", "visitas"], paginas)
print(f"Semana {semana}: {len(todas)} termos buscados ({len(sem)} sem resultado), {len(paginas)} páginas de resíduo visitadas.")
for r in sorted(sem, key=lambda r: -r[3])[:30]:
    print(f"- sem resultado: {r[1]} ({r[2]}): {r[3]}")
