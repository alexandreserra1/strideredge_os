//! CLI do motor: `stride-vision <foto.jpg|video.mp4> [saida]`
//! Foto  -> esqueleto desenhado + keypoints no terminal.
//! Vídeo -> mp4 com esqueleto em todos os frames + CADÊNCIA estimada (FFT).

use anyhow::{bail, Context, Result};
use image::RgbImage;
use serde_json::json;
use std::io::{Read, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use stride_vision::{
    analyze_form, contact_angle, contact_flight_ms, draw_angles, draw_pose, foot_ground_y,
    foot_strike, hip_tilt_deg, joint_angle, knee_valgus_deg, median, percentile,
    timing_consistent_with_cadence, trunk_lean_deg, BlazePoseBackend, Pose, PoseBackend,
    PoseEngine, RtmPose26Backend,
};

// Confiança mínima de keypoint p/ ENTRAR nas séries de quadril/tronco. 0.4 era baixo demais:
// o quadril "borderline" (0.42-0.45) num enquadramento ruim (só pernas) saltava e poluía a
// amplitude/leg_len. 0.5 é o padrão "visível" — separa quadril real (>0.6) do chute do modelo.
const KP_CONF: f32 = 0.5;

/// Timestamp estável para backends de vídeo: a mesma sequência decodificada sempre recebe os
/// mesmos milissegundos. `probe` já valida FPS; o fallback protege CLI/testes de divisão por zero.
fn frame_timestamp_ms(frame: u32, fps: f32) -> u64 {
    if fps.is_finite() && fps > 0.0 {
        ((frame as f64 * 1_000.0) / fps as f64).round() as u64
    } else {
        frame as u64
    }
}

/// Persiste o dump opt-in de calibração. O caminho vem da configuração local do operador; criar
/// apenas seu diretório-pai torna o CLI utilizável em `/tmp/.../dumps/` sem afetar o vídeo ou os
/// caminhos de produção. Um path sem pai (ex.: `dump.json`) continua válido.
fn write_frame_dump(dump_path: &str, doc: &serde_json::Value) -> Result<()> {
    let path = Path::new(dump_path);
    if let Some(parent) = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("criando diretório do dump {}", parent.display()))?;
    }
    std::fs::write(path, serde_json::to_string(doc)?)
        .with_context(|| format!("gravando dump de calibração {}", path.display()))?;
    Ok(())
}

/// Um registro por FRAME DECODIFICADO pro dump de calibração: índice, timestamp, se houve pose,
/// confiança e os landmarks por NOME SEMÂNTICO (x, y, conf). Pontos de pé só quando o layout os
/// traz. Backend-independente: o arnês recomputa qualquer ângulo no MESMO frame pros dois motores.
fn frame_record(pose: &Option<Pose>, i: u32, t_ms: u64) -> serde_json::Value {
    let Some(p) = pose else {
        return serde_json::json!({ "i": i, "t_ms": t_ms, "present": false });
    };
    let (lay, kp) = (p.layout, &p.keypoints);
    let mut kpm = serde_json::Map::new();
    let named = [
        ("nose", lay.nose),
        ("shoulder_l", lay.shoulder_l),
        ("shoulder_r", lay.shoulder_r),
        ("hip_l", lay.hip_l),
        ("hip_r", lay.hip_r),
        ("knee_l", lay.knee_l),
        ("knee_r", lay.knee_r),
        ("ankle_l", lay.ankle_l),
        ("ankle_r", lay.ankle_r),
    ];
    for (name, idx) in named {
        let (x, y, c) = kp[idx];
        kpm.insert(name.to_string(), serde_json::json!([x, y, c]));
    }
    for (name, opt) in [
        ("heel_l", lay.heel_l),
        ("heel_r", lay.heel_r),
        ("big_toe_l", lay.big_toe_l),
        ("big_toe_r", lay.big_toe_r),
    ] {
        if let Some(idx) = opt {
            let (x, y, c) = kp[idx];
            kpm.insert(name.to_string(), serde_json::json!([x, y, c]));
        }
    }
    let mut record = serde_json::Map::new();
    record.insert("i".into(), serde_json::json!(i));
    record.insert("t_ms".into(), serde_json::json!(t_ms));
    record.insert("present".into(), serde_json::json!(true));
    record.insert("conf".into(), serde_json::json!(p.confidence));
    record.insert("kp".into(), serde_json::Value::Object(kpm));
    // World landmarks 3D (metros) por nome — só o BlazePose traz. São exclusivamente
    // diagnóstico/calibração opt-in; as métricas de produto ficam no espaço image_2d registrado.
    if let Some(w) = &p.world {
        let mut wm = serde_json::Map::new();
        for (name, idx) in named {
            let (x, y, z) = w[idx];
            wm.insert(name.to_string(), serde_json::json!([x, y, z]));
        }
        record.insert("kpw".into(), serde_json::Value::Object(wm));
    }
    serde_json::Value::Object(record)
}

