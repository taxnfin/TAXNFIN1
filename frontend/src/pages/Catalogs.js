import { useState, useEffect, useRef } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Plus, Download, Upload, FileSpreadsheet, Pencil, Trash2, AlertTriangle } from 'lucide-react';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';

const Catalogs = () => {
  const [companies, setCompanies] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogs, setDialogs] = useState({ 
    company: false, account: false, vendor: false, customer: false, 
    editAccount: false, editVendor: false, editCustomer: false 
  });
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, type: null, item: null });
  
  const [companyForm, setCompanyForm] = useState({ nombre: '', rfc: '', moneda_base: 'MXN', pais: 'México' });
  const [accountForm, setAccountForm] = useState({ nombre: '', numero_cuenta: '', banco: '', moneda: 'MXN', saldo_inicial: 0 });
  const [editingAccount, setEditingAccount] = useState(null);
  const [vendorForm, setVendorForm] = useState({ nombre: '', rfc: '', email: '', telefono: '' });
  const [editingVendor, setEditingVendor] = useState(null);
  const [customerForm, setCustomerForm] = useState({ nombre: '', rfc: '', email: '', telefono: '' });
  const [editingCustomer, setEditingCustomer] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [companiesRes, accountsRes, vendorsRes, customersRes] = await Promise.all([
        api.get('/companies'),
        api.get('/bank-accounts'),
        api.get('/vendors'),
        api.get('/customers')
      ]);
      setCompanies(companiesRes.data);
      setBankAccounts(accountsRes.data);
      setVendors(vendorsRes.data);
      setCustomers(customersRes.data);
    } catch (error) {
      toast.error('Error cargando catálogos');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCompany = async (e) => {
    e.preventDefault();
    try {
      await api.post('/companies', companyForm);
      toast.success('Empresa creada');
      setDialogs({ ...dialogs, company: false });
      loadData();
      setCompanyForm({ nombre: '', rfc: '', moneda_base: 'MXN', pais: 'México' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando empresa');
    }
  };

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    try {
      await api.post('/bank-accounts', { ...accountForm, saldo_inicial: parseFloat(accountForm.saldo_inicial) });
      toast.success('Cuenta bancaria creada');
      setDialogs({ ...dialogs, account: false });
      loadData();
      setAccountForm({ nombre: '', numero_cuenta: '', banco: '', moneda: 'MXN', saldo_inicial: 0 });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando cuenta');
    }
  };

  const handleEditAccount = (account) => {
    setEditingAccount(account);
    setAccountForm({
      nombre: account.nombre,
      numero_cuenta: account.numero_cuenta,
      banco: account.banco,
      moneda: account.moneda,
      saldo_inicial: account.saldo_inicial
    });
    setDialogs({ ...dialogs, editAccount: true });
  };

  const handleUpdateAccount = async (e) => {
    e.preventDefault();
    if (!editingAccount) return;
    
    try {
      await api.put(`/bank-accounts/${editingAccount.id}`, { 
        ...accountForm, 
        saldo_inicial: parseFloat(accountForm.saldo_inicial) 
      });
      toast.success('Cuenta bancaria actualizada');
      setDialogs({ ...dialogs, editAccount: false });
      setEditingAccount(null);
      loadData();
      setAccountForm({ nombre: '', numero_cuenta: '', banco: '', moneda: 'MXN', saldo_inicial: 0 });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error actualizando cuenta');
    }
  };

  const handleDeleteAccount = async () => {
    if (!deleteConfirm.item || deleteConfirm.type !== 'account') return;
    
    try {
      await api.delete(`/bank-accounts/${deleteConfirm.item.id}`);
      toast.success('Cuenta bancaria eliminada');
      setDeleteConfirm({ open: false, type: null, item: null });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando cuenta');
    }
  };

  // ===== VENDOR HANDLERS =====
  const handleEditVendor = (vendor) => {
    setEditingVendor(vendor);
    setVendorForm({
      nombre: vendor.nombre,
      rfc: vendor.rfc || '',
      email: vendor.email || '',
      telefono: vendor.telefono || ''
    });
    setDialogs({ ...dialogs, editVendor: true });
  };

  const handleUpdateVendor = async (e) => {
    e.preventDefault();
    if (!editingVendor) return;
    
    try {
      await api.put(`/vendors/${editingVendor.id}`, vendorForm);
      toast.success('Proveedor actualizado');
      setDialogs({ ...dialogs, editVendor: false });
      setEditingVendor(null);
      loadData();
      setVendorForm({ nombre: '', rfc: '', email: '', telefono: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error actualizando proveedor');
    }
  };

  const handleDeleteVendor = async () => {
    if (!deleteConfirm.item || deleteConfirm.type !== 'vendor') return;
    
    try {
      await api.delete(`/vendors/${deleteConfirm.item.id}`);
      toast.success('Proveedor eliminado');
      setDeleteConfirm({ open: false, type: null, item: null });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando proveedor');
    }
  };

  // ===== CUSTOMER HANDLERS =====
  const handleEditCustomer = (customer) => {
    setEditingCustomer(customer);
    setCustomerForm({
      nombre: customer.nombre,
      rfc: customer.rfc || '',
      email: customer.email || '',
      telefono: customer.telefono || ''
    });
    setDialogs({ ...dialogs, editCustomer: true });
  };

  const handleUpdateCustomer = async (e) => {
    e.preventDefault();
    if (!editingCustomer) return;
    
    try {
      await api.put(`/customers/${editingCustomer.id}`, customerForm);
      toast.success('Cliente actualizado');
      setDialogs({ ...dialogs, editCustomer: false });
      setEditingCustomer(null);
      loadData();
      setCustomerForm({ nombre: '', rfc: '', email: '', telefono: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error actualizando cliente');
    }
  };

  const handleDeleteCustomer = async () => {
    if (!deleteConfirm.item || deleteConfirm.type !== 'customer') return;
    
    try {
      await api.delete(`/customers/${deleteConfirm.item.id}`);
      toast.success('Cliente eliminado');
      setDeleteConfirm({ open: false, type: null, item: null });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando cliente');
    }
  };

  const handleCreateVendor = async (e) => {
    e.preventDefault();
    try {
      await api.post('/vendors', vendorForm);
      toast.success('Proveedor creado');
      setDialogs({ ...dialogs, vendor: false });
      loadData();
      setVendorForm({ nombre: '', rfc: '', email: '', telefono: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando proveedor');
    }
  };

  const handleCreateCustomer = async (e) => {
    e.preventDefault();
    try {
      await api.post('/customers', customerForm);
      toast.success('Cliente creado');
      setDialogs({ ...dialogs, customer: false });
      loadData();
      setCustomerForm({ nombre: '', rfc: '', email: '', telefono: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando cliente');
    }
  };

  // Template downloads
  const downloadVendorsTemplate = async () => {
    try {
      const response = await api.get('/vendors/template', { responseType: 'blob' });
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'plantilla_proveedores.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Plantilla descargada');
    } catch (error) {
      toast.error('Error descargando plantilla');
    }
  };

  const downloadCustomersTemplate = async () => {
    try {
      const response = await api.get('/customers/template', { responseType: 'blob' });
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'plantilla_clientes.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Plantilla descargada');
    } catch (error) {
      toast.error('Error descargando plantilla');
    }
  };

  // Import handlers
  const handleImportVendors = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/vendors/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const { imported, updated, errors } = response.data;
      toast.success(`${imported} proveedores importados, ${updated} actualizados`);
      if (errors && errors.length > 0) {
        toast.error(`${errors.length} errores: ${errors.slice(0, 2).join(', ')}`);
      }
      loadData();
    } catch (error) {
      toast.error('Error importando proveedores');
    }
    e.target.value = '';
  };

  const handleImportCustomers = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/customers/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const { imported, updated, errors } = response.data;
      toast.success(`${imported} clientes importados, ${updated} actualizados`);
      if (errors && errors.length > 0) {
        toast.error(`${errors.length} errores: ${errors.slice(0, 2).join(', ')}`);
      }
      loadData();
    } catch (error) {
      toast.error('Error importando clientes');
    }
    e.target.value = '';
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="catalogs-page">
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Catálogos</h1>
        <p className="text-[#64748B]">Gestión de empresas, cuentas, proveedores y clientes</p>
      </div>

      <Tabs defaultValue="companies" className="w-full">
        <TabsList>
          <TabsTrigger value="companies" data-testid="tab-companies">Empresas</TabsTrigger>
          <TabsTrigger value="accounts" data-testid="tab-accounts">Cuentas Bancarias</TabsTrigger>
          <TabsTrigger value="vendors" data-testid="tab-vendors">Proveedores</TabsTrigger>
          <TabsTrigger value="customers" data-testid="tab-customers">Clientes</TabsTrigger>
        </TabsList>

        <TabsContent value="companies">
          <Card className="border-[#E2E8F0]">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Empresas</CardTitle>
                <CardDescription>{companies.length} empresas registradas</CardDescription>
              </div>
              <Dialog open={dialogs.company} onOpenChange={(open) => setDialogs({...dialogs, company: open})}>
                <DialogTrigger asChild>
                  <Button className="bg-[#0F172A] gap-2" data-testid="create-company-button">
                    <Plus size={16} /> Nueva Empresa
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Nueva Empresa</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleCreateCompany} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Nombre</Label>
                      <Input data-testid="company-nombre-input" value={companyForm.nombre} onChange={(e) => setCompanyForm({...companyForm, nombre: e.target.value})} required />
                    </div>
                    <div className="space-y-2">
                      <Label>RFC</Label>
                      <Input data-testid="company-rfc-input" value={companyForm.rfc} onChange={(e) => setCompanyForm({...companyForm, rfc: e.target.value})} required />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Moneda Base</Label>
                        <Input value={companyForm.moneda_base} onChange={(e) => setCompanyForm({...companyForm, moneda_base: e.target.value})} />
                      </div>
                      <div className="space-y-2">
                        <Label>País</Label>
                        <Input value={companyForm.pais} onChange={(e) => setCompanyForm({...companyForm, pais: e.target.value})} />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="submit" data-testid="company-submit-button">Crear Empresa</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table className="data-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>RFC</TableHead>
                    <TableHead>Moneda</TableHead>
                    <TableHead>País</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {companies.map((company) => (
                    <TableRow key={company.id}>
                      <TableCell className="font-medium">{company.nombre}</TableCell>
                      <TableCell className="mono">{company.rfc}</TableCell>
                      <TableCell>{company.moneda_base}</TableCell>
                      <TableCell>{company.pais}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="accounts">
          <Card className="border-[#E2E8F0]">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Cuentas Bancarias</CardTitle>
                <CardDescription>{bankAccounts.length} cuentas registradas</CardDescription>
              </div>
              <Dialog open={dialogs.account} onOpenChange={(open) => setDialogs({...dialogs, account: open})}>
                <DialogTrigger asChild>
                  <Button className="bg-[#0F172A] gap-2" data-testid="create-account-button">
                    <Plus size={16} /> Nueva Cuenta
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Nueva Cuenta Bancaria</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleCreateAccount} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Nombre</Label>
                      <Input data-testid="account-nombre-input" value={accountForm.nombre} onChange={(e) => setAccountForm({...accountForm, nombre: e.target.value})} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Banco</Label>
                      <Input data-testid="account-banco-input" value={accountForm.banco} onChange={(e) => setAccountForm({...accountForm, banco: e.target.value})} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Número de Cuenta</Label>
                      <Input data-testid="account-numero-input" value={accountForm.numero_cuenta} onChange={(e) => setAccountForm({...accountForm, numero_cuenta: e.target.value})} required />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Moneda</Label>
                        <Input value={accountForm.moneda} onChange={(e) => setAccountForm({...accountForm, moneda: e.target.value})} />
                      </div>
                      <div className="space-y-2">
                        <Label>Saldo Inicial</Label>
                        <Input type="number" step="0.01" value={accountForm.saldo_inicial} onChange={(e) => setAccountForm({...accountForm, saldo_inicial: e.target.value})} />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="submit" data-testid="account-submit-button">Crear Cuenta</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table className="data-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Banco</TableHead>
                    <TableHead>Número</TableHead>
                    <TableHead>Moneda</TableHead>
                    <TableHead>Saldo Inicial</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bankAccounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell className="font-medium">{account.nombre}</TableCell>
                      <TableCell>{account.banco}</TableCell>
                      <TableCell className="mono">{account.numero_cuenta}</TableCell>
                      <TableCell>{account.moneda}</TableCell>
                      <TableCell className="mono">${account.saldo_inicial?.toLocaleString('es-MX') || '0'}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleEditAccount(account)}
                            className="h-8 w-8 p-0 text-blue-600 hover:text-blue-800 hover:bg-blue-50"
                            data-testid={`edit-account-${account.id}`}
                          >
                            <Pencil size={14} />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => setDeleteConfirm({ open: true, type: 'account', item: account })}
                            className="h-8 w-8 p-0 text-red-600 hover:text-red-800 hover:bg-red-50"
                            data-testid={`delete-account-${account.id}`}
                          >
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Edit Account Dialog */}
          <Dialog open={dialogs.editAccount} onOpenChange={(open) => {
            setDialogs({...dialogs, editAccount: open});
            if (!open) {
              setEditingAccount(null);
              setAccountForm({ nombre: '', numero_cuenta: '', banco: '', moneda: 'MXN', saldo_inicial: 0 });
            }
          }}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Editar Cuenta Bancaria</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleUpdateAccount} className="space-y-4">
                <div className="space-y-2">
                  <Label>Nombre</Label>
                  <Input value={accountForm.nombre} onChange={(e) => setAccountForm({...accountForm, nombre: e.target.value})} required />
                </div>
                <div className="space-y-2">
                  <Label>Banco</Label>
                  <Input value={accountForm.banco} onChange={(e) => setAccountForm({...accountForm, banco: e.target.value})} required />
                </div>
                <div className="space-y-2">
                  <Label>Número de Cuenta</Label>
                  <Input value={accountForm.numero_cuenta} onChange={(e) => setAccountForm({...accountForm, numero_cuenta: e.target.value})} required />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Moneda</Label>
                    <Input value={accountForm.moneda} onChange={(e) => setAccountForm({...accountForm, moneda: e.target.value})} />
                  </div>
                  <div className="space-y-2">
                    <Label>Saldo Inicial</Label>
                    <Input type="number" step="0.01" value={accountForm.saldo_inicial} onChange={(e) => setAccountForm({...accountForm, saldo_inicial: e.target.value})} />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setDialogs({...dialogs, editAccount: false})}>
                    Cancelar
                  </Button>
                  <Button type="submit">Guardar Cambios</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          {/* Delete Confirmation Dialog */}
          <AlertDialog open={deleteConfirm.open} onOpenChange={(open) => setDeleteConfirm({ ...deleteConfirm, open })}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-red-500" />
                  ¿Eliminar cuenta bancaria?
                </AlertDialogTitle>
                <AlertDialogDescription>
                  Esta acción no se puede deshacer. Se eliminará permanentemente la cuenta 
                  <strong> "{deleteConfirm.account?.nombre}"</strong> del banco {deleteConfirm.account?.banco}.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={handleDeleteAccount}
                  className="bg-red-600 hover:bg-red-700"
                >
                  Eliminar
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </TabsContent>

        <TabsContent value="vendors">
          <Card className="border-[#E2E8F0]">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-orange-600">🏢</span> Proveedores
                </CardTitle>
                <CardDescription>{vendors.length} proveedores registrados</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="gap-2" onClick={downloadVendorsTemplate} data-testid="download-vendors-template">
                  <Download size={16} />
                  Plantilla
                </Button>
                <Button variant="outline" className="gap-2" onClick={() => document.getElementById('vendors-import').click()} data-testid="import-vendors-button">
                  <Upload size={16} />
                  Importar
                </Button>
                <input
                  id="vendors-import"
                  type="file"
                  accept=".xlsx,.xls"
                  className="hidden"
                  onChange={handleImportVendors}
                />
                <Dialog open={dialogs.vendor} onOpenChange={(open) => setDialogs({...dialogs, vendor: open})}>
                  <DialogTrigger asChild>
                    <Button className="bg-[#0F172A] gap-2" data-testid="create-vendor-button">
                      <Plus size={16} /> Nuevo Proveedor
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Nuevo Proveedor</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleCreateVendor} className="space-y-4">
                      <div className="space-y-2">
                        <Label>Nombre</Label>
                        <Input data-testid="vendor-nombre-input" value={vendorForm.nombre} onChange={(e) => setVendorForm({...vendorForm, nombre: e.target.value})} required />
                      </div>
                      <div className="space-y-2">
                        <Label>RFC</Label>
                        <Input data-testid="vendor-rfc-input" value={vendorForm.rfc} onChange={(e) => setVendorForm({...vendorForm, rfc: e.target.value})} />
                      </div>
                      <div className="space-y-2">
                        <Label>Email</Label>
                        <Input type="email" value={vendorForm.email} onChange={(e) => setVendorForm({...vendorForm, email: e.target.value})} />
                      </div>
                      <div className="space-y-2">
                        <Label>Teléfono</Label>
                        <Input value={vendorForm.telefono} onChange={(e) => setVendorForm({...vendorForm, telefono: e.target.value})} />
                      </div>
                      <DialogFooter>
                        <Button type="submit" data-testid="vendor-submit-button">Crear Proveedor</Button>
                      </DialogFooter>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {vendors.length === 0 ? (
                <div className="text-center py-12">
                  <FileSpreadsheet size={48} className="mx-auto text-[#94A3B8] mb-4" />
                  <p className="text-[#64748B] mb-4">No hay proveedores registrados</p>
                  <div className="flex gap-2 justify-center">
                    <Button variant="outline" className="gap-2" onClick={downloadVendorsTemplate}>
                      <Download size={16} /> Descargar Plantilla
                    </Button>
                    <Button className="bg-[#0F172A] gap-2" onClick={() => document.getElementById('vendors-import').click()}>
                      <Upload size={16} /> Importar Excel
                    </Button>
                  </div>
                </div>
              ) : (
                <Table className="data-table">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nombre</TableHead>
                      <TableHead>RFC</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Teléfono</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendors.map((vendor) => (
                      <TableRow key={vendor.id}>
                        <TableCell className="font-medium">{vendor.nombre}</TableCell>
                        <TableCell className="mono">{vendor.rfc || '-'}</TableCell>
                        <TableCell>{vendor.email || '-'}</TableCell>
                        <TableCell>{vendor.telefono || '-'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="customers">
          <Card className="border-[#E2E8F0]">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-blue-600">👤</span> Clientes
                </CardTitle>
                <CardDescription>{customers.length} clientes registrados</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="gap-2" onClick={downloadCustomersTemplate} data-testid="download-customers-template">
                  <Download size={16} />
                  Plantilla
                </Button>
                <Button variant="outline" className="gap-2" onClick={() => document.getElementById('customers-import').click()} data-testid="import-customers-button">
                  <Upload size={16} />
                  Importar
                </Button>
                <input
                  id="customers-import"
                  type="file"
                  accept=".xlsx,.xls"
                  className="hidden"
                  onChange={handleImportCustomers}
                />
                <Dialog open={dialogs.customer} onOpenChange={(open) => setDialogs({...dialogs, customer: open})}>
                  <DialogTrigger asChild>
                    <Button className="bg-[#0F172A] gap-2" data-testid="create-customer-button">
                      <Plus size={16} /> Nuevo Cliente
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Nuevo Cliente</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleCreateCustomer} className="space-y-4">
                      <div className="space-y-2">
                        <Label>Nombre</Label>
                        <Input data-testid="customer-nombre-input" value={customerForm.nombre} onChange={(e) => setCustomerForm({...customerForm, nombre: e.target.value})} required />
                      </div>
                      <div className="space-y-2">
                        <Label>RFC</Label>
                        <Input data-testid="customer-rfc-input" value={customerForm.rfc} onChange={(e) => setCustomerForm({...customerForm, rfc: e.target.value})} />
                      </div>
                      <div className="space-y-2">
                        <Label>Email</Label>
                        <Input type="email" value={customerForm.email} onChange={(e) => setCustomerForm({...customerForm, email: e.target.value})} />
                      </div>
                      <div className="space-y-2">
                        <Label>Teléfono</Label>
                        <Input value={customerForm.telefono} onChange={(e) => setCustomerForm({...customerForm, telefono: e.target.value})} />
                      </div>
                      <DialogFooter>
                        <Button type="submit" data-testid="customer-submit-button">Crear Cliente</Button>
                      </DialogFooter>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {customers.length === 0 ? (
                <div className="text-center py-12">
                  <FileSpreadsheet size={48} className="mx-auto text-[#94A3B8] mb-4" />
                  <p className="text-[#64748B] mb-4">No hay clientes registrados</p>
                  <div className="flex gap-2 justify-center">
                    <Button variant="outline" className="gap-2" onClick={downloadCustomersTemplate}>
                      <Download size={16} /> Descargar Plantilla
                    </Button>
                    <Button className="bg-[#0F172A] gap-2" onClick={() => document.getElementById('customers-import').click()}>
                      <Upload size={16} /> Importar Excel
                    </Button>
                  </div>
                </div>
              ) : (
                <Table className="data-table">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nombre</TableHead>
                      <TableHead>RFC</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Teléfono</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {customers.map((customer) => (
                      <TableRow key={customer.id}>
                        <TableCell className="font-medium">{customer.nombre}</TableCell>
                        <TableCell className="mono">{customer.rfc || '-'}</TableCell>
                        <TableCell>{customer.email || '-'}</TableCell>
                        <TableCell>{customer.telefono || '-'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Catalogs;
