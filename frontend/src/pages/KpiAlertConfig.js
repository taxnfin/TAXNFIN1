import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import api from '../api/axios';
import {
  Plus, Trash2, Bell, BellOff, AlertTriangle, AlertCircle, Info,
  ArrowDown, ArrowUp, Pencil
} from 'lucide-react';

const metricOptions = [
  { key: 'gross_margin', section: 'margins', label: 'Margen Bruto', unit: '%' },
  { key: 'ebitda_margin', section: 'margins', label: 'Margen EBITDA', unit: '%' },
  { key: 'operating_margin', section: 'margins', label: 'Margen Operativo', unit: '%' },
  { key: 'net_margin', section: 'margins', label: 'Margen Neto', unit: '%' },
  { key: 'roic', section: 'returns', label: 'ROIC', unit: '%' },
  { key: 'roe', section: 'returns', label: 'ROE', unit: '%' },
  { key: 'roa', section: 'returns', label: 'ROA', unit: '%' },
  { key: 'asset_turnover', section: 'efficiency', label: 'Rotación de Activos', unit: 'x' },
  { key: 'dso', section: 'efficiency', label: 'DSO (Días de Cobro)', unit: ' días' },
  { key: 'dpo', section: 'efficiency', label: 'DPO (Días de Pago)', unit: ' días' },
  { key: 'cash_conversion_cycle', section: 'efficiency', label: 'Ciclo Conversión Efectivo', unit: ' días' },
  { key: 'current_ratio', section: 'liquidity', label: 'Razón Circulante', unit: 'x' },
  { key: 'quick_ratio', section: 'liquidity', label: 'Prueba Ácida', unit: 'x' },
  { key: 'cash_ratio', section: 'liquidity', label: 'Razón de Efectivo', unit: 'x' },
  { key: 'debt_to_equity', section: 'solvency', label: 'Deuda / Capital', unit: 'x' },
  { key: 'debt_to_assets', section: 'solvency', label: 'Deuda / Activos', unit: '%' },
  { key: 'interest_coverage', section: 'solvency', label: 'Cobertura de Intereses', unit: 'x' },
  { key: 'equity_ratio', section: 'solvency', label: 'Razón de Capital', unit: '%' },
];

const levelConfig = {
  info: { icon: Info, color: '#3B82F6', bg: '#EFF6FF', label: 'Informativa' },
  warning: { icon: AlertTriangle, color: '#F59E0B', bg: '#FFFBEB', label: 'Alerta' },
  critical: { icon: AlertCircle, color: '#EF4444', bg: '#FEF2F2', label: 'Crítica' },
};

