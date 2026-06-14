const PageHeader = ({ title, subtitle, breadcrumb, actions }) => {
  return (
    <div className="bg-[#0D1B2A] border-b border-slate-700 px-6 py-4 -mx-6 -mt-6 mb-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-[#00C9A7] font-semibold uppercase tracking-widest mb-1">
            {breadcrumb || 'TaxnFin · CFO Intelligence'}
          </p>
          <h1 className="text-xl font-bold text-white" style={{ fontFamily: 'Manrope' }}>{title}</h1>
          {subtitle && <p className="text-sm text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
