//! stride-vision — pose estimation (YOLO11-pose via ONNX) + biomecânica feita na mão.
//!
//! Pipeline: imagem/frame -> letterbox 640x640 -> inferência -> 17 keypoints COCO
//! -> esqueleto desenhado + séries temporais (tornozelos) -> cadência (FFT).

use anyhow::{anyhow, Result};

/// erros do `ort` (não-Send) -> anyhow
fn o<T, E: std::fmt::Display>(r: std::result::Result<T, E>) -> Result<T> {
    r.map_err(|e| anyhow!("ort: {e}"))
}
use image::{DynamicImage, Rgb, RgbImage};
use imageproc::drawing::{draw_filled_circle_mut, draw_line_segment_mut};
use ndarray::Array4;
use ort::session::{builder::GraphOptimizationLevel, Session};
use rustfft::{num_complex::Complex, FftPlanner};

pub const INPUT: u32 = 640;
pub const KP_NAMES: [&str; 17] = [
    "nariz", "olho_e", "olho_d", "orelha_e", "orelha_d", "ombro_e", "ombro_d",
    "cotovelo_e", "cotovelo_d", "punho_e", "punho_d", "quadril_e", "quadril_d",
    "joelho_e", "joelho_d", "tornozelo_e", "tornozelo_d",
];
/// Ligações do esqueleto COCO (pares de índices de keypoints).
pub const SKELETON: [(usize, usize); 16] = [
    (15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12), (5, 6),
    (5, 7), (7, 9), (6, 8), (8, 10), (0, 5), (0, 6), (0, 1), (0, 2),
];

#[derive(Debug, Clone)]
pub struct Pose {
    /// (x, y, confiança) em coordenadas da imagem ORIGINAL
    pub keypoints: [(f32, f32, f32); 17],
    pub confidence: f32,
}

pub struct PoseEngine {
    session: Session,
}

impl PoseEngine {
    pub fn new(model_path: &str) -> Result<Self> {
        let session = o(o(o(o(Session::builder())?
            .with_optimization_level(GraphOptimizationLevel::Level3))?
            .with_intra_threads(4))?
            .commit_from_file(model_path))?;
        Ok(Self { session })
    }

    /// Detecta a pessoa mais confiante no frame. None = ninguém acima do limiar.
    pub fn infer(&mut self, img: &RgbImage) -> Result<Option<Pose>> {
        let (ow, oh) = (img.width() as f32, img.height() as f32);
        // letterbox: escala preservando proporção + padding cinza
        let scale = (INPUT as f32 / ow).min(INPUT as f32 / oh);
        let (nw, nh) = ((ow * scale) as u32, (oh * scale) as u32);
        let resized = image::imageops::resize(img, nw, nh, image::imageops::FilterType::Triangle);
        let (px, py) = (((INPUT - nw) / 2) as f32, ((INPUT - nh) / 2) as f32);

        let mut input = Array4::<f32>::from_elem((1, 3, INPUT as usize, INPUT as usize), 114.0 / 255.0);
        for (x, y, p) in resized.enumerate_pixels() {
            let (xx, yy) = (x as usize + px as usize, y as usize + py as usize);
            for c in 0..3 {
                input[[0, c, yy, xx]] = p.0[c] as f32 / 255.0;
            }
        }

        let tensor = o(ort::value::TensorRef::from_array_view(input.view()))?;
        let outputs = o(self.session.run(ort::inputs![tensor]))?;
        let out = o(outputs[0].try_extract_array::<f32>())?;   // [1, 56, N]
        let n = out.shape()[2];
        let at = |c: usize, i: usize| out[[0, c, i]];

        // melhor âncora (1 pessoa por frame é o caso do spike)
        let mut best: Option<(f32, usize)> = None;
        for i in 0..n {
            let conf = at(4, i);
            if conf > best.as_ref().map(|(c, _)| *c).unwrap_or(0.35) {
                best = Some((conf, i));
            }
        }
        let Some((conf, i)) = best else { return Ok(None) };

        let mut kps = [(0f32, 0f32, 0f32); 17];
        for k in 0..17 {
            let x = (at(5 + k * 3, i) - px) / scale;
            let y = (at(6 + k * 3, i) - py) / scale;
            kps[k] = (x.clamp(0.0, ow), y.clamp(0.0, oh), at(7 + k * 3, i));
        }
        Ok(Some(Pose { keypoints: kps, confidence: conf }))
    }
}

/// Desenha o esqueleto sobre o frame (o "vídeo da IA vendo o movimento").
pub fn draw_pose(img: &mut RgbImage, pose: &Pose) {
    let bone = Rgb([110u8, 86, 247]);     // brand roxo
    let joint = Rgb([52u8, 211, 153]);    // verde
    let w = (img.width().max(img.height()) / 320).max(2) as i32;
    for &(a, b) in SKELETON.iter() {
        let (ka, kb) = (pose.keypoints[a], pose.keypoints[b]);
        if ka.2 < 0.35 || kb.2 < 0.35 { continue; }
        // traço "grosso": segmentos deslocados
        for off in -(w / 2)..=(w / 2) {
            draw_line_segment_mut(img, (ka.0 + off as f32, ka.1), (kb.0 + off as f32, kb.1), bone);
            draw_line_segment_mut(img, (ka.0, ka.1 + off as f32), (kb.0, kb.1 + off as f32), bone);
        }
    }
    for &(x, y, c) in pose.keypoints.iter() {
        if c < 0.35 { continue; }
        draw_filled_circle_mut(img, (x as i32, y as i32), w * 2, joint);
    }
}

