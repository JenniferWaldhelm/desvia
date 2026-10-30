#!/usr/bin/env python3
"""Avisa os buscadores que usam IndexNow (Bing, Yandex e outros) sobre as URLs do sitemap."""
import json
import re
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE_URL = "https://jenniferwaldhelm.github.io/desvia"
HOST = "jenniferwaldhelm.github.io"

chave = (RAIZ / "gerador" / "indexnow_key.txt").read_text().strip()
urls = re.findall(r"<loc>([^<]+)</loc>", (RAIZ / "sitemap.xml").read_text(encoding="utf-8"))
corpo = json.dumps({
    "host": HOST,
    "key": chave,
    "keyLocation": f"{BASE_URL}/{chave}.txt",
    "urlList": urls,
}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=corpo,
                             headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"IndexNow: {r.status} para {len(urls)} URLs")
except urllib.error.HTTPError as e:
    # 202 = aceito; 403 = chave não encontrada (site ainda publicando); 422 = URL fora do host
    print(f"IndexNow respondeu {e.code}: {e.read()[:200]!r}")
