import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  TrendingUp,
  CreditCard,
  ArrowRightLeft,
  Building2,
  Receipt,
  DollarSign,
  FileText,
  Link2,
  BarChart3,
  Calculator,
  Presentation,
  Lightbulb,
  ScrollText,
  Sparkles,
  Settings,
  FolderOpen,
  Tags,
  FileSpreadsheet,
  LogOut,
  ChevronDown,
  ChevronRight,
  Building,
  Sun,
  Moon,
} from 'lucide-react';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import NotificationBell from './NotificationBell';

// ─── Theme tokens ────────────────────────────────────────────────────────────
const DARK = {
  bg:        '#0A1628',
  sidebar:   '#0D1B2A',
  sidebar2:  '#152235',
  border:    'rgba(255,255,255,0.07)',
  border2:   'rgba(255,255,255,0.13)',
  text1:     '#F0F4F8',
  text2:     '#8FA3BC',
  text3:     '#4E6479',
  active:    'rgba(0,201,167,0.10)',
  activeBar: '#00C9A7',
  accent:    '#00C9A7',
  accentTxt: '#00C9A7',
  hover:     'rgba(255,255,255,0.05)',
  main:      '#0A1628',
};

const LIGHT = {
  bg:        '#F5F7FA',
  sidebar:   '#FFFFFF',
  sidebar2:  '#F0F4F8',
  border:    'rgba(0,0,0,0.07)',
  border2:   'rgba(0,0,0,0.13)',
  text1:     '#1A2332',
  text2:     '#4E6479',
  text3:     '#8FA3BC',
  active:    'rgba(0,158,131,0.09)',
  activeBar: '#009E83',
  accent:    '#009E83',
  accentTxt: '#007A65',
  hover:     'rgba(0,0,0,0.04)',
  main:      '#F5F7FA',
};

// ─── Nav structure ────────────────────────────────────────────────────────────
const buildNav = (isAdmin) => [
  {
    section: 'Principal',
    items: [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
      {
        name: 'Cash Flow',
        icon: TrendingUp,
        sub: [
          { name: 'Proyecciones 13/18S', href: '/projections' },
          { name: 'Vista mensual',       href: '/projections?view=monthly' },
          { name: 'Por cliente/proveedor', href: '/projections?view=entity' },
        ],
      },
      { name: 'Cobranza y Pagos', href: '/payments', icon: CreditCard },
      { name: 'Aging CxC / CxP',  href: '/transactions', icon: ArrowRightLeft },
    ],
  },
  {
    section: 'Operaciones',
    items: [
      {
        name: 'Cuentas y Bancos',
        icon: Building2,
        sub: [
          { name: 'Cuentas bancarias',       href: '/bank' },
          { name: 'Conciliaciones',           href: '/bank-statements' },
          { name: 'Importar estado de cuenta', href: '/bank-statements?import=true' },
          { name: 'Tipos de cambio',          href: '/fx-rates' },
        ],
      },
      {
        name: 'SAT y Fiscal',
        icon: FileText,
        badge: 'MX',
        badgeStyle: 'mx',
        sub: [
          { name: 'CFDI emitidos',                     href: '/cfdi?tab=emitidos' },
          { name: 'CFDI recibidos',                    href: '/cfdi?tab=recibidos' },
          { name: 'Integraciones (Alegra · Contalink)', href: '/integrations' },
          { name: 'Estados Financieros',               href: '/contalink-financial' },
        ],
      },
    ],
  },
  {
    section: 'Inteligencia',
    items: [
      {
        name: 'Reportes',
        icon: BarChart3,
        sub: [
          { name: 'Reporte Board',        href: '/board-report' },
          { name: 'Métricas financieras', href: '/financial-metrics' },
          { name: 'Decisiones / Alertas', href: '/treasury' },
        ],
      },
      {
        name: 'IA Ejecutiva',
        href: '/advanced',
        icon: Sparkles,
        badge: 'PRO',
        badgeStyle: 'pro',
      },
    ],
  },
  ...(isAdmin
    ? [{
        section: '',
        items: [{ name: 'Admin', href: '/admin', icon: Settings }],
      }]
    : []),
];

