# backend/cenarios_sensibilidade.py
"""
Cenários (pessimista/base/otimista) e Análise de Sensibilidade sobre o DCF
principal (FCFF via NOPAT, ver valuation/dcf.py::calcular_dcf()).

Reaproveita calcular_dcf() como motor de cálculo — não duplica a lógica de
projeção/desconto de fluxo de caixa. Cada combinação de premissas (WACC, g
perpétuo, margem EBITDA, crescimento de receita) vira uma chamada a
calcular_dcf() já existente; este módulo só decide QUAIS combinações rodar
e como organizar o resultado (cenários e matrizes de sensibilidade).

Margem EBITDA — decisão de modelagem: calcular_dcf() recebe um
`fluxo_caixa_atual` já pronto (FCL via NOPAT, calculado fora deste módulo a
partir do EBIT — ver valuation/nopat.py), não modela receita/margem
separadamente. Pra simular um cenário de margem diferente sem duplicar a
cadeia EBIT->NOPAT->FCL, escalamos o fluxo de caixa base proporcionalmente
à razão entre a margem do cenário e a margem atual
(`fluxo_cenario = fluxo_base * margem_cenario / margem_base`), assumindo
receita constante nessa escala — aproximação simples e documentada, não uma
recalibração do motor de NOPAT.
"""

from dataclasses import dataclass
from typing import Optional


class WaccInvalidoError(ValueError):
    """
    WACC <= g perpétuo — o valor terminal do modelo de Gordon Growth
    (fluxo_terminal / (wacc - g)) fica indefinido (divisão por zero) ou
    negativo (denominador negativo) nessa combinação. calcular_dcf() sozinho
    trata isso devolvendo 0.0 silenciosamente (bug comum em implementações
    de DCF: parece um "valor justo zero" legítimo em vez de um erro de
    input). Este módulo levanta um erro explícito e tratável em vez de
    propagar esse 0.0 como se fosse um resultado válido.
    """


@dataclass
class DeltasCenario:
    """
    Deltas aplicados ao cenário PESSIMISTA (com sinal invertido para o
    OTIMISTA) em relação ao cenário base. Todos em pontos percentuais
    absolutos (ex: wacc_pp=0.015 -> WACC base + 1,5pp no pessimista, - 1,5pp
    no otimista), exceto onde documentado. Parametrizáveis — não
    hardcoded sem opção de override pelo chamador.
    """
    wacc_pp: float = 0.015
    g_perpetuo_pp: float = 0.01
    margem_ebitda_pp: float = 0.02
    crescimento_receita_pp: float = 0.03


VARIAVEIS_SENSIBILIDADE = ("wacc", "g_perpetuo", "margem_ebitda", "crescimento_receita")

_PASSO_PADRAO_POR_VARIAVEL = {
    "wacc": 0.02,
    "g_perpetuo": 0.01,
    "margem_ebitda": 0.02,
    "crescimento_receita": 0.03,
}


def _validar_wacc_g(taxa_desconto: float, taxa_crescimento_perpetuidade: float) -> None:
    if taxa_desconto <= taxa_crescimento_perpetuidade:
        raise WaccInvalidoError(
            f"WACC ({taxa_desconto:.2%}) <= g perpétuo ({taxa_crescimento_perpetuidade:.2%}) — "
            "combinação matematicamente inválida para o modelo de Gordon Growth "
            "(o valor terminal ficaria indefinido ou negativo)."
        )


def _avaliar_dcf(
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
    margem_ebitda_atual: float,
    margem_ebitda_cenario: float,
    divida_liquida: float = 0.0,
) -> float:
    """
    Ponto único de chamada a calcular_dcf() usado por gerar_cenarios() e
    gerar_matriz_sensibilidade() — garante que os dois caminhos apliquem a
    mesma trava de WACC<=g e a mesma conversão de margem->fluxo.
    """
    from valuation.dcf import calcular_dcf

    _validar_wacc_g(taxa_desconto, taxa_crescimento_perpetuidade)

    fator_margem = (margem_ebitda_cenario / margem_ebitda_atual) if margem_ebitda_atual > 0 else 1.0
    fluxo_cenario = fluxo_caixa_atual * max(fator_margem, 0.0)

    resultado = calcular_dcf(
        fluxo_caixa_atual=fluxo_cenario,
        taxa_crescimento=taxa_crescimento,
        taxa_desconto=taxa_desconto,
        anos_projecao=anos_projecao,
        taxa_crescimento_perpetuidade=taxa_crescimento_perpetuidade,
        num_acoes=num_acoes,
        preco_atual=preco_atual,
        divida_liquida=divida_liquida,
    )
    return resultado["valor_intrinseco"]


