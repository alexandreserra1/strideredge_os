//! CLI do motor: `stride-vision <foto.jpg|video.mp4> [saida]`
//! Foto  -> esqueleto desenhado + keypoints no terminal.
//! Vídeo -> mp4 com esqueleto em todos os frames + CADÊNCIA estimada (FFT).

use anyhow::{bail, Context, Result};
use image::RgbImage;
use serde_json::json;
use std::io::{Read, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use stride_vision::{analyze_form, contact_angle, contact_flight_ms, foot_strike, draw_angles,
                    hip_tilt_deg, joint_angle, knee_valgus_deg, median, percentile,
                    trunk_lean_deg, draw_pose, PoseBackend, PoseEngine, RtmPose26Backend};

// Confiança mínima de keypoint p/ ENTRAR nas séries de quadril/tronco. 0.4 era baixo demais:
// o quadril "borderline" (0.42-0.45) num enquadramento ruim (só pernas) saltava e poluía a
// amplitude/leg_len. 0.5 é o padrão "visível" — separa quadril real (>0.6) do chute do modelo.
const KP_CONF: f32 = 0.5;

/// Dono de um filho ffmpeg enquanto o pipeline usa seus pipes. `Child` não espera nem mata o
/// processo no `Drop`; portanto uma saída antecipada por erro de inferência poderia deixá-lo
/// executando. Este guard encerra+recolhe o filho nesse caso e exige exit status 0 no sucesso.
struct ManagedChild {
    child: Option<Child>,
    role: &'static str,
}

impl ManagedChild {
    fn new(child: Child, role: &'static str) -> Self {
        Self { child: Some(child), role }
    }

    fn take_stdout(&mut self) -> Result<ChildStdout> {
        self.child.as_mut().and_then(|child| child.stdout.take())
            .ok_or_else(|| anyhow::anyhow!("{0}: stdout indisponível", self.role))
    }

    fn take_stdin(&mut self) -> Result<ChildStdin> {
        self.child.as_mut().and_then(|child| child.stdin.take())
            .ok_or_else(|| anyhow::anyhow!("{0}: stdin indisponível", self.role))
    }

    fn wait_success(&mut self) -> Result<()> {
        let mut child = self.child.take()
            .ok_or_else(|| anyhow::anyhow!("{0}: processo já foi aguardado", self.role))?;
        let status = child.wait().with_context(|| format!("esperando {}", self.role))?;
        if status.success() {
            Ok(())
        } else {
            bail!("{} terminou com status {status}", self.role)
        }
    }
}

impl Drop for ManagedChild {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill(); // pode já ter terminado; ainda o recolhemos abaixo
            let _ = child.wait();
        }
    }
}

