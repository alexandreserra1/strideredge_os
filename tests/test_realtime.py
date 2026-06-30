"""Testes do motor de cues em tempo real — determinísticos, sem LLM, sem som."""

from analytics.realtime import (
    Sample, Window, Target, Cue, RealtimeCoach, ReplayDriver, Hysteresis,
    PaceCueRule, HrCeilingCueRule, CadenceCueRule, LogAnnouncer, CallbackAnnouncer,
)


def test_callback_announcer_encaminha_ao_host():
    # costura de entrega: o host (app) recebe o cue p/ falar no TTS nativo
    saidas = []
    CallbackAnnouncer(saidas.append).announce(Cue("pace", "acelere", 2))
    assert saidas and saidas[0].kind == "pace" and saidas[0].message == "acelere"


def test_hysteresis_nao_pisca_no_limiar():
    h = Hysteresis(enter=161.5, exit_=166.6)   # cadencia: abaixo e ruim
    assert h.below(160) is True      # entrou no problema (160 < 161.5)
    assert h.below(163) is True      # banda morta vindo de baixo -> CONTINUA (nao pisca)
    assert h.below(168) is False     # so sai acima de 166.6
    assert h.below(163) is False     # banda morta vindo de cima -> continua ok


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


# --- Falar como gente: sustain + nao-tagarelar + re-lembrete (template-method) ---

def test_sustain_e_nao_tagarela():
    r, w, t = PaceCueRule(), _win(speed=2.5), _target()   # problema persistente (lento)
    assert r.evaluate(w, t, 0.0) is None        # acabou de comecar -> ainda nao sustentou
    assert r.evaluate(w, t, 5.0) is None         # 5s < sustain (8s)
    assert r.evaluate(w, t, 10.0) is not None    # sustentou -> fala UMA vez
    assert r.evaluate(w, t, 15.0) is None         # mesmo problema -> quieto (nao tagarela)
    assert r.evaluate(w, t, 140.0) is not None    # re-lembrete so apos o cooldown (120s)


def test_fala_de_novo_apos_voltar_ao_normal():
    r, t = PaceCueRule(), _target()
    slow, ok = _win(speed=2.5), _win(speed=3.0)
    r.evaluate(slow, t, 0.0)                          # comeca a sustentar
    assert r.evaluate(slow, t, 10.0) is not None      # falou (lento, sustentado)
    assert r.evaluate(ok, t, 12.0) is None             # voltou ao normal -> reseta
    r.evaluate(slow, t, 14.0)                          # problema recomecou
    assert r.evaluate(slow, t, 24.0) is not None       # sustentou de novo -> fala de novo


# --- Motor: prioridade + announcer ---

def test_prioridade_fc_vence_pace():
    coach = RealtimeCoach([PaceCueRule(), HrCeilingCueRule()], _target(), LogAnnouncer())
    # sustenta pace lento E FC alta ate passar o sustain (8s)
    fired = [coach.on_sample(Sample(float(tt), 2.5, 185, 170)) for tt in range(0, 11)]
    fired = [c for c in fired if c]
    assert fired and fired[0].kind == "hr"              # seguranca tem prioridade
    assert any(c.kind == "hr" for c in coach.announcer.cues)


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
