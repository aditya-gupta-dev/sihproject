import React, { useRef, useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ESPNode {
  x: number;
  y: number;
  id: number;
}

export const Simulation: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [nodes, setNodes] = useState<ESPNode[]>([]);
  const navigate = useNavigate();

  // Mine layout paths
  const paths = [
    { start: { x: 100, y: 150 }, end: { x: 300, y: 200 } },
    { start: { x: 300, y: 200 }, end: { x: 550, y: 150 } },
    { start: { x: 300, y: 200 }, end: { x: 350, y: 400 } },
    { start: { x: 100, y: 150 }, end: { x: 150, y: 350 } },
    { start: { x: 150, y: 350 }, end: { x: 350, y: 400 } },
    { start: { x: 150, y: 350 }, end: { x: 100, y: 550 } },
    { start: { x: 350, y: 400 }, end: { x: 450, y: 600 } },
    { start: { x: 100, y: 550 }, end: { x: 450, y: 600 } },
    { start: { x: 550, y: 150 }, end: { x: 700, y: 300 } },
    { start: { x: 450, y: 600 }, end: { x: 700, y: 550 } },
    { start: { x: 700, y: 300 }, end: { x: 700, y: 550 } },
  ];

  // Draw the simulation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Draw dark gritty background
    ctx.fillStyle = '#0a0a0c'; // Very dark base
    ctx.fillRect(0, 0, width, height);

    // Add some noise for a gritty look
    ctx.fillStyle = 'rgba(255, 255, 255, 0.02)';
    for (let i = 0; i < 2000; i++) {
      const nx = Math.random() * width;
      const ny = Math.random() * height;
      const size = Math.random() * 2;
      ctx.fillRect(nx, ny, size, size);
    }

    // Draw mine paths
    ctx.strokeStyle = '#2d2d35'; // Dark grey/brown for paths
    ctx.lineWidth = 20;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    ctx.beginPath();
    paths.forEach((path) => {
      ctx.moveTo(path.start.x, path.start.y);
      ctx.lineTo(path.end.x, path.end.y);
    });
    ctx.stroke();

    // Draw path center lines (like rails)
    ctx.strokeStyle = '#4a4a55';
    ctx.lineWidth = 2;
    ctx.setLineDash([10, 15]);
    ctx.beginPath();
    paths.forEach((path) => {
      ctx.moveTo(path.start.x, path.start.y);
      ctx.lineTo(path.end.x, path.end.y);
    });
    ctx.stroke();
    ctx.setLineDash([]); // Reset line dash

    // Draw ESP Nodes
    nodes.forEach((node) => {
      // Draw a glowing effect
      const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, 20);
      gradient.addColorStop(0, 'rgba(52, 211, 153, 0.4)'); // emerald-400
      gradient.addColorStop(1, 'rgba(52, 211, 153, 0)');
      
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 20, 0, Math.PI * 2);
      ctx.fill();

      // Draw the ESP chip icon
      ctx.fillStyle = '#1e1e24';
      ctx.fillRect(node.x - 10, node.y - 10, 20, 20);
      
      // Chip details (pins)
      ctx.fillStyle = '#9ca3af'; // gray-400
      for (let i = 0; i < 3; i++) {
        // Left pins
        ctx.fillRect(node.x - 14, node.y - 7 + (i * 6), 4, 2);
        // Right pins
        ctx.fillRect(node.x + 10, node.y - 7 + (i * 6), 4, 2);
      }

      // Chip core
      ctx.fillStyle = '#34d399'; // emerald-400
      ctx.fillRect(node.x - 4, node.y - 4, 8, 8);

      // Label
      ctx.fillStyle = '#a7f3d0';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`ESP-${node.id}`, node.x, node.y + 20);
    });

  }, [nodes, paths]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Optional: Snap to closest path logic here if desired, 
    // for now we just add it exactly where clicked.

    setNodes((prev) => [
      ...prev,
      { x, y, id: prev.length > 0 ? Math.max(...prev.map(n => n.id)) + 1 : 1 },
    ]);
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0a0a0c] text-zinc-200 overflow-hidden font-mono">
      {/* Top Header */}
      <header className="h-14 bg-[#111217] border-b border-[#22252b] flex items-center px-4 shrink-0 select-none">
        <button 
          onClick={() => navigate('/')}
          className="p-2 hover:bg-[#1a1b23] rounded-md text-zinc-400 hover:text-zinc-100 transition-colors mr-4"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-zinc-100">MINE NETWORK SIMULATION</h1>
          <div className="text-[10px] text-zinc-500 mt-0.5 flex items-center gap-2">
            <span>MAP: SECTOR 7G</span>
            <span>|</span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              DEPLOYMENT MODE ACTIVE
            </span>
          </div>
        </div>
      </header>

      {/* Canvas Container */}
      <main className="flex-1 relative w-full h-full flex items-center justify-center p-4">
        <div className="relative border border-[#22252b] rounded-lg overflow-hidden shadow-2xl bg-black/50">
          <canvas
            ref={canvasRef}
            width={800}
            height={700}
            onClick={handleCanvasClick}
            className="cursor-crosshair block"
          />
          {/* Overlay info */}
          <div className="absolute top-4 right-4 bg-[#111217]/80 backdrop-blur border border-[#22252b] p-3 rounded-md text-xs pointer-events-none">
            <h3 className="text-zinc-300 font-bold mb-2 uppercase text-[10px]">Instructions</h3>
            <ul className="text-zinc-500 space-y-1">
              <li>• Click on the map to deploy ESP nodes</li>
              <li>• Nodes build the mesh network</li>
              <li>• Active Nodes: <span className="text-emerald-400 font-bold">{nodes.length}</span></li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
};
