#!/usr/bin/env python3
"""Levanta empresas de resíduos de um município do Paraná e grava uma tabela pronta
para colar na aba Pontos da planilha mestra.

Fontes:
  1. IAT GeoPR (licenças estaduais, com coordenadas) — API pública do painel Licenciamento Ambiental
  2. CTF/APP do IBAMA (dados abertos) — empresas inscritas em atividades de resíduos
  3. Receita Federal (BrasilAPI / minhareceita.org) — situação do CNPJ, telefone e endereço

Uso: python3 coleta/buscar_cidade.py "Ibiporã"
Saída: coleta/<cidade>.csv  (colunas da aba Pontos + Situação CNPJ + Já na base)
       coleta/<cidade>-resumo.md
"""
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HOJE = date.today().strftime("%d/%m/%Y")
IAT = "https://geopr.iat.pr.gov.br/server/rest/services/00_PUBLICACOES/licenciamento_ambiental_pr/FeatureServer/0/query"
CTF_ZIP = "https://stibamadadosabertosprd.blob.core.windows.net/dados-abertos/dados/CTF/APP/pessoas-juridicas-inscritas-no-ctf-app1_csv.zip"
UA = {"User-Agent": "Desvia/1.0 (+https://jenniferwaldhelm.github.io/desvia/)"}

# Atividades do IAT que indicam prestação de serviço de resíduos
IAT_INCLUI = re.compile(r"Disposição de resíduos|Gerenciamento de resíduos|Reciclagem|Recuperação e refino|"
                        r"cargas em geral e de resíduos classe|transporte de resíduos|Transportadora de resíduos", re.I)
IAT_EXCLUI = re.compile(r"Autom|sem resíduos", re.I)
# Atividades do CTF: 017.* (tratamento/destinação), 018.014 (transporte OLUC), 018.074 (transporte resíduos perigosos)
CTF_INCLUI = re.compile(r"\b(017\.\d{3}|018\.014|018\.074)\b|tratamento e destina|destinação de resíduos|transporte de cargas perigosas - (lei n|resolu)", re.I)
# Quem não presta serviço de resíduos a terceiros
NOME_EXCLUI = re.compile(r"ÁGUA E ESGOTO|AGUA E ESGOTO|SANEPAR|SAMAE|SAAE|COMPANHIA DE SANEAMENTO", re.I)

COLUNAS = ["ID", "Nome", "CNPJ", "Tipo de ponto", "Serviço", "Resíduos aceitos", "Classe NBR 10004", "Endereço",
           "Município sede", "Lat", "Lng", "Municípios atendidos", "Órgão licença", "Tipo licença", "Nº licença",
           "Validade licença", "Status licença (auto)", "Telefone", "Site/rede", "Fonte", "Data verificação", "Obs",
           "Situação CNPJ", "Já na base"]


def norm(t):
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower().strip()


def so_digitos(v):
    d = str(int(v)) if isinstance(v, (int, float)) else re.sub(r"\D", "", str(v or ""))
    return d.zfill(14) if len(d) > 11 else d


def fmt_cnpj(d):
    d = so_digitos(d).zfill(14)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else d


def get(url, tentativas=3, timeout=60):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))


# ── 1. IAT ──────────────────────────────────────────────────────────────
def buscar_iat(cidade):
    todos, off = [], 0
    while True:
        q = urllib.parse.urlencode({"f": "json", "where": f"nome_municipio='{cidade}'", "outFields": "*",
                                    "returnGeometry": "false", "resultRecordCount": 2000, "resultOffset": off,
                                    "orderByFields": "objectid"})
        r = json.loads(get(f"{IAT}?{q}"))
        if "error" in r:
            raise RuntimeError(r["error"])
        fs = [f["attributes"] for f in r.get("features", [])]
        todos += fs
        if len(fs) < 2000:
            break
        off += 2000
    empresas = {}
    for a in todos:
        chave = f"{a.get('desc_grupo_atividade')} | {a.get('desc_atividade')}"
        if not IAT_INCLUI.search(chave) or IAT_EXCLUI.search(chave) or NOME_EXCLUI.search(a.get("nome_razao_social") or ""):
            continue
        cnpj = so_digitos(a.get("cpf_cnpj"))
        e = empresas.setdefault(cnpj, {"nome": a["nome_razao_social"], "atividades": set(), "lic": None,
                                       "lat": a.get("y"), "lng": a.get("x")})
        e["atividades"].add(a.get("desc_atividade") or "")
        if not e["lic"] or (a.get("dt_validade") or 0) > (e["lic"].get("dt_validade") or 0):
            e["lic"] = a
    return len(todos), empresas


# ── 2. CTF/IBAMA ────────────────────────────────────────────────────────
DIAG = []


def buscar_ctf(cidade):
    bruto = get(CTF_ZIP, timeout=600)
    z = zipfile.ZipFile(io.BytesIO(bruto))
    alvo = norm(cidade)
    empresas = {}
    for nome in z.namelist():
        if not nome.lower().endswith(".csv") or (any(n.lower().endswith("_pr.csv") for n in z.namelist())
                                                  and not nome.lower().endswith("_pr.csv")):
            continue
        with z.open(nome) as fh:
            amostra = fh.read(4096).decode("utf-8", "replace")
        sep = ";" if amostra.count(";") > amostra.count(",") else ","
        with z.open(nome) as fh:
            leitor = csv.reader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), delimiter=sep)
            cab = [norm(c) for c in next(leitor)]

            def col(*chaves):
                for i, c in enumerate(cab):
                    if any(k in c for k in chaves):
                        return i
                return None
            i_cnpj, i_nome = col("cnpj"), col("razao", "nome", "inscrito")
            i_mun, i_uf = col("municipio"), col("estado", "uf")
            i_ccat, i_dcat = col("codigo da categoria"), col("descricao da categoria")
            i_catv, i_dativ = col("codigo da atividade"), col("descricao da atividade")
            i_sit = col("situacao cadastral", "situacao")
            if None in (i_cnpj, i_nome, i_mun):
                DIAG.append(f"CTF {nome}: colunas não reconhecidas: {cab[:20]}")
                continue

            def codigo(linha):
                try:
                    return f"{int(linha[i_ccat]):03d}.{int(linha[i_catv]):03d}"
                except (TypeError, ValueError, IndexError):
                    return ""
            n_mun, n_ok = 0, 0
            for linha in leitor:
                try:
                    if norm(linha[i_mun]) != alvo:
                        continue
                    if i_uf is not None and norm(linha[i_uf]) not in ("pr", "parana"):
                        continue
                    n_mun += 1
                    desc = " ".join(linha[i] for i in (i_dcat, i_dativ) if i is not None)
                    ativ = f"{codigo(linha)} {desc}"
                    if not CTF_INCLUI.search(ativ) or NOME_EXCLUI.search(linha[i_nome]):
                        continue
                except IndexError:
                    continue
                n_ok += 1
                cnpj = so_digitos(linha[i_cnpj])
                e = empresas.setdefault(cnpj, {"nome": linha[i_nome], "atividades": set(),
                                               "situacao": linha[i_sit] if i_sit is not None else ""})
                e["atividades"].add(linha[i_dativ] if i_dativ is not None else ativ)
            if n_mun:
                DIAG.append(f"CTF {nome}: {n_mun} atividades no município, {n_ok} de resíduos")
    return empresas


