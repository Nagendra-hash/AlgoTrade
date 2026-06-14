// Backtest report export utilities — CSV & PDF
// Path: frontend/src/lib/export.ts
import type { CompareBacktestItem, BacktestTrade } from "@/hooks/useBacktest";

// ── CSV Export ───────────────────────────────────────────────

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeCSV(val: unknown): string {
  const s = String(val ?? "");
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function exportCSV(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.map(escapeCSV).join(","),
    ...rows.map((row) => headers.map((h) => escapeCSV(row[h])).join(",")),
  ];
  downloadBlob(lines.join("\n"), filename, "text/csv;charset=utf-8;");
}

// ── Compare Results → CSV ────────────────────────────────────

function exportTradesCSV(
  trades: BacktestTrade[],
  strategyLabel: string,
  symbol: string,
) {
  if (!trades.length) return;
  const rows = trades.map((t, i) => ({
    "#": i + 1,
    Entry: t.entry_date,
    Exit: t.exit_date,
    Side: t.side,
    Qty: t.qty,
    "Entry Price": t.entry_price,
    "Exit Price": t.exit_price,
    "P&L": t.pnl,
    "P&L %": t.pnl_pct,
  }));
  const slug = strategyLabel.replace(/\s+/g, "-").toLowerCase();
  exportCSV(rows, `backtest-trades-${slug}-${symbol}.csv`);
}

export function exportCompareResultsCSV(
  results: CompareBacktestItem[],
  symbol: string,
  timeframe: string,
  period: string,
) {
  // ── Part 1: Comparison metrics ──
  const metrics = [
    { key: "total_return", label: "Total Return (%)" },
    { key: "total_pnl", label: "Total P&L (₹)" },
    { key: "final_capital", label: "Final Capital (₹)" },
    { key: "total_trades", label: "Total Trades" },
    { key: "win_rate", label: "Win Rate (%)" },
    { key: "max_drawdown", label: "Max Drawdown (%)" },
    { key: "profit_factor", label: "Profit Factor" },
    { key: "sharpe_ratio", label: "Sharpe Ratio" },
  ];

  const rows: Record<string, unknown>[] = [
    { Metric: `Backtest Comparison — ${symbol} (${timeframe}/${period})` },
    ...metrics.map((m) => {
      const row: Record<string, unknown> = { Metric: m.label };
      for (const item of results) {
        row[item.label] = (item.result as any)[m.key];
      }
      return row;
    }),
  ];

  exportCSV(rows, `backtest-compare-${symbol}-${timeframe}-${period}.csv`);

  // ── Part 2: Per-strategy trade logs (separate files) ──
  for (const item of results) {
    exportTradesCSV(item.result.trades ?? [], item.label, symbol);
  }
}

// ── Single Backtest Trades → CSV ─────────────────────────────

export function exportSingleTradesCSV(
  trades: BacktestTrade[],
  symbol: string,
  strategyName: string,
) {
  if (!trades.length) return;
  const rows = trades.map((t, i) => ({
    "#": i + 1,
    Entry: t.entry_date,
    Exit: t.exit_date,
    Side: t.side,
    Qty: t.qty,
    "Entry Price": t.entry_price,
    "Exit Price": t.exit_price,
    "P&L": t.pnl,
    "P&L %": t.pnl_pct,
  }));
  exportCSV(rows, `backtest-trades-${symbol}-${strategyName.replace(/\s+/g, "-").toLowerCase()}.csv`);
}

// ── PDF Export ───────────────────────────────────────────────

export async function exportToPDF(
  elementId: string,
  filename: string,
): Promise<void> {
  try {
    const el = document.getElementById(elementId);
    if (!el) {
      console.error(`Export PDF failed: element #${elementId} not found`);
      return;
    }

    const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
      import("html2canvas"),
      import("jspdf"),
    ]);

    const canvas = await html2canvas(el, {
      scale: 2,
      backgroundColor: "#111827",
      useCORS: true,
      logging: false,
    });

    const imgData = canvas.toDataURL("image/png");
    const pdf = new jsPDF("p", "mm", "a4");
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

    let heightLeft = pdfHeight;
    let position = 0;
    const pageHeight = pdf.internal.pageSize.getHeight();

    // First page
    pdf.addImage(imgData, "PNG", 0, position, pdfWidth, pdfHeight);
    heightLeft -= pageHeight;

    // Additional pages if content overflows
    while (heightLeft > 0) {
      position = heightLeft - pdfHeight;
      pdf.addPage();
      pdf.addImage(imgData, "PNG", 0, position, pdfWidth, pdfHeight);
      heightLeft -= pageHeight;
    }

    pdf.save(filename);
  } catch (err) {
    console.error("Export PDF failed:", err);
  }
}
