#!/usr/bin/env python3
"""Gera metricas/resumo-por-cidade.md: o que as pessoas procuram em cada município nas últimas
4 semanas registradas (buscas na barra + visitas às páginas de resíduo). Serve para a análise
mensal e para enviar às prefeituras."""
import csv
from collections import Counter, defaultdict
from pathlib import Path

PASTA = Path(__file__).resolve().parent


def ler(nome):
    arq = PASTA / nome
    if not arq.exists():
        return []
    with open(arq, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ultimas(linhas, n=4):
    sems = sorted({r["semana"] for r in linhas}, key=lambda s: s.split("-")[1][6:] + s.split("-")[1][3:5] + s.split("-")[1][:2])
    return set(sems[-n:]), sems[-n:]


buscas, paginas = ler("buscas.csv"), ler("paginas-residuo.csv")
s1, lista = ultimas(buscas + paginas)
termo, sem, pag = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
for r in buscas:
    if r["semana"] in s1:
        termo[r["cidade"]][r["termo"]] += int(r["contagem"])
        if r["achou"] == "não":
            sem[r["cidade"]][r["termo"]] += int(r["contagem"])
for r in paginas:
    if r["semana"] in s1:
        pag[r["cidade"]][r["residuo"].replace("-", " ")] += int(r["visitas"])

periodo = f"{lista[0].split('-')[0]} a {lista[-1].split('-')[1]}" if lista else "sem dados ainda"
out = [f"# O que as pessoas procuram em cada município", "", f"Período: {periodo}. Fonte: contador de visitas do Desvia (GoatCounter), sem dados pessoais.", ""]
cidades = sorted(set(termo) | set(pag), key=lambda c: -(sum(termo[c].values()) + sum(pag[c].values())))
for c in cidades:
    if c == "todas":
        nome = "Busca geral (sem cidade escolhida)"
    else:
        nome = c.replace("-", " ").title()
    out += [f"## {nome}", ""]
    if pag[c]:
        out.append("Páginas de resíduo mais visitadas: " + "; ".join(f"{k} ({v})" for k, v in pag[c].most_common(8)) + ".")
    if termo[c]:
        out.append("Mais buscados: " + "; ".join(f"{k} ({v})" for k, v in termo[c].most_common(10)) + ".")
    if sem[c]:
        out.append("Procurados sem resultado: " + "; ".join(f"{k} ({v})" for k, v in sem[c].most_common(10)) + ".")
    out.append("")
(PASTA / "resumo-por-cidade.md").write_text("\n".join(out), encoding="utf-8")
print(f"Resumo de {len(cidades)} cidades ({periodo}).")
