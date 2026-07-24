"""Execução pesada da análise de forma, separada da fachada HTTP/CRUD.

`FormProcessingMixin` preserva os métodos internos de `FormService` para não quebrar a fila nem
os fakes de teste. Ele recebe do serviço apenas dependências já configuradas: fila, binário,
resolver de backend e snapshot de assets.
"""

import json
import math
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from api.pose_backends import PoseBackendSnapshot
from core.database import get_connection
from core.logging import Logger


_log = Logger("form")
_MAX_ATTEMPTS = 3
_FRONTAL_METRICS = ("pelvic_drop_deg", "knee_valgus_deg")
_SHADOW_METRICS = (
    "cadence_spm", "ground_contact_ms", "flight_ms", "knee_contact_deg", "hip_contact_deg",
    "vertical_oscillation_pct", "trunk_lean_deg",
)


@dataclass
class ProcessingReport:
    """Telemetria interna e sem PII dos estágios de uma análise.

    Não mistura duração com as métricas biomecânicas, que são insumo do coach. O relatório fica no
    banco para decidir capacidade/otimização e nunca é devolvido pelo endpoint do atleta.
    """

    stages: dict = field(default_factory=dict)

    def completed(self, name: str, started: float, **extra) -> None:
        self.stages[name] = {
            "status": "completed",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            **extra,
        }

    def status(self, name: str, value: str, **extra) -> None:
        self.stages[name] = {"status": value, **extra}

    def payload(self) -> dict:
        return {"schema_version": 1, "stages": self.stages}


def fuse_metrics(lateral: dict, frontal: Optional[dict]) -> dict:
    """Funde lateral e frontal sem transformar ausência de medida em risco baixo."""
    fused = dict(lateral)
    sources = {"sagittal": "lateral"}
    if frontal is None:
        fused["metric_sources"] = sources
        return fused
    if frontal.get("reliable"):
        for key in _FRONTAL_METRICS:
            fused[key] = frontal.get(key)
        sources["frontal_plane"] = "frontal"
    else:
        for key in _FRONTAL_METRICS:
            fused[key] = None
        sources["frontal_plane"] = "dropped_unreliable"
        reason = frontal.get("reason") or frontal.get("quality_note") or "captura ruim"
        fused["frontal_note"] = (
            f"A captura frontal não ficou confiável ({reason}) — refilme de frente para medir "
            "queda pélvica e valgo dinâmico de joelho.")
    fused["metric_sources"] = sources
    return fused


