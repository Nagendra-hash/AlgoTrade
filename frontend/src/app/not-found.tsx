// Path: frontend/src/app/not-found.tsx
import Link from "next/link";
import { TrendingUp, Home } from "lucide-react";
export default function NotFound() {
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center text-center px-4">
      <TrendingUp className="h-16 w-16 text-gray-700 mb-6" />
      <h1 className="text-8xl font-black text-white mb-4">404</h1>
      <h2 className="text-2xl font-bold text-gray-300 mb-2">Page Not Found</h2>
      <p className="text-gray-400 mb-8 max-w-sm">The page you&apos;re looking for doesn&apos;t exist.</p>
      <Link href="/dashboard" className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-all">
        <Home className="h-4 w-4" /> Back to Dashboard
      </Link>
    </div>
  );
}
