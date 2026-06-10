# backend/tests/test_setor.py
import pytest
from valuation.setor import (
    aplicar_restricoes_setor,
    get_configuracao_setor,
    obter_pesos_setoriais,
    buscar_concorrentes_por_subsetor
)

# Mocks base históricos que o seu arquivo de teste utiliza
GRAHAM_BASE = {"classificacao": "Descontada", "preco_justo": 50.0}
BAZIN_BASE = {"classificacao": "Descontada", "preco_justo": 60.0}
MULTIPLOS_BASE = {
    "pl": {"classificacao": "Neutra", "desconto": 0},
    "pvp": {"classificacao": "Neutra", "desconto": 0}
}
DCF_BASE = {"classificacao": "Descontada", "valor_intrinseco": 55.0}


# ── TESTES DAS NOVAS IMPLEMENTAÇÕES SETORIAIS ──

def test_deve_retornar_pesos_padrao_para_subsetor_geral():
    pesos = obter_pesos_setoriais("Geral")
    assert pesos["graham"] == 0.2
    assert pesos["dcf"] == 0.2


def test_deve_retornar_pesos_customizados_para_bancos():
    pesos = obter_pesos_setoriais("Bancos Comerciais")
    assert pesos["dcf"] == 0.0  # DCF zerado para bancos
    assert pesos["graham"] == 0.4


# ── REINTEGRAÇÃO DOS TESTES HISTÓRICOS QUE ESTAVAM FALHANDO ──

def test_banco_invalida_graham_e_dcf():
    """Para bancos Graham e DCF devem ser marcados como não aplicável."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Intermediários Financeiros",
        GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Não aplicável"


def test_banco_mantém_bazin_e_multiplos():
    """Bazin, P/L e P/VP devem permanecer válidos para bancos."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Bancos", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert b["classificacao"] == "Descontada"
    assert m["pl"]["classificacao"] == "Neutra"


def test_setor_geral_todos_validos():
    """Setor não mapeado deve usar todos os métodos."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Indústria Geral", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Descontada"
    assert d["classificacao"] == "Descontada"


def test_tech_invalida_graham_bazin_pvp():
    """Tecnologia deve invalidar Graham, Bazin e P/VP."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Tecnologia", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Não aplicável"
    assert b["classificacao"] == "Não aplicável"
    assert m["pvp"]["classificacao"] == "Não aplicável"


def test_config_setor_retorna_metricas_ideais():
    """Configuração do setor deve retornar métricas ideais."""
    config = get_configuracao_setor("Bancos")
    assert "ROE" in config["metricas_ideais"]


def test_busca_parcial_setor():
    """Deve encontrar setor por correspondência parcial."""
    config = get_configuracao_setor("Petróleo, Gás e Biocombustíveis")
    assert "EV/EBITDA" in config["metricas_ideais"]


def test_holding_invalida_graham_pl_dcf():
    """Holdings devem invalidar Graham, P/L e DCF."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Intermediários Financeiros",
        GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE,
        ticker="ITSA4"
    )
    assert g["classificacao"] == "Não aplicável"
    assert m["pl"]["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Não aplicável"