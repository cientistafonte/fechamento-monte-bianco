#!/usr/bin/env python3
# ============================================================
#  Gerador automático de Fechamento de Mercado — Monte Bianco MFO
#  Roda sozinho no GitHub Actions: busca cotações e gera o PNG.
# ============================================================

import json
import os
from datetime import datetime

import yfinance as yf
from playwright.sync_api import sync_playwright

# ------------------------------------------------------------
#  Configuração
# ------------------------------------------------------------
TEMPLATE = "fechamento.html"          # template no mesmo repositório
SAIDA_DIR = "saida"                    # onde o PNG é salvo

# Meses em português (não dependemos de locale no servidor do GitHub)
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo"]

# Lista de ativos: (rótulo, ticker Yahoo Finance, casas decimais)
ATIVOS = [
    ("Ibovespa",         "^BVSP",     0),
    ("S&P 500",          "^GSPC",     0),
    ("Nasdaq",           "^IXIC",     0),
    ("Dow Jones",        "^DJI",      0),
    ("Euro Stoxx 50",    "^STOXX50E", 0),
    ("Nikkei 225",       "^N225",     0),
    ("Dólar (USD/BRL)",  "BRL=X",     2),
    ("Euro (EUR/BRL)",   "EURBRL=X",  2),
    ("Bitcoin (BTC)",    "BTC-USD",   0),
    ("Ethereum (ETH)",   "ETH-USD",   0),
    ("Ouro (oz)",        "GC=F",      0),
    ("Petróleo Brent",   "BZ=F",      2),
]


# ------------------------------------------------------------
#  Formatação (padrão brasileiro)
# ------------------------------------------------------------
def fmt_num(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_var(pct):
    sinal = "+" if pct >= 0 else "-"
    return f"{sinal}{abs(pct):.2f}".replace(".", ",") + "%"


def variacao_dia(ticker):
    h = yf.Ticker(ticker).history(period="5d", interval="1d").dropna(subset=["Close"])
    if len(h) < 2:
        return None, None
    ultimo, anterior = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
    return ultimo, (ultimo / anterior - 1) * 100


def data_por_extenso():
    agora = datetime.now()
    return f"{DIAS[agora.weekday()]}, {agora.day:02d} de {MESES[agora.month - 1]}"


# ------------------------------------------------------------
#  1) Buscar cotações
# ------------------------------------------------------------
def coletar():
    resultado = []
    for nome, ticker, casas in ATIVOS:
        try:
            preco, pct = variacao_dia(ticker)
            if preco is None:
                print(f"[aviso] sem dados: {nome} ({ticker})")
                continue
            resultado.append({
                "name": nome,
                "value": fmt_num(preco, casas),
                "chg": fmt_var(pct),
            })
            print(f"[ok] {nome:<20} {fmt_num(preco, casas):>12} {fmt_var(pct):>8}")
        except Exception as e:
            print(f"[erro] {nome} ({ticker}): {e}")
    return {"data": data_por_extenso(), "ativos": resultado}


# ------------------------------------------------------------
#  2) Renderizar o PNG a partir do template
# ------------------------------------------------------------
def renderizar(payload):
    os.makedirs(SAIDA_DIR, exist_ok=True)
    nome_arquivo = f"fechamento-{datetime.now():%Y-%m-%d}.png"
    caminho = os.path.join(SAIDA_DIR, nome_arquivo)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1500},
                                device_scale_factor=2)
        page.goto("file://" + os.path.abspath(TEMPLATE))
        page.wait_for_timeout(800)

        page.fill("#jsonPaste", json.dumps(payload, ensure_ascii=False))
        page.click("#importJson")
        page.wait_for_timeout(600)

        page.eval_on_selector("#card", "el => { el.style.transform='none'; el.style.margin='0'; }")
        page.wait_for_timeout(400)

        page.query_selector("#cardBg").screenshot(path=caminho)
        browser.close()

    # também salva uma cópia com nome fixo, fácil de linkar
    fixo = os.path.join(SAIDA_DIR, "fechamento-mais-recente.png")
    with open(caminho, "rb") as src, open(fixo, "wb") as dst:
        dst.write(src.read())

    print(f"[ok] imagem gerada: {caminho}")
    print(f"[ok] cópia fixa:    {fixo}")
    return caminho


if __name__ == "__main__":
    dados = coletar()
    if not dados["ativos"]:
        raise SystemExit("Nenhuma cotação coletada — abortando.")
    renderizar(dados)
