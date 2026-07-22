import json

import pytest

import sotp as sotp_module
from sotp import (
    Segmento,
    ConfiguracaoSotp,
    calcular_ev_segmento,
    calcular_sotp,
    carregar_configuracao_sotp,
)
from valuation.dcf import calcular_dcf


# ─── calcular_ev_segmento() — cada método isolado ───────────────────────────

def test_segmento_ev_ebitda_calcula_multiplicacao_direta():
    segmento = Segmento(nome="Braço Financeiro", metodo="ev_ebitda", ebitda=1000.0, multiplo_ev_ebitda=8.0)
    resultado = calcular_ev_segmento(segmento)
    assert resultado["erro"] is None
    assert resultado["ev"] == pytest.approx(8000.0)
    assert resultado["nome"] == "Braço Financeiro"
    assert resultado["metodo"] == "ev_ebitda"


def test_segmento_ev_receita_calcula_multiplicacao_direta():
    segmento = Segmento(nome="Braço Varejo", metodo="ev_receita", receita=5000.0, multiplo_ev_receita=1.5)
    resultado = calcular_ev_segmento(segmento)
    assert resultado["erro"] is None
    assert resultado["ev"] == pytest.approx(7500.0)


def test_segmento_dcf_bate_com_calcular_dcf_direto_num_acoes_1_divida_0():
    """O EV do segmento DCF tem que ser IDÊNTICO a chamar calcular_dcf()
    direto com num_acoes=1/divida_liquida=0 — prova que calcular_ev_segmento
    reaproveita o motor de verdade, não reimplementa a fórmula."""
    segmento = Segmento(
        nome="Braço Industrial", metodo="dcf",
        fluxo_caixa_atual=1000.0, taxa_crescimento=0.08, taxa_desconto=0.12,
        anos_projecao=5, taxa_crescimento_perpetuidade=0.03,
    )
    resultado = calcular_ev_segmento(segmento)
    esperado = calcular_dcf(
        fluxo_caixa_atual=1000.0, taxa_crescimento=0.08, taxa_desconto=0.12,
        anos_projecao=5, taxa_crescimento_perpetuidade=0.03,
        num_acoes=1.0, preco_atual=1.0, divida_liquida=0.0,
    )
    assert resultado["erro"] is None
    assert resultado["ev"] == esperado["valor_intrinseco"]


def test_segmento_ev_ebitda_campos_ausentes_retorna_erro_nao_quebra():
    segmento = Segmento(nome="X", metodo="ev_ebitda")
    resultado = calcular_ev_segmento(segmento)
    assert resultado["ev"] is None
    assert resultado["erro"] is not None


def test_segmento_dcf_wacc_menor_ou_igual_a_g_retorna_erro_tratado():
    """Mesma trava de WACC<=g de cenarios_sensibilidade.py — não pode
    devolver o 0.0 silencioso que calcular_dcf() sozinho devolveria."""
    segmento = Segmento(
        nome="Braço Regulado", metodo="dcf",
        fluxo_caixa_atual=1000.0, taxa_crescimento=0.05, taxa_desconto=0.03,
        anos_projecao=5, taxa_crescimento_perpetuidade=0.03,
    )
    resultado = calcular_ev_segmento(segmento)
    assert resultado["ev"] is None
    assert "WACC" in resultado["erro"]


def test_segmento_metodo_desconhecido_retorna_erro():
    segmento = Segmento(nome="X", metodo="metodo_invalido")  # type: ignore[arg-type]
    resultado = calcular_ev_segmento(segmento)
    assert resultado["ev"] is None
    assert resultado["erro"] is not None


# ─── calcular_sotp() — configuração sintética de 2-3 segmentos conhecidos ───
# Segmento 1 (Financeiro, ev_ebitda): EBITDA 1000 x múltiplo 8.0  = EV 8000
# Segmento 2 (Industrial, ev_ebitda): EBITDA  500 x múltiplo 5.0  = EV 2500
# Segmento 3 (Varejo,     ev_receita): Receita 2000 x múltiplo 1.2 = EV 2400
# EV consolidado bruto = 8000 + 2500 + 2400 = 12900
# Dívida líquida consolidada = 3000
# Equity bruto = 12900 - 3000 = 9900
# Desconto de holding 20% -> Equity pós-desconto = 9900 * 0.8 = 7920
# Num. ações = 1000 -> preço justo = 7920 / 1000 = 7.92

def _configuracao_sintetica(desconto_holding_pct: float = 0.20) -> ConfiguracaoSotp:
    return ConfiguracaoSotp(
        segmentos=[
            Segmento(nome="Financeiro", metodo="ev_ebitda", ebitda=1000.0, multiplo_ev_ebitda=8.0),
            Segmento(nome="Industrial", metodo="ev_ebitda", ebitda=500.0, multiplo_ev_ebitda=5.0),
            Segmento(nome="Varejo", metodo="ev_receita", receita=2000.0, multiplo_ev_receita=1.2),
        ],
        divida_liquida_consolidada=3000.0,
        num_acoes=1000.0,
        desconto_holding_pct=desconto_holding_pct,
    )


