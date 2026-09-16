import React, { useEffect, useState } from 'react';
import { 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  Clock, 
  Trash2,
  SlidersHorizontal,
  Map
} from 'lucide-react';
import { StreamConnectionState } from '../types/telemetry';
import { Link } from 'react-router-dom';

interface HeaderProps {
  roverId: number | null;
  overallState: StreamConnectionState;
  backendUrl: string;
  onReconnect: () => void;
  onClearHistory: () => void;
  onOpenSettings: () => void;
  lastUpdated: Date | null;
}

export const Header: React.FC<HeaderProps> = ({
  roverId,
  overallState,
  backendUrl,
  onReconnect,
  onClearHistory,
  onOpenSettings,
  lastUpdated,
}) => {
  const [sessionTime, setSessionTime] = useState('00:00:00');
  const [secondsAgo, setSecondsAgo] = useState<number | null>(null);

  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - start) / 1000);
      const hrs = String(Math.floor(elapsed / 3600)).padStart(2, '0');
      const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
      const secs = String(elapsed % 60).padStart(2, '0');
      setSessionTime(`${hrs}:${mins}:${secs}`);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!lastUpdated) {
      setSecondsAgo(null);
      return;
    }
    const updateDiff = () => {
      const diff = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);
      setSecondsAgo(diff);
    };
    updateDiff();
    const interval = setInterval(updateDiff, 1000);
    return () => clearInterval(interval);
  }, [lastUpdated]);

  const cleanHost = backendUrl.replace(/^https?:\/\//, '').replace(/\/+$/, '');

  const renderStatus = () => {
    switch (overallState) {
      case 'connected':
        return (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span>LIVE</span>
          </div>
        );
      case 'connecting':
        return (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-950/60 border border-amber-800/60 text-amber-400 text-xs font-mono">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>CONNECTING</span>
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-950/60 border border-rose-800/60 text-rose-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-rose-500"></span>
            <span>DISCONNECTED</span>
          </div>
        );
      default:
        return (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/60 text-zinc-400 text-xs font-mono">
            <WifiOff className="w-3 h-3" />
            <span>STANDBY</span>
          </div>
        );
    }
  };

  return (
    <header className="h-10 px-3 bg-[#16171c] border-b border-[#22252b] flex items-center justify-between text-xs select-none shrink-0 z-30">
      
      {/* Left section: Title & Rover ID */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-4 bg-blue-600 rounded-xs"></div>
          <span className="font-semibold text-slate-200 tracking-wide text-[13px]">
            ROVER TELEMETRY STATION
          </span>
        </div>

        <span className="text-zinc-600">|</span>

        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#1e2229] border border-[#2c323b] text-zinc-300 font-mono text-[11px]">
          <span className="text-zinc-500">UNIT:</span>
          <span className="font-bold text-slate-200">{roverId ? `ROVER #${roverId}` : 'ROVER-01'}</span>
        </div>

        <div className="hidden md:flex items-center gap-1.5 text-[11px] text-zinc-400 font-mono">
          <span className="text-zinc-600">TARGET:</span>
          <span className="text-zinc-300 truncate max-w-[200px]">{cleanHost}</span>
        </div>
      </div>

      {/* Right section: Sync, MET, Status & Actions */}
      <div className="flex items-center gap-3">
        
        {/* Packet sync */}
        <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-mono text-zinc-400">
          <Wifi className="w-3 h-3 text-zinc-500" />
          <span className="text-zinc-500">SYNC:</span>
          {secondsAgo !== null ? (
            <span className={secondsAgo < 5 ? 'text-emerald-400 font-medium' : 'text-amber-400'}>
              {secondsAgo === 0 ? 'NOW' : `${secondsAgo}s ago`}
            </span>
          ) : (
            <span className="text-zinc-500">WAITING</span>
          )}
        </div>

        {/* MET clock */}
        <div className="flex items-center gap-1 text-[11px] font-mono text-zinc-300 bg-[#1e2229] px-2 py-0.5 rounded border border-[#2c323b]">
          <Clock className="w-3 h-3 text-zinc-500" />
          <span className="text-zinc-500">MET:</span>
          <span className="font-medium text-zinc-200">{sessionTime}</span>
        </div>

        {/* Connection status badge */}
        {renderStatus()}

        {/* Action buttons */}
        <div className="flex items-center gap-1 border-l border-zinc-800 pl-2">
          <button
            onClick={onReconnect}
            title="Reconnect SSE streams"
            className="p-1 rounded bg-[#1e2229] hover:bg-[#272b35] border border-[#2c323b] text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onClearHistory}
            title="Clear rolling buffers"
            className="p-1 rounded bg-[#1e2229] hover:bg-[#272b35] border border-[#2c323b] text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onOpenSettings}
            title="Station Settings"
            className="p-1 rounded bg-[#1e2229] hover:bg-[#272b35] border border-[#2c323b] text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>

    </header>
  );
};
