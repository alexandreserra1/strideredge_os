const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
class ApiError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
        this.name = 'ApiError';
    }
}
async function request(path, options) {
    const url = `${BASE_URL}${path}`;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options?.headers },
        ...options,
    });
    if (!res.ok) {
        const text = await res.text().catch(() => 'Unknown error');
        throw new ApiError(res.status, text);
    }
    return res.json();
}
export const api = {
    activities: {
        list: () => request('/activities'),
        detail: (id) => request(`/activities/${id}`),
        track: (id) => request(`/activities/${id}/track`),
        telemetry: (id) => request(`/activities/${id}/telemetry`),
        spectrum: (id) => request(`/activities/${id}/cadence-spectrum`),
        coach: (id) => request(`/activities/${id}/coach`, { method: 'POST' }),
    },
    trainingLoad: {
        list: () => request('/training-load'),
    },
    fitness: {
        get: () => request('/fitness'),
    },
    ask: (question) => request('/ask', {
        method: 'POST',
        body: JSON.stringify({ question }),
    }),
};
//# sourceMappingURL=client.js.map