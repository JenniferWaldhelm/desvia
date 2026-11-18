#!/usr/bin/env python3
"""Procura na base aberta de CNPJs da Receita Federal as empresas de um município
do Paraná com atividade (CNAE) ligada a resíduos, inclusive as que não aparecem
no IAT nem no CTF/IBAMA (ex.: locadoras de caçamba sem licença).

Fonte: dados abertos do CNPJ (arquivos Estabelecimentos, Municipios e Cnaes),
publicados todo mês pela Receita. Razão social e natureza jurídica vêm da
BrasilAPI / minhareceita.org, só para as empresas filtradas.

Uso: python3 coleta/buscar_receita.py "Sarandi"   (com RECEITA_PR=<pasta> usa o arquivo mensal, em segundos)
     python3 coleta/buscar_receita.py --pr <pasta>  (gera o arquivo mensal do Paraná)
Saída: coleta/<cidade>-receita.csv e coleta/<cidade>-receita-resumo.md
Não altera o site nem a planilha: a Jen confere a lista antes.
"""
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
import gzip
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TMP = Path("/tmp/receita")
UA = {"User-Agent": "Desvia/1.0 (+https://desvia.eco.br/)"}
# Desde 2025 os arquivos ficam num compartilhamento público (Nextcloud/WebDAV) da Receita
SHARE = "YggdBLfdninEJX9"
WEBDAV = "https://arquivos.receitafederal.gov.br/public.php/webdav/"
AUTH = {"Authorization": "Basic " + __import__("base64").b64encode(f"{SHARE}:".encode()).decode()}
HOJE = date.today().strftime("%d/%m/%Y")
BASES = [
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/",
    "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/",
]

# CNAEs que já indicam serviço de resíduo (principal ou secundário)
FORTES = {
    "3702900": "Esgoto e limpa-fossa (exceto redes)",
    "3811400": "Coleta de resíduos não perigosos",
    "3812200": "Coleta de resíduos perigosos",
    "3821100": "Tratamento e disposição de resíduos não perigosos",
    "3822000": "Tratamento e disposição de resíduos perigosos",
    "3831901": "Recuperação de sucatas de alumínio",
    "3831999": "Recuperação de materiais metálicos",
    "3832700": "Recuperação de materiais plásticos",
    "3839401": "Usinas de compostagem",
    "3839499": "Recuperação de outros materiais",
    "3900500": "Descontaminação e gestão de resíduos",
    "4687701": "Comércio atacadista de papel e papelão usados",
    "4687702": "Comércio atacadista de resíduos e sucatas não metálicos",
    "4687703": "Comércio atacadista de sucatas metálicas",
}
# CNAEs que só contam se o nome indicar resíduo (caçamba, entulho etc.)
FRACOS = {
    "7732201": "Aluguel de máquinas e equipamentos para construção",
    "7739099": "Aluguel de outras máquinas e equipamentos",
    "4930201": "Transporte rodoviário de carga municipal",
    "4930202": "Transporte rodoviário de carga intermunicipal",
}
NOME_RESIDUO = re.compile(r"ca[cç]amba|entulho|recicl|sucata|ferro velho|residuo|ambiental|fossa|desentup|"
                          r"aparas|compost|metais|limpa|coleta", re.I)
SITUACAO = {"01": "Nula", "02": "Ativa", "03": "Suspensa", "04": "Inapta", "08": "Baixada"}


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()


def cab(url):
    return {**UA, **AUTH} if url.startswith(WEBDAV) else UA


def get(url, timeout=120, method="GET", extra=None):
    req = urllib.request.Request(url, headers={**cab(url), **(extra or {})}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def baixar(url, destino):
    for tentativa in range(4):
        try:
            req = urllib.request.Request(url, headers=cab(url))
            with urllib.request.urlopen(req, timeout=600) as r, open(destino, "wb") as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
            return destino
        except Exception as e:  # noqa: BLE001
            print(f"  falha ao baixar {url} ({e}); tentativa {tentativa + 1}", file=sys.stderr)
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"não consegui baixar {url}")


