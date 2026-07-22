from valuation.multiplos import calcular_multiplos, classificacao_agregada_multiplos


def test_pl_descontado():
    """P/L atual bem abaixo da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=6.0, pvp_atual=1.5,
        pl_medio_historico=10.0, pvp_medio_historico=1.8,
        preco_atual=30.0
    )
    assert resultado["pl"]["classificacao"] == "Descontada"
    assert resultado["pl"]["desconto"] == 40.0


def test_pvp_descontado():
    """P/VP atual bem abaixo da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=10.0, pvp_atual=1.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=30.0
    )
    assert resultado["pvp"]["classificacao"] == "Descontada"
    assert resultado["pvp"]["desconto"] == 50.0


def test_pl_caro():
    """P/L atual acima da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=15.0, pvp_atual=2.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=50.0
    )
    assert resultado["pl"]["classificacao"] == "Cara"
    assert resultado["pl"]["desconto"] < 0


def test_pl_neutro():
    """P/L atual próximo da média histórica."""
    resultado = calcular_multiplos(
        pl_atual=9.0, pvp_atual=2.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=50.0
    )
    assert resultado["pl"]["classificacao"] == "Neutra"


def test_pl_negativo():
    """P/L negativo — empresa com prejuízo."""
    resultado = calcular_multiplos(
        pl_atual=-5.0, pvp_atual=1.5,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=20.0
    )
    assert resultado["pl"]["classificacao"] == "Não aplicável"
    assert resultado["pl"]["desconto"] is None


# ─── classificação agregada (bug pré-existente corrigido) ──────────────────
# Achado real: calcular_multiplos() nunca retornava uma chave "classificacao"
# no nível raiz do dict — só "pl"/"pvp" aninhados. O pilar
# "patrimonial_multiplos" da Matriz de Consenso (main.py) lia
# multiplos.get("classificacao", "") e SEMPRE caía em "Não aplicável", pra
# QUALQUER ticker, não só setores com restrição — descoberto durante a
# investigação de EV/EBITDA pra bancos (ver CONTEXT.md).

def test_classificacao_agregada_aparece_no_retorno():
    resultado = calcular_multiplos(
        pl_atual=6.0, pvp_atual=1.0,
        pl_medio_historico=10.0, pvp_medio_historico=2.0,
        preco_atual=30.0,
    )
    assert "classificacao" in resultado
    assert resultado["classificacao"] == "Descontada"


def test_agregada_todos_descontados_e_descontada():
    assert classificacao_agregada_multiplos("Descontada", "Descontada") == "Descontada"


def test_agregada_todos_caros_e_cara():
    assert classificacao_agregada_multiplos("Cara", "Cara") == "Cara"


def test_agregada_sinal_misto_e_neutra():
    assert classificacao_agregada_multiplos("Descontada", "Cara") == "Neutra"
    assert classificacao_agregada_multiplos("Descontada", "Neutra") == "Neutra"
    assert classificacao_agregada_multiplos("Neutra", "Neutra") == "Neutra"


def test_agregada_um_nao_aplicavel_usa_so_o_outro():
    # Só P/L válido (ex: PVP negativo) — a agregada segue o que sobrou.
    assert classificacao_agregada_multiplos("Descontada", "Não aplicável") == "Descontada"
    assert classificacao_agregada_multiplos("Não aplicável", "Cara") == "Cara"


def test_agregada_ambos_nao_aplicaveis_e_nao_aplicavel():
    assert classificacao_agregada_multiplos("Não aplicável", "Não aplicável") == "Não aplicável"