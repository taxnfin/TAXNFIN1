"""
CFDI SAT Integration Module
Handles authentication with SAT portal and CFDI downloads via RFC + CIEC
"""

import asyncio
import aiohttp
import logging
import uuid
import base64
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from cryptography.fernet import Fernet
from xml.etree import ElementTree as ET
import re

logger = logging.getLogger(__name__)

# SAT Portal URLs
SAT_LOGIN_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/Login.aspx"
SAT_CONSULTA_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaReceptor.aspx"
SAT_EMISOR_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaEmisor.aspx"

# Encryption key for credentials (should be in .env in production)
def get_encryption_key():
    key = os.environ.get('SAT_ENCRYPTION_KEY')
    if not key:
        # Generate and store a new key if not exists
        key = Fernet.generate_key().decode()
        logger.warning("SAT_ENCRYPTION_KEY not found, using generated key. Set this in .env for production!")
    return key.encode() if isinstance(key, str) else key


class SATCredentialManager:
    """Manages encrypted storage and retrieval of SAT credentials"""
    
    def __init__(self, db):
        self.db = db
        self.fernet = Fernet(get_encryption_key())
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    async def save_credentials(self, company_id: str, rfc: str, ciec: str) -> Dict:
        """Save encrypted SAT credentials for a company"""
        encrypted_ciec = self.encrypt(ciec)
        
        credential_doc = {
            'id': str(uuid.uuid4()),
            'company_id': company_id,
            'rfc': rfc.upper().strip(),
            'ciec_encrypted': encrypted_ciec,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'last_sync': None,
            'status': 'active'
        }
        
        # Upsert - update if exists, insert if new
        await self.db.sat_credentials.update_one(
            {'company_id': company_id},
            {'$set': credential_doc},
            upsert=True
        )
        
        return {
            'id': credential_doc['id'],
            'rfc': rfc,
            'status': 'configured',
            'message': 'Credenciales SAT guardadas correctamente'
        }
    
    async def get_credentials(self, company_id: str) -> Optional[Dict]:
        """Get decrypted SAT credentials for a company"""
        cred = await self.db.sat_credentials.find_one(
            {'company_id': company_id, 'status': 'active'},
            {'_id': 0}
        )
        
        if not cred:
            return None
        
        try:
            decrypted_ciec = self.decrypt(cred['ciec_encrypted'])
            return {
                'rfc': cred['rfc'],
                'ciec': decrypted_ciec,
                'last_sync': cred.get('last_sync'),
                'status': cred['status']
            }
        except Exception as e:
            logger.error(f"Error decrypting credentials: {e}")
            return None
    
    async def delete_credentials(self, company_id: str) -> bool:
        """Delete SAT credentials for a company"""
        result = await self.db.sat_credentials.delete_one({'company_id': company_id})
        return result.deleted_count > 0
    
    async def update_last_sync(self, company_id: str):
        """Update last sync timestamp"""
        await self.db.sat_credentials.update_one(
            {'company_id': company_id},
            {'$set': {'last_sync': datetime.utcnow()}}
        )


