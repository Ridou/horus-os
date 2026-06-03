"use client";

import { TrendingUp, TrendingDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { MiniChart } from "./MiniChart";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon;
  trend?: number;
  data?: number[];
  className?: string;
}

/** Title, value, optional trend percentage, and optional inline sparkline. */
export function MetricCard({
  title,
  value,
  icon: Icon,
  trend,
  data,
  className,
}: MetricCardProps) {
  const trendPositive = trend !== undefined && trend > 0;
  const trendNegative = trend !== undefined && trend < 0;

  return (
    <div
      className={cn(
        "border border-border-subtle bg-bg-secondary p-4 transition-colors border-glow",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] uppercase tracking-wider text-text-muted">
          {title}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5 text-text-muted" />}
      </div>
      <div className="mt-1 flex items-end justify-between gap-2">
        <span className="text-2xl font-bold leading-none text-text-primary tabular-nums">
          {value}
        </span>
        {trend !== undefined && trend !== 0 && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-[10px] font-medium",
              trendPositive && "text-success",
              trendNegative && "text-danger",
            )}
          >
            {trendPositive ? (
              <TrendingUp size={12} />
            ) : (
              <TrendingDown size={12} />
            )}
            {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>
      {data && data.length >= 2 && (
        <div className="pt-2">
          <MiniChart data={data} />
        </div>
      )}
    </div>
  );
}

export default MetricCard;
