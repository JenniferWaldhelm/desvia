#!/usr/bin/env python3
"""Procura o site das empresas da revisão pelo domínio do e-mail cadastrado na Receita (sugestão da Jen
em 18/11/2026: empresa com site é sinal de que funciona). Só conta se o site responde.
Uso: RECEITA_PR=/tmp/receita-pr python3 coleta/sites.py
Saída: coleta/sites-revisao.csv (CNPJ, Site)."""
import csv
import glob
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preparar as P  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
cnpjs = set()
for arq in glob.glob(str(RAIZ / "coleta" / "*revisao*.csv")) + [str(RAIZ / "dados" / "pontos.csv")]:
    for r in csv.DictReader(open(arq, encoding="utf-8")):
        d = re.sub(r"\D", "", r.get("CNPJ", ""))
        if len(d) == 14:
            cnpjs.add(d)
doms = P.sites_da_receita()
alvo = {c: doms[c] for c in cnpjs if c in doms}
with ThreadPoolExecutor(max_workers=12) as ex:
    res = dict(zip(alvo, ex.map(P.site_no_ar, alvo.values())))
with open(RAIZ / "coleta" / "sites-revisao.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["CNPJ", "Site"])
    for c, s in sorted(res.items()):
        if s:
            w.writerow([f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}", s])
print(f"CNPJs: {len(cnpjs)}; com e-mail de domínio próprio: {len(alvo)}; site no ar: {sum(1 for s in res.values() if s)}")
