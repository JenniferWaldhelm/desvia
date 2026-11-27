"""Procura pontos que parecem ser o mesmo lugar (duplicados prováveis).

Duas comparações, dentro de cada município:
1. a base (aba Pontos, só ativos) com ela mesma;
2. os candidatos da aba Revisão que ainda não estão no site com a base (se o segredo GOOGLE_SA_JSON existir).

Compara o nome por significado (modelo de linguagem pequeno, roda no próprio GitHub, sem custo),
o nome letra a letra, o endereço e a distância entre os pinos. Palavras genéricas ("loja", "farmácia",
"shopping", "Ltda"...) não contam. Só avisa: grava coleta/duplicados.md e coleta/duplicados.csv.
A decisão de marcar "duplicado" na coluna Situação é da Jen.

Uso: python3 coleta/duplicados.py
"""
import csv
import json
import math
import os
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
PLANILHA = "1SdtbIlpzAYfDwxlu4X9d_BmBsOi1a9uF1UByRpUIMps"

# palavras que não ajudam a diferenciar um lugar do outro
VAZIAS = set("""ltda me epp eireli sa s/a cia comercio industria e de da do das dos em
servicos ambientais ambiental transportes transporte residuos reciclagem reciclaveis materiais material
loja lojas filial unidade programa ponto pev farmacia farmacias drogaria drogarias droga shopping center
supermercado supermercados mercado atacado atacadista cooperativa associacao coop posto av avenida rua""".split())


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def nome_limpo(s):
    s = sem_acento(s)
    p = [w for w in re.findall(r"[a-z0-9]+", s) if w not in VAZIAS]
    return " ".join(p) or " ".join(re.findall(r"[a-z0-9]+", s))


def end_limpo(s):
    s = sem_acento(s)
    s = re.sub(r"\(aprox\.?\)|endereco a confirmar.*", " ", s)
    s = re.sub(r"\b(rua|r|avenida|av|rodovia|rod|estrada|travessa|tv|alameda|al|n|no|numero)\b\.?", " ", s)
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
    for la, lo in ((p.get("Lat", ""), p.get("Lng", "")), cache.get(p.get("ID", ""), ("", ""))):
        try:
            return float(str(la).replace(",", ".")), float(str(lo).replace(",", "."))
        except (ValueError, AttributeError):
            continue
    return None


# redes e marcas: duas lojas de redes diferentes no mesmo endereço não são duplicadas,
# e duas lojas da mesma rede só são se o número do endereço bater
REDES = set("""vivo tim claro oi nissei raia drogasil pague menos panvel drogamais mais hiperfarma farmapaulo
muffato supermuffato condor cancao amigao atacadao assai max cobasi petz magazine luiza casas bahia americanas
leroy merlin havan sicoob sicredi caixa itau bradesco santander""".split())


def redes(s):
    return set(re.findall(r"[a-z0-9]+", sem_acento(s))) & REDES


def letras(a, b):
    """Semelhança do nome letra a letra e por palavras (sem as genéricas)."""
    na, nb = nome_limpo(a), nome_limpo(b)
    wa, wb = set(na.split()), set(nb.split())
    jac = len(wa & wb) / len(wa | wb) if wa | wb else 0
    return max(SequenceMatcher(None, na, nb).ratio(), jac)


def comparar(a, b, sim_sig, cache):
    """Devolve (nível, motivo, detalhes) ou None."""
    cn_a, cn_b = re.sub(r"\D", "", a.get("CNPJ", "")), re.sub(r"\D", "", b.get("CNPJ", ""))
    if cn_a and cn_a == cn_b:
        return "certo", "mesmo CNPJ", {}
    if cn_a and cn_b:
        return None  # CNPJs diferentes: estabelecimentos diferentes na Receita
    ra, rb = redes(a["Nome"]), redes(b["Nome"])
    if ra != rb:
        return None  # redes diferentes, ou o shopping e uma loja dentro dele
    sim_let = letras(a["Nome"], b["Nome"])
    if sim_let < 0.6:
        return None  # sem nada em comum além do tipo de lugar (ex.: Vivo e TIM no mesmo shopping)
    ea, eb = end_limpo(a.get("Endereço", "")), end_limpo(b.get("Endereço", ""))
    sim_end = SequenceMatcher(None, ea, eb).ratio() if ea and eb else None
    mesmo_num = bool(numero(a.get("Endereço"))) and numero(a.get("Endereço")) == numero(b.get("Endereço"))
    d = dist(coord(a, cache), coord(b, cache))
    if ra and ea and eb and not mesmo_num:
        return None  # mesma rede, outro número: outra loja
    det = {"Nome (semelhança)": f"{sim_sig:.0%}", "Nome (letras)": f"{sim_let:.0%}",
           "Endereço (semelhança)": "" if sim_end is None else f"{sim_end:.0%}",
           "Distância (m)": "" if d is None else round(d)}
    if sim_sig >= 0.80 and ((sim_end or 0) >= 0.80 and mesmo_num or (d is not None and d < 60)):
        return "provável", "nome parecido e mesmo endereço", det
    if sim_sig >= 0.90 and (not ea or not eb) and (d is None or d < 400):
        return "possível", "nome quase igual; um deles sem endereço", det
    if sim_sig >= 0.65 and (sim_end or 0) >= 0.85 and mesmo_num:
        return "possível", "mesmo endereço e nome parecido", det
    return None


