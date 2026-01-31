"""
SAT FIEL Integration Module - Using cfdiclient library
Handles authentication with SAT Web Services using FIEL (e.firma)
"""

import asyncio
import base64
import logging
import os
import uuid as uuid_module
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from io import BytesIO

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# Import cfdiclient library (official SAT CFDI client)
from cfdiclient import Fiel, Autenticacion, SolicitaDescargaRecibidos, SolicitaDescargaEmitidos, VerificaSolicitudDescarga, DescargaMasiva

logger = logging.getLogger(__name__)


class FIELManager:
    """Manages FIEL (e.firma) certificates using cfdiclient"""
    
    def __init__(self, cer_content: bytes, key_content: bytes, password: str):
        self.cer_content = cer_content
        self.key_content = key_content
        self.password = password
        self.rfc = None
        self.serial_number = None
        self.not_before = None
        self.not_after = None
        self.fiel = None  # cfdiclient Fiel object
        
        self._load_certificate()
        self._create_fiel()
    
    def _load_certificate(self):
        """Load and parse the .cer certificate"""
        try:
            cert = x509.load_der_x509_certificate(self.cer_content, default_backend())
            
            # Extract RFC from subject
            import re
            subject_str = str(cert.subject)
            match = re.search(r'([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})', subject_str.upper())
            if match:
                self.rfc = match.group(1)
            
            # Also try from serialNumber attribute
            if not self.rfc:
                for attr in cert.subject:
                    if attr.oid.dotted_string == '2.5.4.5':  # serialNumber
                        value = attr.value
                        if '/' in value:
                            self.rfc = value.split('/')[0].strip().upper()
                        else:
                            self.rfc = value.strip().upper()[:13]
                        break
            
            self.serial_number = format(cert.serial_number, 'X')
            self.not_before = cert.not_valid_before_utc
            self.not_after = cert.not_valid_after_utc
            
            logger.info(f"Certificate loaded: RFC={self.rfc}, Serial={self.serial_number[:16]}...")
            
        except Exception as e:
            logger.error(f"Error loading certificate: {e}")
            raise ValueError(f"Error al cargar el certificado .cer: {str(e)}")
    
    def _create_fiel(self):
        """Create cfdiclient Fiel object"""
        try:
            self.fiel = Fiel(self.cer_content, self.key_content, self.password)
            logger.info("FIEL object created successfully")
        except Exception as e:
            logger.error(f"Error creating FIEL: {e}")
            raise ValueError(f"Error al crear FIEL: {str(e)} - Verifique que la contraseña sea correcta")
    
    def is_valid(self) -> bool:
        """Check if the certificate is currently valid"""
        now = datetime.now(timezone.utc)
        return self.not_before <= now <= self.not_after
    
    def get_info(self) -> Dict:
        """Get certificate information"""
        return {
            'rfc': self.rfc,
            'serial_number': self.serial_number,
            'valid_from': self.not_before.isoformat() if self.not_before else None,
            'valid_to': self.not_after.isoformat() if self.not_after else None,
            'is_valid': self.is_valid()
        }


