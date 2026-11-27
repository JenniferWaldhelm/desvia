"""Busca empresas pelo nome no IAT (licenças) e confere o CNPJ no arquivo mensal da Receita.
Serve para empresas que aparecem em listas oficiais sem CNPJ (ex.: lista da prefeitura de Londrina).
Uso: python3 coleta/buscar_por_nome.py /tmp/receita-pr/receita-pr.csv.gz "KFG AMBIENTAL" "M. M. SERVI"
Grava coleta/busca-por-nome.md. Só consulta, não muda a planilha."""
import csv
import gzip
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from buscar_cidade import IAT, get  # noqa: E402
from buscar_receita import receita  # noqa: E402

arq = Path(sys.argv[1])
nomes = sys.argv[2:]
saida = ["# Busca por nome (IAT e Receita)", ""]
cnpjs = {}
for nome in nomes:
    saida.append(f"## {nome}")
    w = "UPPER(nome_razao_social) LIKE '%" + nome.upper().replace("'", "''") + "%'"
    try:
        r = json.loads(get(f"{IAT}?" + urllib.parse.urlencode({"f": "json", "where": w, "outFields": "*", "returnGeometry": "false"}), tentativas=2))
        feats = [f["attributes"] for f in r.get("features", [])]
    except Exception as e:  # noqa: BLE001
        saida.append(f"- IAT: erro {e}")
        feats = []
    if not feats:
        saida.append("- IAT: nada encontrado")
    for a in feats:
        c = str(a.get("cpf_cnpj") or "").zfill(14)
        cnpjs[c] = a.get("nome_razao_social")
        val = a.get("dt_validade")
        if isinstance(val, (int, float)):
            import datetime
            val = datetime.datetime.utcfromtimestamp(val / 1000).strftime("%d/%m/%Y")
        saida.append(f"- IAT: {a.get('nome_razao_social')} | CNPJ {c} | {a.get('sigla_modalidade')} {a.get('num_documento')} | validade {val} | {a.get('nome_municipio')} | {str(a.get('desc_atividade') or a.get('atividade') or '')[:120]}")
    saida.append("")

saida.append("## Receita")
achados = set()
if arq.exists():
    with gzip.open(arq, "rt", encoding="utf-8", newline="") as f:
        for a in csv.DictReader(f):
            if a["cnpj"].zfill(14) in cnpjs:
                achados.add(a["cnpj"].zfill(14))
                saida.append(f"- {a['cnpj']} {cnpjs[a['cnpj'].zfill(14)]} | fantasia {a['fantasia']} | {a['situacao']} | {a['endereco']} | CEP {a['cep']} | {a['municipio']} | tel {a['telefone']} | CNAE {a['principal']}")
for c in cnpjs:
    if c not in achados:
        try:
            d = receita(c)
            saida.append(f"- {c} (consulta direta): {json.dumps(d, ensure_ascii=False)[:600]}")
        except Exception as e:  # noqa: BLE001
            saida.append(f"- {c}: não está no arquivo mensal; consulta direta falhou ({e})")

Path("coleta/busca-por-nome.md").write_text("\n".join(saida) + "\n", encoding="utf-8")
print("\n".join(saida))
