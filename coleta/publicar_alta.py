#!/usr/bin/env python3
"""Seleciona da aba Revisão as empresas de confiança Alta ainda sem decisão da Jen e prepara para a aba Pontos.
Entrada: revisao.csv (aba Revisão) e dados/pontos.csv. Saída: coleta/alta-publicar.csv (colunas da aba Pontos,
IDs finais) e coleta/alta-fora.csv (o que ficou de fora e por quê). Decisão da Jen (26/11): publicar as Alta com o
aviso "a empresa ainda não confirmou" e o link de correção; Média continuam na Revisão."""
import csv, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
rev = list(csv.reader(open(sys.argv[1], encoding="utf-8")))
cab, linhas = rev[0], rev[1:]
pontos = list(csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")))
COLS = list(pontos[0].keys())[:22]


def norm(t):
    return re.sub(r"\s+", " ", "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()).strip()


dig = lambda t: re.sub(r"\D", "", t or "")
ja_cnpj = {dig(p["CNPJ"]) for p in pontos if dig(p["CNPJ"])}
recus = {dig(l.split(",")[0]) for l in open(RAIZ / "coleta" / "recusados.csv", encoding="utf-8") if dig(l.split(",")[0])}
maxid = {}
for p in pontos:
    m = re.match(r"([A-Z]{3})-(\d+)", p["ID"])
    if m:
        maxid[m.group(1)] = max(maxid.get(m.group(1), 0), int(m.group(2)))

FORA_NOME = r"pizzar|restaurant|lanchonet|padaria|panific|bar e |hotel|academia|salao|escola|igreja|farmacia|drogaria|clinica|odonto|imobiliar|contabil|advocacia|consultoria"
publicar, fora, vistos = [], [], set()
for l in linhas:
    l += [""] * (len(cab) - len(l))
    conf, porque, func, receb = l[0].strip(), l[1], l[2].strip(), l[3].strip()
    if conf != "Alta":
        continue
    p = dict(zip(COLS, l[5:27]))
    c = dig(p["CNPJ"])
    motivo = ""
    if func or receb:
        motivo = "já decidido pela Jen"
    elif c and c in ja_cnpj:
        motivo = "já está na aba Pontos"
    elif c and c in recus:
        motivo = "recusado antes"
    elif c and c in vistos:
        motivo = "repetido na Revisão"
    elif "so lp/li" in norm(porque):
        motivo = "só licença prévia/instalação: ainda não pode funcionar"
    elif re.search(FORA_NOME, norm(p["Nome"])):
        motivo = "nome fora do tema"
    if motivo:
        fora.append([p["ID"], p["Nome"], p["Município sede"], motivo])
        continue
    vistos.add(c)
    pre = p["ID"][:3]
    maxid[pre] = maxid.get(pre, 0) + 1
    p["ID"] = f"{pre}-{maxid[pre]:03d}"
    p["Status licença (auto)"] = ""          # coluna Q é fórmula na planilha: nunca escrever
    p["Data verificação"] = p["Data verificação"] or "26/11/2026"
    publicar.append(p)

with open(RAIZ / "coleta" / "alta-publicar.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(publicar)
with open(RAIZ / "coleta" / "alta-fora.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["ID provisório", "Nome", "Município", "Motivo"]); w.writerows(fora)
from collections import Counter
print(f"Publicar: {len(publicar)}", dict(Counter(p['Município sede'] for p in publicar)))
print(f"Fora: {len(fora)}", dict(Counter(x[3] for x in fora)))