class SATWebService:
    """SAT SOAP Web Service client using cfdiclient"""
    
    def __init__(self, fiel_manager: FIELManager):
        self.fiel_manager = fiel_manager
        self.fiel = fiel_manager.fiel
        self.token = None
        self.token_created = None
    
    async def authenticate(self) -> Dict:
        """Authenticate with SAT using FIEL"""
        try:
            auth = Autenticacion(self.fiel)
            token = auth.obtener_token()
            
            if token:
                self.token = token
                self.token_created = datetime.now(timezone.utc)
                logger.info("SAT Authentication successful!")
                return {
                    'success': True,
                    'message': '¡Autenticación exitosa con el SAT!',
                    'rfc': self.fiel_manager.rfc,
                    'token_preview': token[:50] + '...' if len(token) > 50 else token
                }
            else:
                return {
                    'success': False,
                    'error': 'No se recibió token de autenticación del SAT'
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"SAT Authentication error: {error_msg}")
            
            # Parse common errors
            if '401' in error_msg or 'Unauthorized' in error_msg:
                return {'success': False, 'error': 'Credenciales FIEL inválidas o expiradas'}
            elif '300' in error_msg:
                return {'success': False, 'error': 'Usuario no válido en el SAT'}
            elif '301' in error_msg:
                return {'success': False, 'error': 'XML mal formado en la solicitud'}
            elif '302' in error_msg:
                return {'success': False, 'error': 'Sello mal formado'}
            elif '303' in error_msg:
                return {'success': False, 'error': 'Sello no corresponde al RFC'}
            elif '304' in error_msg:
                return {'success': False, 'error': 'Certificado revocado o inválido'}
            elif '305' in error_msg:
                return {'success': False, 'error': 'Certificado expirado'}
            elif 'timeout' in error_msg.lower():
                return {'success': False, 'error': 'Tiempo de espera agotado al conectar con SAT'}
            elif 'connection' in error_msg.lower():
                return {'success': False, 'error': 'Error de conexión con el servidor SAT'}
            else:
                return {'success': False, 'error': f'Error de autenticación: {error_msg}'}
    
    def _ensure_token(self) -> bool:
        """Ensure we have a valid token"""
        if not self.token:
            return False
        
        # Token is valid for ~5 minutes
        if self.token_created:
            elapsed = (datetime.now(timezone.utc) - self.token_created).total_seconds()
            if elapsed > 240:  # 4 minutes
                self.token = None
                return False
        
        return True
    
    async def solicitar_descarga_recibidos(
        self,
        fecha_inicio,
        fecha_fin,
        rfc_emisor: str = None,
        tipo_comprobante: str = None
    ) -> Dict:
        """Request download of received CFDIs"""
        
        if not self._ensure_token():
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            descarga = SolicitaDescargaRecibidos(self.fiel)
            
            # Format dates - handle both datetime and string
            if isinstance(fecha_inicio, str):
                fecha_inicio_str = fecha_inicio.split('T')[0] + 'T00:00:00'
            else:
                fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%dT00:00:00')
            
            if isinstance(fecha_fin, str):
                fecha_fin_str = fecha_fin.split('T')[0] + 'T23:59:59'
            else:
                fecha_fin_str = fecha_fin.strftime('%Y-%m-%dT23:59:59')
            
            # Make request
            if rfc_emisor:
                result = descarga.solicitar_descarga(
                    self.token,
                    self.fiel_manager.rfc,
                    fecha_inicio_str,
                    fecha_fin_str,
                    rfc_emisor=rfc_emisor,
                    tipo_comprobante=tipo_comprobante
                )
            else:
                result = descarga.solicitar_descarga(
                    self.token,
                    self.fiel_manager.rfc,
                    fecha_inicio_str,
                    fecha_fin_str,
                    tipo_comprobante=tipo_comprobante
                )
            
            # Parse result
            if result:
                cod_estatus = result.get('cod_estatus', '')
                mensaje = result.get('mensaje', '')
                id_solicitud = result.get('id_solicitud', '')
                
                success = cod_estatus == '5000'
                
                return {
                    'success': success,
                    'id_solicitud': id_solicitud,
                    'codigo': cod_estatus,
                    'mensaje': mensaje or ('Solicitud creada exitosamente' if success else self._parse_error_code(cod_estatus)),
                    'tipo': 'recibidos'
                }
            
            return {'success': False, 'error': 'Sin respuesta del SAT'}
            
        except Exception as e:
            logger.error(f"Error requesting download: {e}")
            return {'success': False, 'error': f'Error solicitando descarga: {str(e)}'}
    
    async def solicitar_descarga_emitidos(
        self,
        fecha_inicio,
        fecha_fin,
        rfc_receptor: str = None,
        tipo_comprobante: str = None
    ) -> Dict:
        """Request download of emitted CFDIs"""
        
        if not self._ensure_token():
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            descarga = SolicitaDescargaEmitidos(self.fiel)
            
            # Format dates - handle both datetime and string
            if isinstance(fecha_inicio, str):
                fecha_inicio_str = fecha_inicio.split('T')[0] + 'T00:00:00'
            else:
                fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%dT00:00:00')
            
            if isinstance(fecha_fin, str):
                fecha_fin_str = fecha_fin.split('T')[0] + 'T23:59:59'
            else:
                fecha_fin_str = fecha_fin.strftime('%Y-%m-%dT23:59:59')
            
            if rfc_receptor:
                result = descarga.solicitar_descarga(
                    self.token,
                    self.fiel_manager.rfc,
                    fecha_inicio_str,
                    fecha_fin_str,
                    rfc_receptor=rfc_receptor,
                    tipo_comprobante=tipo_comprobante
                )
            else:
                result = descarga.solicitar_descarga(
                    self.token,
                    self.fiel_manager.rfc,
                    fecha_inicio_str,
                    fecha_fin_str,
                    tipo_comprobante=tipo_comprobante
                )
            
            if result:
                cod_estatus = result.get('cod_estatus', '')
                mensaje = result.get('mensaje', '')
                id_solicitud = result.get('id_solicitud', '')
                
                success = cod_estatus == '5000'
                
                return {
                    'success': success,
                    'id_solicitud': id_solicitud,
                    'codigo': cod_estatus,
                    'mensaje': mensaje or ('Solicitud creada exitosamente' if success else self._parse_error_code(cod_estatus)),
                    'tipo': 'emitidos'
                }
            
            return {'success': False, 'error': 'Sin respuesta del SAT'}
            
        except Exception as e:
            logger.error(f"Error requesting download: {e}")
            return {'success': False, 'error': f'Error solicitando descarga: {str(e)}'}
    
    async def verificar_solicitud(self, id_solicitud: str) -> Dict:
        """Check status of a download request"""
        
        if not self._ensure_token():
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            verifica = VerificaSolicitudDescarga(self.fiel)
            result = verifica.verificar_descarga(
                self.token,
                self.fiel_manager.rfc,
                id_solicitud
            )
            
            if result:
                cod_estatus = result.get('cod_estatus', '')
                estado_solicitud = result.get('estado_solicitud', '')
                mensaje = result.get('mensaje', '')
                numero_cfdis = result.get('numero_cfdis', '0')
                paquetes = result.get('paquetes', [])
                
                estado_map = {
                    '1': 'Aceptada',
                    '2': 'En proceso', 
                    '3': 'Terminada',
                    '4': 'Error',
                    '5': 'Rechazada',
                    '6': 'Vencida'
                }
                
                return {
                    'success': True,
                    'estado': estado_solicitud,
                    'estado_texto': estado_map.get(str(estado_solicitud), 'Desconocido'),
                    'codigo': cod_estatus,
                    'mensaje': mensaje,
                    'numero_cfdis': int(numero_cfdis) if numero_cfdis else 0,
                    'paquetes': paquetes if isinstance(paquetes, list) else [paquetes] if paquetes else []
                }
            
            return {'success': False, 'error': 'Sin respuesta del SAT'}
            
        except Exception as e:
            logger.error(f"Error verifying request: {e}")
            return {'success': False, 'error': f'Error verificando solicitud: {str(e)}'}
    
    async def descargar_paquete(self, id_paquete: str) -> Dict:
        """Download a package of CFDIs"""
        
        if not self._ensure_token():
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            descarga = DescargaMasiva(self.fiel)
            result = descarga.descargar_paquete(
                self.token,
                self.fiel_manager.rfc,
                id_paquete
            )
            
            if result:
                cod_estatus = result.get('cod_estatus', '')
                paquete_b64 = result.get('paquete_b64', '')
                
                if cod_estatus == '5000' and paquete_b64:
                    zip_content = base64.b64decode(paquete_b64)
                    return {
                        'success': True,
                        'codigo': cod_estatus,
                        'zip_content': zip_content,
                        'size_bytes': len(zip_content)
                    }
                else:
                    return {
                        'success': False,
                        'codigo': cod_estatus,
                        'error': self._parse_error_code(cod_estatus)
                    }
            
            return {'success': False, 'error': 'Sin respuesta del SAT'}
            
        except Exception as e:
            logger.error(f"Error downloading package: {e}")
            return {'success': False, 'error': f'Error descargando paquete: {str(e)}'}
    
    def _parse_error_code(self, code: str) -> str:
        """Parse SAT error codes to human readable messages"""
        error_codes = {
            '300': 'Usuario no válido',
            '301': 'XML mal formado',
            '302': 'Sello mal formado',
            '303': 'Sello no corresponde al RFC solicitante',
            '304': 'Certificado revocado o caduco',
            '305': 'Certificado expirado',
            '5000': 'Solicitud recibida con éxito',
            '5002': 'No se encontraron CFDIs',
            '5003': 'Error al procesar la solicitud',
            '5004': 'Solicitud duplicada',
            '5005': 'Solicitud no existe',
        }
        return error_codes.get(str(code), f'Código de error: {code}')


