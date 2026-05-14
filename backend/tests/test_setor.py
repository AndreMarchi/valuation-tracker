from valuation.setor import get_configuracao_setor, aplicar_restricoes_setor

GRAHAM_BASE  = {"classificacao": "Descontada", "preco_justo": 28.0, "margem_seguranca": 80.0}
BAZIN_BASE   = {"classificacao": "Descontada", "preco_justo": 20.0, "margem_seguranca": 30.0}
DCF_BASE     = {"classificacao": "Descontada", "valor_intrinseco": 30.0, "margem_seguranca": 90.0, "cenarios": {}}
MULTIPLOS_BASE = {
    "preco_atual": 15.0,
    "pl":  {"classificacao": "Neutra", "valor": 7.0, "media_historica": 8.0, "desconto": 12.0},
    "pvp": {"classificacao": "Neutra", "valor": 0.95, "media_historica": 1.2, "desconto": 20.0},
}


def test_banco_invalida_graham_e_dcf():
    """Para bancos Graham e DCF devem ser marcados como não aplicável."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Intermediários Financeiros",
        GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Não aplicável"
    assert b["classificacao"] == "Descontada"  # Bazin válido


def test_banco_mantém_bazin_e_multiplos():
    """Bazin, P/L e P/VP devem permanecer válidos para bancos."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Bancos", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert b["classificacao"] == "Descontada"
    assert m["pl"]["classificacao"] == "Neutra"
    assert m["pvp"]["classificacao"] == "Neutra"


def test_setor_geral_todos_validos():
    """Setor não mapeado deve usar todos os métodos."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Indústria Geral", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Descontada"
    assert b["classificacao"] == "Descontada"
    assert d["classificacao"] == "Descontada"


def test_tech_invalida_graham_bazin_pvp():
    """Tecnologia deve invalidar Graham, Bazin e P/VP."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Tecnologia", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Não aplicável"
    assert b["classificacao"] == "Não aplicável"
    assert m["pvp"]["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Descontada"  # DCF válido


def test_config_setor_retorna_metricas_ideais():
    """Configuração do setor deve retornar métricas ideais."""
    config = get_configuracao_setor("Bancos")
    assert "metricas_ideais" in config
    assert len(config["metricas_ideais"]) > 0


def test_busca_parcial_setor():
    """Deve encontrar setor por correspondência parcial."""
    config = get_configuracao_setor("Petróleo, Gás e Biocombustíveis")
    assert "graham" in config["metodos_invalidos"]

def test_holding_invalida_graham_pl_dcf():
    """Holdings devem invalidar Graham, P/L e DCF."""
    g, b, m, d, config = aplicar_restricoes_setor(
        "Intermediários Financeiros",
        GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE,
        ticker="ITSA4"
    )
    assert g["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Não aplicável"
    assert m["pl"]["classificacao"] == "Não aplicável"
    assert b["classificacao"] == "Descontada"  # Bazin válido
    assert m["pvp"]["classificacao"] == "Neutra"  # P/VP válido