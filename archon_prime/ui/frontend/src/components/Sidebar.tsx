import React from 'react';
import { 
  LayoutDashboard, 
  Settings, 
  Home, 
  LogOut
} from 'lucide-react';

interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  isMobileOpen: boolean;
  setIsMobileOpen: (open: boolean) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentPath, onNavigate, isMobileOpen, setIsMobileOpen }) => {
  const navItems = [
    { path: '/', label: 'Home', icon: Home },
    { path: '/dashboard', label: 'Live Dashboard', icon: LayoutDashboard },
    { path: '/admin', label: 'System Admin', icon: Settings },
  ];

  return (
    <>
      {isMobileOpen && (
        <div 
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside className={`fixed top-0 left-0 z-30 h-full w-64 bg-archon-card border-r border-archon-border transition-transform duration-300 ease-in-out ${isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="flex flex-col h-full">
          <div className="p-6 border-b border-archon-border flex items-center gap-3">
            <div className="h-10 w-10 bg-gradient-to-br from-[#1e4a8a] to-[#153e75] rounded-lg flex flex-col items-center justify-center text-white shadow-lg shadow-blue-900/20 border border-blue-700/30 flex-shrink-0">
              <span className="text-[5px] font-bold tracking-wider text-blue-100/80 mt-0.5">ARCHON</span>
              <span className="text-lg font-black leading-none tracking-tighter -mt-0.5">RI</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold tracking-tight text-white leading-none">ARCHON</span>
              <span className="text-[7px] font-bold text-blue-400 tracking-[0.15em] mt-1 whitespace-nowrap">RESEARCH & INTELLIGENCE</span>
            </div>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2">
            {navItems.map((item) => (
              <button
                key={item.path}
                onClick={() => {
                  onNavigate(item.path);
                  setIsMobileOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${currentPath === item.path ? 'bg-archon-accent/10 text-archon-accentLight border border-archon-accent/20' : 'text-gray-400 hover:bg-archon-border/50 hover:text-white'}`}
              >
                <item.icon className="w-5 h-5" />
                {item.label}
              </button>
            ))}
          </nav>

          <div className="p-4 border-t border-archon-border">
            <div className="bg-archon-bg p-4 rounded-lg border border-archon-border">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-archon-success animate-pulse"></div>
                <span className="text-xs text-gray-400 font-mono">SYSTEM ONLINE</span>
              </div>
              <p className="text-xs text-gray-500">v2.0.0</p>
            </div>
            <button className="mt-4 w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