/// Cadência (passos/min) a partir da série vertical de UM tornozelo.
/// FFT: frequência dominante da oscilação de um pé * 2 (dois pés) * 60.
pub fn cadence_spm(ankle_y: &[f32], fps: f32) -> Option<f32> {
    if ankle_y.len() < 16 { return None; }
    let mean = ankle_y.iter().sum::<f32>() / ankle_y.len() as f32;
    let mut buf: Vec<Complex<f32>> =
        ankle_y.iter().map(|v| Complex::new(v - mean, 0.0)).collect();
    FftPlanner::new().plan_fft_forward(buf.len()).process(&mut buf);
    let n = buf.len();
    // procura o pico entre 0.5 e 2.5 Hz (30–150 passos/min por pé — faixa humana)
    let hz = |i: usize| i as f32 * fps / n as f32;
    let (mut bi, mut bm) = (0, 0f32);
    for i in 1..n / 2 {
        if hz(i) < 0.5 || hz(i) > 2.5 { continue; }
        let m = buf[i].norm();
        if m > bm { bm = m; bi = i; }
    }
    if bi == 0 { return None; }
    Some(hz(bi) * 2.0 * 60.0)
}

// ---------- métricas de forma (biomecânica feita na mão) ----------

/// Métricas extraídas das séries temporais dos keypoints (JSON p/ o backend).
#[derive(Debug, serde::Serialize)]
pub struct FormMetrics {
    pub frames: usize,
    pub fps: f32,
    /// % de frames com pessoa detectada (qualidade do vídeo p/ análise)
    pub detection_rate_pct: f32,
    pub cadence_spm: Option<f32>,
    pub cadence_left: Option<f32>,
    pub cadence_right: Option<f32>,
    /// diferença de amplitude entre tornozelos E/D (0% = simétrico)
    pub asymmetry_pct: Option<f32>,
    /// oscilação vertical do quadril como % do comprimento da perna
    /// (invariante à distância da câmera)
    pub vertical_oscillation_pct: Option<f32>,
}

/// amplitude robusta de uma série (p95 - p5; ignora outliers de detecção)
fn amplitude(series: &[f32]) -> Option<f32> {
    if series.len() < 8 { return None; }
    let mut v: Vec<f32> = series.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p = |q: f32| v[((v.len() - 1) as f32 * q) as usize];
    Some(p(0.95) - p(0.05))
}

/// Consolida as séries por frame em métricas de forma.
/// `leg_len_px` = mediana da distância quadril->tornozelo (escala do corpo).
pub fn analyze_form(
    ankle_l: &[f32], ankle_r: &[f32], hip_y: &[f32],
    leg_len_px: f32, fps: f32, total_frames: usize,
) -> FormMetrics {
    let (cl, cr) = (cadence_spm(ankle_l, fps), cadence_spm(ankle_r, fps));
    let cadence = match (cl, cr) {
        (Some(l), Some(r)) => Some((l + r) / 2.0),
        (a, b) => a.or(b),
    };
    let asymmetry = match (amplitude(ankle_l), amplitude(ankle_r)) {
        (Some(a), Some(b)) if a.max(b) > 0.0 => Some((a - b).abs() / a.max(b) * 100.0),
        _ => None,
    };
    let vert_osc = amplitude(hip_y)
        .filter(|_| leg_len_px > 0.0)
        .map(|a| a / leg_len_px * 100.0);
    FormMetrics {
        frames: total_frames,
        fps,
        detection_rate_pct: if total_frames > 0 {
            ankle_l.len() as f32 / total_frames as f32 * 100.0
        } else { 0.0 },
        cadence_spm: cadence,
        cadence_left: cl,
        cadence_right: cr,
        asymmetry_pct: asymmetry.map(|v| (v * 10.0).round() / 10.0),
        vertical_oscillation_pct: vert_osc.map(|v| (v * 10.0).round() / 10.0),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// série senoidal: pé oscilando a 1.4 Hz filmado a 30 fps
    fn sine(hz: f32, fps: f32, secs: f32, amp: f32) -> Vec<f32> {
        (0..(fps * secs) as usize)
            .map(|i| amp * (2.0 * std::f32::consts::PI * hz * i as f32 / fps).sin())
            .collect()
    }

    #[test]
    fn cadencia_de_uma_senoide_conhecida() {
        // 1.4 Hz por pé -> 1.4*2*60 = 168 spm
        let c = cadence_spm(&sine(1.4, 30.0, 10.0, 20.0), 30.0).unwrap();
        assert!((c - 168.0).abs() < 6.0, "cadência {c} fora do esperado");
    }

    #[test]
    fn assimetria_detecta_diferenca_de_amplitude() {
        let l = sine(1.4, 30.0, 10.0, 20.0);
        let r = sine(1.4, 30.0, 10.0, 14.0);          // perna direita 30% mais curta
        let m = analyze_form(&l, &r, &sine(2.8, 30.0, 10.0, 4.0), 100.0, 30.0, 300);
        let asym = m.asymmetry_pct.unwrap();
        assert!(asym > 20.0 && asym < 40.0, "assimetria {asym}");
        assert!(m.vertical_oscillation_pct.unwrap() > 5.0);
    }

    #[test]
    fn series_curtas_degradam_gracioso() {
        let m = analyze_form(&[1.0; 4], &[1.0; 4], &[1.0; 4], 100.0, 30.0, 4);
        assert!(m.cadence_spm.is_none() && m.asymmetry_pct.is_none());
    }
}
