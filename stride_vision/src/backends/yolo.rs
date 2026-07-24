//! backends/yolo.rs — `PoseEngine`: YOLO11-pose (COCO-17) via ONNX. Backend de PRODUÇÃO.
//!
//! Uma etapa: letterbox 640x640 -> inferência -> decode do tensor [1, 4+1+3*K, N]. Rastreio
//! temporal (`last_center`) evita trocar de pessoa em vídeo com várias (corredor + apresentadores).

use anyhow::Result;
use image::RgbImage;
use ndarray::Array4;
use ort::session::Session;

use crate::layout::{KeypointLayout, COCO17};
use crate::onnx::{load_session, o};
use crate::pose::{Pose, PoseBackend};
use crate::INPUT;

pub struct PoseEngine {
    session: Session,
    layout: &'static KeypointLayout,
    // centro (640-space) da pessoa rastreada no frame anterior — consistência temporal p/ NÃO
    // trocar de pessoa em vídeo com várias (corredor + apresentadores parados). None = reacquire.
    last_center: Option<(f32, f32)>,
}

impl PoseEngine {
    /// Motor com o layout PADRÃO (COCO-17). É o caminho usado em produção hoje.
    pub fn new(model_path: &str) -> Result<Self> {
        Self::with_layout(model_path, &COCO17)
    }

    /// Motor com um layout explícito (ex.: `&HALPE26` quando o modelo estiver disponível).
    pub fn with_layout(model_path: &str, layout: &'static KeypointLayout) -> Result<Self> {
        let session = load_session(model_path)?;
        Ok(Self {
            session,
            layout,
            last_center: None,
        })
    }

    /// Layout ativo deste motor (índices semânticos p/ quem consome as poses).
    pub fn layout(&self) -> &'static KeypointLayout {
        self.layout
    }

    /// Detecta a pessoa mais confiante no frame. None = ninguém acima do limiar.
    pub fn infer(&mut self, img: &RgbImage) -> Result<Option<Pose>> {
        let (ow, oh) = (img.width() as f32, img.height() as f32);
        // letterbox: escala preservando proporção + padding cinza
        let scale = (INPUT as f32 / ow).min(INPUT as f32 / oh);
        let (nw, nh) = ((ow * scale) as u32, (oh * scale) as u32);
        let resized = image::imageops::resize(img, nw, nh, image::imageops::FilterType::Triangle);
        let (px, py) = (((INPUT - nw) / 2) as f32, ((INPUT - nh) / 2) as f32);

        let mut input =
            Array4::<f32>::from_elem((1, 3, INPUT as usize, INPUT as usize), 114.0 / 255.0);
        for (x, y, p) in resized.enumerate_pixels() {
            let (xx, yy) = (x as usize + px as usize, y as usize + py as usize);
            for c in 0..3 {
                input[[0, c, yy, xx]] = p.0[c] as f32 / 255.0;
            }
        }

        let tensor = o(ort::value::TensorRef::from_array_view(input.view()))?;
        let outputs = o(self.session.run(ort::inputs![tensor]))?;
        // saída YOLO-pose: [1, 4+1+3*K, N] — 4 box + 1 conf + 3 (x,y,conf) por keypoint.
        // COCO-17 => 56 canais; Halpe26 => 5+78 = 83. Derivado do layout, não hard-coded.
        let out = o(outputs[0].try_extract_array::<f32>())?;
        let k_count = self.layout.count;
        let n = out.shape()[2];
        let at = |c: usize, i: usize| out[[0, c, i]];

        // candidatos acima do limiar — podem ser PESSOAS DIFERENTES no quadro (corredor +
        // apresentadores). Escolhe por CONSISTÊNCIA TEMPORAL: a mais próxima do frame anterior
        // (não troca de pessoa); na 1ª vez (ou reacquire), a de maior confiança.
        let mut cands: Vec<(f32, usize, f32, f32)> = Vec::new(); // (conf, i, cx, cy) em 640-space
        for i in 0..n {
            if at(4, i) > 0.35 {
                cands.push((at(4, i), i, at(0, i), at(1, i)));
            }
        }
        if cands.is_empty() {
            return Ok(None);
        }
        let (conf, i) = match self.last_center {
            Some((lx, ly)) => {
                let b = cands
                    .iter()
                    .min_by(|a, b| {
                        let da = (a.2 - lx).powi(2) + (a.3 - ly).powi(2);
                        let db = (b.2 - lx).powi(2) + (b.3 - ly).powi(2);
                        da.partial_cmp(&db).unwrap()
                    })
                    .unwrap();
                (b.0, b.1)
            }
            None => {
                let b = cands
                    .iter()
                    .max_by(|a, b| a.0.partial_cmp(&b.0).unwrap())
                    .unwrap();
                (b.0, b.1)
            }
        };
        self.last_center = Some((at(0, i), at(1, i)));

        let mut kps = vec![(0f32, 0f32, 0f32); k_count];
        for k in 0..k_count {
            let x = (at(5 + k * 3, i) - px) / scale;
            let y = (at(6 + k * 3, i) - py) / scale;
            kps[k] = (x.clamp(0.0, ow), y.clamp(0.0, oh), at(7 + k * 3, i));
        }
        Ok(Some(Pose {
            keypoints: kps,
            confidence: conf,
            layout: self.layout,
            world: None,
        }))
    }
}

/// O YOLO11 segue sendo o backend de produção. Esta implementação deixa explícito que o motor
/// atual fala o contrato genérico, sem declarar falsamente que um ONNX RTMPose já é compatível
/// com o decoder YOLO acima.
impl PoseBackend for PoseEngine {
    fn layout(&self) -> &'static KeypointLayout {
        PoseEngine::layout(self)
    }

    fn infer(&mut self, img: &RgbImage, _timestamp_ms: u64) -> Result<Option<Pose>> {
        PoseEngine::infer(self, img)
    }
}
