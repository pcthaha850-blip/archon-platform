import React from 'react';
import { ViewState } from '../types';
import { ArrowRight, Zap, Shield, Globe, Cpu } from 'lucide-react';

interface LandingProps {
  onGetStarted: () => void;
}

const Landing: React.FC<LandingProps> = ({ onGetStarted }) => {
  return (
    <div className="min-h-screen bg-archon-bg flex flex-col">
      {/* Hero Section */}
      <section className="relative flex-1 flex flex-col items-center justify-center text-center px-4 py-20 overflow-hidden">
        {/* Abstract Background Decoration */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-archon-accent/10 rounded-full blur-[100px] pointer-events-none"></div>
        
        <div className="relative z-10 max-w-4xl mx-auto space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-archon-border/50 border border-archon-border backdrop-blur-sm">
            <span className="flex h-2 w-2 rounded-full bg-archon-success"></span>
            <span className="text-xs font-medium text-gray-300">Archon V2 is Live</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-white">
            Algorithmic Trading, <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-teal-400">Democratized.</span>
          </h1>
          
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Access institutional-grade tools, real-time GCC market data, and AI-driven analytics in a unified workspace.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button 
              onClick={onGetStarted}
              className="px-8 py-4 bg-white text-black font-bold rounded-lg hover:bg-gray-200 transition-colors flex items-center gap-2 group"
            >
              Launch Platform
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
            <button className="px-8 py-4 bg-transparent border border-archon-border text-white font-medium rounded-lg hover:bg-archon-border/50 transition-colors">
              Read Documentation
            </button>
          </div>
        </div>

        {/* Dashboard Preview */}
        <div className="relative z-10 mt-16 w-full max-w-6xl mx-auto">
          <div className="relative rounded-xl border border-archon-border bg-archon-card shadow-2xl overflow-hidden aspect-video group">
            <div className="absolute inset-0 bg-gradient-to-t from-archon-bg via-transparent to-transparent z-20"></div>
            {/* Mock UI Representation */}
            <div className="p-4 h-full flex flex-col gap-4 opacity-80 group-hover:opacity-100 transition-opacity duration-500">
               <div className="h-16 w-full border-b border-archon-border flex items-center justify-between px-4">
                  <div className="w-32 h-6 bg-gray-700 rounded animate-pulse"></div>
                  <div className="flex gap-4">
                    <div className="w-8 h-8 bg-gray-700 rounded-full animate-pulse"></div>
                    <div className="w-8 h-8 bg-gray-700 rounded-full animate-pulse"></div>
                  </div>
               </div>
               <div className="flex-1 grid grid-cols-12 gap-4 p-4">
                  <div className="col-span-3 bg-gray-800/50 rounded-lg animate-pulse"></div>
                  <div className="col-span-6 bg-gray-800/50 rounded-lg flex flex-col p-4">
                    <div className="h-40 w-full bg-gray-700/30 rounded mt-auto"></div>
                  </div>
                  <div className="col-span-3 bg-gray-800/50 rounded-lg animate-pulse"></div>
               </div>
            </div>
            
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-30">
               <button onClick={onGetStarted} className="px-6 py-3 bg-archon-accent text-white font-bold rounded-full shadow-lg hover:scale-105 transition-transform">
                 View Live Demo
               </button>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-4 border-t border-archon-border bg-[#1A1D21]">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
           {[
             { icon: Zap, title: "Microsecond Latency", desc: "Optimized execution engine for high-frequency strategies." },
             { icon: Shield, title: "Enterprise Security", desc: "Bank-grade encryption and key management protocols." },
             { icon: Globe, title: "Global Markets", desc: "Direct access to Crypto, Forex, and GCC Equities." },
             { icon: Cpu, title: "AI Core", desc: "Built-in ML models for sentiment and trend prediction." }
           ].map((f, i) => (
             <div key={i} className="p-6 rounded-2xl bg-archon-card border border-archon-border hover:border-gray-600 transition-colors">
               <div className="w-12 h-12 bg-archon-bg rounded-lg border border-archon-border flex items-center justify-center mb-4 text-archon-accent">
                 <f.icon className="w-6 h-6" />
               </div>
               <h3 className="text-lg font-bold text-white mb-2">{f.title}</h3>
               <p className="text-gray-400 text-sm">{f.desc}</p>
             </div>
           ))}
        </div>
      </section>
      
      <footer className="py-8 border-t border-archon-border text-center text-gray-500 text-sm">
        <p>&copy; 2024 Archon Platform. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default Landing;