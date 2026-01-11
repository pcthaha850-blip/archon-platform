import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { Metric } from '../types';

interface MetricCardProps {
  metric: Metric;
}

const MetricCard: React.FC<MetricCardProps> = ({ metric }) => {
  const isPositive = metric.trend === 'up';
  const isNegative = metric.trend === 'down';

  return (
    <div className="bg-archon-card border border-archon-border rounded-xl p-6 hover:border-archon-accent/30 transition-all duration-200">
      <h3 className="text-sm font-medium text-gray-400 mb-2">{metric.label}</h3>
      <div className="flex items-end justify-between">
        <span className="text-2xl font-bold text-white tracking-tight">{metric.value}</span>
        
        {metric.change !== undefined && (
          <div className={`
            flex items-center text-xs font-medium px-2 py-1 rounded
            ${isPositive ? 'text-archon-success bg-archon-success/10' : ''}
            ${isNegative ? 'text-archon-danger bg-archon-danger/10' : ''}
            ${!isPositive && !isNegative ? 'text-gray-400 bg-gray-800' : ''}
          `}>
            {isPositive && <ArrowUpRight className="w-3 h-3 mr-1" />}
            {isNegative && <ArrowDownRight className="w-3 h-3 mr-1" />}
            {!isPositive && !isNegative && <Minus className="w-3 h-3 mr-1" />}
            {Math.abs(metric.change)}%
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricCard;