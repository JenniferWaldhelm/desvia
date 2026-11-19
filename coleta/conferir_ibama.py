#!/usr/bin/env python3
"""Confere no IAT e na Receita as empresas que declaram ao IBAMA (RAPP) receber
resíduo de terceiros nos municípios do Desvia e ainda não estão na base.

Lê coleta/ibama-residuos-empresas.csv (gerado por coleta/ibama_rapp.py).
Grava coleta/ibama-candidatas.csv, com as colunas da aba Pontos + Situação CNPJ
+ Último ano no RAPP + Recomendação, e coleta/ibama-candidatas-resumo.md.

Uso: python3 coleta/conferir_ibama.py
"""
import csv
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coleta"))
import buscar_cidade as bc  # noqa: E402

MUNICIPIOS = ["Londrina", "Maringá", "Apucarana", "Arapongas", "Rolândia", "Cambé", "Cambira", "Ibiporã",
              "Mandaguari", "Jandaia do Sul", "Marialva", "Sarandi"]
COLUNAS = bc.COLUNAS[:-1] + ["Último ano no RAPP", "Recomendação"]


def main():
    por_nome = {bc.norm(m): m for m in MUNICIPIOS}
    with open(RAIZ / "coleta" / "ibama-residuos-empresas.csv", encoding="utf-8") as f:
        cand = [e for e in csv.DictReader(f)
                if bc.norm(e["Município"]) in por_nome and not e["No Desvia (ID)"] and e["Papel no RAPP"] != "gerador"]
    cnpjs = {bc.so_digitos(e["CNPJ"]) for e in cand}
    try:
        _, iat = bc.buscar_iat_por_cnpj(cnpjs)
    except Exception as e:  # noqa: BLE001
        print(f"IAT indisponível: {e}", file=sys.stderr)
        iat = {}

    linhas = []
    for e in cand:
        cnpj = bc.so_digitos(e["CNPJ"])
        cidade = por_nome[bc.norm(e["Município"])]
        i = iat.get(cnpj)
        rf = bc.receita(cnpj)
        time.sleep(0.4)
        lic = i["lic"] if i else None
        tl = (lic or {}).get("sigla_modalidade") or ""
        validade = bc.data_iat((lic or {}).get("dt_validade"))
        if i:
            tipo, serv = bc.classificar(i["atividades"])
        else:
            tipo, serv = "Tratamento/destinação final", "Destinação final"
        nome = e["Razão social"].strip()
        if rf["fantasia"] and bc.norm(rf["fantasia"]) not in bc.norm(nome):
            nome = f"{nome} ({rf['fantasia'].title()})"
        anos = re.findall(r"\d{4}", e["Anos"])
        ultimo = anos[-1] if anos else ""
        recebe = e["Resíduos que recebe (mais frequentes)"].split("; ")
        obs = [f"Declarou ao IBAMA (RAPP) receber resíduo de terceiros ({e['Anos']})."]
        if not i:
            obs.append("Sem licença no IAT: pedir licença antes de indicar.")
        if tl in ("LP", "LI", "LI-A"):
            obs.append("Só Licença Prévia ou de Instalação: não autoriza operação.")
        sit = rf["situacao"]
        if sit and sit.lower() not in ("ativa", "não consultada"):
            obs.append(f"CNPJ {sit.lower()} na Receita em {bc.HOJE}.")
        if rf["pf"]:
            obs.append("Empresário individual: endereço não publicado.")

        if sit and sit.lower() not in ("ativa", "não consultada"):
            rec = "Não incluir (CNPJ inativo)"
        elif ultimo and int(ultimo) < 2020 and not i:
            rec = "Não incluir (parou de declarar e sem licença)"
        elif i:
            rec = "Incluir"
        else:
            rec = "Incluir (sem licença no IAT)"

        linhas.append({
            "ID": "", "Nome": nome, "CNPJ": e["CNPJ"], "Tipo de ponto": tipo, "Serviço": serv,
            "Resíduos aceitos": "; ".join(recebe[:10])[:400], "Classe NBR 10004": "",
            "Endereço": "" if rf["pf"] else rf["endereco"], "Município sede": cidade,
            "Lat": "" if rf["pf"] or not i or not i.get("lat") else f"{i['lat']:.5f}",
            "Lng": "" if rf["pf"] or not i or not i.get("lng") else f"{i['lng']:.5f}",
            "Municípios atendidos": cidade, "Órgão licença": "IAT" if i else "", "Tipo licença": tl,
            "Nº licença": str((lic or {}).get("num_documento") or ""), "Validade licença": validade,
            "Status licença (auto)": "", "Telefone": rf["telefone"], "Site/rede": "",
            "Fonte": ", ".join(["IBAMA (RAPP)"] + (["IAT GeoPR"] if i else []) + (["Receita"] if sit != "não consultada" else [])),
            "Data verificação": bc.HOJE, "Obs": " ".join(obs), "Situação CNPJ": sit,
            "Último ano no RAPP": ultimo, "Recomendação": rec,
        })
    linhas.sort(key=lambda l: (not l["Recomendação"].startswith("Incluir"), MUNICIPIOS.index(l["Município sede"]), l["Nome"]))
    with open(RAIZ / "coleta" / "ibama-candidatas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    r = [f"# Candidatas do IBAMA (RAPP): conferência em {bc.HOJE}", "",
         f"- Empresas conferidas: {len(linhas)}",
         f"- Com licença no IAT: {sum(1 for l in linhas if l['Órgão licença'])}",
         f"- CNPJ ativo na Receita: {sum(1 for l in linhas if l['Situação CNPJ'].lower() == 'ativa')}",
         f"- Receita não respondeu: {sum(1 for l in linhas if l['Situação CNPJ'] == 'não consultada')}", ""]
    r += [f"- {l['Recomendação']}: {l['Nome']} ({l['Município sede']}) · licença {l['Tipo licença'] or '-'} {l['Validade licença']} · "
          f"CNPJ {l['Situação CNPJ'] or '-'} · último RAPP {l['Último ano no RAPP']}" for l in linhas]
    r += [""] + [f"- {d}" for d in bc.IAT_DIAG]
    (RAIZ / "coleta" / "ibama-candidatas-resumo.md").write_text("\n".join(r), encoding="utf-8")
    print("\n".join(r))


if __name__ == "__main__":
    main()
