import ast
from pathlib import Path

from valuation.crescimento import (
    detectar_fase_crescimento,
    calcular_peg_ratio,
    calcular_ev_receita,
    calcular_rule_of_40,
    calcular_dcf_duas_fases,
)


def test_detectar_crescimento_alto():
    assert detectar_fase_crescimento(0.20) == "alto"


def test_detectar_crescimento_medio():
    assert detectar_fase_crescimento(0.10) == "medio"


def test_detectar_crescimento_maduro():
    assert detectar_fase_crescimento(0.03) == "maduro"


def test_peg_descontado():
    """P/L 10x com crescimento 20% → PEG 0.5 → descontada."""
    resultado = calcular_peg_ratio(pl=10.0, crescimento_lucro=0.20)
    assert resultado["peg"] == 0.5
    assert resultado["classificacao"] == "Descontada"


def test_peg_caro():
    """P/L 50x com crescimento 10% → PEG 5.0 → cara."""
    resultado = calcular_peg_ratio(pl=50.0, crescimento_lucro=0.10)
    assert resultado["classificacao"] == "Cara"


def test_peg_nao_aplicavel():
    """Crescimento negativo → não aplicável."""
    resultado = calcular_peg_ratio(pl=10.0, crescimento_lucro=-0.05)
    assert resultado["classificacao"] == "Não aplicável"


def test_rule_of_40_excelente():
    """Crescimento 40% + Margem 30% = 70% → excelente."""
    resultado = calcular_rule_of_40(0.40, 0.30)
    assert resultado["rule_of_40"] == 70.0
    assert resultado["classificacao"] == "Excelente"


def test_rule_of_40_saudavel():
    """Crescimento 20% + Margem 25% = 45% → saudável."""
    resultado = calcular_rule_of_40(0.20, 0.25)
    assert resultado["classificacao"] == "Saudável"


def test_rule_of_40_preocupante():
    """Crescimento 5% + Margem 5% = 10% → preocupante."""
    resultado = calcular_rule_of_40(0.05, 0.05)
    assert resultado["classificacao"] == "Preocupante"


def test_dcf_duas_fases_retorna_campos():
    resultado = calcular_dcf_duas_fases(
        lucro_por_acao=2.29,
        crescimento_fase1=0.20,
        anos_fase1=5,
        crescimento_fase2=0.04,
        ke=0.14,
        preco_atual=72.53,
    )
    assert "valor_intrinseco" in resultado
    assert "cenarios" in resultado
    assert resultado["cenarios"]["otimista"] > resultado["cenarios"]["base"]
    assert resultado["cenarios"]["pessimista"] < resultado["cenarios"]["base"]


def test_dcf_duas_fases_lpa_negativo():
    resultado = calcular_dcf_duas_fases(
        lucro_por_acao=-1.0,
        crescimento_fase1=0.20,
        anos_fase1=5,
        crescimento_fase2=0.04,
        ke=0.14,
        preco_atual=50.0,
    )
    assert resultado["classificacao"] == "Não aplicável"


# ─── Ke vs WACC (bug estrutural corrigido) ─────────────────────────────────
# calcular_dcf_duas_fases() desconta LPA (fluxo de EQUITY) — precisa ser
# descontado ao Ke, nunca à WACC. Numa empresa endividada, WACC < Ke sempre
# (mistura dívida mais barata via tax shield), então descontar à WACC infla
# o valor justo. Ver CONTEXT.md (achado real: BEEF3, WACC 14,55% vs Ke
# 20,18%, inflação de +59,3% no valor_intrinseco antes da correção).

def test_descontar_ao_ke_correto_da_valor_menor_que_descontar_a_wacc_antiga():
    """Caso normal de empresa endividada: Ke > WACC. O valor_intrinseco
    calculado com o Ke correto deve ser estritamente MENOR que o mesmo
    cálculo com a WACC (mais baixa) — confirma a DIREÇÃO do efeito, não só
    que o resultado mudou."""
    params_comuns = dict(
        lucro_por_acao=0.71,
        crescimento_fase1=0.177,
        anos_fase1=5,
        crescimento_fase2=0.04,
        preco_atual=3.68,
    )
    wacc = 0.1455  # menor que o Ke — caso normal de empresa endividada
    ke = 0.2018

    resultado_com_wacc_errada = calcular_dcf_duas_fases(**params_comuns, ke=wacc)
    resultado_com_ke_correto = calcular_dcf_duas_fases(**params_comuns, ke=ke)

    assert resultado_com_ke_correto["valor_intrinseco"] < resultado_com_wacc_errada["valor_intrinseco"]
    # mesma direção nos três cenários, não só no base
    assert resultado_com_ke_correto["cenarios"]["otimista"] < resultado_com_wacc_errada["cenarios"]["otimista"]
    assert resultado_com_ke_correto["cenarios"]["pessimista"] < resultado_com_wacc_errada["cenarios"]["pessimista"]


def test_ev_receita_descontado():
    resultado = calcular_ev_receita(
        psr_atual=0.8,
        setor="Material de Transporte",
        receita_12m=43_000_000_000,
        num_acoes=740_000_000,
        div_liquida=5_000_000_000,
        valor_mercado=50_000_000_000,
    )
    assert resultado["classificacao"] == "Descontada"


# ─── crescimento de LUCRO, não de RECEITA, pra projetar o LPA ──────────────
# Achado real (Status Invest): CAGR de Receita 5a da BEEF3 = +23,09%, CAGR
# de Lucro 5a = +0,42% — main.py usava crescimento_5a (receita) direto como
# crescimento_fase1 do DCF Duas Fases, que projeta LPA (fluxo de lucro).
# Corrigido: main.py agora usa buscar_crescimento_lucro_anual_cvm() (CVM,
# testado em test_crescimento_lucro_cvm.py) com piso conservador de 2%
# quando indisponível — nunca mais crescimento_5a bruto.

def test_main_py_nao_usa_crescimento_5a_bruto_no_dcf_duas_fases():
    """Checagem estática (AST) do call site em main.py: o argumento
    crescimento_fase1 de calcular_dcf_duas_fases() não pode ser a variável
    crescimento_5a (receita) diretamente — reintroduziria o bug."""
    main_py = Path(__file__).parent.parent / "main.py"
    arvore = ast.parse(main_py.read_text(encoding="utf-8"), filename=str(main_py))

    chamadas = [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "calcular_dcf_duas_fases"
    ]
    assert chamadas, "Nenhuma chamada a calcular_dcf_duas_fases() encontrada em main.py — teste não protege nada."

    for chamada in chamadas:
        for kw in chamada.keywords:
            if kw.arg != "crescimento_fase1":
                continue
            # aceita variável (ex: crescimento_lucro_fase1) ou expressão —
            # só rejeita explicitamente o nome da variável de receita bruta,
            # com ou sem min(..., 0.30) por cima.
            nos_da_expressao = list(ast.walk(kw.value))
            nomes_usados = {n.id for n in nos_da_expressao if isinstance(n, ast.Name)}
            assert "crescimento_5a" not in nomes_usados, (
                f"main.py:{chamada.lineno} — crescimento_fase1 ainda referencia 'crescimento_5a' "
                "(crescimento de RECEITA) — LPA é fluxo de LUCRO, precisa de "
                "buscar_crescimento_lucro_anual_cvm() ou equivalente, não crescimento_5a bruto."
            )