def gerar_cenarios(
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
    margem_ebitda_atual: float,
    divida_liquida: float = 0.0,
    deltas: Optional[DeltasCenario] = None,
) -> dict:
    """
    Roda o DCF existente (calcular_dcf()) três vezes: pessimista (WACC
    +delta, g perpétuo -delta, margem EBITDA -delta, crescimento de receita
    -delta), base (inputs originais) e otimista (o inverso do pessimista).

    Levanta WaccInvalidoError se qualquer uma das três combinações (base,
    pessimista ou otimista) cair em WACC<=g — nunca devolve um valor
    "calculado" a partir de um input matematicamente inválido.
    """
    deltas = deltas or DeltasCenario()

    def _cenario(delta_wacc: float, delta_g: float, delta_margem: float, delta_cresc: float) -> float:
        return _avaliar_dcf(
            fluxo_caixa_atual=fluxo_caixa_atual,
            taxa_crescimento=taxa_crescimento + delta_cresc,
            taxa_desconto=taxa_desconto + delta_wacc,
            anos_projecao=anos_projecao,
            taxa_crescimento_perpetuidade=taxa_crescimento_perpetuidade + delta_g,
            num_acoes=num_acoes,
            preco_atual=preco_atual,
            margem_ebitda_atual=margem_ebitda_atual,
            margem_ebitda_cenario=margem_ebitda_atual + delta_margem,
            divida_liquida=divida_liquida,
        )

    valor_pessimista = _cenario(
        deltas.wacc_pp, -deltas.g_perpetuo_pp, -deltas.margem_ebitda_pp, -deltas.crescimento_receita_pp
    )
    valor_base = _cenario(0.0, 0.0, 0.0, 0.0)
    valor_otimista = _cenario(
        -deltas.wacc_pp, deltas.g_perpetuo_pp, deltas.margem_ebitda_pp, deltas.crescimento_receita_pp
    )

    margem_seguranca_base = ((valor_base - preco_atual) / preco_atual) * 100 if preco_atual > 0 else None

    return {
        "preco_atual": preco_atual,
        "cenarios": {
            "pessimista": round(valor_pessimista, 2),
            "base": round(valor_base, 2),
            "otimista": round(valor_otimista, 2),
        },
        "faixa": {
            "minimo": round(min(valor_pessimista, valor_base, valor_otimista), 2),
            "maximo": round(max(valor_pessimista, valor_base, valor_otimista), 2),
        },
        "margem_seguranca_base": round(margem_seguranca_base, 2) if margem_seguranca_base is not None else None,
        "premissas_base": {
            "wacc": round(taxa_desconto, 4),
            "g_perpetuo": round(taxa_crescimento_perpetuidade, 4),
            "margem_ebitda": round(margem_ebitda_atual, 4),
            "crescimento_receita": round(taxa_crescimento, 4),
        },
        "deltas_aplicados": {
            "wacc_pp": deltas.wacc_pp,
            "g_perpetuo_pp": deltas.g_perpetuo_pp,
            "margem_ebitda_pp": deltas.margem_ebitda_pp,
            "crescimento_receita_pp": deltas.crescimento_receita_pp,
        },
    }