/// Dono de um filho ffmpeg enquanto o pipeline usa seus pipes. `Child` não espera nem mata o
/// processo no `Drop`; portanto uma saída antecipada por erro de inferência poderia deixá-lo
/// executando. Este guard encerra+recolhe o filho nesse caso e exige exit status 0 no sucesso.
struct ManagedChild {
    child: Option<Child>,
    role: &'static str,
}

impl ManagedChild {
    fn new(child: Child, role: &'static str) -> Self {
        Self {
            child: Some(child),
            role,
        }
    }

    fn take_stdout(&mut self) -> Result<ChildStdout> {
        self.child
            .as_mut()
            .and_then(|child| child.stdout.take())
            .ok_or_else(|| anyhow::anyhow!("{0}: stdout indisponível", self.role))
    }

    fn take_stdin(&mut self) -> Result<ChildStdin> {
        self.child
            .as_mut()
            .and_then(|child| child.stdin.take())
            .ok_or_else(|| anyhow::anyhow!("{0}: stdin indisponível", self.role))
    }

    fn wait_success(&mut self) -> Result<()> {
        let mut child = self
            .child
            .take()
            .ok_or_else(|| anyhow::anyhow!("{0}: processo já foi aguardado", self.role))?;
        let status = child
            .wait()
            .with_context(|| format!("esperando {}", self.role))?;
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
    let (mut view, mut backend, mut benchmark, mut benchmark_output, mut pos, mut i) = (
        "lateral".to_string(),
        "yolo17".to_string(),
        false,
        None::<String>,
        Vec::<String>::new(),
        1usize,
    );
    // --no-overlay: passada SÓ-MÉTRICAS (pula desenho + reencode). É o caminho rápido do "métricas
    // primeiro": o backend roda esta passada, mostra o resultado, e enfileira o overlay depois.
    let mut no_overlay = false;
    // --sample-stride N: infere 1 a cada N frames (amostragem temporal). É o A4: metade do trabalho
    // do modelo a 15fps se a cadência/contato/ângulos aguentarem. Só vale p/ métricas/benchmark —
    // overlay e dump de calibração EXIGEM todos os frames (senão vídeo/alinhamento quebram).
    let mut sample_stride = 1usize;
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
        } else if raw[i] == "--sample-stride" {
            sample_stride = raw
                .get(i + 1)
                .and_then(|v| v.parse::<usize>().ok())
                .filter(|&n| n >= 1)
                .context("--sample-stride exige um inteiro >= 1")?;
            i += 2;
        } else if raw[i] == "--output" {
            benchmark_output = raw.get(i + 1).cloned();
            i += 2;
        } else {
            pos.push(raw[i].clone());
            i += 1;
        }
    }
    if pos.is_empty() {
        bail!("uso: stride-vision <foto.jpg|video.mp4> [saida] [--view lateral|frontal] [--backend yolo17|halpe26|blazepose33]");
    }
    let view = if view == "frontal" {
        "frontal"
    } else {
        "lateral"
    };
    let input = &pos[0];
    let mut engine: Box<dyn PoseBackend> = match backend.as_str() {
        "yolo17" => {
            let model =
                std::env::var("STRIDE_MODEL").unwrap_or_else(|_| "models/yolo11n-pose.onnx".into());
            Box::new(PoseEngine::new(&model)?)
        }
        "halpe26" => {
            let detector = std::env::var("STRIDE_HALPE_DETECTOR")
                .context("halpe26 exige STRIDE_HALPE_DETECTOR (ONNX do detector de pessoa)")?;
            let pose = std::env::var("STRIDE_HALPE_POSE")
                .context("halpe26 exige STRIDE_HALPE_POSE (ONNX RTMPose Halpe26)")?;
            Box::new(RtmPose26Backend::new(&detector, &pose)?)
        }
        "blazepose33" => {
            let runtime = std::env::var("STRIDE_MEDIAPIPE_LIB")
                .context("blazepose33 exige STRIDE_MEDIAPIPE_LIB (runtime C oficial MediaPipe)")?;
            let model = std::env::var("STRIDE_BLAZEPOSE_MODEL")
                .context("blazepose33 exige STRIDE_BLAZEPOSE_MODEL (bundle .task oficial)")?;
            Box::new(BlazePoseBackend::new(&runtime, &model)?)
        }
        other => bail!("backend inválido '{other}': use yolo17, halpe26 ou blazepose33"),
    };

    if benchmark {
        let out = benchmark_output.ok_or_else(|| {
            anyhow::anyhow!("uso: stride-vision <video.mp4> --benchmark --output <relatorio.json>")
        })?;
        return run_benchmark(&mut *engine, input, &out, sample_stride);
    }

    let ext = input.rsplit('.').next().unwrap_or("").to_lowercase();
    if matches!(ext.as_str(), "jpg" | "jpeg" | "png") {
        run_image(&mut *engine, input, &pos.get(1).cloned().unwrap_or_else(|| "pose_out.jpg".into()))
    } else {
        let out = pos.get(1).cloned().unwrap_or_else(|| "pose_out.mp4".into());
        run_video(&mut *engine, input, &out, view, !no_overlay, sample_stride)
    }
}