class SATFIELCredentialManager:
    """Manages FIEL credential storage"""
    
    def __init__(self, db):
        self.db = db
    
    async def save_fiel(
        self,
        company_id: str,
        cer_content: bytes,
        key_content: bytes,
        password: str
    ) -> Dict:
        """Validate and save FIEL credentials"""
        try:
            # Validate FIEL
            fiel_manager = FIELManager(cer_content, key_content, password)
            
            if not fiel_manager.is_valid():
                return {
                    'success': False,
                    'error': f'El certificado FIEL ha expirado. Válido hasta: {fiel_manager.not_after}'
                }
            
            # Encrypt and store
            from cryptography.fernet import Fernet
            key = os.environ.get('SAT_ENCRYPTION_KEY')
            if not key:
                key = Fernet.generate_key().decode()
                logger.warning("SAT_ENCRYPTION_KEY not set!")
            
            fernet = Fernet(key.encode() if isinstance(key, str) else key)
            
            credential_doc = {
                'id': str(uuid_module.uuid4()),
                'company_id': company_id,
                'rfc': fiel_manager.rfc,
                'serial_number': fiel_manager.serial_number,
                'cer_encrypted': fernet.encrypt(cer_content).decode(),
                'key_encrypted': fernet.encrypt(key_content).decode(),
                'password_encrypted': fernet.encrypt(password.encode()).decode(),
                'valid_from': fiel_manager.not_before.isoformat(),
                'valid_to': fiel_manager.not_after.isoformat(),
                'auth_type': 'fiel',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'last_sync': None,
                'status': 'active'
            }
            
            # Upsert
            await self.db.sat_credentials.update_one(
                {'company_id': company_id},
                {'$set': credential_doc},
                upsert=True
            )
            
            return {
                'success': True,
                'rfc': fiel_manager.rfc,
                'serial_number': fiel_manager.serial_number,
                'valid_to': fiel_manager.not_after.isoformat(),
                'message': 'FIEL guardada correctamente'
            }
            
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error saving FIEL: {e}")
            return {'success': False, 'error': f'Error guardando FIEL: {str(e)}'}
    
    async def get_fiel(self, company_id: str) -> Optional[FIELManager]:
        """Get decrypted FIEL"""
        cred = await self.db.sat_credentials.find_one(
            {'company_id': company_id, 'status': 'active', 'auth_type': 'fiel'},
            {'_id': 0}
        )
        
        if not cred:
            return None
        
        try:
            from cryptography.fernet import Fernet
            key = os.environ.get('SAT_ENCRYPTION_KEY')
            if not key:
                logger.error("SAT_ENCRYPTION_KEY not set")
                return None
            
            fernet = Fernet(key.encode() if isinstance(key, str) else key)
            
            cer_content = fernet.decrypt(cred['cer_encrypted'].encode())
            key_content = fernet.decrypt(cred['key_encrypted'].encode())
            password = fernet.decrypt(cred['password_encrypted'].encode()).decode()
            
            return FIELManager(cer_content, key_content, password)
            
        except Exception as e:
            logger.error(f"Error loading FIEL: {e}")
            return None
    
    async def get_status(self, company_id: str) -> Optional[Dict]:
        """Get FIEL status"""
        cred = await self.db.sat_credentials.find_one(
            {'company_id': company_id},
            {'_id': 0, 'cer_encrypted': 0, 'key_encrypted': 0, 'password_encrypted': 0}
        )
        return cred
    
    async def delete_fiel(self, company_id: str) -> bool:
        """Delete FIEL credentials"""
        result = await self.db.sat_credentials.delete_one({'company_id': company_id})
        return result.deleted_count > 0


