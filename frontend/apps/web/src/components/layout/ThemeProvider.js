import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useContext, useEffect, useState } from 'react';
const ThemeContext = createContext({
    theme: 'dark',
    setTheme: () => { },
});
export function ThemeProvider({ children }) {
    const [theme, setThemeState] = useState(() => {
        const saved = localStorage.getItem('strider-theme');
        return saved || 'dark';
    });
    const setTheme = (t) => {
        setThemeState(t);
        localStorage.setItem('strider-theme', t);
    };
    useEffect(() => {
        const root = document.documentElement;
        if (theme === 'dark') {
            root.classList.add('dark');
        }
        else {
            root.classList.remove('dark');
        }
    }, [theme]);
    return (_jsx(ThemeContext.Provider, { value: { theme, setTheme }, children: children }));
}
export const useTheme = () => useContext(ThemeContext);
//# sourceMappingURL=ThemeProvider.js.map