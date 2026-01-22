import * as XLSX from 'xlsx';
import { format } from 'date-fns';

/**
 * Export data to Excel file (.xlsx)
 * @param {Array} data - Array of objects to export
 * @param {string} filename - Base filename (without extension)
 * @param {string} sheetName - Name of the Excel sheet
 * @param {Object} options - Additional options
 */
export const exportToExcel = (data, filename, sheetName = 'Datos', options = {}) => {
  if (!data || data.length === 0) {
    console.error('No data to export');
    return false;
  }

  try {
    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // Create worksheet from data
    const ws = XLSX.utils.json_to_sheet(data);
    
    // Auto-width columns
    const colWidths = [];
    const headers = Object.keys(data[0]);
    headers.forEach((header, i) => {
      let maxWidth = header.length;
      data.forEach(row => {
        const val = row[header];
        const len = val ? String(val).length : 0;
        if (len > maxWidth) maxWidth = len;
      });
      colWidths.push({ wch: Math.min(maxWidth + 2, 50) });
    });
    ws['!cols'] = colWidths;
    
    // Add worksheet to workbook
    XLSX.utils.book_append_sheet(wb, ws, sheetName);
    
    // Generate filename with timestamp
    const timestamp = format(new Date(), 'yyyy-MM-dd_HHmm');
    const fullFilename = `${filename}_${timestamp}.xlsx`;
    
    // Use XLSX native writeFile for browser download
    XLSX.writeFile(wb, fullFilename);
    
    return true;
  } catch (error) {
    console.error('Error exporting to Excel:', error);
    return false;
  }
};

/**
 * Export multiple sheets to Excel
 * @param {Array} sheets - Array of {name, data} objects
 * @param {string} filename - Base filename
 */
export const exportMultiSheetExcel = (sheets, filename) => {
  if (!sheets || sheets.length === 0) {
    console.error('No sheets to export');
    return false;
  }

  try {
    const wb = XLSX.utils.book_new();
    
    sheets.forEach(sheet => {
      if (sheet.data && sheet.data.length > 0) {
        const ws = XLSX.utils.json_to_sheet(sheet.data);
        
        // Auto-width columns
        const colWidths = [];
        const headers = Object.keys(sheet.data[0]);
        headers.forEach((header) => {
          let maxWidth = header.length;
          sheet.data.forEach(row => {
            const val = row[header];
            const len = val ? String(val).length : 0;
            if (len > maxWidth) maxWidth = len;
          });
          colWidths.push({ wch: Math.min(maxWidth + 2, 50) });
        });
        ws['!cols'] = colWidths;
        
        XLSX.utils.book_append_sheet(wb, ws, sheet.name.substring(0, 31)); // Sheet name max 31 chars
      }
    });
    
    // Generate filename with timestamp
    const timestamp = format(new Date(), 'yyyy-MM-dd_HHmm');
    const fullFilename = `${filename}_${timestamp}.xlsx`;
    
    // Use XLSX native writeFile for browser download
    XLSX.writeFile(wb, fullFilename);
    
    return true;
  } catch (error) {
    console.error('Error exporting to Excel:', error);
    return false;
  }
};

// Pre-configured export functions for each module

export const exportCFDIs = (cfdis, categories) => {
  const getCategoryName = (catId) => {
    const cat = categories.find(c => c.id === catId);
    return cat?.nombre || '';
  };
  
  const getSubcategoryName = (catId, subId) => {
    const cat = categories.find(c => c.id === catId);
    const sub = cat?.subcategorias?.find(s => s.id === subId);
    return sub?.nombre || '';
  };

  const data = cfdis.map(cfdi => ({
    'Fecha Emisión': cfdi.fecha_emision ? format(new Date(cfdi.fecha_emision), 'dd/MM/yyyy') : '',
    'UUID': cfdi.uuid || '',
    'Tipo': cfdi.tipo_cfdi === 'ingreso' ? 'Ingreso' : 'Egreso',
    'Emisor RFC': cfdi.emisor_rfc || '',
    'Emisor Nombre': cfdi.emisor_nombre || '',
    'Receptor RFC': cfdi.receptor_rfc || '',
    'Receptor Nombre': cfdi.receptor_nombre || '',
    'Categoría': getCategoryName(cfdi.category_id),
    'Subcategoría': getSubcategoryName(cfdi.category_id, cfdi.subcategory_id),
    'Subtotal': cfdi.subtotal || 0,
    'IVA': cfdi.iva || 0,
    'Total': cfdi.total || 0,
    'Moneda': cfdi.moneda || 'MXN',
    'Método Pago': cfdi.metodo_pago || '',
    'Forma Pago': cfdi.forma_pago || '',
    'Uso CFDI': cfdi.uso_cfdi || '',
    'Estado': cfdi.estado_conciliacion || 'pendiente'
  }));

  return exportToExcel(data, 'CFDIs', 'CFDIs');
};