class FormProcessingMixin:
    """Normalização, execução do motor e jobs secundários de uma análise."""

    _ENV = {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}
    _NORMALIZE_LADDER = (
        {"max_side": 1280, "crf": "23", "preset": "medium"},
        {"max_side": 960, "crf": "28", "preset": "veryfast"},
        {"max_side": 640, "crf": "30", "preset": "ultrafast"},
    )

    def _normalize(self, src: Path) -> Path:
        """Normaliza rotação/codec para um H264 que o motor consegue decodificar."""
        dst = src.parent / f"{src.stem}.normalized.mp4"
        for step in self._NORMALIZE_LADDER:
            if self._ffmpeg_normalize(src, dst, **step):
                return dst
        return src

    def _ffmpeg_normalize(self, src: Path, dst: Path, max_side: int, crf: str,
                           preset: str) -> bool:
        vf = (f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease,"
              "scale=trunc(iw/2)*2:trunc(ih/2)*2")
        cmd = [
            "ffmpeg", "-v", "error", "-y", "-i", str(src),
            "-vf", vf, "-metadata:s:v:0", "rotate=0", "-c:v", "libx264",
            "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-an", str(dst),
        ]
        result = subprocess.run(cmd, env={**self._ENV}, capture_output=True, text=True, timeout=300)
        return result.returncode == 0 and dst.exists() and dst.stat().st_size > 0

    def _run_engine(self, original: Path, overlay: Path, view: str,
                    snapshot: PoseBackendSnapshot, draw_overlay: bool = True) -> dict:
        """Roda o motor Rust; sem overlay, entrega a passada rápida de métricas."""
        return self._run_engine_impl(original, overlay, view, snapshot, draw_overlay)

    def _run_engine_impl(self, original: Path, overlay: Path, view: str,
                         snapshot: PoseBackendSnapshot, draw_overlay: bool,
                         timings: Optional[dict] = None) -> dict:
        """Implementação de produção com decomposição opcional de normalização e inferência."""
        normalize_started = time.perf_counter()
        source = self._normalize(original)
        if timings is not None:
            timings["normalize_ms"] = round((time.perf_counter() - normalize_started) * 1000, 1)
        cmd = [str(self.binary), str(source), str(overlay), "--view", view,
               "--backend", snapshot.effective]
        if not draw_overlay:
            cmd.append("--no-overlay")
        engine_started = time.perf_counter()
        result = subprocess.run(
            cmd, env={**snapshot.subprocess_env, **self._ENV},
            capture_output=True, text=True, timeout=600)
        if timings is not None:
            timings["engine_ms"] = round((time.perf_counter() - engine_started) * 1000, 1)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-300:] or "motor falhou")
        metrics = json.loads((overlay.parent / f"{overlay.stem}.metrics.json").read_text())
        if source != original:
            source.unlink(missing_ok=True)
        return metrics

    def _run_engine_profiled(self, original: Path, overlay: Path, view: str,
                             snapshot: PoseBackendSnapshot, draw_overlay: bool = True) -> tuple:
        """Roda o contrato existente e devolve durações sem exigir que os fakes mudem de assinatura."""
        started = time.perf_counter()
        timings = {}
        # Os fakes nos testes (e extensões futuras) podem continuar sobrescrevendo `_run_engine`.
        # Só a implementação de produção entra no caminho que separa ffmpeg e o subprocesso Rust.
        implementation = getattr(self._run_engine, "__func__", None)
        if implementation is FormProcessingMixin._run_engine:
            metrics = self._run_engine_impl(original, overlay, view, snapshot, draw_overlay, timings)
        else:
            metrics = self._run_engine(original, overlay, view, snapshot, draw_overlay)
        timings["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return metrics, timings

    @staticmethod
    def _shadow_quality(metrics: dict) -> dict:
        out = {"reliable": bool(metrics.get("reliable"))}
        for key in ("detection_rate_pct", "frames", "fps"):
            value = metrics.get(key)
            if isinstance(value, (int, float)) and math.isfinite(value):
                out[key] = value
        reason = metrics.get("reason")
        if isinstance(reason, str):
            out["reason"] = reason[:160]
        return out

    @staticmethod
    def _shadow_backend_metadata(snapshot: PoseBackendSnapshot) -> dict:
        return {
            "requested": snapshot.requested,
            "effective": snapshot.effective,
            "model_version": snapshot.model_version,
            "assets": dict(snapshot.model_assets),
        }

    @staticmethod
    def _shadow_metric_deltas(primary: dict, candidate: dict) -> dict:
        """Diferenças numéricas pareadas, sem decidir qual backend está clinicamente correto."""
        deltas = {}
        for key in _SHADOW_METRICS:
            left, right = primary.get(key), candidate.get(key)
            if (isinstance(left, (int, float)) and isinstance(right, (int, float)) and
                    math.isfinite(left) and math.isfinite(right)):
                deltas[key] = round(right - left, 3)
        return deltas

    def _run_shadow(self, original: Path, view: str, primary_metrics: dict) -> dict:
        if self._shadow_configuration_error:
            return {"status": "failed", "reason": self._shadow_configuration_error}
        if not primary_metrics.get("reliable"):
            return {"status": "skipped", "reason": "primary_unreliable"}
        if self.shadow_backend is None:
            return {"status": "skipped", "reason": "not_configured"}

        started = time.perf_counter()
        shadow_overlay = original.parent / "shadow_overlay.mp4"
        shadow_metrics_path = shadow_overlay.parent / f"{shadow_overlay.stem}.metrics.json"
        try:
            snapshot = self._resolve_backend_snapshot(self.shadow_backend)
            shadow_view = "lateral" if view == "combined" else view
            shadow_metrics = self._run_engine(original, shadow_overlay, shadow_view, snapshot,
                                              draw_overlay=False)
            primary_quality = self._shadow_quality(primary_metrics)
            candidate_quality = self._shadow_quality(shadow_metrics)
            report = {
                "status": "completed",
                "backend": self._shadow_backend_metadata(snapshot),
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "primary_quality": primary_quality,
                "shadow_quality": candidate_quality,
                "comparison": {
                    "reliable_match": primary_quality["reliable"] == candidate_quality["reliable"],
                    "metric_deltas": self._shadow_metric_deltas(primary_metrics, shadow_metrics),
                    "joint_angle_space_match": (
                        primary_metrics.get("joint_angle_space") == shadow_metrics.get("joint_angle_space")),
                },
            }
            if ("detection_rate_pct" in primary_quality and
                    "detection_rate_pct" in candidate_quality):
                report["comparison"]["detection_rate_delta_pct"] = round(
                    candidate_quality["detection_rate_pct"] - primary_quality["detection_rate_pct"], 3)
            return report
        except Exception as exc:  # shadow nunca pode falhar a análise principal
            _log.error("form_shadow_failed", error=str(exc)[:200], backend=self.shadow_backend)
            return {
                "status": "failed",
                "reason": "shadow_execution_failed",
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        finally:
            shadow_overlay.unlink(missing_ok=True)
            shadow_metrics_path.unlink(missing_ok=True)
            (original.parent / f"{original.stem}.normalized.mp4").unlink(missing_ok=True)

    @staticmethod
    def _persist_shadow_report(con, analysis_id: str, report: dict) -> None:
        con.execute(
            "UPDATE form_analyses SET shadow_report=? WHERE analysis_id=?",
            [json.dumps(report, sort_keys=True), analysis_id])

    @staticmethod
    def _persist_processing_report(con, analysis_id: str, report: ProcessingReport) -> None:
        """Persiste somente duração/status dos estágios; nunca métricas, paths ou dados do atleta."""
        con.execute(
            "UPDATE form_analyses SET processing_report=? WHERE analysis_id=?",
            [json.dumps(report.payload(), sort_keys=True), analysis_id])

    @staticmethod
    def _complete_overlay_report(analysis_id: str, started: float, status: str,
                                 timings: Optional[dict] = None) -> None:
        """Atualiza o estágio cosmético sem tocar no resultado biométrico já entregue.

        O job de overlay pode rodar em outro worker. Ele lê e regrava apenas o pequeno JSON interno
        depois que `_process` já o persistiu, evitando estado compartilhado entre threads Python.
        """
        con = get_connection()
        row = con.execute(
            "SELECT processing_report FROM form_analyses WHERE analysis_id=?", [analysis_id]
        ).fetchone()
        try:
            payload = json.loads(row[0]) if row and row[0] else {"schema_version": 1, "stages": {}}
        except (TypeError, json.JSONDecodeError):
            payload = {"schema_version": 1, "stages": {}}
        payload.setdefault("stages", {})["overlay"] = {
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            **(timings or {}),
        }
        con.execute(
            "UPDATE form_analyses SET processing_report=? WHERE analysis_id=?",
            [json.dumps(payload, sort_keys=True), analysis_id])

    def _process(self, analysis_id: str, original: Path, view: str = "lateral",
                 frontal_original: Optional[Path] = None,
                 snapshot: Optional[PoseBackendSnapshot] = None, attempt: int = 1) -> None:
        """Entrega métricas primeiro e agenda o overlay cosmético depois."""
        overlay = original.parent / "overlay.mp4"
        con = get_connection()
        report = ProcessingReport()
        try:
            snapshot = snapshot or self._backend_snapshot()
            stage_started = time.perf_counter()
            base, metrics_timing = self._run_engine_profiled(
                original, overlay, view, snapshot, draw_overlay=False)
            report.completed("metrics", stage_started, **metrics_timing)
            frontal = None
            if frontal_original is not None:
                stage_started = time.perf_counter()
                frontal, frontal_timing = self._run_engine_profiled(
                    frontal_original, original.parent / "overlay_frontal.mp4", "frontal", snapshot,
                    draw_overlay=False)
                report.completed("frontal_metrics", stage_started, **frontal_timing)
            metrics = fuse_metrics(base, frontal) if frontal_original is not None else base
            stored_view = "combined" if frontal_original is not None else view
            con.execute(
                "UPDATE form_analyses SET status='done', video_path=NULL, metrics=?, view=? "
                "WHERE analysis_id=?", [json.dumps(metrics), stored_view, analysis_id])
            if self.shadow_backend is not None or self._shadow_configuration_error:
                try:
                    shadow_report = self._run_shadow(original, stored_view, base)
                    self._persist_shadow_report(con, analysis_id, shadow_report)
                    timing_status = "completed" if shadow_report.get("status") == "completed" else "skipped"
                    report_timing = shadow_report.get("duration_ms")
                    if isinstance(report_timing, (int, float)):
                        report.status("shadow", timing_status, duration_ms=report_timing)
                    else:
                        report.status("shadow", timing_status)
                    _log.info("form_shadow_done", analysis_id=analysis_id,
                              status=shadow_report.get("status"), backend=self.shadow_backend)
                except Exception as shadow_error:  # noqa: BLE001 — isolamento deliberado
                    report.status("shadow", "failed")
                    _log.error("form_shadow_report_failed", analysis_id=analysis_id,
                               error=str(shadow_error)[:200])
            if frontal_original is not None:
                frontal_original.unlink(missing_ok=True)
            # Persiste ANTES de enfileirar: a fila de testes (e uma implementação futura) pode
            # executar o job imediatamente; assim o overlay sempre encontra um relatório para
            # completar em vez de ter sua duração sobrescrita como apenas "queued".
            overlay_requested = bool(base.get("reliable"))
            report.status("overlay", "queued" if overlay_requested else "skipped_unreliable")
            self._persist_processing_report(con, analysis_id, report)
            queued = overlay_requested and self.queue.enqueue(
                self._render_overlay, analysis_id, original, view, snapshot) is not False
            if overlay_requested and not queued:
                report.status("overlay", "not_queued")
                self._persist_processing_report(con, analysis_id, report)
            if not queued:
                original.unlink(missing_ok=True)
            _log.info("form_done", analysis_id=analysis_id, reliable=base.get("reliable"),
                      reason=base.get("reason"), detection_rate=base.get("detection_rate_pct"),
                      raw_vert_osc_pct=base.get("diag_vert_osc_pct"),
                      leg_len_px=base.get("diag_leg_len_px"), view=stored_view,
                      frontal_reliable=(frontal or {}).get("reliable") if frontal else None,
                      backend=snapshot.effective, model_version=snapshot.model_version)
        except Exception as exc:  # noqa: BLE001 — falha transitória ganha retry limitado
            if attempt < _MAX_ATTEMPTS and original.exists():
                _log.info("form_retry", analysis_id=analysis_id, attempt=attempt,
                          error=str(exc)[:200])
                if self.queue.enqueue(self._process, analysis_id, original, view,
                                      frontal_original, snapshot, attempt + 1) is not False:
                    return
            con.execute(
                "UPDATE form_analyses SET status='failed', error=? WHERE analysis_id=?",
                [str(exc)[:300], analysis_id])
            original.unlink(missing_ok=True)
            if frontal_original is not None:
                frontal_original.unlink(missing_ok=True)
            _log.error("form_failed", analysis_id=analysis_id, attempts=attempt, error=str(exc)[:200])

    def _render_overlay(self, analysis_id: str, original: Path, view: str,
                        snapshot: PoseBackendSnapshot) -> None:
        overlay = original.parent / "overlay.mp4"
        overlay_view = "frontal" if view == "frontal" else "lateral"
        started = time.perf_counter()
        overlay_status = "failed"
        overlay_timing = None
        try:
            _, overlay_timing = self._run_engine_profiled(
                original, overlay, overlay_view, snapshot, draw_overlay=True)
            get_connection().execute(
                "UPDATE form_analyses SET video_path=? WHERE analysis_id=?",
                [str(overlay), analysis_id])
            overlay_status = "completed"
            _log.info("form_overlay_done", analysis_id=analysis_id)
        except Exception as exc:  # noqa: BLE001 — overlay não afeta o resultado já entregue
            _log.error("form_overlay_failed", analysis_id=analysis_id, error=str(exc)[:200])
        finally:
            self._complete_overlay_report(analysis_id, started, overlay_status, overlay_timing)
            original.unlink(missing_ok=True)
            (original.parent / f"{original.stem}.normalized.mp4").unlink(missing_ok=True)
