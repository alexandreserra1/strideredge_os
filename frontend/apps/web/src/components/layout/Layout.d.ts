import type { ReactNode } from 'react';
interface LayoutProps {
    children: ReactNode;
    currentRoute: string;
    onNavigate: (route: string) => void;
    acwr?: number;
}
export default function Layout({ children, currentRoute, onNavigate, acwr }: LayoutProps): import("react").JSX.Element;
export {};
//# sourceMappingURL=Layout.d.ts.map