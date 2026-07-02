const TYPE_MAP = {
    RUN: 'run', CARDIO: 'treadmill', HIIT: 'crossfit',
    STRENGTH: 'strength', HYROX: 'hyrox', CROSSFIT: 'crossfit',
};
export function toActivityType(primary) {
    return TYPE_MAP[(primary || '').toUpperCase()] || 'run';
}
function paceFrom(distanceM, durationS) {
    if (!distanceM || !durationS)
        return '—';
    const secPerKm = durationS / (distanceM / 1000);
    return `${Math.floor(secPerKm / 60)}:${String(Math.round(secPerKm % 60)).padStart(2, '0')}`;
}
/** Atividade da API -> card de treino da UI. */
export function toWorkoutSession(a) {
    return {
        id: a.activity_id,
        type: toActivityType(a.primary_type),
        name: a.activity_name,
        distance_km: Math.round((a.distance_m || 0) / 100) / 10,
        duration_min: Math.round((a.duration_s || 0) / 60),
        pace: paceFrom(a.distance_m, a.duration_s),
        avg_hr: a.avg_hr ?? 0,
        cadence: a.avg_cadence ?? 0,
        calories: a.calories ?? 0,
        elevation_gain: a.total_elevation_gain ?? 0,
        date: a.start_time,
    };
}
const ACWR_STATUS = {
    destreino: 'low', aquecendo: 'low',
    'zona segura': 'optimal',
    atencao: 'high', 'atenção': 'high',
    'risco de lesao': 'very_high', 'risco de lesão': 'very_high',
};
export function toAcwrStatus(status) {
    return ACWR_STATUS[(status || '').toLowerCase()] || 'optimal';
}
/** Estado de carga mais recente (o "hoje" do atleta). */
export function latestAcwr(items) {
    if (!items?.length)
        return null;
    const last = items[items.length - 1];
    return { acwr: last.acwr ?? 0, status: toAcwrStatus(String(last.status)) };
}
//# sourceMappingURL=adapters.js.map