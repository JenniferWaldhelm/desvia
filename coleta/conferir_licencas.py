#!/usr/bin/env python3
"""Confere se as empresas achadas na Receita (coleta/<cidade>-receita.csv) têm
licença no IAT (SGA/GeoPR, qualquer município) ou inscrição de resíduos no CTF/IBAMA.

Uso: python3 coleta/conferir_licencas.py "Sarandi"
Acrescenta ao CSV as colunas IAT licença, IAT validade, IAT atividades e CTF/IBAMA,
e atualiza o resumo. Não altera o site nem a planilha.
"""
import csv
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buscar_cidade as bc  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def main():
    cidade = sys.argv[1]
    slug = re.sub(r"[^a-z0-9]+", "-", bc.norm(cidade).lower()).strip("-")
    arq = RAIZ / "coleta" / f"{slug}-receita.csv"
    linhas = list(csv.DictReader(open(arq, encoding="utf-8")))
    cnpjs = [bc.so_digitos(l["CNPJ"]) for l in linhas]

    n, iat = bc.buscar_iat_por_cnpj(cnpjs)
    try:
        ctf = bc.buscar_ctf(cidade)
    except Exception as e:  # noqa: BLE001
        print(f"CTF indisponível: {e}", file=sys.stderr)
        ctf = {}

    hoje = date.today()
    for l, c in zip(linhas, cnpjs):
        i = iat.get(c)
        lic = (i or {}).get("lic") or {}
        tipo = lic.get("sigla_modalidade") or ""
        num = str(lic.get("num_documento") or "")
        val = bc.data_iat(lic.get("dt_validade"))
        l["IAT licença"] = f"{tipo} {num}".strip()
        l["IAT validade"] = val
        l["IAT atividades"] = "; ".join(sorted(a for a in (i or {}).get("atividades", set()) if a))[:200]
        l["CTF/IBAMA"] = "Sim" if c in ctf else ""

    campos = list(linhas[0].keys())
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    novas = [l for l in linhas if not l.get("Já na base")]
    com_iat = [l for l in novas if l["IAT licença"]]
    so_aa = [l for l in com_iat if l["IAT licença"].split()[0] in ("AA",)]
    venc = [l for l in com_iat if l["IAT validade"] and
            date(*map(int, reversed(l["IAT validade"].split("/")))) < hoje]
    com_ctf = [l for l in novas if l["CTF/IBAMA"]]
    texto = [
        "",
        f"## Licenças (conferido em {hoje:%d/%m/%Y})",
        "",
        f"- IAT por CNPJ: {len(cnpjs)} consultados, {n} registros de licença",
        f"- Novas com licença no IAT: {len(com_iat)} (só AA: {len(so_aa)}; vencidas: {len(venc)})",
        f"- Novas com inscrição de resíduos no CTF/IBAMA: {len(com_ctf)}",
        f"- Novas sem licença nem CTF: {sum(1 for l in novas if not l['IAT licença'] and not l['CTF/IBAMA'])}",
        "",
        "Com licença no IAT:",
    ] + [f"- {l['Razão social'] or l['Nome fantasia']} ({l['CNPJ']}): {l['IAT licença']} até {l['IAT validade'] or '?'}"
         for l in com_iat]
    resumo = RAIZ / "coleta" / f"{slug}-receita-resumo.md"
    corpo = resumo.read_text(encoding="utf-8").split("\n## Licenças")[0].rstrip("\n")
    resumo.write_text(corpo + "\n" + "\n".join(texto) + "\n", encoding="utf-8")
    print("\n".join(texto))
    print("\n".join(bc.IAT_DIAG + bc.DIAG), file=sys.stderr)


if __name__ == "__main__":
    main()
