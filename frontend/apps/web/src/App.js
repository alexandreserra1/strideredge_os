import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useCallback } from 'react';
import { ThemeProvider } from './components/layout/ThemeProvider';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Landing from './pages/Landing';
import WorkoutDetail from './pages/WorkoutDetail';
import PlanScreen from './pages/PlanScreen';
import RunMode from './pages/RunMode';
import HyroxScreen from './pages/HyroxScreen';
import { mockAcwrCurrent } from './pages/mockData';
export default function App() {
    const [route, setRoute] = useState('dashboard');
    const [acwr] = useState(mockAcwrCurrent.acwr);
    const navigate = useCallback((r) => {
        if (['landing', 'dashboard', 'plano', 'detalhe', 'corrida', 'hyrox'].includes(r)) {
            setRoute(r);
        }
    }, []);
    const renderPage = () => {
        switch (route) {
            case 'landing':
                return _jsx(Landing, { onNavigate: navigate });
            case 'dashboard':
                return _jsx(Dashboard, { onNavigate: navigate });
            case 'plano':
                return _jsx(PlanScreen, {});
            case 'detalhe':
                return _jsx(WorkoutDetail, { onNavigate: navigate });
            case 'corrida':
                return _jsx(RunMode, {});
            case 'hyrox':
                return _jsx(HyroxScreen, {});
            default:
                return _jsx(Dashboard, { onNavigate: navigate });
        }
    };
    const isLanding = route === 'landing';
    return (_jsx(ThemeProvider, { children: isLanding ? (_jsxs("div", { className: "min-h-screen bg-surface", children: [_jsx("header", { className: "sticky top-0 z-50 bg-surface-100/80 backdrop-blur-xl border-b border-border-light", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 h-14 flex items-center justify-between", children: [_jsxs("button", { onClick: () => navigate('landing'), className: "flex items-center gap-2", children: [_jsx("span", { className: "grid place-items-center w-7 h-7 rounded-lg bg-brand text-brand-ink font-black text-sm", children: "S" }), _jsxs("span", { className: "font-bold tracking-tight", children: ["Strider", _jsx("span", { className: "text-brand", children: "Edge" })] })] }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsx("button", { onClick: () => navigate('dashboard'), className: "btn-ghost text-sm", children: "Login" }), _jsx("button", { onClick: () => navigate('dashboard'), className: "btn-primary text-sm", children: "Come\u00E7ar" })] })] }) }), _jsx(Landing, { onNavigate: navigate })] })) : (_jsx(Layout, { currentRoute: route, onNavigate: navigate, acwr: acwr, children: renderPage() })) }));
}
//# sourceMappingURL=App.js.map