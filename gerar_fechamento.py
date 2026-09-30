#!/usr/bin/env python3
# ============================================================
#  Fechamento de Mercado — Monte Bianco
#  Busca as cotações, monta o gráfico do EWZ (Ibovespa em dólar)
#  e gera o PNG no formato story (1080x1920), pronto para publicação.
# ============================================================

import json
import os
from datetime import datetime

import yfinance as yf
from playwright.sync_api import sync_playwright

# ------------------------------------------------------------
#  Configuração
# ------------------------------------------------------------
TEMPLATE = "fechamento.html"
SAIDA_DIR = "saida"

# Gráfico em destaque: Ibovespa em dólar, representado pelo ETF EWZ
EWZ_TICKER = "EWZ"
EWZ_PREGOES = 40          # quantos pregões aparecem no gráfico

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo"]

# (rótulo exibido, ticker Yahoo Finance, casas decimais)
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
#  Formatação no padrão brasileiro
# ------------------------------------------------------------
def fmt_num(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_var(pct):
    sinal = "+" if pct >= 0 else "-"
    return f"{sinal}{abs(pct):.2f}".replace(".", ",") + "%"


def data_por_extenso():
    agora = datetime.now()
    return f"{DIAS[agora.weekday()]}, {agora.day:02d} de {MESES[agora.month - 1]}"


def fechamentos(ticker, periodo="6mo"):
    """Série de fechamentos diários, já sem valores vazios."""
    h = yf.Ticker(ticker).history(period=periodo, interval="1d")
    return h.dropna(subset=["Close"])["Close"].astype(float).tolist()


def variacao_dia(ticker):
    s = fechamentos(ticker, periodo="5d")
    if len(s) < 2:
        return None, None
    return s[-1], (s[-1] / s[-2] - 1) * 100


# ------------------------------------------------------------
#  1) Coleta
# ------------------------------------------------------------
def coletar_ativos():
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
    return resultado


def coletar_ewz():
    """Série do EWZ para o gráfico + valor e variação do dia."""
    serie = fechamentos(EWZ_TICKER, periodo="6mo")
    if len(serie) < 2:
        raise RuntimeError("Sem dados suficientes do EWZ para montar o gráfico.")
    serie = [round(v, 2) for v in serie[-EWZ_PREGOES:]]
    pct_dia = (serie[-1] / serie[-2] - 1) * 100
    print(f"[ok] EWZ  {len(serie)} pregões  último US$ {serie[-1]}  dia {fmt_var(pct_dia)}")
    return {
        "valor": fmt_num(serie[-1], 2),
        "chg": fmt_var(pct_dia),
        "serie": serie,
    }


# ------------------------------------------------------------
#  2) Renderização do PNG
# ------------------------------------------------------------
def renderizar(payload):
    os.makedirs(SAIDA_DIR, exist_ok=True)
    caminho = os.path.join(SAIDA_DIR, f"fechamento-{datetime.now():%Y-%m-%d}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 2100},
                                device_scale_factor=2)
        page.goto("file://" + os.path.abspath(TEMPLATE))
        page.wait_for_timeout(1200)

        page.fill("#jsonPaste", json.dumps(payload, ensure_ascii=False))
        page.click("#importJson")
        page.wait_for_timeout(800)

        page.eval_on_selector("#card", "el => { el.style.transform='none'; el.style.margin='0'; }")
        page.wait_for_timeout(400)

        page.query_selector("#cardBg").screenshot(path=caminho)
        browser.close()

    fixo = os.path.join(SAIDA_DIR, "fechamento-mais-recente.png")
    with open(caminho, "rb") as src, open(fixo, "wb") as dst:
        dst.write(src.read())

    print(f"[ok] imagem gerada: {caminho}")
    return caminho


if __name__ == "__main__":
    dados = {
        "data": data_por_extenso(),
        "ewz": coletar_ewz(),
        "ativos": coletar_ativos(),
    }
    if not dados["ativos"]:
        raise SystemExit("Nenhuma cotação coletada — abortando.")
    renderizar(dados)
