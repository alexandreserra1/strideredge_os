"""Testes do motor de cues em tempo real — determinísticos, sem LLM, sem som."""

from analytics.realtime import (
    Sample, Window, Target, Cue, RealtimeCoach, ReplayDriver,
    PaceCueRule, HrCeilingCueRule, CadenceCueRule, LogAnnouncer,
)


def _target():
    # faixa-alvo 300-360 s/km (5:00-6:00 min/km); teto FC 170; cadencia base 170
    return Target(pace_low_s_km=300, pace_high_s_km=360, hr_ceiling=170, cadence_base=170)


def _win(speed=3.0, hr=150, cad=170):
    w = Window()
    w.add(Sample(0.0, speed, hr, cad))
    return w


# --- Regras isoladas ---

def test_pace_rule_lento_manda_acelerar():
    msg = PaceCueRule()._check(_win(speed=2.5), _target())   # 2.5 m/s = 400 s/km (lento)
    assert msg and "celere" in msg.lower()


def test_pace_rule_rapido_manda_segurar():
    msg = PaceCueRule()._check(_win(speed=4.0), _target())   # 4.0 m/s = 250 s/km (rapido)
    assert msg and "segura" in msg.lower()


def test_pace_rule_na_faixa_fica_quieto():
    assert PaceCueRule()._check(_win(speed=3.0), _target()) is None  # 333 s/km, dentro


def test_hr_ceiling_dispara_acima_do_teto():
    assert HrCeilingCueRule()._check(_win(hr=185), _target()) is not None
    assert HrCeilingCueRule()._check(_win(hr=150), _target()) is None


def test_cadence_rule_dispara_quando_cai():
    assert CadenceCueRule()._check(_win(cad=150), _target()) is not None   # <170*0.95
    assert CadenceCueRule()._check(_win(cad=170), _target()) is None


# --- Cooldown (template-method na BaseCueRule) ---

def test_cooldown_silencia_repeticao():
    r, w, t = PaceCueRule(), _win(speed=2.5), _target()
    assert r.evaluate(w, t, 0.0) is not None     # dispara
    assert r.evaluate(w, t, 5.0) is None         # dentro do cooldown (20s) -> quieto
    assert r.evaluate(w, t, 30.0) is not None     # passou o cooldown -> dispara de novo


# --- Motor: prioridade + announcer ---

def test_prioridade_fc_vence_pace():
    coach = RealtimeCoach([PaceCueRule(), HrCeilingCueRule()], _target(), LogAnnouncer())
    cue = coach.on_sample(Sample(0.0, 2.5, 185, 170))   # pace lento E FC alta no mesmo tick
    assert cue.kind == "hr"                              # seguranca tem prioridade
    assert coach.announcer.cues == [cue]                # foi anunciado


# --- Replay sobre um .FIT real (conftest sintetico) ---

def test_replay_roda_e_produz_cues():
    from core.database import get_connection
    aid = str(get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE activity_name = 'Corrida Floripa'"
    ).fetchone()[0])
    target = Target(pace_low_s_km=200, pace_high_s_km=250, hr_ceiling=160, cadence_base=170)
    coach = RealtimeCoach([PaceCueRule(), HrCeilingCueRule(), CadenceCueRule()], target, LogAnnouncer())
    cues = ReplayDriver(coach).run(aid)
    assert isinstance(cues, list)
    assert all(isinstance(c, Cue) for _, c in cues)
