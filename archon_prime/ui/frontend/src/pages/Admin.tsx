import React from 'react';
import { Plugin, SystemStatus } from '../types';
import { CheckCircle, AlertTriangle, XCircle, Power, Activity } from 'lucide-react';

const AdminPanel: React.FC = () => {
  const systemStatus: SystemStatus[] = [
    { service: 'Order Execution Engine', status: 'operational', latency: 45 },
    { service: 'Market Data Feed', status: 'operational', latency: 12 },
    { service: 'Risk Management', status: 'operational', latency: 5 },
    { service: 'Plugin Manager', status: 'degraded', latency: 150 },
    { service: 'Notification Service', status: 'down', latency: 0 },
  ];

  const plugins: Plugin[] = [
    { id: '1', name: 'Binance Connector', version: '2.1.0', status: 'active', description: 'Real-time spot and futures trading on Binance.' },
    { id: '2', name: 'Coinbase Pro', version: '1.4.2', status: 'active', description: 'Institutional data feed integration.' },
    { id: '3', name: 'Sentiment Analysis', version: '0.9.5-beta', status: 'inactive', description: 'Twitter/X sentiment NLP module.' },
    { id: '4', name: 'Mean Reversion Bot', version: '3.0.1', status: 'active', description: 'Standard deviation based algo strategy.' },
  ];

  return (
    <div className="space-y-8">
       <div>
          <h1 className="text-2xl font-bold text-white">System Administration</h1>
          <p className="text-gray-400 text-sm mt-1">Manage platform services and plugins</p>
        </div>

      {/* System Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {systemStatus.map((status, idx) => (
          <div key={idx} className="bg-archon-card border border-archon-border rounded-xl p-5 flex items-start justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Service</p>
              <h3 className="font-semibold text-white">{status.service}</h3>
              <p className="text-xs text-gray-500 mt-2">Latency: {status.latency > 0 ? `${status.latency}ms` : 'N/A'}</p>
            </div>
            <div className={`
              w-8 h-8 rounded-full flex items-center justify-center
              ${status.status === 'operational' ? 'bg-archon-success/20 text-archon-success' : ''}
              ${status.status === 'degraded' ? 'bg-archon-warning/20 text-archon-warning' : ''}
              ${status.status === 'down' ? 'bg-archon-danger/20 text-archon-danger' : ''}
            `}>
              {status.status === 'operational' && <CheckCircle className="w-5 h-5" />}
              {status.status === 'degraded' && <AlertTriangle className="w-5 h-5" />}
              {status.status === 'down' && <XCircle className="w-5 h-5" />}
            </div>
          </div>
        ))}
      </div>

      {/* Plugins Section */}
      <div className="bg-archon-card border border-archon-border rounded-xl overflow-hidden">
        <div className="p-6 border-b border-archon-border">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-archon-accent" />
            Installed Plugins
          </h2>
        </div>
        <div className="divide-y divide-archon-border">
          {plugins.map((plugin) => (
            <div key={plugin.id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <h3 className="font-semibold text-white">{plugin.name}</h3>
                  <span className="px-2 py-0.5 bg-gray-800 text-gray-400 text-xs rounded border border-gray-700">v{plugin.version}</span>
                </div>
                <p className="text-sm text-gray-400 mt-1">{plugin.description}</p>
              </div>
              <div className="flex items-center gap-4">
                 <div className="flex items-center gap-2 text-sm">
                    <div className={`w-2 h-2 rounded-full ${plugin.status === 'active' ? 'bg-archon-success' : 'bg-gray-500'}`}></div>
                    <span className="text-gray-300 capitalize">{plugin.status}</span>
                 </div>
                 <button className={`
                    p-2 rounded-lg transition-colors border
                    ${plugin.status === 'active' 
                      ? 'bg-archon-danger/10 border-archon-danger/20 text-archon-danger hover:bg-archon-danger/20' 
                      : 'bg-archon-success/10 border-archon-success/20 text-archon-success hover:bg-archon-success/20'}
                 `}>
                   <Power className="w-4 h-4" />
                 </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AdminPanel;