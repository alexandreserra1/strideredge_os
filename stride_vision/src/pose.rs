//! pose.rs — o tipo `Pose` (saída normalizada) + o contrato `PoseBackend`.
//!
//! O pipeline de vídeo só precisa de poses normalizadas e do layout semântico; não deve saber se
//! elas vieram do YOLO (uma etapa) ou do RTMDet+RTMPose (duas etapas). Trocar o motor de pose é
//! trocar a implementação de `PoseBackend`, sem tocar em desenho nem em métricas.

use anyhow::Result;
use image::RgbImage;

use crate::layout::KeypointLayout;

#[derive(Debug, Clone)]
pub struct Pose {
    /// (x, y, confiança) em coordenadas da imagem ORIGINAL, um por keypoint do `layout`
    pub keypoints: Vec<(f32, f32, f32)>,
    pub confidence: f32,
    /// layout que descreve esses keypoints (índices semânticos, nomes, esqueleto)
    pub layout: &'static KeypointLayout,
}

/// Contrato de inferência de pose. Hoje `PoseEngine` (YOLO11) é a única implementação ativa; o
/// `RtmPose26Backend` (Halpe26) só entra depois que o spike em `tools/halpe26/` validar o ONNX e
/// os keypoints dos pés em vídeo real.
pub trait PoseBackend {
    fn layout(&self) -> &'static KeypointLayout;
    fn infer(&mut self, img: &RgbImage) -> Result<Option<Pose>>;
}
