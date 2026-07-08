//! CLI do motor: `stride-vision <foto.jpg|video.mp4> [saida]`
//! Foto  -> esqueleto desenhado + keypoints no terminal.
//! Vídeo -> mp4 com esqueleto em todos os frames + CADÊNCIA estimada (FFT).

use anyhow::{bail, Context, Result};
use image::RgbImage;
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use stride_vision::{analyze_form, cadence_spm, draw_pose, PoseEngine, KP_NAMES};

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        bail!("uso: stride-vision <foto.jpg|video.mp4> [saida]");
    }
    let input = &args[1];
    let model = std::env::var("STRIDE_MODEL")
        .unwrap_or_else(|_| "models/yolo11n-pose.onnx".into());
    let mut engine = PoseEngine::new(&model)?;

    let ext = input.rsplit('.').next().unwrap_or("").to_lowercase();
    if matches!(ext.as_str(), "jpg" | "jpeg" | "png") {
        let out = args.get(2).cloned().unwrap_or_else(|| "pose_out.jpg".into());
        run_image(&mut engine, input, &out)
    } else {
        let out = args.get(2).cloned().unwrap_or_else(|| "pose_out.mp4".into());
        run_video(&mut engine, input, &out)
    }
}

fn run_image(engine: &mut PoseEngine, input: &str, out: &str) -> Result<()> {
    let mut img = image::open(input).context("abrindo imagem")?.to_rgb8();
    let t = std::time::Instant::now();
    match engine.infer(&img)? {
        Some(pose) => {
            println!("pessoa detectada (conf {:.2}) em {:?}", pose.confidence, t.elapsed());
            for (k, &(x, y, c)) in pose.keypoints.iter().enumerate() {
                if c > 0.35 {
                    println!("  {:12} ({:5.0},{:5.0}) conf {:.2}", KP_NAMES[k], x, y, c);
                }
            }
            draw_pose(&mut img, &pose);
            img.save(out)?;
            println!("esqueleto salvo em {out}");
        }
        None => println!("nenhuma pessoa detectada"),
    }
    Ok(())
}

/// Vídeo via ffmpeg (pipes rawvideo): decodifica -> infere+desenha -> re-encoda.
fn run_video(engine: &mut PoseEngine, input: &str, out: &str) -> Result<()> {
    let (w, h, fps) = probe(input)?;
    println!("vídeo {w}x{h} @ {fps:.1}fps");

    let mut dec = Command::new("ffmpeg")
        .args(["-v", "error", "-i", input, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        .stdout(Stdio::piped()).spawn().context("ffmpeg (instale com: brew install ffmpeg)")?;
    let mut enc = Command::new("ffmpeg")
        .args(["-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", &format!("{w}x{h}"), "-r", &format!("{fps}"), "-i", "-",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
        .stdin(Stdio::piped()).spawn()?;

    let mut src = dec.stdout.take().unwrap();
    let mut dst = enc.stdin.take().unwrap();
    let mut buf = vec![0u8; (w * h * 3) as usize];
    let (mut frames, mut ankle_l, mut ankle_r) = (0u32, Vec::new(), Vec::new());
    let (mut hip_y, mut leg_lens) = (Vec::new(), Vec::new());
    let t = std::time::Instant::now();

    loop {
        if let Err(e) = read_exact_or_eof(&mut src, &mut buf) {
            if frames == 0 { bail!("nada decodificado: {e}") } else { break }
        }
        let mut img: RgbImage = RgbImage::from_raw(w, h, buf.clone()).unwrap();
        if let Some(pose) = engine.infer(&img)? {
            let kp = &pose.keypoints;
            ankle_l.push(kp[15].1);
            ankle_r.push(kp[16].1);
            hip_y.push((kp[11].1 + kp[12].1) / 2.0);          // centro do quadril
            // comprimento da perna (quadril->tornozelo) = escala do corpo no vídeo
            leg_lens.push(((kp[11].0 - kp[15].0).powi(2) + (kp[11].1 - kp[15].1).powi(2)).sqrt());
            draw_pose(&mut img, &pose);
        }
        dst.write_all(img.as_raw())?;
        frames += 1;
    }
    drop(dst);
    enc.wait()?;
    let el = t.elapsed().as_secs_f32();
    println!("{frames} frames em {el:.1}s ({:.1} fps de processamento)", frames as f32 / el);

    // métricas consolidadas -> JSON ao lado do vídeo (o backend lê daqui)
    leg_lens.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let leg_len = leg_lens.get(leg_lens.len() / 2).copied().unwrap_or(0.0);
    let metrics = analyze_form(&ankle_l, &ankle_r, &hip_y, leg_len, fps, frames as usize);
    let mpath = format!("{}.metrics.json", out.trim_end_matches(".mp4"));
    std::fs::write(&mpath, serde_json::to_string_pretty(&metrics)?)?;

    match metrics.cadence_spm {
        Some(c) => println!("CADÊNCIA: {c:.0} spm | assimetria: {:?}% | osc. vertical: {:?}%",
                            metrics.asymmetry_pct, metrics.vertical_oscillation_pct),
        None => println!("cadência: série curta demais (filme >5s)"),
    }
    println!("vídeo: {out}\nmétricas: {mpath}");
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
               "stream=width,height,r_frame_rate", "-of", "csv=p=0", input])
        .output().context("ffprobe")?;
    let s = String::from_utf8_lossy(&out.stdout);
    let parts: Vec<&str> = s.trim().split(',').collect();
    let rate: Vec<f32> = parts[2].split('/').map(|x| x.parse().unwrap_or(1.0)).collect();
    Ok((parts[0].parse()?, parts[1].parse()?, rate[0] / rate.get(1).copied().unwrap_or(1.0)))
}
