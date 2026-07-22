"""
trabalhador.py
Worker de varredura em massa da B3. Roda em background (BackgroundTasks do
FastAPI), monta o "mapa" de oportunidades agrupado por setor e persiste em
dados/snapshot_mercado.json.

Reaproveita o mesmo pipeline de valuation usado em /api/valuation/{ticker}
(main.py), exceto: histórico 5a (yfinance, caro e rate-limited), peer group
de concorrentes (O(n²), não afeta o score) e DCF de concessão (nicho).
"""

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from dados.provider import buscar_dados
from dados.cvm_provider import buscar_saude_financeira_cvm
from dados.selic import buscar_selic_atual

from valuation.setor import (
    obter_todos_resultados_fundamentus,
    obter_pesos_setoriais,
    aplicar_restricoes_setor,
)
from valuation.graham import calcular_graham
from valuation.bazin import calcular_bazin
from valuation.multiplos import calcular_multiplos
from valuation.dcf import calcular_dcf
from valuation.score import calcular_score
from valuation.saude_financeira import calcular_saude_financeira, extrair_crescimento_cvm
from valuation.capm import calcular_capm, resolver_beta
from valuation.wacc import calcular_wacc
from valuation.nopat import calcular_fcl_via_nopat
from valuation.risco import analisar_risco
from valuation.endividamento import analisar_endividamento

logger = logging.getLogger(__name__)

CAMINHO_SNAPSHOT = os.path.join("dados", "snapshot_mercado.json")
CAMINHO_SETORES_JSON = os.path.join("dados", "setores_b3.json")
LIQUIDEZ_MINIMA_DIARIA = 500_000
MAX_WORKERS = 6

SETORES_CICLICOS = {
    "Transporte Aéreo", "Transporte",
    "Alimentos", "Mineração", "Siderurgia e Metalurgia",
}

_lock = threading.Lock()
_scan_em_andamento_flag = False


def scan_em_andamento() -> bool:
    return _scan_em_andamento_flag


# ─────────────────────────────────────────────────────────────────────────
# Cadastro (nome/setor/subsetor) — sempre do JSON local, nunca do bulk
# ─────────────────────────────────────────────────────────────────────────

def _carregar_tickers_representativos() -> list:
    """
    Lê setores_b3.json e retorna 1 ticker representativo por empresa
    (o primeiro de cada entrada "Tickets"), evitando duplicar ON/PN/UNIT
    da mesma empresa na varredura.
    """
    if not os.path.exists(CAMINHO_SETORES_JSON):
        logger.error("setores_b3.json não encontrado em %s", CAMINHO_SETORES_JSON)
        return []

    with open(CAMINHO_SETORES_JSON, "r", encoding="utf-8") as f:
        empresas = json.load(f)

    tickers = []
    for emp in empresas:
        tickers_raw = str(emp.get("Tickets", "")).upper().strip()
        if not tickers_raw or tickers_raw == "NONE":
            continue
        ticker_principal = tickers_raw.split(",")[0].strip()
        if ticker_principal:
            tickers.append(ticker_principal)
    return tickers


def _cadastro_por_ticker() -> dict:
    """Mapa ticker -> {nome, setor, subsetor} a partir do JSON local."""
    if not os.path.exists(CAMINHO_SETORES_JSON):
        return {}

    with open(CAMINHO_SETORES_JSON, "r", encoding="utf-8") as f:
        empresas = json.load(f)

    mapa = {}
    for emp in empresas:
        tickers_raw = str(emp.get("Tickets", "")).upper().strip()
        if not tickers_raw or tickers_raw == "NONE":
            continue
        for t in [x.strip() for x in tickers_raw.split(",")]:
            mapa[t] = {
                "nome": emp.get("Nome", ""),
                "setor": emp.get("Setor_de_atuacao", "Geral"),
                "subsetor": emp.get("Segmento_de_mercado", "Geral"),
            }
    return mapa


# ─────────────────────────────────────────────────────────────────────────
# Mapeamento do bulk do Fundamentus -> mesmo formato de buscar_dados()
#
# Colunas confirmadas em fundamentus/resultado.py (_rename_cols): cotacao,
# pl, pvp, psr, dy, pa, pcg, pebit, pacl, evebit, evebitda, mrgebit, mrgliq,
# roic, roe, liqc, liq2m, patrliq, divbpatr, c5y. dy/roe/roic/mrgebit/mrgliq/
# c5y já vêm em decimal (perc_to_float). Não há lpa/vpa/ebit_12m/div_liquida
# diretos no bulk — lpa/vpa são derivados de cotacao/pl e cotacao/pvp;
# ebit_12m e div_liquida ficam 0.0 (bulk não traz valores absolutos de EBIT
# ou dívida líquida, só múltiplos/razões), o que faz o DCF cair em "Não
# aplicável" e a trava de endividamento não penalizar tickers bulk — mesmo
# trade-off descrito na decisão de arquitetura original.
# ─────────────────────────────────────────────────────────────────────────

