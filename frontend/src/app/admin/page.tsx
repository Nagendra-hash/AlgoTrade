"use client";
// Path: frontend/src/app/admin/page.tsx
import { DashboardLayout } from "@/components/layout/DashboardLayout";

export default function Page() {
  return (
    <DashboardLayout>
      <div className="flex items-center justify-center h-64 text-center">
        <div>
          <div className="h-16 w-16 rounded-2xl bg-gray-800 flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">🚧</span>
          </div>
          <h2 className="text-white font-bold text-xl mb-2">Admin Panel</h2>
          <p className="text-gray-400 text-sm">Coming soon — this module is under development.</p>
        </div>
      </div>
    </DashboardLayout>
  );
}