class SATFIELSyncService:
    """Service for syncing CFDIs using FIEL"""
    
    def __init__(self, db):
        self.db = db
        self.credential_manager = SATFIELCredentialManager(db)
    
    async def test_connection(self, company_id: str) -> Dict:
        """Test SAT connection"""
        fiel_manager = await self.credential_manager.get_fiel(company_id)
        if not fiel_manager:
            return {'success': False, 'error': 'No hay FIEL configurada para esta empresa'}
        
        if not fiel_manager.is_valid():
            return {'success': False, 'error': 'El certificado FIEL ha expirado'}
        
        ws = SATWebService(fiel_manager)
        result = await ws.authenticate()
        
        if result.get('success'):
            await self.db.sat_credentials.update_one(
                {'company_id': company_id},
                {'$set': {
                    'last_test': datetime.now(timezone.utc).isoformat(),
                    'last_test_result': 'success'
                }}
            )
        else:
            await self.db.sat_credentials.update_one(
                {'company_id': company_id},
                {'$set': {
                    'last_test': datetime.now(timezone.utc).isoformat(),
                    'last_test_result': result.get('error', 'error')
                }}
            )
        
        return result
    
    async def request_download(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = None,
        tipo_solicitud: str = 'recibidos'  # 'recibidos' or 'emitidos'
    ) -> Dict:
        """Request CFDI download"""
        fiel_manager = await self.credential_manager.get_fiel(company_id)
        if not fiel_manager:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel_manager)
        
        # Request based on type
        if tipo_solicitud == 'emitidos':
            result = await ws.solicitar_descarga_emitidos(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                tipo_comprobante=tipo_comprobante if tipo_comprobante and tipo_comprobante != 'todos' else None
            )
        else:
            result = await ws.solicitar_descarga_recibidos(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                tipo_comprobante=tipo_comprobante if tipo_comprobante and tipo_comprobante != 'todos' else None
            )
        
        if result.get('success') and result.get('id_solicitud'):
            await self.db.sat_download_requests.insert_one({
                'id': str(uuid_module.uuid4()),
                'company_id': company_id,
                'id_solicitud': result['id_solicitud'],
                'fecha_inicio': fecha_inicio.isoformat(),
                'fecha_fin': fecha_fin.isoformat(),
                'tipo_comprobante': tipo_comprobante,
                'tipo_solicitud': tipo_solicitud,
                'estado': 'solicitada',
                'created_at': datetime.now(timezone.utc).isoformat()
            })
        
        return result
    
    async def check_request_status(self, company_id: str, id_solicitud: str) -> Dict:
        """Check download request status"""
        fiel_manager = await self.credential_manager.get_fiel(company_id)
        if not fiel_manager:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel_manager)
        result = await ws.verificar_solicitud(id_solicitud)
        
        if result.get('success'):
            await self.db.sat_download_requests.update_one(
                {'id_solicitud': id_solicitud},
                {'$set': {
                    'estado': result.get('estado_texto', 'desconocido'),
                    'numero_cfdis': result.get('numero_cfdis', 0),
                    'paquetes': result.get('paquetes', []),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }}
            )
        
        return result
    
    async def download_and_process_package(self, company_id: str, id_paquete: str) -> Dict:
        """Download and process CFDI package"""
        fiel_manager = await self.credential_manager.get_fiel(company_id)
        if not fiel_manager:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel_manager)
        result = await ws.descargar_paquete(id_paquete)
        
        if result.get('success') and result.get('zip_content'):
            processed = await self._process_zip(company_id, result['zip_content'])
            return {
                'success': True,
                'package_id': id_paquete,
                'cfdis_found': processed['total'],
                'cfdis_new': processed['new'],
                'cfdis_updated': processed['updated'],
                'errors': processed['errors']
            }
        
        return result
    
    async def _process_zip(self, company_id: str, zip_content: bytes) -> Dict:
        """Process ZIP with CFDIs"""
        from services.cfdi_parser import CFDIParser
        
        results = {'total': 0, 'new': 0, 'updated': 0, 'errors': []}
        
        try:
            with zipfile.ZipFile(BytesIO(zip_content), 'r') as zf:
                for filename in zf.namelist():
                    if filename.endswith('.xml'):
                        results['total'] += 1
                        try:
                            xml_content = zf.read(filename).decode('utf-8')
                            cfdi_data = CFDIParser.parse_xml_string(xml_content)
                            
                            if cfdi_data and cfdi_data.get('uuid'):
                                existing = await self.db.cfdis.find_one({
                                    'uuid': cfdi_data['uuid'],
                                    'company_id': company_id
                                })
                                
                                now = datetime.now(timezone.utc).isoformat()
                                
                                if existing:
                                    await self.db.cfdis.update_one(
                                        {'id': existing['id']},
                                        {'$set': {
                                            'xml_original': xml_content,
                                            'updated_at': now,
                                            'source': 'sat_fiel_sync'
                                        }}
                                    )
                                    results['updated'] += 1
                                else:
                                    doc = {
                                        'id': str(uuid_module.uuid4()),
                                        'company_id': company_id,
                                        'source': 'sat_fiel_sync',
                                        'xml_original': xml_content,
                                        'estado_conciliacion': 'pendiente',
                                        'monto_pagado': 0,
                                        'monto_cobrado': 0,
                                        'created_at': now,
                                        'updated_at': now,
                                        **cfdi_data
                                    }
                                    await self.db.cfdis.insert_one(doc)
                                    results['new'] += 1
                                    
                        except Exception as e:
                            results['errors'].append(f"{filename}: {str(e)}")
                            
        except Exception as e:
            logger.error(f"Error processing ZIP: {e}")
            results['errors'].append(f"Error ZIP: {str(e)}")
        
        return results
