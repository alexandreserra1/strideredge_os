import type { ReactNode } from 'react';
interface KpiCardProps {
    label: string;
    value: string | number;
    sub?: string;
    icon?: ReactNode;
    accent?: 'lime' | 'green' | 'yellow' | 'red' | 'orange' | 'blue';
    trend?: 'up' | 'down' | 'stable';
    children?: ReactNode;
}
export default function KpiCard({ label, value, sub, icon, accent, trend, children }: KpiCardProps): import("react").JSX.Element;
export {};
//# sourceMappingURL=KpiCard.d.ts.map