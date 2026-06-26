//! fft.rs — analise espectral (Transformada Rapida de Fourier) de um sinal.
//!
//! Uso no projeto: a cadencia ao longo do tempo e um sinal. A FFT o decompoe em
//! frequencias — cadencia estavel concentra energia numa frequencia; "arrastar a
//! passada" espalha energia. Revela padroes que a media movel nao captura.

// Bloco 1 — imports. `{ }` agrupa imports da mesma origem (= from x import a, b).
// `num_complex::Complex` vem de um sub-modulo que a rustfft reexporta (`::` = `.`).
use rustfft::{num_complex::Complex, FftPlanner};

// Bloco 2 — struct de retorno (= um @dataclass). `pub` expoe pra fora do modulo;
// precisa estar na caixa E em cada campo.
pub struct Spectrum {
    pub frequencies: Vec<f64>,        // = list[float]
    pub magnitudes: Vec<f64>,
    pub dominant_frequency: f64,
}

/// Bloco 3 — assinatura. `&[f64]` = "me EMPRESTA os numeros so pra ler"
/// (em Python a lista ja chega por referencia; aqui declaramos a intencao).
pub fn spectrum(samples: &[f64], sample_rate_hz: f64) -> Spectrum {
    // Bloco 4 — guarda de borda + media.
    let n = samples.len();
    if n == 0 {
        return Spectrum { frequencies: Vec::new(), magnitudes: Vec::new(), dominant_frequency: 0.0 };
    }
    // Remove o nivel medio (DC) senao a frequencia 0 domina e esconde o resto.
    // `sum::<f64>()` = sum(...) somando como f64; `n as f64` = conversao int->float.
    let mean: f64 = samples.iter().sum::<f64>() / n as f64;

    // Bloco 5 — montar e rodar a FFT.
    // `mut` porque o planner muda de estado ao planejar.
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(n);
    // `.map(...).collect()` = list comprehension; `|&x|` desembrulha a referencia.
    // Sinal entra como complexo (parte imaginaria 0), ja sem a media.
    let mut buffer: Vec<Complex<f64>> =
        samples.iter().map(|&x| Complex::new(x - mean, 0.0)).collect();
    // FFT roda IN-PLACE: modifica o buffer, por isso `&mut` (emprestimo mutavel).
    fft.process(&mut buffer);

    // Bloco 6 — extrair frequencias e magnitudes (sinal real e simetrico: metade basta).
    let half = n / 2;
    let mut frequencies = Vec::with_capacity(half); // reserva espaco (otimizacao)
    let mut magnitudes = Vec::with_capacity(half);
    for k in 0..half {
        // frequencia do bin k = k * (taxa / N).
        frequencies.push(k as f64 * sample_rate_hz / n as f64);
        // magnitude = modulo do complexo = energia naquela frequencia.
        magnitudes.push(buffer[k].norm());
    }

    // Bloco 7 — frequencia dominante (maior magnitude, pulando k=0/DC).
    let mut dominant_frequency = 0.0;
    let mut best_mag = 0.0;
    for k in 1..half {
        if magnitudes[k] > best_mag {
            best_mag = magnitudes[k];
            dominant_frequency = frequencies[k];
        }
    }

    // Bloco 8 — ultima expressao SEM `;` = valor de retorno. Atalho: campo com
    // mesmo nome da variavel nao precisa repetir (`frequencies` = `frequencies: frequencies`).
    Spectrum { frequencies, magnitudes, dominant_frequency }
}