fn main() -> Result<()> {
    // Separa flags dos posicionais (entrada [, saída]). `--benchmark` não desenha nem reencoda:
    // mede só decode + pose, o mesmo estágio usado para comparar backends de keypoints.
    let raw: Vec<String> = std::env::args().collect();
    let (mut view, mut backend, mut benchmark, mut benchmark_output, mut pos, mut i) =
        ("lateral".to_string(), "yolo17".to_string(), false, None::<String>, Vec::<String>::new(), 1usize);
    // --no-overlay: passada SÓ-MÉTRICAS (pula desenho + reencode). É o caminho rápido do "métricas
    // primeiro": o backend roda esta passada, mostra o resultado, e enfileira o overlay depois.
    let mut no_overlay = false;
    while i < raw.len() {
        if raw[i] == "--view" {
            view = raw.get(i + 1).cloned().unwrap_or_else(|| "lateral".into());
            i += 2;
        } else if raw[i] == "--backend" {
            backend = raw.get(i + 1).cloned().unwrap_or_else(|| "yolo17".into());
            i += 2;
        } else if raw[i] == "--benchmark" {
            benchmark = true;
            i += 1;
        } else if raw[i] == "--no-overlay" {
            no_overlay = true;
            i += 1;
        } else if raw[i] == "--output" {
            benchmark_output = raw.get(i + 1).cloned();
            i += 2;
        } else {
            pos.push(raw[i].clone());
            i += 1;
        }
    }
    if pos.is_empty() {
        bail!("uso: stride-vision <foto.jpg|video.mp4> [saida] [--view lateral|frontal] [--backend yolo17|halpe26]");
    }
    let view = if view == "frontal" { "frontal" } else { "lateral" };
    let input = &pos[0];
    let mut engine: Box<dyn PoseBackend> = match backend.as_str() {
        "yolo17" => {
            let model = std::env::var("STRIDE_MODEL")
                .unwrap_or_else(|_| "models/yolo11n-pose.onnx".into());
            Box::new(PoseEngine::new(&model)?)
        }
        "halpe26" => {
            let detector = std::env::var("STRIDE_HALPE_DETECTOR")
                .context("halpe26 exige STRIDE_HALPE_DETECTOR (ONNX do detector de pessoa)")?;
            let pose = std::env::var("STRIDE_HALPE_POSE")
                .context("halpe26 exige STRIDE_HALPE_POSE (ONNX RTMPose Halpe26)")?;
            Box::new(RtmPose26Backend::new(&detector, &pose)?)
        }
        other => bail!("backend inválido '{other}': use yolo17 ou halpe26"),
    };

    if benchmark {
        let out = benchmark_output.ok_or_else(|| anyhow::anyhow!(
            "uso: stride-vision <video.mp4> --benchmark --output <relatorio.json>"))?;
        return run_benchmark(&mut *engine, input, &out);
    }

    let ext = input.rsplit('.').next().unwrap_or("").to_lowercase();
    if matches!(ext.as_str(), "jpg" | "jpeg" | "png") {
        let out = pos.get(1).cloned().unwrap_or_else(|| "pose_out.jpg".into());
        run_image(&mut *engine, input, &out)
    } else {
        let out = pos.get(1).cloned().unwrap_or_else(|| "pose_out.mp4".into());
        run_video(&mut *engine, input, &out, view, !no_overlay)
    }
}

fn run_image(engine: &mut dyn PoseBackend, input: &str, out: &str) -> Result<()> {
    let mut img = image::open(input).context("abrindo imagem")?.to_rgb8();
    let t = std::time::Instant::now();
    match engine.infer(&img)? {
        Some(pose) => {
            println!("pessoa detectada (conf {:.2}) em {:?}", pose.confidence, t.elapsed());
            for (k, &(x, y, c)) in pose.keypoints.iter().enumerate() {
                if c > 0.35 {
                    println!("  {:12} ({:5.0},{:5.0}) conf {:.2}", pose.layout.names[k], x, y, c);
                }
            }
            draw_pose(&mut img, &pose);
            draw_angles(&mut img, &pose);
            img.save(out)?;
            println!("esqueleto salvo em {out}");
        }
        None => println!("nenhuma pessoa detectada"),
    }
    Ok(())
}

