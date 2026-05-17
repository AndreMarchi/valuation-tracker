from valuation.capm import calcular_capm


def test_capm_retorna_campos_obrigatorios():
    resultado = calcular_capm("Varejo")
    assert "taxa_desconto" in resultado
    assert "beta" in resultado
    assert "selic" in resultado


def test_capm_setor_conhecido():
    """Setor conhecido deve usar beta específico."""
    resultado = calcular_capm("Transporte Aéreo")
    assert resultado["beta"] == 1.50
    assert resultado["taxa_desconto"] > 0.14


def test_capm_setor_desconhecido():
    """Setor desconhecido deve usar beta padrão 1.0."""
    resultado = calcular_capm("Setor Inexistente")
    assert resultado["beta"] == 1.0


def test_capm_beta_manual():
    """Beta manual deve sobrescrever o padrão do setor."""
    resultado = calcular_capm("Varejo", beta=0.75)
    assert resultado["beta"] == 0.75


def test_capm_taxa_maior_que_selic():
    """Taxa de desconto deve ser sempre maior que a Selic."""
    resultado = calcular_capm("Tecnologia")
    assert resultado["taxa_desconto"] > resultado["selic"]