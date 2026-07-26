//! backends — implementações de `PoseBackend`.
//!
//! `blazepose` (GHUM, 33 pts + 3D, Apache) é o backend do PRODUTO. `yolo` (COCO-17, uma etapa) é a
//! régua de comparação (shadow/avaliação pareada). Ambos falam o mesmo contrato `PoseBackend`,
//! então quem consome não sabe qual roda.

mod blazepose;
mod yolo;

pub use blazepose::BlazePoseBackend;
pub use yolo::PoseEngine;