/// Medição comparável entre backends: decode + inferência de pose, sem desenho, encode ou métricas.
fn run_benchmark(engine: &mut dyn PoseBackend, input: &str, out: &str) -> Result<()> {
    let (w, h, fps) = probe(input)?;
    let layout = engine.layout();
    let decoder = Command::new("ffmpeg")
        .args(["-v", "error", "-i", input, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        .stdout(Stdio::piped()).spawn().context("ffmpeg (instale com: brew install ffmpeg)")?;
    let mut dec = ManagedChild::new(decoder, "ffmpeg decoder");
    let mut src = dec.take_stdout()?;
    let mut buf = vec![0u8; (w * h * 3) as usize];
    let (mut frames, mut detected, mut foot_visible) = (0u32, 0u32, 0u32);
    let started = std::time::Instant::now();
    loop {
        if read_exact_or_eof(&mut src, &mut buf).is_err() { break }
        let img = RgbImage::from_raw(w, h, buf.clone()).unwrap();
        if let Some(pose) = engine.infer(&img)? {
            detected += 1;
            if layout.has_foot() {
                let foot_indices = [layout.big_toe_l, layout.big_toe_r, layout.small_toe_l,
                                    layout.small_toe_r, layout.heel_l, layout.heel_r];
                if foot_indices.into_iter().flatten().all(|index| pose.keypoints[index].2 >= 0.35) {
                    foot_visible += 1;
                }
            }
        }
        frames += 1;
    }
    dec.wait_success()?;
    let report = benchmark_report(input, frames, detected, foot_visible, started.elapsed().as_secs_f64(), fps);
    std::fs::write(out, serde_json::to_string_pretty(&report)?)?;
    println!("benchmark: {frames} frames em {:.1}s ({:.1} fps) | detecção {:.1}%\nrelatório: {out}",
             report["runs"][0]["wall_seconds"].as_f64().unwrap_or(0.0),
             report["runs"][0]["frames"].as_f64().unwrap_or(0.0)
                 / report["runs"][0]["wall_seconds"].as_f64().unwrap_or(1.0),
             report["runs"][0]["detection_rate_pct"].as_f64().unwrap_or(0.0));
    Ok(())
}

fn benchmark_report(input: &str, frames: u32, detected: u32, foot_visible: u32,
                    wall_seconds: f64, source_fps: f32) -> serde_json::Value {
    let detection_rate = if frames == 0 { 0.0 } else { detected as f64 / frames as f64 };
    let video = Path::new(input).file_name().and_then(|name| name.to_str()).unwrap_or(input);
    json!({
        "runs": [{
            "video": video,
            "frames": frames,
            "wall_seconds": wall_seconds,
            "source_fps": source_fps,
            "sample_stride": 1,
            "measurement_stage": "decode+pose_inference",
            "detection_rate_pct": detection_rate * 100.0,
            "foot_points_visible_frames": foot_visible,
            "foot_points_visible": foot_visible > 0,
            "reliable": detection_rate >= 0.8,
        }],
        "human_overlay_review_required": true,
    })
}

/// Vídeo via ffmpeg (pipes rawvideo): decodifica -> infere (+ desenha, quando `overlay`) -> re-encoda.
/// `view` = "lateral" (métricas sagitais) | "frontal" (queda pélvica, valgo de joelho).
/// `overlay=false` (--no-overlay): passada SÓ-MÉTRICAS — pula o encoder e o desenho por frame
/// (glow/goniômetros são pixel-pesados), devolvendo só o JSON. É o caminho rápido do "métricas
/// primeiro"; o overlay vira uma 2ª passada, enfileirada à parte pelo backend.
fn run_video(engine: &mut dyn PoseBackend, input: &str, out: &str, view: &str, overlay: bool) -> Result<()> {
    let (w, h, fps) = probe(input)?;
    let lay = engine.layout();   // índices semânticos (quadril/joelho/tornozelo...) do layout ativo
    println!("vídeo {w}x{h} @ {fps:.1}fps (vista: {view}, overlay: {overlay}) — layout {}", lay.name);

    let decoder = Command::new("ffmpeg")
        .args(["-v", "error", "-i", input, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        .stdout(Stdio::piped()).spawn().context("ffmpeg (instale com: brew install ffmpeg)")?;
    let mut dec = ManagedChild::new(decoder, "ffmpeg decoder");
    let mut src = dec.take_stdout()?;
    // Encoder só existe na passada de overlay. Sem ele não reencodamos nada — só coletamos séries.
    let (mut enc, mut dst) = if overlay {
        let encoder = Command::new("ffmpeg")
            .args(["-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                   "-s", &format!("{w}x{h}"), "-r", &format!("{fps}"), "-i", "-",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
            .stdin(Stdio::piped()).spawn()?;
        let mut e = ManagedChild::new(encoder, "ffmpeg encoder");
        let d = e.take_stdin()?;
        (Some(e), Some(d))
    } else {
        (None, None)
    };
    let mut buf = vec![0u8; (w * h * 3) as usize];
    let (mut frames, mut ankle_l, mut ankle_r) = (0u32, Vec::new(), Vec::new());
    let (mut hip_y, mut leg_lens) = (Vec::new(), Vec::new());
    // séries de ângulo por perna (E/D) + soma de confiança p/ escolher a perna visível
    let (mut knee_l, mut knee_r, mut hip_l, mut hip_r) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let (mut conf_l, mut conf_r) = (0f32, 0f32);
    let mut trunk = Vec::new();   // inclinação do tronco por frame
    // séries X (posição horizontal) p/ padrão de pisada + direção "pra frente"
    let (mut ax_l, mut ax_r, mut kx_l, mut kx_r) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let mut nose_dx = Vec::new();   // nariz − quadril-médio (sinal = direção da corrida)
    let mut pelvic_tilt = Vec::new();   // inclinação da linha do quadril por frame (plano frontal)
    let t = std::time::Instant::now();

    loop {
        if let Err(e) = read_exact_or_eof(&mut src, &mut buf) {
            if frames == 0 { bail!("nada decodificado: {e}") } else { break }
        }
        let mut img: RgbImage = RgbImage::from_raw(w, h, buf.clone()).unwrap();
        if let Some(pose) = engine.infer(&img)? {
            let kp = &pose.keypoints;
            ankle_l.push(kp[lay.ankle_l].1);
            ankle_r.push(kp[lay.ankle_r].1);
            // BUG corrigido: hip_y e leg_len entravam SEM guarda de confiança (diferente de
            // trunk/pelvic abaixo). Keypoint de baixa confiança tem coordenada-lixo -> quadril
            // "saltava" (amplitude 681% da perna) e leg_len oscilava -> FALSO "não-lateral".
            // Agora só entra com o quadril confiável; leg_len usa a perna VISÍVEL (na lateral a
            // de trás é ocluída, baixa conf.).
            if kp[lay.hip_l].2 > KP_CONF && kp[lay.hip_r].2 > KP_CONF {
                hip_y.push((kp[lay.hip_l].1 + kp[lay.hip_r].1) / 2.0);      // centro do quadril
            }
            let leg = |hip: (f32, f32, f32), ank: (f32, f32, f32)|
                ((hip.0 - ank.0).powi(2) + (hip.1 - ank.1).powi(2)).sqrt();
            if kp[lay.hip_l].2 > KP_CONF && kp[lay.ankle_l].2 > KP_CONF {
                leg_lens.push(leg(kp[lay.hip_l], kp[lay.ankle_l]));           // perna esquerda
            } else if kp[lay.hip_r].2 > KP_CONF && kp[lay.ankle_r].2 > KP_CONF {
                leg_lens.push(leg(kp[lay.hip_r], kp[lay.ankle_r]));           // perna direita (esquerda ocluída)
            }
            // ângulos articulares por perna (joelho: quadril-joelho-tornozelo; quadril: ombro-quadril-joelho)
            knee_l.push(joint_angle(kp[lay.hip_l], kp[lay.knee_l], kp[lay.ankle_l]));
            knee_r.push(joint_angle(kp[lay.hip_r], kp[lay.knee_r], kp[lay.ankle_r]));
            hip_l.push(joint_angle(kp[lay.shoulder_l], kp[lay.hip_l], kp[lay.knee_l]));
            hip_r.push(joint_angle(kp[lay.shoulder_r], kp[lay.hip_r], kp[lay.knee_r]));
            conf_l += kp[lay.hip_l].2.min(kp[lay.knee_l].2).min(kp[lay.ankle_l].2);
            conf_r += kp[lay.hip_r].2.min(kp[lay.knee_r].2).min(kp[lay.ankle_r].2);
            ax_l.push(kp[lay.ankle_l].0); ax_r.push(kp[lay.ankle_r].0);
            kx_l.push(kp[lay.knee_l].0); kx_r.push(kp[lay.knee_r].0);
            nose_dx.push(kp[lay.nose].0 - (kp[lay.hip_l].0 + kp[lay.hip_r].0) / 2.0);
            // inclinação do tronco: ombro-médio vs quadril-médio (só com tronco confiável)
            if kp[lay.shoulder_l].2 > KP_CONF && kp[lay.shoulder_r].2 > KP_CONF && kp[lay.hip_l].2 > KP_CONF && kp[lay.hip_r].2 > KP_CONF {
                let sh = ((kp[lay.shoulder_l].0 + kp[lay.shoulder_r].0) / 2.0, (kp[lay.shoulder_l].1 + kp[lay.shoulder_r].1) / 2.0);
                let hp = ((kp[lay.hip_l].0 + kp[lay.hip_r].0) / 2.0, (kp[lay.hip_l].1 + kp[lay.hip_r].1) / 2.0);
                trunk.push(trunk_lean_deg(sh, hp));
            }
            // queda pélvica (plano frontal): inclinação da linha do quadril quando ela é confiável
            if kp[lay.hip_l].2 > KP_CONF && kp[lay.hip_r].2 > KP_CONF {
                pelvic_tilt.push(hip_tilt_deg(kp[lay.hip_l], kp[lay.hip_r]));
            }
            if overlay {
                draw_pose(&mut img, &pose);
                if view == "lateral" { draw_angles(&mut img, &pose); }   // goniômetros sagitais só na lateral
            }
        }
        if let Some(d) = dst.as_mut() { d.write_all(img.as_raw())?; }   // só reencoda na passada de overlay
        frames += 1;
    }
    drop(dst);   // fecha o stdin do encoder (se houver) -> ele finaliza o mp4
    dec.wait_success()?;
    if let Some(e) = enc.as_mut() { e.wait_success()?; }
    let el = t.elapsed().as_secs_f32();
    println!("{frames} frames em {el:.1}s ({:.1} fps de processamento)", frames as f32 / el);

    // métricas consolidadas -> JSON ao lado do vídeo (o backend lê daqui)
    leg_lens.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let leg_len = leg_lens.get(leg_lens.len() / 2).copied().unwrap_or(0.0);
    // as DUAS pernas consistentemente visíveis? (numa lateral uma é ocluída -> baixa conf.)
    let both_legs_ok = frames > 0
        && conf_l / frames as f32 > 0.35 && conf_r / frames as f32 > 0.35;
    let mut metrics = analyze_form(&ankle_l, &ankle_r, &hip_y, leg_len, fps, frames as usize,
                                   view, both_legs_ok);

    if view == "frontal" {
        // plano frontal: queda pélvica (pico da inclinação da bacia) + valgo (pior perna)
        metrics.pelvic_drop_deg = percentile(&pelvic_tilt, 0.90).map(|v| (v * 10.0).round() / 10.0);
        let valgus = knee_valgus_deg(&knee_l).into_iter()
            .chain(knee_valgus_deg(&knee_r))
            .fold(None, |acc: Option<f32>, v| Some(acc.map_or(v, |a| a.max(v))));
        metrics.knee_valgus_deg = valgus;
    } else {
        // vista lateral: ângulo no APOIO (perna mais visível), contato/voo, pisada, tronco
        let right = conf_r >= conf_l;
        let (knee_ser, hip_ser, ankle_ser) = if right {
            (&knee_r, &hip_r, &ankle_r)
        } else {
            (&knee_l, &hip_l, &ankle_l)
        };
        metrics.knee_contact_deg = contact_angle(knee_ser, ankle_ser);
        metrics.hip_contact_deg = contact_angle(hip_ser, ankle_ser);
        metrics.trunk_lean_deg = median(&trunk).map(|v| (v * 10.0).round() / 10.0);
        let (gct, flight) = contact_flight_ms(&ankle_l, &ankle_r, fps);
        metrics.ground_contact_ms = gct;
        metrics.flight_ms = flight;
        let facing = median(&nose_dx).unwrap_or(0.0);
        let (ax, kx) = if right { (&ax_r, &kx_r) } else { (&ax_l, &kx_l) };
        metrics.foot_strike = foot_strike(ax, ankle_ser, kx, facing, leg_len).map(|s| s.to_string());
    }
    let mpath = format!("{}.metrics.json", out.trim_end_matches(".mp4"));
    std::fs::write(&mpath, serde_json::to_string_pretty(&metrics)?)?;

    if view == "frontal" {
        println!("FRONTAL | queda pélvica: {:?}° | valgo joelho: {:?}° | confiável: {}",
                 metrics.pelvic_drop_deg, metrics.knee_valgus_deg, metrics.reliable);
    } else {
        match metrics.cadence_spm {
            Some(c) => println!("CADÊNCIA: {c:.0} spm | assimetria: {:?}% | osc. vertical: {:?}%",
                                metrics.asymmetry_pct, metrics.vertical_oscillation_pct),
            None => println!("cadência: série curta demais (filme >5s)"),
        }
    }
    if overlay { println!("vídeo: {out}"); }
    println!("métricas: {mpath}");
    Ok(())
}

fn read_exact_or_eof(r: &mut impl Read, buf: &mut [u8]) -> std::io::Result<()> {
    let mut filled = 0;
    while filled < buf.len() {
        let n = r.read(&mut buf[filled..])?;
        if n == 0 {
            return Err(std::io::Error::new(std::io::ErrorKind::UnexpectedEof, "eof"));
        }
        filled += n;
    }
    Ok(())
}

fn probe(input: &str) -> Result<(u32, u32, f32)> {
    let out = Command::new("ffprobe")
        .args(["-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height,r_frame_rate:stream_side_data=rotation", "-of", "csv=p=0", input])
        .output().context("ffprobe")?;
    let s = String::from_utf8_lossy(&out.stdout);
    let parts: Vec<&str> = s.trim().split(',').collect();
    if parts.len() < 3 {
        bail!("ffprobe não retornou dimensões e FPS do vídeo");
    }
    let rate: Vec<f32> = parts[2].split('/').map(|x| x.parse().unwrap_or(1.0)).collect();
    let rotation = parts.get(3).and_then(|value| value.parse::<i32>().ok()).unwrap_or(0);
    let (width, height) = oriented_dimensions(parts[0].parse()?, parts[1].parse()?, rotation);
    Ok((width, height, rate[0] / rate.get(1).copied().unwrap_or(1.0)))
}

/// O ffmpeg auto-rota vídeos de celular; o buffer raw precisa usar a geometria já orientada.
fn oriented_dimensions(width: u32, height: u32, rotation: i32) -> (u32, u32) {
    if rotation.rem_euclid(180) == 90 { (height, width) } else { (width, height) }
}

#[cfg(test)]
mod cli_tests {
    use super::{oriented_dimensions, ManagedChild};
    use std::process::Command;

    #[test]
    fn dimensoes_trocam_nas_rotacoes_de_celular() {
        assert_eq!(oriented_dimensions(1024, 576, -90), (576, 1024));
        assert_eq!(oriented_dimensions(1024, 576, 90), (576, 1024));
        assert_eq!(oriented_dimensions(1024, 576, 0), (1024, 576));
        assert_eq!(oriented_dimensions(1024, 576, 180), (1024, 576));
    }

    #[test]
    fn benchmark_tem_estagio_e_amostragem_explicitos() {
        let report = super::benchmark_report("/tmp/corrida.mp4", 100, 90, 80, 4.0, 25.0);
        let run = &report["runs"][0];
        assert_eq!(run["video"], "corrida.mp4");
        assert_eq!(run["sample_stride"], 1);
        assert_eq!(run["measurement_stage"], "decode+pose_inference");
        assert_eq!(run["reliable"], true);
        assert_eq!(run["foot_points_visible_frames"], 80);
    }

    #[test]
    fn processo_filhos_com_erro_nao_sao_sucesso() {
        let child = Command::new("sh").args(["-c", "exit 7"]).spawn().unwrap();
        let mut managed = ManagedChild::new(child, "ffmpeg de teste");
        assert!(managed.wait_success().is_err());
    }
}
