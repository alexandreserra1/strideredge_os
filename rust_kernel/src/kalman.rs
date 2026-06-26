//! kalman.rs — filtro de Kalman 1D com modelo de VELOCIDADE CONSTANTE (CV).
//!
//! Tira o tremor do GPS da Garmin SEM atrasar nas curvas, porque modela tambem
//! a velocidade: a predicao "empurra" a posicao na direcao em que voce vinha
//! andando. E o mesmo motor que dados de IMU (dispositivo no pe) vao exigir.
//!
//! Estado:        x = [posicao, velocidade]            (vetor 2x1)
//! Covariancia:   P = [[p00, p01], [p10, p11]]         (matriz 2x2)
//! Transicao:     F = [[1, dt], [0, 1]]
//! Medicao:       H = [1, 0]   (so observamos a posicao)
//!
//! Em vez de uma lib de matrizes, expandimos cada operacao 2x2 em escalares —
//! mais codigo, mas voce ve a matematica acontecendo campo a campo.

/// Filtro CV para UMA dimensao (ex: latitude). Para lat+lon usamos dois.
pub struct KalmanFilterCV {
    // --- estado x ---
    position: f64,
    velocity: f64,
    // --- covariancia P (2x2), guardada como 4 escalares ---
    p00: f64, // var(posicao)
    p01: f64, // cov(posicao, velocidade)
    p10: f64, // cov(velocidade, posicao)  (= p01, mas guardamos os dois)
    p11: f64, // var(velocidade)
    // --- parametros de ruido ---
    dt: f64,                // passo de tempo entre amostras (1s no Garmin)
    process_noise: f64,     // intensidade do ruido de processo (q)
    measurement_noise: f64, // ruido da medida do GPS (R)
}

impl KalmanFilterCV {
    /// Construtor. Comeca parado (velocidade 0) e bem incerto (P grande).
    pub fn new(
        initial_position: f64,
        dt: f64,
        process_noise: f64,
        measurement_noise: f64,
    ) -> Self {
        Self {
            position: initial_position,
            velocity: 0.0,
            p00: 1.0,
            p01: 0.0,
            p10: 0.0,
            p11: 1.0,
            dt,
            process_noise,
            measurement_noise,
        }
    }

    /// Processa UMA medida (posicao observada) e devolve a estimativa suavizada.
    /// `&mut self`: o metodo ALTERA os campos da struct.
    pub fn update(&mut self, measurement: f64) -> f64 {
        let dt = self.dt;

        // ================= 1) PREDICAO =================
        // x' = F x  ->  pos avanca pela velocidade; vel constante.
        self.position += self.velocity * dt;
        // (velocity nao muda na predicao do modelo CV)

        // P' = F P F^T + Q
        // Primeiro FP = F * P, com F = [[1, dt], [0, 1]]:
        let fp00 = self.p00 + dt * self.p10;
        let fp01 = self.p01 + dt * self.p11;
        let fp10 = self.p10;
        let fp11 = self.p11;
        // Agora (FP) * F^T, com F^T = [[1, 0], [dt, 1]]:
        let mut p00 = fp00 + dt * fp01;
        let mut p01 = fp01;
        let mut p10 = fp10 + dt * fp11;
        let mut p11 = fp11;

        // + Q (ruido de processo, modelo de aceleracao branca):
        //   Q = q * [[dt^4/4, dt^3/2], [dt^3/2, dt^2]]
        let q = self.process_noise;
        let dt2 = dt * dt;
        let dt3 = dt2 * dt;
        let dt4 = dt3 * dt;
        p00 += q * dt4 / 4.0;
        p01 += q * dt3 / 2.0;
        p10 += q * dt3 / 2.0;
        p11 += q * dt2;

        // ================= 2) CORRECAO =================
        // Inovacao S = H P H^T + R = p00 + R  (so observamos a posicao).
        let s = p00 + self.measurement_noise;
        // Ganho de Kalman K = P H^T / S = [p00/s, p10/s].
        let k0 = p00 / s;
        let k1 = p10 / s;

        // Residual (inovacao): diferenca entre medida e predicao.
        let residual = measurement - self.position;
        // x = x + K * residual
        self.position += k0 * residual;
        self.velocity += k1 * residual;

        // P = (I - K H) P, com K H = [[k0, 0], [k1, 0]]:
        //   I - K H = [[1 - k0, 0], [-k1, 1]]
        let new_p00 = (1.0 - k0) * p00;
        let new_p01 = (1.0 - k0) * p01;
        let new_p10 = -k1 * p00 + p10;
        let new_p11 = -k1 * p01 + p11;
        self.p00 = new_p00;
        self.p01 = new_p01;
        self.p10 = new_p10;
        self.p11 = new_p11;

        self.position // ultima expressao sem `;` = valor de retorno
    }
}

/// Suaviza uma serie inteira de uma dimensao.
///
/// `series: &[f64]` = SLICE: janela EMPRESTADA sobre os numeros, sem copiar nem
/// tomar posse. Retorna um `Vec<f64>` novo (possuido pelo chamador).
pub fn smooth_series(
    series: &[f64],
    dt: f64,
    process_noise: f64,
    measurement_noise: f64,
) -> Vec<f64> {
    if series.is_empty() {
        return Vec::new();
    }
    let mut filter = KalmanFilterCV::new(series[0], dt, process_noise, measurement_noise);
    // `.iter()` empresta cada &f64; `.map` transforma; `.collect` junta num Vec.
    // `*value` desreferencia o &f64 para obter o f64.
    series.iter().map(|value| filter.update(*value)).collect()
}
