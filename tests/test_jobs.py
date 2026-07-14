"""Testa a costura de job (core/jobs.py) — fila leve in-process."""

import threading
import time

from core.jobs import LocalJobQueue


def _wait(cond, tries=100):
    for _ in range(tries):
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_fila_executa_job_enfileirado():
    done = threading.Event()
    q = LocalJobQueue(workers=1)
    q.start()
    q.enqueue(lambda: done.set())
    assert _wait(done.is_set), "o job enfileirado deveria ter rodado"


def test_job_recebe_args():
    got = []
    q = LocalJobQueue(workers=1)
    q.start()
    q.enqueue(lambda a, b: got.append((a, b)), 1, b=2)
    assert _wait(lambda: got == [(1, 2)])


def test_excecao_num_job_nao_derruba_o_worker():
    ok = threading.Event()
    q = LocalJobQueue(workers=1)
    q.start()
    q.enqueue(lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # job que explode
    q.enqueue(lambda: ok.set())                                      # o worker tem que sobreviver
    assert _wait(ok.is_set), "o worker deveria sobreviver à exceção e rodar o próximo job"


def test_start_idempotente():
    q = LocalJobQueue(workers=2)
    q.start()
    q.start()  # segunda chamada não cria mais workers nem quebra
    assert len(q._threads) == 2
