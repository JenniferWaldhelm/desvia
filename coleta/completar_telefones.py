#!/usr/bin/env python3
"""Sugere telefone para os pontos da base que estão sem (pedido da Jen em 18/11/2026: o telefone ajuda
a pessoa a ligar e confirmar se o local recebe). Fonte: arquivo mensal da Receita (release receita-pr).
  - ponto com CNPJ: telefone do estabelecimento na Receita;
  - ponto sem CNPJ: empresa ativa da mesma cidade, mesmo número e mesma rua (ou CEP), com o nome batendo.
Uso: RECEITA_PR=/tmp/receita-pr python3 coleta/completar_telefones.py
Saída: coleta/telefones-sugeridos.csv (para a Jen conferir antes de gravar). Não altera a planilha."""
import csv
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preparar_localizadores as PL  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def main():
    base = [p for p in csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")) if p["ID"] and not p["Telefone"].strip()]
    cidades = sorted({p["Município sede"] for p in base if p["Município sede"]})
    receita = PL.ler_receita(os.environ.get("RECEITA_PR"), cidades)
    if not receita:
        sys.exit("Sem o arquivo mensal da Receita (RECEITA_PR).")
    por_cnpj = {a["cnpj"]: a for lst in receita.values() for a in lst}
    out = []
    for p in base:
        cnpj = re.sub(r"\D", "", p["CNPJ"])
        a, como = None, ""
        if cnpj and cnpj in por_cnpj:
            a, como = por_cnpj[cnpj], "CNPJ do ponto"
        elif not cnpj and p["Endereço"]:
            c = PL.achar_cnpj({"Nome": p["Nome"], "Endereço": p["Endereço"], "CEP": ""}, receita.get(PL.n(p["Município sede"]), []))
            if c:
                a, como = por_cnpj.get(c), "empresa no mesmo endereço com o mesmo nome"
        if a and a.get("telefone"):
            out.append({"ID": p["ID"], "Nome": p["Nome"], "Cidade": p["Município sede"], "Endereço": p["Endereço"],
                        "Telefone sugerido": a["telefone"], "Como achou": como, "CNPJ": a["cnpj"], "Usar?": ""})
    with open(RAIZ / "coleta" / "telefones-sugeridos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Usar?", "ID", "Nome", "Cidade", "Endereço", "Telefone sugerido", "Como achou", "CNPJ"])
        w.writeheader()
        w.writerows(out)
    print(f"Pontos sem telefone: {len(base)}. Telefone sugerido para {len(out)}.")


if __name__ == "__main__":
    main()
