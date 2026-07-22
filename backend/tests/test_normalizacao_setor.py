"""
test_normalizacao_setor.py
Teste de regressão pro mismatch sistêmico de string de setor — confirmado
rodando buscar_dados() de verdade contra 11 tickers de setores variados
(BEEF3/JBSS3/BRFS3, ITUB4, MGLU3, TAEE3, VALE3, PETR4, WEGE3, RENT3,
CSNA3): a string crua do provedor ("Alimentos Processados", "Comércio")
não batia por igualdade exata com as chaves hardcoded em BETA_POR_SETOR,
PSR_MEDIO_SETOR e SETORES_CICLICOS — só FATOR_CONVERSAO_NOPAT já tratava
"Alimentos"/"Alimentos Processados" como sinônimos. Consequência real: o
cap de crescimento de setor cíclico (8%) nunca disparava pra BEEF3/JBSS3/
BRFS3, inflando o DCF (ver CONTEXT.md).

Este teste NÃO depende de rede (buscar_dados ao vivo) — cobre
especificamente os mapeamentos confirmados empiricamente em
dados/normalizacao_setor.py, e confirma que os 4 dicionários downstream
(BETA_POR_SETOR, PSR_MEDIO_SETOR, SETORES_CICLICOS de main.py e de
scanner/trabalhador.py, FATOR_CONVERSAO_NOPAT) passam a bater depois da
normalização, pros tickers/setores confirmados.
"""

import ast
from pathlib import Path

from dados.normalizacao_setor import normalizar_setor
from valuation.capm import BETA_POR_SETOR
from valuation.crescimento import PSR_MEDIO_SETOR

BACKEND_DIR = Path(__file__).parent.parent

# Réplica do fator_conversao_nopat (definido localmente dentro de
# calcular_fcl_via_nopat, não é importável no nível do módulo) — mesma
# lista de chaves de valuation/nopat.py, mantida em sincronia manualmente
# (se o dicionário real mudar, atualize aqui também).
FATOR_CONVERSAO_NOPAT_CHAVES = {
    "Transporte Aéreo", "Transporte", "Petróleo, Gás e Biocombustíveis",
    "Alimentos", "Alimentos Processados", "Siderurgia e Metalurgia",
    "Mineração", "Construção Civil", "Energia Elétrica", "Varejo",
    "Tecnologia", "Intermediários Financeiros",
}


class TestNormalizarSetor:

    def test_alimentos_processados_normaliza_para_alimentos(self):
        # BEEF3, JBSS3, BRFS3 — string real confirmada via buscar_dados()
        assert normalizar_setor("Alimentos Processados") == "Alimentos"

    def test_comercio_normaliza_para_varejo(self):
        # MGLU3 — string real confirmada via buscar_dados()
        assert normalizar_setor("Comércio") == "Varejo"
        assert normalizar_setor("comercio") == "Varejo"  # sem acento

    def test_setores_ja_canonicos_passam_inalterados(self):
        # Confirmados batendo direto nos dicionários — não devem ser
        # remapeados pra outra coisa.
        for setor in (
            "Mineração", "Siderurgia e Metalurgia", "Energia Elétrica",
            "Petróleo, Gás e Biocombustíveis", "Intermediários Financeiros",
        ):
            assert normalizar_setor(setor) == setor

    def test_setor_sem_mapeamento_conhecido_passa_inalterado(self):
        # WEGE3/RENT3 — sem evidência empírica de qual seria o canônico,
        # não deve inventar um mapeamento.
        assert normalizar_setor("Máquinas e Equipamentos") == "Máquinas e Equipamentos"
        assert normalizar_setor("Diversos") == "Diversos"

    def test_vazio_ou_none_nao_quebra(self):
        assert normalizar_setor("") == ""
        assert normalizar_setor(None) is None

    def test_case_e_espacos_sao_tolerados(self):
        assert normalizar_setor("  ALIMENTOS PROCESSADOS  ") == "Alimentos"

    def test_gas_normaliza_para_energia_eletrica(self):
        # CEGR3 (CEG), CGAS3 (Comgás), PASS3 (Compass) — distribuidoras
        # reguladas de gás canalizado, achado real da auditoria setorial
        # (scripts/auditoria_setorial.py). Diferente de Alimentos/Comércio
        # acima (variante de string do MESMO conceito), aqui é uma
        # aproximação de PERFIL DE RISCO — concessão regulada de capex
        # intensivo, mais parecido com Energia Elétrica do que com
        # Petróleo, Gás e Biocombustíveis (E&P de commodity). Ver
        # dados/normalizacao_setor.py e CONTEXT.md.
        assert normalizar_setor("Gás") == "Energia Elétrica"
        assert normalizar_setor("gas") == "Energia Elétrica"  # sem acento


