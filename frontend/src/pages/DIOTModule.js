import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Download, FileSpreadsheet, FileText, Filter, RefreshCw, Building2, DollarSign, Receipt } from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import * as XLSX from 'xlsx';

const DIOTModule = () => {
  const [diotData, setDiotData] = useState([]);
  const [summary, setSummary] = useState({ totalOperaciones: 0, totalIVA: 0, totalMonto: 0 });
  const [loading, setLoading] = useState(true);
  const [fechaDesde, setFechaDesde] = useState(format(new Date(new Date().getFullYear(), new Date().getMonth(), 1), 'yyyy-MM-dd'));
  const [fechaHasta, setFechaHasta] = useState(format(new Date(), 'yyyy-MM-dd'));

  useEffect(() => {
    loadDIOTData();
  }, []);

  const loadDIOTData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (fechaDesde) params.append('fecha_desde', fechaDesde);
      if (fechaHasta) params.append('fecha_hasta', fechaHasta);
      
      const response = await api.get(`/diot/preview?${params.toString()}`);
      setDiotData(response.data.records || []);
      setSummary(response.data.summary || { totalOperaciones: 0, totalIVA: 0, totalMonto: 0 });
    } catch (error) {
      console.error('Error loading DIOT data:', error);
      toast.error('Error cargando datos DIOT');
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = () => {
    loadDIOTData();
  };

  const exportToExcel = () => {
    if (diotData.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }

    try {
      const wb = XLSX.utils.book_new();
      
      // Prepare data for Excel
      const excelData = diotData.map(row => ({
        'Tipo Tercero': row.tipo_tercero_desc,
        'Tipo Operación': row.tipo_operacion_desc,
        'RFC': row.rfc,
        'Nombre/Razón Social': row.nombre,
        'País': row.pais,
        'Nacionalidad': row.nacionalidad,
        'Valor Actos Pagados': row.valor_actos_pagados,
        'Valor Actos 0%': row.valor_actos_0,
        'Valor Actos Exentos': row.valor_actos_exentos,
        'Valor Actos 16%': row.valor_actos_16,
        'IVA Retenido': row.iva_retenido,
        'IVA Acreditable': row.iva_acreditable,
        'Fecha Pago': row.fecha_pago,
        'UUID': row.uuid,
        'Categoría': row.categoria,
        'Subcategoría': row.subcategoria
      }));

      const ws = XLSX.utils.json_to_sheet(excelData);
      
      // Auto-width columns
      const colWidths = Object.keys(excelData[0] || {}).map(key => ({
        wch: Math.max(key.length, ...excelData.map(row => String(row[key] || '').length)) + 2
      }));
      ws['!cols'] = colWidths;

      XLSX.utils.book_append_sheet(wb, ws, 'DIOT');
      
      // Add summary sheet
      const summaryData = [
        { 'Concepto': 'Total Operaciones', 'Valor': summary.totalOperaciones },
        { 'Concepto': 'Total Monto', 'Valor': summary.totalMonto },
        { 'Concepto': 'Total IVA', 'Valor': summary.totalIVA },
        { 'Concepto': 'Período', 'Valor': `${fechaDesde} a ${fechaHasta}` }
      ];
      const wsSummary = XLSX.utils.json_to_sheet(summaryData);
      XLSX.utils.book_append_sheet(wb, wsSummary, 'Resumen');

      const filename = `DIOT_${fechaDesde}_${fechaHasta}.xlsx`;
      XLSX.writeFile(wb, filename);
      toast.success('DIOT exportado a Excel');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Error al exportar');
    }
  };

  const exportToTXT = () => {
    if (diotData.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }

    try {
      // Format SAT-compatible TXT (pipe-delimited)
      const lines = diotData.map(row => [
        row.tipo_tercero,
        row.tipo_operacion,
        row.rfc || '',
        '', // ID Fiscal (for foreigners)
        row.nombre || '',
        row.pais || 'MX',
        row.nacionalidad || '',
        Math.round(row.valor_actos_pagados || 0),
        Math.round(row.valor_actos_0 || 0),
        Math.round(row.valor_actos_exentos || 0),
        Math.round(row.valor_actos_16 || 0),
        Math.round(row.iva_retenido || 0),
        Math.round(row.iva_acreditable || 0)
      ].join('|'));

      const content = lines.join('\n');
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `DIOT_${fechaDesde}_${fechaHasta}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      toast.success('DIOT exportado a TXT (formato SAT)');
    } catch (error) {
      console.error('Export TXT error:', error);
      toast.error('Error al exportar TXT');
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount || 0);
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="diot-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>
            Reporte DIOT
          </h1>
          <p className="text-[#64748B]">Declaración Informativa de Operaciones con Terceros (Solo Egresos)</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={exportToExcel} className="gap-2 bg-green-600 hover:bg-green-700" data-testid="export-diot-excel">
            <FileSpreadsheet size={16} />
            Exportar Excel
          </Button>
          <Button onClick={exportToTXT} variant="outline" className="gap-2" data-testid="export-diot-txt">
            <FileText size={16} />
            Exportar TXT
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Operaciones</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.totalOperaciones}</div>
            <p className="text-xs text-muted-foreground">Facturas de egreso en período</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Monto Total</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(summary.totalMonto)}</div>
            <p className="text-xs text-muted-foreground">Valor de actos pagados</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">IVA Acreditable</CardTitle>
            <Building2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(summary.totalIVA)}</div>
            <p className="text-xs text-muted-foreground">IVA trasladado del período</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">IVA Retenido</CardTitle>
            <Building2 className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{formatCurrency(summary.totalIVARetenido || 0)}</div>
            <p className="text-xs text-muted-foreground">Retenciones de IVA</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter size={18} />
            Filtros
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-end">
            <div className="space-y-2">
              <Label>Fecha Desde</Label>
              <Input
                type="date"
                value={fechaDesde}
                onChange={(e) => setFechaDesde(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Fecha Hasta</Label>
              <Input
                type="date"
                value={fechaHasta}
                onChange={(e) => setFechaHasta(e.target.value)}
              />
            </div>
            <Button onClick={handleFilter} className="gap-2">
              <RefreshCw size={16} />
              Filtrar
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Data Table */}
      <Card>
        <CardHeader>
          <CardTitle>Detalle de Operaciones</CardTitle>
          <CardDescription>
            Facturas de egreso (gastos) en el período seleccionado - basado en fecha de emisión
          </CardDescription>
        </CardHeader>
        <CardContent>
          {diotData.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Receipt size={48} className="mx-auto mb-4 opacity-50" />
              <p>No hay facturas de egreso en el período seleccionado</p>
              <p className="text-sm mt-2">Sube tus CFDIs de egreso (gastos) en el módulo de CFDIs</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tipo</TableHead>
                    <TableHead>RFC</TableHead>
                    <TableHead>Nombre/Razón Social</TableHead>
                    <TableHead className="text-right">Subtotal</TableHead>
                    <TableHead className="text-right">IVA Acred.</TableHead>
                    <TableHead className="text-right">IVA Ret.</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>F. Emisión</TableHead>
                    <TableHead>F. Pago</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Categoría</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {diotData.map((row, idx) => (
                    <TableRow key={idx} className={row.pagado ? 'bg-green-50/50' : ''}>
                      <TableCell>
                        <span className="text-xs px-2 py-1 rounded bg-gray-100">{row.tipo_tercero}</span>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{row.rfc}</TableCell>
                      <TableCell className="max-w-[200px] truncate" title={row.nombre}>{row.nombre}</TableCell>
                      <TableCell className="text-right font-mono">{formatCurrency(row.subtotal || row.valor_actos_16)}</TableCell>
                      <TableCell className="text-right font-mono text-green-600">{formatCurrency(row.iva_acreditable)}</TableCell>
                      <TableCell className="text-right font-mono text-red-600">{row.iva_retenido > 0 ? formatCurrency(row.iva_retenido) : '-'}</TableCell>
                      <TableCell className="text-right font-mono font-semibold">{formatCurrency(row.valor_actos_pagados)}</TableCell>
                      <TableCell className="text-sm">{row.fecha_emision || '-'}</TableCell>
                      <TableCell className="text-sm">{row.fecha_pago || '-'}</TableCell>
                      <TableCell>
                        {row.pagado ? (
                          <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-700">Pagado</span>
                        ) : (
                          <span className="text-xs px-2 py-1 rounded bg-yellow-100 text-yellow-700">Pendiente</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-gray-600">{row.categoria || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* SAT Format Info */}
      <Card>
        <CardHeader>
          <CardTitle>Información del Formato</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-gray-600">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="font-semibold mb-2">Tipos de Tercero:</h4>
              <ul className="list-disc list-inside space-y-1">
                <li><span className="font-mono">04</span> - Proveedor Nacional</li>
                <li><span className="font-mono">05</span> - Proveedor Extranjero</li>
                <li><span className="font-mono">15</span> - Proveedor Global</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-2">Tipos de Operación:</h4>
              <ul className="list-disc list-inside space-y-1">
                <li><span className="font-mono">03</span> - Prestación de servicios profesionales</li>
                <li><span className="font-mono">06</span> - Arrendamiento de inmuebles</li>
                <li><span className="font-mono">85</span> - Otros</li>
              </ul>
            </div>
          </div>
          <p className="mt-4">
            <strong>Nota:</strong> El archivo TXT exportado está en formato compatible con el portal del SAT (campos separados por "|").
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default DIOTModule;
