import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Moon, Sun, Bell } from 'lucide-react';
import { useTheme } from './ThemeProvider';
// Cor da prontidão a partir do ACWR (sweet spot 0.8–1.3)
function readiness(acwr) {
    if (acwr == null)
        return { color: 'var(--text-muted)', label: '—' };
    if (acwr < 0.8)
        return { color: '#38BDF8', label: 'Leve' };
    if (acwr <= 1.3)
        return { color: '#34D399', label: 'Ótima' };
    if (acwr <= 1.5)
        return { color: '#F5B14C', label: 'Atenção' };
    return { color: '#FB5E7E', label: 'Alta' };
}
export default function Topbar({ acwr, onNotifications }) {
    const { theme, setTheme } = useTheme();
    const r = readiness(acwr);
    return (_jsxs("header", { className: "h-16 glass border-b border-border-light flex items-center justify-between px-4 md:px-6 sticky top-0 z-40", children: [_jsx("div", { className: "md:hidden", children: _jsxs("span", { className: "text-lg font-bold", children: ["Strider", _jsx("span", { className: "text-brand", children: "Edge" })] }) }), _jsxs("div", { className: "flex items-center gap-2 ml-auto", children: [_jsxs("div", { className: "hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-200 border border-border-light", children: [_jsx("span", { className: "w-2 h-2 rounded-full", style: { background: r.color, boxShadow: `0 0 8px ${r.color}` } }), _jsxs("span", { className: "text-xs font-medium text-text-secondary", children: ["Prontid\u00E3o ", _jsx("span", { className: "text-text-primary font-semibold tabular-nums", children: acwr?.toFixed(2) ?? '—' })] })] }), _jsx("button", { onClick: () => setTheme(theme === 'dark' ? 'light' : 'dark'), className: "p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-200 transition-all duration-200", title: theme === 'dark' ? 'Modo claro' : 'Modo escuro', children: theme === 'dark' ? _jsx(Sun, { size: 18 }) : _jsx(Moon, { size: 18 }) }), _jsxs("button", { onClick: onNotifications, className: "p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-200 transition-all duration-200 relative", children: [_jsx(Bell, { size: 18 }), _jsx("span", { className: "absolute top-1.5 right-1.5 w-2 h-2 bg-brand rounded-full" })] })] })] }));
}
//# sourceMappingURL=Topbar.js.map