// ─── Badge styles ─────────────────────────────────────────────────────────────
const BADGE = {
  mx:  { bg: 'rgba(96,165,250,0.12)',  color: '#60A5FA' },
  pro: { bg: 'rgba(167,139,250,0.12)', color: '#A78BFA' },
  v2:  { bg: 'rgba(255,179,71,0.12)',  color: '#FFB347' },
};

// ─── Component ────────────────────────────────────────────────────────────────
const Layout = ({ user, onLogout, companies, selectedCompany, onCompanyChange }) => {
  const location = useLocation();
  const storedUser = JSON.parse(localStorage.getItem('user') || '{}');
  const isAdmin = storedUser?.role === 'admin';

  // Theme
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('taxnfin-theme');
    return saved ? saved === 'dark' : true;
  });
  const t = dark ? DARK : LIGHT;

  useEffect(() => {
    localStorage.setItem('taxnfin-theme', dark ? 'dark' : 'light');
  }, [dark]);

  // Open sections (collapsible groups)
  const nav = buildNav(isAdmin);

  const getDefaultOpen = () => {
    const open = {};
    nav.forEach(({ items }) => {
      items.forEach((item) => {
        if (item.sub) {
          const anyActive = item.sub.some(
            (s) => location.pathname === s.href || location.pathname + location.search === s.href
          );
          if (anyActive) open[item.name] = true;
        }
      });
    });
    return open;
  };

  const [openGroups, setOpenGroups] = useState(getDefaultOpen);

  const toggleGroup = (name) =>
    setOpenGroups((prev) => ({ ...prev, [name]: !prev[name] }));

  const isActive = (href) =>
    href && (location.pathname === href || location.pathname + location.search === href);

  const isGroupActive = (item) =>
    item.href
      ? isActive(item.href)
      : item.sub?.some((s) => isActive(s.href));

  // ── Styles (inline, theme-aware) ──────────────────────────────────────────
  const S = {
    shell: {
      display: 'flex', height: '100vh',
      background: t.main, fontFamily: "'DM Sans', -apple-system, sans-serif",
    },
    sidebar: {
      width: 240, minWidth: 240,
      background: t.sidebar,
      borderRight: `1px solid ${t.border}`,
      display: 'flex', flexDirection: 'column',
      transition: 'background 0.25s, border-color 0.25s',
    },
    header: { padding: '16px 16px 14px', borderBottom: `1px solid ${t.border}` },
    logoRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
    logoMark: {
      width: 28, height: 28, borderRadius: 7, flexShrink: 0,
      background: 'linear-gradient(135deg,#00C9A7,#008B72)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'monospace', fontSize: 11, fontWeight: 600, color: '#fff',
    },
    logoName: { fontSize: 14, fontWeight: 700, color: t.text1, letterSpacing: -0.3, marginLeft: 8, flex: 1 },
    logoSub:  { fontSize: 9, color: t.accent, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', marginLeft: 8 },
    nav: { flex: 1, padding: '10px 8px 6px', overflowY: 'auto' },
    sectionLabel: {
      fontSize: 9, fontWeight: 700, color: t.text3,
      letterSpacing: '0.1em', textTransform: 'uppercase',
      padding: '8px 8px 3px',
    },
    navItem: (active) => ({
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '7px 9px', borderRadius: 8, cursor: 'pointer',
      transition: 'background 0.12s, color 0.12s',
      color: active ? t.accentTxt : t.text2,
      background: active ? t.active : 'transparent',
      position: 'relative', marginBottom: 1,
      textDecoration: 'none',
    }),
    activeBar: {
      position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
      width: 3, height: 16, background: t.activeBar,
      borderRadius: '0 2px 2px 0',
    },
    navLabel: (active) => ({
      fontSize: 12.5, flex: 1, lineHeight: 1,
      fontWeight: active ? 500 : 400, color: 'inherit',
    }),
    subItem: (active) => ({
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 9px 5px 33px', fontSize: 11.5,
      color: active ? t.accentTxt : t.text3,
      borderRadius: 6, cursor: 'pointer', marginBottom: 1,
      transition: 'color 0.12s, background 0.12s',
      background: active ? t.active : 'transparent',
      textDecoration: 'none',
    }),
    footer: { padding: '8px 8px 12px', borderTop: `1px solid ${t.border}` },
    footItem: {
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 9px', fontSize: 11.5, color: t.text3,
      borderRadius: 7, cursor: 'pointer',
      transition: 'color 0.12s, background 0.12s',
      textDecoration: 'none',
    },
    themeRow: {
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 9px', borderRadius: 7, cursor: 'pointer',
      fontSize: 11.5, color: t.text3, marginBottom: 2,
      transition: 'background 0.12s',
    },
    main: { flex: 1, overflowY: 'auto', background: t.main, transition: 'background 0.25s' },
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={S.shell} data-testid="main-layout">

      {/* ── SIDEBAR ── */}
      <aside style={S.sidebar} data-testid="sidebar">

        {/* Header */}
        <div style={S.header}>
          <div style={S.logoRow}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={S.logoMark}>T₦</div>
              <div>
                <div style={S.logoName}>TaxnFin</div>
                <div style={S.logoSub}>Cashflow</div>
              </div>
            </div>
            <NotificationBell />
          </div>

          {/* Company selector */}
          <div style={{ fontSize: 9, fontWeight: 700, color: t.text3, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
            Empresa activa
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                data-testid="company-selector"
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 7,
                  background: t.sidebar2, border: `1px solid ${t.border}`,
                  borderRadius: 8, padding: '6px 9px', cursor: 'pointer',
                  color: t.text1, fontSize: 12, fontWeight: 500,
                  transition: 'border-color 0.15s',
                }}
              >
                <Building size={14} color={t.accent} style={{ flexShrink: 0 }} />
                <span style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {selectedCompany?.nombre || 'Seleccionar empresa'}
                </span>
                <ChevronDown size={13} color={t.text3} style={{ flexShrink: 0 }} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="start">
              {companies.length === 0 ? (
                <DropdownMenuItem disabled>No hay empresas disponibles</DropdownMenuItem>
              ) : (
                companies.map((company) => (
                  <DropdownMenuItem
                    key={company.id}
                    onClick={() => onCompanyChange(company)}
                    className={cn('cursor-pointer', selectedCompany?.id === company.id && 'bg-[#F1F5F9]')}
                    data-testid={`company-option-${company.id}`}
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">{company.nombre}</span>
                      <span className="text-xs text-[#64748B]">RFC: {company.rfc}</span>
                    </div>
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Nav */}
        <nav style={S.nav}>
          {nav.map(({ section, items }) => (
            <div key={section} style={{ marginBottom: 4 }}>
              {section && <div style={S.sectionLabel}>{section}</div>}

              {items.map((item) => {
                const Icon = item.icon;
                const active = isGroupActive(item);
                const isOpen = !!openGroups[item.name];

                // Simple link (no sub)
                if (item.href && !item.sub) {
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                      style={S.navItem(active)}
                      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = t.hover; }}
                      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}
                    >
                      {active && <div style={S.activeBar} />}
                      <Icon size={15} style={{ flexShrink: 0 }} />
                      <span style={S.navLabel(active)}>{item.name}</span>
                      {item.badge && (
                        <span style={{ fontSize: 9, fontWeight: 700, borderRadius: 3, padding: '1px 5px', ...BADGE[item.badgeStyle] }}>
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                }

                // Collapsible group
                return (
                  <div key={item.name}>
                    <div
                      style={S.navItem(active)}
                      onClick={() => toggleGroup(item.name)}
                      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = t.hover; }}
                      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = active ? t.active : 'transparent'; }}
                    >
                      {active && <div style={S.activeBar} />}
                      <Icon size={15} style={{ flexShrink: 0 }} />
                      <span style={S.navLabel(active)}>{item.name}</span>
                      {item.badge && (
                        <span style={{ fontSize: 9, fontWeight: 700, borderRadius: 3, padding: '1px 5px', ...BADGE[item.badgeStyle] }}>
                          {item.badge}
                        </span>
                      )}
                      {isOpen
                        ? <ChevronDown size={12} color={t.text3} style={{ flexShrink: 0 }} />
                        : <ChevronRight size={12} color={t.text3} style={{ flexShrink: 0 }} />}
                    </div>

                    {/* Sub items */}
                    <div style={{
                      overflow: 'hidden',
                      maxHeight: isOpen ? 300 : 0,
                      transition: 'max-height 0.22s ease',
                    }}>
                      {item.sub.map((s) => {
                        const subActive = isActive(s.href);
                        return (
                          <Link
                            key={s.name}
                            to={s.href}
                            style={S.subItem(subActive)}
                            onMouseEnter={(e) => { if (!subActive) e.currentTarget.style.background = t.hover; }}
                            onMouseLeave={(e) => { if (!subActive) e.currentTarget.style.background = subActive ? t.active : 'transparent'; }}
                          >
                            <span style={{ width: 4, height: 4, borderRadius: '50%', background: subActive ? t.accentTxt : t.text3, flexShrink: 0 }} />
                            <span style={{ flex: 1, color: 'inherit' }}>{s.name}</span>
                            {s.tag && (
                              <span style={{ fontSize: 8.5, fontWeight: 600, borderRadius: 3, padding: '1px 4px', ...BADGE.v2 }}>
                                {s.tag}
                              </span>
                            )}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div style={S.footer}>
          {/* User info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 9px', marginBottom: 2 }}>
            <div style={{
              width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg,#00C9A7,#008B72)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 700, color: '#fff',
            }}>
              {user?.nombre?.[0]?.toUpperCase() || 'U'}
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500, color: t.text1 }}>{user?.nombre}</div>
              <div style={{ fontSize: 10, color: t.text3 }}>{user?.role} · MXN</div>
            </div>
          </div>

          {/* Theme toggle */}
          <div style={S.themeRow} onClick={() => setDark((d) => !d)}
            onMouseEnter={(e) => e.currentTarget.style.background = t.hover}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            {dark
              ? <Sun size={14} color={t.text3} />
              : <Moon size={14} color={t.text3} />}
            <span style={{ flex: 1, color: t.text3 }}>{dark ? 'Modo diurno' : 'Modo nocturno'}</span>
            {/* Track */}
            <div style={{
              width: 28, height: 16, borderRadius: 8, flexShrink: 0, position: 'relative',
              background: dark ? t.border2 : t.accent,
              transition: 'background 0.25s',
            }}>
              <div style={{
                position: 'absolute', top: 2, left: 2,
                width: 12, height: 12, borderRadius: '50%', background: '#fff',
                transition: 'transform 0.22s',
                transform: dark ? 'translateX(0)' : 'translateX(12px)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
              }} />
            </div>
          </div>

          {/* Config links */}
          <Link to="/categories" style={S.footItem}
            onMouseEnter={(e) => e.currentTarget.style.background = t.hover}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <Tags size={13} color={t.text3} />
            <span>Categorías &amp; Catálogos</span>
          </Link>

          {isAdmin && (
            <Link to="/admin" style={S.footItem}
              onMouseEnter={(e) => e.currentTarget.style.background = t.hover}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <Settings size={13} color={t.text3} />
              <span>Admin</span>
            </Link>
          )}

          {isAdmin && (
            <Link to="/audit-logs" style={S.footItem}
              onMouseEnter={(e) => e.currentTarget.style.background = t.hover}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <ScrollText size={13} color={t.text3} />
              <span>Bitácora</span>
            </Link>
          )}

          {/* Logout */}
          <div
            style={{ ...S.footItem, color: '#EF4444', marginTop: 2 }}
            onClick={onLogout}
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(239,68,68,0.08)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <LogOut size={13} />
            <span>Cerrar sesión</span>
          </div>
        </div>
      </aside>

      {/* ── MAIN ── */}
      <main style={S.main}>
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
