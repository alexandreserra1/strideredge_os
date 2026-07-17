"""analytics/injury_taxonomy.py — vocabulário controlado de lesão de corrida.

A maneira PROFISSIONAL de coletar dado de lesão (informática médica): define a taxonomia ANTES
de coletar, senão o dado não serve pro ML. Aqui mora o vocabulário (região + diagnóstico) e o
mapa `lesão → fatores biomecânicos que a literatura associa` (chaves de `biomechanics.ideal_targets`,
fonte única). Esse mapa entra no ML em três lugares: define o RÓTULO (y), dá o PRIOR de quais
features importam por lesão, e habilita a VALIDAÇÃO do modelo de risco contra outcome real.

Honestidade: mapa (factors+source) SÓ com fonte citável. As 6 lesões estão mapeadas; fascite plantar
e Aquiles usam fatores PROXY de carga (o risco primário delas — dorsiflexão/pronação do pé — não é
medível com o pose COCO-17 atual; migra pra primário no upgrade Halpe26 — ver docs/adr/0001).
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
    # Fatores PROXY: o risco primário destas duas (dorsiflexão de tornozelo reduzida + pronação do
    # retropé) NÃO é medível com o pose atual (COCO-17 não tem keypoints de pé). Mapeamos os proxies
    # de CARGA que a literatura também liga a elas e que já medimos; migram p/ os fatores primários
    # quando o motor subir p/ Halpe26/RTMPose (ver ADR 0001 + AI-STRATEGY.md:99).
    "plantar": {
        "label": "Fascite plantar", "region": "pe",
        "factors": ["cadence_spm", "vertical_oscillation_pct"],
        "source": "PMC11878588",
    },
    "achilles": {
        "label": "Tendinopatia do Aquiles", "region": "tornozelo",
        "factors": ["cadence_spm", "knee_contact_deg"],
        "source": "PMC9845578",
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


def taxonomy_payload() -> dict:
    """Vocabulário controlado p/ o picker do frontend (single-source: região→diagnóstico→lado)."""
    return {
        "regions": list(REGIONS),
        "sides": list(SIDES),
        "diagnoses": [
            {"id": dx, "label": d["label"], "region": d["region"], "is_mapped": is_mapped(dx)}
            for dx, d in DIAGNOSES.items()
        ],
    }
