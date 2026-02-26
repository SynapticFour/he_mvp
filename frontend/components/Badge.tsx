// SPDX-License-Identifier: Apache-2.0
export function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "success" | "warning" | "pending" | "default";
}) {
  const classes = {
    success: "bg-success/15 text-success",
    warning: "bg-warning/15 text-amber-700",
    pending: "bg-amber-100 text-amber-800",
    default: "bg-slate-100 text-slate-700",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes[variant]}`}
    >
      {children}
    </span>
  );
}
