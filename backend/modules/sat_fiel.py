"""
SAT FIEL Integration Module
Handles authentication with SAT Web Services using FIEL (e.firma)
Implements the official SAT SOAP API for massive CFDI downloads
"""

import asyncio
import base64
import hashlib
import logging
import os
import tempfile
import uuid as uuid_module
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from io import BytesIO
from xml.etree import ElementTree as ET

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
import requests

logger = logging.getLogger(__name__)

# SAT Web Service URLs (Production)
SAT_AUTH_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
SAT_SOLICITUD_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolsolicitudDescargaMasivaTercerosCFDI.svc"
SAT_VERIFICA_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
SAT_DESCARGA_URL = "https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"

# SOAP Namespaces
NS = {
    's': 'http://schemas.xmlsoap.org/soap/envelope/',
    'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
    'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
}


class FIELManager:
    """Manages FIEL (e.firma) certificates and signing operations"""
    
    def __init__(self, cer_content: bytes, key_content: bytes, password: str):
        """
        Initialize FIEL manager with certificate and private key
        
        Args:
            cer_content: Binary content of .cer file
            key_content: Binary content of .key file
            password: Password for the private key
        """
        self.certificate = None
        self.private_key = None
        self.rfc = None
        self.serial_number = None
        self.not_before = None
        self.not_after = None
        
        self._load_certificate(cer_content)
        self._load_private_key(key_content, password)
    
    def _load_certificate(self, cer_content: bytes):
        """Load and parse the .cer certificate file"""
        try:
            self.certificate = x509.load_der_x509_certificate(cer_content, default_backend())
            
            # Extract RFC from certificate subject
            subject = self.certificate.subject
            for attr in subject:
                if attr.oid == NameOID.SERIAL_NUMBER or attr.oid.dotted_string == '2.5.4.45':
                    # SAT uses this OID for RFC
                    value = attr.value
                    if '/' in value:
                        self.rfc = value.split('/')[0].strip()
                    else:
                        self.rfc = value.strip()
                    break
                elif attr.oid == NameOID.COMMON_NAME:
                    # Fallback to common name
                    cn = attr.value
                    if len(cn) >= 12:
                        self.rfc = cn[:13] if len(cn) >= 13 else cn[:12]
            
            # Get serial number
            self.serial_number = format(self.certificate.serial_number, 'x').upper()
            
            # Get validity dates
            self.not_before = self.certificate.not_valid_before_utc
            self.not_after = self.certificate.not_valid_after_utc
            
            logger.info(f"Certificate loaded: RFC={self.rfc}, Serial={self.serial_number}")
            
        except Exception as e:
            logger.error(f"Error loading certificate: {e}")
            raise ValueError(f"Error al cargar el certificado .cer: {str(e)}")
    
    def _load_private_key(self, key_content: bytes, password: str):
        """Load and decrypt the .key private key file"""
        try:
            self.private_key = serialization.load_der_private_key(
                key_content,
                password=password.encode('utf-8'),
                backend=default_backend()
            )
            logger.info("Private key loaded successfully")
        except Exception as e:
            logger.error(f"Error loading private key: {e}")
            raise ValueError(f"Error al cargar la llave privada .key: Contraseña incorrecta o archivo inválido")
    
    def get_certificate_base64(self) -> str:
        """Get certificate in base64 format"""
        cert_der = self.certificate.public_bytes(serialization.Encoding.DER)
        return base64.b64encode(cert_der).decode('utf-8')
    
    def sign(self, data: bytes) -> bytes:
        """Sign data using the private key with SHA256"""
        signature = self.private_key.sign(
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return signature
    
    def sign_base64(self, data: str) -> str:
        """Sign string data and return base64 encoded signature"""
        signature = self.sign(data.encode('utf-8'))
        return base64.b64encode(signature).decode('utf-8')
    
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
    """SAT SOAP Web Service client for CFDI downloads"""
    
    def __init__(self, fiel: FIELManager):
        self.fiel = fiel
        self.token = None
        self.token_expires = None
    
    def _create_soap_envelope(self, body_content: str, action: str) -> str:
        """Create a SOAP envelope with security headers"""
        now = datetime.now(timezone.utc)
        created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        expires = (now + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        # Create the timestamp and token for signing
        timestamp_id = f"_0"
        
        envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
    <s:Header>
        <o:Security xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" s:mustUnderstand="1">
            <u:Timestamp u:Id="{timestamp_id}">
                <u:Created>{created}</u:Created>
                <u:Expires>{expires}</u:Expires>
            </u:Timestamp>
            {self._create_binary_security_token()}
            {self._create_signature(created, expires)}
        </o:Security>
    </s:Header>
    <s:Body>
        {body_content}
    </s:Body>
</s:Envelope>'''
        
        return envelope
    
    def _create_binary_security_token(self) -> str:
        """Create BinarySecurityToken element with certificate"""
        cert_b64 = self.fiel.get_certificate_base64()
        return f'''<o:BinarySecurityToken u:Id="uuid-{uuid_module.uuid4()}" 
            ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" 
            EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{cert_b64}</o:BinarySecurityToken>'''
    
    def _create_signature(self, created: str, expires: str) -> str:
        """Create XML Signature element"""
        # Simplified - in production would need full canonicalization
        to_sign = f"{created}{expires}"
        signature_value = self.fiel.sign_base64(to_sign)
        
        return f'''<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
            <SignedInfo>
                <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                <SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                <Reference URI="#_0">
                    <Transforms>
                        <Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </Transforms>
                    <DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                    <DigestValue>{base64.b64encode(hashlib.sha256(to_sign.encode()).digest()).decode()}</DigestValue>
                </Reference>
            </SignedInfo>
            <SignatureValue>{signature_value}</SignatureValue>
            <KeyInfo>
                <o:SecurityTokenReference xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
                    <o:Reference ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                </o:SecurityTokenReference>
            </KeyInfo>
        </Signature>'''
    
    async def authenticate(self) -> Dict:
        """
        Authenticate with SAT using FIEL
        Returns authentication token
        """
        try:
            now = datetime.now(timezone.utc)
            created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            expires = (now + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            uuid_str = str(uuid_module.uuid4())
            
            # Create authentication SOAP request
            body = '<Autentica xmlns="http://DescargaMasivaTerceros.gob.mx"/>'
            
            soap_envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
    <s:Header>
        <o:Security xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" s:mustUnderstand="1">
            <u:Timestamp u:Id="_0">
                <u:Created>{created}</u:Created>
                <u:Expires>{expires}</u:Expires>
            </u:Timestamp>
            <o:BinarySecurityToken u:Id="uuid-{uuid_str}" 
                ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" 
                EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{self.fiel.get_certificate_base64()}</o:BinarySecurityToken>
            <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
                <SignedInfo>
                    <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    <SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <Reference URI="#_0">
                        <Transforms>
                            <Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                        </Transforms>
                        <DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <DigestValue>{base64.b64encode(hashlib.sha256(f"{created}{expires}".encode()).digest()).decode()}</DigestValue>
                    </Reference>
                </SignedInfo>
                <SignatureValue>{self.fiel.sign_base64(f"{created}{expires}")}</SignatureValue>
                <KeyInfo>
                    <o:SecurityTokenReference>
                        <o:Reference URI="#uuid-{uuid_str}" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </o:SecurityTokenReference>
                </KeyInfo>
            </Signature>
        </o:Security>
    </s:Header>
    <s:Body>
        {body}
    </s:Body>
</s:Envelope>'''
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica'
            }
            
            response = requests.post(SAT_AUTH_URL, data=soap_envelope.encode('utf-8'), headers=headers, timeout=30)
            
            logger.info(f"Auth response status: {response.status_code}")
            
            if response.status_code == 200:
                # Parse response to get token
                root = ET.fromstring(response.content)
                
                # Find token in response
                token_elem = root.find('.//{http://DescargaMasivaTerceros.gob.mx}AutenticaResult')
                if token_elem is not None and token_elem.text:
                    self.token = token_elem.text
                    self.token_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
                    return {
                        'success': True,
                        'token': self.token[:50] + '...',
                        'expires': self.token_expires.isoformat(),
                        'rfc': self.fiel.rfc
                    }
                
                # Check for fault
                fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
                if fault is not None:
                    fault_string = fault.find('faultstring')
                    error_msg = fault_string.text if fault_string is not None else 'Error desconocido'
                    return {'success': False, 'error': f'Error SAT: {error_msg}'}
                
                return {'success': False, 'error': 'No se recibió token de autenticación'}
            else:
                return {'success': False, 'error': f'Error HTTP {response.status_code}: {response.text[:200]}'}
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Tiempo de espera agotado al conectar con SAT'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'No se pudo conectar con el servidor SAT'}
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return {'success': False, 'error': f'Error de autenticación: {str(e)}'}
    
    async def solicitar_descarga(
        self,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_solicitud: str = 'CFDI',  # CFDI or Metadata
        tipo_comprobante: str = None,  # I, E, P, N, T or None for all
        rfc_emisor: str = None,
        rfc_receptor: str = None,
        estado_comprobante: str = '1'  # 1=Vigente, 0=Cancelado
    ) -> Dict:
        """
        Request CFDI download from SAT
        """
        if not self.token:
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            # Use FIEL RFC if not specified
            if not rfc_emisor and not rfc_receptor:
                rfc_receptor = self.fiel.rfc
            
            fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%dT00:00:00')
            fecha_fin_str = fecha_fin.strftime('%Y-%m-%dT23:59:59')
            
            # Build request attributes
            attrs = f'FechaInicial="{fecha_inicio_str}" FechaFinal="{fecha_fin_str}" TipoSolicitud="{tipo_solicitud}"'
            
            if rfc_emisor:
                attrs += f' RfcEmisor="{rfc_emisor}"'
            if rfc_receptor:
                attrs += f' RfcReceptores="{rfc_receptor}"'
            if tipo_comprobante:
                attrs += f' TipoComprobante="{tipo_comprobante}"'
            if estado_comprobante:
                attrs += f' EstadoComprobante="{estado_comprobante}"'
            
            body = f'''<des:SolicitaDescarga xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx">
                <des:solicitud {attrs}/>
            </des:SolicitaDescarga>'''
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescarga',
                'Authorization': f'WRAP access_token="{self.token}"'
            }
            
            now = datetime.now(timezone.utc)
            created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            expires = (now + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            soap_envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx" xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
    <s:Header>
        <o:Security xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" s:mustUnderstand="1">
            <u:Timestamp u:Id="_0">
                <u:Created>{created}</u:Created>
                <u:Expires>{expires}</u:Expires>
            </u:Timestamp>
        </o:Security>
    </s:Header>
    <s:Body>
        {body}
    </s:Body>
</s:Envelope>'''
            
            response = requests.post(SAT_SOLICITUD_URL, data=soap_envelope.encode('utf-8'), headers=headers, timeout=30)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                # Find IdSolicitud in response
                result = root.find('.//{http://DescargaMasivaTerceros.sat.gob.mx}SolicitaDescargaResult')
                if result is not None:
                    id_solicitud = result.get('IdSolicitud')
                    cod_estatus = result.get('CodEstatus')
                    mensaje = result.get('Mensaje')
                    
                    return {
                        'success': cod_estatus == '5000',
                        'id_solicitud': id_solicitud,
                        'codigo': cod_estatus,
                        'mensaje': mensaje
                    }
                
                return {'success': False, 'error': 'Respuesta inesperada del SAT'}
            else:
                return {'success': False, 'error': f'Error HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error requesting download: {e}")
            return {'success': False, 'error': str(e)}
    
    async def verificar_solicitud(self, id_solicitud: str) -> Dict:
        """
        Check status of a download request
        """
        if not self.token:
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            body = f'''<des:VerificaSolicitudDescarga xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx">
                <des:solicitud IdSolicitud="{id_solicitud}" RfcSolicitante="{self.fiel.rfc}"/>
            </des:VerificaSolicitudDescarga>'''
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga',
                'Authorization': f'WRAP access_token="{self.token}"'
            }
            
            now = datetime.now(timezone.utc)
            created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            expires = (now + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            soap_envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx" xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
    <s:Header>
        <o:Security xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" s:mustUnderstand="1">
            <u:Timestamp u:Id="_0">
                <u:Created>{created}</u:Created>
                <u:Expires>{expires}</u:Expires>
            </u:Timestamp>
        </o:Security>
    </s:Header>
    <s:Body>
        {body}
    </s:Body>
</s:Envelope>'''
            
            response = requests.post(SAT_VERIFICA_URL, data=soap_envelope.encode('utf-8'), headers=headers, timeout=30)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                result = root.find('.//{http://DescargaMasivaTerceros.sat.gob.mx}VerificaSolicitudDescargaResult')
                if result is not None:
                    estado = result.get('EstadoSolicitud')
                    cod_estatus = result.get('CodEstatus')
                    mensaje = result.get('Mensaje')
                    numero_cfdis = result.get('NumeroCFDIs', '0')
                    
                    # Get package IDs
                    paquetes = []
                    for paquete in result.findall('.//{http://DescargaMasivaTerceros.sat.gob.mx}IdsPaquetes'):
                        paquetes.append(paquete.text)
                    
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
                        'estado': estado,
                        'estado_texto': estado_map.get(estado, 'Desconocido'),
                        'codigo': cod_estatus,
                        'mensaje': mensaje,
                        'numero_cfdis': int(numero_cfdis) if numero_cfdis else 0,
                        'paquetes': paquetes
                    }
                
                return {'success': False, 'error': 'Respuesta inesperada'}
            else:
                return {'success': False, 'error': f'Error HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error verifying request: {e}")
            return {'success': False, 'error': str(e)}
    
    async def descargar_paquete(self, id_paquete: str) -> Dict:
        """
        Download a package of CFDIs
        Returns ZIP file content with XMLs
        """
        if not self.token:
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            body = f'''<des:PeticionDescargaMasivaTercerosEntrada xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx">
                <des:peticionDescarga IdPaquete="{id_paquete}" RfcSolicitante="{self.fiel.rfc}"/>
            </des:PeticionDescargaMasivaTercerosEntrada>'''
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar',
                'Authorization': f'WRAP access_token="{self.token}"'
            }
            
            now = datetime.now(timezone.utc)
            created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            expires = (now + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            soap_envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx" xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
    <s:Header>
        <o:Security xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" s:mustUnderstand="1">
            <u:Timestamp u:Id="_0">
                <u:Created>{created}</u:Created>
                <u:Expires>{expires}</u:Expires>
            </u:Timestamp>
        </o:Security>
    </s:Header>
    <s:Body>
        {body}
    </s:Body>
</s:Envelope>'''
            
            response = requests.post(SAT_DESCARGA_URL, data=soap_envelope.encode('utf-8'), headers=headers, timeout=120)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                result = root.find('.//{http://DescargaMasivaTerceros.sat.gob.mx}RespuestaDescargaMasivaTercerosSalida')
                if result is not None:
                    cod_estatus = result.get('CodEstatus')
                    paquete_b64 = result.get('Paquete')
                    
                    if cod_estatus == '5000' and paquete_b64:
                        # Decode the ZIP package
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
                            'error': 'No se pudo obtener el paquete'
                        }
                
                return {'success': False, 'error': 'Respuesta inesperada'}
            else:
                return {'success': False, 'error': f'Error HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error downloading package: {e}")
            return {'success': False, 'error': str(e)}


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
        """
        Validate and save FIEL credentials
        """
        try:
            # Validate FIEL by loading it
            fiel = FIELManager(cer_content, key_content, password)
            
            if not fiel.is_valid():
                return {
                    'success': False,
                    'error': f'El certificado FIEL ha expirado. Válido hasta: {fiel.not_after}'
                }
            
            # Store encrypted (using base64 for simplicity - in production use proper encryption)
            from cryptography.fernet import Fernet
            key = os.environ.get('SAT_ENCRYPTION_KEY', Fernet.generate_key().decode())
            fernet = Fernet(key.encode() if isinstance(key, str) else key)
            
            credential_doc = {
                'id': str(uuid_module.uuid4()),
                'company_id': company_id,
                'rfc': fiel.rfc,
                'serial_number': fiel.serial_number,
                'cer_encrypted': fernet.encrypt(cer_content).decode(),
                'key_encrypted': fernet.encrypt(key_content).decode(),
                'password_encrypted': fernet.encrypt(password.encode()).decode(),
                'valid_from': fiel.not_before.isoformat(),
                'valid_to': fiel.not_after.isoformat(),
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
                'rfc': fiel.rfc,
                'serial_number': fiel.serial_number,
                'valid_to': fiel.not_after.isoformat(),
                'message': 'FIEL guardada correctamente'
            }
            
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error saving FIEL: {e}")
            return {'success': False, 'error': f'Error guardando FIEL: {str(e)}'}
    
    async def get_fiel(self, company_id: str) -> Optional[FIELManager]:
        """Get decrypted FIEL for a company"""
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
        """Get FIEL status without decrypting"""
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
        """Test SAT connection using saved FIEL"""
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada para esta empresa'}
        
        if not fiel.is_valid():
            return {'success': False, 'error': 'El certificado FIEL ha expirado'}
        
        ws = SATWebService(fiel)
        result = await ws.authenticate()
        
        if result.get('success'):
            # Update last test
            await self.db.sat_credentials.update_one(
                {'company_id': company_id},
                {'$set': {
                    'last_test': datetime.now(timezone.utc).isoformat(),
                    'last_test_result': 'success'
                }}
            )
        
        return result
    
    async def request_download(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = None,
        tipo_solicitud: str = 'CFDI'
    ) -> Dict:
        """Request CFDI download from SAT"""
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel)
        
        result = await ws.solicitar_descarga(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo_solicitud=tipo_solicitud,
            tipo_comprobante=tipo_comprobante,
            rfc_receptor=fiel.rfc
        )
        
        if result.get('success') and result.get('id_solicitud'):
            # Store the request
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
        """Check status of a download request"""
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel)
        result = await ws.verificar_solicitud(id_solicitud)
        
        if result.get('success'):
            # Update request status
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
        """Download a package and process its CFDIs"""
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel)
        result = await ws.descargar_paquete(id_paquete)
        
        if result.get('success') and result.get('zip_content'):
            # Process the ZIP
            processed = await self._process_zip_package(company_id, result['zip_content'])
            return {
                'success': True,
                'package_id': id_paquete,
                'cfdis_found': processed['total'],
                'cfdis_new': processed['new'],
                'cfdis_updated': processed['updated'],
                'errors': processed['errors']
            }
        
        return result
    
    async def _process_zip_package(self, company_id: str, zip_content: bytes) -> Dict:
        """Process a ZIP package containing CFDI XMLs"""
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
                                # Check if exists
                                existing = await self.db.cfdis.find_one({
                                    'uuid': cfdi_data['uuid'],
                                    'company_id': company_id
                                })
                                
                                now = datetime.now(timezone.utc).isoformat()
                                
                                if existing:
                                    # Update
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
                                    # Insert new
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
            results['errors'].append(f"Error procesando ZIP: {str(e)}")
        
        return results
