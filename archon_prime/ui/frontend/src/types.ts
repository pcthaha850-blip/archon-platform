export interface Position {
  id: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  size: number;
  entryPrice: number;
  markPrice: number;
  pnl: number;
  pnlPercent: number;
}

export interface SystemStatus {
  service: string;
  status: 'operational' | 'degraded' | 'down';
  latency: number;
}

export interface Plugin {
  id: string;
  name: string;
  version: string;
  status: 'active' | 'inactive';
  description: string;
}

export interface Metric {
  label: string;
  value: string | number;
  change?: number; // percentage
  trend?: 'up' | 'down' | 'neutral';
}

export enum ViewState {
  LANDING = 'LANDING',
  DASHBOARD = 'DASHBOARD',
  ADMIN = 'ADMIN'
}