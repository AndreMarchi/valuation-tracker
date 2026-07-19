"""
fcfe.py — Fluxo de Caixa Livre do Acionista (FCFE) e Valuation por Equity DCF.

Complementa o módulo de FCFF/WACC já existente no Valuation Tracker. FCFE é
particularmente relevante para setores onde dívida é insumo operacional e não
financiamento (bancos, seguradoras) — nesses casos o approach FCFF/WACC distorce
o resultado e o FCFE descontado a Ke é o padrão de mercado.

Convenções:
- Todos os valores monetários na mesma unidade (ex: R$ mil, conforme
  ESCALA_MOEDA já tratado no restante do app).
- Taxas de crescimento e Ke/WACC em formato decimal (ex: 0.12 para 12%).
- Quando um cálculo não é matematicamente viável (ex: Ke <= g), a função
  retorna None nos campos afetados e preenche 'alerta' com a justificativa,
  seguindo a mesma convenção de N/A do restante do sistema.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ResultadoFCFE:
    lucro_liquido: float
    reinvestimento_liquido: float
    delta_divida_liquida: float
    fcfe: float
    alerta: Optional[str] = None


def calcular_fcfe(
    lucro_liquido: float,
    capex: float,
    depreciacao: float,
    delta_ccl: float,
    novas_dividas_emitidas: float,
    amortizacao_dividas: float,
) -> ResultadoFCFE:
    """
    FCFE = Lucro Líquido - Reinvestimento Líquido + ΔDívida Líquida

    Reinvestimento Líquido = (CAPEX - Depreciação) + ΔCCL
    ΔDívida Líquida = Novas Dívidas Emitidas - Amortização de Dívidas
    """
    reinvestimento_liquido = (capex - depreciacao) + delta_ccl
    delta_divida_liquida = novas_dividas_emitidas - amortizacao_dividas
    fcfe = lucro_liquido - reinvestimento_liquido + delta_divida_liquida

    alerta = None
    if lucro_liquido < 0:
        alerta = (
            "Lucro líquido negativo: FCFE calculado, mas resultado deve ser "
            "interpretado com cautela — modelo de crescimento estável na "
            "perpetuidade fica menos confiável partindo de uma base negativa."
        )

    return ResultadoFCFE(
        lucro_liquido=lucro_liquido,
        reinvestimento_liquido=reinvestimento_liquido,
        delta_divida_liquida=delta_divida_liquida,
        fcfe=fcfe,
        alerta=alerta,
    )


def projetar_fcfe(
    fcfe_base: float, taxa_crescimento: float, anos: int
) -> List[float]:
    """
    Projeta o FCFE para os 'anos' seguintes usando uma taxa de crescimento
    constante (estágio explícito). Para crescimento não-constante, chame esta
    função por período com taxas diferentes e concatene as listas.
    """
    if anos <= 0:
        raise ValueError("Número de anos de projeção deve ser positivo.")
    return [
        fcfe_base * ((1 + taxa_crescimento) ** ano) for ano in range(1, anos + 1)
    ]


@dataclass
class ValorTerminalFCFE:
    valor: Optional[float]
    alerta: Optional[str] = None


def valor_terminal_fcfe(
    fcfe_ultimo_ano_explicito: float, ke: float, g_perpetuo: float
) -> ValorTerminalFCFE:
    """
    Valor Terminal = FCFE_(N+1) / (Ke - g)
    FCFE_(N+1) = FCFE do último ano explícito * (1 + g_perpetuo)
    """
    if ke <= g_perpetuo:
        return ValorTerminalFCFE(
            valor=None,
            alerta=(
                f"Ke ({ke:.2%}) <= taxa de crescimento perpétuo ({g_perpetuo:.2%}): "
                "valor terminal indefinido (denominador <= 0). Revise premissas — "
                "g_perpetuo deve ser inferior ao custo de capital próprio e, em "
                "geral, ao crescimento nominal de longo prazo da economia."
            ),
        )
    fcfe_n1 = fcfe_ultimo_ano_explicito * (1 + g_perpetuo)
    return ValorTerminalFCFE(valor=fcfe_n1 / (ke - g_perpetuo))


@dataclass
class ValuationFCFEResultado:
    fcfe_projetados: List[float]
    valor_presente_fcfe_explicito: float
    valor_terminal: Optional[float]
    valor_presente_valor_terminal: Optional[float]
    valor_justo_equity: Optional[float]
    valor_justo_por_acao: Optional[float]
    alerta: Optional[str] = None


def valuation_fcfe_dois_estagios(
    fcfe_ano_base: float,
    taxa_crescimento_explicito: float,
    anos_explicitos: int,
    ke: float,
    g_perpetuo: float,
    numero_acoes: float,
) -> ValuationFCFEResultado:
    """
    Valuation de equity via FCFE em dois estágios: projeta 'anos_explicitos'
    anos a 'taxa_crescimento_explicito', calcula valor terminal em Gordon
    Growth com 'g_perpetuo', desconta tudo a Ke e divide pelo número de ações.

    Diferente do DCF via FCFF: aqui chega-se direto ao valor de equity — não
    é necessário subtrair dívida líquida, pois o FCFE já contempla os fluxos
    de dívida (emissões e amortizações) na sua definição.
    """
    if numero_acoes <= 0:
        return ValuationFCFEResultado(
            fcfe_projetados=[],
            valor_presente_fcfe_explicito=0.0,
            valor_terminal=None,
            valor_presente_valor_terminal=None,
            valor_justo_equity=None,
            valor_justo_por_acao=None,
            alerta="Número de ações inválido (<= 0): impossível calcular valor por ação.",
        )

    fcfe_projetados = projetar_fcfe(fcfe_ano_base, taxa_crescimento_explicito, anos_explicitos)

    valor_presente_explicito = sum(
        fcfe / ((1 + ke) ** ano)
        for ano, fcfe in enumerate(fcfe_projetados, start=1)
    )

    vt = valor_terminal_fcfe(fcfe_projetados[-1], ke, g_perpetuo)
    if vt.valor is None:
        return ValuationFCFEResultado(
            fcfe_projetados=fcfe_projetados,
            valor_presente_fcfe_explicito=valor_presente_explicito,
            valor_terminal=None,
            valor_presente_valor_terminal=None,
            valor_justo_equity=None,
            valor_justo_por_acao=None,
            alerta=vt.alerta,
        )

    valor_presente_vt = vt.valor / ((1 + ke) ** anos_explicitos)
    valor_justo_equity = valor_presente_explicito + valor_presente_vt
    valor_justo_por_acao = valor_justo_equity / numero_acoes

    return ValuationFCFEResultado(
        fcfe_projetados=fcfe_projetados,
        valor_presente_fcfe_explicito=valor_presente_explicito,
        valor_terminal=vt.valor,
        valor_presente_valor_terminal=valor_presente_vt,
        valor_justo_equity=valor_justo_equity,
        valor_justo_por_acao=valor_justo_por_acao,
    )