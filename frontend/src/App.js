import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import CFDIModule from './pages/CFDIModule';
import BankModule from './pages/BankModule';
import BankStatementsModule from './pages/BankStatementsModule';
import PaymentsModule from './pages/PaymentsModule';
import Catalogs from './pages/Catalogs';
import Reports from './pages/Reports';
import AdminDashboard from './pages/AdminDashboard';
import AuditLogsPage from './pages/AuditLogsPage';
import AdvancedFeatures from './pages/AdvancedFeatures';
import FXRatesModule from './pages/FXRatesModule';
import CategoriesModule from './pages/CategoriesModule';
import CashflowProjections from './pages/CashflowProjections';
import DIOTModule from './pages/DIOTModule';
import TreasuryDecisions from './pages/TreasuryDecisions';
import FinancialMetrics from './pages/FinancialMetrics';
import BoardReport from './pages/BoardReport';
import Layout from './components/Layout';
import { Toaster } from './components/ui/sonner';
import api from './api/axios';
import './App.css';

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
      const response = await api.get('/companies');
      setCompanies(response.data);
      
      // If no company selected, select the user's company or first one
      if (!selectedCompany && response.data.length > 0) {
        const userCompany = response.data.find(c => c.id === user.company_id);
        const companyToSelect = userCompany || response.data[0];
        setSelectedCompany(companyToSelect);
        localStorage.setItem('selectedCompany', JSON.stringify(companyToSelect));
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

  const handleCompanyChange = (company) => {
    setSelectedCompany(company);
    localStorage.setItem('selectedCompany', JSON.stringify(company));
    // Reload the page to refresh data for new company
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
            <Route path="admin" element={<AdminDashboard />} />
            <Route path="audit-logs" element={<AuditLogsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </>
  );
}

export default App;
