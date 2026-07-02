import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
const accentColors = {
    lime: 'text-lime border-lime/30',
    green: 'text-accent-green border-accent-green/30',
    yellow: 'text-accent-yellow border-accent-yellow/30',
    red: 'text-accent-red border-accent-red/30',
    orange: 'text-accent-orange border-accent-orange/30',
    blue: 'text-accent-blue border-accent-blue/30',
};
const trendIcons = {
    up: '↑',
    down: '↓',
    stable: '→',
};
export default function KpiCard({ label, value, sub, icon, accent = 'lime', trend, children }) {
    return (_jsxs("div", { className: `kpi-card relative overflow-hidden ${children ? 'pb-0' : ''}`, children: [_jsxs("div", { className: "flex items-start justify-between mb-1", children: [_jsx("span", { className: "text-xs font-medium text-text-secondary uppercase tracking-wider", children: label }), icon && _jsx("span", { className: `${accentColors[accent].split(' ')[0]} opacity-70`, children: icon })] }), _jsxs("div", { className: "flex items-baseline gap-2", children: [_jsx("span", { className: "text-2xl md:text-3xl font-bold tracking-tight text-text-primary", children: value }), trend && (_jsx("span", { className: `text-sm font-medium ${trend === 'up' ? 'text-accent-green' : trend === 'down' ? 'text-accent-red' : 'text-text-secondary'}`, children: trendIcons[trend] }))] }), sub && _jsx("p", { className: "text-xs text-text-secondary mt-0.5", children: sub }), children] }));
}
//# sourceMappingURL=KpiCard.js.map