class SATPortalClient:
    """Client for interacting with SAT CFDI portal"""
    
    def __init__(self):
        self.session = None
        self.logged_in = False
        self.cookies = {}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-MX,es;q=0.8,en-US;q=0.5,en;q=0.3',
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def login(self, rfc: str, ciec: str) -> Dict:
        """
        Login to SAT portal with RFC and CIEC
        Returns session info if successful
        """
        try:
            # First, get the login page to extract tokens
            async with self.session.get(SAT_LOGIN_URL) as response:
                if response.status != 200:
                    return {'success': False, 'error': 'No se pudo acceder al portal SAT'}
                
                html = await response.text()
                
                # Extract __VIEWSTATE and other hidden fields
                viewstate = self._extract_field(html, '__VIEWSTATE')
                viewstate_gen = self._extract_field(html, '__VIEWSTATEGENERATOR')
                event_validation = self._extract_field(html, '__EVENTVALIDATION')
            
            # Prepare login data
            login_data = {
                '__VIEWSTATE': viewstate,
                '__VIEWSTATEGENERATOR': viewstate_gen,
                '__EVENTVALIDATION': event_validation,
                'ctl00$MainContent$TxtRFC': rfc,
                'ctl00$MainContent$TxtCiec': ciec,
                'ctl00$MainContent$BtnBuscar': 'Enviar'
            }
            
            # Submit login
            async with self.session.post(SAT_LOGIN_URL, data=login_data) as response:
                result_html = await response.text()
                
                # Check for successful login
                if 'ConsultaReceptor' in str(response.url) or 'Bienvenido' in result_html:
                    self.logged_in = True
                    self.cookies = {str(k): str(v) for k, v in self.session.cookie_jar.filter_cookies(SAT_LOGIN_URL).items()}
                    return {
                        'success': True,
                        'message': 'Autenticación exitosa con SAT',
                        'rfc': rfc
                    }
                elif 'Error' in result_html or 'incorrecto' in result_html.lower():
                    return {
                        'success': False,
                        'error': 'RFC o CIEC incorrectos'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Error de autenticación desconocido'
                    }
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error during SAT login: {e}")
            return {'success': False, 'error': f'Error de conexión: {str(e)}'}
        except Exception as e:
            logger.error(f"Error during SAT login: {e}")
            return {'success': False, 'error': f'Error inesperado: {str(e)}'}
    
    def _extract_field(self, html: str, field_name: str) -> str:
        """Extract hidden field value from HTML"""
        pattern = f'id="{field_name}" value="([^"]*)"'
        match = re.search(pattern, html)
        return match.group(1) if match else ''
    
    async def download_cfdi_recibidos(
        self, 
        fecha_inicio: datetime, 
        fecha_fin: datetime,
        tipo_comprobante: str = 'todos'  # ingreso, egreso, pago, todos
    ) -> List[Dict]:
        """
        Download CFDIs recibidos (received) from SAT portal
        """
        if not self.logged_in:
            return []
        
        try:
            # Navigate to consulta receptor page
            async with self.session.get(SAT_CONSULTA_URL) as response:
                html = await response.text()
                viewstate = self._extract_field(html, '__VIEWSTATE')
                viewstate_gen = self._extract_field(html, '__VIEWSTATEGENERATOR')
                event_validation = self._extract_field(html, '__EVENTVALIDATION')
            
            # Prepare search parameters
            tipo_map = {
                'todos': '-1',
                'ingreso': 'I',
                'egreso': 'E', 
                'pago': 'P',
                'nomina': 'N',
                'traslado': 'T'
            }
            
            search_data = {
                '__VIEWSTATE': viewstate,
                '__VIEWSTATEGENERATOR': viewstate_gen,
                '__EVENTVALIDATION': event_validation,
                'ctl00$MainContent$TxtFechaInicial': fecha_inicio.strftime('%d/%m/%Y'),
                'ctl00$MainContent$TxtFechaFinal': fecha_fin.strftime('%d/%m/%Y'),
                'ctl00$MainContent$DdlTipoComprobante': tipo_map.get(tipo_comprobante, '-1'),
                'ctl00$MainContent$BtnBuscar': 'Buscar CFDI'
            }
            
            # Execute search
            async with self.session.post(SAT_CONSULTA_URL, data=search_data) as response:
                result_html = await response.text()
                
                # Parse results - this would need to be adapted based on actual SAT response
                cfdis = self._parse_cfdi_list(result_html)
                return cfdis
                
        except Exception as e:
            logger.error(f"Error downloading CFDIs recibidos: {e}")
            return []
    
    async def download_cfdi_emitidos(
        self,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = 'todos'
    ) -> List[Dict]:
        """
        Download CFDIs emitidos (issued) from SAT portal
        """
        if not self.logged_in:
            return []
        
        try:
            # Navigate to consulta emisor page
            async with self.session.get(SAT_EMISOR_URL) as response:
                html = await response.text()
                viewstate = self._extract_field(html, '__VIEWSTATE')
                viewstate_gen = self._extract_field(html, '__VIEWSTATEGENERATOR')
                event_validation = self._extract_field(html, '__EVENTVALIDATION')
            
            tipo_map = {
                'todos': '-1',
                'ingreso': 'I',
                'egreso': 'E',
                'pago': 'P',
                'nomina': 'N',
                'traslado': 'T'
            }
            
            search_data = {
                '__VIEWSTATE': viewstate,
                '__VIEWSTATEGENERATOR': viewstate_gen,
                '__EVENTVALIDATION': event_validation,
                'ctl00$MainContent$TxtFechaInicial': fecha_inicio.strftime('%d/%m/%Y'),
                'ctl00$MainContent$TxtFechaFinal': fecha_fin.strftime('%d/%m/%Y'),
                'ctl00$MainContent$DdlTipoComprobante': tipo_map.get(tipo_comprobante, '-1'),
                'ctl00$MainContent$BtnBuscar': 'Buscar CFDI'
            }
            
            async with self.session.post(SAT_EMISOR_URL, data=search_data) as response:
                result_html = await response.text()
                cfdis = self._parse_cfdi_list(result_html)
                return cfdis
                
        except Exception as e:
            logger.error(f"Error downloading CFDIs emitidos: {e}")
            return []
    
    def _parse_cfdi_list(self, html: str) -> List[Dict]:
        """Parse CFDI list from SAT response HTML"""
        cfdis = []
        
        # This is a simplified parser - actual implementation would need
        # to handle the specific HTML structure from SAT
        
        # Look for table rows with CFDI data
        uuid_pattern = r'([a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})'
        uuids = re.findall(uuid_pattern, html)
        
        for uuid_found in set(uuids):
            cfdis.append({
                'uuid': uuid_found,
                'source': 'sat_portal'
            })
        
        return cfdis
    
    async def download_xml(self, uuid: str) -> Optional[str]:
        """
        Download individual CFDI XML by UUID
        """
        if not self.logged_in:
            return None
        
        try:
            download_url = f"https://portalcfdi.facturaelectronica.sat.gob.mx/RecuperaCfdi.aspx?uuid={uuid}"
            
            async with self.session.get(download_url) as response:
                if response.status == 200:
                    xml_content = await response.text()
                    if '<?xml' in xml_content or '<cfdi:Comprobante' in xml_content:
                        return xml_content
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading XML for {uuid}: {e}")
            return None


