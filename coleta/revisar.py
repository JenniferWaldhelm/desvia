#!/usr/bin/env python3
"""Revisão mensal: compara a coleta automática de cada cidade publicada com a base do site.

Lê coleta/<cidade>.csv (gerado por buscar_cidade.py) e dados/pontos.csv e grava
coleta/revisao-AAAA-MM.md com: CNPJs que deixaram de estar ativos, licenças do IAT
renovadas ou vencidas desde a última conferência e empresas novas.
"""
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "gerador"))
from gerar import CIDADES  # noqa: E402

dig = lambda s: re.sub(r"\D", "", s or "")


def data(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


base = {}
for r in csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")):
    if dig(r["CNPJ"]):
        base.setdefault(dig(r["CNPJ"]), r)

hoje = date.today()
linhas = [f"# Revisão mensal: {hoje:%m/%Y}", ""]
total = 0
for slug, cidade in CIDADES.items():
    arq = RAIZ / "coleta" / f"{slug}.csv"
    if not arq.exists():
        linhas += [f"## {cidade}", "", "- Sem coleta neste mês.", ""]
        continue
    inativos, renovadas, vencidas, novas = [], [], [], []
    for c in csv.DictReader(open(arq, encoding="utf-8")):
        b = base.get(dig(c["CNPJ"]))
        sit = (c.get("Situação CNPJ") or "").lower()
        if not b:
            if sit == "ativa":
                novas.append(f"{c['Nome']} ({c['CNPJ']}): {c['Resíduos aceitos'][:80]}")
            continue
        nome = f"{b['ID']} {b['Nome']}"
        if sit and sit not in ("ativa", "não consultada") and "inapt" not in b["Obs"].lower() and "baixad" not in b["Obs"].lower():
            inativos.append(f"{nome}: CNPJ {sit} na Receita")
        vb, vc = data(b["Validade licença"]), data(c["Validade licença"])
        if vc and (not vb or (vc - vb).days > 2):  # IAT grava em UTC: ignora diferença de 1 dia
            renovadas.append(f"{nome}: {c['Tipo licença']} {c['Nº licença']} válida até {c['Validade licença']} (na base: {b['Validade licença'] or 'sem licença'})")
        elif vb and 0 <= (hoje - vb).days <= 45:  # venceu desde a última revisão
            vencidas.append(f"{nome}: venceu em {b['Validade licença']} e não há renovação no IAT")
    n = len(inativos) + len(renovadas) + len(vencidas) + len(novas)
    total += n
    linhas += [f"## {cidade} ({n} mudanças)", ""]
    for titulo, lst in (("CNPJ deixou de estar ativo", inativos), ("Licença nova ou renovada no IAT", renovadas),
                        ("Licença vencida sem renovação", vencidas), ("Empresas novas (ativas) fora da base", novas)):
        if lst:
            linhas += [f"**{titulo}**", ""] + [f"- {x}" for x in lst] + [""]
linhas.insert(2, f"Total de mudanças para revisar: **{total}**\n")
saida = RAIZ / "coleta" / f"revisao-{hoje:%Y-%m}.md"
saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("\n".join(linhas))
