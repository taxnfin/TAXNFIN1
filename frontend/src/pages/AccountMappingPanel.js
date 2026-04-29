import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import api from '../api/axios';
import {
  ArrowRight, Plus, Trash2, Sparkles, Check, RefreshCw,
  DollarSign, ShoppingCart, Briefcase, CreditCard, Building2,
  Receipt, Layers, AlertTriangle
} from 'lucide-react';

const categoryIcons = {
  ingresos: DollarSign,
  otros_ingresos: DollarSign,
  costo_ventas: ShoppingCart,
  gastos_venta: Receipt,
  gastos_administracion: Briefcase,
  gastos_generales: Layers,
  gastos_financieros: CreditCard,
  otros_gastos: AlertTriangle,
  impuestos: Building2,
  depreciacion: Layers,
  amortizacion: Layers,
};

const groupColors = {
  income: '#10B981',
  cost: '#EF4444',
  opex: '#F59E0B',
  financial: '#6366F1',
  tax: '#8B5CF6',
  other: '#6B7280',
  non_cash: '#94A3B8',
};

const AccountMappingPanel = () => {
  const [mappings, setMappings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [financialCategories, setFinancialCategories] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [mappingsRes, categoriesRes, finCatRes] = await Promise.all([
        api.get('/account-mappings'),
        api.get('/categories'),
        api.get('/account-mappings/categories'),
      ]);
      setMappings(mappingsRes.data);
      setCategories(categoriesRes.data);
      setFinancialCategories(finCatRes.data);
    } catch {}
  };

  const autoDetect = async () => {
    setLoading(true);
    try {
      const res = await api.post('/account-mappings/auto-detect');
      setSuggestions(res.data);
      if (res.data.length === 0) {
        toast.info('Todas las categorías ya están mapeadas');
      }
    } catch {
      toast.error('Error detectando mapeos');
    } finally {
      setLoading(false);
    }
  };

  const applySuggestion = async (suggestion) => {
    try {
      await api.post('/account-mappings', {
        source_type: suggestion.source_type,
        source_id: suggestion.source_id,
        source_value: suggestion.source_value,
        target_category: suggestion.suggested_target,
        integration: suggestion.integration,
      });
      toast.success(`Mapeado: ${suggestion.source_value} → ${suggestion.suggested_target}`);
      setSuggestions(prev => prev.filter(s => s.source_id !== suggestion.source_id));
      fetchAll();
    } catch {
      toast.error('Error aplicando mapeo');
    }
  };

  const applyAllSuggestions = async () => {
    for (const s of suggestions) {
      try {
        await api.post('/account-mappings', {
          source_type: s.source_type,
          source_id: s.source_id,
          source_value: s.source_value,
          target_category: s.suggested_target,
          integration: s.integration,
        });
      } catch {}
    }
    toast.success(`${suggestions.length} mapeos aplicados`);
    setSuggestions([]);
    fetchAll();
  };

  const updateMapping = async (mappingId, newTarget) => {
    try {
      await api.put(`/account-mappings/${mappingId}`, { target_category: newTarget });
      toast.success('Mapeo actualizado');
      fetchAll();
    } catch {
      toast.error('Error actualizando');
    }
  };

  const deleteMapping = async (mappingId) => {
    try {
      await api.delete(`/account-mappings/${mappingId}`);
      toast.success('Mapeo eliminado');
      fetchAll();
    } catch {
      toast.error('Error eliminando');
    }
  };

  const changeSuggestionTarget = (sourceId, newTarget) => {
    setSuggestions(prev => prev.map(s => 
      s.source_id === sourceId ? { ...s, suggested_target: newTarget } : s
    ));
  };

  const getFinCatLabel = (key) => financialCategories.find(c => c.key === key)?.label || key;
  const getFinCatGroup = (key) => financialCategories.find(c => c.key === key)?.group || 'other';

  return (
    <div className="space-y-6" data-testid="account-mapping-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-gray-800">Mapeo de Cuentas Contables</h3>
          <p className="text-sm text-gray-500">Define cómo se clasifican tus categorías en los estados financieros</p>
        </div>
        <Button onClick={autoDetect} disabled={loading} className="gap-2" data-testid="auto-detect-btn">
          <Sparkles className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Auto-detectar Mapeos
        </Button>
      </div>

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2 text-amber-800">
                <Sparkles className="w-4 h-4" /> {suggestions.length} Sugerencias de Mapeo
              </CardTitle>
              <Button size="sm" onClick={applyAllSuggestions} className="gap-1" data-testid="apply-all-suggestions">
                <Check className="w-3.5 h-3.5" /> Aplicar Todas
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {suggestions.map(s => {
              const Icon = categoryIcons[s.suggested_target] || Layers;
              const color = groupColors[getFinCatGroup(s.suggested_target)] || '#6B7280';
              return (
                <div key={s.source_id} className="flex items-center gap-3 p-2 bg-white rounded-lg border">
                  <span className="text-sm font-medium text-gray-800 flex-1">{s.source_value}</span>
                  <ArrowRight className="w-4 h-4 text-gray-400" />
                  <Select value={s.suggested_target} onValueChange={v => changeSuggestionTarget(s.source_id, v)}>
                    <SelectTrigger className="w-52 h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {financialCategories.map(fc => (
                        <SelectItem key={fc.key} value={fc.key}>{fc.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: color + '20', color }}>
                    {Math.round(s.confidence * 100)}%
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => applySuggestion(s)} className="h-7 px-2">
                    <Check className="w-3.5 h-3.5 text-green-600" />
                  </Button>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Current Mappings */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Mapeos Configurados ({mappings.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {mappings.length === 0 ? (
            <div className="py-8 text-center">
              <Layers className="w-10 h-10 mx-auto text-gray-300 mb-3" />
              <p className="text-sm text-gray-500">No hay mapeos configurados</p>
              <p className="text-xs text-gray-400 mt-1">Usa "Auto-detectar" para crear mapeos basados en tus categorías</p>
            </div>
          ) : (
            <div className="space-y-2">
              {mappings.map(m => {
                const Icon = categoryIcons[m.target_category] || Layers;
                const color = groupColors[getFinCatGroup(m.target_category)] || '#6B7280';
                return (
                  <div key={m.id} className="flex items-center gap-3 p-3 rounded-lg border hover:bg-gray-50" data-testid={`mapping-${m.id}`}>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-800">{m.source_value}</p>
                      <p className="text-[10px] text-gray-400">{m.integration} • {m.source_type}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-gray-400" />
                    <Select value={m.target_category} onValueChange={v => updateMapping(m.id, v)}>
                      <SelectTrigger className="w-52 h-8 text-xs">
                        <div className="flex items-center gap-2">
                          <Icon className="w-3.5 h-3.5" style={{ color }} />
                          <span>{getFinCatLabel(m.target_category)}</span>
                        </div>
                      </SelectTrigger>
                      <SelectContent>
                        {financialCategories.map(fc => (
                          <SelectItem key={fc.key} value={fc.key}>{fc.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button size="sm" variant="ghost" onClick={() => deleteMapping(m.id)} className="h-7 px-2 text-red-400 hover:text-red-600">
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      <Card>
        <CardContent className="p-4">
          <h4 className="text-xs font-bold text-gray-600 uppercase mb-3">Categorías Financieras</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {financialCategories.map(fc => {
              const Icon = categoryIcons[fc.key] || Layers;
              const color = groupColors[fc.group] || '#6B7280';
              return (
                <div key={fc.key} className="flex items-center gap-2 text-xs">
                  <Icon className="w-3.5 h-3.5" style={{ color }} />
                  <span className="text-gray-700">{fc.label}</span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AccountMappingPanel;
