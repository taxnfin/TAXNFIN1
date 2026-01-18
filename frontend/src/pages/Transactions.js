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
import { Plus, Upload, Download, Tag } from 'lucide-react';
import { format } from 'date-fns';

const Transactions = () => {
  const [transactions, setTransactions] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    bank_account_id: '',
    concepto: '',
    monto: '',
    tipo_transaccion: 'egreso',
    fecha_transaccion: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    es_real: false,
    es_proyeccion: true,
    vendor_id: '',
    customer_id: '',
    category_id: '',
    subcategory_id: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [txnRes, accountsRes, vendorsRes, customersRes, categoriesRes] = await Promise.all([
        api.get('/transactions?limit=100'),
        api.get('/bank-accounts'),
        api.get('/vendors'),
        api.get('/customers'),
        api.get('/categories')
      ]);
      setTransactions(txnRes.data);
      setBankAccounts(accountsRes.data);
      setVendors(vendorsRes.data);
      setCustomers(customersRes.data);
      setCategories(categoriesRes.data);
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/transactions', {
        ...formData,
        monto: parseFloat(formData.monto),
        vendor_id: formData.vendor_id || null,
        customer_id: formData.customer_id || null,
        category_id: formData.category_id || null,
        subcategory_id: formData.subcategory_id || null
      });
      toast.success('Transacción creada');
      setDialogOpen(false);
      loadData();
      setFormData({
        bank_account_id: '',
        concepto: '',
        monto: '',
        tipo_transaccion: 'egreso',
        fecha_transaccion: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
        es_real: false,
        es_proyeccion: true,
        vendor_id: '',
        customer_id: '',
        category_id: '',
        subcategory_id: ''
      });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando transacción');
    }
  };

  const getCategoryName = (categoryId) => {
    const cat = categories.find(c => c.id === categoryId);
    return cat ? cat.nombre : '';
  };

  const getCustomerName = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    return customer ? customer.nombre : '';
  };

  const getVendorName = (vendorId) => {
    const vendor = vendors.find(v => v.id === vendorId);
    return vendor ? vendor.nombre : '';
  };

  const selectedCategory = categories.find(c => c.id === formData.category_id);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formDataFile = new FormData();
    formDataFile.append('file', file);

    try {
      const response = await api.post('/transactions/import', formDataFile, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(`Importadas: ${response.data.imported} transacciones`);
      if (response.data.errors.length > 0) {
        toast.warning(`${response.data.errors.length} errores encontrados`);
      }
      loadData();
    } catch (error) {
      toast.error('Error importando transacciones');
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="transactions-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Transacciones</h1>
          <p className="text-[#64748B]">Gestión de ingresos y egresos</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="gap-2"
            onClick={async () => {
              try {
                const response = await api.get('/transactions/template', { responseType: 'blob' });
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', 'plantilla_transacciones.xlsx');
                document.body.appendChild(link);
                link.click();
                link.remove();
                toast.success('Plantilla descargada');
              } catch (error) {
                toast.error('Error descargando plantilla');
              }
            }}
            data-testid="download-template-button"
          >
            <Download size={16} />
            Descargar Plantilla
          </Button>
          
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => document.getElementById('file-upload').click()}
            data-testid="upload-transactions-button"
          >
            <Upload size={16} />
            Importar Excel
          </Button>
          <input
            id="file-upload"
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={handleFileUpload}
          />
          
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#0F172A] hover:bg-[#1E293B] gap-2" data-testid="create-transaction-button">
                <Plus size={16} />
                Nueva Transacción
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Nueva Transacción</DialogTitle>
                <DialogDescription>Registra un ingreso o egreso proyectado o real</DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Cuenta Bancaria</Label>
                  <Select value={formData.bank_account_id} onValueChange={(v) => setFormData({...formData, bank_account_id: v})}>
                    <SelectTrigger data-testid="transaction-bank-account-select">
                      <SelectValue placeholder="Selecciona cuenta" />
                    </SelectTrigger>
                    <SelectContent>
                      {bankAccounts.map(acc => (
                        <SelectItem key={acc.id} value={acc.id}>{acc.nombre} - {acc.banco}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>Concepto</Label>
                  <Input
                    data-testid="transaction-concepto-input"
                    value={formData.concepto}
                    onChange={(e) => setFormData({...formData, concepto: e.target.value})}
                    placeholder="Descripción de la transacción"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Monto</Label>
                    <Input
                      data-testid="transaction-monto-input"
                      type="number"
                      step="0.01"
                      value={formData.monto}
                      onChange={(e) => setFormData({...formData, monto: e.target.value})}
                      required
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Tipo</Label>
                    <Select value={formData.tipo_transaccion} onValueChange={(v) => setFormData({...formData, tipo_transaccion: v})}>
                      <SelectTrigger data-testid="transaction-type-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ingreso">Ingreso</SelectItem>
                        <SelectItem value="egreso">Egreso</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Fecha</Label>
                  <Input
                    data-testid="transaction-fecha-input"
                    type="datetime-local"
                    value={formData.fecha_transaccion}
                    onChange={(e) => setFormData({...formData, fecha_transaccion: e.target.value})}
                    required
                  />
                </div>

                {/* Categoría */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-1">
                    <Tag size={14} className="text-[#8B5CF6]" />
                    Categoría
                  </Label>
                  <Select 
                    value={formData.category_id} 
                    onValueChange={(v) => setFormData({...formData, category_id: v, subcategory_id: ''})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar categoría (opcional)" />
                    </SelectTrigger>
                    <SelectContent>
                      {categories
                        .filter(c => c.tipo === formData.tipo_transaccion)
                        .map(cat => (
                          <SelectItem key={cat.id} value={cat.id}>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{backgroundColor: cat.color}} />
                              {cat.nombre}
                            </div>
                          </SelectItem>
                        ))
                      }
                    </SelectContent>
                  </Select>
                </div>

                {/* Subcategoría */}
                {selectedCategory && selectedCategory.subcategorias && selectedCategory.subcategorias.length > 0 && (
                  <div className="space-y-2">
                    <Label>Subcategoría</Label>
                    <Select 
                      value={formData.subcategory_id} 
                      onValueChange={(v) => setFormData({...formData, subcategory_id: v})}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar subcategoría (opcional)" />
                      </SelectTrigger>
                      <SelectContent>
                        {selectedCategory.subcategorias.map(sub => (
                          <SelectItem key={sub.id} value={sub.id}>{sub.nombre}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* Cliente para Ingresos */}
                {formData.tipo_transaccion === 'ingreso' && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-1">
                      <span className="text-blue-600">👤</span> Cliente
                    </Label>
                    <Select 
                      value={formData.customer_id} 
                      onValueChange={(v) => setFormData({...formData, customer_id: v})}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar cliente (opcional)" />
                      </SelectTrigger>
                      <SelectContent>
                        {customers.map(customer => (
                          <SelectItem key={customer.id} value={customer.id}>
                            <div className="flex flex-col">
                              <span>{customer.nombre}</span>
                              <span className="text-xs text-[#64748B]">{customer.rfc}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* Proveedor para Egresos */}
                {formData.tipo_transaccion === 'egreso' && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-1">
                      <span className="text-orange-600">🏢</span> Proveedor
                    </Label>
                    <Select 
                      value={formData.vendor_id} 
                      onValueChange={(v) => setFormData({...formData, vendor_id: v})}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar proveedor (opcional)" />
                      </SelectTrigger>
                      <SelectContent>
                        {vendors.map(vendor => (
                          <SelectItem key={vendor.id} value={vendor.id}>
                            <div className="flex flex-col">
                              <span>{vendor.nombre}</span>
                              <span className="text-xs text-[#64748B]">{vendor.rfc}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.es_real}
                      onChange={(e) => setFormData({...formData, es_real: e.target.checked, es_proyeccion: !e.target.checked})}
                      className="rounded"
                    />
                    <span className="text-sm">Es real</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.es_proyeccion}
                      onChange={(e) => setFormData({...formData, es_proyeccion: e.target.checked, es_real: !e.target.checked})}
                      className="rounded"
                    />
                    <span className="text-sm">Es proyección</span>
                  </label>
                </div>

                <DialogFooter>
                  <Button type="submit" data-testid="transaction-submit-button">Crear Transacción</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Listado de Transacciones</CardTitle>
          <CardDescription>{transactions.length} transacciones registradas</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead>Concepto</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Monto</TableHead>
                <TableHead>Categoría / Tercero</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Origen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-[#94A3B8] py-8">
                    No hay transacciones registradas. Crea la primera.
                  </TableCell>
                </TableRow>
              ) : (
                transactions.map((txn) => (
                  <TableRow key={txn.id} data-testid={`transaction-row-${txn.id}`}>
                    <TableCell className="mono">{format(new Date(txn.fecha_transaccion), 'dd/MM/yyyy HH:mm')}</TableCell>
                    <TableCell>{txn.concepto}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 text-xs rounded ${txn.tipo_transaccion === 'ingreso' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {txn.tipo_transaccion === 'ingreso' ? '↑ Ingreso' : '↓ Egreso'}
                      </span>
                    </TableCell>
                    <TableCell className={`mono font-semibold ${txn.tipo_transaccion === 'ingreso' ? 'text-green-600' : 'text-red-600'}`}>
                      {txn.tipo_transaccion === 'ingreso' ? '+' : '-'}${txn.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        {txn.category_id && (
                          <div className="text-sm font-medium flex items-center gap-1">
                            <Tag size={12} className="text-[#8B5CF6]" />
                            {getCategoryName(txn.category_id)}
                          </div>
                        )}
                        {txn.tipo_transaccion === 'ingreso' && txn.customer_id && (
                          <div className="text-xs text-blue-600">
                            👤 {getCustomerName(txn.customer_id)}
                          </div>
                        )}
                        {txn.tipo_transaccion === 'egreso' && txn.vendor_id && (
                          <div className="text-xs text-orange-600">
                            🏢 {getVendorName(txn.vendor_id)}
                          </div>
                        )}
                        {!txn.category_id && !txn.customer_id && !txn.vendor_id && (
                          <span className="text-xs text-[#94A3B8]">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {txn.es_real && <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">Real</span>}
                      {txn.es_proyeccion && <span className="text-xs px-2 py-1 bg-amber-100 text-amber-800 rounded">Proyección</span>}
                    </TableCell>
                    <TableCell className="text-xs text-[#64748B]">{txn.origen}</TableCell>
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

export default Transactions;
