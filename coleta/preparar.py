#!/usr/bin/env python3
"""Etapas 3 e 4 do levantamento (coleta/LEIA-ME.md): junta a coleta automática de uma cidade
(<cidade>.csv e <cidade>-receita.csv), faz as checagens que antes eram feitas à mão e dá uma
nota de confiança a cada candidato.

Checagens: mesmo CNPJ em várias linhas (fica a melhor licença), já na base, CNPJ não ativo,
só AA (regra de 04/11/2026), ponto fora do limite oficial do município, coordenada repetida
(centro da cidade), mesmo endereço, nome em MAIÚSCULAS, resíduo em linguagem simples, MEI sem
endereço, ID provisório.

Uso: python3 coleta/preparar.py "Sarandi"
Saída: coleta/<cidade>-revisao.csv (formato da aba Revisão: colunas de decisão + A:V da aba Pontos)
       coleta/<cidade>-revisao-resumo.md
Não altera o site nem a planilha: a Jen marca na aba Revisão o que entra.
"""
import csv
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HOJE = date.today()
GEOJSON = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-41-mun.json"
CACHE = Path("/tmp/geojs-41-mun.json")
PONTOS = ["ID", "Nome", "CNPJ", "Tipo de ponto", "Serviço", "Resíduos aceitos", "Classe NBR 10004", "Endereço",
          "Município sede", "Lat", "Lng", "Municípios atendidos", "Órgão licença", "Tipo licença", "Nº licença",
          "Validade licença", "Status licença (auto)", "Telefone", "Site/rede", "Fonte", "Data verificação", "Obs"]
DECISAO = ["Confiança", "Por quê", "Funciona?", "Recebe resíduo?", "Nota da Jen"]
EXTRA = ["Atividades (original)", "Situação CNPJ", "Origem"]
PREFIXO = {"londrina": "LDA", "mandaguari": "MGI", "ibipora": "IBI", "maringa": "MGA", "rolandia": "ROL",
           "cambe": "CAM", "apucarana": "APU", "sarandi": "SAR", "arapongas": "ARA", "marialva": "MRV",
           "jandaia do sul": "JDS", "cambira": "CBR"}
NOME_RESIDUO = re.compile(r"cacamba|entulho|recicl|sucata|ferro velho|residuo|ambiental|fossa|desentup|aparas|"
                          r"compost|metais|coleta|pneu|eletron|papel|plastic|vidro|oleo", re.I)
FORTES_LIC = ("LO", "RLO", "LAS", "RLAS", "LAU", "DLAE", "DLAM", "LI", "LP", "RLI", "LI-A")

# Texto técnico (CTF, IAT, CNAE) → linguagem simples. A ordem importa: o primeiro que casar em cada trecho.
SIMPLES = [
    (r"pneu", "Pneus"),
    (r"eletroeletr|eletronic", "Eletroeletrônicos"),
    (r"lampada", "Lâmpadas"),
    (r"pilha|bateria", "Pilhas e baterias"),
    (r"oleo lubrificante|oleo usado|rerrefino|oluc", "Óleo lubrificante usado"),
    (r"oleo (vegetal|de cozinha)|oleos e gorduras", "Óleo de cozinha"),
    (r"construcao civil|entulho|rcc|demolicao|cacamba", "Entulho e resíduos da construção civil"),
    (r"saude|hospitalar|infectante|servicos de saude", "Resíduos de serviços de saúde"),
    (r"sucata|metal|ferro", "Sucata metálica"),
    (r"papel|papelao|aparas", "Papel e papelão"),
    (r"plastic", "Plásticos"),
    (r"vidro", "Vidro"),
    (r"compost|organico|poda", "Resíduos orgânicos e poda"),
    (r"madeira", "Madeira"),
    (r"textil|tecido", "Têxteis"),
    (r"fossa|esgoto|efluente", "Limpa-fossa (esgoto de fossa)"),
    (r"nao perigos|classe ii", "Resíduos não perigosos (Classe II)"),
    (r"perigos|classe i\b", "Resíduos perigosos (Classe I)"),
    (r"coleta de residuo", "Coleta de resíduos"),
    (r"aterro", "Aterro"),
    (r"triagem|reciclagem|recuperacao de materia", "Recicláveis"),
    (r"transporte de residuo|transportadora de cargas em geral e de residuos", "Transporte de resíduos"),
]