export const exportPayments = (payments, fxRates = {}) => {
  const data = payments.map(p => {
    const moneda = p.moneda || 'MXN';
    const monto = p.monto || 0;
    // Get FX rate - prioritize the rate stored in the payment (historical) or use current rate
    const tcHistorico = p.tipo_cambio_historico || fxRates[moneda] || 1;
    const montoMXN = moneda === 'MXN' ? monto : monto * tcHistorico;
    
    return {
      'Fecha Vencimiento': p.fecha_vencimiento ? format(new Date(p.fecha_vencimiento), 'dd/MM/yyyy') : '',
      'Fecha Pago': p.fecha_pago ? format(new Date(p.fecha_pago), 'dd/MM/yyyy') : '',
      'Tipo': p.tipo === 'cobro' ? 'Cobro' : 'Pago',
      'Concepto': p.concepto || '',
      'Beneficiario': p.beneficiario || '',
      'Monto Original': monto,
      'Moneda': moneda,
      'TC Histórico': moneda !== 'MXN' ? tcHistorico : '',
      'Monto MXN': Math.round(montoMXN * 100) / 100,
      'Método': p.metodo_pago || '',
      'Estatus': p.estatus || '',
      'Real/Proyección': p.es_real ? 'Real' : 'Proyección',
      'Referencia': p.referencia || '',
      'Cuenta Bancaria': p.bank_account_name || '',
      'Notas': p.notas || ''
    };
  });

  return exportToExcel(data, 'Pagos', 'Pagos');
};

export const exportBankAccounts = (accounts, summary) => {
  const data = accounts.map(acc => ({
    'Banco': acc.banco || '',
    'Nombre Cuenta': acc.nombre || '',
    'Número Cuenta': acc.numero_cuenta || '',
    'Moneda': acc.moneda || 'MXN',
    'Saldo Inicial': acc.saldo_inicial || 0,
    'Fecha Saldo': acc.fecha_saldo ? format(new Date(acc.fecha_saldo), 'dd/MM/yyyy') : '',
    'País': acc.pais_banco || '',
    'Activa': acc.activo ? 'Sí' : 'No'
  }));

  return exportToExcel(data, 'Cuentas_Bancarias', 'Cuentas');
};

export const exportCustomers = (customers) => {
  const data = customers.map(c => ({
    'Nombre': c.nombre || '',
    'RFC': c.rfc || '',
    'Email': c.email || '',
    'Teléfono': c.telefono || '',
    'Dirección': c.direccion || '',
    'Activo': c.activo ? 'Sí' : 'No'
  }));

  return exportToExcel(data, 'Clientes', 'Clientes');
};

export const exportVendors = (vendors) => {
  const data = vendors.map(v => ({
    'Nombre': v.nombre || '',
    'RFC': v.rfc || '',
    'Email': v.email || '',
    'Teléfono': v.telefono || '',
    'Dirección': v.direccion || '',
    'Banco': v.banco || '',
    'Cuenta': v.cuenta_bancaria || '',
    'CLABE': v.clabe || '',
    'Activo': v.activo ? 'Sí' : 'No'
  }));

  return exportToExcel(data, 'Proveedores', 'Proveedores');
};

export const exportCategories = (categories) => {
  const data = [];
  categories.forEach(cat => {
    data.push({
      'Categoría': cat.nombre || '',
      'Tipo': cat.tipo === 'ingreso' ? 'Ingreso' : 'Egreso',
      'Subcategoría': '',
      'Activa': cat.activo ? 'Sí' : 'No'
    });
    if (cat.subcategorias) {
      cat.subcategorias.forEach(sub => {
        data.push({
          'Categoría': cat.nombre || '',
          'Tipo': cat.tipo === 'ingreso' ? 'Ingreso' : 'Egreso',
          'Subcategoría': sub.nombre || '',
          'Activa': sub.activo ? 'Sí' : 'No'
        });
      });
    }
  });

  return exportToExcel(data, 'Categorias', 'Categorías');
};

