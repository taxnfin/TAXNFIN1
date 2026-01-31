"""
CFDI SAT Integration Module
Handles authentication with SAT portal and CFDI downloads via RFC + CIEC
Uses Selenium for web scraping the SAT portal
"""

import asyncio
import logging
import uuid as uuid_module
import base64
import os
import tempfile
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from cryptography.fernet import Fernet
from xml.etree import ElementTree as ET
import re

logger = logging.getLogger(__name__)

# SAT Portal URLs (2025 updated)
SAT_LOGIN_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/"
SAT_CONSULTA_RECEPTOR_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaReceptor.aspx"
SAT_CONSULTA_EMISOR_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaEmisor.aspx"


def get_encryption_key():
    """Get or generate encryption key for credentials"""
    key = os.environ.get('SAT_ENCRYPTION_KEY')
    if not key:
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
            'id': str(uuid_module.uuid4()),
            'company_id': company_id,
            'rfc': rfc.upper().strip(),
            'ciec_encrypted': encrypted_ciec,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
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
    
    async def get_credential_status(self, company_id: str) -> Optional[Dict]:
        """Get SAT credential status without decrypting CIEC"""
        cred = await self.db.sat_credentials.find_one(
            {'company_id': company_id},
            {'_id': 0, 'ciec_encrypted': 0}
        )
        return cred
    
    async def delete_credentials(self, company_id: str) -> bool:
        """Delete SAT credentials for a company"""
        result = await self.db.sat_credentials.delete_one({'company_id': company_id})
        return result.deleted_count > 0
    
    async def update_last_sync(self, company_id: str, sync_result: Dict = None):
        """Update last sync timestamp and result"""
        update_data = {
            'last_sync': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        if sync_result:
            update_data['last_sync_result'] = sync_result
        
        await self.db.sat_credentials.update_one(
            {'company_id': company_id},
            {'$set': update_data}
        )


class SATPortalClient:
    """
    Client for interacting with SAT CFDI portal using Selenium
    Handles authentication and CFDI downloads
    """
    
    def __init__(self):
        self.driver = None
        self.logged_in = False
        self.download_dir = None
        self._chrome_available = None
    
    def _check_chrome_available(self):
        """Check if Chrome/Chromium is available"""
        if self._chrome_available is not None:
            return self._chrome_available
        
        import shutil
        chrome_paths = ['google-chrome', 'chromium', 'chromium-browser', 'chrome']
        for chrome in chrome_paths:
            if shutil.which(chrome):
                self._chrome_available = True
                return True
        self._chrome_available = False
        return False
    
    def _get_chrome_options(self):
        """Configure Chrome options for headless scraping"""
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Configure download directory
        self.download_dir = tempfile.mkdtemp()
        prefs = {
            'download.default_directory': self.download_dir,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': True
        }
        options.add_experimental_option('prefs', prefs)
        
        return options
    
    def _init_driver(self):
        """Initialize Selenium WebDriver"""
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Check if Chrome is available
        if not self._check_chrome_available():
            logger.warning("Chrome/Chromium not found on system")
            return False
        
        try:
            options = self._get_chrome_options()
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            logger.error(f"Error initializing WebDriver: {e}")
            return False
    
    def _close_driver(self):
        """Close WebDriver and cleanup"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        self.logged_in = False
    
    async def login(self, rfc: str, ciec: str) -> Dict:
        """
        Login to SAT portal with RFC and CIEC
        Returns session info if successful
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        try:
            if not self._init_driver():
                return {'success': False, 'error': 'No se pudo inicializar el navegador'}
            
            logger.info(f"Attempting SAT login for RFC: {rfc}")
            
            # Navigate to login page
            self.driver.get(SAT_LOGIN_URL)
            await asyncio.sleep(2)
            
            wait = WebDriverWait(self.driver, 20)
            
            # Try to find and fill RFC field
            try:
                # Common selectors for SAT login page
                rfc_selectors = [
                    (By.ID, 'rfc'),
                    (By.NAME, 'Rfc'),
                    (By.ID, 'txtRfc'),
                    (By.XPATH, "//input[contains(@id, 'RFC') or contains(@name, 'rfc')]"),
                    (By.CSS_SELECTOR, "input[placeholder*='RFC']")
                ]
                
                rfc_input = None
                for selector_type, selector_value in rfc_selectors:
                    try:
                        rfc_input = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                        if rfc_input:
                            break
                    except:
                        continue
                
                if not rfc_input:
                    # Take screenshot for debugging
                    screenshot_path = f"/tmp/sat_login_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.error(f"Could not find RFC input. Screenshot saved to {screenshot_path}")
                    return {'success': False, 'error': 'No se pudo encontrar el campo RFC en el portal'}
                
                rfc_input.clear()
                rfc_input.send_keys(rfc)
                
            except Exception as e:
                logger.error(f"Error filling RFC: {e}")
                return {'success': False, 'error': f'Error ingresando RFC: {str(e)}'}
            
            # Try to find and fill CIEC/password field
            try:
                ciec_selectors = [
                    (By.ID, 'password'),
                    (By.NAME, 'Password'),
                    (By.ID, 'txtContrasena'),
                    (By.XPATH, "//input[@type='password']"),
                    (By.CSS_SELECTOR, "input[type='password']")
                ]
                
                ciec_input = None
                for selector_type, selector_value in ciec_selectors:
                    try:
                        ciec_input = self.driver.find_element(selector_type, selector_value)
                        if ciec_input:
                            break
                    except:
                        continue
                
                if not ciec_input:
                    return {'success': False, 'error': 'No se pudo encontrar el campo CIEC/Contraseña'}
                
                ciec_input.clear()
                ciec_input.send_keys(ciec)
                
            except Exception as e:
                logger.error(f"Error filling CIEC: {e}")
                return {'success': False, 'error': f'Error ingresando CIEC: {str(e)}'}
            
            # Find and click submit button
            try:
                submit_selectors = [
                    (By.ID, 'submit'),
                    (By.XPATH, "//input[@type='submit']"),
                    (By.XPATH, "//button[@type='submit']"),
                    (By.XPATH, "//input[@value='Enviar' or @value='Aceptar' or @value='Ingresar']"),
                    (By.CSS_SELECTOR, "button.submit, input.submit")
                ]
                
                submit_btn = None
                for selector_type, selector_value in submit_selectors:
                    try:
                        submit_btn = self.driver.find_element(selector_type, selector_value)
                        if submit_btn:
                            break
                    except:
                        continue
                
                if submit_btn:
                    submit_btn.click()
                else:
                    return {'success': False, 'error': 'No se pudo encontrar el botón de enviar'}
                    
            except Exception as e:
                logger.error(f"Error clicking submit: {e}")
                return {'success': False, 'error': f'Error al enviar formulario: {str(e)}'}
            
            # Wait for login result
            await asyncio.sleep(3)
            
            # Check if login was successful
            current_url = self.driver.current_url.lower()
            page_source = self.driver.page_source.lower()
            
            if 'consulta' in current_url or 'receptor' in current_url or 'emisor' in current_url:
                self.logged_in = True
                logger.info("SAT login successful")
                return {
                    'success': True,
                    'message': 'Autenticación exitosa con SAT',
                    'rfc': rfc
                }
            elif 'error' in page_source or 'incorrecto' in page_source or 'invalido' in page_source:
                return {
                    'success': False,
                    'error': 'RFC o CIEC incorrectos. Verifique sus credenciales.'
                }
            else:
                # Check for CAPTCHA or other challenges
                if 'captcha' in page_source:
                    return {
                        'success': False,
                        'error': 'El portal SAT requiere CAPTCHA. Intente más tarde o desde su navegador.'
                    }
                
                # Save screenshot for debugging
                screenshot_path = f"/tmp/sat_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.warning(f"Unknown login result. Screenshot saved to {screenshot_path}")
                
                return {
                    'success': False,
                    'error': 'No se pudo verificar el resultado del login. El portal podría estar en mantenimiento.'
                }
                
        except Exception as e:
            logger.error(f"Error during SAT login: {e}")
            return {'success': False, 'error': f'Error inesperado: {str(e)}'}
    
    async def download_cfdis(
        self,
        tipo: str,  # 'recibidos' or 'emitidos'
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = 'todos'
    ) -> List[Dict]:
        """
        Download CFDIs from SAT portal
        Returns list of CFDI info dictionaries
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions as EC
        
        if not self.logged_in:
            return []
        
        cfdis_found = []
        
        try:
            # Navigate to appropriate consultation page
            if tipo == 'recibidos':
                self.driver.get(SAT_CONSULTA_RECEPTOR_URL)
            else:
                self.driver.get(SAT_CONSULTA_EMISOR_URL)
            
            await asyncio.sleep(2)
            wait = WebDriverWait(self.driver, 15)
            
            # Fill date fields
            try:
                # Date start field
                fecha_inicio_selectors = [
                    (By.ID, 'ctl00_MainContent_CldFechaInicial2_Calendario_text'),
                    (By.ID, 'txtFechaInicio'),
                    (By.XPATH, "//input[contains(@id, 'FechaInicial') or contains(@id, 'fechaInicio')]")
                ]
                
                fecha_input = None
                for sel_type, sel_value in fecha_inicio_selectors:
                    try:
                        fecha_input = self.driver.find_element(sel_type, sel_value)
                        if fecha_input:
                            break
                    except:
                        continue
                
                if fecha_input:
                    fecha_input.clear()
                    fecha_input.send_keys(fecha_inicio.strftime('%d/%m/%Y'))
                
                # Date end field
                fecha_fin_selectors = [
                    (By.ID, 'ctl00_MainContent_CldFechaFinal2_Calendario_text'),
                    (By.ID, 'txtFechaFin'),
                    (By.XPATH, "//input[contains(@id, 'FechaFinal') or contains(@id, 'fechaFin')]")
                ]
                
                fecha_fin_input = None
                for sel_type, sel_value in fecha_fin_selectors:
                    try:
                        fecha_fin_input = self.driver.find_element(sel_type, sel_value)
                        if fecha_fin_input:
                            break
                    except:
                        continue
                
                if fecha_fin_input:
                    fecha_fin_input.clear()
                    fecha_fin_input.send_keys(fecha_fin.strftime('%d/%m/%Y'))
                    
            except Exception as e:
                logger.warning(f"Error setting dates: {e}")
            
            # Select comprobante type if not 'todos'
            if tipo_comprobante != 'todos':
                try:
                    tipo_select = self.driver.find_element(By.XPATH, "//select[contains(@id, 'TipoComprobante')]")
                    select = Select(tipo_select)
                    
                    tipo_map = {
                        'ingreso': 'I',
                        'egreso': 'E',
                        'pago': 'P',
                        'nomina': 'N',
                        'traslado': 'T'
                    }
                    
                    if tipo_comprobante in tipo_map:
                        select.select_by_value(tipo_map[tipo_comprobante])
                except:
                    pass
            
            # Click search button
            try:
                search_selectors = [
                    (By.ID, 'ctl00_MainContent_BtnBusqueda'),
                    (By.XPATH, "//input[@value='Buscar CFDI']"),
                    (By.XPATH, "//button[contains(text(), 'Buscar')]")
                ]
                
                search_btn = None
                for sel_type, sel_value in search_selectors:
                    try:
                        search_btn = self.driver.find_element(sel_type, sel_value)
                        if search_btn:
                            break
                    except:
                        continue
                
                if search_btn:
                    search_btn.click()
                    await asyncio.sleep(3)
                    
            except Exception as e:
                logger.error(f"Error clicking search: {e}")
                return []
            
            # Parse results - look for UUIDs and download links
            page_source = self.driver.page_source
            
            # Extract UUIDs using regex pattern for CFDI UUIDs
            uuid_pattern = r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'
            uuids_found = set(re.findall(uuid_pattern, page_source))
            
            for cfdi_uuid in uuids_found:
                cfdis_found.append({
                    'uuid': cfdi_uuid.upper(),
                    'tipo': tipo,
                    'source': 'sat_portal'
                })
            
            logger.info(f"Found {len(cfdis_found)} CFDIs ({tipo})")
            
            # Try to download XMLs
            for cfdi_info in cfdis_found:
                try:
                    xml_content = await self._download_xml(cfdi_info['uuid'])
                    if xml_content:
                        cfdi_info['xml_content'] = xml_content
                except Exception as e:
                    logger.warning(f"Could not download XML for {cfdi_info['uuid']}: {e}")
            
            return cfdis_found
            
        except Exception as e:
            logger.error(f"Error downloading CFDIs: {e}")
            return cfdis_found
    
    async def _download_xml(self, uuid: str) -> Optional[str]:
        """Download individual CFDI XML by UUID"""
        from selenium.webdriver.common.by import By
        
        if not self.logged_in:
            return None
        
        try:
            # Try to find download link for this UUID
            download_selectors = [
                f"//a[contains(@href, '{uuid}') and contains(@href, 'xml')]",
                f"//a[contains(@onclick, '{uuid}')]",
                f"//img[contains(@onclick, '{uuid}')]/parent::a"
            ]
            
            for selector in download_selectors:
                try:
                    download_link = self.driver.find_element(By.XPATH, selector)
                    if download_link:
                        download_link.click()
                        await asyncio.sleep(2)
                        
                        # Check download directory for the file
                        if self.download_dir:
                            import glob
                            xml_files = glob.glob(f"{self.download_dir}/*.xml")
                            for xml_file in xml_files:
                                with open(xml_file, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    if uuid.upper() in content.upper():
                                        os.remove(xml_file)
                                        return content
                        break
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading XML for {uuid}: {e}")
            return None
    
    def close(self):
        """Close the browser and cleanup"""
        self._close_driver()
        if self.download_dir:
            import shutil
            try:
                shutil.rmtree(self.download_dir)
            except:
                pass


class CFDIParser:
    """Parser for CFDI XML documents"""
    
    CFDI_NS = {
        'cfdi': 'http://www.sat.gob.mx/cfd/4',
        'cfdi3': 'http://www.sat.gob.mx/cfd/3',
        'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
        'nomina12': 'http://www.sat.gob.mx/nomina12'
    }
    
    @classmethod
    def parse_xml(cls, xml_string: str) -> Optional[Dict]:
        """Parse CFDI XML and extract key information"""
        try:
            xml_string = xml_string.strip()
            if xml_string.startswith('\ufeff'):
                xml_string = xml_string[1:]
            
            root = ET.fromstring(xml_string.encode('utf-8'))
            
            # Detect version
            version = root.get('Version', root.get('version', '4.0'))
            ns = cls.CFDI_NS['cfdi'] if version.startswith('4') else cls.CFDI_NS['cfdi3']
            
            cfdi_data = {
                'version': version,
                'serie': root.get('Serie', ''),
                'folio': root.get('Folio', ''),
                'fecha_emision': root.get('Fecha'),
                'forma_pago': root.get('FormaPago', ''),
                'metodo_pago': root.get('MetodoPago', ''),
                'moneda': root.get('Moneda', 'MXN'),
                'tipo_cambio': float(root.get('TipoCambio', '1') or '1'),
                'tipo_comprobante': root.get('TipoDeComprobante', ''),
                'subtotal': float(root.get('SubTotal', '0') or '0'),
                'descuento': float(root.get('Descuento', '0') or '0'),
                'total': float(root.get('Total', '0') or '0'),
            }
            
            # Extract Emisor
            emisor = root.find(f'.//{{{ns}}}Emisor')
            if emisor is not None:
                cfdi_data['emisor_rfc'] = emisor.get('Rfc', '')
                cfdi_data['emisor_nombre'] = emisor.get('Nombre', '')
                cfdi_data['regimen_fiscal'] = emisor.get('RegimenFiscal', '')
            
            # Extract Receptor
            receptor = root.find(f'.//{{{ns}}}Receptor')
            if receptor is not None:
                cfdi_data['receptor_rfc'] = receptor.get('Rfc', '')
                cfdi_data['receptor_nombre'] = receptor.get('Nombre', '')
                cfdi_data['uso_cfdi'] = receptor.get('UsoCFDI', '')
            
            # Extract Timbre Fiscal Digital (UUID)
            for ns_prefix, ns_uri in cls.CFDI_NS.items():
                tfd = root.find(f'.//{{{ns_uri}}}TimbreFiscalDigital')
                if tfd is not None:
                    cfdi_data['uuid'] = tfd.get('UUID', '')
                    cfdi_data['fecha_timbrado'] = tfd.get('FechaTimbrado', '')
                    break
            
            # Extract Impuestos
            impuestos_ns = f'{{{ns}}}Impuestos'
            impuestos = root.find(f'.//{impuestos_ns}')
            if impuestos is not None:
                cfdi_data['total_impuestos_trasladados'] = float(impuestos.get('TotalImpuestosTrasladados', '0') or '0')
                cfdi_data['total_impuestos_retenidos'] = float(impuestos.get('TotalImpuestosRetenidos', '0') or '0')
            else:
                cfdi_data['total_impuestos_trasladados'] = 0
                cfdi_data['total_impuestos_retenidos'] = 0
            
            # Determine tipo_cfdi
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
    
    async def validate_credentials(self, rfc: str, ciec: str) -> Dict:
        """Validate SAT credentials without saving them"""
        client = SATPortalClient()
        try:
            result = await client.login(rfc, ciec)
            return result
        finally:
            client.close()
    
    async def sync_cfdis(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = 'todos',
        incluir_emitidos: bool = True,
        incluir_recibidos: bool = True
    ) -> Dict:
        """Sync CFDIs from SAT for a company"""
        
        # Get credentials
        credentials = await self.credential_manager.get_credentials(company_id)
        if not credentials:
            return {
                'success': False,
                'error': 'No hay credenciales SAT configuradas para esta empresa'
            }
        
        results = {
            'success': True,
            'emitidos': {'downloaded': 0, 'new': 0, 'updated': 0, 'errors': 0},
            'recibidos': {'downloaded': 0, 'new': 0, 'updated': 0, 'errors': 0},
            'total_new': 0,
            'total_updated': 0,
            'errors': [],
            'sync_date': datetime.now(timezone.utc).isoformat()
        }
        
        client = SATPortalClient()
        
        try:
            # Login
            login_result = await client.login(credentials['rfc'], credentials['ciec'])
            if not login_result['success']:
                return {
                    'success': False,
                    'error': login_result.get('error', 'Error de autenticación')
                }
            
            # Download recibidos
            if incluir_recibidos:
                recibidos = await client.download_cfdis(
                    'recibidos', fecha_inicio, fecha_fin, tipo_comprobante
                )
                results['recibidos']['downloaded'] = len(recibidos)
                
                for cfdi_info in recibidos:
                    try:
                        saved = await self._save_cfdi(cfdi_info, company_id, 'recibido')
                        if saved == 'new':
                            results['recibidos']['new'] += 1
                        elif saved == 'updated':
                            results['recibidos']['updated'] += 1
                    except Exception as e:
                        results['recibidos']['errors'] += 1
                        results['errors'].append(f"Recibido {cfdi_info.get('uuid', 'unknown')}: {str(e)}")
            
            # Download emitidos
            if incluir_emitidos:
                emitidos = await client.download_cfdis(
                    'emitidos', fecha_inicio, fecha_fin, tipo_comprobante
                )
                results['emitidos']['downloaded'] = len(emitidos)
                
                for cfdi_info in emitidos:
                    try:
                        saved = await self._save_cfdi(cfdi_info, company_id, 'emitido')
                        if saved == 'new':
                            results['emitidos']['new'] += 1
                        elif saved == 'updated':
                            results['emitidos']['updated'] += 1
                    except Exception as e:
                        results['emitidos']['errors'] += 1
                        results['errors'].append(f"Emitido {cfdi_info.get('uuid', 'unknown')}: {str(e)}")
            
            results['total_new'] = results['emitidos']['new'] + results['recibidos']['new']
            results['total_updated'] = results['emitidos']['updated'] + results['recibidos']['updated']
            
            # Update last sync
            await self.credential_manager.update_last_sync(company_id, {
                'total_new': results['total_new'],
                'total_updated': results['total_updated'],
                'errors_count': len(results['errors'])
            })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in SAT sync: {e}")
            return {
                'success': False,
                'error': f'Error durante la sincronización: {str(e)}'
            }
        finally:
            client.close()
    
    async def _save_cfdi(self, cfdi_info: Dict, company_id: str, origen: str) -> str:
        """Save individual CFDI to database. Returns 'new', 'updated', or 'exists'"""
        
        cfdi_uuid = cfdi_info.get('uuid', '').upper()
        if not cfdi_uuid:
            raise Exception("CFDI sin UUID")
        
        # Check if exists
        existing = await self.db.cfdis.find_one({
            'uuid': cfdi_uuid,
            'company_id': company_id
        }, {'_id': 0, 'id': 1})
        
        # Parse XML if available
        cfdi_data = None
        xml_content = cfdi_info.get('xml_content')
        if xml_content:
            cfdi_data = CFDIParser.parse_xml(xml_content)
        
        if existing:
            # Update with new data if we have XML
            if cfdi_data and xml_content:
                await self.db.cfdis.update_one(
                    {'id': existing['id']},
                    {'$set': {
                        'xml_original': xml_content,
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }}
                )
                return 'updated'
            return 'exists'
        
        # Create new CFDI record
        now = datetime.now(timezone.utc)
        
        doc = {
            'id': str(uuid_module.uuid4()),
            'company_id': company_id,
            'uuid': cfdi_uuid,
            'origen': origen,
            'source': 'sat_sync',
            'estado_conciliacion': 'pendiente',
            'monto_pagado': 0,
            'monto_cobrado': 0,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat()
        }
        
        # Add parsed data if available
        if cfdi_data:
            doc.update({
                'version': cfdi_data.get('version'),
                'serie': cfdi_data.get('serie'),
                'folio': cfdi_data.get('folio'),
                'fecha_emision': cfdi_data.get('fecha_emision'),
                'fecha_timbrado': cfdi_data.get('fecha_timbrado'),
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
                'impuestos': cfdi_data.get('total_impuestos_trasladados', 0),
                'forma_pago': cfdi_data.get('forma_pago'),
                'metodo_pago': cfdi_data.get('metodo_pago'),
                'regimen_fiscal': cfdi_data.get('regimen_fiscal'),
            })
            if xml_content:
                doc['xml_original'] = xml_content
        else:
            # Minimal record without XML data
            doc.update({
                'fecha_emision': now.isoformat(),
                'tipo_cfdi': 'ingreso' if origen == 'recibido' else 'egreso',
                'total': 0,
                'subtotal': 0,
                'moneda': 'MXN'
            })
        
        await self.db.cfdis.insert_one(doc)
        return 'new'
    
    async def get_sync_history(self, company_id: str, limit: int = 10) -> List[Dict]:
        """Get sync history for a company"""
        history = await self.db.sat_sync_history.find(
            {'company_id': company_id},
            {'_id': 0}
        ).sort('created_at', -1).limit(limit).to_list(limit)
        
        return history
