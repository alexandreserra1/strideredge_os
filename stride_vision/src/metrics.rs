//! metrics.rs — biomecânica feita na mão a partir das séries temporais dos keypoints.
//!
//! Consome só `Vec<f32>` (séries de tornozelo/quadril/ângulos) — nada de imagem nem de modelo.
//! `analyze_form` consolida tudo no DTO `FormMetrics` (JSON pro backend), com os quality gates por
//! vista (lateral × frontal). Séries curtas/ruins degradam gracioso (None + nota), nunca chutam.

use rustfft::{num_complex::Complex, FftPlanner};
use std::collections::HashMap;

/// Geometria dos ângulos articulares expostos pelo produto.
///
/// A captura é uma única câmera lateral/frontal e a validação pareada atual do BlazePose foi
/// feita neste espaço. World landmarks do modelo seguem disponíveis somente no dump diagnóstico;
/// escolhê-los implicitamente mudaria os limiares clínicos conforme o backend.
pub const PRODUCTION_JOINT_ANGLE_SPACE: &str = "image_2d";

/// Duração mínima do vídeo p/ análise confiável: menos que isso = poucos ciclos de passada, FFT de
/// cadência instável e amostra pequena de cada métrica. A 15s (~21 passadas/perna @170spm) há sinal
/// suficiente p/ ver o que está certo/errado com robustez. Predição de lesão exige amostra boa.
pub const MIN_DURATION_S: f32 = 15.0;

/// Cadência (passos/min) a partir da série vertical de UM tornozelo.
/// FFT: frequência dominante da oscilação de um pé * 2 (dois pés) * 60.
pub fn cadence_spm(ankle_y: &[f32], fps: f32) -> Option<f32> {
    if ankle_y.len() < 16 {
        return None;
    }
    let mean = ankle_y.iter().sum::<f32>() / ankle_y.len() as f32;
    let mut buf: Vec<Complex<f32>> = ankle_y
        .iter()
        .map(|v| Complex::new(v - mean, 0.0))
        .collect();
    FftPlanner::new()
        .plan_fft_forward(buf.len())
        .process(&mut buf);
    let n = buf.len();
    // procura o pico entre 0.5 e 2.5 Hz (30–150 passos/min por pé — faixa humana)
    let hz = |i: usize| i as f32 * fps / n as f32;
    let (mut bi, mut bm) = (0, 0f32);
    for i in 1..n / 2 {
        if hz(i) < 0.5 || hz(i) > 2.5 {
            continue;
        }
        let m = buf[i].norm();
        if m > bm {
            bm = m;
            bi = i;
        }
    }
    if bi == 0 {
        return None;
    }
    Some(hz(bi) * 2.0 * 60.0)
}

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
    /// flexão do JOELHO no instante do apoio do pé (graus). Reto ~180°; muito reto no
    /// apoio = passada longa (overstriding), impacto direto na articulação.
    pub knee_contact_deg: Option<f32>,
    /// flexão do QUADRIL no apoio (graus): abertura tronco↔coxa.
    pub hip_contact_deg: Option<f32>,
    /// Espaço geométrico dos ângulos de joelho/quadril expostos nesta análise. É metadado de
    /// proveniência, não uma alegação de precisão 3D clínica.
    pub joint_angle_space: String,
    /// inclinação do TRONCO em relação à vertical (graus). Leve inclinação pra frente
    /// (~5–10°) é eficiente; ereto/pra trás freia; muito inclinado sobrecarrega a lombar.
    pub trunk_lean_deg: Option<f32>,
    /// tempo de contato com o solo por passo (ms). Menor = mais elástico/rápido.
    pub ground_contact_ms: Option<f32>,
    /// tempo de voo (ambos os pés no ar) por passo (ms).
    pub flight_ms: Option<f32>,
    /// Sinal que ancorou GCT/voo/ângulos no apoio: pé direto quando disponível, tornozelo como
    /// fallback. É proveniência, não uma nova métrica clínica.
    pub ground_contact_source: Option<String>,
    /// Cobertura dos pares calcanhar+ponta do pé entre as pernas detectadas (0–100). None em
    /// layouts sem pontos de pé.
    pub foot_landmark_coverage_pct: Option<f32>,
    /// padrão de pisada ESTIMADO por tornozelo×joelho: "calcanhar" | "médio" | "antepé".
    /// Mesmo layouts com calcanhar/ponta não o promovem a medida clínica de pronação.
    pub foot_strike: Option<String>,
    // ----- métricas do plano FRONTAL (só na vista frontal) -----
    /// queda pélvica contralateral (graus): a bacia caindo pro lado da perna no ar no apoio.
    /// >~10° associa-se a dor patelofemoral / banda IT / canelite.
    pub pelvic_drop_deg: Option<f32>,
    /// valgo dinâmico de joelho / FPPA (graus): desvio do joelho da linha quadril-tornozelo no
    /// plano frontal (joelho "caindo pra dentro"). Maior = mais carga na patela.
    pub knee_valgus_deg: Option<f32>,
    /// vista da câmera desta análise: "lateral" (sagital) | "frontal".
    pub view: Option<String>,
    /// as métricas são confiáveis? false = enquadramento/ângulo ruim (vista errada, atleta
    /// some do quadro, ou pernas mal rastreadas). A UI avisa.
    pub reliable: bool,
    /// por que não é confiável (vazio quando reliable=true)
    pub quality_note: Option<String>,
    // ---- Observabilidade do quality gate: os INSUMOS crus da decisão, pra calibrar o limiar com
    // dado real (não no chute). Preservados MESMO quando a métrica é rejeitada/nulificada.
    /// código machine-readable do motivo: ok | low_detection | not_lateral | both_legs_missing
    pub reason: String,
    /// oscilação vertical CRUA (%) — antes do filtro ≤40% (ver se a rejeição foi borderline 41 ou lixo 200)
    pub diag_vert_osc_pct: Option<f32>,
    /// comprimento de perna em px (denominador da razão) — ver se a rejeição foi encurtamento de perspectiva
    pub diag_leg_len_px: f32,
    /// Confiabilidade POR MÉTRICA (0.0–1.0): fração dos frames/amostras usados no cálculo de CADA
    /// métrica cujos keypoints envolvidos tiveram confiança >= KP_CONF (main.rs). Mesma régua p/
    /// toda métrica — sem caso especial pro joelho. Chaves = nomes dos campos acima (ex.:
    /// "knee_contact_deg", "cadence_spm"). Ausência de chave = métrica não computada nesta corrida
    /// (não confundir com 0.0, que é "computada mas com keypoints de baixa confiança").
    pub metric_confidence: HashMap<String, f32>,
    /// Coeficiente de variação (desvio-padrão / |média|) entre as AMOSTRAS de métricas com
    /// MÚLTIPLAS amostras por passada (ângulo no apoio, contato, voo, oscilação). Cadência é valor
    /// único de FFT e não entra aqui (ausente, não zero). CV alto = passadas inconsistentes entre
    /// si (ruído de rastreio ou variabilidade real do atleta) — outro sinal de quanto confiar.
    pub metric_cv: HashMap<String, f32>,
}

