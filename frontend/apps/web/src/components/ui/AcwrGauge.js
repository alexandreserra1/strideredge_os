import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import AnimatedNumber from './AnimatedNumber';
const statusConfig = {
    low: { color: 'text-accent-yellow', hex: '#F5B14C', label: 'Atenção' },
    optimal: { color: 'text-accent-green', hex: '#34D399', label: 'Pronto' },
    high: { color: 'text-accent-orange', hex: '#FF8A4C', label: 'Limiar' },
    very_high: { color: 'text-accent-red', hex: '#FB5E7E', label: 'Alerta' },
};
export default function AcwrGauge({ value, status }) {
    const cfg = statusConfig[status] || statusConfig.optimal;
    const pct = Math.min(value / 1.5, 1) * 100;
    return (_jsxs("div", { className: "kpi-card", children: [_jsx("span", { className: "text-xs font-medium text-text-secondary uppercase tracking-wider", children: "Prontid\u00E3o \u00B7 ACWR" }), _jsxs("div", { className: "flex items-center justify-between mt-2", children: [_jsxs("div", { className: "relative w-16 h-16", children: [_jsxs("svg", { viewBox: "0 0 36 36", className: "w-16 h-16 -rotate-90", children: [_jsx("path", { d: "M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32", stroke: "var(--surface-300)", strokeWidth: "4", fill: "none" }), _jsx("path", { d: "M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32", stroke: cfg.hex, strokeWidth: "4", fill: "none", strokeDasharray: `${pct} ${100 - pct}`, strokeLinecap: "round", style: { transition: 'stroke-dasharray .7s cubic-bezier(.22,1,.36,1)' } })] }), _jsx(AnimatedNumber, { value: value, decimals: 2, className: `absolute inset-0 flex items-center justify-center text-lg font-bold tabular-nums ${cfg.color}` })] }), _jsxs("div", { className: "flex flex-col items-end", children: [_jsx("span", { className: `text-sm font-semibold ${cfg.color}`, children: cfg.label }), _jsx("span", { className: "text-xs text-text-secondary", children: "Carga ideal: 0.8\u20131.3" })] })] }), _jsx("div", { className: "mt-3 h-1.5 bg-surface-300 rounded-full overflow-hidden", children: _jsx("div", { className: "h-full rounded-full transition-all duration-700", style: { width: `${pct}%`, backgroundColor: cfg.hex } }) })] }));
}
//# sourceMappingURL=AcwrGauge.js.map