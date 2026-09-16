import React, { useState } from 'react';
import { Header } from './components/Header';
import { VideoViewport } from './components/VideoViewport';
import { TemperaturePanel } from './components/TemperaturePanel';
import { DistancePanel } from './components/DistancePanel';
import { HumidityPanel } from './components/HumidityPanel';
import { LedControlPanel } from './components/LedControlPanel';
import { TelemetryHistoryChart } from './components/TelemetryHistoryChart';
import { EventLogPanel } from './components/EventLogPanel';
import { SettingsModal } from './components/SettingsModal';
import { useRoverTelemetry } from './hooks/useRoverTelemetry';
import { loadConfig, saveConfig } from './config/api';
import { DashboardConfig } from './types/telemetry';

export const Dashboard: React.FC = () => {
  const [config, setConfig] = useState<DashboardConfig>(loadConfig());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const {
    stats,
    activeRoverId,
    overallState,
    logs,
    reconnectAll,
    clearHistory,
    clearLogs,
    addLog,
  } = useRoverTelemetry(config.backendBaseUrl, config.historyLimit);

  const handleSaveConfig = (newCfg: DashboardConfig) => {
    const updated = saveConfig(newCfg);
    setConfig(updated);
    addLog('SYSTEM', 'info', `Target backend updated to ${updated.backendBaseUrl}`);
  };

  const lastUpdatedTimes = [
    stats.temp.lastUpdated?.getTime() ?? 0,
    stats.dist.lastUpdated?.getTime() ?? 0,
    stats.humd.lastUpdated?.getTime() ?? 0,
  ];
  const maxTimestamp = Math.max(...lastUpdatedTimes);
  const latestTelemetryDate = maxTimestamp > 0 ? new Date(maxTimestamp) : null;

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-[#111217] text-zinc-200 select-none">
      
      {/* Top Header */}
      <Header
        roverId={activeRoverId}
        overallState={overallState}
        backendUrl={config.backendBaseUrl}
        onReconnect={reconnectAll}
        onClearHistory={clearHistory}
        onOpenSettings={() => setIsSettingsOpen(true)}
        lastUpdated={latestTelemetryDate}
      />

      {/* Main Viewport Grid (Single-Page, Zero-Scroll) */}
      <main className="flex-1 min-h-0 p-2 gap-2 flex flex-col md:flex-row overflow-hidden">
        
        {/* Left Column: Optics Viewport + Time-series Timeline (56% width) */}
        <section className="w-full md:w-[56%] flex flex-col gap-2 h-full min-h-0">
          
          {/* Top Left: Video / Camera Monitor */}
          <div className="flex-[3] min-h-0 flex flex-col">
            <VideoViewport
              backendUrl={config.backendBaseUrl}
              roverId={activeRoverId}
              distAhead={stats.dist.current}
            />
          </div>

          {/* Bottom Left: Multi-stream Correlation Graph */}
          <div className="flex-[2] min-h-0 flex flex-col">
            <TelemetryHistoryChart
              tempStats={stats.temp}
              distStats={stats.dist}
              humdStats={stats.humd}
            />
          </div>

        </section>

        {/* Right Column: Controls, Primary Telemetry, Audit Logs (44% width) */}
        <section className="w-full md:w-[44%] flex flex-col gap-2 h-full min-h-0">
          
          {/* Top Right: Rover LED Control */}
          <div className="shrink-0">
            <LedControlPanel
              backendUrl={config.backendBaseUrl}
              roverId={activeRoverId}
              onLog={addLog}
            />
          </div>

          {/* Middle Right: 3 Metric Cards side-by-side */}
          <div className="grid grid-cols-3 gap-2 shrink-0">
            {/* Chassis Temperature */}
            <TemperaturePanel
              stats={stats.temp}
              highThreshold={config.highTempThreshold}
            />

            {/* Obstacle Distance Ahead */}
            <DistancePanel
              stats={stats.dist}
              lowThreshold={config.lowDistThreshold}
            />

            {/* Atmospheric Humidity */}
            <HumidityPanel
              stats={stats.humd}
              highThreshold={config.highHumdThreshold}
            />
          </div>

          {/* Bottom Right: Audit Log Terminal */}
          <div className="flex-1 min-h-0 flex flex-col">
            <EventLogPanel logs={logs} onClearLogs={clearLogs} />
          </div>

        </section>

      </main>

      {/* Slim Status Bar */}
      <footer className="h-6 px-3 bg-[#16171c] border-t border-[#22252b] flex items-center justify-between text-[10px] font-mono text-zinc-500 shrink-0 select-none">
        <div className="flex items-center gap-3">
          <span className="text-zinc-400 font-semibold">ROVER TELEMETRY TERMINAL</span>
          <span className="text-zinc-700">|</span>
          <span>SSE: /temp, /dist, /humd</span>
          <span className="text-zinc-700">|</span>
          <span>OPTICS: /video</span>
          <span className="text-zinc-700">|</span>
          <span>CMD: /led</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>EVENT-DRIVEN STREAMING (ZERO POLLING)</span>
        </div>
      </footer>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onSave={handleSaveConfig}
      />

    </div>
  );
};
