"""Testes das funções puras de carga/ACWR (sem banco, determinísticas)."""

from analytics.training_load import TrainingLoad

activity_trimp = TrainingLoad.activity_trimp
acwr_status = TrainingLoad.acwr_status


# --- TRIMP ponderado por zona (Edwards) ---

def test_trimp_from_zones_edwards():
    # 60s em cada bucket; pesos [1,1,2,3,4,5,5] -> minutos(1) * pesos
    zone_seconds = [60, 60, 60, 60, 60, 60, 60]
    # 1*1 + 1*1 + 1*2 + 1*3 + 1*4 + 1*5 + 1*5 = 21
    assert activity_trimp(zone_seconds, avg_hr=150, duration_min=7) == 21.0


def test_trimp_fallback_uses_avg_hr_zone():
    # sem zonas: avg_hr 150 / hr_max 198 = 0.76 -> peso 3; 30min * 3 = 90
    assert activity_trimp(None, avg_hr=150, duration_min=30, hr_max=198) == 90.0


def test_trimp_zero_without_data():
    assert activity_trimp(None, avg_hr=None, duration_min=None) == 0.0


# --- ACWR + portão de confiança ---

def test_burn_in_is_aquecendo_regardless_of_acwr():
    assert acwr_status(4.0, days_of_history=5) == "aquecendo"


def test_safe_zone_after_burn_in():
    assert acwr_status(1.0, days_of_history=40) == "zona segura"


def test_risk_after_burn_in():
    assert acwr_status(1.8, days_of_history=40) == "risco de lesao"


def test_detrain_after_burn_in():
    assert acwr_status(0.6, days_of_history=40) == "destreino"
