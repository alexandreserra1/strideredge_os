//! CLI do motor: `stride-vision <foto.jpg|video.mp4> [saida]`
//! Foto  -> esqueleto desenhado + keypoints no terminal.
//! Vídeo -> mp4 com esqueleto em todos os frames + CADÊNCIA estimada (FFT).

use anyhow::{bail, Context, Result};
use image::RgbImage;
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use stride_vision::{cadence_spm, draw_pose, PoseEngine, KP_NAMES};

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
    let t = std::time::Instant::now();

    loop {
        if let Err(e) = read_exact_or_eof(&mut src, &mut buf) {
            if frames == 0 { bail!("nada decodificado: {e}") } else { break }
        }
        let mut img: RgbImage = RgbImage::from_raw(w, h, buf.clone()).unwrap();
        if let Some(pose) = engine.infer(&img)? {
            ankle_l.push(pose.keypoints[15].1);
            ankle_r.push(pose.keypoints[16].1);
            draw_pose(&mut img, &pose);
        }
        dst.write_all(img.as_raw())?;
        frames += 1;
    }
    drop(dst);
    enc.wait()?;
    let el = t.elapsed().as_secs_f32();
    println!("{frames} frames em {el:.1}s ({:.1} fps de processamento)", frames as f32 / el);

    match (cadence_spm(&ankle_l, fps), cadence_spm(&ankle_r, fps)) {
        (Some(l), Some(r)) => println!("CADÊNCIA estimada: {:.0} spm (E {l:.0} / D {r:.0})", (l + r) / 2.0),
        (Some(c), None) | (None, Some(c)) => println!("CADÊNCIA estimada: {c:.0} spm (um tornozelo)"),
        _ => println!("cadência: série curta demais (filme >5s)"),
    }
    println!("vídeo com esqueleto salvo em {out}");
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
