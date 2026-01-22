"""CFDI XML Parser service"""
from typing import Dict, Any
from lxml import etree
from fastapi import HTTPException


def parse_cfdi_xml(xml_content: str) -> Dict[str, Any]:
    """Parse a CFDI XML and extract relevant data"""
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
        ns = {
            'cfdi': 'http://www.sat.gob.mx/cfd/4', 
            'cfdi3': 'http://www.sat.gob.mx/cfd/3',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
            'nomina12': 'http://www.sat.gob.mx/nomina12'
        }
        
        # Detect CFDI version (3.3 or 4.0)
        cfdi_ns = 'cfdi' if root.tag.startswith('{http://www.sat.gob.mx/cfd/4}') else 'cfdi3'
        if cfdi_ns == 'cfdi3':
            ns['cfdi'] = 'http://www.sat.gob.mx/cfd/3'
        
        timbre = root.find('.//tfd:TimbreFiscalDigital', ns)
        uuid = timbre.get('UUID') if timbre is not None else None
        fecha_timbrado = timbre.get('FechaTimbrado') if timbre is not None else None
        
        emisor = root.find('cfdi:Emisor', ns)
        receptor = root.find('cfdi:Receptor', ns)
        
        # Map SAT codes to enum values
        tipo_comprobante_map = {
            'i': 'ingreso',
            'e': 'egreso', 
            'p': 'pago',
            'n': 'nota_credito',
            't': 'ingreso'  # Traslado -> treat as ingreso
        }
        tipo_raw = root.get('TipoDeComprobante', 'I').lower()
        tipo_cfdi = tipo_comprobante_map.get(tipo_raw, 'ingreso')
        
        # Extract MetodoPago, FormaPago and other fields from XML
        metodo_pago = root.get('MetodoPago', '')  # PUE or PPD
        forma_pago = root.get('FormaPago', '')    # 01, 02, 03, etc.
        uso_cfdi = receptor.get('UsoCFDI', '') if receptor is not None else ''
        descuento = float(root.get('Descuento', 0) or 0)
        
        # Extract tax details from Impuestos node
        impuestos_node = root.find('cfdi:Impuestos', ns)
        total_impuestos_trasladados = float(impuestos_node.get('TotalImpuestosTrasladados', 0) or 0) if impuestos_node is not None else 0
        total_impuestos_retenidos = float(impuestos_node.get('TotalImpuestosRetenidos', 0) or 0) if impuestos_node is not None else 0
        
        # Extract individual tax amounts
        iva_trasladado = 0
        isr_retenido = 0
        iva_retenido = 0
        ieps = 0
        
        if impuestos_node is not None:
            # Traslados (IVA, IEPS)
            traslados = impuestos_node.find('cfdi:Traslados', ns)
            if traslados is not None:
                for traslado in traslados.findall('cfdi:Traslado', ns):
                    impuesto = traslado.get('Impuesto', '')
                    importe = float(traslado.get('Importe', 0) or 0)
                    if impuesto == '002':  # IVA
                        iva_trasladado += importe
                    elif impuesto == '003':  # IEPS
                        ieps += importe
            
            # Retenciones (ISR, IVA)
            retenciones = impuestos_node.find('cfdi:Retenciones', ns)
            if retenciones is not None:
                for retencion in retenciones.findall('cfdi:Retencion', ns):
                    impuesto = retencion.get('Impuesto', '')
                    importe = float(retencion.get('Importe', 0) or 0)
                    if impuesto == '001':  # ISR
                        isr_retenido += importe
                    elif impuesto == '002':  # IVA Retenido
                        iva_retenido += importe
        
        # Check for payroll (nómina) complement - ALWAYS treat as egreso
        nomina_element = root.find('.//nomina12:Nomina', ns)
        is_nomina = nomina_element is not None
        
        # Check for payroll keywords in concepts
        conceptos = root.findall('.//cfdi:Concepto', ns)
        conceptos_text = ' '.join([
            (c.get('Descripcion', '') + ' ' + c.get('ClaveProdServ', '')).lower() 
            for c in conceptos
        ])
        payroll_keywords = ['sueldo', 'salario', 'nómina', 'nomina', 'pago de nómina', 
                           'aguinaldo', 'liquidación', 'finiquito', '84111505']
        has_payroll_keywords = any(kw in conceptos_text for kw in payroll_keywords)
        
        return {
            'uuid': uuid,
            'tipo_cfdi': tipo_cfdi,
            'emisor_rfc': emisor.get('Rfc') if emisor is not None else '',
            'emisor_nombre': emisor.get('Nombre') if emisor is not None else '',
            'receptor_rfc': receptor.get('Rfc') if receptor is not None else '',
            'receptor_nombre': receptor.get('Nombre') if receptor is not None else '',
            'fecha_emision': root.get('Fecha'),
            'fecha_timbrado': fecha_timbrado,
            'moneda': root.get('Moneda', 'MXN'),
            'subtotal': float(root.get('SubTotal', 0)),
            'descuento': descuento,
            'total': float(root.get('Total', 0)),
            'metodo_pago': metodo_pago,
            'forma_pago': forma_pago,
            'uso_cfdi': uso_cfdi,
            'impuestos': total_impuestos_trasladados,
            'iva_trasladado': iva_trasladado,
            'isr_retenido': isr_retenido,
            'iva_retenido': iva_retenido,
            'ieps': ieps,
            'is_nomina': is_nomina or has_payroll_keywords
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parseando XML CFDI: {str(e)}")
