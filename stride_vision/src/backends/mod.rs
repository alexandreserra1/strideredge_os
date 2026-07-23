//! backends — implementações de `PoseBackend`.
//!
//! `yolo` (COCO-17, uma etapa) é o backend de PRODUÇÃO. `rtm` (Halpe26, RTMDet+RTMPose, duas
//! etapas) é EXPERIMENTAL e bloqueado por asset — não é selecionado por padrão nem carrega pesos
//! implícitos. Ambos falam o mesmo contrato `PoseBackend`, então quem consome não sabe qual roda.

mod yolo;
mod rtm;

pub use yolo::PoseEngine;
pub use rtm::RtmPose26Backend;
