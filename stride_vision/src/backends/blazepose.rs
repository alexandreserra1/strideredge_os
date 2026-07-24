//! Adaptador do Pose Landmarker oficial (MediaPipe Tasks C API) para o contrato Rust.
//!
//! A ponte C++ só conhece a ABI externa e retorna 33 landmarks normalizados. Esta camada é dona
//! da semântica do StriderEdge: pixels da imagem original e confiança compatível com os demais
//! backends (`min(visibility, presence)`). Nenhuma métrica clínica é criada aqui.

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};
use std::ptr::NonNull;

use anyhow::{anyhow, bail, Result};
use image::RgbImage;

use crate::layout::{KeypointLayout, BLAZEPOSE33};
use crate::pose::{Pose, PoseBackend};

const LANDMARK_COUNT: usize = 33;
const FIELDS_PER_LANDMARK: usize = 4;
const RAW_VALUES: usize = LANDMARK_COUNT * FIELDS_PER_LANDMARK;
const WORLD_VALUES: usize = LANDMARK_COUNT * 3; // (x,y,z) em metros por keypoint
const ERROR_BUFFER: usize = 512;

#[repr(C)]
struct SePoseBridge {
    _private: [u8; 0],
}

unsafe extern "C" {
    fn se_pose_bridge_create(
        runtime_path: *const c_char,
        model_path: *const c_char,
        error: *mut c_char,
        error_size: usize,
    ) -> *mut SePoseBridge;
    fn se_pose_bridge_infer(
        bridge: *mut SePoseBridge,
        rgb: *const u8,
        width: u32,
        height: u32,
        timestamp_ms: i64,
        out_landmarks: *mut f32,
        out_world: *mut f32,
        found: *mut c_int,
        error: *mut c_char,
        error_size: usize,
    ) -> c_int;
    fn se_pose_bridge_close(bridge: *mut SePoseBridge);
}

/// Backend nativo, opt-in, para o bundle oficial `.task` do Pose Landmarker.
/// `runtime_path` aponta para o runtime C oficial empacotado para a plataforma; não há Python no
/// caminho de inferência. O handle é mutável porque o modo vídeo mantém estado de rastreamento.
pub struct BlazePoseBackend {
    bridge: NonNull<SePoseBridge>,
}

impl BlazePoseBackend {
    pub fn new(runtime_path: &str, model_path: &str) -> Result<Self> {
        let runtime = CString::new(runtime_path)
            .map_err(|_| anyhow!("caminho do runtime MediaPipe inválido"))?;
        let model = CString::new(model_path)
            .map_err(|_| anyhow!("caminho do modelo BlazePose inválido"))?;
        let mut error = [0 as c_char; ERROR_BUFFER];
        let bridge = unsafe {
            se_pose_bridge_create(
                runtime.as_ptr(),
                model.as_ptr(),
                error.as_mut_ptr(),
                error.len(),
            )
        };
        let bridge = NonNull::new(bridge).ok_or_else(|| anyhow!(bridge_error(&error)))?;
        Ok(Self { bridge })
    }

    fn pose_from_raw(
        raw: &[f32; RAW_VALUES],
        world: &[f32; WORLD_VALUES],
        width: u32,
        height: u32,
    ) -> Result<Pose> {
        let mut keypoints = Vec::with_capacity(LANDMARK_COUNT);
        let mut confidence_sum = 0.0;
        for index in 0..LANDMARK_COUNT {
            let offset = index * FIELDS_PER_LANDMARK;
            let (x, y, visibility, presence) = (
                raw[offset],
                raw[offset + 1],
                raw[offset + 2],
                raw[offset + 3],
            );
            if !(x.is_finite() && y.is_finite() && visibility.is_finite() && presence.is_finite()) {
                bail!("MediaPipe retornou landmark não-finito no índice {index}");
            }
            // A C API entrega coordenadas normalizadas. Clamping evita coordenada marginal fora do
            // frame contaminar as métricas; a confiança segue o contrato pedido: min(vis, presence).
            let confidence = visibility.min(presence).clamp(0.0, 1.0);
            keypoints.push((
                x.clamp(0.0, 1.0) * width as f32,
                y.clamp(0.0, 1.0) * height as f32,
                confidence,
            ));
            confidence_sum += confidence;
        }
        // World landmarks 3D (metros). Só valem se o runtime os trouxe (bridge zera senão) — se tudo
        // zero, mantém None e o consumidor cai no 2D. Não-finito vira zero (não derruba a pose).
        let world_pts: Vec<(f32, f32, f32)> = (0..LANDMARK_COUNT)
            .map(|i| {
                let w = i * 3;
                let f = |v: f32| if v.is_finite() { v } else { 0.0 };
                (f(world[w]), f(world[w + 1]), f(world[w + 2]))
            })
            .collect();
        let has_world = world_pts
            .iter()
            .any(|&(x, y, z)| x != 0.0 || y != 0.0 || z != 0.0);
        Ok(Pose {
            keypoints,
            confidence: confidence_sum / LANDMARK_COUNT as f32,
            layout: &BLAZEPOSE33,
            world: if has_world { Some(world_pts) } else { None },
        })
    }
}