def _linha_bulk_valida(linha) -> bool:
    if linha is None:
        return False
    try:
        preco = float(linha.get("cotacao", 0) or 0)
        pl = float(linha.get("pl", 0) or 0)
        return preco > 0 and pl != 0
    except (TypeError, ValueError):
        return False


def _mapear_linha_bulk(ticker: str, linha, cadastro: dict) -> dict:
    """
    Converte 1 linha do DataFrame de obter_todos_resultados_fundamentus()
    para o mesmo formato de dict que buscar_dados() retorna, usando o
    cadastro local (setores_b3.json) para nome/setor/subsetor.
    """
    info = cadastro.get(ticker, {})

    def _f(campo, padrao=0.0):
        try:
            return float(linha.get(campo, padrao) or padrao)
        except (TypeError, ValueError):
            return padrao

    preco = _f("cotacao")
    pl = _f("pl")
    pvp = _f("pvp")
    dividend_yield_dec = _f("dy")
    roe_dec = _f("roe")
    mrgliq_dec = _f("mrgliq")
    patrim_liq = _f("patrliq")

    lpa = round(preco / pl, 4) if pl else 0.0
    vpa = round(preco / pvp, 4) if pvp else 0.0
    num_acoes = round(patrim_liq / vpa, 2) if vpa else 0.0

    return {
        "ticker": ticker,
        "nome": info.get("nome", ticker),
        "setor": info.get("setor", "Geral"),
        "industria": info.get("subsetor", "Geral"),
        "preco_atual": preco,
        "lpa": lpa,
        "vpa": vpa,
        "pl": pl,
        "pvp": pvp,
        "dividendo_anual": round(preco * dividend_yield_dec, 2) if dividend_yield_dec else 0.0,
        "dividend_yield": round(dividend_yield_dec * 100, 2),
        "fluxo_caixa": 0.0,  # bulk não traz FCL; NOPAT usa ebit_12m (0.0 aqui)
        "num_acoes": num_acoes,
        "roe": round(roe_dec * 100, 2),
        "divida_ebitda": 0.0,
        "margem_lucro": round(mrgliq_dec * 100, 2),
        "crescimento_receita_5a": _f("c5y"),
        "ebit_12m": 0.0,
        "div_liquida": 0.0,
        "beta": 1.0,
        "liq2m": _f("liq2m"),
        "patrliq": patrim_liq,
    }


# ─────────────────────────────────────────────────────────────────────────
# Perfil de setor (deriva de obter_pesos_setoriais, sem taxonomia nova)
# ─────────────────────────────────────────────────────────────────────────

def _classificar_perfil_setor(subsetor: str) -> str:
    pesos = obter_pesos_setoriais(subsetor)
    if pesos.get("bazin", 0) >= 0.3 and pesos.get("dcf", 0) <= 0.1:
        return "Renda / Longo Prazo"
    if pesos.get("dcf", 0) >= 0.4 and pesos.get("bazin", 0) <= 0.1:
        return "Crescimento / Cíclico"
    return "Misto"


# ─────────────────────────────────────────────────────────────────────────
# Pipeline enxuto por ticker (espelha /api/valuation/{ticker}, sem
# histórico 5a, sem peer group, sem DCF de concessão)
# ─────────────────────────────────────────────────────────────────────────