class CFDIParser:
    """Parser for CFDI XML documents"""
    
    CFDI_NS = {
        'cfdi': 'http://www.sat.gob.mx/cfd/4',
        'cfdi3': 'http://www.sat.gob.mx/cfd/3',
        'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
    }
    
    @classmethod
    def parse_xml(cls, xml_string: str) -> Optional[Dict]:
        """
        Parse CFDI XML and extract key information
        """
        try:
            # Remove BOM if present
            xml_string = xml_string.strip()
            if xml_string.startswith('\ufeff'):
                xml_string = xml_string[1:]
            
            root = ET.fromstring(xml_string.encode('utf-8'))
            
            # Detect version (3.3 or 4.0)
            version = root.get('Version', root.get('version', '4.0'))
            ns = cls.CFDI_NS['cfdi'] if version.startswith('4') else cls.CFDI_NS['cfdi3']
            
            # Extract basic info
            cfdi_data = {
                'version': version,
                'serie': root.get('Serie', ''),
                'folio': root.get('Folio', ''),
                'fecha_emision': root.get('Fecha'),
                'forma_pago': root.get('FormaPago', ''),
                'metodo_pago': root.get('MetodoPago', ''),
                'moneda': root.get('Moneda', 'MXN'),
                'tipo_cambio': float(root.get('TipoCambio', '1')),
                'tipo_comprobante': root.get('TipoDeComprobante', ''),
                'subtotal': float(root.get('SubTotal', '0')),
                'descuento': float(root.get('Descuento', '0')),
                'total': float(root.get('Total', '0')),
            }
            
            # Extract Emisor
            emisor = root.find('.//cfdi:Emisor', {'cfdi': ns}) or root.find('.//{%s}Emisor' % ns)
            if emisor is not None:
                cfdi_data['emisor_rfc'] = emisor.get('Rfc', '')
                cfdi_data['emisor_nombre'] = emisor.get('Nombre', '')
                cfdi_data['regimen_fiscal'] = emisor.get('RegimenFiscal', '')
            
            # Extract Receptor
            receptor = root.find('.//cfdi:Receptor', {'cfdi': ns}) or root.find('.//{%s}Receptor' % ns)
            if receptor is not None:
                cfdi_data['receptor_rfc'] = receptor.get('Rfc', '')
                cfdi_data['receptor_nombre'] = receptor.get('Nombre', '')
                cfdi_data['uso_cfdi'] = receptor.get('UsoCFDI', '')
            
            # Extract Timbre Fiscal Digital (UUID)
            tfd = root.find('.//tfd:TimbreFiscalDigital', cls.CFDI_NS)
            if tfd is not None:
                cfdi_data['uuid'] = tfd.get('UUID', '')
                cfdi_data['fecha_timbrado'] = tfd.get('FechaTimbrado', '')
                cfdi_data['sello_cfd'] = tfd.get('SelloCFD', '')[:50] if tfd.get('SelloCFD') else ''
                cfdi_data['sello_sat'] = tfd.get('SelloSAT', '')[:50] if tfd.get('SelloSAT') else ''
            
            # Extract Impuestos (taxes)
            impuestos = root.find('.//cfdi:Impuestos', {'cfdi': ns}) or root.find('.//{%s}Impuestos' % ns)
            if impuestos is not None:
                cfdi_data['total_impuestos_trasladados'] = float(impuestos.get('TotalImpuestosTrasladados', '0'))
                cfdi_data['total_impuestos_retenidos'] = float(impuestos.get('TotalImpuestosRetenidos', '0'))
            
            # Determine tipo_cfdi based on TipoDeComprobante
            tipo_map = {'I': 'ingreso', 'E': 'egreso', 'P': 'pago', 'N': 'nomina', 'T': 'traslado'}
            cfdi_data['tipo_cfdi'] = tipo_map.get(cfdi_data['tipo_comprobante'], 'otro')
            
            return cfdi_data
            
        except ET.ParseError as e:
            logger.error(f"XML Parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing CFDI: {e}")
            return None


