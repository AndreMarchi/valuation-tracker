# backend/tests/test_setor.py
import pytest
from valuation.setor import (
    aplicar_restricoes_setor,
    get_configuracao_setor,
    obter_pesos_setoriais,
    buscar_concorrentes_por_subsetor,
    CONFIGURACAO_PADRAO,
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
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Intermediários Financeiros",
        GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Não aplicável"


def test_banco_mantém_bazin_e_multiplos():
    """Bazin, P/L e P/VP devem permanecer válidos para bancos."""
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Bancos", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert b["classificacao"] == "Descontada"
    assert m["pl"]["classificacao"] == "Neutra"


def test_setor_geral_todos_validos():
    """Setor não mapeado deve usar todos os métodos."""
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Indústria Geral", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Descontada"
    assert d["classificacao"] == "Descontada"


def test_tech_invalida_graham_bazin_pvp():
    """Tecnologia deve invalidar Graham, Bazin e P/VP."""
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Tecnologia", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE
    )
    assert g["classificacao"] == "Não aplicável"
    assert b["classificacao"] == "Não aplicável"
    assert m["pvp"]["classificacao"] == "Não aplicável"


def test_tech_recalcula_classificacao_agregada_apos_invalidar_pvp():
    # Regressão: multiplos["classificacao"] tinha que ser recalculada DEPOIS
    # da restrição zerar P/VP, senão ficava presa ao valor "Neutra" (base
    # de PL+PVP ambos neutros) mesmo com P/VP já marcado "Não aplicável".
    m_base = {
        "pl": {"classificacao": "Descontada", "desconto": 30},
        "pvp": {"classificacao": "Descontada", "desconto": 30},
    }
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Tecnologia", GRAHAM_BASE, BAZIN_BASE, m_base, DCF_BASE
    )
    assert m["pvp"]["classificacao"] == "Não aplicável"
    # só P/L sobrou válido (Descontada) — a agregada tem que seguir só ele,
    # não continuar "Descontada" por coincidência nem virar "Neutra" à toa.
    assert m["classificacao"] == "Descontada"


def test_bancos_e_seguradoras_invalidam_ev_ebitda():
    """EV/EBITDA não se aplica a banco/seguradora — mesma família de
    Graham/DCF, decisão tomada numa investigação posterior à criação deste
    arquivo (ver CONTEXT.md)."""
    ev_ebitda_base = {"classificacao": "Descontada", "preco_justo": 42.0}
    for setor in ("Bancos", "Intermediários Financeiros", "Seguradoras"):
        g, b, m, d, e, config = aplicar_restricoes_setor(
            setor, GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE,
            ev_ebitda=ev_ebitda_base,
        )
        assert e["classificacao"] == "Não aplicável", setor
        assert e["preco_justo"] is None, setor
        assert "ev_ebitda" in config["metodos_invalidos"], setor


def test_ev_ebitda_none_nao_quebra_quando_setor_invalida():
    """Chamador que não calcula EV/EBITDA (ex: scanner/trabalhador.py) pode
    deixar o parâmetro no default None — não deve quebrar mesmo pra setor
    que invalidaria o método."""
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Bancos", GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE,
    )
    assert e is None


# ─── Endividamento não se aplica a banco/seguradora ────────────────────────
# Achado real: analisar_endividamento() recebia ebit_12m=0 pra banco (EBIT
# operacional não é um conceito limpo pra esse tipo de negócio, mesma razão
# de Graham/DCF/EV-EBITDA), caindo no ramo "else: div_ebit=0" — mostrava
# "0,0x · sem alertas" como se fosse ausência real de dívida, quando na
# verdade é "métrica não se aplica". Ver CONTEXT.md.

def test_bancos_e_seguradoras_invalidam_endividamento():
    for setor in ("Bancos", "Intermediários Financeiros", "Seguradoras"):
        config = get_configuracao_setor(setor)
        assert "endividamento" in config["metodos_invalidos"], setor
        assert config["justificativas"].get("endividamento"), setor


def test_setores_nao_financeiros_nao_invalidam_endividamento():
    for setor in ("Varejo", "Energia Elétrica", "Construção Civil", "Indústria Geral"):
        config = get_configuracao_setor(setor)
        assert "endividamento" not in config["metodos_invalidos"], setor


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
    g, b, m, d, e, config = aplicar_restricoes_setor(
        "Intermediários Financeiros",
        GRAHAM_BASE, BAZIN_BASE, MULTIPLOS_BASE, DCF_BASE,
        ticker="ITSA4"
    )
    assert g["classificacao"] == "Não aplicável"
    assert m["pl"]["classificacao"] == "Não aplicável"
    assert d["classificacao"] == "Não aplicável"


# ── regressão: string vazia é substring de qualquer coisa em Python ────────
# ("" in "bancos" é True) — mesma vulnerabilidade encontrada e corrigida em
# fcfe_valuation.py::eh_setor_bancario_ou_segurador() durante a Fase 3 do
# FCFE (ver CONTEXT.md). Sem o guard, um setor vazio/ausente casava
# incorretamente com a primeira chave de CONFIGURACAO_SETORES
# ("Intermediários Financeiros"), aplicando restrições de banco a um ticker
# sem nenhuma informação de setor.

def test_setor_vazio_nao_cai_em_classificacao_especifica():
    config = get_configuracao_setor("")
    assert config["metodos_validos"] == CONFIGURACAO_PADRAO["metodos_validos"]
    assert config["metodos_invalidos"] == CONFIGURACAO_PADRAO["metodos_invalidos"]
    assert config["metricas_ideais"] == CONFIGURACAO_PADRAO["metricas_ideais"]
    assert "dcf" not in config["metodos_invalidos"]


def test_setor_none_nao_cai_em_classificacao_especifica():
    config = get_configuracao_setor(None)
    assert config["metodos_validos"] == CONFIGURACAO_PADRAO["metodos_validos"]
    assert config["metodos_invalidos"] == CONFIGURACAO_PADRAO["metodos_invalidos"]