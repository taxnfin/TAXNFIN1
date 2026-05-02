import { useState } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Loader2, ShieldCheck, AlertTriangle, ShieldAlert, RefreshCw } from 'lucide-react';

const STATUS_CONFIG = {
  ok: {
    label: 'OK',
    Icon: ShieldCheck,
    color: 'bg-emerald-100 text-emerald-700 border-emerald-300',
    description: 'Tipo de cambio dentro del ±1% del DOF',
  },
  warning: {
    label: 'Revisar',
    Icon: AlertTriangle,
    color: 'bg-amber-100 text-amber-800 border-amber-300',
    description: 'Desviación 1%-5% del DOF',
  },
  critical: {
    label: 'Crítico',
    Icon: ShieldAlert,
    color: 'bg-red-100 text-red-700 border-red-300',
    description: 'Desviación >5% — posible error de captura, puede afectar deducibilidad SAT',
  },
  unknown: {
    label: 'Sin DOF',
    Icon: AlertTriangle,
    color: 'bg-slate-100 text-slate-600 border-slate-300',
    description: 'Banxico no publicó FIX para esa fecha (fin de semana o feriado)',
  },
};

export const FXValidationPanel = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');

  const runAudit = async () => {
    setLoading(true);
    try {
      const res = await api.get('/cfdi/audit/fx-validation', { params: { limit: 1000 } });
      const d = res.data;
      if (!d.success && d.error === 'banxico_token_missing') {
        toast.error(d.message, { duration: 12000 });
        setData(null);
        return;
      }
      setData(d);
      const total = d.summary.ok + d.summary.warning + d.summary.critical + d.summary.unknown;
      toast.success(`Auditoría completada: ${total} CFDIs analizados`);
    } catch (e) {
      toast.error('Error al ejecutar la auditoría');
    } finally {
      setLoading(false);
    }
  };

  const filteredResults = (data?.results || []).filter(r => filterStatus === 'all' || r.status === filterStatus);

  return (
    <Card data-testid="fx-validation-panel" className="border-slate-200">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck size={20} className="text-emerald-600" />
              Auditoría de Tipos de Cambio
            </CardTitle>
            <CardDescription className="mt-1">
              Compara el TC de cada CFDI contra el FIX oficial publicado por Banxico (DOF) en el día de emisión.
              Una desviación &gt;5% suele indicar error de captura y puede comprometer la deducibilidad ante el SAT.
            </CardDescription>
          </div>
          <Button
            onClick={runAudit}
            disabled={loading}
            className="bg-emerald-600 hover:bg-emerald-700 gap-2"
            data-testid="run-fx-audit-btn"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {loading ? 'Auditando...' : 'Ejecutar auditoría'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!data && !loading && (
          <div className="text-sm text-slate-500 py-8 text-center">
            Click en <span className="font-semibold">"Ejecutar auditoría"</span> para comparar todos los TC de tus CFDIs en moneda extranjera contra el DOF de Banxico.
          </div>
        )}
        
        {data && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              {Object.entries(STATUS_CONFIG).map(([status, cfg]) => (
                <button
                  key={status}
                  data-testid={`fx-summary-${status}`}
                  type="button"
                  className={`text-left p-3 rounded-lg border-2 transition-all ${
                    filterStatus === status ? 'ring-2 ring-offset-1 ring-slate-400 ' : ''
                  }${cfg.color}`}
                  onClick={() => setFilterStatus(filterStatus === status ? 'all' : status)}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <cfg.Icon size={16} />
                    <span className="text-xs font-semibold uppercase tracking-wide">{cfg.label}</span>
                  </div>
                  <div className="text-2xl font-bold mono">{data.summary[status] || 0}</div>
                </button>
              ))}
            </div>
            
            {filterStatus !== 'all' && (
              <div className="text-xs text-slate-500 mb-3">
                Filtrando: <span className="font-semibold">{STATUS_CONFIG[filterStatus]?.label}</span>{' '}
                <button className="underline ml-2" onClick={() => setFilterStatus('all')}>limpiar</button>
              </div>
            )}
            
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="w-[110px]">Fecha</TableHead>
                    <TableHead>Folio / Cliente</TableHead>
                    <TableHead className="w-[80px]">Moneda</TableHead>
                    <TableHead className="text-right w-[110px]">TC CFDI</TableHead>
                    <TableHead className="text-right w-[110px]">TC DOF</TableHead>
                    <TableHead className="text-right w-[100px]">Desv.</TableHead>
                    <TableHead className="w-[100px]">Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredResults.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-slate-500 py-6">
                        Sin resultados para este filtro.
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredResults.slice(0, 200).map((r) => {
                      const cfg = STATUS_CONFIG[r.status] || STATUS_CONFIG.unknown;
                      return (
                        <TableRow key={r.cfdi_id} data-testid={`fx-row-${r.cfdi_id}`}>
                          <TableCell className="mono text-xs">{r.fecha_emision}</TableCell>
                          <TableCell className="text-sm">
                            <div className="font-medium">{r.folio || '—'}</div>
                            <div className="text-xs text-slate-500">{r.receptor || r.emisor}</div>
                          </TableCell>
                          <TableCell className="mono text-xs">{r.moneda}</TableCell>
                          <TableCell className="mono text-right">{r.actual_rate?.toFixed(4) || '—'}</TableCell>
                          <TableCell className="mono text-right">{r.official_rate?.toFixed(4) || '—'}</TableCell>
                          <TableCell className={`mono text-right font-semibold ${
                            r.deviation_pct == null ? 'text-slate-400'
                              : Math.abs(r.deviation_pct) > 5 ? 'text-red-600'
                              : Math.abs(r.deviation_pct) > 1 ? 'text-amber-600'
                              : 'text-emerald-600'
                          }`}>
                            {r.deviation_pct != null ? `${r.deviation_pct > 0 ? '+' : ''}${r.deviation_pct.toFixed(2)}%` : '—'}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className={`${cfg.color} gap-1 font-normal`}>
                              <cfg.Icon size={12} />
                              {cfg.label}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
            
            {filteredResults.length > 200 && (
              <p className="text-xs text-slate-500 mt-3 text-center">
                Mostrando 200 de {filteredResults.length} resultados.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default FXValidationPanel;
