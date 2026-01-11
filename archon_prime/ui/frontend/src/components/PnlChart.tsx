import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const data = [
  { time: '09:00', value: 1000 },
  { time: '10:00', value: 1200 },
  { time: '11:00', value: 1150 },
  { time: '12:00', value: 1380 },
  { time: '13:00', value: 1450 },
  { time: '14:00', value: 1600 },
  { time: '15:00', value: 1550 },
  { time: '16:00', value: 1800 },
  { time: '17:00', value: 1750 },
  { time: '18:00', value: 1950 },
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-archon-bg border border-archon-border p-3 rounded shadow-xl">
        <p className="text-gray-400 text-xs mb-1">{label}</p>
        <p className="text-archon-accent font-bold text-sm">
          ${payload[0].value.toLocaleString()}
        </p>
      </div>
    );
  }
  return null;
};

const PnlChart: React.FC = () => {
  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2E3339" vertical={false} />
          <XAxis 
            dataKey="time" 
            stroke="#6B7280" 
            fontSize={12} 
            tickLine={false}
            axisLine={false}
          />
          <YAxis 
            stroke="#6B7280" 
            fontSize={12} 
            tickFormatter={(value) => `$${value}`}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area 
            type="monotone" 
            dataKey="value" 
            stroke="#3B82F6" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorValue)" 
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PnlChart;