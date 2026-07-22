# backend/scorecard_qualitativo.py
"""
Scorecard Qualitativo — captura avaliação qualitativa (moat, gestão,
concentração de clientes, risco regulatório, poder de precificação) como
input estruturado, e converte isso num ajuste BOUNDED aplicado ao Score de
Atratividade (valuation/score.py::calcular_score()) já existente — não cria
um score paralelo desconectado do resto do app: o resultado final
(`score_ajustado_qualitativo`) é sempre `score_base + ajuste`, nunca um
número novo e independente.

Este módulo não pretende automatizar julgamento qualitativo — as 5
dimensões são preenchidas manualmente pelo analista (via sliders no
frontend), o módulo só formaliza a CONVERSÃO desse julgamento num ajuste
numérico consistente e limitado.
"""

from dataclasses import dataclass

CAMPOS_DIMENSAO = ("moat", "gestao", "concentracao_clientes", "risco_regulatorio", "poder_precificacao")

# Teto do ajuste (em pontos, na mesma escala 0-10 do Score de Atratividade).
# Mesma ordem de grandeza das penalizações já existentes no projeto
# (valuation/endividamento.py: 0.5 a 2.5 pontos; valuation/risco.py:
# PENALIZACAO_*) — um valor consistente com o resto do app, não inventado
# do zero. 1.5 pontos (15% da escala 0-10) garante que o scorecard
# qualitativo NUNCA domina o resultado quantitativo: mesmo no caso mais
# extremo (scorecard perfeito 10/10 em tudo), um ativo com score_base=1
# ("Cara/Evitar") sai no máximo em 2.5 — ainda longe de "Muito Atrativa"
# (>=8). O ajuste é uma nuance, não um veredito por si só.
TETO_AJUSTE_PONTOS = 1.5


@dataclass
class ScorecardQualitativo:
    """
    5 dimensões, cada uma 0-10. A escala abaixo é fixa — usá-la sempre com
    o mesmo significado é o que torna scorecards comparáveis entre
    análises diferentes ao longo do tempo (o critério pra um "7" hoje
    precisa ser o mesmo daqui a 6 meses, senão o histórico perde sentido).

    Em TODAS as dimensões, 10 = melhor pro caso de investimento (nunca
    "mais" de um jeito ambíguo) — inclusive `concentracao_clientes`, onde
    10 significa "bem diversificada" (nota alta = MENOS concentração de
    risco), não "muito concentrada":

    - moat (vantagem competitiva sustentável):
        0-2  nenhuma barreira de entrada, produto/serviço commodity, fácil de replicar
        3-5  alguma diferenciação (marca, escala, custo), replicável em poucos anos
        6-8  barreira relevante (rede, marca forte, regulação, custo de troca)
        9-10 monopólio/quase-monopólio estrutural, vantagem muito difícil de replicar

    - gestao (qualidade e alinhamento de gestão/governança):
        0-2  histórico de destruição de valor, governança fraca, conflitos recorrentes
        3-5  gestão mediana, sem red flags graves nem track record excepcional
        6-8  bom histórico de alocação de capital, governança adequada
        9-10 gestão classe mundial, track record consistente de criação de valor

    - concentracao_clientes (diversificação da base de clientes/receita):
        0-2  >50% da receita em poucos clientes/1 contrato, sem diversificação
        3-5  concentração moderada, alguma dependência de poucos clientes-chave
        6-8  base de clientes razoavelmente diversificada
        9-10 receita pulverizada, nenhum cliente individual relevante

    - risco_regulatorio (ausência de exposição a risco regulatório/político):
        0-2  setor fortemente regulado/politizado, histórico de intervenção adversa
        3-5  alguma exposição regulatória, mudanças de regra possíveis
        6-8  regulação estável e previsível
        9-10 pouca ou nenhuma exposição regulatória relevante

    - poder_precificacao (capacidade de repassar custos/aumentar preços):
        0-2  sem poder de precificação, tomador de preço (commodity pura)
        3-5  poder de precificação limitado, repasse parcial e defasado
        6-8  consegue repassar custos com razoável consistência
        9-10 forte poder de precificação, demanda inelástica

    Default 5.0 (neutro) em todas — ausência de avaliação explícita não
    deve, por si só, penalizar nem beneficiar o score (ver
    calcular_ajuste_qualitativo: média=5 -> ajuste=0).
    """
    moat: float = 5.0
    gestao: float = 5.0
    concentracao_clientes: float = 5.0
    risco_regulatorio: float = 5.0
    poder_precificacao: float = 5.0

    def __post_init__(self):
        for campo in CAMPOS_DIMENSAO:
            valor = getattr(self, campo)
            if not (0.0 <= valor <= 10.0):
                raise ValueError(f"{campo} precisa estar entre 0 e 10 (recebido: {valor})")


