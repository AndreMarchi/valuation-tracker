from valuation.risco import analisar_risco


def test_petrobras_penalizada():
    """Petrobras deve ter penalização de empresa estatal."""
    resultado = analisar_risco("PETR4", "Petróleo e Gás Integrado", 8.0)
    assert resultado["is_estatal"] == True
    assert resultado["penalizacao"] == 2.0
    assert resultado["score_ajustado"] == 6.0


def test_empresa_privada_sem_penalizacao():
    """Empresa privada fora de setor regulado não deve ter penalização."""
    resultado = analisar_risco("MGLU3", "Varejo", 7.0)
    assert resultado["penalizacao"] == 0.0
    assert resultado["score_ajustado"] == 7.0
    assert resultado["alertas"] == []


def test_setor_regulado_penalizado():
    """Empresa privada em setor regulado deve ter penalização menor."""
    resultado = analisar_risco("VIVT3", "Telecomunicações", 7.0)
    assert resultado["penalizacao"] == 1.0
    assert resultado["score_ajustado"] == 6.0


def test_score_nao_vai_abaixo_de_zero():
    """Score ajustado nunca deve ser negativo."""
    resultado = analisar_risco("PETR4", "Petróleo e Gás Integrado", 1.0)
    assert resultado["score_ajustado"] >= 0.0


def test_alertas_retornados_para_estatal():
    """Deve retornar pelo menos um alerta para empresa estatal."""
    resultado = analisar_risco("BBAS3", "Bancos", 8.0)
    assert len(resultado["alertas"]) >= 1
    assert resultado["alertas"][0]["tipo"] == "estatal"