//! rust_kernel — o nucleo de calculo numerico do StriderEdge OS.
//!
//! Divisao de trabalho do projeto:
//!   - Python  -> I/O, rede, banco de dados, API (as partes "lentas" sao I/O mesmo).
//!   - Rust    -> matematica pesada e sequencial (Kalman, DTW, FFT), onde o GIL
//!                do Python trava e o loop puro e lento.
//!
//! FATIA 0: por enquanto so existe UMA funcao trivial (`mean_heart_rate`).
//! O objetivo nao e o algoritmo, e provar que a ponte Python<->Rust compila,
//! importa e que dados cruzam a fronteira. Os algoritmos reais vem na Fatia 2.

// `use` = igual ao `import` do Python. `pyo3::prelude` e um pacote com os nomes
// mais usados da biblioteca pyo3; `::*` significa "traga tudo".
use pyo3::prelude::*;

// `mod ...;` declara modulos que vivem em arquivos irmaos (kalman.rs, dtw.rs, fft.rs).
mod dtw;
mod fft;
mod kalman;

/// Media aritmetica de uma serie de numeros (ex: frequencia cardiaca).
///
/// `#[pyfunction]` e um atributo (parecido com um @decorator do Python, mas em
/// tempo de compilacao) que manda a pyo3 gerar a "cola" que converte os tipos
/// Python <-> Rust automaticamente.
#[pyfunction]
fn mean_heart_rate(samples: Vec<f64>) -> PyResult<f64> {
    // `samples: Vec<f64>` recebido POR VALOR (sem `&`): a funcao toma POSSE da
    // lista. Ao terminar, o Vec e liberado da memoria automaticamente — sem
    // garbage collector, Rust libera no momento certo.

    // Protege contra divisao por zero. `.is_empty()` devolve true se nao ha itens.
    if samples.is_empty() {
        return Ok(0.0); // `Ok(...)` embrulha o valor no caso de SUCESSO do Result.
    }

    // `let` cria variavel (imutavel por padrao em Rust).
    // `.iter()` cria um iterador que EMPRESTA cada elemento (&f64) sem consumir
    // o vetor. `.sum()` soma tudo; o `: f64` diz ao compilador o tipo do total.
    let sum: f64 = samples.iter().sum();

    // `.len()` devolve a quantidade de itens como `usize` (inteiro do tamanho da
    // maquina). `as f64` e uma conversao EXPLICITA — Rust nao converte numero
    // sozinho. Sem o `as f64`, dividir f64 por usize nem compilaria.
    Ok(sum / samples.len() as f64)
}

/// Suaviza uma trilha de GPS com filtro de Kalman, tirando o tremor do sinal.
///
/// Recebe latitudes e longitudes (em graus) e devolve uma TUPLA `(lat, lon)`
/// suavizadas — a pyo3 converte `(Vec<f64>, Vec<f64>)` num `tuple` do Python.
/// `process_noise` e `measurement_noise` controlam o quanto confiar no modelo
/// vs. no GPS (passados do Python para podermos calibrar).
#[pyfunction]
fn smooth_gps(
    latitudes: Vec<f64>,
    longitudes: Vec<f64>,
    dt: f64,
    process_noise: f64,
    measurement_noise: f64,
) -> PyResult<(Vec<f64>, Vec<f64>)> {
    // `&latitudes` empresta o Vec como slice `&[f64]` para a funcao de suavizacao,
    // sem copiar nem ceder posse.
    let smooth_lat = kalman::smooth_series(&latitudes, dt, process_noise, measurement_noise);
    let smooth_lon = kalman::smooth_series(&longitudes, dt, process_noise, measurement_noise);
    Ok((smooth_lat, smooth_lon))
}

/// Compara dois esforcos com Dynamic Time Warping.
///
/// Devolve uma TUPLA `(distancia, caminho)`: o caminho e uma lista de pares
/// (i, j) dizendo qual ponto da serie A casa com qual da serie B. A pyo3
/// converte `(f64, Vec<(usize, usize)>)` num `(float, list[tuple])` do Python.
#[pyfunction]
fn compare_efforts(
    series_a: Vec<f64>,
    series_b: Vec<f64>,
) -> PyResult<(f64, Vec<(usize, usize)>)> {
    let result = dtw::dtw(&series_a, &series_b);
    Ok((result.distance, result.path))
}

/// Analisa o espectro de frequencias de um sinal (ex: cadencia ao longo do tempo).
///
/// Devolve `(frequencias, magnitudes, frequencia_dominante)`. A pyo3 traduz a
/// tupla `(Vec<f64>, Vec<f64>, f64)` para `(list, list, float)` no Python.
/// Nao expomos a struct Spectrum porque o Python nao conhece tipos Rust.
#[pyfunction]
fn cadence_spectrum(
    samples: Vec<f64>,
    sample_rate_hz: f64,
) -> PyResult<(Vec<f64>, Vec<f64>, f64)> {
    let result = fft::spectrum(&samples, sample_rate_hz);
    Ok((result.frequencies, result.magnitudes, result.dominant_frequency))
}

/// Funcao que REGISTRA o modulo Python. O nome dela (`rust_kernel`) precisa ser
/// igual ao nome do modulo que o Python vai importar.
///
/// `m: &Bound<'_, PyModule>`:
///   - `&`            -> referencia EMPRESTADA: usamos o modulo mas nao somos
///                       donos dele (quem e dona e a pyo3).
///   - `Bound<...>`   -> objeto Python amarrado ao interpretador.
///   - `'_`           -> lifetime anonima: o compilador garante que o emprestimo
///                       nao vive mais que o objeto original (sem ponteiro solto).
/// `-> PyResult<()>`  -> retorna sucesso ou erro, sem valor util. `()` e o tipo
///                       "unit", equivalente ao None/void.
#[pymodule]
fn rust_kernel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // `wrap_pyfunction!` (o `!` indica MACRO) embrulha a funcao Rust num objeto
    // que o Python entende. O primeiro `?` propaga erro se o embrulho falhar.
    // `m.add_function(...)` anexa a funcao ao modulo; o segundo `?` propaga erro.
    m.add_function(wrap_pyfunction!(mean_heart_rate, m)?)?;
    m.add_function(wrap_pyfunction!(smooth_gps, m)?)?;
    m.add_function(wrap_pyfunction!(compare_efforts, m)?)?;
    m.add_function(wrap_pyfunction!(cadence_spectrum, m)?)?;
    Ok(()) // sucesso "vazio": registro concluido.
}
