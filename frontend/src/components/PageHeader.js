export function PageHeader({ title, subtitle, actions, testid }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-6" data-testid={testid}>
      <div>
        <h1 className="font-head font-extrabold text-2xl lg:text-3xl tracking-tight">{title}</h1>
        {subtitle && <p className="text-muted-foreground text-sm mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