impl PoseBackend for BlazePoseBackend {
    fn layout(&self) -> &'static KeypointLayout {
        &BLAZEPOSE33
    }

    fn infer(&mut self, img: &RgbImage, timestamp_ms: u64) -> Result<Option<Pose>> {
        let mut raw = [0.0; RAW_VALUES];
        let mut world = [0.0f32; WORLD_VALUES];
        let mut found = 0;
        let mut error = [0 as c_char; ERROR_BUFFER];
        let status = unsafe {
            se_pose_bridge_infer(
                self.bridge.as_ptr(),
                img.as_raw().as_ptr(),
                img.width(),
                img.height(),
                timestamp_ms
                    .try_into()
                    .map_err(|_| anyhow!("timestamp fora do limite MediaPipe"))?,
                raw.as_mut_ptr(),
                world.as_mut_ptr(),
                &mut found,
                error.as_mut_ptr(),
                error.len(),
            )
        };
        if status != 0 {
            bail!("inferência BlazePose falhou: {}", bridge_error(&error));
        }
        if found == 0 {
            return Ok(None);
        }
        Self::pose_from_raw(&raw, &world, img.width(), img.height()).map(Some)
    }
}

impl Drop for BlazePoseBackend {
    fn drop(&mut self) {
        unsafe { se_pose_bridge_close(self.bridge.as_ptr()) }
    }
}

fn bridge_error(error: &[c_char; ERROR_BUFFER]) -> String {
    unsafe { CStr::from_ptr(error.as_ptr()) }
        .to_string_lossy()
        .into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn converte_normalizado_para_pixel_e_usa_minimo_de_visibilidade_e_presenca() {
        let mut raw = [0.5; RAW_VALUES];
        for point in raw.chunks_exact_mut(FIELDS_PER_LANDMARK) {
            point[2] = 0.9;
            point[3] = 0.7;
        }
        raw[..4].copy_from_slice(&[0.25, 0.75, 0.8, 0.6]);
        let pose = BlazePoseBackend::pose_from_raw(&raw, &[0.0; WORLD_VALUES], 320, 80).unwrap();
        assert_eq!(pose.layout.name, "blazepose33");
        assert_eq!(pose.keypoints[0], (80.0, 60.0, 0.6));
        assert_eq!(pose.keypoints[1], (160.0, 40.0, 0.7));
        assert!(pose.world.is_none()); // world todo-zero => None (runtime não trouxe 3D)
    }

    #[test]
    fn world_landmarks_3d_entram_quando_presentes() {
        let mut raw = [0.5; RAW_VALUES];
        let mut world = [0.0f32; WORLD_VALUES];
        world[..3].copy_from_slice(&[0.10, -0.20, 0.30]); // metros
        let pose = BlazePoseBackend::pose_from_raw(&raw, &world, 100, 100).unwrap();
        assert_eq!(pose.world.as_ref().unwrap()[0], (0.10, -0.20, 0.30));
        raw[2] = f32::NAN; // NaN na confiança ainda derruba
        assert!(BlazePoseBackend::pose_from_raw(&raw, &world, 100, 100).is_err());
    }

    #[test]
    fn recusa_resposta_nativa_com_nan() {
        let mut raw = [0.5; RAW_VALUES];
        raw[2] = f32::NAN;
        assert!(BlazePoseBackend::pose_from_raw(&raw, &[0.0; WORLD_VALUES], 10, 10).is_err());
    }
}
