//! dtw.rs — Dynamic Time Warping: compara duas series temporais permitindo
//! "esticar/encolher" o tempo, e mede o quao parecidas elas sao.
//!
//! Uso no projeto: comparar dois esforcos (corrida de hoje vs. um PR no mesmo
//! percurso), mesmo que voce tenha largado em ritmos diferentes.
//!
//! Custo: O(n*m). E uma matriz inteira de contas — doloroso em Python puro,
//! rapido em Rust.

/// Resultado do DTW: a distancia total e o caminho de alinhamento.
pub struct DtwResult {
    pub distance: f64,                 // quao diferentes sao as series (0 = identicas)
    pub path: Vec<(usize, usize)>,     // pares (i, j): ponto i de A casa com ponto j de B
}

/// Calcula o DTW entre duas series.
///
/// `a: &[f64]` e `b: &[f64]` = SLICES emprestados (sem copiar nem tomar posse).
pub fn dtw(a: &[f64], b: &[f64]) -> DtwResult {
    let n = a.len();
    let m = b.len();

    // Caso de borda: serie vazia -> distancia 0 e caminho vazio.
    if n == 0 || m == 0 {
        return DtwResult { distance: 0.0, path: Vec::new() };
    }

    // Matriz de custo acumulado (n x m). `vec![v; k]` cria k copias de v.
    // `f64::INFINITY` marca celulas ainda nao alcancaveis.
    let mut cost = vec![vec![f64::INFINITY; m]; n];

    // Celula inicial: so a diferenca dos primeiros pontos.
    cost[0][0] = (a[0] - b[0]).abs();

    // Primeira coluna e primeira linha: so existe um caminho ate elas.
    for i in 1..n {
        cost[i][0] = cost[i - 1][0] + (a[i] - b[0]).abs();
    }
    for j in 1..m {
        cost[0][j] = cost[0][j - 1] + (a[0] - b[j]).abs();
    }

    // Miolo da matriz: cada celula = diferenca local + menor vizinho anterior.
    for i in 1..n {
        for j in 1..m {
            let diagonal = cost[i - 1][j - 1]; // avanca nas duas series
            let up = cost[i - 1][j];           // "segura" B, avanca A
            let left = cost[i][j - 1];          // "segura" A, avanca B
            let best_prev = diagonal.min(up).min(left);
            cost[i][j] = (a[i] - b[j]).abs() + best_prev;
        }
    }

    // --- BACKTRACK: reconstroi o caminho do canto final ate a origem ---
    let mut path = Vec::new();
    let (mut i, mut j) = (n - 1, m - 1);
    path.push((i, j));
    while i > 0 || j > 0 {
        if i == 0 {
            j -= 1; // grudado na primeira linha: so da pra ir pra esquerda
        } else if j == 0 {
            i -= 1; // grudado na primeira coluna: so da pra ir pra cima
        } else {
            // escolhe o vizinho de menor custo (diagonal, cima, esquerda).
            let diagonal = cost[i - 1][j - 1];
            let up = cost[i - 1][j];
            let left = cost[i][j - 1];
            let best = diagonal.min(up).min(left);
            if best == diagonal {
                i -= 1;
                j -= 1;
            } else if best == up {
                i -= 1;
            } else {
                j -= 1;
            }
        }
        path.push((i, j));
    }
    path.reverse(); // construimos do fim pro comeco; invertemos pra ordem natural

    DtwResult { distance: cost[n - 1][m - 1], path }
}