/// Fração (0.0–1.0) de flags `true` num vetor de confiança por-amostra (>= KP_CONF, decidido pelo
/// chamador). 0.0 quando não há amostra — a AUSÊNCIA da chave no mapa (não este valor) é quem
/// sinaliza "métrica não computada"; uma vez inserida, a fração é sempre um número.
pub fn confidence_fraction(flags: &[bool]) -> f32 {
    if flags.is_empty() {
        return 0.0;
    }
    flags.iter().filter(|&&f| f).count() as f32 / flags.len() as f32
}

/// Coeficiente de variação (desvio-padrão / |média|) de um conjunto de amostras da MESMA métrica
/// (ex.: o ângulo do joelho em cada apoio detectado). `None` com <2 amostras ou média ~0 (evita
/// dividir por zero ou inventar um CV de sinal degenerado).
pub fn coefficient_of_variation(samples: &[f32]) -> Option<f32> {
    if samples.len() < 2 {
        return None;
    }
    let mean = samples.iter().sum::<f32>() / samples.len() as f32;
    if mean.abs() < 1e-6 {
        return None;
    }
    let var = samples.iter().map(|v| (v - mean).powi(2)).sum::<f32>() / samples.len() as f32;
    Some((var.sqrt() / mean.abs() * 1000.0).round() / 1000.0)
}

/// amplitude robusta de uma série (p95 - p5; ignora outliers de detecção)
fn amplitude(series: &[f32]) -> Option<f32> {
    if series.len() < 8 {
        return None;
    }
    let mut v: Vec<f32> = series.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p = |q: f32| v[((v.len() - 1) as f32 * q) as usize];
    Some(p(0.95) - p(0.05))
}

/// Métricas vazias (base): tudo None, só frames/fps/detecção + reliable/nota. O main preenche o
/// que fizer sentido por vista.
fn empty_metrics(
    total_frames: usize,
    fps: f32,
    detection: f32,
    view: &str,
    reliable: bool,
    note: Option<String>,
    reason: &str,
) -> FormMetrics {
    FormMetrics {
        frames: total_frames,
        fps,
        detection_rate_pct: detection,
        cadence_spm: None,
        cadence_left: None,
        cadence_right: None,
        asymmetry_pct: None,
        vertical_oscillation_pct: None,
        knee_contact_deg: None,
        hip_contact_deg: None,
        joint_angle_space: PRODUCTION_JOINT_ANGLE_SPACE.to_string(),
        trunk_lean_deg: None,
        ground_contact_ms: None,
        flight_ms: None,
        ground_contact_source: None,
        foot_landmark_coverage_pct: None,
        foot_strike: None,
        pelvic_drop_deg: None,
        knee_valgus_deg: None,
        view: Some(view.to_string()),
        reliable,
        quality_note: note,
        reason: reason.to_string(),
        diag_vert_osc_pct: None,
        diag_leg_len_px: 0.0,
        metric_confidence: HashMap::new(),
        metric_cv: HashMap::new(),
    }
}

