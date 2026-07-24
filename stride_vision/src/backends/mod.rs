//! backends — implementações de `PoseBackend`.
//!
//! `yolo` (COCO-17, uma etapa) é o backend de PRODUÇÃO. `rtm` (Halpe26, RTMDet+RTMPose, duas
//! etapas) é EXPERIMENTAL e bloqueado por asset — não é selecionado por padrão nem carrega pesos
//! implícitos. Ambos falam o mesmo contrato `PoseBackend`, então quem consome não sabe qual roda.

mod blazepose;
mod rtm;
mod yolo;

pub use blazepose::BlazePoseBackend;
pub use rtm::RtmPose26Backend;
pub use yolo::PoseEngine;
