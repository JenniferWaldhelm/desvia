"""Procura pontos que parecem ser o mesmo lugar (duplicados prováveis) na base.

Compara, dentro de cada município, o nome (por significado, com um modelo de linguagem pequeno
que roda no próprio GitHub), o endereço e a distância entre os pinos. Só avisa: grava
coleta/duplicados.md e coleta/duplicados.csv para a Jen decidir. Não muda a planilha.

Uso: python3 coleta/duplicados.py
"""
import csv
import math
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# palavras que não ajudam a diferenciar uma empresa da outra
VAZIAS = set("""ltda me epp eireli sa s/a s a cia comercio comércio industria indústria e de da do das dos
servicos serviços ambientais ambiental transportes transporte residuos resíduos reciclagem reciclaveis
recicláveis materiais material loja filial unidade programa ponto pev""".split())


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def nome_limpo(s):
    s = sem_acento(re.sub(r"\(.*?\)", " ", s or "") + " " + " ".join(re.findall(r"\((.*?)\)", s or "")))
    p = [w for w in re.findall(r"[a-z0-9]+", s) if w not in VAZIAS]
    return " ".join(p) or sem_acento(s)


def end_limpo(s):
    s = sem_acento(s)
    s = re.sub(r"\b(rua|r|avenida|av|rodovia|rod|estrada|travessa|tv|alameda|al|n|no|numero)\b\.?", " ", s)
    s = re.sub(r"\(aprox\.?\)|endereco a confirmar.*", " ", s)
    return " ".join(re.findall(r"[a-z0-9]+", s))


def numero(s):
    m = re.search(r"\b(\d{1,5})\b", s or "")
    return m.group(1) if m else ""


def dist(a, b):
    if not (a and b):
        return None
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def coord(p, cache):
    for la, lo in ((p["Lat"], p["Lng"]), cache.get(p["ID"], ("", ""))):
        try:
            return float(la.replace(",", ".")), float(lo.replace(",", "."))
        except (ValueError, AttributeError):
            continue
    return None


def main():
    pontos = [p for p in csv.DictReader(open(RAIZ / "dados/pontos.csv", encoding="utf-8"))
              if (p.get("Situação") or "ativo").strip().lower() in ("", "ativo")]
    cache = {}
    arq = RAIZ / "dados/coordenadas.csv"
    if arq.exists():
        cache = {c["ID"]: (c["Lat"], c["Lng"]) for c in csv.DictReader(open(arq, encoding="utf-8"))}

    from sentence_transformers import SentenceTransformer
    modelo = SentenceTransformer(MODELO)
    nomes = [nome_limpo(p["Nome"]) for p in pontos]
    vet = modelo.encode(nomes, normalize_embeddings=True, batch_size=64, show_progress_bar=False)

    por_cidade = defaultdict(list)
    for i, p in enumerate(pontos):
        por_cidade[sem_acento(p["Município sede"])].append(i)

    achados = []
    for idx in por_cidade.values():
        for a_i, i in enumerate(idx):
            for j in idx[a_i + 1:]:
                a, b = pontos[i], pontos[j]
                cn_a, cn_b = re.sub(r"\D", "", a["CNPJ"]), re.sub(r"\D", "", b["CNPJ"])
                sim_nome = float(vet[i] @ vet[j])
                ea, eb = end_limpo(a["Endereço"]), end_limpo(b["Endereço"])
                sim_end = SequenceMatcher(None, ea, eb).ratio() if ea and eb else None
                mesmo_num = bool(numero(a["Endereço"])) and numero(a["Endereço"]) == numero(b["Endereço"])
                d = dist(coord(a, cache), coord(b, cache))
                motivo, nivel = None, None
                if cn_a and cn_a == cn_b:
                    motivo, nivel = "mesmo CNPJ", "certo"
                elif cn_a and cn_b:
                    continue  # CNPJs diferentes: estabelecimentos diferentes na Receita
                elif sim_nome >= 0.80 and ((sim_end or 0) >= 0.80 and mesmo_num or (d is not None and d < 60)):
                    motivo, nivel = "nome parecido e mesmo endereço", "provável"
                elif sim_nome >= 0.92 and (not ea or not eb) and (d is None or d < 400):
                    motivo, nivel = "nome quase igual; um deles sem endereço", "possível"
                elif sim_nome >= 0.60 and d is not None and d < 25 and (sim_end or 0) >= 0.6:
                    motivo, nivel = "mesmo lugar no mapa e nome parecido", "possível"
                elif (sim_end or 0) >= 0.92 and mesmo_num and sim_nome >= 0.55:
                    motivo, nivel = "mesmo endereço e nome parecido", "possível"
                if motivo:
                    achados.append({
                        "Nível": nivel, "Motivo": motivo, "Município": a["Município sede"],
                        "ID 1": a["ID"], "Nome 1": a["Nome"], "Endereço 1": a["Endereço"], "Fonte 1": a["Fonte"],
                        "ID 2": b["ID"], "Nome 2": b["Nome"], "Endereço 2": b["Endereço"], "Fonte 2": b["Fonte"],
                        "Nome (semelhança)": f"{sim_nome:.0%}",
                        "Endereço (semelhança)": "" if sim_end is None else f"{sim_end:.0%}",
                        "Distância (m)": "" if d is None else round(d)})

    ordem = {"certo": 0, "provável": 1, "possível": 2}
    achados.sort(key=lambda x: (ordem[x["Nível"]], x["Município"], x["ID 1"]))
    with open(RAIZ / "coleta/duplicados.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(achados[0].keys()) if achados else ["Nível"])
        w.writeheader()
        w.writerows(achados)
    cont = defaultdict(int)
    for x in achados:
        cont[x["Nível"]] += 1
    linhas = ["# Duplicados prováveis na base", "",
              f"Pontos ativos comparados: {len(pontos)}. Pares achados: {len(achados)} "
              f"(certos: {cont['certo']}, prováveis: {cont['provável']}, possíveis: {cont['possível']}).", "",
              "Só aviso. A decisão de marcar \"duplicado\" na coluna Situação é da Jen.", ""]
    for x in achados:
        linhas.append(f"- **{x['Nível']}** ({x['Motivo']}; nome {x['Nome (semelhança)']}, endereço {x['Endereço (semelhança)'] or '–'}, "
                      f"{x['Distância (m)'] or '?'} m): {x['ID 1']} {x['Nome 1']} | {x['Endereço 1'] or 'sem endereço'}  ×  "
                      f"{x['ID 2']} {x['Nome 2']} | {x['Endereço 2'] or 'sem endereço'}")
    (RAIZ / "coleta/duplicados.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas[:6]))


if __name__ == "__main__":
    main()
