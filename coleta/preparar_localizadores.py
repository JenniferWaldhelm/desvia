#!/usr/bin/env python3
"""Cruza coleta/localizadores-pr.csv com a base do site e prepara a revisão de cada cidade.

Para cada ponto dos localizadores:
  - já na base (mesmo CNPJ, mesmo endereço ou mesmo nome na cidade): se o resíduo do programa ainda não
    está no ponto, propõe "acrescentar resíduo"; senão, ignora;
  - novo: acha o CNPJ no arquivo mensal da Receita (mesma cidade, mesmo CEP ou rua, mesmo número) e
    confere a licença no IAT e o CTF/IBAMA (decisão da Jen de 18/11/2026);
  - balcão (farmácia, mercado, loja, banco, Correios) fica PEV privado; recicladora, sucata,
    ferro-velho, borracharia de pneus ou empresa ambiental entra como empresa.

Uso: RECEITA_PR=/tmp/receita-pr python3 coleta/preparar_localizadores.py [cidade ...]
Saída: coleta/<cidade>-localizadores-revisao.csv e coleta/localizadores-revisao-resumo.md
"""
import csv
import gzip
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preparar as P  # noqa: E402
import localizadores as L  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
HOJE = date.today()
EMPRESA = re.compile(r"RECICL|SUCATA|FERRO VELHO|AMBIENTAL|RESIDUO|COOPERATIV|ASSOCIACAO DE CATADORES|"
                     r"ECOPONTO|AUTO PECAS|BORRACHARIA|RECAPAG|RECAUCH|PNEUS", re.I)
RESIDUO_SITE = {  # palavra que precisa estar na coluna F para o ponto ganhar a etiqueta
    "Pneus": "pneus", "Pilhas e baterias": "pilhas", "Eletroeletrônicos": "eletroeletr", "Lâmpadas": "lâmpadas",
    "Embalagens de óleo lubrificante": "embalagens de óleo lubrificante", "Medicamentos vencidos ou em desuso": "medicamentos",
}
TEXTO_F = {"Pneus": "Pneus inservíveis", "Pilhas e baterias": "Pilhas e baterias portáteis",
           "Eletroeletrônicos": "Eletroeletrônicos e eletrodomésticos", "Lâmpadas": "Lâmpadas (fluorescentes, LED e outras)",
           "Embalagens de óleo lubrificante": "Embalagens plásticas de óleo lubrificante"}


def n(t):
    return P.norm(t).upper()


def chave_rua(end):
    e = n(end)
    num = re.search(r"\b(\d{1,5})\b", e)
    pal = [w for w in re.findall(r"[A-Z]{4,}", e) if w not in {"AVENIDA", "RUA", "RODOVIA", "CENTRO", "JARDIM", "VILA", "PARQUE", "TRAVESSA"}]
    return (pal[0] if pal else "", num.group(1) if num else "")


GENERICOS = {"LTDA", "LOJA", "FILIAL", "COMERCIO", "PARANA", "SUPERMERCADO", "SUPERMERCADOS", "FARMACIA", "FARMACIAS",
             "DROGARIA", "CASAS", "MAGAZINE", "ABREE", "ATACADO", "CENTRO", "MATERIAIS", "ELETRICOS", "SECRETARIA",
             "MUNICIPAL", "PREFEITURA", "ASSOCIACAO", "AVENIDA", "RUA", "UNIDADE", "AGENCIA", "POSTO", "AUTO"}


def tokens(nome, cidade=""):
    fora = GENERICOS | set(n(cidade).split())
    return {w for w in re.findall(r"[A-Z0-9]{3,}", n(nome)) if w not in fora}


def ler_receita(pasta, cidades):
    arq = Path(pasta or "") / "receita-pr.csv.gz"
    if not pasta or not arq.exists():
        return {}
    alvo = {n(c) for c in cidades}
    por = defaultdict(list)
    with gzip.open(arq, "rt", encoding="utf-8", newline="") as f:
        for a in csv.DictReader(f):
            if n(a["municipio"]) in alvo and a["situacao"] == "Ativa":
                por[n(a["municipio"])].append(a)
    return por