def calcular_ajuste_qualitativo(scorecard: ScorecardQualitativo, teto_ajuste_pontos: float = TETO_AJUSTE_PONTOS) -> dict:
    """
    Ajuste ADITIVO, não multiplicativo — decisão de modelagem explícita:

    Um ajuste MULTIPLICATIVO (`score_ajustado = score_base * fator`)
    trava qualquer ativo com `score_base = 0` em 0 pra sempre (0 ×
    qualquer fator continua 0), mesmo com um scorecard qualitativo
    perfeito — indefensável, já que `score_base = 0` é um valor legítimo
    dentro da escala 0-10 (não um "erro"/ausência de dado), e um ativo com
    fundamentos quantitativos ruins mas moat/gestão excepcionais deveria
    poder ser nudged pra cima, dentro de um limite. Um ajuste ADITIVO não
    tem essa patologia: `score_base = 0` ainda pode receber até
    `+teto_ajuste_pontos`.

    Fórmula: `ajuste = (média_das_5_dimensões - 5.0) / 5.0 * teto_ajuste_pontos`
    — média=5 (neutro) -> ajuste=0; média=10 (scorecard perfeito) ->
    ajuste=+teto; média=0 (scorecard péssimo) -> ajuste=-teto. Como a
    média de 5 valores em [0,10] está sempre em [0,10], `ajuste` já cai
    sempre dentro de `[-teto, +teto]` sem precisar de clamp adicional
    aqui (o clamp do SCORE FINAL fica em aplicar_ajuste_ao_score(), pra
    cobrir o caso de `score_base` já estar perto da borda 0/10).
    """
    dimensoes = [getattr(scorecard, campo) for campo in CAMPOS_DIMENSAO]
    media = sum(dimensoes) / len(dimensoes)
    ajuste = (media - 5.0) / 5.0 * teto_ajuste_pontos
    return {
        "media_dimensoes": round(media, 2),
        "ajuste_pontos": round(ajuste, 2),
        "teto_ajuste_pontos": teto_ajuste_pontos,
    }


def aplicar_ajuste_ao_score(
    score_base: float,
    scorecard: ScorecardQualitativo,
    teto_ajuste_pontos: float = TETO_AJUSTE_PONTOS,
) -> dict:
    """
    Aplica o ajuste qualitativo ao Score de Atratividade REAL daquele
    ticker (`score_base`, vindo de valuation/score.py::calcular_score())
    — nunca um score inventado à parte. `score_ajustado_qualitativo` é
    clampado em [0, 10] (a escala do Score de Atratividade), cobrindo o
    caso de `score_base` já estar perto de uma borda (ex: score_base=10,
    ajuste=+1.2 -> clampado de volta em 10, não 11.2).
    """
    resultado_ajuste = calcular_ajuste_qualitativo(scorecard, teto_ajuste_pontos)
    score_ajustado = max(0.0, min(10.0, score_base + resultado_ajuste["ajuste_pontos"]))
    return {
        "score_base": round(score_base, 2),
        **resultado_ajuste,
        "score_ajustado_qualitativo": round(score_ajustado, 2),
    }
