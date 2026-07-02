import type { Activity, ActivityDetail, TrainingLoadItem, FitnessData, TrackData, CadenceSpectrum, WeeklyPlan, WorkoutSession } from '@strideredge/core';
export declare const mockActivities: WorkoutSession[];
export declare const todayPrescribed: {
    type: "run";
    name: string;
    description: string;
    target_pace: string;
    target_hr: string;
    duration_min: number;
    distance_km: number;
    adjusted: boolean;
};
export declare const mockTrainingLoad: TrainingLoadItem[];
export declare const mockFitness: FitnessData;
export declare const mockActivityDetail: ActivityDetail;
export declare const mockTrack: TrackData;
export declare const mockTelemetry: {
    timestamp: string;
    heart_rate: number;
    cadence: number;
    altitude: number;
    speed_ms: number;
}[];
export declare const mockSpectrum: CadenceSpectrum;
export declare const mockPlan: WeeklyPlan[];
export declare const mockCoachVerdict: {
    verdict: string;
    strengths: string[];
    improvements: string[];
    actions: string[];
    citations: string[];
};
export declare const mockActivitiesList: Activity[];
export declare const mockAcwrCurrent: TrainingLoadItem;
//# sourceMappingURL=mockData.d.ts.map