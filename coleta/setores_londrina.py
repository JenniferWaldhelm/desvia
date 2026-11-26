"""Setores da coleta de Londrina (comum e seletiva) para a caixa "Em que dia passa a coleta na sua rua?".

Fonte: CMTU Londrina, serviço CMTUDirOperServicos do GeoLondrina (camada 1 = Coleta Domiciliar, 2 = Coleta Seletiva).
Gera dados/setores-londrina.geojson no mesmo formato de dados/setores-maringa.geojson
(tipo, turno, dias, setor) e acrescenta horario, cooperativa e telefone quando existem.

Uso:
  python3 coleta/setores_londrina.py                      # baixa do GeoLondrina
  python3 coleta/setores_londrina.py comum.geojson seletiva.geojson   # usa arquivos já baixados
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

SERVICO = "https://geo.londrina.pr.gov.br/server/rest/services/CMTUInternet/CMTUDirOperServicos/MapServer"
CONSULTA = "/{camada}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
SAIDA = Path(__file__).resolve().parent.parent / "dados" / "setores-londrina.geojson"
FONTE = "CMTU Londrina (GeoLondrina, setores da coleta domiciliar e da coleta seletiva)"

DIA = {"SEGUNDA": "2ª", "TERÇA": "3ª", "TERCA": "3ª", "QUARTA": "4ª", "QUINTA": "5ª", "SEXTA": "6ª",
       "SABADO": "Sábado", "SÁBADO": "Sábado"}
TODOS = "2ª, 3ª, 4ª, 5ª, 6ª e Sábado"

# Telefones com erro de digitação no mapa da CMTU: vale o que aparece na maioria dos setores da cooperativa.
# Coopermudança: número confirmado pela Jen em 26/11/2026 (o celular do mapa da CMTU está desatualizado).
TELEFONE = {
    "COOCEPEVE": "(43) 3322-1450 / (43) 98412-8452",
    "COOPER REFUM": "(43) 3037-6973 / (43) 99914-2693",
    "COOPER REGIÃO": "(43) 3341-0398 / (43) 3321-6992",
    "COOPERMUDANÇA": "(43) 3339-2199 / (43) 99672-3414",
    "COOPERNORTH": "(43) 3339-0617 / (43) 98403-8325",
    "COOPEROESTE": "(43) 3348-8838 / (43) 99640-1433",
    "ECORECIN": "(43) 3326-1205 / (43) 98424-7738",
}
NOME = {"COOCEPEVE": "Cepeve", "COOPER REFUM": "Cooper Refum", "COOPER REGIÃO": "Cooper Região",
        "COOPERMUDANÇA": "Coopermudança", "COOPERNORTH": "Coopernorth", "COOPEROESTE": "Cooperoeste",
        "ECORECIN": "Ecorecin"}


def lista(dias):
    return dias[0] if len(dias) == 1 else ", ".join(dias[:-1]) + " e " + dias[-1]


def dias_comum(freq):
    parte = freq.split("-")[0].strip().upper()
    if parte.startswith("DIARIO") or parte.startswith("DIÁRIO"):
        return TODOS
    return lista([DIA[d.strip()] for d in parte.split(",") if d.strip()])


def horario(h):
    m = re.search(r"(\d{1,2}):(\d{2})", h or "")
    if not m:
        return ""
    hh, mm = int(m.group(1)), m.group(2)
    return f"a partir das {hh}h" + ("" if mm == "00" else mm)


def arred(coords):
    """5 casas decimais (cerca de 1 m), sem pontos repetidos em seguida."""
    out = []
    for anel in coords:
        novo = []
        for x, y in anel:
            p = [round(x, 5), round(y, 5)]
            if not novo or novo[-1] != p:
                novo.append(p)
        if novo[0] != novo[-1]:
            novo.append(novo[0])
        if len(novo) >= 4:
            out.append(novo)
    return out


def ler(arg, camada):
    if arg:
        return json.loads(Path(arg).read_text(encoding="utf-8"))
    with urllib.request.urlopen(SERVICO + CONSULTA.format(camada=camada), timeout=60) as r:
        return json.load(r)


def main():
    a = sys.argv[1:] + [None, None]
    comum, seletiva = ler(a[0], 1), ler(a[1], 2)
    feats = []
    for f in comum["features"]:
        p = f["properties"]
        freq = p.get("FREQUENCIA") or ""
        turno = "noturno" if "NOTURNO" in freq.upper() else "diurno"
        h = horario(p.get("HORARIO")) or ("a partir das 18h30" if turno == "noturno" else "a partir das 7h")
        feats.append({"type": "Feature", "properties": {"tipo": "comum", "turno": turno, "dias": dias_comum(freq),
                                                         "setor": "", "horario": h},
                      "geometry": {"type": "Polygon", "coordinates": arred(f["geometry"]["coordinates"])}})
    for f in seletiva["features"]:
        p = f["properties"]
        dia = (p.get("DIADASEMANA") or "").split("-")[0].strip().upper()
        coop = (p.get("COOPERATIVA") or "").strip().upper()
        feats.append({"type": "Feature", "properties": {"tipo": "seletiva", "turno": "", "dias": DIA[dia],
                                                         "setor": f"Setor {p.get('SETOR', '').strip()}",
                                                         "cooperativa": NOME.get(coop, coop.title()),
                                                         "telefone": TELEFONE.get(coop, p.get("TELCONTATO") or "")},
                      "geometry": {"type": "Polygon", "coordinates": arred(f["geometry"]["coordinates"])}})
    SAIDA.write_text(json.dumps({"type": "FeatureCollection", "fonte": FONTE, "features": feats},
                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{SAIDA.name}: {sum(1 for f in feats if f['properties']['tipo'] == 'comum')} setores da coleta comum, "
          f"{sum(1 for f in feats if f['properties']['tipo'] == 'seletiva')} da seletiva")


if __name__ == "__main__":
    main()
