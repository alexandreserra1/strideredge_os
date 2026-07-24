"""Testes herméticos do trilho Halpe26: contrato de dados, não inferência pesada."""

import importlib.util
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _tool(name):
    path = _ROOT / "tools" / "halpe26" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"halpe26_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _instance(score=0.9):
    return {"keypoints": [[float(i), float(i + 1)] for i in range(26)], "scores": [score] * 26}


def test_validate_halpe26_rejeita_formato_ou_quantidade_errada():
    validate = _tool("validate")
    assert validate.validate_instances({"instances": [{"keypoints": [], "scores": []}]})["valid"] is False


def test_validate_halpe26_exige_seis_pontos_dos_pes_para_gate_estrito():
    validate = _tool("validate")
    report = validate.validate_instances({"instances": [_instance()]})
    assert report["valid"] is True
    assert report["instances_with_all_foot_points"] == 1
    assert report["keypoint_order"][20:26] == ["hallux_e", "hallux_d", "dedinho_e", "dedinho_d", "calcanhar_e", "calcanhar_d"]


def test_benchmark_so_aprova_sem_regressao_de_confiabilidade_e_com_pontos_dos_pes():
    benchmark = _tool("benchmark")
    baseline = {"runs": [{"video": "lateral", "frames": 300, "wall_seconds": 10, "reliable": True,
                            "sample_stride": 1, "measurement_stage": "decode+pose_inference"}]}
    candidate = {"runs": [{"video": "lateral", "frames": 300, "wall_seconds": 12, "reliable": True,
                             "foot_points_visible": True, "sample_stride": 1,
                             "measurement_stage": "decode+pose_inference"}]}
    report = benchmark.compare(baseline, candidate)
    assert report["eligible_for_rust_adapter"] is True


def test_benchmark_recusa_medicoes_com_amostragem_ou_estagios_diferentes():
    benchmark = _tool("benchmark")
    baseline = {"runs": [{"video": "lateral", "frames": 300, "wall_seconds": 10,
                           "reliable": True, "sample_stride": 1,
                           "measurement_stage": "decode+pose_inference"}]}
    candidate = {"runs": [{"video": "lateral", "frames": 50, "wall_seconds": 2,
                            "reliable": True, "foot_points_visible": True, "sample_stride": 6,
                            "measurement_stage": "decode+pose_inference"}]}
    assert benchmark.compare(baseline, candidate)["eligible_for_rust_adapter"] is False


def test_benchmark_recusa_contagem_de_frames_diferente_no_mesmo_video():
    benchmark = _tool("benchmark")
    baseline = {"runs": [{"video": "lateral", "frames": 300, "wall_seconds": 10,
                           "reliable": True, "sample_stride": 1,
                           "measurement_stage": "decode+pose_inference"}]}
    candidate = {"runs": [{"video": "lateral", "frames": 299, "wall_seconds": 10,
                            "reliable": True, "foot_points_visible": True, "sample_stride": 1,
                            "measurement_stage": "decode+pose_inference"}]}
    assert benchmark.compare(baseline, candidate)["same_frames"] is False


def test_benchmark_pareia_varios_videos_e_calcula_throughput_agregado_sem_vencedor_clinico():
    benchmark = _tool("benchmark")
    baseline = {"runs": [
        {"video": "laisa.mp4", "frames": 100, "wall_seconds": 5, "reliable": True,
         "sample_stride": 1, "measurement_stage": "decode+pose_inference", "detection_rate_pct": 98},
        {"video": "video23.mp4", "frames": 100, "wall_seconds": 10, "reliable": True,
         "sample_stride": 1, "measurement_stage": "decode+pose_inference", "detection_rate_pct": 97},
    ]}
    candidate = {"runs": [
        {"video": "video23.mp4", "frames": 100, "wall_seconds": 12, "reliable": True,
         "sample_stride": 1, "measurement_stage": "decode+pose_inference", "detection_rate_pct": 98,
         "foot_points_visible_frames": 90},
        {"video": "laisa.mp4", "frames": 100, "wall_seconds": 6, "reliable": True,
         "sample_stride": 1, "measurement_stage": "decode+pose_inference", "detection_rate_pct": 99,
         "foot_points_visible_frames": 95},
    ]}
    report = benchmark.compare(baseline, candidate)
    assert report["eligible_for_shadow_evaluation"] is True
    assert report["fps_ratio"] == 0.833
    assert [pair["video"] for pair in report["pairs"]] == ["laisa.mp4", "video23.mp4"]
    assert report["pairs"][0]["candidate_foot_coverage"] == 0.95
    assert report["clinical_winner"] is None
    assert report["clinical_conclusion"] == "not_assessed"