def norm(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower().strip()


def digitos(v):
    return re.sub(r"\D", "", v or "")


def data(v):
    try:
        return datetime.strptime(v.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


MINUSC = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "para", "com"}
SUFIXOS = {"ltda": "Ltda", "me": "ME", "epp": "EPP", "eireli": "Eireli", "s/a": "S/A", "sa": "S.A.", "cia": "Cia"}


def _parte_bonita(parte):
    out = []
    for i, p in enumerate(re.split(r"\s+", parte.replace(" - ", " ").strip())):
        b = p.lower()
        chave = b.strip(".,&")
        if chave in SUFIXOS:
            out.append(b.replace(chave, SUFIXOS[chave]))
        elif i and chave in MINUSC:
            out.append(b)
        elif p.isupper() and 1 < len(chave) <= 4 and chave.isalpha() and not re.search(r"[aeiou]", chave):
            out.append(p)  # sigla sem vogal: MGR, GXS
        elif re.fullmatch(r"([a-z]\.)+[a-z]?\.?", b):
            out.append(p.upper())  # iniciais: C. G., J.A.
        else:
            out.append(b[:1].upper() + b[1:])
    return " ".join(out)


def nome_bonito(nome):
    """'RECICLAVEIS CIDADE VERDE LTDA - ME' → 'Reciclaveis Cidade Verde Ltda ME'; 'Aparas De Papeis' → 'Aparas de Papeis'.
    Trata separadamente o nome e o que está entre parênteses."""
    partes = re.split(r"(\([^)]*\)?)", nome.strip())
    out = []
    for parte in partes:
        if not parte.strip():
            continue
        dentro = parte.startswith("(")
        miolo = parte.strip("()") if dentro else parte
        letras = [c for c in miolo if c.isalpha()]
        maiusc = letras and sum(c.isupper() for c in letras) / len(letras) >= 0.8
        titulo = letras and all(w[:1].isupper() for w in miolo.split() if w[:1].isalpha())
        if maiusc or titulo:
            miolo = _parte_bonita(miolo)
        out.append(f"({miolo})" if dentro else miolo.strip())
    return " ".join(out)


def simples(texto):
    achados = []
    for trecho in re.split(r"[;,]", texto or ""):
        t = norm(trecho)
        for rx, frase in SIMPLES:
            if re.search(rx, t):
                if frase not in achados:
                    achados.append(frase)
                break
    return "; ".join(achados)


def tipo_servico(texto):
    t = norm(texto)
    if re.search(r"cacamba|entulho|construcao civil", t) and not re.search(r"aterro|triagem|britag", t):
        return "Coleta e transporte", "Coleta"
    if "transport" in t and not re.search(r"triagem|tratamento|reciclagem|aterro|recupera|disposi", t):
        return "Coleta e transporte", "Transporte"
    if re.search(r"fossa|esgoto", t):
        return "Coleta e transporte", "Coleta"
    if re.search(r"comercio atacadista|sucata|aparas|recuperacao de materia|reciclagem de plastic", t):
        return "Tratamento/destinação final", "Compra de recicláveis"
    if re.search(r"coleta de residuo", t):
        return "Coleta e transporte", "Coleta"
    if "triagem" in t or "armazenamento" in t:
        return "Tratamento/destinação final", "Triagem"
    return "Tratamento/destinação final", "Destinação final"


_FEATS = None


def poligono(cidade):
    global _FEATS
    try:
        from shapely.geometry import shape
    except ImportError:
        return None
    try:
        if not CACHE.exists():
            req = urllib.request.Request(GEOJSON, headers={"User-Agent": "Desvia/1.0"})
            CACHE.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        if _FEATS is None:
            _FEATS = json.loads(CACHE.read_text(encoding="utf-8"))["features"]
        for f in _FEATS:
            if norm(f["properties"].get("name", "")) == norm(cidade):
                return shape(f["geometry"])
    except Exception as e:  # noqa: BLE001
        print(f"Limite do município indisponível: {e}", file=sys.stderr)
    return None


def melhor_licenca(linhas):
    """Entre várias licenças do mesmo CNPJ: prefere as de operação válidas e, nelas, a de validade mais longa."""
    def peso(l):
        t = l["Tipo licença"].upper()
        v = data(l["Validade licença"]) or date(1900, 1, 1)
        oper = t in ("LO", "RLO", "LAS", "RLAS", "LAU", "DLAE", "DLAM")
        return (bool(t) and t != "AA", oper, v >= HOJE, v)
    return max(linhas, key=peso)


def principal(cidade):
    slug = re.sub(r"[^a-z0-9]+", "-", norm(cidade)).strip("-")
    base = list(csv.DictReader(open(RAIZ / "dados" / "pontos.csv", encoding="utf-8")))
    na_base = {digitos(p["CNPJ"]): p["ID"] for p in base if digitos(p["CNPJ"])}
    candidatos, fora = {}, Counter()

    # etapa 1: IAT + CTF (uma linha por licença/atividade) → uma por CNPJ
    a1 = RAIZ / "coleta" / f"{slug}.csv"
    grupos = defaultdict(list)
    if a1.exists():
        for l in csv.DictReader(open(a1, encoding="utf-8")):
            grupos[digitos(l["CNPJ"])].append(l)
    for cnpj, ls in grupos.items():
        l = dict(melhor_licenca(ls))
        ativ = "; ".join(sorted({x["Resíduos aceitos"] for x in ls if x["Resíduos aceitos"]}))
        if cnpj in na_base or l.get("Já na base"):
            fora["já na base"] += 1
            continue
        sit = (l.get("Situação CNPJ") or "").lower()
        if sit and sit not in ("ativa", "não consultada"):
            fora[f"CNPJ {sit}"] += 1
            continue
        if l["Tipo licença"].upper() == "AA":
            fora["só Autorização Ambiental (AA)"] += 1
            continue
        l["Atividades (original)"], l["Situação CNPJ"], l["Origem"] = ativ, l.get("Situação CNPJ", ""), "IAT/CTF"
        l["_cnae_principal"], l["_ctf"] = False, "CTF/IBAMA" in l["Fonte"]
        candidatos[cnpj] = l

    # etapa 2: Receita por atividade (já com licença do IAT e CTF conferidos)
    a2 = RAIZ / "coleta" / f"{slug}-receita.csv"
    if a2.exists():
        for r in csv.DictReader(open(a2, encoding="utf-8")):
            cnpj = digitos(r["CNPJ"])
            if cnpj in na_base or r.get("Já na base"):
                fora["já na base"] += 1
                continue
            if cnpj in candidatos:
                c = candidatos[cnpj]
                c["_cnae_principal"] = c["_cnae_principal"] or "(principal)" in r["Atividades de resíduo"]
                c["Telefone"] = c["Telefone"] or r["Telefone"]
                continue
            lic = (r.get("IAT licença") or "").split(" ", 1)
            tl, num = (lic[0], lic[1]) if len(lic) == 2 else ("", "")
            if tl.upper() == "AA":
                fora["só Autorização Ambiental (AA)"] += 1
                continue
            mei = bool(r["Pessoa física/MEI"])
            nome = r["Nome fantasia"] or r["Razão social"]
            if r["Nome fantasia"] and r["Razão social"] and norm(r["Nome fantasia"]) not in norm(r["Razão social"]):
                nome = f"{r['Nome fantasia']} ({r['Razão social']})"
            texto = " ; ".join([r["Atividades de resíduo"], r.get("IAT atividades", "")])
            tipo, serv = tipo_servico(texto + " " + nome)
            candidatos[cnpj] = {
                "ID": "", "Nome": nome, "CNPJ": r["CNPJ"], "Tipo de ponto": tipo, "Serviço": serv,
                "Resíduos aceitos": "", "Classe NBR 10004": "", "Endereço": "" if mei else r["Endereço"],
                "Município sede": cidade, "Lat": "", "Lng": "", "Municípios atendidos": cidade,
                "Órgão licença": "IAT" if tl else "", "Tipo licença": tl, "Nº licença": num,
                "Validade licença": r.get("IAT validade", ""), "Status licença (auto)": "", "Telefone": r["Telefone"],
                "Site/rede": "", "Fonte": "Receita Federal" + (", IAT GeoPR" if tl else "") + (", CTF/IBAMA" if r.get("CTF/IBAMA") else ""),
                "Data verificação": HOJE.strftime("%d/%m/%Y"),
                "Obs": "Empresário individual: endereço não publicado." if mei else "",
                "Atividades (original)": texto.strip(" ;"), "Situação CNPJ": "Ativa", "Origem": "Receita",
                "_cnae_principal": "(principal)" in r["Atividades de resíduo"], "_ctf": bool(r.get("CTF/IBAMA")),
                "_mei": mei,
            }

    # serviço de água e esgoto fica de fora (LEIA-ME, etapa 1)
    for cnpj in [k for k, c in candidatos.items() if re.search(r"saneamento|aguas de |sanepar|samae|servico autonomo de agua", norm(c["Nome"]))]:
        candidatos.pop(cnpj)
        fora["serviço de água e esgoto"] += 1

    # recusados pela Jen em revisões anteriores (coleta/recusados.csv: CNPJ, Nome, Motivo, Data)
    rec = RAIZ / "coleta" / "recusados.csv"
    if rec.exists():
        for r in csv.DictReader(open(rec, encoding="utf-8")):
            if candidatos.pop(digitos(r["CNPJ"]), None):
                fora["recusado antes pela Jen"] += 1

    pol = poligono(cidade)
    coords = Counter((c["Lat"], c["Lng"]) for c in candidatos.values() if c["Lat"])
    ends = defaultdict(list)
    for cnpj, c in candidatos.items():
        if c["Endereço"]:
            ends[norm(re.sub(r"\s+", " ", c["Endereço"]))].append(cnpj)

    # próximo ID: maior número da cidade na base (a planilha pode ter IDs mais novos: conferir antes de gravar)
    pref = PREFIXO.get(norm(cidade), norm(cidade)[:3].upper())
    usados = [int(m.group(1)) for p in base if (m := re.match(rf"{pref}-(\d+)$", p["ID"]))]
    prox = max(usados, default=0) + 1

    saida = []
    for cnpj, c in sorted(candidatos.items(), key=lambda kv: kv[1]["Nome"]):
        motivos, pts = [], 0
        c["Nome"] = nome_bonito(c["Nome"])
        txt = simples(c["Atividades (original)"]) or simples(c["Nome"])
        c["Resíduos aceitos"] = txt or ""
        if not txt:
            motivos.append("resíduo não identificado: escrever à mão")
        if c["Tipo licença"] and c["Tipo licença"].upper() in FORTES_LIC:
            v = data(c["Validade licença"])
            motivos.append(f"licença {c['Tipo licença']} {'válida' if v and v >= HOJE else 'vencida'}")
            if c["Tipo licença"].upper() in ("LP", "LI", "LI-A"):
                pts -= 1
                motivos.append("só LP/LI: ainda não pode funcionar")
            else:
                pts += 2 if v and v >= HOJE else 1
        elif c.get("_ctf"):
            pts += 1
            motivos.append("só CTF/IBAMA")
        else:
            motivos.append("sem licença nas bases")
        if c.get("_cnae_principal"):
            pts += 2
            motivos.append("atividade de resíduo é a principal")
        if NOME_RESIDUO.search(norm(c["Nome"])):
            pts += 1
            motivos.append("nome indica resíduo")
        if c["Telefone"]:
            pts += 1
        else:
            motivos.append("sem telefone")
        if c.get("_mei"):
            pts -= 1
            motivos.append("MEI")
        if c["Lat"] and coords[(c["Lat"], c["Lng"])] >= 3:
            c["Lat"] = c["Lng"] = ""
            motivos.append("coordenada repetida (centro da cidade): apagada")
        if c["Lat"] and pol is not None:
            from shapely.geometry import Point
            if not pol.contains(Point(float(c["Lng"]), float(c["Lat"]))):
                motivos.append("coordenada FORA do município: conferir sede")
                pts -= 1
        if c["Endereço"]:
            iguais = [x for x in ends[norm(re.sub(r"\s+", " ", c["Endereço"]))] if x != cnpj]
            if iguais:
                motivos.append("mesmo endereço de " + ", ".join(candidatos[x]["Nome"][:30] for x in iguais[:2]) + ": juntar?")
        c["Confiança"] = "Alta" if pts >= 4 else "Média" if pts == 3 else "Baixa"
        c["Por quê"] = "; ".join(motivos)
        saida.append(c)

    ordem = {"Alta": 0, "Média": 1, "Baixa": 2}
    saida.sort(key=lambda c: (ordem[c["Confiança"]], c["Nome"]))
    for c in saida:
        if c["Confiança"] != "Baixa":
            c["ID"] = f"{pref}-{prox:03d}"
            prox += 1

    arq = RAIZ / "coleta" / f"{slug}-revisao.csv"
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DECISAO + PONTOS + EXTRA, extrasaction="ignore")
        w.writeheader()
        for c in saida:
            w.writerow({**c, "Funciona?": "", "Recebe resíduo?": "", "Nota da Jen": ""})

    n = Counter(c["Confiança"] for c in saida)
    resumo = [f"# {cidade}: candidatos para revisão ({HOJE:%d/%m/%Y})", "",
              f"- Candidatos: {len(saida)} (Alta {n['Alta']}, Média {n['Média']}, Baixa {n['Baixa']})",
              f"- Para a Jen conferir (Alta + Média): {n['Alta'] + n['Média']}",
              "- Fora antes da nota: " + (", ".join(f"{k} {v}" for k, v in fora.most_common()) or "nenhum"),
              f"- Limite oficial do município: {'conferido' if pol is not None else 'NÃO conferido (sem shapely ou geojson)'}",
              f"- IDs provisórios a partir de {pref}-{max(usados, default=0) + 1:03d} (conferir a coluna A da planilha antes de gravar)",
              "", f"Lista em {arq.name}. Nada foi gravado na planilha."]
    (RAIZ / "coleta" / f"{slug}-revisao-resumo.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    print("\n".join(resumo))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Uso: python3 coleta/preparar.py "Nome do município"')
    principal(sys.argv[1].strip())
