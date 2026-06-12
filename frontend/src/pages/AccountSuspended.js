import { AlertCircle, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';

const AccountSuspended = () => {
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('selectedCompany');
    window.location.href = '/login';
  };

  return (
    <div className="min-h-screen bg-[#0F172A] flex items-center justify-center p-8">
      <div className="max-w-md w-full bg-white rounded-xl p-8 text-center shadow-2xl">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-9 h-9 text-red-500" />
        </div>
        <h1 className="text-2xl font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>
          Cuenta Suspendida
        </h1>
        <p className="text-[#64748B] mb-2 text-sm leading-relaxed">
          Tu empresa ha sido suspendida temporalmente por falta de pago.
        </p>
        <p className="text-[#64748B] mb-6 text-sm leading-relaxed">
          Contacta al equipo de TaxnFin para regularizar tu cuenta y recuperar el acceso.
        </p>
        <div className="space-y-3">
          <a href="mailto:soporte@taxnfin.com">
            <Button className="w-full bg-[#10B981] hover:bg-[#059669] gap-2">
              <Mail className="w-4 h-4" />
              soporte@taxnfin.com
            </Button>
          </a>
          <Button variant="outline" className="w-full" onClick={handleLogout}>
            Cerrar sesión
          </Button>
        </div>
        <p className="text-xs text-[#94A3B8] mt-6">TaxnFin Cashflow · cashflow.taxnfin.com</p>
      </div>
    </div>
  );
};

export default AccountSuspended;
