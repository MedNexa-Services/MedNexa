import * as React from "react";
import { cn } from "cn";
import { Card } from "@/components/ui/card";

interface EmptyStateProps {
  icon?: React.ElementType;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <Card
      className={cn(
        "p-8 text-center border-dashed border-2 border-border bg-card/40 flex flex-col items-center justify-center min-h-[220px]",
        className
      )}
    >
      {Icon && (
        <div className="w-12 h-12 rounded-2xl bg-muted/70 text-muted-foreground flex items-center justify-center mb-3">
          <Icon className="w-6 h-6" />
        </div>
      )}
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="text-xs text-muted-foreground max-w-sm mx-auto mt-1 mb-4 leading-relaxed">
        {description}
      </p>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </Card>
  );
}
