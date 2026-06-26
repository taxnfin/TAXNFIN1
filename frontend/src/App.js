import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Login from './pages/Login';
import ResetPassword from './pages/ResetPassword';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import CFDIModule from './pages/CFDIModule';
import BankModule from './pages/BankModule';
import BankStatementsModule from './pages/BankStatementsModule';
import PaymentsModule from './pages/PaymentsModule';
import Catalogs from './pages/Catalogs';
import Reports from './pages/Reports';
import AdminPanel from './pages/AdminPanel';
import AuditLogsPage from './pages/AuditLogsPage';
import AdvancedFeatures from './pages/AdvancedFeatures';
import FXRatesModule from './pages/FXRatesModule';
import CategoriesModule from './pages/CategoriesModule';
import CashflowProjections from './pages/CashflowProjections';
import DIOTModule from './pages/DIOTModule';
import TreasuryDecisions from './pages/TreasuryDecisions';
import FinancialMetrics from './pages/FinancialMetrics';
import BoardReport from './pages/BoardReport';
import Integrations from './pages/Integrations';
import ContalinkFinancialImport from './components/ContalinkFinancialImport';
import Financiamiento from './pages/Financiamiento';
import ConsejoEstrategico from './pages/ConsejoEstrategico';
import Usuarios from './pages/Usuarios';
import AccountSuspended from './pages/AccountSuspended';
import AuditPortal from './pages/AuditPortal';
import AuditEngagement from './pages/AuditEngagement';
import AuditPublic from './pages/AuditPublic';
import Layout from './components/Layout';
import { Toaster } from './components/ui/sonner';
import api from './api/axios';
import './App.css';

// Protege rutas solo para admin — doble candado: rol + email
const PLATFORM_ADMIN_EMAIL = 'hola@taxnfin.com';
const AdminRoute = ({ user, children }) => {
  if (!user || user.role !== 'admin' || user.email !== PLATFORM_ADMIN_EMAIL) {
    return <Navigate to="/" replace />;
  }
  return children;
};

// Bloquea el acceso de admin a rutas financieras — redirige a /admin
const NonAdminRoute = ({ user }) => {
  if (user?.role === 'admin' && user?.email === PLATFORM_ADMIN_EMAIL) {
    return <Navigate to="/admin" replace />;
  }
  return <Outlet />;
};

function App() {
  const [user, setUser] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    const storedCompany = localStorage.getItem('selectedCompany');
    
    if (token && storedUser) {
      setUser(JSON.parse(storedUser));
      if (storedCompany) {
        setSelectedCompany(JSON.parse(storedCompany));
      }
    }
    setLoading(false);
  }, []);

  // Fetch companies when user logs in
  useEffect(() => {
    if (user) {
      fetchCompanies();
    }
  }, [user]);

  const fetchCompanies = async () => {
    try {
      const [companiesRes, intRes] = await Promise.all([
        api.get('/companies'),
        api.get('/integrations/connected').catch(() => ({ data: [] })),
      ]);
      setCompanies(companiesRes.data);

      const connections = Array.isArray(intRes.data) ? intRes.data : [];
      const alegraViaIntegrations = connections.some(i => i.integration_type === 'alegra');

      if (!selectedCompany && companiesRes.data.length > 0) {
        const userCompany = companiesRes.data.find(c => c.id === user.company_id);
        const base = userCompany || companiesRes.data[0];
        const alegraConnected = base.alegra_connected === true || alegraViaIntegrations;
        // Inferir ERP: viene del backend, o lo deducimos del flag alegra_connected
        const erp = base.erp || (alegraConnected ? 'alegra' : 'ninguno');
        const enriched = { ...base, alegra_connected: alegraConnected, erp };
        setSelectedCompany(enriched);
        localStorage.setItem('selectedCompany', JSON.stringify(enriched));
      } else if (selectedCompany) {
        const currentBase = companiesRes.data.find(c => c.id === selectedCompany.id) || selectedCompany;
        const alegraConnected = currentBase.alegra_connected === true || alegraViaIntegrations;
        const erp = currentBase.erp || (alegraConnected ? 'alegra' : selectedCompany.erp || 'ninguno');
        const enriched = { ...currentBase, alegra_connected: alegraConnected, erp };
        setSelectedCompany(enriched);
        localStorage.setItem('selectedCompany', JSON.stringify(enriched));
      }
    } catch (error) {
      console.error('Error fetching companies:', error);
    }
  };

  const handleLogin = (userData, token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('selectedCompany');
    setUser(null);
    setSelectedCompany(null);
    setCompanies([]);
  };

  const handleCompanyChange = async (company) => {
    // Re-fetch integrations for the new company before storing, so alegra_connected is accurate
    try {
      const intRes = await api.get('/integrations/connected').catch(() => ({ data: [] }));
      const connections = Array.isArray(intRes.data) ? intRes.data : [];
      const alegraConnected = company.alegra_connected === true || connections.some(i => i.integration_type === 'alegra');
      const enriched = { ...company, alegra_connected: alegraConnected };
      setSelectedCompany(enriched);
      localStorage.setItem('selectedCompany', JSON.stringify(enriched));
    } catch {
      setSelectedCompany(company);
      localStorage.setItem('selectedCompany', JSON.stringify(company));
    }
    window.location.reload();
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Cargando...</div>;
  }

  return (
    <>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" /> : <Login onLogin={handleLogin} />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/account-suspended" element={<AccountSuspended />} />
          <Route path="/audit/public/:linkPublico" element={<AuditPublic />} />
          <Route
            path="/"
            element={
              user ? (
                <Layout 
                  user={user} 
                  onLogout={handleLogout}
                  companies={companies}
                  selectedCompany={selectedCompany}
                  onCompanyChange={handleCompanyChange}
                />
              ) : (
                <Navigate to="/login" />
              )
            }
          >
            {/* Admin-only route */}
            <Route path="admin" element={<AdminRoute user={user}><AdminPanel /></AdminRoute>} />
            {/* Financial routes — redirect to /admin if user is platform admin */}
            <Route element={<NonAdminRoute user={user} />}>
              <Route index element={<Dashboard />} />
              <Route path="transactions" element={<Transactions />} />
              <Route path="cfdi" element={<CFDIModule />} />
              <Route path="bank" element={<BankModule />} />
              <Route path="bank-statements" element={<BankStatementsModule />} />
              <Route path="payments" element={<PaymentsModule />} />
              <Route path="fx-rates" element={<FXRatesModule />} />
              <Route path="categories" element={<CategoriesModule />} />
              <Route path="catalogs" element={<Catalogs />} />
              <Route path="reports" element={<Reports />} />
              <Route path="board-report" element={<BoardReport />} />
              <Route path="projections" element={<CashflowProjections />} />
              <Route path="treasury" element={<TreasuryDecisions />} />
              <Route path="financial-metrics" element={<FinancialMetrics />} />
              <Route path="diot" element={<DIOTModule />} />
              <Route path="advanced" element={<AdvancedFeatures />} />
              <Route path="audit-logs" element={<AuditLogsPage />} />
              <Route path="integrations" element={<Integrations />} />
              <Route path="contalink-financial" element={<ContalinkFinancialImport />} />
              <Route path="financiamiento" element={<Financiamiento />} />
              <Route path="consejo-estrategico" element={<ConsejoEstrategico />} />
              <Route path="usuarios" element={<Usuarios />} />
              <Route path="audit" element={<AuditPortal />} />
              <Route path="audit/:engagementId" element={<AuditEngagement />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </>
  );
}

export default App;
