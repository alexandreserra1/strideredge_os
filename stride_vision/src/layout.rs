//! layout.rs — layout de keypoints (COCO-17 hoje; Halpe26 plugável, ver README-KEYPOINTS.md).
//!
//! TUDO que dependia de "são 17 keypoints" vive AQUI, num só lugar: quantos são, os nomes, o
//! esqueleto de desenho e — o que a biomecânica realmente consome — os índices SEMÂNTICOS
//! (quadril/joelho/tornozelo...). Trocar o motor de pose p/ Halpe26 = apontar o backend pra
//! outro `KeypointLayout`; o parsing do tensor, o desenho e as métricas seguem sem mudança porque
//! falam em NOMES, não em números mágicos. Os pontos de pé são Option: existem no Halpe26, não no
//! COCO-17 (é por isso que hoje a pisada é INFERIDA e não há dorsiflexão — ver README-KEYPOINTS.md).

/// Descreve um conjunto de keypoints: contagem, nomes, esqueleto e os índices semânticos que a
/// biomecânica usa. Layouts diferentes (COCO-17, Halpe26) são só instâncias distintas.
#[derive(Debug)]
pub struct KeypointLayout {
    pub name: &'static str,
    pub count: usize,
    pub names: &'static [&'static str],
    /// pares de índices ligados no desenho do esqueleto
    pub skeleton: &'static [(usize, usize)],
    /// keypoints que NÃO viram articulação desenhada (olhos/orelhas)
    pub face_skip: &'static [usize],
    // índices semânticos (E = esquerdo, D = direito)
    pub nose: usize,
    pub shoulder_l: usize,
    pub shoulder_r: usize,
    pub hip_l: usize,
    pub hip_r: usize,
    pub knee_l: usize,
    pub knee_r: usize,
    pub ankle_l: usize,
    pub ankle_r: usize,
    // pontos de PÉ — Some só quando o layout os traz (Halpe26). None = pisada inferida, sem dorsiflexão.
    pub big_toe_l: Option<usize>,
    pub big_toe_r: Option<usize>,
    pub small_toe_l: Option<usize>,
    pub small_toe_r: Option<usize>,
    pub heel_l: Option<usize>,
    pub heel_r: Option<usize>,
}

impl KeypointLayout {
    /// o layout traz pontos de pé? (destrava pisada MEDIDA + ângulo de dorsiflexão)
    pub fn has_foot(&self) -> bool {
        self.heel_l.is_some() && self.big_toe_l.is_some()
    }
}

const COCO17_NAMES: [&str; 17] = [
    "nariz", "olho_e", "olho_d", "orelha_e", "orelha_d", "ombro_e", "ombro_d",
    "cotovelo_e", "cotovelo_d", "punho_e", "punho_d", "quadril_e", "quadril_d",
    "joelho_e", "joelho_d", "tornozelo_e", "tornozelo_d",
];
/// Ligações do esqueleto para CORRIDA: tronco, quadril, pernas e braços. Sem face —
/// olho/orelha não dizem nada sobre a mecânica de corrida (o Ochy também não usa).
/// Mantemos só nariz->ombros pra enxergar a inclinação da cabeça/tronco.
const COCO17_SKELETON: [(usize, usize); 14] = [
    (15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12), (5, 6),
    (5, 7), (7, 9), (6, 8), (8, 10), (0, 5), (0, 6),
];
const COCO17_FACE_SKIP: [usize; 4] = [1, 2, 3, 4];

/// COCO-17 (YOLO11-pose): layout PADRÃO e único ativo hoje. Sem keypoints de pé.
pub static COCO17: KeypointLayout = KeypointLayout {
    name: "coco17",
    count: 17,
    names: &COCO17_NAMES,
    skeleton: &COCO17_SKELETON,
    face_skip: &COCO17_FACE_SKIP,
    nose: 0,
    shoulder_l: 5, shoulder_r: 6,
    hip_l: 11, hip_r: 12,
    knee_l: 13, knee_r: 14,
    ankle_l: 15, ankle_r: 16,
    big_toe_l: None, big_toe_r: None,
    small_toe_l: None, small_toe_r: None,
    heel_l: None, heel_r: None,
};

const HALPE26_NAMES: [&str; 26] = [
    "nariz", "olho_e", "olho_d", "orelha_e", "orelha_d", "ombro_e", "ombro_d",
    "cotovelo_e", "cotovelo_d", "punho_e", "punho_d", "quadril_e", "quadril_d",
    "joelho_e", "joelho_d", "tornozelo_e", "tornozelo_d",
    "cabeca", "pescoco", "quadril_c", "hallux_e", "hallux_d",
    "dedinho_e", "dedinho_d", "calcanhar_e", "calcanhar_d",
];
/// Esqueleto COCO reaproveitado + os elos do pé (tornozelo→calcanhar→hallux). Blindado por asset:
/// só passa a ser desenhado quando o modelo Halpe26 estiver plugado (ver README-KEYPOINTS.md).
const HALPE26_SKELETON: [(usize, usize); 18] = [
    (15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12), (5, 6),
    (5, 7), (7, 9), (6, 8), (8, 10), (0, 5), (0, 6),
    (15, 24), (24, 20), (16, 25), (25, 21),   // tornozelo→calcanhar→hallux (E/D)
];
const HALPE26_FACE_SKIP: [usize; 4] = [1, 2, 3, 4];

/// Halpe26 (26 keypoints, inclui PÉ): layout-alvo, BLOQUEADO por asset (modelo ONNX não baixado).
/// Presente aqui só pra provar que a costura é uma troca de layout — ver README-KEYPOINTS.md.
pub static HALPE26: KeypointLayout = KeypointLayout {
    name: "halpe26",
    count: 26,
    names: &HALPE26_NAMES,
    skeleton: &HALPE26_SKELETON,
    face_skip: &HALPE26_FACE_SKIP,
    nose: 0,
    shoulder_l: 5, shoulder_r: 6,
    hip_l: 11, hip_r: 12,
    knee_l: 13, knee_r: 14,
    ankle_l: 15, ankle_r: 16,
    big_toe_l: Some(20), big_toe_r: Some(21),
    small_toe_l: Some(22), small_toe_r: Some(23),
    heel_l: Some(24), heel_r: Some(25),
};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn halpe26_trava_os_seis_pontos_semanticos_do_pe() {
        assert_eq!(HALPE26.count, 26);
        assert!(HALPE26.has_foot());
        assert_eq!(HALPE26.names[HALPE26.big_toe_l.unwrap()], "hallux_e");
        assert_eq!(HALPE26.names[HALPE26.big_toe_r.unwrap()], "hallux_d");
        assert_eq!(HALPE26.names[HALPE26.small_toe_l.unwrap()], "dedinho_e");
        assert_eq!(HALPE26.names[HALPE26.small_toe_r.unwrap()], "dedinho_d");
        assert_eq!(HALPE26.names[HALPE26.heel_l.unwrap()], "calcanhar_e");
        assert_eq!(HALPE26.names[HALPE26.heel_r.unwrap()], "calcanhar_d");
    }
}
