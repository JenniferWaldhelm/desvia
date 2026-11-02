#!/usr/bin/env python3
"""Baixa as métricas do mês anterior (Bing Webmaster e GoatCounter) para metricas/AAAA-MM/.

Chaves vêm de variáveis de ambiente (segredos do GitHub): BING_API_KEY e GOATCOUNTER_TOKEN.
Sem a chave, a fonte é pulada. Gera também um resumo.md legível.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITE = "https://jenniferwaldhelm.github.io/desvia/"
GC = "https://projetodesvia.goatcounter.com"

fim = date.today().replace(day=1) - timedelta(days=1)
ini = fim.replace(day=1)
pasta = RAIZ / "metricas" / f"{ini:%Y-%m}"
pasta.mkdir(parents=True, exist_ok=True)
resumo = [f"# Métricas de {ini:%m/%Y}", ""]


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Desvia/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


bing = os.environ.get("BING_API_KEY")
if bing:
    for nome, metodo in (("consultas", "GetQueryStats"), ("paginas", "GetPageStats")):
        try:
            d = get(f"https://ssl.bing.com/webmaster/api.svc/json/{metodo}?" + urllib.parse.urlencode({"siteUrl": SITE, "apikey": bing}))
            linhas = d.get("d", [])
            (pasta / f"bing-{nome}.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=1), encoding="utf-8")
            top = sorted(linhas, key=lambda x: -(x.get("Impressions") or 0))[:15]
            resumo += [f"## Bing: {nome} (top 15 por impressões)", ""] + [
                f"- {x.get('Query') or x.get('Page')}: {x.get('Impressions')} impressões, {x.get('Clicks')} cliques" for x in top] + [""]
        except Exception as e:  # noqa: BLE001
            resumo += [f"- Bing {nome}: erro {e}", ""]
else:
    resumo += ["- Bing: sem chave (segredo BING_API_KEY).", ""]

gct = os.environ.get("GOATCOUNTER_TOKEN")
if gct:
    try:
        q = urllib.parse.urlencode({"start": f"{ini}T00:00:00Z", "end": f"{fim}T23:59:59Z", "limit": 100})
        d = get(f"{GC}/api/v0/stats/hits?{q}", {"Authorization": f"Bearer {gct}", "Content-Type": "application/json"})
        hits = d.get("hits", [])
        (pasta / "goatcounter.json").write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
        cont = lambda h: h.get("count") or sum(s.get("daily", 0) for s in h.get("stats", []))
        for titulo, filtro in (("Páginas mais vistas", lambda p: not p.startswith(("busca", "assistente"))),
                               ("Buscas sem resultado", lambda p: p.startswith("busca-sem-resultado")),
                               ("Buscas com resultado", lambda p: p.startswith("busca/")),
                               ("Escolhas no assistente", lambda p: p.startswith("assistente"))):
            sel = sorted((h for h in hits if filtro(h.get("path", "").lstrip("/"))), key=lambda h: -cont(h))[:20]
            resumo += [f"## GoatCounter: {titulo}", ""] + [f"- {h['path']}: {cont(h)}" for h in sel] + [""]
    except Exception as e:  # noqa: BLE001
        resumo += [f"- GoatCounter: erro {e}", ""]
else:
    resumo += ["- GoatCounter: sem chave (segredo GOATCOUNTER_TOKEN).", ""]

(pasta / "resumo.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
print("\n".join(resumo))