const KpiAlertConfig = () => {
  const [rules, setRules] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form, setForm] = useState({
    metric_key: '',
    condition: 'below',
    threshold: '',
    level: 'warning',
  });

  const fetchRules = async () => {
    try {
      const res = await api.get('/kpi-alert-rules');
      setRules(res.data);
    } catch {}
  };

  useEffect(() => { fetchRules(); }, []);

  const openCreate = () => {
    setEditingRule(null);
    setForm({ metric_key: '', condition: 'below', threshold: '', level: 'warning' });
    setDialogOpen(true);
  };

  const openEdit = (rule) => {
    setEditingRule(rule);
    setForm({
      metric_key: rule.metric_key,
      condition: rule.condition,
      threshold: String(rule.threshold),
      level: rule.level,
    });
    setDialogOpen(true);
  };

  const saveRule = async () => {
    const metric = metricOptions.find(m => m.key === form.metric_key);
    if (!metric) { toast.error('Selecciona una métrica'); return; }
    if (!form.threshold || isNaN(Number(form.threshold))) { toast.error('Ingresa un umbral válido'); return; }

    const payload = {
      metric_key: metric.key,
      metric_section: metric.section,
      metric_label: metric.label,
      condition: form.condition,
      threshold: Number(form.threshold),
      level: form.level,
    };

    try {
      if (editingRule) {
        await api.put(`/kpi-alert-rules/${editingRule.id}`, payload);
        toast.success('Regla actualizada');
      } else {
        await api.post('/kpi-alert-rules', payload);
        toast.success('Regla creada');
      }
      setDialogOpen(false);
      fetchRules();
    } catch {
      toast.error('Error guardando regla');
    }
  };

  const toggleRule = async (ruleId) => {
    try {
      const res = await api.put(`/kpi-alert-rules/${ruleId}/toggle`);
      toast.success(res.data.is_active ? 'Regla activada' : 'Regla desactivada');
      fetchRules();
    } catch {
      toast.error('Error actualizando regla');
    }
  };

  const deleteRule = async (ruleId) => {
    try {
      await api.delete(`/kpi-alert-rules/${ruleId}`);
      toast.success('Regla eliminada');
      fetchRules();
    } catch {
      toast.error('Error eliminando regla');
    }
  };

  return (
    <div className="space-y-4" data-testid="kpi-alert-config">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-gray-800">Alertas por KPI</h3>
          <p className="text-sm text-gray-500">Configura umbrales para recibir notificaciones automáticas</p>
        </div>
        <Button onClick={openCreate} className="gap-2" data-testid="create-alert-rule-btn">
          <Plus className="w-4 h-4" /> Nueva Regla
        </Button>
      </div>

      {rules.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center">
            <Bell className="w-10 h-10 mx-auto text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">No hay reglas de alerta configuradas</p>
            <p className="text-xs text-gray-400 mt-1">Crea una regla para recibir notificaciones cuando un KPI cruce un umbral</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {rules.map(rule => {
            const cfg = levelConfig[rule.level] || levelConfig.warning;
            const LevelIcon = cfg.icon;
            const metric = metricOptions.find(m => m.key === rule.metric_key);
            return (
              <Card key={rule.id} className={`transition-all ${!rule.is_active ? 'opacity-50' : ''}`} data-testid={`alert-rule-${rule.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: cfg.bg }}>
                        <LevelIcon className="w-4 h-4" style={{ color: cfg.color }} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-800">{rule.metric_label}</p>
                        <p className="text-xs text-gray-500">{cfg.label}</p>
                      </div>
                    </div>
                    <Switch
                      checked={rule.is_active}
                      onCheckedChange={() => toggleRule(rule.id)}
                      data-testid={`toggle-rule-${rule.id}`}
                    />
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-sm">
                    {rule.condition === 'below' ? (
                      <ArrowDown className="w-4 h-4 text-red-500" />
                    ) : (
                      <ArrowUp className="w-4 h-4 text-orange-500" />
                    )}
                    <span className="text-gray-700">
                      {rule.condition === 'below' ? 'Por debajo de' : 'Por encima de'}{' '}
                      <strong>{rule.threshold}{metric?.unit || ''}</strong>
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      onClick={() => openEdit(rule)}
                      className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                      data-testid={`edit-rule-${rule.id}`}
                    >
                      <Pencil className="w-3 h-3" /> Editar
                    </button>
                    <button
                      onClick={() => deleteRule(rule.id)}
                      className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1"
                      data-testid={`delete-rule-${rule.id}`}
                    >
                      <Trash2 className="w-3 h-3" /> Eliminar
                    </button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md" data-testid="alert-rule-dialog">
          <DialogHeader>
            <DialogTitle>{editingRule ? 'Editar Regla' : 'Nueva Regla de Alerta'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-medium">Métrica</Label>
              <Select value={form.metric_key} onValueChange={v => setForm(f => ({ ...f, metric_key: v }))}>
                <SelectTrigger data-testid="select-metric">
                  <SelectValue placeholder="Seleccionar métrica" />
                </SelectTrigger>
                <SelectContent>
                  {metricOptions.map(m => (
                    <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium">Condición</Label>
              <Select value={form.condition} onValueChange={v => setForm(f => ({ ...f, condition: v }))}>
                <SelectTrigger data-testid="select-condition">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="below">Por debajo de</SelectItem>
                  <SelectItem value="above">Por encima de</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium">Umbral</Label>
              <Input
                type="number"
                step="0.1"
                value={form.threshold}
                onChange={e => setForm(f => ({ ...f, threshold: e.target.value }))}
                placeholder="Ej: 30.0"
                data-testid="input-threshold"
              />
            </div>
            <div>
              <Label className="text-xs font-medium">Nivel de Alerta</Label>
              <Select value={form.level} onValueChange={v => setForm(f => ({ ...f, level: v }))}>
                <SelectTrigger data-testid="select-level">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="info">Informativa</SelectItem>
                  <SelectItem value="warning">Alerta</SelectItem>
                  <SelectItem value="critical">Crítica</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={saveRule} data-testid="save-alert-rule-btn">
              {editingRule ? 'Guardar Cambios' : 'Crear Regla'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default KpiAlertConfig;
