import { useState, useEffect, useMemo } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Loader2, RefreshCw, FileDown, FileText, Filter, X } from 'lucide-react';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';

const ACTION_LABELS = {
  fx_corrected_to_dof: { label: 'Corrección TC al DOF', color: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  cfdi_create: { label: 'CFDI creado', color: 'bg-blue-100 text-blue-700 border-blue-300' },
  cfdi_update: { label: 'CFDI actualizado', color: 'bg-amber-100 text-amber-800 border-amber-300' },
  cfdi_delete: { label: 'CFDI eliminado', color: 'bg-red-100 text-red-700 border-red-300' },
  payment_create: { label: 'Pago creado', color: 'bg-blue-100 text-blue-700 border-blue-300' },
  payment_update: { label: 'Pago actualizado', color: 'bg-amber-100 text-amber-800 border-amber-300' },
};

const formatActionLabel = (accion) => ACTION_LABELS[accion]?.label || accion;
const actionColor = (accion) => ACTION_LABELS[accion]?.color || 'bg-slate-100 text-slate-700 border-slate-300';

const formatJSON = (obj) => {
  if (!obj) return '—';
  try {
    return Object.entries(obj)
      .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
      .join(' · ');
  } catch {
    return JSON.stringify(obj);
  }
};

export default function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [distinct, setDistinct] = useState({ entidades: [], acciones: [], usuarios: [] });
  
  // Filter state
  const [filters, setFilters] = useState({
    entidad: 'all',
    accion: 'all',
    user_id: 'all',
    fecha_desde: '',
    fecha_hasta: '',
  });
  
  const loadDistinct = async () => {
    try {
      const r = await api.get('/audit-logs/distinct');
      setDistinct(r.data);
    } catch {/* ignore */}
  };
  
  const loadLogs = async () => {
    setLoading(true);
    try {
      const params = { limit: 1000 };
      if (filters.entidad !== 'all') params.entidad = filters.entidad;
      if (filters.accion !== 'all') params.accion = filters.accion;
      if (filters.user_id !== 'all') params.user_id = filters.user_id;
      if (filters.fecha_desde) params.fecha_desde = filters.fecha_desde;
      if (filters.fecha_hasta) params.fecha_hasta = filters.fecha_hasta;
      
      const r = await api.get('/audit-logs', { params });
      setLogs(r.data || []);
    } catch (e) {
      toast.error('Error al cargar la bitácora');
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    loadDistinct();
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Re-fetch when filters change (debounced through user clicks; date inputs only re-query on blur)
  useEffect(() => {
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.entidad, filters.accion, filters.user_id, filters.fecha_desde, filters.fecha_hasta]);
  
  const clearFilters = () => setFilters({ entidad: 'all', accion: 'all', user_id: 'all', fecha_desde: '', fecha_hasta: '' });
  const hasActiveFilters = filters.entidad !== 'all' || filters.accion !== 'all' || filters.user_id !== 'all' || filters.fecha_desde || filters.fecha_hasta;
  
  const summary = useMemo(() => {
    const byAccion = {};
    logs.forEach(l => { byAccion[l.accion] = (byAccion[l.accion] || 0) + 1; });
    return { total: logs.length, byAccion };
  }, [logs]);
  
  const exportToExcel = () => {
    if (logs.length === 0) {
      toast.warning('No hay registros para exportar');
      return;
    }
    const rows = logs.map(l => ({
      'Fecha y Hora': format(new Date(l.timestamp), 'dd/MM/yyyy HH:mm:ss'),
      'Usuario': l.user_id,
      'Entidad': l.entidad,
      'ID Entidad': l.entity_id,
      'Acción': formatActionLabel(l.accion),
      'Acción (técnica)': l.accion,
      'Datos Anteriores': formatJSON(l.datos_anteriores),
      'Datos Nuevos': formatJSON(l.datos_nuevos),
    }));
    const ws = XLSX.utils.json_to_sheet(rows);
    ws['!cols'] = [{ wch: 18 }, { wch: 26 }, { wch: 14 }, { wch: 36 }, { wch: 22 }, { wch: 22 }, { wch: 50 }, { wch: 50 }];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Bitácora');
    XLSX.writeFile(wb, `Bitacora_${format(new Date(), 'yyyy-MM-dd_HHmm')}.xlsx`);
    toast.success(`Exportado: ${logs.length} registros`);
  };
  
  const exportToPDF = () => {
    if (logs.length === 0) {
      toast.warning('No hay registros para exportar');
      return;
    }
    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const pageWidth = pdf.internal.pageSize.getWidth();
    
    // Title
    pdf.setFillColor(252, 252, 250);
    pdf.rect(0, 0, pageWidth, 25, 'F');
    pdf.setFillColor(180, 142, 58);
    pdf.rect(0, 0, 3, 25, 'F');
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(14);
    pdf.setTextColor(15, 23, 42);
    pdf.text('Bitácora de Cambios — Auditoría', 12, 12);
    pdf.setFontSize(9);
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(100, 116, 139);
    pdf.text(`Generado: ${format(new Date(), "dd/MM/yyyy HH:mm")} · ${logs.length} registros`, 12, 19);
    
    const body = logs.map(l => [
      format(new Date(l.timestamp), 'dd/MM/yy HH:mm'),
      l.user_id || '—',
      l.entidad || '—',
      formatActionLabel(l.accion),
      (l.entity_id || '').slice(0, 12) + (l.entity_id?.length > 12 ? '…' : ''),
      formatJSON(l.datos_anteriores).slice(0, 90),
      formatJSON(l.datos_nuevos).slice(0, 90),
    ]);
    
    pdf.autoTable({
      startY: 30,
      head: [['Fecha', 'Usuario', 'Entidad', 'Acción', 'ID', 'Antes', 'Después']],
      body,
      styles: { fontSize: 7, cellPadding: 1.5 },
      headStyles: { fillColor: [180, 142, 58], textColor: [255, 255, 255], fontSize: 8 },
      alternateRowStyles: { fillColor: [248, 246, 240] },
      columnStyles: {
        0: { cellWidth: 22 },
        1: { cellWidth: 36 },
        2: { cellWidth: 18 },
        3: { cellWidth: 32 },
        4: { cellWidth: 22 },
        5: { cellWidth: 65 },
        6: { cellWidth: 65 },
      },
    });
    
    pdf.save(`Bitacora_${format(new Date(), 'yyyy-MM-dd_HHmm')}.pdf`);
    toast.success(`PDF generado: ${logs.length} registros`);
  };
  
  return (
    <div className="space-y-6 p-6" data-testid="audit-logs-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Bitácora de Cambios</h1>
          <p className="text-sm text-slate-500 mt-1">
            Registro inmutable de todas las modificaciones realizadas en el sistema. Útil para auditorías SAT y cumplimiento interno.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadLogs} disabled={loading} className="gap-2" data-testid="audit-refresh-btn">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Actualizar
          </Button>
          <Button variant="outline" onClick={exportToExcel} className="gap-2 border-emerald-300 text-emerald-700 hover:bg-emerald-50" data-testid="audit-export-excel-btn">
            <FileDown size={14} />
            Excel
          </Button>
          <Button variant="outline" onClick={exportToPDF} className="gap-2 border-red-300 text-red-700 hover:bg-red-50" data-testid="audit-export-pdf-btn">
            <FileText size={14} />
            PDF
          </Button>
        </div>
      </div>
      
      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Filter size={16} />
            Filtros
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="ml-auto h-7 gap-1 text-xs" data-testid="audit-clear-filters-btn">
                <X size={12} />
                Limpiar
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div>
              <Label className="text-xs">Entidad</Label>
              <Select value={filters.entidad} onValueChange={(v) => setFilters(f => ({ ...f, entidad: v }))}>
                <SelectTrigger data-testid="filter-entidad-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  {distinct.entidades.map(e => <SelectItem key={e} value={e}>{e}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Acción</Label>
              <Select value={filters.accion} onValueChange={(v) => setFilters(f => ({ ...f, accion: v }))}>
                <SelectTrigger data-testid="filter-accion-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  {distinct.acciones.map(a => <SelectItem key={a} value={a}>{formatActionLabel(a)}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Usuario</Label>
              <Select value={filters.user_id} onValueChange={(v) => setFilters(f => ({ ...f, user_id: v }))}>
                <SelectTrigger data-testid="filter-user-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {distinct.usuarios.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Desde</Label>
              <Input type="date" value={filters.fecha_desde} onChange={(e) => setFilters(f => ({ ...f, fecha_desde: e.target.value }))} data-testid="filter-fecha-desde" />
            </div>
            <div>
              <Label className="text-xs">Hasta</Label>
              <Input type="date" value={filters.fecha_hasta} onChange={(e) => setFilters(f => ({ ...f, fecha_hasta: e.target.value }))} data-testid="filter-fecha-hasta" />
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Resumen</CardTitle>
          <CardDescription>{summary.total} eventos en el rango filtrado</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.byAccion).map(([accion, count]) => (
              <Badge key={accion} variant="outline" className={`${actionColor(accion)} font-normal`}>
                {formatActionLabel(accion)}: <strong className="ml-1">{count}</strong>
              </Badge>
            ))}
            {Object.keys(summary.byAccion).length === 0 && <span className="text-sm text-slate-400">Sin eventos</span>}
          </div>
        </CardContent>
      </Card>
      
      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="w-[150px]">Fecha y Hora</TableHead>
                <TableHead className="w-[160px]">Usuario</TableHead>
                <TableHead className="w-[100px]">Entidad</TableHead>
                <TableHead className="w-[180px]">Acción</TableHead>
                <TableHead>Antes</TableHead>
                <TableHead>Después</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8"><Loader2 className="animate-spin inline" /></TableCell></TableRow>
              ) : logs.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Sin registros</TableCell></TableRow>
              ) : logs.map(l => (
                <TableRow key={l.id} data-testid={`audit-row-${l.id}`}>
                  <TableCell className="text-xs mono">{format(new Date(l.timestamp), 'dd MMM yyyy HH:mm:ss', { locale: es })}</TableCell>
                  <TableCell className="text-xs">{l.user_id}</TableCell>
                  <TableCell><Badge variant="outline" className="text-xs font-mono">{l.entidad}</Badge></TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`${actionColor(l.accion)} font-normal text-xs`}>
                      {formatActionLabel(l.accion)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-slate-600 max-w-md truncate" title={formatJSON(l.datos_anteriores)}>
                    {formatJSON(l.datos_anteriores)}
                  </TableCell>
                  <TableCell className="text-xs text-slate-700 max-w-md truncate" title={formatJSON(l.datos_nuevos)}>
                    {formatJSON(l.datos_nuevos)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