/// Consolida as séries por frame em métricas de forma. `view` = "lateral" | "frontal" decide
/// O QUE se mede e COMO se valida. `both_legs_ok` = as duas pernas ficaram visíveis (sinal de
/// vista frontal boa). `leg_len_px` = mediana da distância quadril->tornozelo (escala do corpo).
pub fn analyze_form(
    ankle_l: &[f32],
    ankle_r: &[f32],
    hip_y: &[f32],
    leg_len_px: f32,
    fps: f32,
    total_frames: usize,
    view: &str,
    both_legs_ok: bool,
) -> FormMetrics {
    let detection = if total_frames > 0 {
        ankle_l.len() as f32 / total_frames as f32 * 100.0
    } else {
        0.0
    };

    // Vídeo curto demais: poucos ciclos de passada -> métricas instáveis. Barra ANTES de tudo
    // (vale p/ lateral e frontal) — melhor pedir um vídeo maior do que analisar com pouco sinal.
    let duration_s = if fps > 0.0 {
        total_frames as f32 / fps
    } else {
        0.0
    };
    if duration_s < MIN_DURATION_S {
        let nota = format!(
            "Vídeo curto demais ({duration_s:.0}s) — filme pelo menos {:.0}s \
            correndo, sem cortes, pra dar pra analisar com confiança.",
            MIN_DURATION_S
        );
        return empty_metrics(
            total_frames,
            fps,
            detection,
            view,
            false,
            Some(nota),
            "too_short",
        );
    }

    // ---- VISTA FRONTAL: as métricas sagitais (cadência, oscilação, pisada) não fazem sentido.
    // Valida por detecção + as DUAS pernas visíveis (numa lateral uma perna é ocluída). O main
    // preenche pelvic_drop/knee_valgus.
    if view == "frontal" {
        let (note, reason) = if detection < 60.0 {
            (
                Some(
                    "O atleta sai do quadro em boa parte do vídeo — filme com ele sempre visível."
                        .into(),
                ),
                "low_detection",
            )
        } else if !both_legs_ok {
            (Some("Não deu pra ver as duas pernas — filme de FRENTE (ou de costas), corpo inteiro, pernas visíveis.".into()), "both_legs_missing")
        } else {
            (None, "ok")
        };
        return empty_metrics(
            total_frames,
            fps,
            detection,
            view,
            note.is_none(),
            note,
            reason,
        );
    }

    // ---- VISTA LATERAL (comportamento existente): cadência, assimetria, oscilação.
    let (cl, cr) = (cadence_spm(ankle_l, fps), cadence_spm(ankle_r, fps));
    // Numa vista LATERAL a perna de trás fica OCLUÍDA: seu tornozelo "pula" no rastreio e a
    // FFT lê um SUB-HARMÔNICO (metade da frequência real). Quando as pernas divergem muito,
    // a cadência de corrida verdadeira é a MAIOR (a perna visível oscila na fundamental);
    // só fazemos a média quando as duas concordam (vista frontal/simétrica, sem oclusão).
    let cadence = match (cl, cr) {
        (Some(l), Some(r)) => Some(if (l - r).abs() / l.max(r) > 0.25 {
            l.max(r)
        } else {
            (l + r) / 2.0
        }),
        (a, b) => a.or(b),
    };
    // Assimetria bilateral NÃO é medível em vista LATERAL: a perna de trás é ocluída, então sua
    // amplitude é sempre menor -> "assimetria" fantasma (~40%) que inflaria o risco (peso 2.0).
    // Precisa das duas pernas igualmente visíveis (frontal/posterior). Aqui é sempre None.
    let asymmetry: Option<f32> = None;
    // oscilação vertical realista fica bem abaixo de ~20% da perna. Acima de 40% é
    // sinal de vista NÃO-lateral (perspectiva) ou perna mal rastreada -> descarta o número.
    // `raw_vert` guarda o valor CRU (observabilidade) mesmo quando rejeitado.
    let raw_vert = amplitude(hip_y)
        .filter(|_| leg_len_px > 0.0)
        .map(|a| a / leg_len_px * 100.0);
    let vert_osc = raw_vert.filter(|v| *v <= 40.0);

    // Guarda de QUALIDADE: confia se o atleta ficou no quadro E a vista é lateral (a
    // oscilação vertical do quadril é o detector de "é lateral?" — plausível ≤40% da perna).
    // NÃO exigimos que as duas pernas concordem: numa lateral boa a de trás é ocluída, então
    // divergência de cadência entre pernas é ESPERADA, não sinal de erro.
    // fração de frames com quadril CONFIÁVEL (hip_y só entra com kp confiante no main). Baixa =
    // tronco fora do quadro (só pernas) — motivo DIFERENTE de "não-lateral", guia o usuário certo.
    let hip_seen = if total_frames > 0 {
        hip_y.len() as f32 / total_frames as f32
    } else {
        0.0
    };
    let (note, reason): (Option<String>, &str) = if detection < 60.0 {
        (
            Some(
                "O atleta sai do quadro em boa parte do vídeo — filme com ele sempre visível."
                    .into(),
            ),
            "low_detection",
        )
    } else if hip_seen < 0.5 {
        (Some("Não deu pra rastrear o quadril com confiança — filme o CORPO INTEIRO (tronco visível), não só as pernas.".into()), "torso_not_visible")
    } else if vert_osc.is_none() {
        (
            Some("Ângulo parece não ser lateral — filme de LADO, corpo inteiro no quadro.".into()),
            "not_lateral",
        )
    } else {
        (None, "ok")
    };

    FormMetrics {
        frames: total_frames,
        fps,
        detection_rate_pct: detection,
        cadence_spm: cadence,
        cadence_left: cl,
        cadence_right: cr,
        asymmetry_pct: asymmetry.map(|v| (v * 10.0).round() / 10.0),
        vertical_oscillation_pct: vert_osc.map(|v| (v * 10.0).round() / 10.0),
        knee_contact_deg: None, // preenchido pelo main a partir das séries de ângulo
        hip_contact_deg: None,
        joint_angle_space: PRODUCTION_JOINT_ANGLE_SPACE.to_string(),
        trunk_lean_deg: None,
        ground_contact_ms: None,
        flight_ms: None,
        ground_contact_source: None,
        foot_landmark_coverage_pct: None,
        foot_strike: None,
        pelvic_drop_deg: None, // frontal — None na lateral
        knee_valgus_deg: None,
        view: Some("lateral".to_string()),
        reliable: note.is_none(),
        quality_note: note,
        reason: reason.to_string(),
        diag_vert_osc_pct: raw_vert.map(|v| (v * 10.0).round() / 10.0),
        diag_leg_len_px: (leg_len_px * 10.0).round() / 10.0,
        // Preenchidos pelo main.rs (é quem tem a confiança por-frame dos keypoints); aqui só o
        // esqueleto vazio, no mesmo padrão de knee_contact_deg/trunk_lean_deg/etc. acima.
        metric_confidence: HashMap::new(),
        metric_cv: HashMap::new(),
    }
}

