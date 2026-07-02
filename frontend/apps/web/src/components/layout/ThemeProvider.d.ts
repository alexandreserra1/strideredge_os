type Theme = 'dark' | 'light';
interface ThemeContextType {
    theme: Theme;
    setTheme: (t: Theme) => void;
}
export declare function ThemeProvider({ children }: {
    children: React.ReactNode;
}): import("react").JSX.Element;
export declare const useTheme: () => ThemeContextType;
export {};
//# sourceMappingURL=ThemeProvider.d.ts.map