def avaliar_ticker(ticker: str, linha_bulk=None, cadastro: dict = None) -> dict:
    ticker_upper = ticker.upper().strip()
    cadastro = cadastro or {}

    if _linha_bulk_valida(linha_bulk):
        dados = _mapear_linha_bulk(ticker_upper, linha_bulk, cadastro)
        fonte = "bulk_fundamentus"
    else:
        dados = buscar_dados(ticker_upper)
        fonte = "individual"

    preco = dados.get("preco_atual", 0)
    lpa = dados.get("lpa", 0)
    vpa = dados.get("vpa", 0)
    pl = dados.get("pl", 0)
    pvp = dados.get("pvp", 0)
    div = dados.get("dividendo_anual", 0)
    fcl = (dados.get("fluxo_caixa", 0) or 0) / 1_000_000
    acoes = (dados.get("num_acoes", 0) or 0) / 1_000_000
    setor = dados.get("setor", "Geral")
    subsetor = dados.get("industria", "Geral")

    if not preco or not acoes:
        raise ValueError(f"Dados insuficientes para {ticker_upper} (preço ou nº de ações zerado)")

    # Saúde financeira via CVM (RAM-cached, barato; não bloqueia se falhar)
    try:
        dados_cvm = buscar_saude_financeira_cvm(ticker_upper, dados.get("nome", ""))
        saude = calcular_saude_financeira(dados_cvm)
        crescimento_cvm = extrair_crescimento_cvm(dados_cvm)
    except Exception:
        saude = {"disponivel": False}
        crescimento_cvm = None

    score_cvm_valor = saude.get("score", 5.0) if saude.get("disponivel") else 5.0
    tend_rec = saude.get("tendencia_receita", "estável") if saude.get("disponivel") else "estável"
    qual_luc = saude.get("qualidade_lucro", 1.0) if saude.get("disponivel") else 1.0

    # Taxa de crescimento (mesma lógica de main.py)
    crescimento_historico = crescimento_cvm if crescimento_cvm is not None else (dados.get("crescimento_receita_5a", 0) or 0)
    taxa_crescimento = max(-0.05, min(crescimento_historico, 0.15))
    if taxa_crescimento == 0:
        taxa_crescimento = 0.05
    if setor in SETORES_CICLICOS:
        taxa_crescimento = min(taxa_crescimento, 0.08)
    if taxa_crescimento < 0 and lpa > 0 and vpa > 0:
        taxa_crescimento = 0.02

    # CAPM + WACC
    selic_val = buscar_selic_atual()
    capm = calcular_capm(
        setor=setor,
        selic_atual=selic_val,
        beta_ativo=resolver_beta(dados.get("beta"), setor),
        valor_mercado=dados.get("valor_mercado", 0) or 0,
    )
    taxa_capm = capm.get("taxa_desconto", 0.12)
    dados_wacc = dict(dados)
    dados_wacc["selic"] = selic_val
    taxa_desconto = calcular_wacc(dados_wacc, taxa_capm)

    # FCL via NOPAT
    fcl_ajustado = calcular_fcl_via_nopat(dados)

    # Métodos clássicos
    graham = calcular_graham(lpa, vpa, preco)
    bazin = calcular_bazin(div, preco)
    pl_historico = pl * 1.2 if pl else 10.0
    pvp_historico = pvp * 1.2 if pvp else 1.5
    multiplos = calcular_multiplos(pl, pvp, pl_historico, pvp_historico, preco)

    if fcl_ajustado > 0 and acoes > 0:
        dcf = calcular_dcf(
            fluxo_caixa_atual=fcl_ajustado,
            taxa_crescimento=taxa_crescimento,
            taxa_desconto=taxa_desconto,
            anos_projecao=5,
            taxa_crescimento_perpetuidade=0.03,
            num_acoes=acoes,
            preco_atual=preco,
            divida_liquida=(dados.get("div_liquida", 0) or 0) / 1_000_000,
        )
    else:
        dcf = {
            "classificacao": "Não aplicável",
            "valor_intrinseco": None,
            "margem_seguranca": None,
            "cenarios": None,
        }

    graham, bazin, multiplos, dcf, _ev_ebitda, config_setor = aplicar_restricoes_setor(
        setor=setor, graham=graham, bazin=bazin, multiplos=multiplos, dcf=dcf, ticker=ticker_upper,
    )

    score = calcular_score(
        graham=graham,
        bazin=bazin,
        multiplos=multiplos,
        dcf=dcf,
        score_cvm=score_cvm_valor,
        lucro_liquido_recente=(lpa if lpa is not None else 1.0),
        fco_recente=fcl,
        subsetor=subsetor,
        tendencia_receita=tend_rec,
        qualidade_lucro=qual_luc,
    )

    # Travas de risco/governança e endividamento (sem rede, baratas)
    risco = analisar_risco(ticker=ticker_upper, setor=setor, score_atual=score.get("score", 0))

    # Dívida Líquida/EBIT não se aplica a banco/seguradora — mesma razão de
    # Graham/DCF/EV-EBITDA (ver valuation/setor.py e CONTEXT.md). Sem essa
    # restrição, ebit_12m=0 caía no ramo "else: div_ebit=0" de
    # analisar_endividamento(), mostrando "0,0x · sem alertas" como se
    # fosse ausência real de dívida. score_ajustado sai IGUAL ao score de
    # entrada — o min() do score_final abaixo não pode ser puxado pra baixo
    # (nem indevidamente "premiado") por uma métrica que não se aplica.
    if "endividamento" in config_setor.get("metodos_invalidos", []):
        endividamento = {
            "classificacao": "Não aplicável",
            "erro": config_setor.get("justificativas", {}).get("endividamento"),
            "div_liquida_ebit": None,
            "div_liquida_patrim": None,
            "alertas": [],
            "penalizacao": 0.0,
            "score_ajustado": score.get("score", 0),
        }
    else:
        endividamento = analisar_endividamento(
            div_liquida=dados.get("div_liquida", 0) or 0,
            ebit_12m=dados.get("ebit_12m", 0) or 0,
            patrim_liq=dados.get("patrim_liq", 0) or 0,
            score_atual=score.get("score", 0),
        )

    # NOTA: main.py hoje calcula risco e endividamento a partir do MESMO
    # score original (não encadeados) e não expõe uma fórmula única de
    # "score final" pros dois juntos nesse trecho. Usamos aqui o pior caso
    # dos três (conservador) como score_atratividade de ranking.
    score_final = min(
        score.get("score", 0),
        risco.get("score_ajustado", score.get("score", 0)),
        endividamento.get("score_ajustado", score.get("score", 0)),
    )

    precos_justos = [
        p for p in [
            graham.get("preco_justo"),
            bazin.get("preco_justo"),
            dcf.get("valor_intrinseco"),
        ] if p
    ]
    preco_justo_medio = sum(precos_justos) / len(precos_justos) if precos_justos else None
    margem_seguranca = (
        round((preco_justo_medio - preco) / preco * 100, 1)
        if preco_justo_medio and preco else None
    )

    alerta_valor_trap = bool(
        score_final >= 6
        and (
            not saude.get("disponivel")
            or (saude.get("score") is not None and saude["score"] < 4)
            or risco.get("em_recuperacao_judicial")
        )
    )

    liquidez = float(dados.get("liq2m", 0) or 0)

    return {
        "ticker": ticker_upper,
        "nome": dados.get("nome", ticker_upper),
        "setor": setor,
        "subsetor": subsetor,
        "preco_atual": preco,
        "preco_justo_medio": round(preco_justo_medio, 2) if preco_justo_medio else None,
        "margem_seguranca": margem_seguranca,
        "score_atratividade": round(score_final, 1),
        "classificacao": score.get("classificacao"),
        "pl": pl,
        "pvp": pvp,
        "dividend_yield": dados.get("dividend_yield", 0),
        "roe": dados.get("roe", 0),
        "divida_ebitda": dados.get("divida_ebitda", 0),
        "liquidez_2m": liquidez,
        "liquidez_ok": (liquidez >= LIQUIDEZ_MINIMA_DIARIA) if liquidez else None,
        "saude_financeira_disponivel": saude.get("disponivel", False),
        "saude_financeira_score": saude.get("score"),
        "alerta_valor_trap": alerta_valor_trap,
        "fonte": fonte,
    }


