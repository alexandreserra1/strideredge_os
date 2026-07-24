//! draw.rs — overlay: esqueleto "neon" + HUD de goniômetros (estilo Ochy).
//!
//! Superfície PURA de desenho: recebe `(&mut RgbImage, &Pose)` e não depende das métricas. É o que
//! permite, no futuro, separar o overlay num job secundário sem tocar em `analyze_form`.

use image::{Rgb, RgbImage};
use imageproc::drawing::{draw_filled_circle_mut, draw_line_segment_mut};
use std::f32::consts::PI;

use crate::pose::Pose;

/// Mistura uma cor com o pixel já presente na imagem (blend alfa manual —
/// imageproc não faz blending real, só substitui o pixel).
fn blend_px(img: &mut RgbImage, x: i32, y: i32, color: Rgb<u8>, alpha: f32) {
    if x < 0 || y < 0 || x as u32 >= img.width() || y as u32 >= img.height() {
        return;
    }
    let p = img.get_pixel_mut(x as u32, y as u32);
    for c in 0..3 {
        p.0[c] = (p.0[c] as f32 * (1.0 - alpha) + color.0[c] as f32 * alpha) as u8;
    }
}

/// Linha com halo (glow): um traço largo e translúcido por baixo + um núcleo fino e
/// saturado por cima — efeito "neon" (referência visual: overlays de motion-capture).
fn glow_line(img: &mut RgbImage, a: (f32, f32), b: (f32, f32), color: Rgb<u8>, core_w: i32) {
    let steps = ((a.0 - b.0).hypot(a.1 - b.1) as i32).max(1);
    for s in 0..=steps {
        let t = s as f32 / steps as f32;
        let (x, y) = (a.0 + (b.0 - a.0) * t, a.1 + (b.1 - a.1) * t);
        // halo: raio maior, alfa baixo, some gradualmente
        for r in 1..=core_w * 2 {
            let alpha = 0.10 * (1.0 - r as f32 / (core_w as f32 * 2.0));
            if alpha <= 0.0 {
                continue;
            }
            for &(dx, dy) in &[(-r, 0), (r, 0), (0, -r), (0, r)] {
                blend_px(img, x as i32 + dx, y as i32 + dy, color, alpha);
            }
        }
    }
    draw_line_segment_mut(img, a, b, color);
    if core_w > 1 {
        draw_line_segment_mut(img, (a.0, a.1 - 1.0), (b.0, b.1 - 1.0), color);
        draw_line_segment_mut(img, (a.0, a.1 + 1.0), (b.0, b.1 + 1.0), color);
    }
}

/// Desenha o esqueleto sobre o frame — estética "neon tech" (halo + núcleo brilhante +
/// articulações com anel), inspirada em overlays de motion-capture esportivo.
pub fn draw_pose(img: &mut RgbImage, pose: &Pose) {
    let bone = Rgb([124u8, 108, 255]); // brand roxo, um tom mais vivo p/ contraste em vídeo
    let joint = Rgb([52u8, 235, 175]); // verde neon
    let joint_core = Rgb([255u8, 255, 255]); // núcleo branco — leitura "sensor ativo"
    let core_w = (img.width().max(img.height()) / 280).max(2) as i32;

    for &(a, b) in pose.layout.skeleton.iter() {
        let (ka, kb) = (pose.keypoints[a], pose.keypoints[b]);
        if ka.2 < 0.35 || kb.2 < 0.35 {
            continue;
        }
        glow_line(img, (ka.0, ka.1), (kb.0, kb.1), bone, core_w);
    }
    for (idx, &(x, y, c)) in pose.keypoints.iter().enumerate() {
        if c < 0.35 || pose.layout.face_skip.contains(&idx) {
            continue;
        }
        let (xi, yi) = (x as i32, y as i32);
        // halo suave por trás da articulação
        for r in (core_w + 2..core_w * 4).rev() {
            let alpha = 0.06 * (1.0 - (r - core_w) as f32 / (core_w as f32 * 3.0));
            if alpha <= 0.0 {
                continue;
            }
            draw_filled_circle_mut(
                img,
                (xi, yi),
                r,
                blend_circle_color(img, xi, yi, joint, alpha),
            );
        }
        draw_filled_circle_mut(img, (xi, yi), core_w * 2, joint);
        draw_filled_circle_mut(img, (xi, yi), (core_w as f32 * 0.8) as i32, joint_core);
    }
}

