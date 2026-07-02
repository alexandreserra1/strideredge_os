import type { Activity, ActivityType, WorkoutSession, TrainingLoadItem, AcwrStatus } from '../types';
export declare function toActivityType(primary: string): ActivityType;
/** Atividade da API -> card de treino da UI. */
export declare function toWorkoutSession(a: Activity): WorkoutSession;
export declare function toAcwrStatus(status: string): AcwrStatus;
/** Estado de carga mais recente (o "hoje" do atleta). */
export declare function latestAcwr(items: TrainingLoadItem[]): {
    acwr: number;
    status: AcwrStatus;
} | null;
//# sourceMappingURL=adapters.d.ts.map