class SATSyncService:
    """Service for syncing CFDIs from SAT to database"""
    
    def __init__(self, db):
        self.db = db
        self.credential_manager = SATCredentialManager(db)
    
    async def sync_cfdis(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = 'todos',
        incluir_emitidos: bool = True,
        incluir_recibidos: bool = True
    ) -> Dict:
        """
        Sync CFDIs from SAT for a company
        """
        # Get credentials
        credentials = await self.credential_manager.get_credentials(company_id)
        if not credentials:
            return {
                'success': False,
                'error': 'No hay credenciales SAT configuradas para esta empresa'
            }
        
        results = {
            'success': True,
            'emitidos': {'downloaded': 0, 'new': 0, 'errors': 0},
            'recibidos': {'downloaded': 0, 'new': 0, 'errors': 0},
            'total_new': 0,
            'errors': []
        }
        
        async with SATPortalClient() as client:
            # Login
            login_result = await client.login(credentials['rfc'], credentials['ciec'])
            if not login_result['success']:
                return {
                    'success': False,
                    'error': login_result.get('error', 'Error de autenticación')
                }
            
            # Download emitidos
            if incluir_emitidos:
                emitidos = await client.download_cfdi_emitidos(
                    fecha_inicio, fecha_fin, tipo_comprobante
                )
                results['emitidos']['downloaded'] = len(emitidos)
                
                for cfdi_info in emitidos:
                    try:
                        saved = await self._save_cfdi(
                            client, cfdi_info['uuid'], company_id, 'emitido'
                        )
                        if saved:
                            results['emitidos']['new'] += 1
                    except Exception as e:
                        results['emitidos']['errors'] += 1
                        results['errors'].append(str(e))
            
            # Download recibidos
            if incluir_recibidos:
                recibidos = await client.download_cfdi_recibidos(
                    fecha_inicio, fecha_fin, tipo_comprobante
                )
                results['recibidos']['downloaded'] = len(recibidos)
                
                for cfdi_info in recibidos:
                    try:
                        saved = await self._save_cfdi(
                            client, cfdi_info['uuid'], company_id, 'recibido'
                        )
                        if saved:
                            results['recibidos']['new'] += 1
                    except Exception as e:
                        results['recibidos']['errors'] += 1
                        results['errors'].append(str(e))
        
        results['total_new'] = results['emitidos']['new'] + results['recibidos']['new']
        
        # Update last sync timestamp
        await self.credential_manager.update_last_sync(company_id)
        
        return results
    
    async def _save_cfdi(
        self, 
        client: SATPortalClient, 
        uuid: str, 
        company_id: str,
        origen: str
    ) -> bool:
        """Save individual CFDI to database"""
        
        # Check if already exists
        existing = await self.db.cfdis.find_one({
            'uuid': uuid.upper(),
            'company_id': company_id
        })
        
        if existing:
            return False  # Already exists
        
        # Download XML
        xml_content = await client.download_xml(uuid)
        if not xml_content:
            raise Exception(f"Could not download XML for {uuid}")
        
        # Parse XML
        cfdi_data = CFDIParser.parse_xml(xml_content)
        if not cfdi_data:
            raise Exception(f"Could not parse XML for {uuid}")
        
        # Prepare document for database
        doc = {
            'id': str(uuid.uuid4()),
            'company_id': company_id,
            'uuid': cfdi_data.get('uuid', uuid).upper(),
            'version': cfdi_data.get('version'),
            'serie': cfdi_data.get('serie'),
            'folio': cfdi_data.get('folio'),
            'fecha_emision': datetime.fromisoformat(cfdi_data['fecha_emision'].replace('T', ' ')) if cfdi_data.get('fecha_emision') else None,
            'fecha_timbrado': datetime.fromisoformat(cfdi_data['fecha_timbrado'].replace('T', ' ')) if cfdi_data.get('fecha_timbrado') else None,
            'emisor_rfc': cfdi_data.get('emisor_rfc'),
            'emisor_nombre': cfdi_data.get('emisor_nombre'),
            'receptor_rfc': cfdi_data.get('receptor_rfc'),
            'receptor_nombre': cfdi_data.get('receptor_nombre'),
            'tipo_cfdi': cfdi_data.get('tipo_cfdi'),
            'tipo_comprobante': cfdi_data.get('tipo_comprobante'),
            'uso_cfdi': cfdi_data.get('uso_cfdi'),
            'moneda': cfdi_data.get('moneda', 'MXN'),
            'tipo_cambio': cfdi_data.get('tipo_cambio', 1),
            'subtotal': cfdi_data.get('subtotal', 0),
            'descuento': cfdi_data.get('descuento', 0),
            'total': cfdi_data.get('total', 0),
            'total_impuestos_trasladados': cfdi_data.get('total_impuestos_trasladados', 0),
            'total_impuestos_retenidos': cfdi_data.get('total_impuestos_retenidos', 0),
            'forma_pago': cfdi_data.get('forma_pago'),
            'metodo_pago': cfdi_data.get('metodo_pago'),
            'regimen_fiscal': cfdi_data.get('regimen_fiscal'),
            'xml_original': xml_content,
            'origen': origen,  # 'emitido' or 'recibido'
            'source': 'sat_sync',
            'estado_conciliacion': 'pendiente',
            'monto_pagado': 0,
            'monto_cobrado': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        await self.db.cfdis.insert_one(doc)
        return True
    
    async def validate_credentials(self, rfc: str, ciec: str) -> Dict:
        """
        Validate SAT credentials without saving them
        """
        async with SATPortalClient() as client:
            result = await client.login(rfc, ciec)
            return result