def test_sotp_soma_evs_dos_segmentos_corretamente():
    resultado = calcular_sotp(_configuracao_sintetica())
    assert resultado["ev_consolidado_bruto"] == pytest.approx(12900.0)
    assert len(resultado["segmentos"]) == 3
    assert resultado["segmentos_com_erro"] == []


def test_sotp_subtrai_divida_liquida_consolidada_uma_unica_vez():
    resultado = calcular_sotp(_configuracao_sintetica(desconto_holding_pct=0.0))
    assert resultado["valor_equity_bruto"] == pytest.approx(9900.0)


def test_sotp_aplica_desconto_de_holding():
    resultado = calcular_sotp(_configuracao_sintetica(desconto_holding_pct=0.20))
    assert resultado["valor_equity_pos_desconto"] == pytest.approx(7920.0)
    assert resultado["preco_justo_por_acao"] == pytest.approx(7.92)


def test_sotp_desconto_holding_zero_nao_muda_valor_equity():
    com_zero = calcular_sotp(_configuracao_sintetica(desconto_holding_pct=0.0))
    assert com_zero["valor_equity_pos_desconto"] == com_zero["valor_equity_bruto"]


def test_sotp_desconto_holding_e_parametrizavel_nao_hardcoded():
    resultado_10 = calcular_sotp(_configuracao_sintetica(desconto_holding_pct=0.10))
    resultado_30 = calcular_sotp(_configuracao_sintetica(desconto_holding_pct=0.30))
    assert resultado_10["valor_equity_pos_desconto"] > resultado_30["valor_equity_pos_desconto"]
    assert resultado_10["desconto_holding_pct"] == pytest.approx(0.10)
    assert resultado_30["desconto_holding_pct"] == pytest.approx(0.30)


def test_sotp_segmento_com_erro_nao_entra_na_soma_mas_e_reportado():
    config = _configuracao_sintetica()
    config.segmentos.append(Segmento(nome="Segmento Incompleto", metodo="ev_ebitda"))  # sem ebitda/multiplo
    resultado = calcular_sotp(config)
    # a soma continua batendo só com os 3 segmentos válidos
    assert resultado["ev_consolidado_bruto"] == pytest.approx(12900.0)
    assert resultado["segmentos_com_erro"] == ["Segmento Incompleto"]
    assert len(resultado["segmentos"]) == 4


def test_sotp_num_acoes_zero_retorna_preco_justo_none_sem_quebrar():
    config = _configuracao_sintetica()
    config.num_acoes = 0.0
    resultado = calcular_sotp(config)
    assert resultado["preco_justo_por_acao"] is None
    # o valor agregado continua calculável
    assert resultado["valor_equity_pos_desconto"] == pytest.approx(7920.0)


def test_sotp_todos_os_segmentos_com_erro_soma_zero_sem_quebrar():
    config = ConfiguracaoSotp(
        segmentos=[Segmento(nome="X", metodo="ev_ebitda")],
        divida_liquida_consolidada=100.0,
        num_acoes=10.0,
    )
    resultado = calcular_sotp(config)
    assert resultado["ev_consolidado_bruto"] == pytest.approx(0.0)
    assert resultado["segmentos_com_erro"] == ["X"]


# ─── carregar_configuracao_sotp() — JSON de configuração por ticker ─────────

def test_carrega_configuracao_de_arquivo_json(tmp_path, monkeypatch):
    arquivo = tmp_path / "sotp_config.json"
    arquivo.write_text(json.dumps({
        "TESTE4": {
            "segmentos": [
                {"nome": "Financeiro", "metodo": "ev_ebitda", "ebitda": 1000.0, "multiplo_ev_ebitda": 8.0},
            ],
            "divida_liquida_consolidada": 500.0,
            "num_acoes": 100.0,
            "desconto_holding_pct": 0.15,
        }
    }), encoding="utf-8")
    monkeypatch.setattr(sotp_module, "CONFIG_PATH", arquivo)

    config = carregar_configuracao_sotp("teste4")  # case-insensitive
    assert config is not None
    assert len(config.segmentos) == 1
    assert config.segmentos[0].nome == "Financeiro"
    assert config.divida_liquida_consolidada == pytest.approx(500.0)
    assert config.num_acoes == pytest.approx(100.0)
    assert config.desconto_holding_pct == pytest.approx(0.15)


def test_arquivo_ausente_retorna_none_nao_configuracao_vazia(tmp_path, monkeypatch):
    monkeypatch.setattr(sotp_module, "CONFIG_PATH", tmp_path / "nao_existe.json")
    assert carregar_configuracao_sotp("QUALQUER4") is None


def test_ticker_nao_mapeado_no_arquivo_retorna_none(tmp_path, monkeypatch):
    arquivo = tmp_path / "sotp_config.json"
    arquivo.write_text(json.dumps({"OUTRO4": {"segmentos": []}}), encoding="utf-8")
    monkeypatch.setattr(sotp_module, "CONFIG_PATH", arquivo)
    assert carregar_configuracao_sotp("TESTE4") is None
