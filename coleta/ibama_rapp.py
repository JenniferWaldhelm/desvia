#!/usr/bin/env python3
"""Tipos de resíduo declarados ao IBAMA (RAPP) pelas empresas do Paraná.

Baixa as bases abertas do RAPP, fica só com o Paraná e cruza pelo CNPJ com a
base do Desvia (dados/pontos.csv). Não altera o site nem a planilha: grava
arquivos para a Jen revisar.

Bases:
  - Resíduos Sólidos – Destinador   (quem recebe e destina; o principal)
  - Resíduos Sólidos – Armazenador  (quem armazena)
  - Resíduos Sólidos – Gerador      (quem gera; serve para achar demanda)
  - Produtos Reciclados             (formulário de 2006 a 2013)
  - Pilhas e Baterias – Reciclador
  - Pilhas e Baterias – Fabricante (destinação)

O IBAMA não publica a lista de colunas dessas bases. O script reconhece as
colunas pelo nome do cabeçalho e anota no resumo o que encontrou em cada base,
para corrigir as regras se alguma coluna vier com outro nome.

Uso: python3 coleta/ibama_rapp.py [pasta_com_arquivos_ja_baixados]
Saída: coleta/ibama-rapp-pr.csv            uma linha por resíduo declarado no PR
       coleta/ibama-residuos-empresas.csv  uma linha por empresa (CNPJ), com o que declarou
       coleta/ibama-rapp-resumo.md
"""
import csv
import io
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "gerador"))
csv.field_size_limit(10**8)

UA = {"User-Agent": "Desvia/1.0 (+https://desvia.eco.br/)"}
BLOB = "https://stibamadadosabertosprd.blob.core.windows.net/dados-abertos/dados/"
PORTAL = "https://dadosabertos.ibama.gov.br/dados/"

# nome curto, papel da empresa na base, caminho do arquivo (tenta o blob e depois o portal)
BASES = [
    ("destinador", "destinador", "RAPP/residuoSolidosDestinador/relatorio.csv"),
    ("armazenador", "armazenador", "RAPP/residuoSolidosArmazenador/relatorio.csv"),
    ("gerador", "gerador", "RAPP/residuoSolidosGerador/relatorio.csv"),
    ("produtos-reciclados", "reciclador", "RAPP/produtosReciclados/relatorio.csv"),
    ("pilhas-reciclador", "reciclador", "PILHAS_BATERIAS_RECICLADOR/pilhas_baterias_reciclador.csv"),
    ("pilhas-fabricante-destinacao", "destinador",
     "PILHAS_BATERIAS_FABRICANTES/pilhas_baterias_destinacao_fabricantes/pilhas_baterias_destinacao_fabricantes_todos_anos.csv.zip"),
]

# Campos que o script procura, com as palavras que identificam a coluna no cabeçalho
CAMPOS = {
    "cnpj": [r"cnpj", r"cpf"],
    "razao": [r"razao", r"nome empresa", r"nome do estabelecimento", r"^nome$", r"empresa"],
    "uf": [r"^uf\b", r"\buf\b", r"estado", r"sigla uf"],
    "municipio": [r"municipio", r"cidade"],
    "codigo_residuo": [r"codigo.*residuo", r"residuo.*codigo", r"cod.*residuo"],
    "residuo": [r"descricao.*residuo", r"residuo.*descricao", r"tipo.*residuo", r"^residuo", r"residuo",
                r"descricao", r"produto", r"tipo de pilha", r"tipo"],
    "classe": [r"periculosidade", r"classifica", r"classe"],
    "ano": [r"^ano", r"ano\b", r"exercicio"],
    "quantidade": [r"quantidade", r"\bqtd", r"peso", r"massa"],
    "unidade": [r"unidade", r"\bund\b"],
    "destinacao": [r"tipo.*destina", r"destinacao", r"tratamento", r"armazenamento", r"finalidade", r"destino"],
}
NAO_SAO = {  # o que não pode ser confundido com cada campo
    "residuo": r"cnpj|codigo|cod\b|quantidade|unidade|ano|classif|periculos|municipio|uf\b|destina|tratamento",
    "razao": r"cnpj|municipio|uf\b|residuo|codigo",
    "destinacao": r"cnpj|razao|nome|municipio|uf\b|codigo|quantidade",
    "uf": r"cnpj|codigo",
    "municipio": r"codigo|cod\b|ibge",
    "ano": r"cnpj|municipio",
}
# Palavras que indicam a "outra" empresa da linha (ex.: na base de destinador, o gerador)
OUTROS_PAPEIS = {
    "destinador": ["gerador", "armazenador", "origem"],
    "armazenador": ["gerador", "destinador", "destino"],
    "gerador": ["destinador", "armazenador", "destino"],
    "reciclador": ["fornecedor", "origem", "gerador"],
}