export const exportAging = (cxcData, cxpData) => {
  const sheets = [];
  
  if (cxcData && cxcData.length > 0) {
    sheets.push({
      name: 'CxC',
      data: cxcData.map(c => ({
        'Antigüedad': c.bucket || '',
        'Cliente': c.cliente || '',
        'UUID': c.uuid || '',
        'Fecha': c.fecha ? format(new Date(c.fecha), 'dd/MM/yyyy') : '',
        'Días Vencido': c.dias || 0,
        'Moneda': c.moneda || 'MXN',
        'Total': c.total || 0,
        'Pagado': c.pagado || 0,
        'Pendiente': c.pendiente || 0,
        'Pendiente MXN': c.pendienteMXN || 0
      }))
    });
  }
  
  if (cxpData && cxpData.length > 0) {
    sheets.push({
      name: 'CxP',
      data: cxpData.map(c => ({
        'Antigüedad': c.bucket || '',
        'Proveedor': c.proveedor || '',
        'UUID': c.uuid || '',
        'Fecha': c.fecha ? format(new Date(c.fecha), 'dd/MM/yyyy') : '',
        'Días Vencido': c.dias || 0,
        'Moneda': c.moneda || 'MXN',
        'Total': c.total || 0,
        'Pagado': c.pagado || 0,
        'Pendiente': c.pendiente || 0,
        'Pendiente MXN': c.pendienteMXN || 0
      }))
    });
  }

  return exportMultiSheetExcel(sheets, 'Aging_Cartera');
};

export const exportProjections = (weeklyData, saldoInicial, currency = 'MXN', fxRate = 1) => {
  if (!weeklyData || weeklyData.length === 0) {
    console.error('No data to export');
    return false;
  }

  try {
    const convert = (val) => currency === 'MXN' ? val : val / fxRate;
    
    const data = weeklyData.map((week, idx) => ({
      'Semana': week.label || `Sem ${idx + 1}`,
      'Fecha Inicio': week.weekStart ? format(new Date(week.weekStart), 'dd/MM/yyyy') : '',
      'Saldo Inicial': convert(week.saldoInicial || (idx === 0 ? saldoInicial : 0)),
      'Ingresos': convert(week.ingresos?.total || 0),
      'Egresos': convert(week.egresos?.total || 0),
      'Flujo Neto': convert(week.flujoNeto || 0),
      'Saldo Final': convert(week.saldoFinal || 0)
    }));

    return exportToExcel(data, `Proyecciones_${currency}`, 'Proyecciones');
  } catch (error) {
    console.error('Error exporting projections:', error);
    return false;
  }
};

export const exportFxRates = (rates) => {
  const data = rates.map(r => ({
    'Fecha': r.fecha_vigencia ? format(new Date(r.fecha_vigencia), 'dd/MM/yyyy HH:mm') : '',
    'Moneda': r.moneda_cotizada || r.moneda_origen || '',
    'Tipo de Cambio (MXN)': r.tipo_cambio || r.tasa || 0,
    'Fuente': r.fuente || 'manual'
  }));

  return exportToExcel(data, 'Tipos_Cambio', 'TC');
};

export const exportReports = (weeks) => {
  const data = weeks.map(w => ({
    'Semana': `S${w.numero_semana}`,
    'Año': w.año || '',
    'Fecha Inicio': w.fecha_inicio ? format(new Date(w.fecha_inicio), 'dd/MM/yyyy') : '',
    'Fecha Fin': w.fecha_fin ? format(new Date(w.fecha_fin), 'dd/MM/yyyy') : '',
    'Saldo Inicial': w.saldo_inicial || 0,
    'Ingresos Reales': w.total_ingresos_reales || 0,
    'Egresos Reales': w.total_egresos_reales || 0,
    'Ingresos Proyectados': w.total_ingresos_proyectados || 0,
    'Egresos Proyectados': w.total_egresos_proyectados || 0,
    'Saldo Final Real': w.saldo_final_real || 0,
    'Saldo Final Proyectado': w.saldo_final_proyectado || 0
  }));

  return exportToExcel(data, 'Reporte_Cashflow', 'Cashflow');
};
