#!/usr/bin/env python3
"""Converte endereços em coordenadas (OpenStreetMap/Nominatim).

Entrada: coleta/geocodificar.csv (ID, Endereço, Município)
Saída:   coleta/geocodificado.csv (ID, Lat, Lng, Precisão, Achado)
Precisão: "número" (achou o endereço), "rua" (só a rua) ou "não achado".
"""
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = "Desvia/1.0 (https://jenniferwaldhelm.github.io/desvia)"


def busca(q):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "countrycodes": "br"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"})
    time.sleep(1.2)  # regra de uso: no máximo 1 consulta por segundo
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return d[0] if d else None


def main():
    saida = []
    for l in csv.DictReader(open(RAIZ / "coleta" / "geocodificar.csv", encoding="utf-8")):
        cidade = f"{l['Município']}, Paraná, Brasil"
        end = re.sub(r"^Av\.", "Avenida", l["Endereço"].strip())
        end = re.sub(r"^Rod\.", "Rodovia", end)
        r, prec = busca(f"{end}, {cidade}"), "número"
        if not r:  # tenta só a rua
            rua = end.split(",")[0]
            r, prec = busca(f"{rua}, {cidade}"), "rua"
        if r and l["Município"].lower() not in r.get("display_name", "").lower():
            r = None  # caiu em outra cidade
        saida.append({"ID": l["ID"], "Lat": f"{float(r['lat']):.5f}" if r else "",
                      "Lng": f"{float(r['lon']):.5f}" if r else "",
                      "Precisão": prec if r else "não achado",
                      "Achado": r["display_name"][:120] if r else ""})
        print(saida[-1]["ID"], saida[-1]["Precisão"])
    with open(RAIZ / "coleta" / "geocodificado.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ID", "Lat", "Lng", "Precisão", "Achado"])
        w.writeheader()
        w.writerows(saida)


if __name__ == "__main__":
    main()
