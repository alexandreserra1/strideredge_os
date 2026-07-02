import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import BottomNav from './BottomNav';
export default function Layout({ children, currentRoute, onNavigate, acwr }) {
    return (_jsxs("div", { className: "flex min-h-screen bg-surface", children: [_jsx(Sidebar, { currentRoute: currentRoute, onNavigate: onNavigate }), _jsxs("div", { className: "flex-1 flex flex-col min-w-0", children: [_jsx(Topbar, { acwr: acwr }), _jsx("main", { className: "flex-1 p-4 md:p-6 lg:p-8 pb-20 md:pb-8", children: children })] }), _jsx(BottomNav, { currentRoute: currentRoute, onNavigate: onNavigate })] }));
}
//# sourceMappingURL=Layout.js.map