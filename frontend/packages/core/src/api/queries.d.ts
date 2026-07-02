export declare function useActivities(): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").Activity[]>, Error>;
export declare function useActivity(id: string | undefined): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").ActivityDetail>, Error>;
export declare function useTrack(id: string | undefined): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").TrackData>, Error>;
export declare function useTelemetry(id: string | undefined): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").TelemetryPoint[]>, Error>;
export declare function useCadenceSpectrum(id: string | undefined): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").CadenceSpectrum>, Error>;
export declare function useCoachVerdict(): import("@tanstack/react-query").UseMutationResult<import("..").CoachVerdict, Error, string, unknown>;
export declare function useTrainingLoad(): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").TrainingLoadItem[]>, Error>;
export declare function useFitness(): import("@tanstack/react-query").UseQueryResult<NoInfer<import("..").FitnessData>, Error>;
export declare function useAsk(): import("@tanstack/react-query").UseMutationResult<import("..").AskResponse, Error, string, unknown>;
//# sourceMappingURL=queries.d.ts.map