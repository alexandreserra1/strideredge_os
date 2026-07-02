import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useRef } from 'react';
import { Play, Pause, StopCircle, Map, Volume2 } from 'lucide-react';
const voiceCues = [
    { time: 5, text: 'Respiração estável. Foco no ritmo.' },
    { time: 15, text: 'Segura o ritmo — FC acima do alvo.' },
    { time: 25, text: 'Cadência excelente, mantém!' },
    { time: 35, text: 'Metade do caminho. Força aí!' },
    { time: 45, text: 'Últimos 5 km. Hora de abrir.' },
    { time: 55, text: 'Mais 1 km! Dá tudo agora!' },
];
export default function RunMode() {
    const [status, setStatus] = useState('idle');
    const [elapsed, setElapsed] = useState(0);
    const [currentCue, setCurrentCue] = useState(null);
    const [showCue, setShowCue] = useState(false);
    const intervalRef = useRef(null);
    const pace = '5:02';
    const distance = (elapsed * 0.0033).toFixed(2);
    const hr = Math.round(155 + Math.sin(elapsed * 0.1) * 8);
    const cadence = 168 + Math.round(Math.sin(elapsed * 0.05) * 4);
    useEffect(() => {
        if (status === 'running') {
            intervalRef.current = setInterval(() => {
                setElapsed(prev => {
                    const next = prev + 1;
                    const cue = voiceCues.find(c => c.time === next);
                    if (cue) {
                        setCurrentCue(cue.text);
                        setShowCue(true);
                        setTimeout(() => setShowCue(false), 5000);
                    }
                    return next;
                });
            }, 1000);
        }
        return () => { if (intervalRef.current)
            clearInterval(intervalRef.current); };
    }, [status]);
    const formatTime = (s) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
    const toggleRun = () => {
        if (status === 'idle') {
            setStatus('running');
            setElapsed(0);
        }
        else if (status === 'running')
            setStatus('paused');
        else if (status === 'paused')
            setStatus('running');
    };
    const stopRun = () => {
        setStatus('finished');
        if (intervalRef.current)
            clearInterval(intervalRef.current);
    };
    if (status === 'idle') {
        return (_jsxs("div", { className: "max-w-2xl mx-auto space-y-8 animate-fade-in mt-12", children: [_jsxs("div", { className: "text-center", children: [_jsx("h1", { className: "text-2xl md:text-3xl font-bold tracking-tight", children: "Modo Corrida" }), _jsx("p", { className: "text-text-secondary mt-1", children: "Treino de hoje: Ritmo \u2014 10 km progressivo" })] }), _jsxs("div", { className: "card p-10 text-center space-y-8", children: [_jsxs("div", { children: [_jsx("p", { className: "text-lg font-semibold", children: "Pronto pra correr?" }), _jsx("p", { className: "text-sm text-text-secondary mt-1", children: "10 km \u00B7 Pace alvo 5:00/km \u00B7 FC 155\u2013165 bpm" })] }), _jsx("button", { onClick: toggleRun, className: "mx-auto w-28 h-28 rounded-full bg-brand text-brand-ink grid place-items-center\n                       shadow-[0_16px_48px_-12px_var(--brand)] hover:scale-105 active:scale-95 transition-transform", children: _jsx(Play, { size: 44, className: "translate-x-1" }) }), _jsx("p", { className: "text-xs text-text-muted", children: "O coach vai te acompanhar por voz durante o treino." })] })] }));
    }
    return (_jsxs("div", { className: "max-w-3xl mx-auto space-y-6 animate-fade-in", children: [_jsxs("div", { className: "card bg-gradient-to-b from-brand/5 to-transparent border-brand/10 p-6 md:p-8", children: [_jsxs("div", { className: "grid grid-cols-3 gap-4 md:gap-8 text-center mb-6", children: [_jsxs("div", { children: [_jsx("p", { className: "text-[10px] font-medium text-text-secondary uppercase tracking-widest", children: "Pace" }), _jsx("p", { className: "text-3xl md:text-5xl font-black text-brand tabular-nums mt-1", children: pace })] }), _jsxs("div", { children: [_jsx("p", { className: "text-[10px] font-medium text-text-secondary uppercase tracking-widest", children: "Dist\u00E2ncia" }), _jsxs("p", { className: "text-3xl md:text-5xl font-black text-text-primary tabular-nums mt-1", children: [distance, " ", _jsx("span", { className: "text-lg font-medium", children: "km" })] })] }), _jsxs("div", { children: [_jsx("p", { className: "text-[10px] font-medium text-text-secondary uppercase tracking-widest", children: "Tempo" }), _jsx("p", { className: "text-3xl md:text-5xl font-black text-text-primary tabular-nums mt-1", children: formatTime(elapsed) })] })] }), _jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-4", children: [_jsxs("div", { className: "bg-surface-300/50 rounded-2xl p-3 text-center", children: [_jsx("p", { className: "text-[10px] text-text-secondary uppercase tracking-wider", children: "FC" }), _jsxs("p", { className: "text-xl md:text-2xl font-bold text-accent-red tabular-nums", children: [hr, " ", _jsx("span", { className: "text-xs font-medium", children: "bpm" })] })] }), _jsxs("div", { className: "bg-surface-300/50 rounded-2xl p-3 text-center", children: [_jsx("p", { className: "text-[10px] text-text-secondary uppercase tracking-wider", children: "Cad\u00EAncia" }), _jsxs("p", { className: "text-xl md:text-2xl font-bold text-accent-green tabular-nums", children: [cadence, " ", _jsx("span", { className: "text-xs font-medium", children: "spm" })] })] }), _jsxs("div", { className: "bg-surface-300/50 rounded-2xl p-3 text-center", children: [_jsx("p", { className: "text-[10px] text-text-secondary uppercase tracking-wider", children: "Eleva\u00E7\u00E3o" }), _jsxs("p", { className: "text-xl md:text-2xl font-bold tabular-nums", children: [Math.round(elapsed * 0.3), " ", _jsx("span", { className: "text-xs font-medium", children: "m" })] })] }), _jsxs("div", { className: "bg-surface-300/50 rounded-2xl p-3 text-center", children: [_jsx("p", { className: "text-[10px] text-text-secondary uppercase tracking-wider", children: "Zona FC" }), _jsxs("p", { className: "text-xl md:text-2xl font-bold text-brand tabular-nums", children: ["Z", hr > 165 ? '3' : hr > 155 ? '2' : '1'] })] })] }), _jsx("div", { className: "mt-4 h-2 bg-surface-300 rounded-full overflow-hidden", children: _jsx("div", { className: "h-full bg-gradient-to-r from-accent-green via-accent-yellow to-accent-red rounded-full transition-all duration-1000", style: { width: `${Math.min(100, ((hr - 100) / 80) * 100)}%` } }) }), _jsxs("div", { className: "flex justify-between text-[10px] text-text-secondary mt-1", children: [_jsx("span", { children: "100" }), _jsx("span", { children: "Z2" }), _jsx("span", { children: "Z3" }), _jsx("span", { children: "180" })] })] }), showCue && currentCue && (_jsxs("div", { className: "animate-slide-up flex items-center gap-3 p-4 rounded-2xl border border-brand/25 bg-brand/[0.06]", children: [_jsxs("div", { className: "relative grid place-items-center w-10 h-10 rounded-full bg-brand/15 text-brand shrink-0", children: [_jsx(Volume2, { size: 18 }), _jsx("span", { className: "absolute inset-0 rounded-full border border-brand/40 animate-pulse-ring" })] }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("span", { className: "text-[11px] font-semibold text-brand uppercase tracking-wider", children: "Coach ao vivo" }), _jsx("p", { className: "text-sm md:text-base font-medium", children: currentCue })] })] })), _jsxs("div", { className: "flex items-center justify-center gap-6", children: [_jsx("button", { onClick: toggleRun, className: `w-16 h-16 rounded-full flex items-center justify-center text-white transition-all duration-200 shadow-lg
            ${status === 'running' ? 'bg-accent-orange shadow-accent-orange/20' : 'bg-accent-green shadow-accent-green/20'}`, children: status === 'running' ? _jsx(Pause, { size: 28 }) : _jsx(Play, { size: 28 }) }), _jsx("button", { onClick: stopRun, className: "w-12 h-12 rounded-full bg-accent-red/20 text-accent-red hover:bg-accent-red/30 flex items-center justify-center transition-all", children: _jsx(StopCircle, { size: 20 }) }), _jsx("button", { className: "w-12 h-12 rounded-xl bg-surface-200 text-text-secondary hover:text-text-primary hover:bg-surface-300 flex items-center justify-center transition-all border border-border-light", children: _jsx(Map, { size: 20 }) })] })] }));
}
//# sourceMappingURL=RunMode.js.map