def norm(t):
    t = unicodedata.normalize("NFD", str(t or ""))
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn").lower().replace("_", " ")).strip()


def digitos(v):
    d = re.sub(r"\D", "", str(v or ""))
    return d.zfill(14) if 11 < len(d) <= 14 else d


def fmt_cnpj(d):
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else d


def baixar(caminho, pasta):
    """Devolve o caminho local do arquivo (baixa se ainda não existir)."""
    destino = pasta / caminho.replace("/", "__")
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    erros = []
    for base in (BLOB, PORTAL):
        for i in range(3):
            try:
                req = urllib.request.Request(base + caminho, headers=UA)
                with urllib.request.urlopen(req, timeout=900) as r, open(destino, "wb") as f:
                    while bloco := r.read(1 << 20):
                        f.write(bloco)
                return destino
            except Exception as e:  # noqa: BLE001
                erros.append(f"{base}: {e}")
                time.sleep(3 * (i + 1))
    raise RuntimeError("; ".join(erros[-2:]))


def abrir_texto(arq):
    """Abre CSV (ou o primeiro CSV de um .zip) como texto, detectando a codificação."""
    if zipfile.is_zipfile(arq):
        z = zipfile.ZipFile(arq)
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        abrir = lambda: z.open(nome)  # noqa: E731
    else:
        abrir = lambda: open(arq, "rb")  # noqa: E731
    with abrir() as b:
        amostra = b.read(2_000_000)
    amostra = amostra[:amostra.rfind(b"\n") + 1] or amostra  # não corta caractere no meio
    bruto = abrir()
    for cod in ("utf-8-sig", "cp1252"):
        try:
            amostra.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    texto = io.TextIOWrapper(bruto, encoding=cod, errors="replace", newline="")
    primeira = amostra.decode(cod, errors="replace").splitlines()[0] if amostra else ""
    sep = max((";", ",", "\t", "|"), key=primeira.count)
    return texto, sep, cod


def mapear(cab, papel):
    """Escolhe, para cada campo, a coluna do cabeçalho. Prefere a coluna da empresa do papel da base."""
    ncab = [norm(c) for c in cab]
    outros = OUTROS_PAPEIS.get(papel, [])
    achado = {}
    for campo, padroes in CAMPOS.items():
        candidatos = []
        for i, c in enumerate(ncab):
            if i in achado.values():
                continue
            if campo in NAO_SAO and re.search(NAO_SAO[campo], c) and not (campo == "residuo" and re.search(r"descri", c) and "residuo" in c):
                continue
            for prio, p in enumerate(padroes):
                if re.search(p, c):
                    # coluna da outra empresa da linha fica por último
                    peso = (1 if any(o in c for o in outros) else 0, 0 if papel in c else 1, prio, i)
                    candidatos.append((peso, i))
                    break
        if candidatos:
            achado[campo] = min(candidatos)[1]
    # colunas da outra empresa (para saber de quem veio ou para onde foi)
    for i, c in enumerate(ncab):
        if any(o in c for o in outros):
            if "cnpj" in c and "outro_cnpj" not in achado:
                achado["outro_cnpj"] = i
            elif re.search(r"razao|nome", c) and "outro_razao" not in achado:
                achado["outro_razao"] = i
    return achado


