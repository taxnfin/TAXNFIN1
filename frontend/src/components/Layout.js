import { Outlet, Link, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { cn } from '@/lib/utils';
import { 
  LayoutDashboard, 
  ArrowRightLeft, 
  FileText, 
  Building2, 
  FolderOpen, 
  BarChart3, 
  Settings,
  LogOut,
  Sparkles,
  ChevronDown,
  Building,
  DollarSign,
  CreditCard,
  Tags,
  TrendingUp,
  FileSpreadsheet
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

const Layout = ({ user, onLogout, companies, selectedCompany, onCompanyChange }) => {
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Proyecciones', href: '/projections', icon: TrendingUp, highlight: true },
    { name: 'Aging CxC/CxP', href: '/transactions', icon: ArrowRightLeft },
    { name: 'CFDI / SAT', href: '/cfdi', icon: FileText },
    { name: 'Bancario', href: '/bank', icon: Building2 },
    { name: 'Cobranza y Pagos', href: '/payments', icon: CreditCard },
    { name: 'Tipos de Cambio', href: '/fx-rates', icon: DollarSign },
    { name: 'Categorías', href: '/categories', icon: Tags },
    { name: 'Catálogos', href: '/catalogs', icon: FolderOpen },
    { name: 'Reportes', href: '/reports', icon: BarChart3 },
    { name: 'IA & Avanzado', href: '/advanced', icon: Sparkles },
    { name: 'Admin', href: '/admin', icon: Settings },
  ];

  return (
    <div className="flex h-screen bg-[#F8FAFC]" data-testid="main-layout">
      <aside className="w-64 bg-white border-r border-[#E2E8F0] flex flex-col" data-testid="sidebar">
        <div className="p-6 border-b border-[#E2E8F0]">
          <h1 className="text-xl font-bold text-[#0F172A] tracking-tight" style={{fontFamily: 'Manrope'}}>TaxnFin Cashflow</h1>
          <p className="text-xs text-[#64748B] mt-1">{user?.nombre}</p>
          <p className="text-xs text-[#94A3B8] mono">{user?.role}</p>
        </div>

        {/* Company Selector */}
        <div className="p-4 border-b border-[#E2E8F0]">
          <label className="text-xs font-medium text-[#64748B] uppercase tracking-wider mb-2 block">
            Empresa Activa
          </label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="outline" 
                className="w-full justify-between text-left font-normal"
                data-testid="company-selector"
              >
                <div className="flex items-center gap-2 truncate">
                  <Building size={16} className="text-[#0EA5E9] shrink-0" />
                  <span className="truncate">
                    {selectedCompany?.nombre || 'Seleccionar empresa'}
                  </span>
                </div>
                <ChevronDown size={16} className="text-[#94A3B8] shrink-0" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="start">
              {companies.length === 0 ? (
                <DropdownMenuItem disabled>
                  No hay empresas disponibles
                </DropdownMenuItem>
              ) : (
                companies.map((company) => (
                  <DropdownMenuItem
                    key={company.id}
                    onClick={() => onCompanyChange(company)}
                    className={cn(
                      "cursor-pointer",
                      selectedCompany?.id === company.id && "bg-[#F1F5F9]"
                    )}
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
        
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                to={item.href}
                data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-sm transition-colors duration-150',
                  isActive
                    ? 'bg-[#0F172A] text-white'
                    : 'text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F172A]'
                )}
              >
                <Icon size={18} />
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-[#E2E8F0]">
          <Button
            data-testid="logout-button"
            onClick={onLogout}
            variant="outline"
            className="w-full justify-start gap-3 text-[#EF4444] border-[#EF4444] hover:bg-[#FEF2F2]"
          >
            <LogOut size={18} />
            Cerrar Sesión
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