def test_benchmark_recusa_relatorios_nao_pareados_e_explica_motivo():
    benchmark = _tool("benchmark")
    baseline = {"runs": [{"video": "laisa.mp4", "frames": 100, "wall_seconds": 5,
                            "reliable": True, "sample_stride": 1,
                            "measurement_stage": "decode+pose_inference"}]}
    candidate = {"runs": [{"video": "outro.mp4", "frames": 100, "wall_seconds": 5,
                             "reliable": True, "sample_stride": 1,
                             "measurement_stage": "decode+pose_inference", "foot_points_visible": True}]}
    report = benchmark.compare(baseline, candidate)
    assert report["eligible_for_shadow_evaluation"] is False
    assert "candidate_missing_videos:laisa.mp4" in report["ineligibility_reasons"]
    assert "baseline_missing_videos:outro.mp4" in report["ineligibility_reasons"]


def test_benchmark_reporta_regressao_de_deteccao_quando_metricas_estao_disponiveis():
    benchmark = _tool("benchmark")
    baseline = {"runs": [{"video": "lateral.mp4", "frames": 100, "wall_seconds": 5,
                            "reliable": True, "sample_stride": 1,
                            "measurement_stage": "decode+pose_inference", "detection_rate_pct": 99}]}
    candidate = {"runs": [{"video": "lateral.mp4", "frames": 100, "wall_seconds": 5,
                             "reliable": True, "sample_stride": 1,
                             "measurement_stage": "decode+pose_inference", "detection_rate_pct": 90,
                             "foot_points_visible_frames": 100}]}
    report = benchmark.compare(baseline, candidate)
    assert report["detection_comparable"] is True
    assert report["detection_ok"] is False
    assert report["pairs"][0]["detection_rate_delta_pct"] == -9.0
    assert "candidate_detection_regression" in report["ineligibility_reasons"]


def test_benchmark_trata_deteccao_ausente_como_aviso_e_nao_dado_inventado():
    benchmark = _tool("benchmark")
    baseline = {"runs": [{"video": "lateral.mp4", "frames": 100, "wall_seconds": 5,
                            "reliable": True, "sample_stride": 1,
                            "measurement_stage": "decode+pose_inference"}]}
    candidate = {"runs": [{"video": "lateral.mp4", "frames": 100, "wall_seconds": 5,
                             "reliable": True, "sample_stride": 1,
                             "measurement_stage": "decode+pose_inference", "foot_points_visible": True}]}
    report = benchmark.compare(baseline, candidate)
    assert report["eligible_for_shadow_evaluation"] is True
    assert report["ineligibility_reasons"] == []
    assert report["comparison_warnings"] == ["detection_not_comparable"]


def test_benchmark_rejeita_video_duplicado_para_nao_parear_repeticoes_ambiguas():
    benchmark = _tool("benchmark")
    report = {"runs": [
        {"video": "lateral.mp4", "frames": 100, "wall_seconds": 5, "reliable": True,
         "sample_stride": 1, "measurement_stage": "decode+pose_inference"},
        {"video": "lateral.mp4", "frames": 100, "wall_seconds": 5, "reliable": True,
         "sample_stride": 1, "measurement_stage": "decode+pose_inference"},
    ]}
    try:
        benchmark.compare(report, report)
    except ValueError as error:
        assert "vídeo duplicado" in str(error)
    else:
        raise AssertionError("esperava rejeitar run duplicada")


def test_export_command_nao_baixa_nem_executa_modelo():
    export = _tool("export")
    cmd = export.export_command(Path("/tmp/mmdeploy"), Path("deploy.py"), Path("model.py"),
                                Path("body26.pth"), Path("out"), "cpu")
    assert cmd[0] and "deploy.py" in cmd[1] and "--device" in cmd


def test_runner_de_video_so_marca_confiavel_quando_pes_ficam_visiveis_na_maioria():
    runner = _tool("run_video_reference")
    reports = [
        {"valid": True, "instances_with_all_foot_points": 1},
        {"valid": True, "instances_with_all_foot_points": 1},
        {"valid": True, "instances_with_all_foot_points": 0},
    ]
    summary = runner.summarize_samples(reports, min_visible_rate=0.8)
    assert runner.sample_stride(30.0, 5.0) == 6
    assert summary["foot_points_visible_rate"] == 0.6667
    assert summary["reliable"] is False


def test_runner_de_video_espelha_dimensoes_do_ffmpeg_para_rotacao_de_celular():
    runner = _tool("run_video_reference")
    assert runner.oriented_dimensions(1024, 576, -90) == (576, 1024)
    assert runner.oriented_dimensions(1024, 576, 0) == (1024, 576)


def test_runner_normaliza_keypoints_sem_carregar_modelo():
    runner = _tool("run_reference")
    class Row(list):
        def tolist(self):
            return list(self)

    out = runner.normalize_keypoints([Row([[1.0, 2.0]] * 26)], [Row([1.05] * 26)])
    assert len(out["instances"]) == 1
    assert len(out["instances"][0]["keypoints"]) == 26
    assert out["instances"][0]["scores"] == [1.0] * 26
