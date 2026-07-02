import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
const statusConfig = {
    low: { color: 'text-accent-yellow', bg: 'bg-accent-yellow/20', label: 'Atenção' },
    optimal: { color: 'text-accent-green', bg: 'bg-accent-green/20', label: 'Pronto' },
    high: { color: 'text-accent-orange', bg: 'bg-accent-orange/20', label: 'Limiar' },
    very_high: { color: 'text-accent-red', bg: 'bg-accent-red/20', label: 'Alerta' },
};
export default function AcwrGauge({ value, status }) {
    const cfg = statusConfig[status] || statusConfig.optimal;
    const pct = Math.min(value / 1.5, 1) * 100;
    return (_jsxs("div", { className: "kpi-card", children: [_jsx("span", { className: "text-xs font-medium text-text-secondary uppercase tracking-wider", children: "Prontid\u00E3o \u00B7 ACWR" }), _jsxs("div", { className: "flex items-center justify-between mt-2", children: [_jsxs("div", { className: "relative w-16 h-16", children: [_jsxs("svg", { viewBox: "0 0 36 36", className: "w-16 h-16 -rotate-90", children: [_jsx("path", { d: "M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32", stroke: "#1F2B00", strokeWidth: "4", fill: "none" }), _jsx("path", { d: "M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32", stroke: "currentColor", strokeWidth: "4", fill: "none", strokeDasharray: `${pct} ${100 - pct}`, strokeLinecap: "round", className: cfg.color })] }), _jsx("span", { className: `absolute inset-0 flex items-center justify-center text-lg font-bold ${cfg.color}`, children: value.toFixed(2) })] }), _jsxs("div", { className: "flex flex-col items-end", children: [_jsx("span", { className: `text-sm font-semibold ${cfg.color}`, children: cfg.label }), _jsx("span", { className: "text-xs text-text-secondary", children: "Carga ideal: 0.8\u20131.3" })] })] }), _jsx("div", { className: "mt-3 h-1.5 bg-surface-300 rounded-full overflow-hidden", children: _jsx("div", { className: `h-full rounded-full transition-all duration-500 ${cfg.bg}`, style: { width: `${pct}%` } }) })] }));
}
//# sourceMappingURL=AcwrGauge.js.map