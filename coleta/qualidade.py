#!/usr/bin/env python3
"""Checagem semanal da base (roda antes de gerar o site).

1. Coordenadas: pontos com endereço e sem Lat/Lng são procurados no OpenStreetMap (até 60 por semana).
   O que achar vai para dados/coordenadas.csv e o site já usa no mapa; a planilha não é alterada.
2. Duplicados: mesmo CNPJ em duas linhas, ou nomes parecidos a menos de 50 m.
Gera coleta/qualidade.md com o que precisa de decisão da Jen.
"""
import csv
import difflib
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Desvia/1.0 (https://desvia.eco.br/)", "Accept-Language": "pt-BR"}
import os
LIMITE = int(os.environ.get("GEO_LIMITE", "60"))


def norm(t):
    t = unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\b(ltda|me|epp|eireli|s/?a|de|da|do|e)\b", " ", t)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


pontos = [p for p in csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")) if (p.get("ID") or "").strip()]
arq_cache = RAIZ / "dados" / "coordenadas.csv"
cache = {r["ID"]: r for r in csv.DictReader(open(arq_cache, encoding="utf-8"))} if arq_cache.exists() else {}

# 1. coordenadas
achados, nao_achados, feitos = [], [], 0
for p in pontos:
    if num(p["Lat"]) is not None or not p["Endereço"].strip() or p["Tipo de ponto"] == "Programa logística reversa" or "www." in p["Endereço"] or "site" in p["Endereço"].lower():
        continue
    c = cache.get(p["ID"])
    if c and c.get("Endereço usado") == p["Endereço"]:
        if not c.get("Lat"):
            nao_achados.append(p)
        continue
    if feitos >= LIMITE:
        continue
    feitos += 1
    end = re.sub(r"\(.*?\)", "", p["Endereço"]).replace("Av.", "Avenida").replace("R.", "Rua").strip(" ,")
    r = None
    for q in (f"{end}, {p['Município sede']}, Paraná, Brasil", f"{end.split(',')[0]}, {p['Município sede']}, Paraná, Brasil"):
        time.sleep(1.2)
        try:
            url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1, "countrycodes": "br"})
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as resp:
                d = json.load(resp)
        except Exception:  # noqa: BLE001
            d = []
        if d and norm(p["Município sede"]) in norm(d[0].get("display_name", "")):
            r = d[0]
            break
    cache[p["ID"]] = {"ID": p["ID"], "Lat": f"{float(r['lat']):.5f}" if r else "", "Lng": f"{float(r['lon']):.5f}" if r else "",
                      "Endereço usado": p["Endereço"], "Achado": (r or {}).get("display_name", "")[:120]}
    (achados if r else nao_achados).append(p)

with open(arq_cache, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["ID", "Lat", "Lng", "Endereço usado", "Achado"])
    w.writeheader()
    w.writerows(sorted(cache.values(), key=lambda r: r["ID"]))

# 2. duplicados
dups = []
por_cnpj = {}
for p in pontos:
    d = re.sub(r"\D", "", p["CNPJ"])
    if d:
        por_cnpj.setdefault(d, []).append(p["ID"])
dups += [f"Mesmo CNPJ: {', '.join(ids)}" for ids in por_cnpj.values() if len(ids) > 1]
coords = []
for p in pontos:
    la, lo = num(p["Lat"]), num(p["Lng"])
    if la is None and p["ID"] in cache and cache[p["ID"]].get("Lat"):
        la, lo = float(cache[p["ID"]]["Lat"]), float(cache[p["ID"]]["Lng"])
    if la is not None:
        coords.append((p, la, lo, norm(p["Nome"])))
for i in range(len(coords)):
    p, la, lo, n1 = coords[i]
    for q, la2, lo2, n2 in coords[i + 1:]:
        if abs(la - la2) > 0.001 or abs(lo - lo2) > 0.001:
            continue
        dist = 6371000 * math.hypot(math.radians(la2 - la), math.radians(lo2 - lo) * math.cos(math.radians(la)))
        if dist < 50 and difflib.SequenceMatcher(None, n1, n2).ratio() >= 0.8:
            dups.append(f"Nome parecido a {dist:.0f} m: {p['ID']} {p['Nome']} / {q['ID']} {q['Nome']}")

linhas = ["# Qualidade da base", "",
          f"- Coordenadas achadas nesta rodada: {len(achados)} (já aparecem no mapa)",
          f"- Endereços que o OpenStreetMap não achou: {len(nao_achados)}",
          f"- Possíveis duplicados: {len(dups)}", ""]
if achados:
    linhas += ["## Coordenadas achadas (conferir e, se quiser, copiar para a planilha)", ""]
    linhas += [f"- {p['ID']} {p['Nome']}: {cache[p['ID']]['Lat']}, {cache[p['ID']]['Lng']}" for p in achados] + [""]
if nao_achados:
    linhas += ["## Sem coordenada (pegar no Google Maps)", ""] + [f"- {p['ID']} {p['Nome']} ({p['Endereço']}, {p['Município sede']})" for p in nao_achados] + [""]
if dups:
    linhas += ["## Possíveis duplicados (decidir qual fica)", ""] + [f"- {d}" for d in dups] + [""]
(RAIZ / "coleta" / "qualidade.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("\n".join(linhas[:5]))
