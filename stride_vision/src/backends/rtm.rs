//! backends/rtm.rs — RTMPose / Halpe26 (EXPERIMENTAL, dois ONNX).
//!
//! O detector YOLOX do pacote ONNX oficial já contém NMS e devolve caixas xyxy + score. O pose
//! model recebe um crop top-down 192x256 e devolve SimCC: duas distribuições 1D (X e Y) para cada
//! keypoint. Este backend não é selecionado pelo CLI padrão e não carrega pesos implícitos; quem o
//! usa precisa fornecer os dois caminhos de assets aprovados explicitamente.

use anyhow::{anyhow, Result};
use image::RgbImage;
use ndarray::Array4;
use ort::session::Session;

use crate::layout::{KeypointLayout, HALPE26};
use crate::onnx::{load_session, o};
use crate::pose::{Pose, PoseBackend};

const RTMDET_INPUT: u32 = 640;
const RTMPOSE_WIDTH: u32 = 192;
const RTMPOSE_HEIGHT: u32 = 256;
const RTMPOSE_MEAN: [f32; 3] = [123.675, 116.28, 103.53];
const RTMPOSE_STD: [f32; 3] = [58.395, 57.12, 57.375];

#[derive(Clone, Copy, Debug)]
struct RtmCrop {
    center_x: f32,
    center_y: f32,
    scale_x: f32,
    scale_y: f32,
}

impl RtmCrop {
    fn from_xyxy(x1: f32, y1: f32, x2: f32, y2: f32) -> Self {
        let (mut scale_x, mut scale_y) = ((x2 - x1).max(1.0) * 1.25, (y2 - y1).max(1.0) * 1.25);
        let aspect = RTMPOSE_WIDTH as f32 / RTMPOSE_HEIGHT as f32;
        if scale_x > scale_y * aspect { scale_y = scale_x / aspect; }
        else { scale_x = scale_y * aspect; }
        Self { center_x: (x1 + x2) * 0.5, center_y: (y1 + y2) * 0.5, scale_x, scale_y }
    }

    fn to_image(self, x: f32, y: f32) -> (f32, f32) {
        (x / RTMPOSE_WIDTH as f32 * self.scale_x + self.center_x - self.scale_x * 0.5,
         y / RTMPOSE_HEIGHT as f32 * self.scale_y + self.center_y - self.scale_y * 0.5)
    }
}

/// Backend experimental de 26 pontos: RTMDet/YOLOX (pessoa) + RTMPose/SimCC (Halpe26).
pub struct RtmPose26Backend {
    detector: Session,
    pose: Session,
    last_center: Option<(f32, f32)>,
}

impl RtmPose26Backend {
    pub fn new(detector_path: &str, pose_path: &str) -> Result<Self> {
        Ok(Self { detector: load_session(detector_path)?, pose: load_session(pose_path)?, last_center: None })
    }

    fn detector_input(img: &RgbImage) -> (Array4<f32>, f32) {
        let (ow, oh) = (img.width() as f32, img.height() as f32);
        let ratio = (RTMDET_INPUT as f32 / ow).min(RTMDET_INPUT as f32 / oh);
        let (nw, nh) = ((ow * ratio) as u32, (oh * ratio) as u32);
        let resized = image::imageops::resize(img, nw, nh, image::imageops::FilterType::Triangle);
        // rtmlib recebe OpenCV/BGR: padding no canto superior esquerdo, sem centralizar.
        let mut input = Array4::<f32>::from_elem((1, 3, RTMDET_INPUT as usize, RTMDET_INPUT as usize), 114.0);
        for (x, y, p) in resized.enumerate_pixels() {
            input[[0, 0, y as usize, x as usize]] = p.0[2] as f32;
            input[[0, 1, y as usize, x as usize]] = p.0[1] as f32;
            input[[0, 2, y as usize, x as usize]] = p.0[0] as f32;
        }
        (input, ratio)
    }

    fn detect(&mut self, img: &RgbImage) -> Result<Option<(f32, RtmCrop)>> {
        let (input, ratio) = Self::detector_input(img);
        let tensor = o(ort::value::TensorRef::from_array_view(input.view()))?;
        let outputs = o(self.detector.run(ort::inputs![tensor]))?;
        let dets = o(outputs[0].try_extract_array::<f32>())?;
        if dets.ndim() != 3 || dets.shape()[0] != 1 || dets.shape()[2] != 5 {
            return Err(anyhow!("ONNX RTMDet incompatível: esperado dets [1,N,5], recebido {:?}", dets.shape()));
        }
        let mut candidates = Vec::new();
        for i in 0..dets.shape()[1] {
            let score = dets[[0, i, 4]];
            let (x1, y1, x2, y2) = (dets[[0, i, 0]] / ratio, dets[[0, i, 1]] / ratio,
                                     dets[[0, i, 2]] / ratio, dets[[0, i, 3]] / ratio);
            if score.is_finite() && score > 0.3 && x2 > x1 && y2 > y1 {
                let crop = RtmCrop::from_xyxy(x1, y1, x2, y2);
                candidates.push((score, crop));
            }
        }
        if candidates.is_empty() { return Ok(None); }
        let chosen = match self.last_center {
            Some((last_x, last_y)) => candidates.into_iter().min_by(|a, b| {
                let da = (a.1.center_x - last_x).powi(2) + (a.1.center_y - last_y).powi(2);
                let db = (b.1.center_x - last_x).powi(2) + (b.1.center_y - last_y).powi(2);
                da.partial_cmp(&db).unwrap()
            }).unwrap(),
            None => candidates.into_iter().max_by(|a, b| a.0.partial_cmp(&b.0).unwrap()).unwrap(),
        };
        self.last_center = Some((chosen.1.center_x, chosen.1.center_y));
        Ok(Some(chosen))
    }

