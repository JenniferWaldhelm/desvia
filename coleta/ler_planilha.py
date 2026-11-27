#!/usr/bin/env python3
"""Lê as abas Pontos e Fila de cidades direto pela API do Google Sheets (sem o atraso da cópia publicada).
Usa a conta de serviço só de leitura guardada no segredo GOOGLE_SA_JSON. Grava dados/pontos.novo.csv e
dados/cidades.api.csv. Se algo falhar, sai com erro e a publicação volta a usar a cópia publicada."""
import csv, json, os, sys
from urllib.parse import quote
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

PLANILHA = "1SdtbIlpzAYfDwxlu4X9d_BmBsOi1a9uF1UByRpUIMps"
cred = service_account.Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SA_JSON"]), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
s = AuthorizedSession(cred)


def aba(nome, destino):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{PLANILHA}/values/{quote(nome)}?valueRenderOption=FORMATTED_VALUE"
    r = s.get(url, timeout=60)
    r.raise_for_status()
    linhas = r.json().get("values", [])
    cab = linhas[0]
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        for l in linhas[1:]:
            w.writerow((l + [""] * len(cab))[:len(cab)])
    print(f"{nome}: {len(linhas) - 1} linhas pela API")


aba("Pontos", "dados/pontos.novo.csv")
aba("Fila de cidades", "dados/cidades.api.csv")