/// Aproximação de cor pra blend em `draw_filled_circle_mut` (que substitui, não mistura):
/// devolve a cor do halo já misturada com o fundo atual naquele ponto.
fn blend_circle_color(img: &RgbImage, x: i32, y: i32, color: Rgb<u8>, alpha: f32) -> Rgb<u8> {
    if x < 0 || y < 0 || x as u32 >= img.width() || y as u32 >= img.height() {
        return color;
    }
    let bg = img.get_pixel(x as u32, y as u32);
    Rgb([
        (bg.0[0] as f32 * (1.0 - alpha) + color.0[0] as f32 * alpha) as u8,
        (bg.0[1] as f32 * (1.0 - alpha) + color.0[1] as f32 * alpha) as u8,
        (bg.0[2] as f32 * (1.0 - alpha) + color.0[2] as f32 * alpha) as u8,
    ])
}

// ---------- HUD de ângulos articulares (o "técnico" tipo Ochy) ----------
// Sobre os keypoints desenhamos GONIÔMETROS: dois raios ao longo dos membros + o arco entre
// eles, em cores distintas (joelho=ciano, quadril=âmbar). Sem número piscando no frame — o
// valor que importa é o ângulo NO APOIO do pé, medido na série inteira e mostrado na UI.

/// Ângulo interno (graus) no vértice `b`, formado por a–b–c. Os pontos são (x,y,conf) mas só x,y
/// entram — é o ângulo 2D projetado na imagem.
pub fn joint_angle(a: (f32, f32, f32), b: (f32, f32, f32), c: (f32, f32, f32)) -> f32 {
    let (v1x, v1y) = (a.0 - b.0, a.1 - b.1);
    let (v2x, v2y) = (c.0 - b.0, c.1 - b.1);
    let (m1, m2) = (
        (v1x * v1x + v1y * v1y).sqrt(),
        (v2x * v2x + v2y * v2y).sqrt(),
    );
    if m1 == 0.0 || m2 == 0.0 {
        return 0.0;
    }
    ((v1x * v2x + v1y * v2y) / (m1 * m2))
        .clamp(-1.0, 1.0)
        .acos()
        .to_degrees()
}

