"""analytics/realtime.py — motor de COACHING EM TEMPO REAL (momento 2 do coach).

Determinístico, sem LLM (o LLM é lento/aleatório demais p/ o ao-vivo). A cada amostra de
telemetria, regras (Strategy) olham a janela recente vs. o alvo e talvez disparam um aviso
curto, falado por um announcer (voz). Latência microssegundos — o pesado (suavizar sinal) já
é o kernel Rust quando formos ao stream; aqui a média móvel da janela já suaviza.

Testável HOJE por REPLAY: alimenta um .FIT do banco tick-a-tick, como se fosse ao vivo
(mesmo padrão de "testar em traço gravado" do plan.md §10.1). O motor é o mesmo do dev ao
app: só troca a FONTE (replay -> stream BLE) e o ANNOUNCER (log -> say -> TTS do celular).
"""

import subprocess
from collections import deque
from dataclasses import dataclass
from typing import List, Optional

from core.database import get_connection
from core.framework.interfaces import BaseCueRule, BaseAnnouncer


@dataclass
class Sample:
    """Uma leitura de telemetria no instante t (segundos desde o inicio)."""
    t: float
    speed_ms: Optional[float]
    heart_rate: Optional[int]
    cadence: Optional[int]


@dataclass
class Target:
    """Alvo da sessão (vem do que já temos: pace do preditor + zonas reais do atleta)."""
    pace_low_s_km: float    # limite RÁPIDO da faixa-alvo (s/km)
    pace_high_s_km: float   # limite LENTO da faixa-alvo (s/km)
    hr_ceiling: int         # teto de FC (ex: topo da Z2 p/ treino leve)
    cadence_base: int       # cadência de referência do atleta


@dataclass
class Cue:
    """O aviso a falar. Value object."""
    kind: str
    message: str
    priority: int


class Window:
    """Janela móvel das últimas `seconds` de amostras — suaviza ruído (média do trecho)."""

    def __init__(self, seconds: float = 15.0):
        self.seconds = seconds
        self._buf: deque = deque()

    def add(self, s: Sample) -> None:
        self._buf.append(s)
        while self._buf and s.t - self._buf[0].t > self.seconds:
            self._buf.popleft()

    def avg(self, field: str) -> Optional[float]:
        vals = [getattr(x, field) for x in self._buf if getattr(x, field) is not None]
        return sum(vals) / len(vals) if vals else None


# --- Regras (Strategy): cada uma herda BaseCueRule e implementa só a condição ---

class PaceCueRule(BaseCueRule):
    kind, priority = "pace", 2

    def _check(self, window: Window, target: Target) -> Optional[str]:
        sp = window.avg("speed_ms")
        if not sp:
            return None
        pace = 1000.0 / sp  # s/km
        if pace > target.pace_high_s_km:
            return "Acelere um pouco — voce esta abaixo do ritmo-alvo."
        if pace < target.pace_low_s_km:
            return "Segura o ritmo — esta rapido demais para o alvo."
        return None


class HrCeilingCueRule(BaseCueRule):
    kind, priority = "hr", 3   # seguranca = prioridade alta

    def _check(self, window: Window, target: Target) -> Optional[str]:
        hr = window.avg("heart_rate")
        if hr and hr > target.hr_ceiling:
            return "FC acima do teto — alivie um pouco."
        return None


class CadenceCueRule(BaseCueRule):
    kind, priority = "cadence", 1

    def _check(self, window: Window, target: Target) -> Optional[str]:
        cad = window.avg("cadence")
        if cad and cad < target.cadence_base * 0.95:
            return "Cadencia caiu — encurte e acelere a passada."
        return None


# --- Announcers (entrega) ---

class LogAnnouncer(BaseAnnouncer):
    """Coleta os cues numa lista (silencioso) — para testes e replay determinístico."""

    def __init__(self):
        self.cues: List[Cue] = []

    def announce(self, cue: Cue) -> None:
        self.cues.append(cue)


class MacSayAnnouncer(BaseAnnouncer):
    """Fala o cue pelo `say` do macOS (offline, instantâneo) — para OUVIR o replay/demo."""

    def __init__(self, voice: str = "Luciana"):  # voz PT-BR no macOS
        self.voice = voice

    def announce(self, cue: Cue) -> None:
        subprocess.run(["say", "-v", self.voice, cue.message], check=False)


# --- Motor: COMPOE regras + alvo + announcer (= Coach compõe analyzers) ---

class RealtimeCoach:
    """Processa a telemetria tick-a-tick e emite o cue de maior prioridade (com cooldown)."""

    def __init__(self, rules: List[BaseCueRule], target: Target, announcer: BaseAnnouncer = None):
        self.rules = rules
        self.target = target
        self.announcer = announcer or LogAnnouncer()
        self.window = Window()

    def on_sample(self, s: Sample) -> Optional[Cue]:
        self.window.add(s)
        fired = []
        for rule in self.rules:
            msg = rule.evaluate(self.window, self.target, s.t)
            if msg:
                fired.append(Cue(rule.kind, msg, rule.priority))
        if not fired:
            return None
        cue = max(fired, key=lambda c: c.priority)  # seguranca (FC) > pace > cadencia
        self.announcer.announce(cue)
        return cue


class ReplayDriver:
    """Alimenta a telemetria de um .FIT (do banco) no motor, como se fosse ao vivo (~1 Hz)."""

    def __init__(self, coach: RealtimeCoach):
        self.coach = coach

    def run(self, activity_id: str) -> List[Cue]:
        rows = get_connection().execute(
            """SELECT speed_ms, heart_rate, cadence FROM fact_telemetry
               WHERE activity_id = ? AND speed_ms IS NOT NULL ORDER BY timestamp""",
            [activity_id],
        ).fetchall()
        cues = []
        for t, (sp, hr, cad) in enumerate(rows):   # t = segundos (telemetria ~1 Hz)
            cue = self.coach.on_sample(Sample(float(t), sp, hr, cad))
            if cue:
                cues.append((t, cue))
        return cues


if __name__ == "__main__":
    # Demo: replay de uma corrida real, FALANDO os cues (say). Alvo leve (Z2).
    from analytics.intensity import HrZoneAnalyzer
    con = get_connection()
    aid, name = con.execute(
        "SELECT activity_id, activity_name FROM dim_activities WHERE primary_type='RUN' "
        "ORDER BY start_time DESC LIMIT 1"
    ).fetchone()
    z = HrZoneAnalyzer().analyze(str(aid))
    target = Target(pace_low_s_km=270, pace_high_s_km=360,
                    hr_ceiling=z.get("z2_high") or 150, cadence_base=170)
    coach = RealtimeCoach([PaceCueRule(), HrCeilingCueRule(), CadenceCueRule()],
                          target, MacSayAnnouncer())
    print(f"=== Replay (com voz): {name} ===")
    for t, cue in ReplayDriver(coach).run(str(aid)):
        print(f"  {t:4d}s  [{cue.kind}] {cue.message}")
