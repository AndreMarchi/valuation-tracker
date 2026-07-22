"""
test_concessao_wiring.py
Teste de regressão pro bug de wiring: `enriquecer_com_concessao()` (em
main.py) monta a análise de DCF com cliff de concessão e escreve em
`resultado["concessao"]`/`resultado["metodos"]["dcf_concessao"]`, mas
estava DEFINIDA e nunca CHAMADA em lugar nenhum — `dados_finais` era
retornado por `valuation()` sem nunca passar por essa função, então a
chave "concessao" nunca existia na resposta real de `/api/valuation/{ticker}`
e o card `ConcessaoSection.tsx` do frontend nunca aparecia, mesmo pra
tickers com concessão mapeada (GEPA4/GEPA3).

Diferente de um teste de execução (que precisaria de rede pra buscar_dados),
este analisa o CÓDIGO-FONTE via `ast` — não regex — do corpo da função
`valuation()` em main.py, e falha se `enriquecer_com_concessao(...)` não
for chamada em algum lugar dentro dela. Pega essa classe de bug ("função
existe mas nunca é invocada") se acontecer de novo no futuro, sem depender
de dados externos.
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
MAIN_PY = BACKEND_DIR / "main.py"


def _encontrar_funcao(arvore: ast.AST, nome: str):
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return no
    return None


def _chama_funcao(no_funcao: ast.AST, nome_chamada: str) -> bool:
    for sub_no in ast.walk(no_funcao):
        if isinstance(sub_no, ast.Call) and isinstance(sub_no.func, ast.Name) and sub_no.func.id == nome_chamada:
            return True
    return False


class TestEnriquecerComConcessaoEhChamadaDentroDeValuation:

    def test_main_py_tem_as_duas_funcoes(self):
        # Canário: se qualquer uma das duas funções for renomeada/removida,
        # o teste abaixo passaria vazio e silencioso.
        arvore = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
        assert _encontrar_funcao(arvore, "valuation") is not None, (
            "Função valuation() não encontrada em main.py — atualize este teste."
        )
        assert _encontrar_funcao(arvore, "enriquecer_com_concessao") is not None, (
            "Função enriquecer_com_concessao() não encontrada em main.py — atualize este teste."
        )

    def test_valuation_chama_enriquecer_com_concessao(self):
        arvore = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
        no_valuation = _encontrar_funcao(arvore, "valuation")
        assert no_valuation is not None

        assert _chama_funcao(no_valuation, "enriquecer_com_concessao"), (
            "enriquecer_com_concessao() não é chamada dentro de valuation() em main.py — "
            "sem essa chamada, resultado['concessao'] nunca existe na resposta real de "
            "/api/valuation/{ticker} e o card ConcessaoSection.tsx do frontend nunca aparece, "
            "mesmo pra tickers com concessão mapeada (GEPA4/GEPA3)."
        )
