"""Config por ambiente."""

import importlib
import pytest

import core.config


def _reload(monkeypatch, env=None):
    if env is None:
        monkeypatch.delenv("STRIDE_ENV", raising=False)
    else:
        monkeypatch.setenv("STRIDE_ENV", env)
    return importlib.reload(core.config)


@pytest.fixture(autouse=True)
def _restore():
    yield
    importlib.reload(core.config)   # re-le o env ja revertido pelo monkeypatch


def test_producao_marca_is_prod(monkeypatch):
    c = _reload(monkeypatch, env="production")
    assert c.IS_PROD is True


def test_ambiente_padrao_e_development(monkeypatch):
    c = _reload(monkeypatch)   # sem STRIDE_ENV
    assert c.IS_PROD is False
