"""Janela deslizante do rate limiter — sem relógio real nem estado global."""

from core.rate_limit import SlidingWindowLimiter


def test_limite_recusa_e_libera_apos_janela():
    now = [100.0]
    limiter = SlidingWindowLimiter(clock=lambda: now[0])
    assert limiter.allow("login:ip", limit=2, window_s=10)
    assert limiter.allow("login:ip", limit=2, window_s=10)
    assert not limiter.allow("login:ip", limit=2, window_s=10)
    now[0] += 10
    assert limiter.allow("login:ip", limit=2, window_s=10)


def test_chaves_nao_compartilham_cota():
    limiter = SlidingWindowLimiter(clock=lambda: 1.0)
    assert limiter.allow("login:a", limit=1, window_s=10)
    assert limiter.allow("login:b", limit=1, window_s=10)
