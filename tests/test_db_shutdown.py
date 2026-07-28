"""Shutdown BOUNDED — o encerramento nunca pode pendurar (SIGTERM travado).

Cobre:
  1) close_connection() com CHECKPOINT/close LENTO -> retorna dentro do timeout (nao pendura).
  2) close_connection() no caminho feliz -> faz o checkpoint e o WAL nao sobra (anti-corrupcao).
  3) JobQueue.stop() -> para os workers e nao trava (mesmo com job preso).
"""

import threading
import time

import core.database as db
from core.jobs import LocalJobQueue


def _restore_real_conn():
    """Reabre a conexao ao banco de teste (a fixture de sessao segue usando-a depois)."""
    db._connection = None
    db.get_connection()


def test_close_connection_bounded_quando_checkpoint_pendura():
    """Se um worker segura a conexao, o CHECKPOINT/close pode bloquear pra sempre. close_connection
    roda isso numa thread e da join(timeout): tem que retornar bem antes do checkpoint 'terminar'."""
    entered = threading.Event()

    class HangingConn:
        def execute(self, sql):
            entered.set()
            time.sleep(30)  # simula o CHECKPOINT preso por um cursor ocupado

        def close(self):
            time.sleep(30)

    saved = db._connection
    db._connection = HangingConn()
    try:
        t0 = time.monotonic()
        db.close_connection(timeout=0.3)
        elapsed = time.monotonic() - t0
        assert entered.is_set(), "o checkpoint deveria ter comecado (rodou na thread)"
        assert elapsed < 3.0, f"close_connection pendurou: {elapsed:.1f}s"
        assert db._connection is None, "a conexao deve ser abandonada mesmo no timeout"
    finally:
        db._connection = saved
        _restore_real_conn()


def test_close_connection_caminho_feliz_faz_checkpoint_e_persiste():
    """Sem ninguem segurando a conexao: checkpoint rapido, fecha ok e os dados persistem no .db
    (a razao anti-corrupcao de existir — o WAL foi drenado, o replay no boot nao explode)."""
    con = db.get_connection()
    con.execute("CREATE TABLE IF NOT EXISTS _shutdown_probe(x INTEGER)")
    con.execute("INSERT INTO _shutdown_probe VALUES (1)")

    t0 = time.monotonic()
    db.close_connection(timeout=5.0)
    elapsed = time.monotonic() - t0

    assert elapsed < 5.0, "caminho feliz nao pode chegar perto do timeout"
    assert db._connection is None

    # reabre e confirma que os dados persistiram (o checkpoint realmente escreveu no .db)
    con2 = db.get_connection()
    assert con2.execute("SELECT count(*) FROM _shutdown_probe").fetchone()[0] == 1
    con2.execute("DROP TABLE _shutdown_probe")


def _wait(cond, tries=200):
    for _ in range(tries):
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_job_queue_stop_para_os_workers():
    q = LocalJobQueue(workers=2)
    q.start()
    threads = list(q._threads)
    q.stop(timeout=3.0)
    assert _wait(lambda: all(not t.is_alive() for t in threads)), "os workers deveriam ter parado"
    assert q._started is False


def test_job_queue_stop_bounded_com_job_preso():
    """Um worker preso num job longo nao pode pendurar o stop() alem do timeout."""
    release = threading.Event()
    q = LocalJobQueue(workers=1)
    q.start()
    q.enqueue(lambda: release.wait(30))  # job que so solta depois do timeout

    t0 = time.monotonic()
    q.stop(timeout=0.3)
    elapsed = time.monotonic() - t0
    release.set()  # libera o job pra thread daemon encerrar
    assert elapsed < 2.0, f"stop() pendurou: {elapsed:.1f}s"


def test_job_queue_stop_idempotente():
    q = LocalJobQueue(workers=1)
    q.start()
    q.stop()
    q.stop()  # segunda chamada nao quebra
