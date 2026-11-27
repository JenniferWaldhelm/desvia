#!/usr/bin/env python3
"""Conferência mensal da base (só avisa, não muda nada). Roda no dia 22, depois do arquivo da Receita (dia 20).
1. Receita: CNPJs da base que deixaram de estar ativos (baixada, inapta, suspensa) no arquivo mensal do PR.
2. IAT: licenças vencidas ou a vencer em 60 dias na base para as quais o IAT já mostra uma licença mais nova.
Saída: coleta/conferencia-mensal.md (a tarefa semanal leva o resumo para a Jen na 1ª segunda do mês)."""
import csv, gzip, re, sys, unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coleta"))
from buscar_cidade import buscar_iat_por_cnpj, data_iat   # noqa: E402

norm = lambda t: "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()
dig = lambda t: re.sub(r"\D", "", t or "")
HOJE = date.today()


def dt(s):
    try:
        return datetime.strptime((s or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


pts = [p for p in csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8"))
       if p["ID"].strip() and norm(p.get("Situação") or "ativo") in ("ativo", "") and len(dig(p["CNPJ"])) == 14]
linhas = [f"# Conferência mensal ({HOJE:%d/%m/%Y})", ""]

# 1. Receita
arq = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/receita-pr/receita-pr.csv.gz")
sit = {}
if arq.exists():
    with gzip.open(arq, "rt", encoding="utf-8", newline="") as f:
        for a in csv.DictReader(f):
            sit[a["cnpj"]] = a["situacao"]
    nao = [(p, sit[dig(p["CNPJ"])]) for p in pts if sit.get(dig(p["CNPJ"]), "Ativa") != "Ativa"]
    linhas += [f"## CNPJ que não está mais ativo na Receita: {len(nao)}", "",
               "Sugestão: marcar 'fechado' na coluna Situação (ou manter com o aviso de CNPJ, se ainda funciona).", ""]
    linhas += [f"- {p['ID']} {p['Nome']} ({p['Município sede']}): {s}" for p, s in nao] + [""]
else:
    linhas += ["## Receita: arquivo do mês não encontrado (conferência pulada)", ""]

# 2. IAT: renovação de licenças vencidas ou a vencer
alvo = [p for p in pts if (dt(p["Validade licença"]) or date(1900, 1, 1)) < HOJE + timedelta(days=60)]
_, achadas = buscar_iat_por_cnpj([dig(p["CNPJ"]) for p in alvo])
novas = []
for p in alvo:
    lic = (achadas.get(dig(p["CNPJ"])) or {}).get("lic")
    if not lic or not lic.get("dt_validade"):
        continue
    val = data_iat(lic["dt_validade"])
    if (dt(val) or date(1900, 1, 1)) > (dt(p["Validade licença"]) or date(1900, 1, 1)):
        novas.append(f"- {p['ID']} {p['Nome']} ({p['Município sede']}): planilha {p['Tipo licença']} {p['Nº licença']} até {p['Validade licença'] or '—'} → IAT {lic.get('sigla_modalidade') or ''} {lic.get('num_documento') or ''} até {val}")
linhas += [f"## Licença mais nova no IAT: {len(novas)} (de {len(alvo)} vencidas ou a vencer em 60 dias)", "",
           "Sugestão: atualizar Tipo, Nº e Validade da licença na aba Pontos.", ""] + novas + [""]
(RAIZ / "coleta" / "conferencia-mensal.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("\n".join(l for l in linhas if l.startswith("#")))