/// Ângulo médio de uma articulação nos instantes de APOIO do pé.
/// Apoio = tornozelo no ponto mais baixo do frame (y máximo local, pois y cresce pra baixo).
/// Medir SEMPRE na mesma fase da passada dá um número estável e comparável — diferente do
/// ângulo instantâneo, que varia o tempo todo. None se a série for curta demais.
pub fn contact_angle(angles: &[f32], ankle_y: &[f32]) -> Option<f32> {
    let vals = contact_angle_samples(angles, ankle_y);
    if vals.len() < 2 {
        return None;
    }
    Some(((vals.iter().sum::<f32>() / vals.len() as f32) * 10.0).round() / 10.0)
}

/// As amostras cruas por-apoio usadas por `contact_angle` (um ângulo por evento de apoio
/// detectado), expostas separadamente pra quem quiser o CV entre apoios sem duplicar a detecção.
pub fn contact_angle_samples(angles: &[f32], ankle_y: &[f32]) -> Vec<f32> {
    let n = angles.len().min(ankle_y.len());
    if n < 12 {
        return Vec::new();
    }
    let mut vals = Vec::new();
    let mut last = 0usize;
    for i in 1..n - 1 {
        let is_contact = ankle_y[i] >= ankle_y[i - 1] && ankle_y[i] > ankle_y[i + 1];
        // espaçamento mínimo entre apoios evita contar o mesmo pico duas vezes
        if is_contact && (vals.is_empty() || i - last >= 4) && angles[i] > 1.0 {
            vals.push(angles[i]);
            last = i;
        }
    }
    vals
}

/// Inclinação do tronco em relação à vertical (graus). 0° = ereto. Vetor quadril→ombro
/// comparado com o eixo vertical da imagem (y cresce pra baixo).
pub fn trunk_lean_deg(shoulder: (f32, f32), hip: (f32, f32)) -> f32 {
    let (dx, dy) = (shoulder.0 - hip.0, hip.1 - shoulder.1); // dy>0 com ombro acima do quadril
    if dy <= 0.0 {
        return 0.0;
    }
    dx.abs().atan2(dy).to_degrees()
}

/// mediana de uma série (robusta a frames ruins)
pub fn median(series: &[f32]) -> Option<f32> {
    if series.is_empty() {
        return None;
    }
    let mut v = series.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    Some(v[v.len() / 2])
}

/// Fases de APOIO de UM pé: máscara "no chão" (ankle_y nos 30% mais baixos da tela) e
/// as durações dos runs contíguos de apoio (>=2 frames, filtra ruído).
fn stance_runs(ankle_y: &[f32]) -> (Vec<usize>, Vec<bool>) {
    let n = ankle_y.len();
    if n < 8 {
        return (vec![], vec![false; n]);
    }
    let mut v = ankle_y.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p = |q: f32| v[(((n - 1) as f32) * q) as usize];
    let (p5, p95) = (p(0.05), p(0.95));
    let thr = p95 - 0.30 * (p95 - p5); // apoio = 30% inferior (mais fundo = chão)
    let down: Vec<bool> = ankle_y.iter().map(|&y| y >= thr).collect();
    let mut runs = Vec::new();
    let mut cur = 0usize;
    for &d in &down {
        if d {
            cur += 1;
        } else if cur > 0 {
            runs.push(cur);
            cur = 0;
        }
    }
    if cur > 0 {
        runs.push(cur);
    }
    runs.retain(|&r| r >= 2);
    (runs, down)
}

/// Tempo de contato com o solo (GCT) e tempo de voo, em ms, a partir do sinal vertical de solo
/// E/D. No COCO é o tornozelo; no BlazePose é calcanhar/ponta do pé quando confiáveis. GCT = média
/// das fases de apoio; voo = média das fases com AMBOS no ar.
pub fn contact_flight_ms(
    ground_l: &[f32],
    ground_r: &[f32],
    fps: f32,
) -> (Option<f32>, Option<f32>) {
    if fps <= 0.0 {
        return (None, None);
    }
    let to_ms = |frames: f32| (frames / fps * 1000.0 * 10.0).round() / 10.0;
    let (runs_l, down_l) = stance_runs(ground_l);
    let (runs_r, down_r) = stance_runs(ground_r);

    // Descarta apoios de duração IMPOSSÍVEL: um apoio de corrida dura ~60–500ms. Um "apoio" mais
    // longo é artefato (sinal achatado/vista não-lateral colapsa vários frames num run gigante) —
    // se entrasse na média, dava GCT absurdo (ex.: 2000ms). Na fonte, não deixa o número-lixo sair.
    let plausivel = |r: &usize| {
        let ms = *r as f32 / fps * 1000.0;
        (60.0..=500.0).contains(&ms)
    };
    let ok_l: Vec<usize> = runs_l.iter().copied().filter(|r| plausivel(r)).collect();
    let ok_r: Vec<usize> = runs_r.iter().copied().filter(|r| plausivel(r)).collect();

    let gct = if ok_l.len() >= 2 && ok_r.len() >= 2 {
        let all: Vec<usize> = ok_l.iter().chain(ok_r.iter()).copied().collect();
        Some(to_ms(all.iter().sum::<usize>() as f32 / all.len() as f32))
    } else {
        None
    };

    let n = down_l.len().min(down_r.len());
    let flight = if n >= 8 {
        let (mut runs, mut cur) = (Vec::new(), 0usize);
        for i in 0..n {
            if !down_l[i] && !down_r[i] {
                cur += 1;
            } else if cur > 0 {
                runs.push(cur);
                cur = 0;
            }
        }
        if cur > 0 {
            runs.push(cur);
        }
        if runs.len() >= 2 {
            Some(to_ms(runs.iter().sum::<usize>() as f32 / runs.len() as f32))
        } else {
            None
        }
    } else {
        None
    };

    (gct, flight)
}

