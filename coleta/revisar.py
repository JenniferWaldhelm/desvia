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

# Regras aprovadas pela Jen (02/11/2026), aplicadas no site por dados/ajustes.csv (a planilha não é alterada):
# - CNPJ baixado: sai do site.  - CNPJ inapto/suspenso: aviso; após 6 meses seguidos, sai.
# - Licença renovada no IAT: o site passa a mostrar a licença nova.
ARQ_SIT = RAIZ / "dados" / "situacao_cnpj.csv"
sit_ant = {r["ID"]: r for r in csv.DictReader(open(ARQ_SIT, encoding="utf-8"))} if ARQ_SIT.exists() else {}
sit_nova, ajustes = {}, []
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
        if sit and sit not in ("ativa", "não consultada"):
            desde = sit_ant.get(b["ID"], {}).get("Desde") if sit_ant.get(b["ID"], {}).get("Situação") == sit else None
            desde = desde or f"{hoje:%d/%m/%Y}"
            sit_nova[b["ID"]] = {"ID": b["ID"], "Situação": sit, "Desde": desde}
            dias = (hoje - data(desde)).days
            if "baixad" in sit:
                ajustes.append({"ID": b["ID"], "Campo": "ocultar", "Valor": "sim", "Motivo": f"CNPJ baixado na Receita (desde {desde})"})
                inativos.append(f"{nome}: CNPJ baixado, saiu do site")
            else:
                ajustes.append({"ID": b["ID"], "Campo": "aviso_cnpj", "Valor": f"CNPJ {sit} na Receita (consulta em {hoje:%d/%m/%Y})", "Motivo": "Receita"})
                if dias >= 180:
                    ajustes.append({"ID": b["ID"], "Campo": "ocultar", "Valor": "sim", "Motivo": f"CNPJ {sit} desde {desde} (mais de 6 meses)"})
                    inativos.append(f"{nome}: CNPJ {sit} desde {desde}, saiu do site (mais de 6 meses)")
                else:
                    inativos.append(f"{nome}: CNPJ {sit} desde {desde} (aviso no site; sai se continuar até {date.fromordinal(data(desde).toordinal() + 180):%d/%m/%Y})")
        vb, vc = data(b["Validade licença"]), data(c["Validade licença"])
        # LP/LI nova não substitui uma LO que a base já tem (ex.: ampliação com LI)
        lo_base = (b.get("Tipo licença") or "").upper().startswith(("LO", "RLO", "LAS", "LAU"))
        so_lp_li = (c.get("Tipo licença") or "").upper() in ("LP", "LI")
        if vc and (not vb or (vc - vb).days > 2) and not (lo_base and so_lp_li):  # IAT grava em UTC: ignora diferença de 1 dia
            for campo in ("Órgão licença", "Tipo licença", "Nº licença", "Validade licença"):
                if c.get(campo):
                    ajustes.append({"ID": b["ID"], "Campo": campo, "Valor": c[campo], "Motivo": "Renovação localizada no IAT"})
            renovadas.append(f"{nome}: {c['Tipo licença']} {c['Nº licença']} válida até {c['Validade licença']} (na base: {b['Validade licença'] or 'sem licença'}). Já aparece no site; copie para a planilha.")
        elif vb and 0 <= (hoje - vb).days <= 45:  # venceu desde a última revisão
            vencidas.append(f"{nome}: venceu em {b['Validade licença']} e não há renovação no IAT")
    n = len(inativos) + len(renovadas) + len(vencidas) + len(novas)
    total += n
    linhas += [f"## {cidade} ({n} mudanças)", ""]
    for titulo, lst in (("CNPJ deixou de estar ativo", inativos), ("Licença nova ou renovada no IAT", renovadas),
                        ("Licença vencida sem renovação", vencidas), ("Empresas novas (ativas) fora da base", novas)):
        if lst:
            linhas += [f"**{titulo}**", ""] + [f"- {x}" for x in lst] + [""]
# pontos sem CNPJ (farmácias, PEVs, brechós) verificados há mais de 12 meses
antigos = []
for r in csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")):
    dv = data(r.get("Data verificação", ""))
    if not dig(r["CNPJ"]) and dv and (hoje - dv).days > 365:
        antigos.append(f"{r['ID']} {r['Nome']} ({r['Município sede']}), verificado em {r['Data verificação']}")
if antigos:
    total += len(antigos)
    linhas += ["## Pontos sem CNPJ verificados há mais de 12 meses (reconferir)", ""] + [f"- {x}" for x in antigos] + [""]

with open(ARQ_SIT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["ID", "Situação", "Desde"]); w.writeheader(); w.writerows(sit_nova.values())
with open(RAIZ / "dados" / "ajustes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["ID", "Campo", "Valor", "Motivo"]); w.writeheader(); w.writerows(ajustes)

linhas.insert(2, f"Total de mudanças para revisar: **{total}**\n")
saida = RAIZ / "coleta" / f"revisao-{hoje:%Y-%m}.md"
saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("\n".join(linhas))