# ── 3. Receita ──────────────────────────────────────────────────────────
def receita(cnpj):
    for url in (f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", f"https://minhareceita.org/{cnpj}"):
        try:
            d = json.loads(get(url, tentativas=2, timeout=30))
            tel = d.get("ddd_telefone_1") or ""
            tel = f"({tel[:2]}) {tel[2:]}" if len(tel) >= 10 else tel
            end = ", ".join(x for x in [f"{d.get('descricao_tipo_de_logradouro') or ''} {d.get('logradouro') or ''}".strip(),
                                        d.get("numero") or "", d.get("bairro") or ""] if x)
            return {"situacao": (d.get("descricao_situacao_cadastral") or "").title(), "telefone": tel,
                    "endereco": end.title() if end.isupper() else end, "fantasia": d.get("nome_fantasia") or "",
                    "pf": str(d.get("codigo_natureza_juridica") or "") == "2135"
                          or "empresário (individual)" in (d.get("natureza_juridica") or "").lower()}
        except Exception:  # noqa: BLE001
            continue
    return {"situacao": "não consultada", "telefone": "", "endereco": "", "fantasia": "", "pf": False}


# ── classificação simples para a planilha ───────────────────────────────
def classificar(atividades):
    t = norm(" ".join(atividades))
    if "transport" in t and not re.search(r"triagem|tratamento|reciclagem|aterro|recupera|disposi", t):
        tipo, serv = "Coleta e transporte", "Transporte"
    elif "reciclagem de plasticos" in t or "recuperacao de materia" in t or "sucata" in t:
        tipo, serv = "Tratamento/destinação final", "Compra de recicláveis"
    elif "triagem" in t or "armazenamento" in t:
        tipo, serv = "Tratamento/destinação final", "Triagem"
    else:
        tipo, serv = "Tratamento/destinação final", "Destinação final"
    return tipo, serv


def data_iat(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%d/%m/%Y") if ms else ""


def principal(cidade):
    slug = re.sub(r"[^a-z0-9]+", "-", norm(cidade)).strip("-")
    base = {}
    with open(RAIZ / "dados" / "pontos.csv", encoding="utf-8") as f:
        for p in csv.DictReader(f):
            if p["CNPJ"]:
                base[so_digitos(p["CNPJ"])] = p["ID"]

    avisos = []
    try:
        n_iat, iat = buscar_iat(cidade)
    except Exception as e:  # noqa: BLE001
        n_iat, iat = 0, {}
        avisos.append(f"IAT não respondeu: {e}")
    try:
        ctf = buscar_ctf(cidade)
    except Exception as e:  # noqa: BLE001
        ctf = {}
        avisos.append(f"CTF/IBAMA não respondeu: {e}")

    linhas = []
    for cnpj in sorted(set(iat) | set(ctf)):
        i, c = iat.get(cnpj), ctf.get(cnpj)
        atividades = (i["atividades"] if i else set()) | (c["atividades"] if c else set())
        rf = receita(cnpj)
        time.sleep(0.4)
        nome = (i or c)["nome"].strip()
        if rf["fantasia"] and norm(rf["fantasia"]) not in norm(nome):
            nome = f"{nome} ({rf['fantasia'].title()})"
        tipo, serv = classificar(atividades)
        lic = i["lic"] if i else None
        tl = (lic or {}).get("sigla_modalidade") or ""
        fontes = [x for x, ok in (("IAT GeoPR", i), ("CTF/IBAMA", c)) if ok] + (["Receita"] if rf["situacao"] != "não consultada" else [])
        obs = []
        if not i:
            obs.append("Só no CTF: pedir licença antes de indicar.")
        if tl in ("LP", "LI", "LI-A"):
            obs.append("Só Licença Prévia ou de Instalação: não autoriza operação.")
        if rf["situacao"] and rf["situacao"].lower() not in ("ativa", "não consultada"):
            obs.append(f"CNPJ {rf['situacao'].lower()} na Receita em {HOJE}.")
        if rf["pf"]:
            obs.append("Empresário individual: endereço não publicado.")
        linhas.append({
            "ID": "", "Nome": nome, "CNPJ": fmt_cnpj(cnpj), "Tipo de ponto": tipo, "Serviço": serv,
            "Resíduos aceitos": "; ".join(sorted(a for a in atividades if a))[:200], "Classe NBR 10004": "",
            "Endereço": "" if rf["pf"] else rf["endereco"], "Município sede": cidade,
            "Lat": "" if rf["pf"] or not i or not i.get("lat") else f"{i['lat']:.5f}",
            "Lng": "" if rf["pf"] or not i or not i.get("lng") else f"{i['lng']:.5f}",
            "Municípios atendidos": cidade, "Órgão licença": "IAT" if i else "", "Tipo licença": tl,
            "Nº licença": str((lic or {}).get("num_documento") or ""), "Validade licença": data_iat((lic or {}).get("dt_validade")),
            "Status licença (auto)": "", "Telefone": rf["telefone"], "Site/rede": "", "Fonte": ", ".join(fontes),
            "Data verificação": HOJE, "Obs": " ".join(obs), "Situação CNPJ": rf["situacao"],
            "Já na base": base.get(cnpj, ""),
        })

    destino = RAIZ / "coleta" / f"{slug}.csv"
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    novas = [l for l in linhas if not l["Já na base"]]
    resumo = [f"# {cidade}: coleta automática em {HOJE}", "",
              f"- Licenças do IAT no município: {n_iat}",
              f"- Empresas de resíduos no IAT: {len(iat)}",
              f"- Empresas de resíduos no CTF/IBAMA: {len(ctf)}",
              f"- Total (sem repetição): {len(linhas)}",
              f"- Já na base: {len(linhas) - len(novas)}",
              f"- Novas: {len(novas)}",
              f"- CNPJ não ativo na Receita: {sum(1 for l in linhas if l['Situação CNPJ'] and l['Situação CNPJ'].lower() not in ('ativa', 'não consultada'))}",
              ""] + [f"- Aviso: {a}" for a in avisos] + (["", "## Diagnóstico CTF", ""] + [f"- {d}" for d in DIAG] if DIAG else [])
    (RAIZ / "coleta" / f"{slug}-resumo.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    print("\n".join(resumo))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Uso: python3 coleta/buscar_cidade.py "Nome do município"')
    principal(sys.argv[1].strip())