/// Durações (ms) de cada apoio PLAUSÍVEL (60–500ms) de qualquer um dos pés — as mesmas amostras
/// que `contact_flight_ms` promedia pro GCT, expostas separadamente pra quem quiser o CV entre
/// apoios sem duplicar o filtro de plausibilidade.
pub fn stance_ms_samples(ground_l: &[f32], ground_r: &[f32], fps: f32) -> Vec<f32> {
    if fps <= 0.0 {
        return Vec::new();
    }
    let to_ms = |frames: f32| (frames / fps * 1000.0 * 10.0).round() / 10.0;
    let (runs_l, _) = stance_runs(ground_l);
    let (runs_r, _) = stance_runs(ground_r);
    let plausivel = |r: &usize| {
        let ms = *r as f32 / fps * 1000.0;
        (60.0..=500.0).contains(&ms)
    };
    runs_l
        .iter()
        .chain(runs_r.iter())
        .filter(|r| plausivel(r))
        .map(|&r| to_ms(r as f32))
        .collect()
}

/// Durações (ms) de cada intervalo de VOO (ambos os pés no ar) — as mesmas amostras que
/// `contact_flight_ms` promedia pro tempo de voo, expostas pra quem quiser o CV entre passadas.
pub fn flight_ms_samples(ground_l: &[f32], ground_r: &[f32], fps: f32) -> Vec<f32> {
    if fps <= 0.0 {
        return Vec::new();
    }
    let to_ms = |frames: f32| (frames / fps * 1000.0 * 10.0).round() / 10.0;
    let (_, down_l) = stance_runs(ground_l);
    let (_, down_r) = stance_runs(ground_r);
    let n = down_l.len().min(down_r.len());
    if n < 8 {
        return Vec::new();
    }
    let (mut runs, mut cur) = (Vec::new(), 0usize);
    for i in 0..n {
        if !down_l[i] && !down_r[i] {
            cur += 1;
        } else if cur > 0 {
            runs.push(cur);
            cur = 0;
        }
    }
    if cur > 0 {
        runs.push(cur);
    }
    runs.into_iter().map(|r| to_ms(r as f32)).collect()
}

/// Folga de medição no gate de consistência temporal. Acima de 1.0 = passo teórico; o excedente
/// tolera ruído de detecção. 1.15 separa captura boa (razão ~0.7) de captura com evento de solo
/// perdido (razão >1.3), sem rejeitar borderline honesto.
const TIMING_TOLERANCE: f32 = 1.15;

/// Invariante biomecânica: numa passada, o tempo de contato + o tempo de voo é ~a duração do PASSO
/// (contato de um pé → contato do outro), e NÃO pode exceder essa duração. Se GCT+voo estoura a
/// passada derivada da cadência, um evento de solo foi perdido e o voo inflou (ex.: video_corrida_23,
/// GCT+voo 498ms vs passo 361ms) — a temporização é não-confiável. `cadence<=0` → não dá pra checar.
pub fn timing_consistent_with_cadence(cadence_spm: f32, gct_ms: f32, flight_ms: f32) -> bool {
    if cadence_spm <= 0.0 {
        return true;
    }
    let step_ms = 60_000.0 / cadence_spm; // ms por passo
    (gct_ms + flight_ms) <= step_ms * TIMING_TOLERANCE
}

/// Ponto vertical que está mais próximo do solo em vista lateral (y cresce para baixo). No
/// contato inicial o calcanhar costuma vencer; no toe-off, a ponta. O máximo preserva ambos sem
/// precisar inferir um evento clínico a partir de um único frame.
pub fn foot_ground_y(heel_y: f32, toe_y: f32) -> f32 {
    heel_y.max(toe_y)
}

/// Padrão de pisada ESTIMADO pela posição do tornozelo × joelho no apoio (proxy da tíbia —
/// não há keypoint de pé). `facing_dir` = sinal de (nariz − quadril) pra saber "pra frente".
/// Tornozelo à frente do joelho no toque = passada longa → calcanhar.
pub fn foot_strike(
    ankle_x: &[f32],
    ankle_y: &[f32],
    knee_x: &[f32],
    facing_dir: f32,
    leg_len_px: f32,
) -> Option<&'static str> {
    let n = ankle_x.len().min(ankle_y.len()).min(knee_x.len());
    if n < 12 || leg_len_px <= 0.0 || facing_dir == 0.0 {
        return None;
    }
    let (mut offs, mut last) = (Vec::new(), 0usize);
    for i in 1..n - 1 {
        let contact = ankle_y[i] >= ankle_y[i - 1] && ankle_y[i] > ankle_y[i + 1];
        if contact && (offs.is_empty() || i - last >= 4) {
            offs.push((ankle_x[i] - knee_x[i]) * facing_dir.signum() / leg_len_px);
            last = i;
        }
    }
    if offs.len() < 2 {
        return None;
    }
    let avg = offs.iter().sum::<f32>() / offs.len() as f32;
    Some(if avg > 0.10 {
        "calcanhar"
    } else if avg < -0.06 {
        "antepé"
    } else {
        "médio"
    })
}

// ---------- plano FRONTAL (queda pélvica + valgo de joelho) ----------

/// Percentil q (0..1) de uma série (robusto). None se curta demais.
pub fn percentile(series: &[f32], q: f32) -> Option<f32> {
    if series.len() < 8 {
        return None;
    }
    let mut v = series.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    Some(v[((v.len() - 1) as f32 * q.clamp(0.0, 1.0)) as usize])
}

/// Inclinação da LINHA DO QUADRIL (kp11–kp12) em relação à horizontal, em graus (0 = bacia
/// nivelada). Por frame; a queda pélvica é o pico dessa inclinação no apoio (ver percentile).
pub fn hip_tilt_deg(hip_l: (f32, f32, f32), hip_r: (f32, f32, f32)) -> f32 {
    let (dx, dy) = ((hip_r.0 - hip_l.0).abs(), (hip_r.1 - hip_l.1).abs());
    if dx == 0.0 && dy == 0.0 {
        return 0.0;
    }
    dy.atan2(dx).to_degrees()
}