def categorias_desvia():
    try:
        import gerar
        return [(slug, nome, chaves) for slug, _, nome, chaves in gerar.CATEGORIAS]
    except Exception:  # noqa: BLE001
        return []


def main():
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/ibama-rapp")
    pasta.mkdir(parents=True, exist_ok=True)

    base_desvia = {}
    with open(RAIZ / "dados" / "pontos.csv", encoding="utf-8") as f:
        for p in csv.DictReader(f):
            d = digitos(p.get("CNPJ"))
            if len(d) == 14:
                base_desvia.setdefault(d, []).append(p)
    cats = categorias_desvia()

    linhas, diag, avisos = [], [], []
    for nome, papel, caminho in BASES:
        try:
            arq = baixar(caminho, pasta)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"{nome}: não baixou ({e})")
            continue
        texto, sep, cod = abrir_texto(arq)
        leitor = csv.reader(texto, delimiter=sep)
        cab = next(leitor, [])
        m = mapear(cab, papel)
        diag.append((nome, papel, arq.stat().st_size, sep, cod, cab, m))
        if "uf" not in m and "municipio" not in m:
            avisos.append(f"{nome}: sem coluna de UF ou município; base ignorada")
            continue
        n_total = n_pr = 0
        for row in leitor:
            n_total += 1
            if len(row) < len(cab):
                row += [""] * (len(cab) - len(row))
            g = lambda k: row[m[k]].strip() if k in m else ""  # noqa: E731
            uf = norm(g("uf"))
            if uf not in ("pr", "parana"):
                continue
            n_pr += 1
            cnpj = digitos(g("cnpj"))
            linhas.append({
                "Base": nome, "Papel": papel, "CNPJ": fmt_cnpj(cnpj), "_cnpj": cnpj, "Razão social": g("razao"),
                "Município": g("municipio"), "Ano": g("ano"), "Código resíduo": g("codigo_residuo"),
                "Resíduo declarado": ("Pilhas e baterias: " if nome.startswith("pilhas") and g("residuo") else "") + g("residuo"), "Classe": g("classe"), "Quantidade": g("quantidade"),
                "Unidade": g("unidade"), "Destinação/tratamento": g("destinacao"),
                "Outra empresa (CNPJ)": fmt_cnpj(digitos(g("outro_cnpj"))), "Outra empresa": g("outro_razao"),
                "No Desvia": "; ".join(p["ID"] for p in base_desvia.get(cnpj, [])),
            })
        texto.close()
        diag[-1] = diag[-1] + (n_total, n_pr)

    # 1) todas as linhas do PR
    campos = [k for k in (linhas[0] if linhas else {}) if not k.startswith("_")]
    with open(RAIZ / "coleta" / "ibama-rapp-pr.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos or ["Base"], extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)

    # 2) uma linha por empresa
    por = defaultdict(list)
    for l in linhas:
        if l["_cnpj"]:
            por[l["_cnpj"]].append(l)
    saida = []
    for cnpj, ls in por.items():
        res = Counter(re.sub(r"\s+", " ", l["Resíduo declarado"]).strip(" .;") for l in ls if l["Resíduo declarado"])
        cods = sorted({l["Código resíduo"] for l in ls if l["Código resíduo"]})
        dest = Counter(l["Destinação/tratamento"] for l in ls if l["Destinação/tratamento"])
        anos = sorted({l["Ano"][:4] for l in ls if re.match(r"\d{4}", l["Ano"])})
        papeis = sorted({l["Papel"] for l in ls})
        texto_res = norm(" ".join(res))
        sugeridas = [nome for _, nome, chaves in cats if any(c in texto_res for c in chaves)]
        desvia = base_desvia.get(cnpj, [])
        aceitos_hoje = " | ".join(p["Resíduos aceitos"] for p in desvia)
        ja_tem = norm(aceitos_hoje)
        novas = [n for _, n, chaves in cats if n in sugeridas and not any(c in ja_tem for c in chaves)] if desvia else []
        saida.append({
            "CNPJ": fmt_cnpj(cnpj),
            "Razão social": Counter(l["Razão social"] for l in ls if l["Razão social"]).most_common(1)[0][0] if any(l["Razão social"] for l in ls) else "",
            "Município": Counter(l["Município"] for l in ls if l["Município"]).most_common(1)[0][0] if any(l["Município"] for l in ls) else "",
            "Papel no RAPP": ", ".join(papeis),
            "Anos": f"{anos[0]}–{anos[-1]}" if len(anos) > 1 else "".join(anos),
            "Nº de tipos de resíduo": len(res),
            "Resíduos declarados (mais frequentes)": "; ".join(r for r, _ in res.most_common(25)),
            "Códigos de resíduo": ", ".join(cods[:40]),
            "Destinação/tratamento": "; ".join(d for d, _ in dest.most_common(8)),
            "Categorias do Desvia sugeridas": ", ".join(sugeridas),
            "No Desvia (ID)": "; ".join(p["ID"] for p in desvia),
            "Resíduos aceitos hoje no Desvia": aceitos_hoje,
            "Categorias que faltam no Desvia": ", ".join(novas),
        })
    # quem já está no Desvia primeiro; depois quem recebe resíduo de terceiros
    ordem = {"destinador": 0, "armazenador": 1, "reciclador": 2, "gerador": 3}
    saida.sort(key=lambda s: (0 if s["No Desvia (ID)"] else 1,
                              min(ordem.get(p, 9) for p in s["Papel no RAPP"].split(", ")), s["Município"], s["Razão social"]))
    campos2 = ["CNPJ", "Razão social", "Município", "Papel no RAPP", "Anos", "Nº de tipos de resíduo",
               "Resíduos declarados (mais frequentes)", "Códigos de resíduo", "Destinação/tratamento",
               "Categorias do Desvia sugeridas", "No Desvia (ID)", "Resíduos aceitos hoje no Desvia",
               "Categorias que faltam no Desvia"]
    with open(RAIZ / "coleta" / "ibama-residuos-empresas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos2)
        w.writeheader()
        w.writerows(saida)

    # 3) resumo
    no_desvia = [s for s in saida if s["No Desvia (ID)"]]
    receptores = [s for s in saida if not s["No Desvia (ID)"] and s["Papel no RAPP"] != "gerador"]
    cinza = [s for s in saida if "cinza" in norm(s["Resíduos declarados (mais frequentes)"]) and s["Papel no RAPP"] != "gerador"]
    r = [f"# RAPP/IBAMA no Paraná ({date.today():%d/%m/%Y})", "",
         f"- Linhas do Paraná: {len(linhas)}",
         f"- Empresas (CNPJ) do Paraná: {len(saida)}",
         f"- Já estão no Desvia: {len(no_desvia)} "
         f"({sum(1 for s in no_desvia if s['Categorias que faltam no Desvia'])} com categorias que faltam no cadastro)",
         f"- Recebem resíduo de terceiros e não estão no Desvia: {len(receptores)}",
         f"- Recebem cinza (destinador, armazenador ou reciclador): {len(cinza)}", ""]
    if avisos:
        r += ["## Avisos", ""] + [f"- {a}" for a in avisos] + [""]
    r += ["## Colunas reconhecidas em cada base", "",
          "Confira se cada campo caiu na coluna certa. Se não, ajuste CAMPOS ou NAO_SAO no script.", ""]
    for d in diag:
        nome, papel, tam, sep, cod, cab, m = d[:7]
        tot, pr = (d[7], d[8]) if len(d) > 7 else ("?", "?")
        r += [f"### {nome} ({papel})", "",
              f"- Arquivo: {tam / 1e6:.1f} MB, separador `{sep}`, codificação {cod}",
              f"- Linhas: {tot}; no Paraná: {pr}",
              "- Campos: " + "; ".join(f"{k} → `{cab[i]}`" for k, i in m.items()),
              "- Cabeçalho completo: " + " | ".join(f"`{c}`" for c in cab), ""]
    (RAIZ / "coleta" / "ibama-rapp-resumo.md").write_text("\n".join(r), encoding="utf-8")
    print("\n".join(r[:8]))


if __name__ == "__main__":
    main()
