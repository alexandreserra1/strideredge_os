"""analytics/injury_taxonomy.py — vocabulário controlado de lesão de corrida.

A maneira PROFISSIONAL de coletar dado de lesão (informática médica): define a taxonomia ANTES
de coletar, senão o dado não serve pro ML. Aqui mora o vocabulário (região + diagnóstico) e o
mapa `lesão → fatores biomecânicos que a literatura associa` (chaves de `biomechanics.ideal_targets`,
fonte única). Esse mapa entra no ML em três lugares: define o RÓTULO (y), dá o PRIOR de quais
features importam por lesão, e habilita a VALIDAÇÃO do modelo de risco contra outcome real.

Honestidade: mapa (factors+source) SÓ nas lesões com fonte no corpus. Fascite plantar e Aquiles
entram no LOG (o atleta pode reportar) com `mapped=False` até adicionarmos a fonte verificada.
"""

# Regiões do corpo (pra agrupar o picker do log e a correlação por região).
REGIONS = (
    "joelho_frente", "joelho_lateral", "canela", "pe", "tornozelo", "quadril", "coxa",
)

# As 6 lesões de corrida dominantes. `factors` referencia as CHAVES de biomechanics.ideal_targets.
# `source` = PMC do corpus (None quando ainda não há fonte -> mapped=False).
DIAGNOSES = {
    "pfp": {
        "label": "Dor patelofemoral (joelho do corredor)", "region": "joelho_frente",
        "factors": ["pelvic_drop_deg", "knee_valgus_deg", "knee_contact_deg"],
        "source": "PMC6829001",
    },
    "itbs": {
        "label": "Síndrome da banda iliotibial", "region": "joelho_lateral",
        "factors": ["pelvic_drop_deg", "knee_valgus_deg"],
        "source": "PMC6829001",
    },
    "mtss": {
        "label": "Canelite (síndrome do estresse tibial medial)", "region": "canela",
        "factors": ["cadence_spm", "pelvic_drop_deg"],
        "source": "PMC11958822",
    },
    "stress_fx": {
        "label": "Fratura por estresse", "region": "canela",
        "factors": ["cadence_spm", "vertical_oscillation_pct"],
        "source": "PMC8192811",
    },
    # Sem fonte no corpus ainda -> entram no log, mas sem mapa citado (mapped=False).
    "plantar": {
        "label": "Fascite plantar", "region": "pe", "factors": [], "source": None,
    },
    "achilles": {
        "label": "Tendinopatia do Aquiles", "region": "tornozelo", "factors": [], "source": None,
    },
}

SIDES = ("esquerdo", "direito", "ambos")


def valid_diagnosis(dx: str) -> bool:
    return dx in DIAGNOSES


def is_mapped(dx: str) -> bool:
    """Tem mapa citado (fatores + fonte)? False = só entra no log, não no modelo/validação."""
    return bool(DIAGNOSES.get(dx, {}).get("source"))


def factors_for(dx: str) -> list:
    """Fatores biomecânicos que a literatura liga a essa lesão (vazio se não mapeada)."""
    return list(DIAGNOSES.get(dx, {}).get("factors", []))


def diagnoses_for_region(region: str) -> list:
    """IDs de diagnóstico daquela região (pra montar o picker do log em cascata)."""
    return [dx for dx, d in DIAGNOSES.items() if d["region"] == region]
