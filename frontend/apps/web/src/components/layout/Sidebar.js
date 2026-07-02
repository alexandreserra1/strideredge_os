import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { LayoutDashboard, CalendarDays, Activity, Play, Dumbbell, Settings, } from 'lucide-react';
const menu = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'plano', label: 'Plano', icon: CalendarDays },
    { id: 'detalhe', label: 'Treinos', icon: Activity },
    { id: 'corrida', label: 'Correr', icon: Play },
    { id: 'hyrox', label: 'HYROX', icon: Dumbbell },
];
export default function Sidebar({ currentRoute, onNavigate }) {
    return (_jsxs("aside", { className: "w-[220px] min-h-screen bg-surface-100 border-r border-border-light flex flex-col shrink-0 hide-mobile", children: [_jsx("div", { className: "p-5 border-b border-border-light", children: _jsxs("button", { onClick: () => onNavigate('dashboard'), className: "flex items-center gap-2.5", children: [_jsx("span", { className: "grid place-items-center w-8 h-8 rounded-lg bg-brand text-brand-ink font-black text-sm", children: "S" }), _jsxs("span", { className: "text-lg font-bold tracking-tight", children: ["Strider", _jsx("span", { className: "text-brand", children: "Edge" })] })] }) }), _jsx("nav", { className: "flex-1 p-3 space-y-1", children: menu.map(({ id, label, icon: Icon }) => (_jsxs("button", { onClick: () => onNavigate(id), className: `w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
              ${currentRoute === id
                        ? 'bg-lime/10 text-lime border border-lime/20'
                        : 'text-text-secondary hover:text-text-primary hover:bg-white/5 dark:hover:bg-white/5 border border-transparent'}`, children: [_jsx(Icon, { size: 18 }), label] }, id))) }), _jsx("div", { className: "p-3 border-t border-border-light", children: _jsxs("button", { onClick: () => onNavigate('settings'), className: "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-white/5 dark:hover:bg-white/5 transition-all duration-200", children: [_jsx(Settings, { size: 18 }), "Ajustes"] }) })] }));
}
//# sourceMappingURL=Sidebar.js.map