/// Valgo dinâmico (FPPA) a partir da série do ângulo FRONTAL do joelho (quadril–joelho–
/// tornozelo). Perna alinhada ~180°; joelho caindo pra dentro derruba o ângulo → valgo sobe.
/// Usa a MEDIANA (a corrida passa a maior parte em apoio) pra estabilidade. None se curta.
pub fn knee_valgus_deg(knee_angle_series: &[f32]) -> Option<f32> {
    median(knee_angle_series).map(|m| ((180.0 - m).max(0.0) * 10.0).round() / 10.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// série senoidal: pé oscilando a `hz` filmado a `fps`
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

    /// sinal de apoio: `air` frames no ar (y baixo) + `ground` frames no chão (y alto), repetido.
    fn stance_signal(air: usize, ground: usize, cycles: usize) -> Vec<f32> {
        let mut v = Vec::new();
        for _ in 0..cycles {
            v.extend(std::iter::repeat(10.0).take(air));
            v.extend(std::iter::repeat(100.0).take(ground));
        }
        v
    }

    #[test]
    fn gct_plausivel_em_sinal_normal() {
        // apoios de 6 frames @25fps = 240ms
        let s = stance_signal(6, 6, 8);
        let (gct, _) = contact_flight_ms(&s, &s, 25.0);
        let g = gct.expect("devia calcular gct");
        assert!((60.0..=500.0).contains(&g), "gct fora do plausível: {g}");
    }

    #[test]
    fn sinal_do_pe_usa_o_ponto_mais_baixo_no_frame() {
        assert_eq!(foot_ground_y(120.0, 105.0), 120.0); // heel-strike
        assert_eq!(foot_ground_y(100.0, 130.0), 130.0); // toe-off
    }

    #[test]
    fn timing_gate_rejeita_gct_mais_voo_maior_que_a_passada() {
        // laisa real: passo ~362ms, GCT+voo 252ms (razão 0.70) -> consistente
        assert!(timing_consistent_with_cadence(165.9, 142.5, 109.1));
        // video_corrida_23 real: passo ~361ms, GCT+voo 498ms (razão 1.38, voo inflado) -> rejeita
        assert!(!timing_consistent_with_cadence(166.0, 217.7, 280.8));
        // sem cadência não dá pra checar -> não rejeita à toa
        assert!(timing_consistent_with_cadence(0.0, 500.0, 500.0));
    }

    #[test]
    fn gct_descarta_apoio_impossivel() {
        // sinal quase todo "no chão" (vista ruim) -> apoios gigantes -> descartados, gct None
        let mut s = vec![100.0f32; 200];
        for i in (0..200).step_by(50) {
            s[i] = 10.0;
        }
        let (gct, _) = contact_flight_ms(&s, &s, 25.0);
        assert!(
            gct.is_none(),
            "apoio impossível deveria virar None, veio {gct:?}"
        );
    }

    #[test]
    fn assimetria_nula_na_lateral_perna_ocluida() {
        // Na LATERAL a perna de trás é ocluída -> assimetria bilateral não é medível (seria
        // fantasma, ~40%, inflando o risco). Deve ser None; a oscilação vertical segue medida.
        let l = sine(1.4, 30.0, 16.0, 20.0);
        let r = sine(1.4, 30.0, 16.0, 14.0); // amplitudes diferentes (oclusão)
        let m = analyze_form(
            &l,
            &r,
            &sine(2.8, 30.0, 16.0, 4.0),
            100.0,
            30.0,
            480,
            "lateral",
            true,
        );
        assert!(
            m.asymmetry_pct.is_none(),
            "assimetria deve ser None na lateral"
        );
        assert!(m.vertical_oscillation_pct.unwrap() > 5.0);
    }

    #[test]
    fn series_curtas_degradam_gracioso() {
        let m = analyze_form(
            &[1.0; 4], &[1.0; 4], &[1.0; 4], 100.0, 30.0, 4, "lateral", true,
        );
        assert!(m.cadence_spm.is_none() && m.asymmetry_pct.is_none());
    }

    #[test]
    fn lateral_com_perna_ocluida_ainda_confia() {
        // vista LATERAL: perna de frente clara (amp grande, 1.4Hz), perna de trás OCLUÍDA
        // (amp menor, cadência com erro de oitava, 0.7Hz). A oscilação vertical plausível
        // confirma que é lateral → confia, e a cadência vem da perna VISÍVEL (~168 spm),
        // não da média com a ocluída.
        let near = sine(1.4, 25.0, 16.0, 20.0);
        let far = sine(0.7, 25.0, 16.0, 6.0);
        let m = analyze_form(
            &near,
            &far,
            &sine(2.8, 25.0, 16.0, 8.0),
            100.0,
            25.0,
            near.len(),
            "lateral",
            true,
        );
        assert!(
            m.reliable && m.quality_note.is_none(),
            "lateral com oclusão deve ser confiável"
        );
        assert!(
            m.cadence_spm.unwrap() > 150.0,
            "cadência deve vir da perna visível, veio {:?}",
            m.cadence_spm
        );
    }

    #[test]
    fn guard_descarta_oscilacao_vertical_absurda() {
        // hip_y com amplitude enorme vs perna curta (vista frontal) -> osc. vertical implausível
        let l = sine(1.4, 25.0, 16.0, 20.0);
        let m = analyze_form(
            &l,
            &l,
            &sine(2.8, 25.0, 16.0, 500.0),
            100.0,
            25.0,
            l.len(),
            "lateral",
            true,
        );
        assert!(m.vertical_oscillation_pct.is_none() && !m.reliable);
    }

    #[test]
    fn boa_entrada_e_confiavel() {
        let l = sine(1.4, 25.0, 16.0, 20.0);
        let m = analyze_form(
            &l,
            &l,
            &sine(2.8, 25.0, 16.0, 8.0),
            100.0,
            25.0,
            l.len(),
            "lateral",
            true,
        );
        assert!(m.reliable && m.vertical_oscillation_pct.is_some() && m.quality_note.is_none());
    }

    #[test]
    fn video_curto_demais_rejeita() {
        // 8s @25fps = 200 frames < 15s -> too_short, não analisa
        let s = sine(1.4, 25.0, 8.0, 20.0);
        let m = analyze_form(&s, &s, &s, 100.0, 25.0, s.len(), "lateral", true);
        assert!(!m.reliable && m.reason == "too_short" && m.cadence_spm.is_none());
    }

    #[test]
    fn tronco_fora_do_quadro_rejeita_com_motivo_certo() {
        // tornozelos cheios (detecção ok) mas quadril confiável em POUCOS frames (tronco fora) ->
        // motivo 'torso_not_visible', não o enganoso 'not_lateral'
        let ankles = sine(1.4, 25.0, 16.0, 20.0); // 400 frames (>15s)
        let hip_sparse = vec![100.0f32; 40]; // 40/400 < 0.5
        let m = analyze_form(
            &ankles,
            &ankles,
            &hip_sparse,
            100.0,
            25.0,
            ankles.len(),
            "lateral",
            true,
        );
        assert!(!m.reliable && m.reason == "torso_not_visible");
    }

    #[test]
    fn contato_mede_o_angulo_na_fase_de_apoio() {
        // tornozelo oscila (y máx = apoio). No apoio o joelho está em ~160°; no voo, ~90°.
        let ankle = sine(1.4, 30.0, 6.0, 20.0);
        let knee: Vec<f32> = ankle
            .iter()
            .map(|&y| if y > 0.0 { 160.0 } else { 90.0 })
            .collect();
        let a = contact_angle(&knee, &ankle).expect("deve achar apoios");
        assert!((a - 160.0).abs() < 5.0, "esperava ~160° no apoio, veio {a}");
    }

    #[test]
    fn contato_serie_curta_devolve_none() {
        assert!(contact_angle(&[150.0; 5], &[1.0; 5]).is_none());
    }

    #[test]
    fn gct_e_voo_de_series_conhecidas() {
        // dois pés em contra-fase a 1.5 Hz, 30fps: há apoio em cada pé e momentos de voo
        let l = sine(1.5, 30.0, 6.0, 20.0);
        let r: Vec<f32> = l.iter().map(|&y| -y).collect(); // fase oposta
        let (gct, flight) = contact_flight_ms(&l, &r, 30.0);
        assert!(gct.is_some(), "GCT deveria existir");
        assert!(
            gct.unwrap() > 0.0 && gct.unwrap() < 1000.0,
            "GCT plausível, veio {:?}",
            gct
        );
        assert!(flight.is_some(), "voo deveria existir");
    }

    #[test]
    fn gct_serie_curta_none() {
        let (g, f) = contact_flight_ms(&[1.0; 6], &[1.0; 6], 30.0);
        assert!(g.is_none() && f.is_none());
    }

    #[test]
    fn pisada_tornozelo_a_frente_e_calcanhar() {
        // tornozelo oscila (apoio no y máx); no apoio fica 30px À FRENTE do joelho
        let ankle_y = sine(1.4, 30.0, 6.0, 20.0);
        let knee_x = vec![100.0; ankle_y.len()];
        let ankle_x: Vec<f32> = ankle_y
            .iter()
            .map(|&y| if y > 0.0 { 130.0 } else { 100.0 })
            .collect();
        // facing_dir positivo (corre pra +x), perna 200px
        assert_eq!(
            foot_strike(&ankle_x, &ankle_y, &knee_x, 1.0, 200.0),
            Some("calcanhar")
        );
    }

    #[test]
    fn tronco_ereto_e_inclinado() {
        // ombro exatamente acima do quadril = 0°
        assert!(trunk_lean_deg((100.0, 0.0), (100.0, 100.0)).abs() < 0.5);
        // ombro deslocado 100px pra frente sobre 100px de altura = 45°
        assert!((trunk_lean_deg((200.0, 0.0), (100.0, 100.0)) - 45.0).abs() < 0.5);
    }

    // ---------- plano frontal ----------

    #[test]
    fn hip_tilt_bacia_nivelada_e_zero() {
        // quadris na mesma altura (y igual) = bacia nivelada = 0°
        assert!(hip_tilt_deg((100.0, 200.0, 1.0), (160.0, 200.0, 1.0)).abs() < 0.5);
        // 60px de largura, 60px de queda = 45°
        assert!((hip_tilt_deg((100.0, 200.0, 1.0), (160.0, 260.0, 1.0)) - 45.0).abs() < 0.5);
    }

    #[test]
    fn knee_valgus_perna_alinhada_e_zero_valgo_alto() {
        // perna alinhada (ângulo ~180°) -> valgo ~0
        assert!(knee_valgus_deg(&[179.0; 20]).unwrap() < 2.0);
        // joelho caindo pra dentro (ângulo 160°) -> valgo ~20°
        assert!((knee_valgus_deg(&[160.0; 20]).unwrap() - 20.0).abs() < 1.0);
    }

    #[test]
    fn frontal_confia_com_duas_pernas_recusa_com_uma() {
        let s = sine(1.0, 25.0, 16.0, 5.0); // série qualquer (>15s), boa detecção
                                            // as duas pernas visíveis -> confiável (métricas sagitais None)
        let ok = analyze_form(&s, &s, &s, 100.0, 25.0, s.len(), "frontal", true);
        assert!(ok.reliable && ok.cadence_spm.is_none() && ok.view.as_deref() == Some("frontal"));
        // uma perna ocluída (both_legs_ok=false) -> recusa com nota de vista frontal
        let bad = analyze_form(&s, &s, &s, 100.0, 25.0, s.len(), "frontal", false);
        assert!(!bad.reliable && bad.quality_note.unwrap().to_lowercase().contains("frente"));
    }

    // ---------- confiança/CV por métrica (metric_confidence / metric_cv) ----------

    #[test]
    fn confianca_alta_quando_todos_os_frames_sao_confiaveis() {
        // (a) keypoints sempre confiáveis -> metric_confidence == 1.0
        let flags = vec![true; 50];
        assert_eq!(confidence_fraction(&flags), 1.0);
    }

    #[test]
    fn confianca_meio_a_meio_fica_perto_de_0_5() {
        // (b) metade dos frames de baixa confiança -> metric_confidence ~0.5
        let mut flags = vec![true; 20];
        flags.extend(vec![false; 20]);
        assert!((confidence_fraction(&flags) - 0.5).abs() < 1e-6);
    }

    #[test]
    fn confianca_vazia_e_zero_nao_pane() {
        assert_eq!(confidence_fraction(&[]), 0.0);
    }

    #[test]
    fn cv_baixo_com_amostras_estaveis() {
        // (c) amostras quase idênticas (ex.: ângulo de joelho estável apoio a apoio) -> CV baixo
        let samples = vec![160.0, 160.5, 159.8, 160.2, 160.1];
        let cv = coefficient_of_variation(&samples).expect("devia calcular CV");
        assert!(cv < 0.02, "CV deveria ser baixo p/ amostras estáveis, veio {cv}");
    }

    #[test]
    fn cv_alto_com_amostras_dispersas() {
        // (d) amostras bem dispersas (rastreio ruim / passadas inconsistentes) -> CV alto
        let samples = vec![100.0, 20.0, 180.0, 40.0, 150.0];
        let cv = coefficient_of_variation(&samples).expect("devia calcular CV");
        assert!(cv > 0.3, "CV deveria ser alto p/ amostras dispersas, veio {cv}");
    }

    #[test]
    fn cv_precisa_de_pelo_menos_duas_amostras() {
        assert!(coefficient_of_variation(&[160.0]).is_none());
        assert!(coefficient_of_variation(&[]).is_none());
    }

    #[test]
    fn contact_angle_samples_alimenta_o_mesmo_valor_que_contact_angle() {
        // as amostras cruas devem ser consistentes com a média que contact_angle expõe
        let ankle = sine(1.4, 30.0, 6.0, 20.0);
        let knee: Vec<f32> = ankle
            .iter()
            .map(|&y| if y > 0.0 { 160.0 } else { 90.0 })
            .collect();
        let samples = contact_angle_samples(&knee, &ankle);
        let mean = samples.iter().sum::<f32>() / samples.len() as f32;
        let a = contact_angle(&knee, &ankle).unwrap();
        assert!(samples.len() >= 2);
        assert!((mean - a).abs() < 0.2, "média das amostras {mean} != contact_angle {a}");
    }

    #[test]
    fn stance_e_flight_ms_samples_tem_media_igual_ao_contact_flight_ms() {
        let l = sine(1.5, 30.0, 6.0, 20.0);
        let r: Vec<f32> = l.iter().map(|&y| -y).collect();
        let (gct, flight) = contact_flight_ms(&l, &r, 30.0);
        let stance = stance_ms_samples(&l, &r, 30.0);
        let fl = flight_ms_samples(&l, &r, 30.0);
        assert!(!stance.is_empty(), "devia ter amostras de apoio");
        assert!(!fl.is_empty(), "devia ter amostras de voo");
        let mean_stance = stance.iter().sum::<f32>() / stance.len() as f32;
        let mean_flight = fl.iter().sum::<f32>() / fl.len() as f32;
        assert!((mean_stance - gct.unwrap()).abs() < 1.0);
        assert!((mean_flight - flight.unwrap()).abs() < 1.0);
    }

    #[test]
    fn serializacao_json_inclui_metric_confidence_e_metric_cv_sem_quebrar_schema() {
        // (e) serialização JSON: os dois mapas novos aparecem, e os campos antigos continuam lá
        let l = sine(1.4, 25.0, 16.0, 20.0);
        let mut m = analyze_form(
            &l,
            &l,
            &sine(2.8, 25.0, 16.0, 8.0),
            100.0,
            25.0,
            l.len(),
            "lateral",
            true,
        );
        m.metric_confidence.insert("cadence_spm".to_string(), 0.92);
        m.metric_confidence.insert("knee_contact_deg".to_string(), 0.5);
        m.metric_cv.insert("knee_contact_deg".to_string(), 0.04);

        let json = serde_json::to_value(&m).expect("deve serializar");
        assert!((json["metric_confidence"]["cadence_spm"].as_f64().unwrap() - 0.92).abs() < 1e-4);
        assert_eq!(json["metric_confidence"]["knee_contact_deg"], 0.5);
        assert!((json["metric_cv"]["knee_contact_deg"].as_f64().unwrap() - 0.04).abs() < 1e-4);
        // schema antigo continua presente e coerente (aditivo, não quebrou nada)
        assert_eq!(json["reliable"], true);
        assert!(json["cadence_spm"].is_number());
        assert!(json["vertical_oscillation_pct"].is_number());
        // métrica nunca computada nesta corrida (frontal-only) fica AUSENTE, não zero
        assert!(json["metric_confidence"].get("pelvic_drop_deg").is_none());
    }
}
