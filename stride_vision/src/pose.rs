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
    /// (x, y, z) em METROS (origem no quadril), um por keypoint — SÓ o BlazePose entrega (3D real);
    /// None nos backends 2D (YOLO/RTM). Permite o ângulo articular imune à projeção 2D.
    pub world: Option<Vec<(f32, f32, f32)>>,
}

/// Contrato de inferência de pose. Três implementações: `PoseEngine` (YOLO11, padrão de transição),
/// `RtmPose26Backend` (Halpe26, experimental, bloqueado por licença dos pesos) e `BlazePoseBackend`
/// (candidato comercial Apache-2.0, opt-in por asset). Trocar de motor é trocar a impl — desenho e
/// métricas não mudam porque falam em índices semânticos do `KeypointLayout`.
pub trait PoseBackend {
    fn layout(&self) -> &'static KeypointLayout;
    /// `timestamp_ms` é monotônico para vídeo; backends sem rastreamento temporal podem ignorá-lo.
    fn infer(&mut self, img: &RgbImage, timestamp_ms: u64) -> Result<Option<Pose>>;
}
