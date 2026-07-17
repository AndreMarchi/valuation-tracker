"""
saude_financeira.py
Calcula score de saúde financeira (0-10) e retroalimenta o valuation
com taxa de crescimento mais precisa baseada em dados trimestrais da CVM.
"""

import logging

logger = logging.getLogger(__name__)


def calcular_saude_financeira(dados_cvm: dict) -> dict:
    """
    Recebe o dict retornado por buscar_saude_financeira_cvm()
    e devolve score, classificação e insights para o frontend.
    """
    if not dados_cvm.get("disponivel"):
        return {
            "disponivel": False,
            "erro": dados_cvm.get("erro", "Dados CVM indisponíveis"),
        }

    score = 5.0  # base neutra
    alertas = []
    destaques = []

    # ── 1. Tendência de receita ──────────────────────────────────────────────
    tendencia = dados_cvm.get("tendencia_receita", "estável")
    if tendencia == "crescendo":
        score += 1.5
        destaques.append("Receita em crescimento nos últimos trimestres")
    elif tendencia == "caindo":
        score -= 1.5
        alertas.append("Receita em queda nos últimos trimestres")

    # ── 2. Qualidade do lucro (FCO / Lucro Líquido) ──────────────────────────
    qualidade = dados_cvm.get("qualidade_lucro")
    if qualidade is not None:
        if qualidade >= 1.2:
            score += 1.5
            destaques.append(f"Excelente geração de caixa operacional ({qualidade:.1f}x o lucro)")
        elif qualidade >= 0.8:
            score += 0.5
            destaques.append(f"Boa qualidade de lucro (FCO/Lucro: {qualidade:.1f}x)")
        elif qualidade >= 0.5:
            score -= 0.5
            alertas.append(f"Lucro parcialmente sustentado por caixa (FCO/Lucro: {qualidade:.1f}x)")
        else:
            score -= 1.5
            alertas.append(f"Qualidade de lucro preocupante — FCO muito abaixo do lucro contábil ({qualidade:.1f}x)")

    # ── 3. Margem líquida — estabilidade ────────────────────────────────────
    margens = dados_cvm.get("margens_pct", [])
    if len(margens) >= 3:
        margem_media = sum(margens) / len(margens)
        margem_ultima = margens[-1]

        if margem_media >= 15:
            score += 1.0
            destaques.append(f"Margem líquida média elevada: {margem_media:.1f}%")
        elif margem_media >= 8:
            score += 0.3
        elif margem_media < 0:
            score -= 1.5
            alertas.append(f"Margem líquida negativa em média: {margem_media:.1f}%")

        # tendência de margem
        if len(margens) >= 4 and margem_ultima > margens[-4] * 1.1:
            score += 0.5
            destaques.append("Margem líquida em expansão")
        elif len(margens) >= 4 and margem_ultima < margens[-4] * 0.9:
            score -= 0.5
            alertas.append("Margem líquida em compressão")

    # ── 4. Alavancagem (Dívida Bruta/EBITDA) ─────────────────────────────────
    # "Bruta", não "líquida": a CVM não disponibiliza o lado do Ativo do
    # balanço (BPA), onde ficariam Caixa/Aplicações Financeiras — ver
    # CONTEXT.md. Dívida bruta é sempre >= dívida líquida, então o erro
    # é sempre para o lado conservador (nunca esconde alavancagem real).
    divida_ebitda = dados_cvm.get("divida_bruta_ebitda")
    alavancagem_critica = False
    if divida_ebitda is not None:
        if divida_ebitda <= 1.0:
            score += 1.0
            destaques.append(f"Baixa alavancagem: Dívida Bruta/EBITDA de {divida_ebitda:.1f}x")
        elif divida_ebitda <= 2.5:
            pass  # faixa neutra
        elif divida_ebitda <= 4.0:
            score -= 1.0
            alertas.append(f"Alavancagem elevada: Dívida Bruta/EBITDA de {divida_ebitda:.1f}x")
        else:
            score -= 2.5
            alavancagem_critica = True
            alertas.append(f"Alavancagem crítica: Dívida Bruta/EBITDA de {divida_ebitda:.1f}x")

    # ── 5. Descasamento cambial da dívida ────────────────────────────────────
    # pct da dívida (Empréstimos e Financiamentos) em moeda estrangeira menos
    # pct da receita em moeda estrangeira (assumida 0% salvo override manual
    # — a CVM não disponibiliza composição cambial de receita). Dívida em
    # dólar sem receita em dólar correspondente é risco de descasamento: uma
    # desvalorização cambial infla a dívida em reais sem contrapartida.
    descasamento_pp = dados_cvm.get("descasamento_cambial_pp")
    descasamento_critico = False
    if descasamento_pp is not None:
        if descasamento_pp >= 40:
            score -= 2.0
            alertas.append(f"Descasamento cambial relevante: {descasamento_pp:.0f} p.p. de dívida em moeda estrangeira acima da receita")
        elif descasamento_pp >= 20:
            score -= 0.8
            alertas.append(f"Descasamento cambial moderado: {descasamento_pp:.0f} p.p. de dívida em moeda estrangeira acima da receita")
        if descasamento_pp >= 50:
            descasamento_critico = True

    # clamp 0–10
    score = round(max(0.0, min(10.0, score)), 1)

    # ── 6. Trava de risco crítico ────────────────────────────────────────────
    # Alavancagem >4x OU descasamento cambial >=50 p.p. não pode ser diluído
    # pela média dos outros pilares — o risco é grave o suficiente para
    # travar a classificação em "Fraca" (score <= 4.5) independentemente do
    # restante do cálculo.
    if alavancagem_critica or descasamento_critico:
        score = min(score, 4.5)

    classificacao = (
        "Excelente" if score >= 8 else
        "Boa"       if score >= 6 else
        "Neutra"    if score >= 4 else
        "Fraca"     if score >= 2 else
        "Crítica"
    )

    return {
        "disponivel": True,
        "score": score,
        "classificacao": classificacao,
        "tendencia_receita": tendencia,
        "qualidade_lucro": qualidade,
        "margens_pct": margens,
        "divida_bruta_ebitda": divida_ebitda,
        "pct_divida_moeda_estrangeira": dados_cvm.get("pct_divida_moeda_estrangeira"),
        "descasamento_cambial_pp": descasamento_pp,
        "receita_trimestral": dados_cvm.get("receita_trimestral", []),
        "lucro_trimestral": dados_cvm.get("lucro_trimestral", []),
        "fco_trimestral": dados_cvm.get("fco_trimestral", []),
        "alertas": alertas,
        "destaques": destaques,
        "cd_cvm": dados_cvm.get("cd_cvm"),
    }


def extrair_crescimento_cvm(dados_cvm: dict):
    """
    Calcula taxa de crescimento de receita com base nos dados trimestrais da CVM.
    Usado para substituir o crescimento_receita_5a do Fundamentus quando disponível.
    Retorna valor decimal (ex: 0.12 = 12%) ou None se dados insuficientes.
    """
    if not dados_cvm.get("disponivel"):
        return None

    receita = dados_cvm.get("receita_trimestral", [])
    if len(receita) < 4:
        return None

    try:
        # compara soma dos últimos 4 trimestres vs 4 anteriores (YoY)
        recentes = sum(r["valor"] for r in receita[-4:])
        anteriores = sum(r["valor"] for r in receita[-8:-4]) if len(receita) >= 8 else None

        if anteriores and anteriores > 0:
            crescimento = (recentes - anteriores) / anteriores
            # limita entre -30% e +50%
            return round(max(-0.30, min(0.50, crescimento)), 4)
    except Exception:
        pass

    return None