def ler_revisao():
    """Candidatos da aba Revisão que ainda não estão no site (coluna "No site?" diferente de sim)."""
    if not os.environ.get("GOOGLE_SA_JSON"):
        return []
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    from urllib.parse import quote
    cred = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SA_JSON"]), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    r = AuthorizedSession(cred).get(f"https://sheets.googleapis.com/v4/spreadsheets/{PLANILHA}/values/{quote('Revisão')}", timeout=60)
    r.raise_for_status()
    linhas = r.json().get("values", [])
    if not linhas:
        return []
    cab = linhas[0]
    cands = []
    for n, l in enumerate(linhas[1:], start=2):
        d = dict(zip(cab, l + [""] * len(cab)))
        if sem_acento(d.get("No site?", "")).startswith("sim") or not d.get("Nome"):
            continue
        d["_linha"] = n
        cands.append(d)
    return cands


def main():
    pontos = [p for p in csv.DictReader(open(RAIZ / "dados/pontos.csv", encoding="utf-8"))
              if (p.get("Situação") or "ativo").strip().lower() in ("", "ativo")]
    cache = {}
    arq = RAIZ / "dados/coordenadas.csv"
    if arq.exists():
        cache = {c["ID"]: (c["Lat"], c["Lng"]) for c in csv.DictReader(open(arq, encoding="utf-8"))}
    try:
        cands = ler_revisao()
        erro_rev = ""
    except Exception as e:  # noqa: BLE001
        cands, erro_rev = [], f" (aba Revisão não lida: {e})"

    from sentence_transformers import SentenceTransformer
    modelo = SentenceTransformer(MODELO)
    todos = pontos + cands
    vet = modelo.encode([nome_limpo(p["Nome"]) for p in todos], normalize_embeddings=True,
                        batch_size=64, show_progress_bar=False)

    base_cid, cand_cid = defaultdict(list), defaultdict(list)
    for i, p in enumerate(pontos):
        base_cid[sem_acento(p["Município sede"])].append(i)
    for k, c in enumerate(cands):
        cand_cid[sem_acento(c.get("Município sede", ""))].append(len(pontos) + k)

    def linha(onde, a, b, res):
        nivel, motivo, det = res
        return {"Onde": onde, "Nível": nivel, "Motivo": motivo, "Município": b["Município sede"],
                "Ponto 1": a.get("ID") or f"Revisão, linha {a['_linha']}", "Nome 1": a["Nome"], "Endereço 1": a.get("Endereço", ""),
                "ID 2": b["ID"], "Nome 2": b["Nome"], "Endereço 2": b.get("Endereço", ""), **det}

    achados = []
    for cid, idx in base_cid.items():
        for x, i in enumerate(idx):
            for j in idx[x + 1:]:
                res = comparar(pontos[i], pontos[j], float(vet[i] @ vet[j]), cache)
                if res:
                    achados.append(linha("base", pontos[i], pontos[j], res))
        for k in cand_cid.get(cid, []):
            c = todos[k]
            melhor = None
            for j in idx:
                res = comparar(c, pontos[j], float(vet[k] @ vet[j]), cache)
                if res and (melhor is None or res[0] == "certo"):
                    melhor = (res, j)
            if melhor:
                achados.append(linha("Revisão", c, pontos[melhor[1]], melhor[0]))

    ordem = {"certo": 0, "provável": 1, "possível": 2}
    achados.sort(key=lambda x: (x["Onde"] != "base", ordem[x["Nível"]], x["Município"], x["Ponto 1"]))
    campos = ["Onde", "Nível", "Motivo", "Município", "Ponto 1", "Nome 1", "Endereço 1", "ID 2", "Nome 2", "Endereço 2",
              "Nome (semelhança)", "Nome (letras)", "Endereço (semelhança)", "Distância (m)"]
    with open(RAIZ / "coleta/duplicados.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(achados)
    base = [x for x in achados if x["Onde"] == "base"]
    rev = [x for x in achados if x["Onde"] == "Revisão"]
    linhas = ["# Duplicados prováveis", "",
              f"Pontos ativos na base: {len(pontos)}. Candidatos da Revisão fora do site: {len(cands)}{erro_rev}.", "",
              f"- Pares dentro da base: {len(base)}",
              f"- Candidatos da Revisão que parecem já estar na base: {len(rev)}", "",
              "Só aviso. A decisão de marcar \"duplicado\" na coluna Situação (ou de não importar o candidato) é da Jen.", ""]
    for titulo, lst in (("## Dentro da base", base), ("## Candidatos da Revisão", rev)):
        linhas += [titulo, ""] + [
            f"- **{x['Nível']}** ({x['Motivo']}; nome {x.get('Nome (semelhança)', '–')}, endereço {x.get('Endereço (semelhança)') or '–'}, "
            f"{x.get('Distância (m)', '') or '?'} m): {x['Ponto 1']} {x['Nome 1']} | {x['Endereço 1'] or 'sem endereço'}  ×  "
            f"{x['ID 2']} {x['Nome 2']} | {x['Endereço 2'] or 'sem endereço'}" for x in lst] + [""]
    (RAIZ / "coleta/duplicados.md").write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas[:7]))


if __name__ == "__main__":
    main()
