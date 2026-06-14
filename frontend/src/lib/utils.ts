// Path: frontend/src/lib/utils.ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", maximumFractionDigits: 2,
  }).format(amount);
}

export function formatCompact(amount: number): string {
  if (amount >= 10_000_000) return `₹${(amount / 10_000_000).toFixed(2)}Cr`;
  if (amount >= 100_000)    return `₹${(amount / 100_000).toFixed(2)}L`;
  if (amount >= 1_000)      return `₹${(amount / 1_000).toFixed(2)}K`;
  return `₹${amount.toFixed(2)}`;
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function getPnLColor(value: number): string {
  return value >= 0 ? "text-green-400" : "text-red-400";
}

export function getPnLBg(value: number): string {
  return value >= 0
    ? "bg-green-400/10 border-green-500/20"
    : "bg-red-400/10 border-red-500/20";
}
