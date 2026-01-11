import React, { useState } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import AdminPanel from './pages/Admin';
import Landing from './pages/Landing';
import { Menu } from 'lucide-react';

const App: React.FC = () => {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // If landing page, render without sidebar layout
  if (location.pathname === '/') {
    return <Landing onGetStarted={() => navigate('/dashboard')} />;
  }

  return (
    <div className="min-h-screen bg-archon-bg text-archon-text font-sans flex">
      <Sidebar 
        currentPath={location.pathname}
        onNavigate={navigate}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
      />

      {/* Main Content Area */}
      <main className="flex-1 lg:ml-64 min-h-screen flex flex-col">
        {/* Mobile Header */}
        <header className="lg:hidden h-16 bg-archon-card border-b border-archon-border flex items-center justify-between px-4 sticky top-0 z-10">
           <div className="flex items-center gap-3">
             <div className="h-8 w-8 bg-[#153e75] rounded flex flex-col items-center justify-center text-white border border-blue-700/30">
                <span className="text-[4px] font-bold tracking-wider text-blue-100/80 mt-0.5">ARCHON</span>
                <span className="text-sm font-black leading-none tracking-tighter -mt-0.5">RI</span>
             </div>
             <div className="flex flex-col">
                <span className="font-bold text-white leading-none text-sm">ARCHON</span>
                <span className="text-[6px] font-bold text-blue-400 tracking-wider">RESEARCH & INTELLIGENCE</span>
             </div>
           </div>
           <button 
             onClick={() => setIsMobileOpen(true)}
             className="p-2 text-gray-400 hover:text-white"
           >
             <Menu className="w-6 h-6" />
           </button>
        </header>

        {/* View Content */}
        <div className="flex-1 p-4 md:p-8 overflow-y-auto">
          <div className="max-w-7xl mx-auto w-full">
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/admin" element={<AdminPanel />} />
            </Routes>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
