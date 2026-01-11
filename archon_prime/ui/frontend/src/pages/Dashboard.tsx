import React, { useState, useEffect } from 'react';
import MetricCard from '../components/MetricCard';
import PnlChart from '../components/PnlChart';
import PositionsTable from '../components/PositionsTable';
import { Position, Metric } from '../types';
import { RefreshCw, Download, Filter } from 'lucide-react';

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [positions, setPositions] = useState<Position[]>([
    { id: '1', symbol: 'BTC-PERP', side: 'LONG', size: 1.5, entryPrice: 62400, markPrice: 63100, pnl: 1050, pnlPercent: 1.12 },
    { id: '2', symbol: 'ETH-PERP', side: 'SHORT', size: 10.0, entryPrice: 3100, markPrice: 3050, pnl: 500, pnlPercent: 1.61 },
    { id: '3', symbol: 'SOL-PERP', side: 'LONG', size: 500, entryPrice: 145.20, markPrice: 142.50, pnl: -1350, pnlPercent: -1.86 },
    { id: '4', symbol: 'WIF-PERP', side: 'LONG', size: 10000, entryPrice: 2.45, markPrice: 2.80, pnl: 3500, pnlPercent: 14.2 },
  ]);

  const refreshData = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 800);
  };

  // Simulate real-time market data updates
  useEffect(() => {
    const interval = setInterval(() => {
      setPositions(currentPositions => 
        currentPositions.map(pos => {
          // Simulate micro-price movements (Random Walk)
          const volatility = 0.0005; // 0.05% volatility per tick
          const change = 1 + (Math.random() * volatility * 2 - volatility);
          const newMarkPrice = pos.markPrice * change;
          
          // Recalculate PnL based on new price
          const priceDiff = pos.side === 'LONG' 
            ? newMarkPrice - pos.entryPrice 
            : pos.entryPrice - newMarkPrice;
            
          const newPnl = priceDiff * pos.size;
          const newPnlPercent = (newPnl / (pos.entryPrice * pos.size)) * 100;

          return {
            ...pos,
            markPrice: newMarkPrice,
            pnl: newPnl,
            pnlPercent: parseFloat(newPnlPercent.toFixed(2))
          };
        })
      );
    }, 1500); // Update every 1.5s

    return () => clearInterval(interval);
  }, []);

  const metrics: Metric[] = [
    { label: 'Total Portfolio Value', value: '$124,592.00', change: 2.4, trend: 'up' },
    { label: 'Daily PnL', value: '+$1,250.50', change: 5.1, trend: 'up' },
    { label: 'Open Exposure', value: '$45,000.00', change: -1.2, trend: 'neutral' },
    { label: 'Win Rate (24h)', value: '68.5%', change: 3.2, trend: 'up' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Market Overview</h1>
          <p className="text-gray-400 text-sm mt-1">Real-time trading performance and active positions</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-3 py-2 bg-archon-card hover:bg-archon-border border border-archon-border rounded text-sm text-gray-300 transition-colors">
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button 
            onClick={refreshData}
            className={`flex items-center gap-2 px-3 py-2 bg-archon-accent hover:bg-blue-600 rounded text-sm text-white font-medium transition-all ${loading ? 'opacity-70' : ''}`}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m, i) => <MetricCard key={i} metric={m} />)}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-archon-card border border-archon-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold text-white">Equity Curve</h2>
            <div className="flex gap-2">
               {['1H', '1D', '1W', '1M'].map((tf) => (
                 <button 
                  key={tf} 
                  className={`px-3 py-1 text-xs rounded-full ${tf === '1D' ? 'bg-archon-accent text-white' : 'text-gray-400 hover:text-white'}`}
                 >
                   {tf}
                 </button>
               ))}
            </div>
          </div>
          <PnlChart />
        </div>

        <div className="bg-archon-card border border-archon-border rounded-xl p-6">
          <h2 className="text-lg font-bold text-white mb-4">Risk Allocation</h2>
          <div className="flex items-center justify-center h-[200px] text-gray-500">
             {/* Simple visual representation for risk */}
             <div className="relative w-40 h-40 rounded-full border-[12px] border-archon-border flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-[12px] border-archon-accent border-r-transparent rotate-45"></div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">65%</div>
                  <div className="text-xs text-gray-400">Utilized</div>
                </div>
             </div>
          </div>
          <div className="space-y-3 mt-4">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Margin Used</span>
              <span className="text-white">$82,100</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Free Margin</span>
              <span className="text-white">$42,492</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Leverage</span>
              <span className="text-archon-warning">4.5x</span>
            </div>
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="bg-archon-card border border-archon-border rounded-xl overflow-hidden">
        <div className="p-6 border-b border-archon-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h2 className="text-lg font-bold text-white">Active Positions</h2>
          <div className="flex gap-2">
            <button className="flex items-center gap-2 px-3 py-1.5 border border-archon-border rounded text-xs text-gray-300 hover:text-white">
              <Filter className="w-3 h-3" />
              Filter
            </button>
          </div>
        </div>
        <PositionsTable positions={positions} />
      </div>
    </div>
  );
};

export default Dashboard;