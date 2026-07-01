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
from analytics.intensity import HrZoneAnalyzer
from analytics.run_analysis import CADENCE_PROTECTIVE_MIN


@dataclass
class Sample:
    """Uma leitura de telemetria no instante t (segundos desde o inicio)."""
    t: float
    speed_ms: Optional[float]
    heart_rate: Optional[int]
    cadence: Optional[int]


@dataclass
class Target:
    """Alvo da sessão. Vem dos DADOS REAIS do atleta (zonas) + a INTENÇÃO da sessão — nunca de
    chute. As fábricas abaixo montam alvos realistas por tipo de treino (leve/longo/ritmo).
    Como no HYROX, a intenção é um RÓTULO do treino, não adivinhação."""
    pace_low_s_km: float    # limite RÁPIDO da faixa-alvo (s/km)
    pace_high_s_km: float   # limite LENTO da faixa-alvo (s/km)
    hr_ceiling: int         # teto de FC
    cadence_base: int       # cadência de referência (limiar protetor)

    # pace "livre" (não cobra ritmo): banda larguíssima -> a regra de pace nunca dispara
    _PACE_FREE = (0.0, 1e9)

    @classmethod
    def easy_run(cls, activity_id: str) -> "Target":
        """Treino LEVE: dirigido por FC (fica na base aeróbica, topo da Z2); pace livre; cadência protetora."""
        z = HrZoneAnalyzer().analyze(activity_id)
        lo, hi = cls._PACE_FREE
        return cls(lo, hi, hr_ceiling=z.get("z2_high") or 150, cadence_base=CADENCE_PROTECTIVE_MIN)

    @classmethod
    def steady_run(cls, activity_id: str) -> "Target":
        """Treino LONGO/steady: fica até o fim da Z3 (não deixa virar treino forte); pace livre."""
        z = HrZoneAnalyzer().analyze(activity_id)
        lo, hi = cls._PACE_FREE
        return cls(lo, hi, hr_ceiling=z.get("hard_from") or 165, cadence_base=CADENCE_PROTECTIVE_MIN)

    @classmethod
    def goal_pace(cls, goal_pace_s_km: float, activity_id: str, tol: float = 0.06) -> "Target":
        """Sessão de RITMO: faixa em torno do pace-alvo (± tol); teto de FC de segurança (início da Z4)."""
        z = HrZoneAnalyzer().analyze(activity_id)
        return cls(pace_low_s_km=goal_pace_s_km * (1 - tol), pace_high_s_km=goal_pace_s_km * (1 + tol),
                   hr_ceiling=z.get("hard_from") or 175, cadence_base=CADENCE_PROTECTIVE_MIN)


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


class Hysteresis:
    """Evita 'piscar' no limiar: liga o estado-problema em `enter`, só desliga em `exit`
    (banda morta entre os dois). `below` p/ 'abaixo é ruim' (cadência); `above` p/ 'acima é ruim' (FC)."""

    def __init__(self, enter: float, exit_: float):
        self.enter, self.exit, self._on = enter, exit_, False

    def below(self, value: float) -> bool:
        self._on = (value < self.enter) if not self._on else (value <= self.exit)
        return self._on

    def above(self, value: float) -> bool:
        self._on = (value > self.enter) if not self._on else (value >= self.exit)
        return self._on


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

    def __init__(self):
        super().__init__()
        self._h: Optional[Hysteresis] = None

    def _check(self, window: Window, target: Target) -> Optional[str]:
        hr = window.avg("heart_rate")
        if hr is None:
            return None
        if self._h is None:   # entra acima do teto; so sai 3 bpm abaixo (banda morta)
            self._h = Hysteresis(enter=target.hr_ceiling, exit_=target.hr_ceiling - 3)
        return "FC acima do teto — alivie um pouco." if self._h.above(hr) else None


class CadenceCueRule(BaseCueRule):
    kind, priority = "cadence", 1

    def __init__(self):
        super().__init__()
        self._h: Optional[Hysteresis] = None

    def _check(self, window: Window, target: Target) -> Optional[str]:
        cad = window.avg("cadence")
        if cad is None:
            return None
        if self._h is None:   # entra abaixo de 95% da base; so sai acima de 98% (banda morta)
            self._h = Hysteresis(enter=target.cadence_base * 0.95, exit_=target.cadence_base * 0.98)
        return "Cadencia caiu — encurte e acelere a passada." if self._h.below(cad) else None


# --- Announcers (entrega) ---

class LogAnnouncer(BaseAnnouncer):
    """Coleta os cues numa lista (silencioso) — para testes e replay determinístico."""

    def __init__(self):
        self.cues: List[Cue] = []

    def announce(self, cue: Cue) -> None:
        self.cues.append(cue)


class MacSayAnnouncer(BaseAnnouncer):
    """Fala o cue pelo `say` do macOS (offline) — para OUVIR o replay/demo. Voz e ritmo
    configuraveis: troque por uma voz PT-BR 'Aprimorada/Premium' (qualidade Siri) baixada em
    Ajustes > Acessibilidade > Conteudo Falado para soar natural. No produto, e o TTS neural
    do celular (mesmo padrao de Runna/Garmin)."""

    def __init__(self, voice: str = "Sandy", rate_wpm: int = 150):  # voz natural + ritmo calmo
        self.voice = voice
        self.rate_wpm = rate_wpm

    def announce(self, cue: Cue) -> None:
        subprocess.run(["say", "-v", self.voice, "-r", str(self.rate_wpm), cue.message], check=False)


class CallbackAnnouncer(BaseAnnouncer):
    """COSTURA de entrega para um host externo (app mobile / integração): encaminha cada Cue
    a um callback. No produto, o app liga esse callback ao **TTS nativo do celular** (iOS/Android),
    que fala no fone — ou seja, o `PhoneTTSAnnouncer` do app É este callback apontando pro bridge
    de voz nativo. Mantém o motor agnóstico de COMO se fala (mesmo padrão Runna/Garmin)."""

    def __init__(self, on_cue):
        self.on_cue = on_cue   # ex: lambda cue: phone_tts.speak(cue.message)

    def announce(self, cue: Cue) -> None:
        self.on_cue(cue)


# --- Motor: COMPOE regras + alvo + announcer (= Coach compõe analyzers) ---
#
# COSTURA da FONTE de dados: o motor consome amostras por on_sample(Sample). Hoje quem alimenta
# é o ReplayDriver (lê o .FIT do banco, ~1 Hz). No app, um "LiveStreamDriver" leria os sensores
# ao vivo (GPS do celular + BLE da cinta/relogio) e chamaria o MESMO on_sample — o motor nao muda.

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
    con = get_connection()
    aid, name = con.execute(
        "SELECT activity_id, activity_name FROM dim_activities WHERE primary_type='RUN' "
        "ORDER BY start_time DESC LIMIT 1"
    ).fetchone()
    target = Target.steady_run(str(aid))   # alvo realista de treino longo (dirigido por FC)
    coach = RealtimeCoach([PaceCueRule(), HrCeilingCueRule(), CadenceCueRule()],
                          target, MacSayAnnouncer())
    print(f"=== Replay (com voz): {name} ===")
    for t, cue in ReplayDriver(coach).run(str(aid)):
        print(f"  {t:4d}s  [{cue.kind}] {cue.message}")