    fn bgr_bilinear(img: &RgbImage, x: f32, y: f32) -> [f32; 3] {
        let pixel = |xx: i32, yy: i32| -> [f32; 3] {
            if xx < 0 || yy < 0 || xx as u32 >= img.width() || yy as u32 >= img.height() { return [0.0; 3]; }
            let p = img.get_pixel(xx as u32, yy as u32).0;
            [p[2] as f32, p[1] as f32, p[0] as f32]
        };
        let (x0, y0) = (x.floor() as i32, y.floor() as i32);
        let (dx, dy) = (x - x0 as f32, y - y0 as f32);
        let (a, b, c, d) = (pixel(x0, y0), pixel(x0 + 1, y0), pixel(x0, y0 + 1), pixel(x0 + 1, y0 + 1));
        let mut out = [0.0; 3];
        for channel in 0..3 {
            out[channel] = a[channel] * (1.0 - dx) * (1.0 - dy) + b[channel] * dx * (1.0 - dy)
                + c[channel] * (1.0 - dx) * dy + d[channel] * dx * dy;
        }
        out
    }

    fn pose_input(img: &RgbImage, crop: RtmCrop) -> Array4<f32> {
        let mut input = Array4::<f32>::zeros((1, 3, RTMPOSE_HEIGHT as usize, RTMPOSE_WIDTH as usize));
        for y in 0..RTMPOSE_HEIGHT as usize {
            for x in 0..RTMPOSE_WIDTH as usize {
                let (source_x, source_y) = crop.to_image(x as f32, y as f32);
                let pixel = Self::bgr_bilinear(img, source_x, source_y);
                for channel in 0..3 {
                    input[[0, channel, y, x]] = (pixel[channel] - RTMPOSE_MEAN[channel]) / RTMPOSE_STD[channel];
                }
            }
        }
        input
    }

    fn simcc_peak(values: &[f32]) -> (usize, f32) {
        values.iter().enumerate().filter(|(_, value)| value.is_finite())
            .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap()).map(|(i, value)| (i, *value)).unwrap_or((0, 0.0))
    }

    fn decode(&mut self, img: &RgbImage, crop: RtmCrop, confidence: f32) -> Result<Pose> {
        let input = Self::pose_input(img, crop);
        let tensor = o(ort::value::TensorRef::from_array_view(input.view()))?;
        let outputs = o(self.pose.run(ort::inputs![tensor]))?;
        if outputs.len() != 2 { return Err(anyhow!("ONNX RTMPose incompatível: esperado duas saídas SimCC")); }
        let (simcc_x, simcc_y) = (o(outputs[0].try_extract_array::<f32>())?, o(outputs[1].try_extract_array::<f32>())?);
        if simcc_x.ndim() != 3 || simcc_y.ndim() != 3 || simcc_x.shape()[0] != 1 || simcc_y.shape()[0] != 1
            || simcc_x.shape()[1] != HALPE26.count || simcc_y.shape()[1] != HALPE26.count {
            return Err(anyhow!("ONNX RTMPose incompatível: esperado SimCC [1,26,X]/[1,26,Y], recebido {:?}/{:?}", simcc_x.shape(), simcc_y.shape()));
        }
        let mut keypoints = Vec::with_capacity(HALPE26.count);
        for k in 0..HALPE26.count {
            let x_values: Vec<f32> = (0..simcc_x.shape()[2]).map(|i| simcc_x[[0, k, i]]).collect();
            let y_values: Vec<f32> = (0..simcc_y.shape()[2]).map(|i| simcc_y[[0, k, i]]).collect();
            let (x_bin, x_score) = Self::simcc_peak(&x_values);
            let (y_bin, y_score) = Self::simcc_peak(&y_values);
            let (x, y) = crop.to_image(x_bin as f32 / 2.0, y_bin as f32 / 2.0);
            // SimCC produz uma ativação; a borda pública de Pose usa confiança [0,1].
            keypoints.push((x.clamp(0.0, img.width() as f32), y.clamp(0.0, img.height() as f32),
                            ((x_score + y_score) * 0.5).clamp(0.0, 1.0)));
        }
        Ok(Pose { keypoints, confidence, layout: &HALPE26 })
    }
}

impl PoseBackend for RtmPose26Backend {
    fn layout(&self) -> &'static KeypointLayout { &HALPE26 }

    fn infer(&mut self, img: &RgbImage) -> Result<Option<Pose>> {
        let Some((confidence, crop)) = self.detect(img)? else { return Ok(None); };
        Ok(Some(self.decode(img, crop, confidence)?))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crop_rtmpose_preserva_aspecto_e_mapeia_centro_da_rede_para_pessoa() {
        let crop = RtmCrop::from_xyxy(100.0, 80.0, 300.0, 280.0);
        assert!((crop.scale_x / crop.scale_y - 0.75).abs() < 0.001);
        let center = crop.to_image(RTMPOSE_WIDTH as f32 * 0.5, RTMPOSE_HEIGHT as f32 * 0.5);
        assert!((center.0 - 200.0).abs() < 0.001 && (center.1 - 180.0).abs() < 0.001);
    }

    #[test]
    fn simcc_escolhe_o_pico_e_descarta_ativacao_invalida() {
        let (index, score) = RtmPose26Backend::simcc_peak(&[0.1, f32::NAN, 0.7, 0.2]);
        assert_eq!((index, score), (2, 0.7));
        assert_eq!(RtmPose26Backend::simcc_peak(&[f32::NAN]), (0, 0.0));
    }
}
