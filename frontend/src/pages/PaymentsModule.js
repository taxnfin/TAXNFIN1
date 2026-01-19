import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Plus, Check, CreditCard, TrendingUp, TrendingDown, CheckCircle2, FileText, User, Building2, AlertCircle } from 'lucide-react';
import { format, addDays } from 'date-fns';
import { Checkbox } from '@/components/ui/checkbox';

const PAYMENT_METHODS = [
  { value: 'transferencia', label: 'Transferencia' },
  { value: 'spei', label: 'SPEI' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'tarjeta', label: 'Tarjeta' },
  { value: 'domiciliacion', label: 'Domiciliación' },
];

const PAYMENT_STATUS = {
  pendiente: { label: 'Pendiente', color: 'bg-yellow-100 text-yellow-800' },
  completado: { label: 'Completado', color: 'bg-green-100 text-green-800' },
  cancelado: { label: 'Cancelado', color: 'bg-red-100 text-red-800' },
  vencido: { label: 'Vencido', color: 'bg-orange-100 text-orange-800' },
};

const PaymentsModule = () => {
  const [payments, setPayments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [filterTipo, setFilterTipo] = useState('all');
  const [filterEstatus, setFilterEstatus] = useState('all');
  const [filterFechaDesde, setFilterFechaDesde] = useState('');
  const [filterFechaHasta, setFilterFechaHasta] = useState('');
  
  // New states for clients/vendors and invoices
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [pendingCfdis, setPendingCfdis] = useState([]);
  const [selectedParty, setSelectedParty] = useState('');
  const [selectedCfdi, setSelectedCfdi] = useState(null);
  const [useCustomAmount, setUseCustomAmount] = useState(false);
  
  const [formData, setFormData] = useState({
    tipo: 'pago',
    concepto: '',
    monto: '',
    moneda: 'MXN',
    metodo_pago: 'transferencia',
    fecha_vencimiento: format(addDays(new Date(), 7), "yyyy-MM-dd'T'HH:mm"),
    beneficiario: '',
    referencia: '',
    domiciliacion_activa: false,
    cfdi_id: null,
    customer_id: null,
    vendor_id: null
  });

  useEffect(() => {
    loadData();
    loadPartiesData();
  }, [filterTipo, filterEstatus, filterFechaDesde, filterFechaHasta]);

  const loadData = async () => {
    try {
      let url = '/payments?limit=100';
      if (filterTipo !== 'all') url += `&tipo=${filterTipo}`;
      if (filterEstatus !== 'all') url += `&estatus=${filterEstatus}`;
      if (filterFechaDesde) url += `&fecha_desde=${filterFechaDesde}`;
      if (filterFechaHasta) url += `&fecha_hasta=${filterFechaHasta}`;
      
      const [paymentsRes, summaryRes] = await Promise.all([
        api.get(url),
        api.get('/payments/summary')
      ]);
      setPayments(paymentsRes.data);
      setSummary(summaryRes.data);
    } catch (error) {
      toast.error('Error cargando pagos');
    } finally {
      setLoading(false);
    }
  };

  const loadPartiesData = async () => {
    try {
      const [customersRes, vendorsRes] = await Promise.all([
        api.get('/customers'),
        api.get('/vendors')
      ]);
      setCustomers(customersRes.data);
      setVendors(vendorsRes.data);
    } catch (error) {
      console.error('Error loading parties:', error);
    }
  };

  // Load pending CFDIs for selected party
  const loadPendingCfdis = async (partyId, tipo) => {
    try {
      // Get CFDIs that match the party (customer for cobro, vendor for pago)
      const tipoCfdi = tipo === 'cobro' ? 'ingreso' : 'egreso';
      const res = await api.get(`/cfdi?tipo=${tipoCfdi}&limit=200`);
      
      // Filter CFDIs that belong to this party and have pending balance
      const partyField = tipo === 'cobro' ? 'customer_id' : 'vendor_id';
      const rfcField = tipo === 'cobro' ? 'receptor_rfc' : 'emisor_rfc';
      
      // Get party info to match by RFC
      const parties = tipo === 'cobro' ? customers : vendors;
      const party = parties.find(p => p.id === partyId);
      
      const filtered = res.data.filter(cfdi => {
        // Match by party_id or RFC
        const matchesParty = cfdi[partyField] === partyId || 
                            (party && cfdi[rfcField] === party.rfc);
        
        // Calculate pending balance
        const amountField = tipo === 'cobro' ? 'monto_cobrado' : 'monto_pagado';
        const pendingAmount = cfdi.total - (cfdi[amountField] || 0);
        
        return matchesParty && pendingAmount > 0 && cfdi.estado_cancelacion !== 'cancelado';
      }).map(cfdi => ({
        ...cfdi,
        saldo_pendiente: cfdi.total - (tipo === 'cobro' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0))
      }));
      
      setPendingCfdis(filtered);
    } catch (error) {
      console.error('Error loading pending CFDIs:', error);
      setPendingCfdis([]);
    }
  };

  // Handle party selection
  const handlePartyChange = (partyId) => {
    setSelectedParty(partyId);
    setSelectedCfdi(null);
    setFormData(prev => ({
      ...prev,
      [formData.tipo === 'cobro' ? 'customer_id' : 'vendor_id']: partyId,
      cfdi_id: null,
      monto: ''
    }));
    
    // Find party name for beneficiario
    const parties = formData.tipo === 'cobro' ? customers : vendors;
    const party = parties.find(p => p.id === partyId);
    if (party) {
      setFormData(prev => ({ ...prev, beneficiario: party.nombre }));
    }
    
    // Load pending CFDIs for this party
    if (partyId) {
      loadPendingCfdis(partyId, formData.tipo);
    } else {
      setPendingCfdis([]);
    }
  };

  // Handle CFDI selection
  const handleCfdiSelect = (cfdi) => {
    setSelectedCfdi(cfdi);
    setFormData(prev => ({
      ...prev,
      cfdi_id: cfdi.id,
      monto: cfdi.saldo_pendiente.toFixed(2),
      concepto: `Pago de factura ${cfdi.uuid?.substring(0, 8)}... - ${cfdi.emisor_nombre || cfdi.receptor_nombre}`,
      referencia: cfdi.uuid,
      moneda: cfdi.moneda || 'MXN'
    }));
    setUseCustomAmount(false);
  };

  // Handle type change
  const handleTipoChange = (tipo) => {
    setFormData(prev => ({
      ...prev,
      tipo,
      customer_id: null,
      vendor_id: null,
      cfdi_id: null,
      monto: '',
      beneficiario: ''
    }));
    setSelectedParty('');
    setSelectedCfdi(null);
    setPendingCfdis([]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/payments', {
        ...formData,
        monto: parseFloat(formData.monto)
      });
      toast.success('Pago registrado');
      setDialogOpen(false);
      loadData();
      resetForm();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error registrando pago');
    }
  };

  const resetForm = () => {
    setFormData({
      tipo: 'pago',
      concepto: '',
      monto: '',
      moneda: 'MXN',
      metodo_pago: 'transferencia',
      fecha_vencimiento: format(addDays(new Date(), 7), "yyyy-MM-dd'T'HH:mm"),
      beneficiario: '',
      referencia: '',
      domiciliacion_activa: false,
      cfdi_id: null,
      customer_id: null,
      vendor_id: null
    });
    setSelectedParty('');
    setSelectedCfdi(null);
    setPendingCfdis([]);
    setUseCustomAmount(false);
  };

  const handleComplete = async (paymentId) => {
    try {
      await api.post(`/payments/${paymentId}/complete`);
      toast.success('Pago marcado como completado');
      loadData();
    } catch (error) {
      toast.error('Error completando pago');
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  const currentParties = formData.tipo === 'cobro' ? customers : vendors;

  return (
    <div className="p-8 space-y-6" data-testid="payments-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Historial de Pagos</h1>
          <p className="text-[#64748B]">Gestión de cobros y pagos programados</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button className="bg-[#0F172A] hover:bg-[#1E293B] gap-2" data-testid="new-payment-button">
              <Plus size={16} />
              Nuevo Pago/Cobro
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Registrar Pago/Cobro</DialogTitle>
              <DialogDescription>Programa un nuevo pago o cobro asociado a una factura</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Tipo y Método */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select value={formData.tipo} onValueChange={handleTipoChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pago">
                        <div className="flex items-center gap-2">
                          <TrendingDown className="text-red-500" size={16} />
                          Pago (Egreso)
                        </div>
                      </SelectItem>
                      <SelectItem value="cobro">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="text-green-500" size={16} />
                          Cobro (Ingreso)
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Método de Pago</Label>
                  <Select value={formData.metodo_pago} onValueChange={(v) => setFormData({...formData, metodo_pago: v})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PAYMENT_METHODS.map(m => (
                        <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Cliente/Proveedor Selector */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  {formData.tipo === 'cobro' ? (
                    <><User size={16} className="text-blue-500" /> Seleccionar Cliente</>
                  ) : (
                    <><Building2 size={16} className="text-orange-500" /> Seleccionar Proveedor</>
                  )}
                </Label>
                <Select value={selectedParty} onValueChange={handlePartyChange}>
                  <SelectTrigger>
                    <SelectValue placeholder={formData.tipo === 'cobro' ? 'Seleccionar cliente...' : 'Seleccionar proveedor...'} />
                  </SelectTrigger>
                  <SelectContent>
                    {currentParties.length === 0 ? (
                      <SelectItem value="none" disabled>
                        No hay {formData.tipo === 'cobro' ? 'clientes' : 'proveedores'} registrados
                      </SelectItem>
                    ) : (
                      currentParties.map(party => (
                        <SelectItem key={party.id} value={party.id}>
                          <div className="flex flex-col">
                            <span className="font-medium">{party.nombre}</span>
                            {party.rfc && <span className="text-xs text-gray-500">{party.rfc}</span>}
                          </div>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Facturas Pendientes */}
              {selectedParty && (
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <FileText size={16} className="text-purple-500" />
                    Facturas Pendientes de {formData.tipo === 'cobro' ? 'Cobro' : 'Pago'}
                  </Label>
                  
                  {pendingCfdis.length === 0 ? (
                    <div className="p-4 bg-gray-50 rounded-lg text-center text-gray-500 flex items-center justify-center gap-2">
                      <AlertCircle size={16} />
                      No hay facturas pendientes para este {formData.tipo === 'cobro' ? 'cliente' : 'proveedor'}
                    </div>
                  ) : (
                    <div className="border rounded-lg max-h-48 overflow-y-auto">
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-gray-50">
                            <TableHead className="w-10"></TableHead>
                            <TableHead>UUID</TableHead>
                            <TableHead>Fecha</TableHead>
                            <TableHead className="text-right">Total</TableHead>
                            <TableHead className="text-right">Pagado</TableHead>
                            <TableHead className="text-right">Pendiente</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {pendingCfdis.map(cfdi => {
                            const isSelected = selectedCfdi?.id === cfdi.id;
                            const pagado = formData.tipo === 'cobro' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0);
                            
                            return (
                              <TableRow 
                                key={cfdi.id} 
                                className={`cursor-pointer hover:bg-blue-50 ${isSelected ? 'bg-blue-100' : ''}`}
                                onClick={() => handleCfdiSelect(cfdi)}
                              >
                                <TableCell>
                                  <Checkbox checked={isSelected} />
                                </TableCell>
                                <TableCell className="font-mono text-xs">
                                  {cfdi.uuid?.substring(0, 8)}...
                                </TableCell>
                                <TableCell className="text-sm">
                                  {format(new Date(cfdi.fecha_emision), 'dd/MM/yy')}
                                </TableCell>
                                <TableCell className="text-right font-mono">
                                  ${cfdi.total.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                </TableCell>
                                <TableCell className="text-right font-mono text-green-600">
                                  ${pagado.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                </TableCell>
                                <TableCell className="text-right font-mono font-bold text-orange-600">
                                  ${cfdi.saldo_pendiente.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              )}

              {/* Selected CFDI Info */}
              {selectedCfdi && (
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="text-sm font-medium text-blue-800">Factura Seleccionada</div>
                      <div className="text-xs text-blue-600">{selectedCfdi.emisor_nombre || selectedCfdi.receptor_nombre}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-blue-800">
                        ${selectedCfdi.saldo_pendiente.toLocaleString('es-MX', {minimumFractionDigits: 2})} {selectedCfdi.moneda}
                      </div>
                      <div className="text-xs text-blue-600">Saldo pendiente</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Monto */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Monto a {formData.tipo === 'cobro' ? 'Cobrar' : 'Pagar'}</Label>
                  {selectedCfdi && (
                    <div className="flex items-center gap-2">
                      <Checkbox 
                        id="customAmount"
                        checked={useCustomAmount}
                        onCheckedChange={(checked) => {
                          setUseCustomAmount(checked);
                          if (!checked) {
                            setFormData(prev => ({ ...prev, monto: selectedCfdi.saldo_pendiente.toFixed(2) }));
                          }
                        }}
                      />
                      <Label htmlFor="customAmount" className="text-sm text-gray-600 cursor-pointer">
                        Pago parcial (monto diferente)
                      </Label>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.monto}
                    onChange={(e) => setFormData({...formData, monto: e.target.value})}
                    required
                    disabled={selectedCfdi && !useCustomAmount}
                    className={`flex-1 ${selectedCfdi && !useCustomAmount ? 'bg-gray-100' : ''}`}
                    placeholder="0.00"
                  />
                  <Select value={formData.moneda} onValueChange={(v) => setFormData({...formData, moneda: v})}>
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MXN">MXN</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {selectedCfdi && useCustomAmount && parseFloat(formData.monto) > selectedCfdi.saldo_pendiente && (
                  <p className="text-xs text-red-500 flex items-center gap-1">
                    <AlertCircle size={12} />
                    El monto excede el saldo pendiente (${selectedCfdi.saldo_pendiente.toFixed(2)})
                  </p>
                )}
              </div>

              {/* Concepto */}
              <div className="space-y-2">
                <Label>Concepto</Label>
                <Input
                  value={formData.concepto}
                  onChange={(e) => setFormData({...formData, concepto: e.target.value})}
                  placeholder="Descripción del pago"
                  required
                />
              </div>

              {/* Fecha y Referencia */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Fecha de Vencimiento</Label>
                  <Input
                    type="datetime-local"
                    value={formData.fecha_vencimiento}
                    onChange={(e) => setFormData({...formData, fecha_vencimiento: e.target.value})}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Referencia / UUID</Label>
                  <Input
                    value={formData.referencia}
                    onChange={(e) => setFormData({...formData, referencia: e.target.value})}
                    placeholder="Número de referencia"
                  />
                </div>
              </div>

              {/* Domiciliación */}
              <div className="flex items-center gap-2">
                <Checkbox
                  id="domiciliacion"
                  checked={formData.domiciliacion_activa}
                  onCheckedChange={(checked) => setFormData({...formData, domiciliacion_activa: checked})}
                />
                <Label htmlFor="domiciliacion" className="cursor-pointer">Domiciliación activa</Label>
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                <Button type="submit" className="bg-[#0F172A]">Registrar {formData.tipo === 'cobro' ? 'Cobro' : 'Pago'}</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card className="border-[#EF4444] bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#DC2626] flex items-center gap-2">
              <TrendingDown size={16} />
              Total a Pagar
            </CardTitle>
            <CardDescription className="text-xs">
              Antes del {summary?.fecha_corte ? format(new Date(summary.fecha_corte), 'dd MMM yyyy') : '-'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#DC2626]">
              ${(summary?.total_por_pagar || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B]">{summary?.pagos_pendientes || 0} pagos pendientes</div>
          </CardContent>
        </Card>

        <Card className="border-[#10B981] bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#059669] flex items-center gap-2">
              <TrendingUp size={16} />
              Total a Cobrar
            </CardTitle>
            <CardDescription className="text-xs">
              Antes del {summary?.fecha_corte ? format(new Date(summary.fecha_corte), 'dd MMM yyyy') : '-'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#059669]">
              ${(summary?.total_por_cobrar || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B]">{summary?.cobros_pendientes || 0} cobros pendientes</div>
          </CardContent>
        </Card>

        <Card className="border-[#0EA5E9] bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#0369A1] flex items-center gap-2">
              <CreditCard size={16} />
              Domiciliación
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#0369A1]">
              ${(summary?.monto_domiciliado || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B]">{summary?.domiciliaciones_activas || 0} activas</div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#64748B] flex items-center gap-2">
              <CheckCircle2 size={16} />
              Pagado Este Mes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#0F172A]">
              ${(summary?.total_pagado_mes || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#64748B] flex items-center gap-2">
              <CheckCircle2 size={16} />
              Cobrado Este Mes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#0F172A]">
              ${(summary?.total_cobrado_mes || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="space-y-1">
              <Label className="text-xs">Tipo</Label>
              <Select value={filterTipo} onValueChange={setFilterTipo}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pago">Pagos</SelectItem>
                  <SelectItem value="cobro">Cobros</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Estatus</Label>
              <Select value={filterEstatus} onValueChange={setFilterEstatus}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pendiente">Pendiente</SelectItem>
                  <SelectItem value="completado">Completado</SelectItem>
                  <SelectItem value="vencido">Vencido</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Desde</Label>
              <Input
                type="date"
                value={filterFechaDesde}
                onChange={(e) => setFilterFechaDesde(e.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Hasta</Label>
              <Input
                type="date"
                value={filterFechaHasta}
                onChange={(e) => setFilterFechaHasta(e.target.value)}
                className="w-40"
              />
            </div>
            <Button variant="outline" onClick={() => {
              setFilterTipo('all');
              setFilterEstatus('all');
              setFilterFechaDesde('');
              setFilterFechaHasta('');
            }}>
              Limpiar Filtros
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Payments Table */}
      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Listado de Pagos y Cobros</CardTitle>
          <CardDescription>{payments.length} registros encontrados</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Fecha Venc.</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Concepto</TableHead>
                <TableHead>Beneficiario</TableHead>
                <TableHead>Referencia</TableHead>
                <TableHead>Método</TableHead>
                <TableHead>Monto</TableHead>
                <TableHead>Estatus</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-[#94A3B8] py-8">
                    No hay pagos registrados. Crea el primero.
                  </TableCell>
                </TableRow>
              ) : (
                payments.map((payment) => (
                  <TableRow key={payment.id}>
                    <TableCell className="mono text-sm">
                      {format(new Date(payment.fecha_vencimiento), 'dd/MM/yyyy')}
                      {payment.domiciliacion_activa && (
                        <span className="ml-2 text-xs px-1 py-0.5 bg-blue-100 text-blue-800 rounded">DOM</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs px-2 py-1 rounded ${
                        payment.tipo === 'cobro' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {payment.tipo === 'cobro' ? '↑ Cobro' : '↓ Pago'}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate">{payment.concepto}</TableCell>
                    <TableCell className="text-sm">{payment.beneficiario || '-'}</TableCell>
                    <TableCell className="text-xs font-mono text-gray-500">
                      {payment.referencia ? payment.referencia.substring(0, 12) + (payment.referencia.length > 12 ? '...' : '') : '-'}
                    </TableCell>
                    <TableCell>
                      <span className="text-xs px-2 py-1 bg-gray-100 text-gray-800 rounded capitalize">
                        {payment.metodo_pago}
                      </span>
                    </TableCell>
                    <TableCell className={`mono font-semibold ${
                      payment.tipo === 'cobro' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {payment.tipo === 'cobro' ? '+' : '-'}${payment.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})} {payment.moneda}
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs px-2 py-1 rounded ${PAYMENT_STATUS[payment.estatus]?.color || 'bg-gray-100'}`}>
                        {PAYMENT_STATUS[payment.estatus]?.label || payment.estatus}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      {payment.estatus === 'pendiente' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-green-600 hover:text-green-800 hover:bg-green-50"
                          onClick={() => handleComplete(payment.id)}
                          title="Marcar como completado"
                        >
                          <Check size={16} />
                        </Button>
                      )}
                      {payment.fecha_pago && (
                        <span className="text-xs text-[#64748B]">
                          Pagado: {format(new Date(payment.fecha_pago), 'dd/MM/yy')}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};

export default PaymentsModule;
