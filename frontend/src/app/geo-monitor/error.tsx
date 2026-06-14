"use client";
import { useEffect } from "react";
import { Globe, RefreshCw } from "lucide-react";

export default function GeoMonitorError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Geo Monitor error:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center max-w-md">
        <div className="h-16 w-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <Globe className="h-8 w-8 text-red-400" />
        </div>
        <h2 className="text-white font-bold text-lg">Failed to load Geopolitical Monitor</h2>
        <p className="text-gray-400 text-sm">
          Could not retrieve geopolitical news data. The news API may be unavailable.
        </p>
        <button onClick={reset}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl text-sm font-medium transition-all">
          <RefreshCw className="h-4 w-4" /> Try again
        </button>
      </div>
    </div>
  );
}
