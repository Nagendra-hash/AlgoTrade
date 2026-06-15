"use client";
import { useEffect } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => { console.error("Page error:", error); }, [error]);
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-center max-w-md px-4">
        <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-white font-bold text-xl mb-2">Something went wrong</h2>
        <p className="text-gray-400 text-sm mb-6">{error.message || "An unexpected error occurred"}</p>
        <button onClick={reset}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold mx-auto transition-all">
          <RefreshCw className="h-4 w-4" /> Try Again
        </button>
      </div>
    </div>
  );
}
