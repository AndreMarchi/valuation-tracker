# backend/sotp.py
"""
SOTP (Sum-of-the-Parts) — valuation por segmento para holdings/conglomerados
da B3 (ex: empresas com braço financeiro + operacional, holdings de
energia). Cada segmento é avaliado separadamente pelo método mais adequado
(múltiplo de EBITDA, múltiplo de receita, ou DCF) e os Enterprise Values
somados formam o Enterprise Value consolidado, do qual se subtrai a dívida
líquida consolidada (uma única vez, no nível do holding — nunca por
segmento) e se aplica um desconto de holding opcional.

A segmentação por unidade de negócio não vem de nenhuma API estruturada do
projeto (Fundamentus/CVM/yfinance não reportam por segmento) — por isso o
mecanismo de input é um arquivo de configuração manual em JSON
(dados/sotp_config.json, ver carregar_configuracao_sotp()), no mesmo
espírito do cache JSON diário já usado pelo Scanner
(dados/snapshot_mercado.json) e do mapeamento manual já usado noutros
módulos (ex: CONCESSOES_CONHECIDAS em valuation/dcf_concessao.py,
OVERRIDE_PCT_RECEITA_MOEDA_ESTRANGEIRA em dados/cvm_provider.py) — não se
tenta inferir segmentos automaticamente.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from valuation.dcf import calcular_dcf

MetodoSegmento = Literal["ev_ebitda", "ev_receita", "dcf"]

CONFIG_PATH = Path(__file__).parent / "dados" / "sotp_config.json"


@dataclass
class Segmento:
    """
    Um segmento/unidade de negócio de uma holding. Só os campos relevantes
    pro `metodo` escolhido precisam ser preenchidos:

    - "ev_ebitda": `ebitda` + `multiplo_ev_ebitda` (múltiplo específico do
      setor daquele segmento — ex: um múltiplo de banco pro braço
      financeiro, um múltiplo industrial pro braço operacional).
    - "ev_receita": `receita` + `multiplo_ev_receita`.
    - "dcf": `fluxo_caixa_atual`, `taxa_crescimento`, `taxa_desconto` (WACC
      ESPECÍFICO do setor daquele segmento — o ponto principal do SOTP é
      não usar o WACC único da holding pra todos os braços de negócio),
      `anos_projecao`, `taxa_crescimento_perpetuidade`. Não inclui
      `num_acoes`/`divida_liquida`/`preco_atual` — esses só fazem sentido
      no nível CONSOLIDADO do SOTP (calcular_sotp()), nunca por segmento.
    """
    nome: str
    metodo: MetodoSegmento
    ebitda: Optional[float] = None
    multiplo_ev_ebitda: Optional[float] = None
    receita: Optional[float] = None
    multiplo_ev_receita: Optional[float] = None
    fluxo_caixa_atual: Optional[float] = None
    taxa_crescimento: Optional[float] = None
    taxa_desconto: Optional[float] = None
    anos_projecao: Optional[int] = None
    taxa_crescimento_perpetuidade: Optional[float] = None


@dataclass
class ConfiguracaoSotp:
    segmentos: list = field(default_factory=list)
    divida_liquida_consolidada: float = 0.0
    num_acoes: float = 0.0
    # Comum em holdings brasileiras negociarem com desconto sobre o SOTP
    # (iliquidez, custos de governança/agência, incerteza sobre alocação
    # de capital do controlador) — explícito como input parametrizável,
    # nunca embutido silenciosamente num valor fixo dentro do cálculo.
    desconto_holding_pct: float = 0.0


def calcular_ev_segmento(segmento: Segmento) -> dict:
    """
    Enterprise Value de UM segmento, conforme `segmento.metodo`.

    "ev_ebitda"/"ev_receita" são multiplicações diretas (EV = métrica ×
    múltiplo) — deliberadamente NÃO reaproveitam
    valuation/ev_ebitda.py::calcular_ev_ebitda() nem
    valuation/crescimento.py::calcular_ev_receita(): essas duas funções
    embutem lógica específica do nível de EMPRESA INTEIRA (blend 50/50
    empresa/setor, divisão por num_acoes, subtração de dívida líquida) que
    não se aplica a um segmento isolado — o SOTP já recebe o múltiplo-alvo
    do segmento diretamente do chamador (não precisa de blend), e
    dívida/ações só entram no nível consolidado (calcular_sotp()). Forçar
    reuso ali exigiria parâmetros fictícios (num_acoes=1, div_liquida=0)
    escondendo lógica de blend que não faz sentido aqui — mais enganoso do
    que uma multiplicação direta e explícita.

    "dcf" REAPROVEITA valuation/dcf.py::calcular_dcf() de verdade (a
    projeção/desconto de fluxo de caixa multi-ano É lógica não-trivial que
    não deve ser duplicada) — chamado com `num_acoes=1.0`/`divida_liquida=0.0`,
    o que faz `valor_intrinseco` degenerar exatamente no Enterprise Value
    bruto do segmento (sem dividir por ação nem subtrair dívida, que só
    fazem sentido no nível consolidado do SOTP).
    """
    if segmento.metodo == "ev_ebitda":
        if segmento.ebitda is None or segmento.multiplo_ev_ebitda is None:
            return _erro_segmento(segmento, "ebitda e multiplo_ev_ebitda são obrigatórios pro método ev_ebitda")
        if segmento.ebitda <= 0 or segmento.multiplo_ev_ebitda <= 0:
            return _erro_segmento(segmento, "ebitda e multiplo_ev_ebitda precisam ser positivos")
        return _ok_segmento(segmento, segmento.ebitda * segmento.multiplo_ev_ebitda)

    if segmento.metodo == "ev_receita":
        if segmento.receita is None or segmento.multiplo_ev_receita is None:
            return _erro_segmento(segmento, "receita e multiplo_ev_receita são obrigatórios pro método ev_receita")
        if segmento.receita <= 0 or segmento.multiplo_ev_receita <= 0:
            return _erro_segmento(segmento, "receita e multiplo_ev_receita precisam ser positivos")
        return _ok_segmento(segmento, segmento.receita * segmento.multiplo_ev_receita)

    if segmento.metodo == "dcf":
        campos = [
            segmento.fluxo_caixa_atual, segmento.taxa_crescimento, segmento.taxa_desconto,
            segmento.anos_projecao, segmento.taxa_crescimento_perpetuidade,
        ]
        if any(c is None for c in campos):
            return _erro_segmento(segmento, "parâmetros de DCF incompletos (fluxo_caixa_atual/taxa_crescimento/taxa_desconto/anos_projecao/taxa_crescimento_perpetuidade)")
        if segmento.fluxo_caixa_atual <= 0:
            return _erro_segmento(segmento, "fluxo_caixa_atual do segmento precisa ser positivo")
        if segmento.taxa_desconto <= segmento.taxa_crescimento_perpetuidade:
            return _erro_segmento(
                segmento,
                f"WACC do segmento ({segmento.taxa_desconto:.2%}) <= g perpétuo "
                f"({segmento.taxa_crescimento_perpetuidade:.2%}) — combinação inválida (mesma trava de cenarios_sensibilidade.py)",
            )
        resultado_dcf = calcular_dcf(
            fluxo_caixa_atual=segmento.fluxo_caixa_atual,
            taxa_crescimento=segmento.taxa_crescimento,
            taxa_desconto=segmento.taxa_desconto,
            anos_projecao=segmento.anos_projecao,
            taxa_crescimento_perpetuidade=segmento.taxa_crescimento_perpetuidade,
            num_acoes=1.0,
            preco_atual=1.0,
            divida_liquida=0.0,
        )
        return _ok_segmento(segmento, resultado_dcf["valor_intrinseco"])

    return _erro_segmento(segmento, f"método desconhecido: {segmento.metodo!r}")


def _ok_segmento(segmento: Segmento, ev: float) -> dict:
    return {"nome": segmento.nome, "metodo": segmento.metodo, "ev": round(ev, 2), "erro": None}


def _erro_segmento(segmento: Segmento, erro: str) -> dict:
    return {"nome": segmento.nome, "metodo": segmento.metodo, "ev": None, "erro": erro}


def calcular_sotp(config: ConfiguracaoSotp) -> dict:
    """
    Soma os Enterprise Values de todos os segmentos (só os calculáveis —
    segmentos com erro entram no retorno em `segmentos_com_erro`, mas não
    na soma, pra um dado incompleto de UM segmento não travar o SOTP
    inteiro), subtrai a dívida líquida CONSOLIDADA (uma única vez, nunca
    por segmento) e aplica o desconto de holding.
    """
    detalhamento = [calcular_ev_segmento(s) for s in config.segmentos]
    evs_validos = [d["ev"] for d in detalhamento if d["ev"] is not None]
    segmentos_com_erro = [d["nome"] for d in detalhamento if d["ev"] is None]

    ev_consolidado_bruto = sum(evs_validos)
    valor_equity_bruto = ev_consolidado_bruto - config.divida_liquida_consolidada
    valor_equity_pos_desconto = valor_equity_bruto * (1 - config.desconto_holding_pct)
    preco_justo_por_acao = (
        valor_equity_pos_desconto / config.num_acoes if config.num_acoes and config.num_acoes > 0 else None
    )

    return {
        "segmentos": detalhamento,
        "segmentos_com_erro": segmentos_com_erro,
        "ev_consolidado_bruto": round(ev_consolidado_bruto, 2),
        "divida_liquida_consolidada": round(config.divida_liquida_consolidada, 2),
        "valor_equity_bruto": round(valor_equity_bruto, 2),
        "desconto_holding_pct": config.desconto_holding_pct,
        "valor_equity_pos_desconto": round(valor_equity_pos_desconto, 2),
        "preco_justo_por_acao": round(preco_justo_por_acao, 2) if preco_justo_por_acao is not None else None,
    }


def _segmento_de_dict(d: dict) -> Segmento:
    campos_validos = {f for f in Segmento.__dataclass_fields__}
    return Segmento(**{k: v for k, v in d.items() if k in campos_validos})


def carregar_configuracao_sotp(ticker: str) -> Optional[ConfiguracaoSotp]:
    """
    Carrega a configuração de segmentos de `dados/sotp_config.json` (JSON
    keyed por ticker, mesmo espírito do cache JSON diário do Scanner —
    ver docstring do módulo). Retorna `None` (não uma configuração vazia
    enganosa) quando o arquivo não existe ou o ticker não está mapeado —
    sinaliza "sem configuração", não "holding sem segmentos".
    """
    if not CONFIG_PATH.exists():
        return None

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config_completa = json.load(f)

    ticker_upper = ticker.upper().strip()
    if ticker_upper not in config_completa:
        return None

    bruto = config_completa[ticker_upper]
    return ConfiguracaoSotp(
        segmentos=[_segmento_de_dict(s) for s in bruto.get("segmentos", [])],
        divida_liquida_consolidada=bruto.get("divida_liquida_consolidada", 0.0),
        num_acoes=bruto.get("num_acoes", 0.0),
        desconto_holding_pct=bruto.get("desconto_holding_pct", 0.0),
    )