# ─────────────────────────────────────────────────────────────────────────
# Orquestração do scan completo
# ─────────────────────────────────────────────────────────────────────────

def _escrever_snapshot_atomico(payload: dict):
    """Escreve em arquivo temporário e faz replace atômico — evita ler
    um JSON parcial se o GET /api/scanner/resultado bater no meio da escrita."""
    caminho_tmp = CAMINHO_SNAPSHOT + ".tmp"
    diretorio = os.path.dirname(CAMINHO_SNAPSHOT)
    if diretorio:
        os.makedirs(diretorio, exist_ok=True)
    with open(caminho_tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(caminho_tmp, CAMINHO_SNAPSHOT)


def executar_scan():
    global _scan_em_andamento_flag

    if not _lock.acquire(blocking=False):
        logger.info("Scan já em andamento — chamada ignorada.")
        return

    _scan_em_andamento_flag = True
    resultados = []
    erros = []

    try:
        tickers = _carregar_tickers_representativos()
        cadastro = _cadastro_por_ticker()
        bulk_df = obter_todos_resultados_fundamentus()
        bulk_indexado = not bulk_df.empty

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for t in tickers:
                linha_bulk = None
                if bulk_indexado and t in bulk_df.index:
                    linha_bulk = bulk_df.loc[t]
                futures[executor.submit(avaliar_ticker, t, linha_bulk, cadastro)] = t

            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    resultados.append(future.result())
                except Exception as e:
                    logger.warning("Falha ao avaliar %s: %s", ticker, e)
                    erros.append({"ticker": ticker, "motivo": str(e)})

        # Agrupamento por setor + perfil + ordenação por score
        setores_map = {}
        for item in resultados:
            setor = item["setor"]
            if setor not in setores_map:
                setores_map[setor] = {
                    "setor": setor,
                    "perfil": _classificar_perfil_setor(item["subsetor"]),
                    "ativos": [],
                }
            setores_map[setor]["ativos"].append(item)

        for grupo in setores_map.values():
            grupo["ativos"].sort(key=lambda a: a["score_atratividade"], reverse=True)

        payload = {
            "data_atualizacao": datetime.now(timezone.utc).astimezone().isoformat(),
            "total_ativos_analisados": len(resultados),
            "total_erros": len(erros),
            "setores": list(setores_map.values()),
            "erros": erros,
        }

        _escrever_snapshot_atomico(payload)
        logger.info(
            "Scan concluído: %d ativos, %d erros.", len(resultados), len(erros)
        )

    finally:
        _scan_em_andamento_flag = False
        _lock.release()