def achar_cnpj(p, empresas):
    """Empresa ativa da Receita na mesma cidade com mesmo CEP (ou mesma rua) e mesmo número."""
    rua, num = chave_rua(p["Endereço"])
    cep = re.sub(r"\D", "", p.get("CEP", ""))
    melhor = None
    for a in empresas:
        r2, n2 = chave_rua(a["endereco"])
        if not num or n2 != num:
            continue
        if (cep and cep == re.sub(r"\D", "", a["cep"])) or (rua and r2 == rua):
            peso = len(tokens(p["Nome"]) & tokens(a["fantasia"]))
            if not melhor or peso > melhor[0]:
                melhor = (peso, a)
    return melhor[1]["cnpj"] if melhor else ""


def main():
    cidades = sys.argv[1:] or L.CIDADES
    locs = list(csv.DictReader(open(RAIZ / "coleta" / "localizadores-pr.csv", encoding="utf-8")))
    base = list(csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")))
    recusados = {re.sub(r"\D", "", r["CNPJ"]) for r in csv.DictReader(open(RAIZ / "coleta" / "recusados.csv", encoding="utf-8"))}

    # OSM sem cidade: usa o limite oficial do município
    pols = {c: P.poligono(c) for c in cidades}
    for l in locs:
        if not l["Cidade"] and l["Lat"]:
            try:
                from shapely.geometry import Point
                pt = Point(float(l["Lng"]), float(l["Lat"]))
                l["Cidade"] = next((c for c, pol in pols.items() if pol is not None and pol.contains(pt)), "")
            except Exception:  # noqa: BLE001
                pass

    receita = ler_receita(os.environ.get("RECEITA_PR"), cidades)
    candidatos = {}
    resumo = [f"# Localizadores: revisão por cidade ({HOJE:%d/%m/%Y})", ""]
    if not receita:
        resumo.append("- Arquivo mensal da Receita não disponível: CNPJ e licença dos pontos novos ficaram sem conferir.")

    for cid in cidades:
        da_cidade = [l for l in locs if n(l["Cidade"]) == n(cid)]
        b = [p for p in base if n(p["Município sede"]) == n(cid)]
        por_cnpj = {re.sub(r"\D", "", p["CNPJ"]): p for p in b if p["CNPJ"]}
        por_rua = defaultdict(list)
        for p in b:
            if p["Endereço"]:
                por_rua[chave_rua(p["Endereço"])].append(p)
        saida, vistos, cont = [], set(), Counter()
        for l in da_cidade:
            k = (l["Programa"], n(l["Nome"]), chave_rua(l["Endereço"]))
            if k in vistos:
                continue
            vistos.add(k)
            cnpj = re.sub(r"\D", "", l.get("CNPJ", ""))
            if not cnpj and receita.get(n(cid)) and l["Programa"] != "OpenStreetMap":
                cnpj = achar_cnpj(l, receita[n(cid)])
            if cnpj and cnpj in recusados:
                cont["recusado antes"] += 1
                continue
            achado = por_cnpj.get(cnpj) if cnpj else None
            if not achado:
                rk = chave_rua(l["Endereço"])
                achado = next((p for p in por_rua.get(rk, []) if rk[1]), None)
            if not achado:
                # pelo nome: aceita se só um ponto da cidade divide uma palavra marcante (5+ letras) com o nome;
                # rede com várias lojas na cidade (Raia, Nissei) precisa do endereço
                tk = {w for w in tokens(l["Nome"], cid) if len(w) >= 5}
                parecidos = [p for p in b if tk & {w for w in tokens(p["Nome"], cid) if len(w) >= 5}]
                if len(parecidos) == 1:
                    achado = parecidos[0]
            palavra = RESIDUO_SITE.get(l["Resíduo"])
            if achado:
                if palavra and palavra not in achado["Resíduos aceitos"].lower():
                    cont["acrescentar resíduo"] += 1
                    saida.append({"Confiança": "Acrescentar resíduo", "ID": achado["ID"], "Nome": achado["Nome"],
                                  "Por quê": f"{l['Programa']} diz que recebe {l['Resíduo'].lower()}; na base o ponto não tem. Acrescentar na coluna F: {TEXTO_F.get(l['Resíduo'], l['Resíduo'])}",
                                  "Resíduos aceitos": achado["Resíduos aceitos"] + "; " + TEXTO_F.get(l["Resíduo"], l["Resíduo"]),
                                  "Endereço": achado["Endereço"], "Município sede": cid, "Fonte": l["Fonte"],
                                  "Data verificação": HOJE.strftime("%d/%m/%Y"), "Origem": l["Programa"]})
                else:
                    cont["já na base"] += 1
                continue
            empresa = bool(EMPRESA.search(n(l["Nome"]))) or l["Programa"] == "Mapa das OSCs"
            if l["Programa"] == "Mapa das OSCs":
                tipo, serv = "Cooperativa/associação", "Recebimento"
            elif empresa:
                tipo, serv = "Tratamento/destinação final", "Recebimento"
            else:
                tipo, serv = "PEV privado", "Recebimento"
            cont["novo"] += 1
            saida.append({
                "Confiança": "OSC (doação?)" if l["Programa"] == "Mapa das OSCs" else ("Localizador: empresa" if empresa else "Localizador"),
                "Por quê": f"{l['Programa']}" + (" · CNPJ achado na Receita" if cnpj and not l.get("CNPJ") else "")
                           + ("" if cnpj else " · CNPJ não achado") + (" · confirmar o que recebe" if l["Programa"] == "Mapa das OSCs" else ""),
                "Nome": P.nome_bonito(l["Nome"]), "CNPJ": f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else "",
                "Tipo de ponto": tipo, "Serviço": serv,
                "Resíduos aceitos": TEXTO_F.get(l["Resíduo"], l["Resíduo"]) if l["Programa"] != "Mapa das OSCs" else "",
                "Endereço": l["Endereço"] + (f", {l['Bairro']}" if l.get("Bairro") and l["Bairro"] not in l["Endereço"] else ""),
                "Município sede": cid, "Municípios atendidos": cid, "Lat": l["Lat"], "Lng": l["Lng"], "Telefone": l["Telefone"],
                "Fonte": l["Fonte"], "Data verificação": HOJE.strftime("%d/%m/%Y"), "Obs": l["Obs"],
                "Atividades (original)": l["Resíduo"], "Origem": l["Programa"], "_cnpj": cnpj})

        # licença dos novos com CNPJ (IAT por CNPJ e CTF da cidade)
        cnpjs = [s["_cnpj"] for s in saida if s.get("_cnpj")]
        if cnpjs:
            try:
                import buscar_cidade as bc
                _, iat = bc.buscar_iat_por_cnpj(cnpjs)
                try:
                    ctf = bc.buscar_ctf(cid)
                except Exception:  # noqa: BLE001
                    ctf = {}
                for s in saida:
                    i = iat.get(s.get("_cnpj", ""))
                    lic = (i or {}).get("lic") or {}
                    if lic and (lic.get("sigla_modalidade") or "").upper() != "AA":
                        s["Órgão licença"] = "IAT"
                        s["Tipo licença"] = lic.get("sigla_modalidade") or ""
                        s["Nº licença"] = str(lic.get("num_documento") or "")
                        s["Validade licença"] = bc.data_iat(lic.get("dt_validade"))
                        s["Por quê"] += f" · licença {s['Tipo licença']} até {s['Validade licença']}"
                    elif s.get("_cnpj"):
                        s["Por quê"] += " · licença ambiental não localizada" + (" (só CTF/IBAMA)" if s["_cnpj"] in ctf else "")
            except Exception as e:  # noqa: BLE001
                resumo.append(f"- {cid}: conferência de licença falhou ({e})")

        # ID provisório
        pref = P.PREFIXO.get(P.norm(cid), P.norm(cid)[:3].upper())
        usados = [int(m.group(1)) for p in base if (m := re.match(rf"{pref}-(\d+)$", p["ID"]))]
        prox = max(usados, default=0) + 1
        for s in saida:
            if not s.get("ID"):
                s["ID"] = f"{pref}-{prox:03d}"
                prox += 1
        slug = re.sub(r"[^a-z0-9]+", "-", P.norm(cid)).strip("-")
        cols = P.DECISAO + P.PONTOS + P.EXTRA
        with open(RAIZ / "coleta" / f"{slug}-localizadores-revisao.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for s in sorted(saida, key=lambda s: (s["Confiança"], s["Nome"])):
                w.writerow({c: s.get(c, "") for c in cols})
        prog = Counter(s["Origem"] for s in saida if s["Confiança"] != "Acrescentar resíduo")
        resumo.append(f"- **{cid}**: {len(da_cidade)} nos localizadores; novos {cont['novo']} ("
                      + ", ".join(f"{k} {v}" for k, v in prog.most_common()) + f"); acrescentar resíduo {cont['acrescentar resíduo']}; "
                      f"já na base {cont['já na base']}" + (f"; recusados antes {cont['recusado antes']}" if cont["recusado antes"] else ""))
    (RAIZ / "coleta" / "localizadores-revisao-resumo.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    print("\n".join(resumo))


if __name__ == "__main__":
    main()
