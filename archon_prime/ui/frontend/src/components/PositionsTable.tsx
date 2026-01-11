import React from 'react';
import { Position } from '../types';
import { Wifi, Activity } from 'lucide-react';

interface PositionsTableProps {
  positions: Position[];
}

const PositionsTable: React.FC<PositionsTableProps> = ({ positions }) => {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-gray-500 uppercase bg-archon-bg border-b border-archon-border">
          <tr>
            <th className="px-6 py-4 font-medium">Symbol</th>
            <th className="px-6 py-4 font-medium">Side</th>
            <th className="px-6 py-4 font-medium">Size</th>
            <th className="px-6 py-4 font-medium">Entry Price</th>
            <th className="px-6 py-4 font-medium">Mark Price</th>
            <th className="px-6 py-4 font-medium text-right">PnL</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-archon-border">
          {positions.map((pos) => {
            const isProfit = pos.pnl >= 0;
            // Generate a fake "streaming" spread/value based on the id to be consistent per render cycle if needed, 
            // but since we want it to look "live", using a small derivation from mark price is good.
            const indexPrice = pos.markPrice * (1 + (pos.side === 'LONG' ? 0.0002 : -0.0002));
            
            return (
              <tr key={pos.id} className="hover:bg-archon-border/20 transition-colors">
                <td className="px-6 py-4 font-medium text-white">
                  <div className="flex items-center gap-2">
                    {pos.symbol}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`
                    inline-flex items-center px-2 py-0.5 rounded text-xs font-bold
                    ${pos.side === 'LONG' ? 'bg-archon-success/20 text-archon-success' : 'bg-archon-danger/20 text-archon-danger'}
                  `}>
                    {pos.side}
                  </span>
                </td>
                <td className="px-6 py-4 text-gray-300">{pos.size}</td>
                <td className="px-6 py-4 text-gray-300">${pos.entryPrice.toLocaleString()}</td>
                <td className="px-6 py-4">
                   <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                         <span className="text-white font-mono font-medium tracking-tight">
                            ${pos.markPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                         </span>
                         <span className="relative flex h-2 w-2" title="Live Data Feed">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-archon-accent opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-archon-accent"></span>
                         </span>
                      </div>
                      <div className="flex items-center gap-1 text-[10px] text-gray-500 font-mono mt-0.5">
                         <Activity className="w-3 h-3 text-archon-success/60" />
                         <span>Idx: {indexPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                      </div>
                   </div>
                </td>
                <td className={`px-6 py-4 text-right font-medium ${isProfit ? 'text-archon-success' : 'text-archon-danger'}`}>
                  {isProfit ? '+' : ''}{pos.pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD 
                  <span className="block text-xs opacity-80">({pos.pnlPercent.toFixed(2)}%)</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default PositionsTable;