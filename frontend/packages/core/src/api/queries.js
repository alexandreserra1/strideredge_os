import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from './client';
export function useActivities() {
    return useQuery({
        queryKey: ['activities'],
        queryFn: api.activities.list,
    });
}
export function useActivity(id) {
    return useQuery({
        queryKey: ['activity', id],
        queryFn: () => api.activities.detail(id),
        enabled: !!id,
    });
}
export function useTrack(id) {
    return useQuery({
        queryKey: ['track', id],
        queryFn: () => api.activities.track(id),
        enabled: !!id,
    });
}
export function useTelemetry(id) {
    return useQuery({
        queryKey: ['telemetry', id],
        queryFn: () => api.activities.telemetry(id),
        enabled: !!id,
    });
}
export function useCadenceSpectrum(id) {
    return useQuery({
        queryKey: ['cadence-spectrum', id],
        queryFn: () => api.activities.spectrum(id),
        enabled: !!id,
    });
}
export function useCoachVerdict() {
    return useMutation({
        mutationFn: (id) => api.activities.coach(id),
    });
}
export function useTrainingLoad() {
    return useQuery({
        queryKey: ['training-load'],
        queryFn: api.trainingLoad.list,
    });
}
export function useFitness() {
    return useQuery({
        queryKey: ['fitness'],
        queryFn: api.fitness.get,
    });
}
export function useAsk() {
    return useMutation({
        mutationFn: (question) => api.ask(question),
    });
}
//# sourceMappingURL=queries.js.map