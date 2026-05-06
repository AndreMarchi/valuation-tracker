from valuation.dcf import calcular_dcf

# Dados base reutilizados nos testes
DADOS_BASE = dict(
    fluxo_caixa_atual=1000.0,
    taxa_crescimento=0.10,
    taxa_desconto=0.12,
    anos_projecao=5,
    taxa_crescimento_perpetuidade=0.03,
    num_acoes=500.0,
    preco_atual=30.0,
)


def test_dcf_retorna_campos_obrigatorios():
    """Resultado deve conter todos os campos esperados."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert "valor_intrinseco" in resultado
    assert "margem_seguranca" in resultado
    assert "classificacao" in resultado
    assert "cenarios" in resultado


def test_dcf_cenarios_presentes():
    """Deve retornar os três cenários: otimista, base e pessimista."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert "otimista" in resultado["cenarios"]
    assert "base" in resultado["cenarios"]
    assert "pessimista" in resultado["cenarios"]


def test_dcf_cenario_otimista_maior_que_base():
    """Cenário otimista deve ser sempre maior que o base."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert resultado["cenarios"]["otimista"] > resultado["cenarios"]["base"]


def test_dcf_cenario_pessimista_menor_que_base():
    """Cenário pessimista deve ser sempre menor que o base."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert resultado["cenarios"]["pessimista"] < resultado["cenarios"]["base"]


def test_dcf_classificacao_valida():
    """Classificação deve ser sempre um dos três valores válidos."""
    resultado = calcular_dcf(**DADOS_BASE)
    assert resultado["classificacao"] in ["Descontada", "Neutra", "Cara"]


def test_dcf_margem_coerente_com_classificacao():
    """Margem de segurança deve ser coerente com a classificação."""
    resultado = calcular_dcf(**DADOS_BASE)
    if resultado["classificacao"] == "Descontada":
        assert resultado["margem_seguranca"] >= 20
    elif resultado["classificacao"] == "Neutra":
        assert 0 <= resultado["margem_seguranca"] < 20
    else:
        assert resultado["margem_seguranca"] < 0