def gerar_matriz_sensibilidade(
    variavel_x: str,
    variavel_y: str,
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
    margem_ebitda_atual: float,
    divida_liquida: float = 0.0,
    passo_x: Optional[float] = None,
    passo_y: Optional[float] = None,
    pontos: int = 2,
) -> dict:
    """
    Matriz de fair values variando duas variáveis por vez (ex: WACC x g
    perpétuo). `pontos` é quantos passos pra cada lado do valor base (a
    matriz final tem `2*pontos+1` linhas e colunas).

    Células em que a combinação daquela linha/coluna resulta em WACC<=g
    ficam como `None` — matematicamente fora do domínio do modelo de Gordon
    Growth, não um erro de input do chamador (as bordas do range de uma
    matriz de sensibilidade legitimamente incluem combinações extremas
    inválidas, sobretudo pra empresas de alto crescimento). Isso é
    diferente de "devolver um valor errado silenciosamente": `None` marca
    explicitamente a célula como indisponível. Uma única combinação
    inválida passada diretamente (gerar_cenarios(), ou uma chamada avulsa)
    continua levantando WaccInvalidoError.
    """
    if variavel_x not in VARIAVEIS_SENSIBILIDADE or variavel_y not in VARIAVEIS_SENSIBILIDADE:
        raise ValueError(f"variavel_x/variavel_y devem ser um de {VARIAVEIS_SENSIBILIDADE}")
    if variavel_x == variavel_y:
        raise ValueError("variavel_x e variavel_y precisam ser diferentes entre si")

    passo_x = passo_x if passo_x is not None else _PASSO_PADRAO_POR_VARIAVEL[variavel_x]
    passo_y = passo_y if passo_y is not None else _PASSO_PADRAO_POR_VARIAVEL[variavel_y]

    valores_base = {
        "wacc": taxa_desconto,
        "g_perpetuo": taxa_crescimento_perpetuidade,
        "margem_ebitda": margem_ebitda_atual,
        "crescimento_receita": taxa_crescimento,
    }

    eixo_x = [valores_base[variavel_x] + i * passo_x for i in range(-pontos, pontos + 1)]
    eixo_y = [valores_base[variavel_y] + i * passo_y for i in range(-pontos, pontos + 1)]

    linhas = []
    for vy in eixo_y:
        linha = []
        for vx in eixo_x:
            cenario = dict(valores_base)
            cenario[variavel_x] = vx
            cenario[variavel_y] = vy

            if cenario["wacc"] <= cenario["g_perpetuo"]:
                linha.append(None)
                continue

            valor = _avaliar_dcf(
                fluxo_caixa_atual=fluxo_caixa_atual,
                taxa_crescimento=cenario["crescimento_receita"],
                taxa_desconto=cenario["wacc"],
                anos_projecao=anos_projecao,
                taxa_crescimento_perpetuidade=cenario["g_perpetuo"],
                num_acoes=num_acoes,
                preco_atual=preco_atual,
                margem_ebitda_atual=margem_ebitda_atual,
                margem_ebitda_cenario=cenario["margem_ebitda"],
                divida_liquida=divida_liquida,
            )
            linha.append(round(valor, 2))
        linhas.append(linha)

    return {
        "variavel_x": variavel_x,
        "variavel_y": variavel_y,
        "eixo_x": [round(v, 4) for v in eixo_x],
        "eixo_y": [round(v, 4) for v in eixo_y],
        "matriz": linhas,  # matriz[i][j] = combinação (eixo_y[i], eixo_x[j])
    }


def gerar_matrizes_padrao(
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
    margem_ebitda_atual: float,
    divida_liquida: float = 0.0,
) -> dict:
    """As 3 combinações mais relevantes pedidas: WACC×g, WACC×margem EBITDA, margem×crescimento de receita."""
    base_kwargs = dict(
        fluxo_caixa_atual=fluxo_caixa_atual,
        taxa_crescimento=taxa_crescimento,
        taxa_desconto=taxa_desconto,
        anos_projecao=anos_projecao,
        taxa_crescimento_perpetuidade=taxa_crescimento_perpetuidade,
        num_acoes=num_acoes,
        preco_atual=preco_atual,
        margem_ebitda_atual=margem_ebitda_atual,
        divida_liquida=divida_liquida,
    )
    return {
        "wacc_x_g_perpetuo": gerar_matriz_sensibilidade("wacc", "g_perpetuo", **base_kwargs),
        "wacc_x_margem_ebitda": gerar_matriz_sensibilidade("wacc", "margem_ebitda", **base_kwargs),
        "margem_ebitda_x_crescimento_receita": gerar_matriz_sensibilidade("margem_ebitda", "crescimento_receita", **base_kwargs),
    }


def gerar_analise_completa(
    fluxo_caixa_atual: float,
    taxa_crescimento: float,
    taxa_desconto: float,
    anos_projecao: int,
    taxa_crescimento_perpetuidade: float,
    num_acoes: float,
    preco_atual: float,
    margem_ebitda_atual: float,
    divida_liquida: float = 0.0,
    deltas: Optional[DeltasCenario] = None,
) -> dict:
    """Combina gerar_cenarios() + gerar_matrizes_padrao() — usado pelo endpoint /valuation/{ticker}/cenarios."""
    resultado = gerar_cenarios(
        fluxo_caixa_atual=fluxo_caixa_atual,
        taxa_crescimento=taxa_crescimento,
        taxa_desconto=taxa_desconto,
        anos_projecao=anos_projecao,
        taxa_crescimento_perpetuidade=taxa_crescimento_perpetuidade,
        num_acoes=num_acoes,
        preco_atual=preco_atual,
        margem_ebitda_atual=margem_ebitda_atual,
        divida_liquida=divida_liquida,
        deltas=deltas,
    )
    resultado["matrizes_sensibilidade"] = gerar_matrizes_padrao(
        fluxo_caixa_atual=fluxo_caixa_atual,
        taxa_crescimento=taxa_crescimento,
        taxa_desconto=taxa_desconto,
        anos_projecao=anos_projecao,
        taxa_crescimento_perpetuidade=taxa_crescimento_perpetuidade,
        num_acoes=num_acoes,
        preco_atual=preco_atual,
        margem_ebitda_atual=margem_ebitda_atual,
        divida_liquida=divida_liquida,
    )
    return resultado