fn run_image(engine: &mut dyn PoseBackend, input: &str, out: &str) -> Result<()> {
    let mut img = image::open(input).context("abrindo imagem")?.to_rgb8();
    let t = std::time::Instant::now();
    match engine.infer(&img, 0)? {
        Some(pose) => {
            println!(
                "pessoa detectada (conf {:.2}) em {:?}",
                pose.confidence,
                t.elapsed()
            );
            for (k, &(x, y, c)) in pose.keypoints.iter().enumerate() {
                if c > 0.35 {
                    println!(
                        "  {:12} ({:5.0},{:5.0}) conf {:.2}",
                        pose.layout.names[k], x, y, c
                    );
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
fn run_benchmark(
    engine: &mut dyn PoseBackend,
    input: &str,
    out: &str,
    sample_stride: usize,
) -> Result<()> {
    let (w, h, fps) = probe(input)?;
    let layout = engine.layout();
    let decoder = Command::new("ffmpeg")
        .args([
            "-v", "error", "-i", input, "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ])
        .stdout(Stdio::piped())
        .spawn()
        .context("ffmpeg (instale com: brew install ffmpeg)")?;
    let mut dec = ManagedChild::new(decoder, "ffmpeg decoder");
    let mut src = dec.take_stdout()?;
    let mut buf = vec![0u8; (w * h * 3) as usize];
    // `decoded` = frames lidos do ffmpeg; `sampled` = os que passaram no crivo do stride (inferidos).
    // A taxa de detecção usa `sampled` como denominador (é o trabalho que o modelo realmente fez).
    let (mut decoded, mut sampled, mut detected, mut foot_visible) = (0u32, 0u32, 0u32, 0u32);
    let started = std::time::Instant::now();
    loop {
        if read_exact_or_eof(&mut src, &mut buf).is_err() {
            break;
        }
        if decoded as usize % sample_stride != 0 {
            decoded += 1;
            continue;
        }
        let img = RgbImage::from_raw(w, h, buf.clone()).unwrap();
        let ts = frame_timestamp_ms(decoded, fps);
        sampled += 1;
        decoded += 1;
        if let Some(pose) = engine.infer(&img, ts)? {
            detected += 1;
            if layout.has_foot() {
                let foot_indices = [
                    layout.big_toe_l,
                    layout.big_toe_r,
                    layout.small_toe_l,
                    layout.small_toe_r,
                    layout.heel_l,
                    layout.heel_r,
                ];
                if foot_indices
                    .into_iter()
                    .flatten()
                    .all(|index| pose.keypoints[index].2 >= 0.35)
                {
                    foot_visible += 1;
                }
            }
        }
    }
    dec.wait_success()?;
    let report = benchmark_report(
        input,
        sampled,
        detected,
        foot_visible,
        started.elapsed().as_secs_f64(),
        fps,
        sample_stride,
    );
    std::fs::write(out, serde_json::to_string_pretty(&report)?)?;
    println!(
        "benchmark: {sampled} frames em {:.1}s ({:.1} fps) | detecção {:.1}%\nrelatório: {out}",
        report["runs"][0]["wall_seconds"].as_f64().unwrap_or(0.0),
        report["runs"][0]["frames"].as_f64().unwrap_or(0.0)
            / report["runs"][0]["wall_seconds"].as_f64().unwrap_or(1.0),
        report["runs"][0]["detection_rate_pct"]
            .as_f64()
            .unwrap_or(0.0)
    );
    Ok(())
}

fn benchmark_report(
    input: &str,
    frames: u32,
    detected: u32,
    foot_visible: u32,
    wall_seconds: f64,
    source_fps: f32,
    sample_stride: usize,
) -> serde_json::Value {
    let detection_rate = if frames == 0 {
        0.0
    } else {
        detected as f64 / frames as f64
    };
    let video = Path::new(input)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(input);
    json!({
        "runs": [{
            "video": video,
            "frames": frames,
            "wall_seconds": wall_seconds,
            "source_fps": source_fps,
            "effective_fps": source_fps / sample_stride as f32,
            "sample_stride": sample_stride,
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
fn run_video(
    engine: &mut dyn PoseBackend,
    input: &str,
    out: &str,
    view: &str,
    overlay: bool,
    sample_stride: usize,
) -> Result<()> {
    let (w, h, fps) = probe(input)?;
    // Overlay reencoda no fps original -> precisa de TODO frame. Dump de calibração alinha o índice
    // do frame ao ground-truth -> subamostrar embaralharia o alinhamento. Nos dois casos, stride=1.
    if sample_stride > 1 && overlay {
        bail!("--sample-stride > 1 é incompatível com overlay (use --no-overlay)");
    }
    if sample_stride > 1 && std::env::var("STRIDE_DUMP_SERIES").is_ok() {
        bail!("--sample-stride > 1 é incompatível com STRIDE_DUMP_SERIES (alinhamento de calibração)");
    }
    // fps EFETIVO: ao inferir 1 a cada N frames, a série de métricas fica em fps/N. A cadência (FFT)
    // e o contato/voo dependem desse fps — passá-lo errado inventaria cadência. Ver analyze_form.
    let effective_fps = fps / sample_stride as f32;
    let lay = engine.layout(); // índices semânticos (quadril/joelho/tornozelo...) do layout ativo
    println!(
        "vídeo {w}x{h} @ {fps:.1}fps (vista: {view}, overlay: {overlay}) — layout {}",
        lay.name
    );

    let decoder = Command::new("ffmpeg")
        .args([
            "-v", "error", "-i", input, "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ])
        .stdout(Stdio::piped())
        .spawn()
        .context("ffmpeg (instale com: brew install ffmpeg)")?;
    let mut dec = ManagedChild::new(decoder, "ffmpeg decoder");
    let mut src = dec.take_stdout()?;
    // Encoder só existe na passada de overlay. Sem ele não reencodamos nada — só coletamos séries.
    let (mut enc, mut dst) = if overlay {
        let encoder = Command::new("ffmpeg")
            .args([
                "-v",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                &format!("{w}x{h}"),
                "-r",
                &format!("{fps}"),
                "-i",
                "-",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                out,
            ])
            .stdin(Stdio::piped())
            .spawn()?;
        let mut e = ManagedChild::new(encoder, "ffmpeg encoder");
        let d = e.take_stdin()?;
        (Some(e), Some(d))
    } else {
        (None, None)
    };
    let mut buf = vec![0u8; (w * h * 3) as usize];
    // `frames` = frames AMOSTRADOS (série de métricas); `decoded` = lidos do ffmpeg (tempo real do
    // timestamp). Com stride=1 são iguais; com stride>1 inferimos só 1 a cada N decodificados.
    let mut decoded = 0u32;
    let (mut frames, mut ankle_l, mut ankle_r) = (0u32, Vec::new(), Vec::new());
    // Sinal vertical de solo: BlazePose usa calcanhar+ponta quando ambos são confiáveis; demais
    // backends (ou frames ocluídos) mantêm o tornozelo como fallback comparável.
    let (mut ground_l, mut ground_r, mut foot_landmark_points) = (Vec::new(), Vec::new(), 0u32);
    let (mut hip_y, mut leg_lens) = (Vec::new(), Vec::new());
    // séries de ângulo por perna (E/D) + soma de confiança p/ escolher a perna visível
    let (mut knee_l, mut knee_r, mut hip_l, mut hip_r) =
        (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let (mut conf_l, mut conf_r) = (0f32, 0f32);
    let mut trunk = Vec::new(); // inclinação do tronco por frame
                                // séries X (posição horizontal) p/ padrão de pisada + direção "pra frente"
    let (mut ax_l, mut ax_r, mut kx_l, mut kx_r) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let mut nose_dx = Vec::new(); // nariz − quadril-médio (sinal = direção da corrida)
    let mut pelvic_tilt = Vec::new(); // inclinação da linha do quadril por frame (plano frontal)
    let t = std::time::Instant::now();
    // DIAGNÓSTICO de calibração (STRIDE_DUMP_SERIES): coleta 1 registro por FRAME DECODIFICADO —
    // índice, timestamp, se houve pose, confiança e os landmarks semânticos. Assim o arnês mede os
    // DOIS backends no MESMO frame/evento anotado pelo ground-truth (não nos picos que cada um acha).
    let want_dump = std::env::var("STRIDE_DUMP_SERIES").ok();
    let mut frame_records: Vec<serde_json::Value> = Vec::new();

    loop {
        if let Err(e) = read_exact_or_eof(&mut src, &mut buf) {
            if frames == 0 {
                bail!("nada decodificado: {e}")
            } else {
                break;
            }
        }
        if decoded as usize % sample_stride != 0 {
            decoded += 1; // frame decodificado mas fora da amostra: não infere (é o ganho do A4)
            continue;
        }
        let mut img: RgbImage = RgbImage::from_raw(w, h, buf.clone()).unwrap();
        let ts = frame_timestamp_ms(decoded, fps);
        let pose_opt = engine.infer(&img, ts)?;
        if let Some(pose) = &pose_opt {
            let kp = &pose.keypoints;
            ankle_l.push(kp[lay.ankle_l].1);
            ankle_r.push(kp[lay.ankle_r].1);
            let ground_y = |ankle: usize, heel: Option<usize>, toe: Option<usize>| match (heel, toe)
            {
                (Some(h), Some(t)) if kp[h].2 >= KP_CONF && kp[t].2 >= KP_CONF => {
                    (foot_ground_y(kp[h].1, kp[t].1), true)
                }
                _ => (kp[ankle].1, false),
            };
            let (ground_left, left_foot) = ground_y(lay.ankle_l, lay.heel_l, lay.big_toe_l);
            let (ground_right, right_foot) = ground_y(lay.ankle_r, lay.heel_r, lay.big_toe_r);
            ground_l.push(ground_left);
            ground_r.push(ground_right);
            foot_landmark_points += u32::from(left_foot) + u32::from(right_foot);
            // BUG corrigido: hip_y e leg_len entravam SEM guarda de confiança (diferente de
            // trunk/pelvic abaixo). Keypoint de baixa confiança tem coordenada-lixo -> quadril
            // "saltava" (amplitude 681% da perna) e leg_len oscilava -> FALSO "não-lateral".
            // Agora só entra com o quadril confiável; leg_len usa a perna VISÍVEL (na lateral a
            // de trás é ocluída, baixa conf.).
            if kp[lay.hip_l].2 > KP_CONF && kp[lay.hip_r].2 > KP_CONF {
                hip_y.push((kp[lay.hip_l].1 + kp[lay.hip_r].1) / 2.0); // centro do quadril
            }
            let leg = |hip: (f32, f32, f32), ank: (f32, f32, f32)| {
                ((hip.0 - ank.0).powi(2) + (hip.1 - ank.1).powi(2)).sqrt()
            };
            if kp[lay.hip_l].2 > KP_CONF && kp[lay.ankle_l].2 > KP_CONF {
                leg_lens.push(leg(kp[lay.hip_l], kp[lay.ankle_l])); // perna esquerda
            } else if kp[lay.hip_r].2 > KP_CONF && kp[lay.ankle_r].2 > KP_CONF {
                leg_lens.push(leg(kp[lay.hip_r], kp[lay.ankle_r])); // perna direita (esquerda ocluída)
            }
            // Ângulos articulares de PRODUÇÃO são sempre 2D na imagem, para todos os backends.
            // Os world landmarks do BlazePose são uma estimativa do modelo, não uma troca segura de
            // geometria: alternar automaticamente mudava os limiares de risco sem mudar o contrato
            // da métrica. O dump STRIDE_DUMP_SERIES preserva kpw para estudo explícito em 3D.
            let angle = |a: usize, b: usize, c: usize| joint_angle(kp[a], kp[b], kp[c]);
            knee_l.push(angle(lay.hip_l, lay.knee_l, lay.ankle_l));
            knee_r.push(angle(lay.hip_r, lay.knee_r, lay.ankle_r));
            hip_l.push(angle(lay.shoulder_l, lay.hip_l, lay.knee_l));
            hip_r.push(angle(lay.shoulder_r, lay.hip_r, lay.knee_r));
            conf_l += kp[lay.hip_l].2.min(kp[lay.knee_l].2).min(kp[lay.ankle_l].2);
            conf_r += kp[lay.hip_r].2.min(kp[lay.knee_r].2).min(kp[lay.ankle_r].2);
            ax_l.push(kp[lay.ankle_l].0);
            ax_r.push(kp[lay.ankle_r].0);
            kx_l.push(kp[lay.knee_l].0);
            kx_r.push(kp[lay.knee_r].0);
            nose_dx.push(kp[lay.nose].0 - (kp[lay.hip_l].0 + kp[lay.hip_r].0) / 2.0);
            // inclinação do tronco: ombro-médio vs quadril-médio (só com tronco confiável)
            if kp[lay.shoulder_l].2 > KP_CONF
                && kp[lay.shoulder_r].2 > KP_CONF
                && kp[lay.hip_l].2 > KP_CONF
                && kp[lay.hip_r].2 > KP_CONF
            {
                let sh = (
                    (kp[lay.shoulder_l].0 + kp[lay.shoulder_r].0) / 2.0,
                    (kp[lay.shoulder_l].1 + kp[lay.shoulder_r].1) / 2.0,
                );
                let hp = (
                    (kp[lay.hip_l].0 + kp[lay.hip_r].0) / 2.0,
                    (kp[lay.hip_l].1 + kp[lay.hip_r].1) / 2.0,
                );
                trunk.push(trunk_lean_deg(sh, hp));
            }
            // queda pélvica (plano frontal): inclinação da linha do quadril quando ela é confiável
            if kp[lay.hip_l].2 > KP_CONF && kp[lay.hip_r].2 > KP_CONF {
                pelvic_tilt.push(hip_tilt_deg(kp[lay.hip_l], kp[lay.hip_r]));
            }
            if overlay {
                draw_pose(&mut img, pose);
                if view == "lateral" {
                    draw_angles(&mut img, pose);
                } // goniômetros sagitais só na lateral
            }
        }
        if want_dump.is_some() {
            frame_records.push(frame_record(&pose_opt, frames, ts));
        }
        if let Some(d) = dst.as_mut() {
            d.write_all(img.as_raw())?;
        } // só reencoda na passada de overlay
        frames += 1;
        decoded += 1;
    }
    drop(dst); // fecha o stdin do encoder (se houver) -> ele finaliza o mp4
    dec.wait_success()?;
    if let Some(e) = enc.as_mut() {
        e.wait_success()?;
    }
    let el = t.elapsed().as_secs_f32();
    println!(
        "{frames} frames em {el:.1}s ({:.1} fps de processamento)",
        frames as f32 / el
    );

    // Grava o dump por-frame (se pedido). Backend-independente: landmarks por NOME semântico +
    // fps/layout, pra o arnês recomputar qualquer ângulo no MESMO frame pros dois backends.
    if let Some(dump_path) = &want_dump {
        let doc = serde_json::json!({
            "layout": lay.name, "fps": fps, "frames_total": frames, "frames": frame_records,
        });
        write_frame_dump(dump_path, &doc)?;
    }

    // métricas consolidadas -> JSON ao lado do vídeo (o backend lê daqui)
    leg_lens.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let leg_len = leg_lens.get(leg_lens.len() / 2).copied().unwrap_or(0.0);
    // as DUAS pernas consistentemente visíveis? (numa lateral uma é ocluída -> baixa conf.)
    let both_legs_ok = frames > 0 && conf_l / frames as f32 > 0.35 && conf_r / frames as f32 > 0.35;
    let mut metrics = analyze_form(
        &ankle_l,
        &ankle_r,
        &hip_y,
        leg_len,
        effective_fps,
        frames as usize,
        view,
        both_legs_ok,
    );

    if view == "frontal" {
        // plano frontal: queda pélvica (pico da inclinação da bacia) + valgo (pior perna)
        metrics.pelvic_drop_deg = percentile(&pelvic_tilt, 0.90).map(|v| (v * 10.0).round() / 10.0);
        let valgus = knee_valgus_deg(&knee_l)
            .into_iter()
            .chain(knee_valgus_deg(&knee_r))
            .fold(None, |acc: Option<f32>, v| {
                Some(acc.map_or(v, |a| a.max(v)))
            });
        metrics.knee_valgus_deg = valgus;
    } else {
        // vista lateral: ângulo no APOIO (perna mais visível), contato/voo, pisada, tronco
        let right = conf_r >= conf_l;
        let (knee_ser, hip_ser, ankle_ser, ground_ser) = if right {
            (&knee_r, &hip_r, &ankle_r, &ground_r)
        } else {
            (&knee_l, &hip_l, &ankle_l, &ground_l)
        };
        metrics.knee_contact_deg = contact_angle(knee_ser, ground_ser);
        metrics.hip_contact_deg = contact_angle(hip_ser, ground_ser);
        metrics.trunk_lean_deg = median(&trunk).map(|v| (v * 10.0).round() / 10.0);
        let (gct, flight) = contact_flight_ms(&ground_l, &ground_r, fps);
        metrics.ground_contact_ms = gct;
        metrics.flight_ms = flight;
        if lay.has_foot() && frames > 0 {
            let coverage = foot_landmark_points as f32 / (2.0 * frames as f32) * 100.0;
            metrics.foot_landmark_coverage_pct = Some((coverage * 10.0).round() / 10.0);
            metrics.ground_contact_source = Some(if foot_landmark_points == 0 {
                "ankle_proxy".to_string()
            } else if foot_landmark_points == 2 * frames {
                "heel_toe_landmarks".to_string()
            } else {
                "heel_toe_with_ankle_fallback".to_string()
            });
        } else {
            metrics.ground_contact_source = Some("ankle_proxy".to_string());
        }
        // Reforço do quality gate: passo ≈ GCT+voo e NÃO pode exceder a passada da cadência. Se
        // estoura (evento de solo perdido inflou o voo — ex.: video_corrida_23, 498ms vs passo
        // 361ms), a temporização é não-confiável -> nulifica GCT/voo (não vira conselho) e marca o
        // motivo. Cadência/ângulos seguem válidos; a captura não é rejeitada, só o timing suspeito.
        if let (Some(cad), Some(g), Some(f)) = (
            metrics.cadence_spm,
            metrics.ground_contact_ms,
            metrics.flight_ms,
        ) {
            if !timing_consistent_with_cadence(cad, g, f) {
                metrics.ground_contact_ms = None;
                metrics.flight_ms = None;
                metrics.ground_contact_source = Some("rejected_timing_vs_cadence".to_string());
            }
        }
        let facing = median(&nose_dx).unwrap_or(0.0);
        let (ax, kx) = if right {
            (&ax_r, &kx_r)
        } else {
            (&ax_l, &kx_l)
        };
        metrics.foot_strike =
            foot_strike(ax, ankle_ser, kx, facing, leg_len).map(|s| s.to_string());
    }
    let mpath = format!("{}.metrics.json", out.trim_end_matches(".mp4"));
    std::fs::write(&mpath, serde_json::to_string_pretty(&metrics)?)?;

    if view == "frontal" {
        println!(
            "FRONTAL | queda pélvica: {:?}° | valgo joelho: {:?}° | confiável: {}",
            metrics.pelvic_drop_deg, metrics.knee_valgus_deg, metrics.reliable
        );
    } else {
        match metrics.cadence_spm {
            Some(c) => println!(
                "CADÊNCIA: {c:.0} spm | assimetria: {:?}% | osc. vertical: {:?}%",
                metrics.asymmetry_pct, metrics.vertical_oscillation_pct
            ),
            None => println!("cadência: série curta demais (filme >5s)"),
        }
    }
    if overlay {
        println!("vídeo: {out}");
    }
    println!("métricas: {mpath}");
    Ok(())
}

fn read_exact_or_eof(r: &mut impl Read, buf: &mut [u8]) -> std::io::Result<()> {
    let mut filled = 0;
    while filled < buf.len() {
        let n = r.read(&mut buf[filled..])?;
        if n == 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::UnexpectedEof,
                "eof",
            ));
        }
        filled += n;
    }
    Ok(())
}

fn probe(input: &str) -> Result<(u32, u32, f32)> {
    let out = Command::new("ffprobe")
        .args([
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate:stream_side_data=rotation",
            "-of",
            "csv=p=0",
            input,
        ])
        .output()
        .context("ffprobe")?;
    let s = String::from_utf8_lossy(&out.stdout);
    let parts: Vec<&str> = s.trim().split(',').collect();
    if parts.len() < 3 {
        bail!("ffprobe não retornou dimensões e FPS do vídeo");
    }
    let rate: Vec<f32> = parts[2]
        .split('/')
        .map(|x| x.parse().unwrap_or(1.0))
        .collect();
    let rotation = parts
        .get(3)
        .and_then(|value| value.parse::<i32>().ok())
        .unwrap_or(0);
    let (width, height) = oriented_dimensions(parts[0].parse()?, parts[1].parse()?, rotation);
    Ok((width, height, rate[0] / rate.get(1).copied().unwrap_or(1.0)))
}

/// O ffmpeg auto-rota vídeos de celular; o buffer raw precisa usar a geometria já orientada.
fn oriented_dimensions(width: u32, height: u32, rotation: i32) -> (u32, u32) {
    if rotation.rem_euclid(180) == 90 {
        (height, width)
    } else {
        (width, height)
    }
}

#[cfg(test)]
mod cli_tests {
    use super::{frame_timestamp_ms, oriented_dimensions, write_frame_dump, ManagedChild};
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
        let report = super::benchmark_report("/tmp/corrida.mp4", 100, 90, 80, 4.0, 25.0, 1);
        let run = &report["runs"][0];
        assert_eq!(run["video"], "corrida.mp4");
        assert_eq!(run["sample_stride"], 1);
        assert_eq!(run["effective_fps"], 25.0);
        assert_eq!(run["measurement_stage"], "decode+pose_inference");
        assert_eq!(run["reliable"], true);
        assert_eq!(run["foot_points_visible_frames"], 80);
    }

    #[test]
    fn benchmark_registra_o_stride_e_o_fps_efetivo() {
        // A 30fps com stride=2, o modelo processa metade dos frames -> 15 fps efetivos.
        let report = super::benchmark_report("/tmp/c.mp4", 50, 45, 40, 2.0, 30.0, 2);
        let run = &report["runs"][0];
        assert_eq!(run["sample_stride"], 2);
        assert_eq!(run["effective_fps"], 15.0);
    }

    #[test]
    fn benchmark_sem_pessoa_nao_e_confiavel() {
        // Ausência de pessoa: 0 detecções em N frames -> reliable=false, pé não visível.
        // O produto NÃO deve opinar em cima disso (degrada gracioso, pede refilmagem).
        let report = super::benchmark_report("/tmp/vazio.mp4", 120, 0, 0, 3.0, 30.0, 1);
        let run = &report["runs"][0];
        assert_eq!(run["detection_rate_pct"], 0.0);
        assert_eq!(run["reliable"], false);
        assert_eq!(run["foot_points_visible"], false);
    }

    #[test]
    fn benchmark_deteccao_parcial_reprova_no_gate() {
        // Vídeo ruim: pessoa entra/sai do quadro (50% de detecção) -> abaixo do piso de 80%.
        let report = super::benchmark_report("/tmp/ruim.mp4", 100, 50, 10, 3.0, 30.0, 1);
        assert_eq!(report["runs"][0]["reliable"], false);
    }

    #[test]
    fn processo_filhos_com_erro_nao_sao_sucesso() {
        let child = Command::new("sh").args(["-c", "exit 7"]).spawn().unwrap();
        let mut managed = ManagedChild::new(child, "ffmpeg de teste");
        assert!(managed.wait_success().is_err());
    }

    #[test]
    fn timestamp_de_video_e_deterministico_e_monotonico() {
        assert_eq!(frame_timestamp_ms(0, 30.0), 0);
        assert_eq!(frame_timestamp_ms(1, 30.0), 33);
        assert_eq!(frame_timestamp_ms(30, 30.0), 1_000);
        assert_eq!(frame_timestamp_ms(4, 0.0), 4);
    }

    #[test]
    fn dump_cria_diretorios_ausentes() {
        let root =
            std::env::temp_dir().join(format!("strideredge-dump-test-{}", std::process::id()));
        let target = root.join("nested").join("series.json");
        let doc = serde_json::json!({"frames": []});
        write_frame_dump(target.to_str().unwrap(), &doc).unwrap();
        assert_eq!(std::fs::read_to_string(&target).unwrap(), "{\"frames\":[]}");
        std::fs::remove_dir_all(root).unwrap();
    }
}