def pasta_recente():
    """Acha a pasta do mês mais recente que já tem os arquivos."""
    try:
        xml = get(WEBDAV, timeout=60, method="PROPFIND", extra={"Depth": "1"}).decode("utf-8", "ignore")
        meses = sorted(set(re.findall(r"/(\d{4}-\d{2})/?</d:href>", xml)), reverse=True)
        for m in meses[:3]:
            lista = get(f"{WEBDAV}{m}/", timeout=60, method="PROPFIND", extra={"Depth": "1"}).decode("utf-8", "ignore")
            if "Estabelecimentos0.zip" in lista:
                return f"{WEBDAV}{m}/", m
        print(f"WebDAV sem pasta completa. Meses vistos: {meses[:5]}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"WebDAV indisponível: {e}", file=sys.stderr)
    for base in BASES:
        try:
            html = get(base, timeout=60).decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"Listagem indisponível em {base}: {e}", file=sys.stderr)
            continue
        meses = sorted(set(re.findall(r'href="(\d{4}-\d{2})/?"', html)), reverse=True)
        for m in meses[:3]:
            url = f"{base}{m}/"
            try:
                lista = get(url, timeout=60).decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                continue
            if "Estabelecimentos0.zip" in lista:
                return url, m
        print(f"Sem pasta mensal completa em {base}. Meses vistos: {meses[:5]}", file=sys.stderr)
    raise SystemExit("Não achei os dados abertos do CNPJ. Conferir o endereço em BASES.")


def ler_zip_csv(caminho):
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            with z.open(nome) as f:
                yield from csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def codigos_municipio(url, cidade):
    alvo = norm(cidade)
    arq = baixar(url + "Municipios.zip", TMP / "Municipios.zip")
    cods = {l[0] for l in ler_zip_csv(arq) if len(l) >= 2 and norm(l[1]) == alvo}
    if not cods:
        raise SystemExit(f"Município {cidade} não achado na tabela da Receita.")
    return cods


def descricoes_cnae(url):
    try:
        arq = baixar(url + "Cnaes.zip", TMP / "Cnaes.zip")
        return {l[0]: l[1] for l in ler_zip_csv(arq) if len(l) >= 2}
    except Exception:  # noqa: BLE001
        return {}


def linha_estab(l, mun=None):
    """Converte uma linha de Estabelecimentos no registro usado aqui (None se não for de resíduo)."""
    principal = l[11]
    secundarias = [c for c in l[12].split(",") if c]
    todas = [principal] + secundarias
    fortes = [c for c in todas if c in FORTES]
    fracos = [c for c in todas if c in FRACOS]
    if not fortes and not fracos:
        return None
    return {
        "cnpj": l[0] + l[1] + l[2], "fantasia": l[4].strip(), "situacao": SITUACAO.get(l[5], l[5]), "inicio": l[10],
        "principal": principal, "fortes": fortes, "fracos": fracos,
        "endereco": " ".join(x for x in [l[13], l[14]] if x).strip() + (f", {l[15]}" if l[15] else "")
                    + (f", {l[17]}" if l[17] else ""),
        "cep": l[18], "telefone": f"({l[21]}) {l[22]}" if l[21] and l[22] else "",
        "municipio": (mun or {}).get(l[20], l[20]),
    }


def filtrar_arquivo(url, i, cods, mun=None):
    """cods=None: guarda o Paraná inteiro (todas as situações), para o arquivo mensal."""
    arq = baixar(f"{url}Estabelecimentos{i}.zip", TMP / f"Estabelecimentos{i}.zip")
    achados, outras = [], {}
    for l in ler_zip_csv(arq):
        if len(l) < 28 or l[19] != "PR" or (cods is not None and l[20] not in cods):
            continue
        a = linha_estab(l, mun)
        if not a:
            continue
        if cods is not None and a["situacao"] != "Ativa":
            outras[a["situacao"]] = outras.get(a["situacao"], 0) + 1
            continue
        achados.append(a)
    arq.unlink(missing_ok=True)
    print(f"  Estabelecimentos{i}: {len(achados)} registros", file=sys.stderr)
    return achados, outras


