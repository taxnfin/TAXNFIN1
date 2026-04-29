import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import api from '../api/axios';
import {
  Building2, Users, FileText, Link2, Plus, Trash2, RefreshCw,
  CheckCircle2, XCircle, Clock, Zap, ArrowRight, Shield, Globe
} from 'lucide-react';
import AccountMappingPanel from './AccountMappingPanel';

const statusConfig = {
  connected: { icon: CheckCircle2, color: '#10B981', label: 'Conectado' },
  error: { icon: XCircle, color: '#EF4444', label: 'Error' },
  pending: { icon: Clock, color: '#F59E0B', label: 'Pendiente' },
  coming_soon: { icon: Clock, color: '#94A3B8', label: 'Próximamente' },
};

const AdminDashboard = () => {
  const [companies, setCompanies] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [availableIntegrations, setAvailableIntegrations] = useState([]);
  const [connectDialog, setConnectDialog] = useState(false);
  const [selectedType, setSelectedType] = useState(null);
  const [credentials, setCredentials] = useState({});
  const [label, setLabel] = useState('');
  const [syncing, setSyncing] = useState(null);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [companiesRes, connectedRes, availableRes] = await Promise.all([
        api.get('/integrations/admin/all-companies'),
        api.get('/integrations/connected'),
        api.get('/integrations/available-list'),
      ]);
      setCompanies(companiesRes.data);
      setIntegrations(connectedRes.data);
      setAvailableIntegrations(availableRes.data);
    } catch {}
  };

  const openConnect = (type) => {
    setSelectedType(type);
    setCredentials({});
    setLabel('');
    setConnectDialog(true);
  };

  const handleConnect = async () => {
    try {
      await api.post('/integrations/connect', {
        integration_type: selectedType.key,
        credentials,
        label: label || undefined,
      });
      toast.success(`${selectedType.name} conectado exitosamente`);
      setConnectDialog(false);
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error conectando');
    }
  };

  const handleSync = async (integrationId) => {
    setSyncing(integrationId);
    try {
      const res = await api.post(`/integrations/${integrationId}/sync`);
      if (res.data.status === 'success') {
        toast.success(res.data.message);
      } else {
        toast.error(res.data.message);
      }
      fetchAll();
    } catch (err) {
      toast.error('Error en sincronización');
    } finally {
      setSyncing(null);
    }
  };

  const handleDisconnect = async (integrationId) => {
    try {
      await api.delete(`/integrations/${integrationId}`);
      toast.success('Integración desconectada');
      fetchAll();
    } catch {
      toast.error('Error desconectando');
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto" data-testid="admin-dashboard">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Panel de Administración</h1>
          <p className="text-sm text-gray-500">Gestión de empresas, usuarios e integraciones</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{companies.length}</p>
              <p className="text-xs text-gray-500">Empresas</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{companies.reduce((s, c) => s + c.users_count, 0)}</p>
              <p className="text-xs text-gray-500">Usuarios</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
              <Link2 className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{integrations.length}</p>
              <p className="text-xs text-gray-500">Integraciones Activas</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
              <FileText className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{companies.reduce((s, c) => s + c.cfdis_count, 0)}</p>
              <p className="text-xs text-gray-500">CFDIs Totales</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Companies Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Building2 className="w-5 h-5" /> Empresas Registradas
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="companies-table">
              <thead>
                <tr className="border-b text-left text-xs font-medium text-gray-500 uppercase">
                  <th className="pb-2 pr-4">Empresa</th>
                  <th className="pb-2 pr-4">RFC</th>
                  <th className="pb-2 pr-4">Usuarios</th>
                  <th className="pb-2 pr-4">CFDIs</th>
                  <th className="pb-2 pr-4">Último Período</th>
                  <th className="pb-2">Integraciones</th>
                </tr>
              </thead>
              <tbody>
                {companies.map(c => (
                  <tr key={c.id} className="border-b last:border-b-0 hover:bg-gray-50">
                    <td className="py-3 pr-4 font-medium text-gray-900">{c.nombre}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-gray-600">{c.rfc}</td>
                    <td className="py-3 pr-4">{c.users_count}</td>
                    <td className="py-3 pr-4">{c.cfdis_count.toLocaleString()}</td>
                    <td className="py-3 pr-4">{c.latest_period || '—'}</td>
                    <td className="py-3">
                      <div className="flex gap-1">
                        {c.integrations.map(i => {
                          const cfg = statusConfig[i.connection_status] || statusConfig.pending;
                          const Icon = cfg.icon;
                          return (
                            <span key={i.id} className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: cfg.color + '15', color: cfg.color }}>
                              <Icon className="w-3 h-3" /> {i.name}
                            </span>
                          );
                        })}
                        {c.integrations.length === 0 && <span className="text-xs text-gray-400">Ninguna</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Integrations Section */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="w-5 h-5" /> Integraciones Contables
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connected Integrations */}
          {integrations.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-gray-700">Conectadas</h4>
              {integrations.map(i => {
                const cfg = statusConfig[i.connection_status] || statusConfig.pending;
                const Icon = cfg.icon;
                return (
                  <div key={i.id} className="flex items-center gap-3 p-3 rounded-lg border" data-testid={`integration-${i.id}`}>
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: cfg.color + '15' }}>
                      <Icon className="w-5 h-5" style={{ color: cfg.color }} />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-800">{i.label || i.name}</p>
                      <p className="text-xs text-gray-500">
                        {cfg.label} {i.last_sync ? `• Última sync: ${new Date(i.last_sync).toLocaleDateString('es-MX')}` : '• Sin sincronizar'}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSync(i.id)}
                      disabled={syncing === i.id}
                      className="gap-1"
                      data-testid={`sync-${i.id}`}
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${syncing === i.id ? 'animate-spin' : ''}`} /> Sincronizar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDisconnect(i.id)}
                      className="text-red-500 hover:text-red-700"
                      data-testid={`disconnect-${i.id}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Available to Connect */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700">Disponibles para Conectar</h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {availableIntegrations.filter(a => !integrations.find(i => i.integration_type === a.key)).map(a => {
                const isComingSoon = a.status === 'coming_soon';
                return (
                  <div
                    key={a.key}
                    className={`p-4 rounded-lg border ${isComingSoon ? 'opacity-50' : 'hover:shadow-md cursor-pointer'} transition-all`}
                    data-testid={`available-${a.key}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h5 className="text-sm font-semibold text-gray-800">{a.name}</h5>
                      {isComingSoon && (
                        <span className="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Próximamente</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mb-3">{a.description}</p>
                    <Button
                      size="sm"
                      className="w-full gap-1"
                      disabled={isComingSoon}
                      onClick={() => openConnect(a)}
                      data-testid={`connect-btn-${a.key}`}
                    >
                      <Plus className="w-3.5 h-3.5" /> Conectar
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Account Mapping Section */}
      <AccountMappingPanel />

      {/* Connect Dialog */}
      <Dialog open={connectDialog} onOpenChange={setConnectDialog}>
        <DialogContent className="sm:max-w-md" data-testid="connect-dialog">
          <DialogHeader>
            <DialogTitle>Conectar {selectedType?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-medium">Etiqueta (opcional)</Label>
              <Input
                value={label}
                onChange={e => setLabel(e.target.value)}
                placeholder={`Ej: ${selectedType?.name} Producción`}
                data-testid="input-label"
              />
            </div>
            {selectedType?.fields?.map(field => (
              <div key={field}>
                <Label className="text-xs font-medium capitalize">{field.replace('_', ' ')}</Label>
                <Input
                  type={field.includes('password') || field.includes('secret') || field.includes('key') ? 'password' : 'text'}
                  value={credentials[field] || ''}
                  onChange={e => setCredentials(prev => ({ ...prev, [field]: e.target.value }))}
                  placeholder={`Ingresa tu ${field.replace('_', ' ')}`}
                  data-testid={`input-${field}`}
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConnectDialog(false)}>Cancelar</Button>
            <Button onClick={handleConnect} data-testid="confirm-connect-btn">Conectar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminDashboard;