class TestSetoresConfirmadosBatemNosDicionariosAposNormalizacao:
    """Confirma que os setores normalizados batem de verdade nos 4 pontos
    downstream que causaram o bug real (SETORES_CICLICOS de main.py e de
    scanner/trabalhador.py, BETA_POR_SETOR, PSR_MEDIO_SETOR,
    FATOR_CONVERSAO_NOPAT)."""

    def _setores_ciclicos_de(self, caminho: Path) -> set:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SETORES_CICLICOS" for t in no.targets
            ):
                return ast.literal_eval(no.value)
        raise AssertionError(f"SETORES_CICLICOS não encontrado em {caminho}")

    def test_alimentos_bate_em_todos_os_4_pontos(self):
        setor = normalizar_setor("Alimentos Processados")
        assert setor in self._setores_ciclicos_de(BACKEND_DIR / "main.py")
        assert setor in self._setores_ciclicos_de(BACKEND_DIR / "scanner" / "trabalhador.py")
        assert setor in BETA_POR_SETOR
        assert setor in PSR_MEDIO_SETOR
        assert setor in FATOR_CONVERSAO_NOPAT_CHAVES

    def test_varejo_bate_em_beta_psr_e_nopat(self):
        setor = normalizar_setor("Comércio")
        assert setor in BETA_POR_SETOR
        assert setor in PSR_MEDIO_SETOR
        assert setor in FATOR_CONVERSAO_NOPAT_CHAVES
        # Varejo nunca foi tratado como cíclico, nos dois SETORES_CICLICOS
        # (não é regressão — comportamento sempre foi esse)
        assert setor not in self._setores_ciclicos_de(BACKEND_DIR / "main.py")

    def test_siderurgia_e_metalurgia_sem_typo_bate_em_ciclicos(self):
        # Regressão específica do typo "Siderurgia e Siderurgia e
        # Metalurgia" em SETORES_CICLICOS, que nunca batia com a string
        # real "Siderurgia e Metalurgia" (confirmado com CSNA3) mesmo essa
        # string batendo em BETA_POR_SETOR e FATOR_CONVERSAO_NOPAT.
        setor = "Siderurgia e Metalurgia"
        assert setor in self._setores_ciclicos_de(BACKEND_DIR / "main.py")
        assert setor in self._setores_ciclicos_de(BACKEND_DIR / "scanner" / "trabalhador.py")
        assert setor in BETA_POR_SETOR
        assert setor in FATOR_CONVERSAO_NOPAT_CHAVES

    def test_nenhum_setores_ciclicos_tem_o_typo_antigo(self):
        typo = "Siderurgia e Siderurgia e Metalurgia"
        assert typo not in self._setores_ciclicos_de(BACKEND_DIR / "main.py")
        assert typo not in self._setores_ciclicos_de(BACKEND_DIR / "scanner" / "trabalhador.py")

    def test_gas_bate_em_beta_nopat_e_nao_e_ciclico(self):
        from valuation.setor import CONFIGURACAO_SETORES

        setor = normalizar_setor("Gás")
        assert setor == "Energia Elétrica"
        assert setor in BETA_POR_SETOR
        assert setor in FATOR_CONVERSAO_NOPAT_CHAVES
        assert setor in CONFIGURACAO_SETORES
        # Energia Elétrica nunca foi tratada como cíclica — gás canalizado
        # regulado também não deveria ser (não é regressão, comportamento
        # esperado)
        assert setor not in self._setores_ciclicos_de(BACKEND_DIR / "main.py")
        assert setor not in self._setores_ciclicos_de(BACKEND_DIR / "scanner" / "trabalhador.py")