CAMPOS_PR = ["cnpj", "fantasia", "situacao", "inicio", "principal", "fortes", "fracos", "endereco", "cep", "telefone", "municipio"]


def baixar_pr(destino):
    """Arquivo mensal: todas as empresas do PR com atividade de resíduo (qualquer situação).
    Grava <destino>/receita-pr.csv.gz, <destino>/cnaes.csv e <destino>/mes.txt."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    url, mes = pasta_recente()
    print(f"Dados abertos do CNPJ: {mes}", file=sys.stderr)
    arq = baixar(url + "Municipios.zip", TMP / "Municipios.zip")
    mun = {l[0]: l[1] for l in ler_zip_csv(arq) if len(l) >= 2}
    cnaes = descricoes_cnae(url)
    todos = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for fut in as_completed([ex.submit(filtrar_arquivo, url, i, None, mun) for i in range(10)]):
            todos += fut.result()[0]
    with gzip.open(destino / "receita-pr.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_PR)
        w.writeheader()
        for a in sorted(todos, key=lambda x: x["cnpj"]):
            w.writerow({**a, "fortes": ",".join(a["fortes"]), "fracos": ",".join(a["fracos"])})
    with open(destino / "cnaes.csv", "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(sorted(cnaes.items()))
    (destino / "mes.txt").write_text(mes + "\n", encoding="utf-8")
    ativas = sum(1 for a in todos if a["situacao"] == "Ativa")
    print(f"# Receita Federal: Paraná ({mes})\n\n- Empresas com atividade de resíduo: {len(todos)} (ativas: {ativas})")


def ler_pr(pasta, cidade):
    """Lê o arquivo mensal do PR e devolve (achados ativos, outras situações, cnaes, mês) da cidade."""
    pasta = Path(pasta)
    alvo = norm(cidade)
    achados, outras = [], {}
    with gzip.open(pasta / "receita-pr.csv.gz", "rt", encoding="utf-8", newline="") as f:
        for a in csv.DictReader(f):
            if norm(a["municipio"]) != alvo:
                continue
            a["fortes"] = [c for c in a["fortes"].split(",") if c]
            a["fracos"] = [c for c in a["fracos"].split(",") if c]
            if a["situacao"] != "Ativa":
                outras[a["situacao"]] = outras.get(a["situacao"], 0) + 1
            else:
                achados.append(a)
    if not achados and not outras:
        raise SystemExit(f"Município {cidade} não achado no arquivo mensal da Receita.")
    cnaes = {}
    if (pasta / "cnaes.csv").exists():
        cnaes = {l[0]: l[1] for l in csv.reader(open(pasta / "cnaes.csv", encoding="utf-8")) if len(l) >= 2}
    mes = (pasta / "mes.txt").read_text(encoding="utf-8").strip() if (pasta / "mes.txt").exists() else "?"
    return achados, outras, cnaes, mes


def receita(cnpj):
    for url in (f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", f"https://minhareceita.org/{cnpj}"):
        try:
            d = json.loads(get(url, timeout=30))
            nat = str(d.get("codigo_natureza_juridica") or "")
            return {"razao": d.get("razao_social") or "", "natureza": d.get("natureza_juridica") or "",
                    "pf": nat == "2135" or bool(d.get("opcao_pelo_mei"))}
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return {"razao": "", "natureza": "", "pf": False}


def fmt_cnpj(c):
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def titulo(s):
    return s.title() if s.isupper() else s


def main():
    if sys.argv[1] == "--pr":
        return baixar_pr(sys.argv[2] if len(sys.argv) > 2 else "/tmp/receita-pr")
    cidade = sys.argv[1]
    slug = re.sub(r"[^a-z0-9]+", "-", norm(cidade).lower()).strip("-")
    pasta_pr = os.environ.get("RECEITA_PR", "")
    if pasta_pr and (Path(pasta_pr) / "receita-pr.csv.gz").exists():
        # rápido: usa o arquivo mensal do Paraná (ação "Receita: arquivo mensal do Paraná")
        achados, outras, cnaes, mes = ler_pr(pasta_pr, cidade)
        print(f"Arquivo mensal do PR: {mes}", file=sys.stderr)
    else:
        TMP.mkdir(parents=True, exist_ok=True)
        url, mes = pasta_recente()
        print(f"Dados abertos do CNPJ: {mes}", file=sys.stderr)
        cods = codigos_municipio(url, cidade)
        cnaes = descricoes_cnae(url)
        achados, outras = [], {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            for fut in as_completed([ex.submit(filtrar_arquivo, url, i, cods) for i in range(10)]):
                a, o = fut.result()
                achados += a
                for k, v in o.items():
                    outras[k] = outras.get(k, 0) + v

    na_base = set()
    p = RAIZ / "dados" / "pontos.csv"
    if p.exists():
        na_base = {re.sub(r"[^0-9A-Za-z]", "", r.get("CNPJ", "")).upper() for r in csv.DictReader(open(p, encoding="utf-8"))}

    linhas, fora_nome = [], 0
    ordem = sorted(achados, key=lambda x: x["cnpj"])
    # Consultas em paralelo: cidades grandes (Londrina) têm milhares de CNPJs
    with ThreadPoolExecutor(max_workers=6) as ex:
        dados_rf = list(ex.map(lambda a: receita(a["cnpj"]), ordem))
    for a, rf in zip(ordem, dados_rf):
        nome = rf["razao"] or a["fantasia"]
        if not a["fortes"] and not NOME_RESIDUO.search(f"{nome} {a['fantasia']}"):
            fora_nome += 1
            continue
        codigos = a["fortes"] + [c for c in a["fracos"] if c not in a["fortes"]]
        linhas.append({
            "CNPJ": fmt_cnpj(a["cnpj"]),
            "Razão social": titulo(rf["razao"]),
            "Nome fantasia": titulo(a["fantasia"]),
            "Pessoa física/MEI": "Sim" if rf["pf"] else "",
            "Atividade principal": f"{a['principal']} {cnaes.get(a['principal'], '')}".strip(),
            "Atividades de resíduo": "; ".join(f"{c} {FORTES.get(c) or FRACOS.get(c)}"
                                               + (" (principal)" if c == a["principal"] else "") for c in codigos),
            "Endereço": titulo(a["endereco"]),
            "CEP": a["cep"],
            "Telefone": a["telefone"],
            "Início": a["inicio"],
            "Já na base": "Sim" if a["cnpj"] in na_base else "",
        })

    saida = RAIZ / "coleta" / f"{slug}-receita.csv"
    campos = list(linhas[0].keys()) if linhas else ["CNPJ"]
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    novas = [l for l in linhas if not l["Já na base"]]
    principal = [l for l in novas if "(principal)" in l["Atividades de resíduo"]]
    resumo = [
        f"# {cidade}: empresas de resíduo na Receita Federal ({HOJE})",
        "",
        f"- Base: dados abertos do CNPJ, pasta {mes}",
        f"- Ativas com atividade de resíduo: {len(linhas)} (já na base: {len(linhas) - len(novas)}; novas: {len(novas)})",
        f"- Novas com a atividade de resíduo como principal: {len(principal)}",
        f"- Pessoa física/MEI entre as novas: {sum(1 for l in novas if l['Pessoa física/MEI'])}",
        f"- Descartadas por CNAE fraco sem nome de resíduo: {fora_nome}",
        f"- Não ativas (fora da lista): " + (", ".join(f"{k} {v}" for k, v in sorted(outras.items())) or "nenhuma"),
        "",
        "Lista completa em " + saida.name + ". Conferir com a Jen antes de gravar na planilha.",
    ]
    (RAIZ / "coleta" / f"{slug}-receita-resumo.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    print("\n".join(resumo))


if __name__ == "__main__":
    main()
