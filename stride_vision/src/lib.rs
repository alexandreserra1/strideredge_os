//! stride-vision — pose estimation + biomecânica feita na mão, organizada em módulos.
//!
//! Pipeline: imagem/frame -> backend de pose (`backends`) -> `Pose` normalizada (`pose`) segundo um
//! layout semântico (`layout`) -> esqueleto/HUD desenhados (`draw`) + séries temporais consolidadas
//! em `FormMetrics` (`metrics`). O carregamento do ONNX Runtime fica isolado em `onnx`.
//!
//! O contrato público (o que o binário `main.rs` consome) é re-exportado aqui na raiz, então trocar
//! a organização interna dos módulos não muda `stride_vision::analyze_form`, `::PoseEngine`, etc.

mod backends;
mod draw;
mod layout;
mod metrics;
mod onnx;
mod pose;

/// Tamanho de entrada do YOLO (letterbox quadrado). Público por estabilidade de API.
pub const INPUT: u32 = 640;

pub use backends::{BlazePoseBackend, PoseEngine, RtmPose26Backend};
pub use draw::{draw_angles, draw_pose, joint_angle, joint_angle_3d};
pub use layout::{KeypointLayout, BLAZEPOSE33, COCO17, HALPE26};
pub use metrics::{
    analyze_form, cadence_spm, contact_angle, contact_flight_ms, foot_ground_y, foot_strike,
    hip_tilt_deg, knee_valgus_deg, median, percentile, timing_consistent_with_cadence,
    trunk_lean_deg, FormMetrics, MIN_DURATION_S, PRODUCTION_JOINT_ANGLE_SPACE,
};
pub use pose::{Pose, PoseBackend};
