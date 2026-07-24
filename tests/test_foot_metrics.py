"""Gates técnicos para observabilidade experimental dos keypoints de pé."""

from analytics.foot_metrics import assess_foot_keypoint_quality


def _frame(index, *, confident=True, jitter=False):
    shift = float(index)
    confidence = 0.95 if confident else 0.10
    # Pé estável relativo ao tornozelo, apesar da translação do corredor pelo frame.
    left_hallux = (shift + 20.0, 100.0, confidence)
    if jitter:
        left_hallux = (shift + (120.0 if index % 2 else -80.0), 100.0, confidence)
    return {
        "tornozelo_e": (shift, 100.0, confidence),
        "hallux_e": left_hallux,
        "dedinho_e": (shift + 15.0, 108.0, confidence),
        "calcanhar_e": (shift - 10.0, 100.0, confidence),
        "tornozelo_d": (shift, 200.0, confidence),
        "hallux_d": (shift + 20.0, 200.0, confidence),
        "dedinho_d": (shift + 15.0, 208.0, confidence),
        "calcanhar_d": (shift - 10.0, 200.0, confidence),
    }


def test_serie_estavel_e_coberta_e_observavel_sem_fazer_interpretacao_clinica():
    report = assess_foot_keypoint_quality([_frame(index) for index in range(20)])

    assert report["experimental"] is True
    assert report["reliable"] is True and report["reason"] == "ok"
    assert report["quality"]["left_coverage"] == 1.0
    assert report["quality"]["left_jitter_ratio"] == 0.0
    assert "pronation" not in report and "dorsiflexion" not in report


def test_recusa_cobertura_temporal_insuficiente():
    frames = [_frame(index, confident=index < 10) for index in range(20)]

    report = assess_foot_keypoint_quality(frames)

    assert report["reliable"] is False
    assert report["reason"] == "insufficient_foot_coverage"
    assert report["quality"]["left_coverage"] == 0.5


def test_recusa_salto_temporal_de_keypoint_mesmo_com_confianca_alta():
    report = assess_foot_keypoint_quality([_frame(index, jitter=True) for index in range(20)])

    assert report["reliable"] is False
    assert report["reason"] == "excessive_keypoint_jitter"
    assert report["quality"]["left_jitter_ratio"] > report["quality"]["maximum_jitter_ratio"]


def test_recusa_serie_malformada_sem_levantar_conclusao():
    report = assess_foot_keypoint_quality([{"hallux_e": (1.0, 2.0, 0.9)}])

    assert report["experimental"] is True
    assert report["reliable"] is False
    assert report["reason"] == "invalid_keypoint_series"
