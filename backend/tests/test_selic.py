from unittest.mock import patch
from dados.selic import buscar_selic_atual


def test_selic_fallback_quando_api_falha():
    """Deve retornar valor padrão quando API falhar."""
    # Limpa cache antes do teste
    from dados import selic as selic_module
    selic_module._cache_selic["valor"] = None
    selic_module._cache_selic["timestamp"] = 0

    with patch("dados.selic.httpx.get", side_effect=Exception("timeout")):
        selic = buscar_selic_atual()
    assert selic == 0.145  # fallback padrão


def test_selic_retorna_decimal():
    """Selic deve ser retornada em decimal."""
    from dados import selic as selic_module
    selic_module._cache_selic["valor"] = None
    selic_module._cache_selic["timestamp"] = 0

    with patch("dados.selic.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = [{"valor": "14.50"}]
        mock_get.return_value.raise_for_status = lambda: None
        selic = buscar_selic_atual()
    assert selic == 0.145

def test_selic_entre_limites_razoaveis():
    """Selic deve estar entre 2% e 30%."""
    with patch("dados.selic.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = [{"valor": "14.75"}]
        mock_get.return_value.raise_for_status = lambda: None
        selic = buscar_selic_atual()
    assert 0.02 <= selic <= 0.30