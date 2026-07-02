import type { Activity, ActivityDetail, TrackData, TelemetryPoint, CadenceSpectrum, CoachVerdict, TrainingLoadItem, FitnessData, AskResponse } from '../types';
export declare const api: {
    activities: {
        list: () => Promise<Activity[]>;
        detail: (id: string) => Promise<ActivityDetail>;
        track: (id: string) => Promise<TrackData>;
        telemetry: (id: string) => Promise<TelemetryPoint[]>;
        spectrum: (id: string) => Promise<CadenceSpectrum>;
        coach: (id: string) => Promise<CoachVerdict>;
    };
    trainingLoad: {
        list: () => Promise<TrainingLoadItem[]>;
    };
    fitness: {
        get: () => Promise<FitnessData>;
    };
    ask: (question: string) => Promise<AskResponse>;
};
//# sourceMappingURL=client.d.ts.map