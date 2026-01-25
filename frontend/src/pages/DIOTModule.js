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
        'Moneda Original': row.moneda || 'MXN',
        'TC Pago': row.tipo_cambio || 1,
        'Subtotal Original': row.subtotal,
        'Subtotal MXN': row.subtotal_mxn || row.subtotal,
        'IVA Acreditable MXN': row.iva_acreditable,
        'IVA Retenido MXN': row.iva_retenido,
        'ISR Retenido MXN': row.isr_retenido || 0,
        'Total Original': row.valor_actos_pagados,
        'Total MXN (DIOT)': row.valor_actos_pagados_mxn || row.valor_actos_pagados,
        'Fecha Pago': row.fecha_pago,
        'Estado': row.pagado ? 'Pagado' : 'Pendiente',
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
          <p className="text-[#64748B]">Declaración Informativa de Operaciones con Terceros (Solo Egresos con IVA)</p>
          <p className="text-xs text-orange-600 mt-1">
            ⚠️ Excluye automáticamente: Nómina, sueldos, asimilados y CFDIs sin IVA acreditable
          </p>
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
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
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
            <CardTitle className="text-sm font-medium">Monto Original</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(summary.totalMonto)}</div>
            <p className="text-xs text-muted-foreground">En moneda original (USD/MXN)</p>
          </CardContent>
        </Card>
        <Card className="bg-blue-50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Monto Total MXN</CardTitle>
            <DollarSign className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-700">{formatCurrency(summary.totalMontoMXN || summary.totalMonto)}</div>
            <p className="text-xs text-muted-foreground">Convertido a pesos (DIOT)</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">IVA Acreditable</CardTitle>
            <Building2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(summary.totalIVA)}</div>
            <p className="text-xs text-muted-foreground">IVA trasladado en MXN</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">IVA Retenido</CardTitle>
            <Building2 className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{formatCurrency(summary.totalIVARetenido || 0)}</div>
            <p className="text-xs text-muted-foreground">Retenciones de IVA en MXN</p>
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
              <p>No hay facturas de egreso <strong>pagadas</strong> en el período seleccionado</p>
              <p className="text-sm mt-2">Las facturas aparecerán aquí cuando se concilien con movimientos bancarios</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tipo</TableHead>
                    <TableHead>RFC</TableHead>
                    <TableHead>Nombre/Razón Social</TableHead>
                    <TableHead className="text-center">Moneda</TableHead>
                    <TableHead className="text-right">TC Pago</TableHead>
                    <TableHead className="text-right">Subtotal Orig.</TableHead>
                    <TableHead className="text-right">Subtotal MXN</TableHead>
                    <TableHead className="text-right">IVA MXN</TableHead>
                    <TableHead className="text-right">Total MXN</TableHead>
                    <TableHead>F. Pago</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {diotData.map((row, idx) => (
                    <TableRow key={idx} className="bg-green-50/30">
                      <TableCell>
                        <span className="text-xs px-2 py-1 rounded bg-gray-100">{row.tipo_tercero}</span>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{row.rfc}</TableCell>
                      <TableCell className="max-w-[180px] truncate" title={row.nombre}>{row.nombre}</TableCell>
                      <TableCell className="text-center">
                        <span className={`text-xs px-2 py-1 rounded font-mono ${row.moneda === 'USD' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100'}`}>
                          {row.moneda || 'MXN'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {row.moneda !== 'MXN' ? (
                          <span className="text-blue-600">{row.tipo_cambio?.toFixed(4) || '-'}</span>
                        ) : (
                          <span className="text-gray-400">1.0000</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {row.moneda !== 'MXN' ? (
                          <span className="text-gray-600">
                            ${(row.subtotal || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                            <span className="text-xs ml-1 text-gray-400">{row.moneda}</span>
                          </span>
                        ) : (
                          formatCurrency(row.subtotal || row.valor_actos_16)
                        )}
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">
                        {formatCurrency(row.subtotal_mxn || row.valor_actos_16)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-green-600">
                        {formatCurrency(row.iva_acreditable)}
                      </TableCell>
                      <TableCell className="text-right font-mono font-semibold">
                        {formatCurrency(row.valor_actos_pagados_mxn || row.valor_actos_pagados)}
                      </TableCell>
                      <TableCell className="text-sm font-medium text-green-700">{row.fecha_pago || '-'}</TableCell>
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
            <strong>Nota:</strong> El archivo TXT exportado está en formato compatible con el portal del SAT (campos separados por &quot;|&quot;).
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default DIOTModule;