/// Ângulo interno 3D (graus) no vértice `b`, de a–b–c em (x,y,z) — a estimativa de world landmarks
/// do BlazePose. Evita a projeção estritamente 2D quando o membro sai do plano da câmera, mas NÃO é
/// ground truth: acurácia só é estabelecida contra mocap/força em avaliação pareada.
pub fn joint_angle_3d(a: (f32, f32, f32), b: (f32, f32, f32), c: (f32, f32, f32)) -> f32 {
    let v1 = (a.0 - b.0, a.1 - b.1, a.2 - b.2);
    let v2 = (c.0 - b.0, c.1 - b.1, c.2 - b.2);
    let m1 = (v1.0 * v1.0 + v1.1 * v1.1 + v1.2 * v1.2).sqrt();
    let m2 = (v2.0 * v2.0 + v2.1 * v2.1 + v2.2 * v2.2).sqrt();
    if m1 == 0.0 || m2 == 0.0 {
        return 0.0;
    }
    ((v1.0 * v2.0 + v1.1 * v2.1 + v1.2 * v2.2) / (m1 * m2))
        .clamp(-1.0, 1.0)
        .acos()
        .to_degrees()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn joint_angle_3d_pega_o_que_o_2d_perde_fora_do_plano() {
        // perna reta em z (fora do plano da imagem): 2D veria 0-len e daria 0; 3D dá 90°
        assert!(
            (joint_angle_3d((0.0, -1.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) - 90.0).abs()
                < 0.01
        );
        // reta: 180° nos dois
        assert!(
            (joint_angle_3d((0.0, -1.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)) - 180.0).abs()
                < 0.01
        );
    }
}

fn thick_line(img: &mut RgbImage, a: (f32, f32), b: (f32, f32), color: Rgb<u8>, w: i32) {
    for off in -(w / 2)..=(w / 2) {
        draw_line_segment_mut(img, (a.0 + off as f32, a.1), (b.0 + off as f32, b.1), color);
        draw_line_segment_mut(img, (a.0, a.1 + off as f32), (b.0, b.1 + off as f32), color);
    }
}

/// Goniômetro num vértice articular: raios ao longo dos membros + arco (sem número).
fn draw_angle_gauge(
    img: &mut RgbImage,
    a: (f32, f32, f32),
    b: (f32, f32, f32),
    c: (f32, f32, f32),
    color: Rgb<u8>,
    r: f32,
) {
    if a.2 < 0.4 || b.2 < 0.4 || c.2 < 0.4 {
        return;
    }
    let (bx, by) = (b.0, b.1);
    let a1 = (a.1 - b.1).atan2(a.0 - b.0);
    let a2 = (c.1 - b.1).atan2(c.0 - b.0);
    let mut d = a2 - a1;
    while d > PI {
        d -= 2.0 * PI
    }
    while d < -PI {
        d += 2.0 * PI
    }
    thick_line(
        img,
        (bx, by),
        (bx + r * a1.cos(), by + r * a1.sin()),
        color,
        2,
    );
    thick_line(
        img,
        (bx, by),
        (bx + r * a2.cos(), by + r * a2.sin()),
        color,
        2,
    );
    let steps = 44;
    for i in 0..steps {
        let t0 = a1 + d * (i as f32 / steps as f32);
        let t1 = a1 + d * ((i + 1) as f32 / steps as f32);
        thick_line(
            img,
            (bx + r * t0.cos(), by + r * t0.sin()),
            (bx + r * t1.cos(), by + r * t1.sin()),
            color,
            2,
        );
    }
}

/// Anota os ângulos de corrida (joelho + quadril) da perna mais visível.
/// Joelho em ciano, quadril em âmbar — a legenda vive na UI (texto é de graça em HTML).
pub fn draw_angles(img: &mut RgbImage, pose: &Pose) {
    let kp = &pose.keypoints;
    let l = pose.layout;
    let knee_c = Rgb([120u8, 232, 255]); // ciano
    let hip_c = Rgb([255u8, 178, 89]); // âmbar
    let conf = |h: usize, k: usize, a: usize| kp[h].2.min(kp[k].2).min(kp[a].2);
    // perna mais confiável (numa filmagem de lado, a de frente pra câmera)
    let (hip, knee, ank, sho) =
        if conf(l.hip_r, l.knee_r, l.ankle_r) >= conf(l.hip_l, l.knee_l, l.ankle_l) {
            (l.hip_r, l.knee_r, l.ankle_r, l.shoulder_r)
        } else {
            (l.hip_l, l.knee_l, l.ankle_l, l.shoulder_l)
        };
    let seg =
        |i: usize, j: usize| ((kp[i].0 - kp[j].0).powi(2) + (kp[i].1 - kp[j].1).powi(2)).sqrt();
    let r_knee = (0.32 * seg(knee, ank)).clamp(15.0, 70.0);
    let r_hip = (0.30 * seg(hip, knee)).clamp(15.0, 70.0);
    draw_angle_gauge(img, kp[hip], kp[knee], kp[ank], knee_c, r_knee); // ângulo do joelho
    draw_angle_gauge(img, kp[sho], kp[hip], kp[knee], hip_c, r_hip); // flexão do quadril

    // linha de PRUMO (vertical de referência) no centro do quadril: mostra a inclinação
    // do tronco de bate-pronto, como o Ochy. Tracejada e translúcida pra não poluir.
    if kp[l.shoulder_l].2 > 0.4
        && kp[l.shoulder_r].2 > 0.4
        && kp[l.hip_l].2 > 0.4
        && kp[l.hip_r].2 > 0.4
    {
        let hx = (kp[l.hip_l].0 + kp[l.hip_r].0) / 2.0;
        let hy = (kp[l.hip_l].1 + kp[l.hip_r].1) / 2.0;
        let sy = (kp[l.shoulder_l].1 + kp[l.shoulder_r].1) / 2.0;
        let len = (hy - sy).abs() * 1.1;
        let mut y = hy;
        while y > hy - len {
            blend_px(img, hx as i32, y as i32, Rgb([235, 235, 245]), 0.5);
            blend_px(img, hx as i32 + 1, y as i32, Rgb([235, 235, 245]), 0.5);
            y -= if ((hy - y) as i32 / 7) % 2 == 0 {
                1.0
            } else {
                6.0
            }; // traço-espaço
        }
    }
}
