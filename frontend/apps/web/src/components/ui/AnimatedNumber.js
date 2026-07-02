import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
/** Conta de 0 até `value` com easing — micro-interação sóbria (sem infantilizar). */
export default function AnimatedNumber({ value, decimals = 0, duration = 650, className, }) {
    const [display, setDisplay] = useState(0);
    const start = useRef(null);
    useEffect(() => {
        let raf = 0;
        start.current = null;
        const step = (t) => {
            if (start.current == null)
                start.current = t;
            const p = Math.min((t - start.current) / duration, 1);
            const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
            setDisplay(value * eased);
            if (p < 1)
                raf = requestAnimationFrame(step);
        };
        raf = requestAnimationFrame(step);
        return () => cancelAnimationFrame(raf);
    }, [value, duration]);
    return _jsx("span", { className: className, children: display.toFixed(decimals) });
}
//# sourceMappingURL=AnimatedNumber.js.map