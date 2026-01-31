"""
SAT FIEL Integration Module - Proper XML Signature Implementation
Handles authentication with SAT Web Services using FIEL (e.firma)
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
from typing import Optional, Dict, List, Any
from io import BytesIO
from xml.etree import ElementTree as ET
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
import requests
from lxml import etree

logger = logging.getLogger(__name__)

# SAT Web Service URLs (Production - Official 2024/2025)
SAT_AUTH_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
SAT_SOLICITUD_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaMasivaTercerosCFDI.svc"
SAT_VERIFICA_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
SAT_DESCARGA_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/DescargaMasivaService.svc"

# Alternative URLs (backup)
SAT_AUTH_URL_ALT = "https://cfdidescargamasiva.sat.gob.mx/nidp/app/login"
SAT_SOLICITUD_URL_ALT = "https://cfdidescargamasiva.sat.gob.mx/solicitud/"
SAT_DESCARGA_URL_ALT = "https://cfdidescargamasiva.sat.gob.mx/descarga/"

# Namespaces
NSMAP = {
    's': 'http://schemas.xmlsoap.org/soap/envelope/',
    'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
    'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}


class FIELManager:
    """Manages FIEL (e.firma) certificates and signing operations"""
    
    def __init__(self, cer_content: bytes, key_content: bytes, password: str):
        self.certificate = None
        self.private_key = None
        self.rfc = None
        self.serial_number = None
        self.not_before = None
        self.not_after = None
        self.cer_content = cer_content
        
        self._load_certificate(cer_content)
        self._load_private_key(key_content, password)
    
    def _load_certificate(self, cer_content: bytes):
        """Load and parse the .cer certificate file"""
        try:
            self.certificate = x509.load_der_x509_certificate(cer_content, default_backend())
            
            # Extract RFC from certificate
            subject = self.certificate.subject
            for attr in subject:
                # Try different OIDs where RFC might be stored
                if attr.oid.dotted_string == '2.5.4.45':  # x500UniqueIdentifier
                    value = attr.value
                    # RFC is usually before the first space or /
                    match = re.match(r'^([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})', value.upper())
                    if match:
                        self.rfc = match.group(1)
                        break
                elif attr.oid == NameOID.SERIAL_NUMBER:
                    value = attr.value
                    if '/' in value:
                        self.rfc = value.split('/')[0].strip().upper()
                    else:
                        self.rfc = value.strip().upper()
                    break
            
            # Fallback: extract from subject string
            if not self.rfc:
                subject_str = str(subject)
                match = re.search(r'([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})', subject_str.upper())
                if match:
                    self.rfc = match.group(1)
            
            # Get serial number in hex
            self.serial_number = format(self.certificate.serial_number, 'X')
            
            # Get validity dates
            self.not_before = self.certificate.not_valid_before_utc
            self.not_after = self.certificate.not_valid_after_utc
            
            logger.info(f"Certificate loaded: RFC={self.rfc}, Serial={self.serial_number[:20]}...")
            
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
        return base64.b64encode(self.cer_content).decode('utf-8')
    
    def get_certificate_pem(self) -> bytes:
        """Get certificate in PEM format"""
        return self.certificate.public_bytes(serialization.Encoding.PEM)
    
    def get_private_key_pem(self) -> bytes:
        """Get private key in PEM format (unencrypted)"""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def sign_sha1(self, data: bytes) -> bytes:
        """Sign data using SHA1 (required by SAT)"""
        signature = self.private_key.sign(
            data,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        return signature
    
    def sign_sha256(self, data: bytes) -> bytes:
        """Sign data using SHA256"""
        signature = self.private_key.sign(
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return signature
    
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


def canonicalize(element):
    """Canonicalize XML element using Exclusive C14N"""
    return etree.tostring(element, method='c14n', exclusive=True, with_comments=False)


class SATWebService:
    """SAT SOAP Web Service client using proper XML Signature"""
    
    def __init__(self, fiel: FIELManager):
        self.fiel = fiel
        self.token = None
        self.token_expires = None
    
    def _build_auth_soap(self) -> bytes:
        """Build SOAP authentication request with proper XML Signature"""
        now = datetime.now(timezone.utc)
        created = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        expires = (now + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        uuid_token = f"uuid-{uuid_module.uuid4()}-1"
        
        # Build the SOAP envelope
        envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope', nsmap={
            's': 'http://schemas.xmlsoap.org/soap/envelope/',
            'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
        })
        
        # Header
        header = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
        
        # Security
        security = etree.SubElement(header, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Security', 
            nsmap={'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'})
        security.set('{http://schemas.xmlsoap.org/soap/envelope/}mustUnderstand', '1')
        
        # Timestamp
        timestamp = etree.SubElement(security, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Timestamp')
        timestamp.set('{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Id', '_0')
        
        created_elem = etree.SubElement(timestamp, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Created')
        created_elem.text = created
        
        expires_elem = etree.SubElement(timestamp, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Expires')
        expires_elem.text = expires
        
        # BinarySecurityToken
        bst = etree.SubElement(security, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}BinarySecurityToken')
        bst.set('{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Id', uuid_token)
        bst.set('ValueType', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3')
        bst.set('EncodingType', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary')
        bst.text = self.fiel.get_certificate_base64()
        
        # Signature
        sig_ns = 'http://www.w3.org/2000/09/xmldsig#'
        signature = etree.SubElement(security, '{%s}Signature' % sig_ns, nsmap={None: sig_ns})
        
        # SignedInfo
        signed_info = etree.SubElement(signature, '{%s}SignedInfo' % sig_ns)
        
        canon_method = etree.SubElement(signed_info, '{%s}CanonicalizationMethod' % sig_ns)
        canon_method.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')
        
        sig_method = etree.SubElement(signed_info, '{%s}SignatureMethod' % sig_ns)
        sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        
        # Reference to Timestamp
        reference = etree.SubElement(signed_info, '{%s}Reference' % sig_ns)
        reference.set('URI', '#_0')
        
        transforms = etree.SubElement(reference, '{%s}Transforms' % sig_ns)
        transform = etree.SubElement(transforms, '{%s}Transform' % sig_ns)
        transform.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')
        
        digest_method = etree.SubElement(reference, '{%s}DigestMethod' % sig_ns)
        digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        # Calculate digest of timestamp
        timestamp_c14n = canonicalize(timestamp)
        digest_value_elem = etree.SubElement(reference, '{%s}DigestValue' % sig_ns)
        digest_value_elem.text = base64.b64encode(hashlib.sha1(timestamp_c14n).digest()).decode()
        
        # Calculate signature
        signed_info_c14n = canonicalize(signed_info)
        signature_bytes = self.fiel.sign_sha1(signed_info_c14n)
        
        sig_value = etree.SubElement(signature, '{%s}SignatureValue' % sig_ns)
        sig_value.text = base64.b64encode(signature_bytes).decode()
        
        # KeyInfo
        key_info = etree.SubElement(signature, '{%s}KeyInfo' % sig_ns)
        sec_token_ref = etree.SubElement(key_info, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}SecurityTokenReference')
        ref = etree.SubElement(sec_token_ref, '{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Reference')
        ref.set('URI', '#' + uuid_token)
        ref.set('ValueType', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3')
        
        # Body
        body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
        autentica = etree.SubElement(body, '{http://DescargaMasivaTerceros.gob.mx}Autentica')
        
        return etree.tostring(envelope, xml_declaration=True, encoding='UTF-8')
    
    async def authenticate(self) -> Dict:
        """Authenticate with SAT using FIEL"""
        try:
            soap_request = self._build_auth_soap()
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica',
            }
            
            logger.info(f"Sending auth request to SAT for RFC: {self.fiel.rfc}")
            
            response = requests.post(
                SAT_AUTH_URL, 
                data=soap_request, 
                headers=headers, 
                timeout=30,
                verify=True
            )
            
            logger.info(f"Auth response status: {response.status_code}")
            
            if response.status_code == 200:
                # Parse response
                root = etree.fromstring(response.content)
                
                # Find token
                token_elem = root.find('.//{http://DescargaMasivaTerceros.gob.mx}AutenticaResult')
                if token_elem is not None and token_elem.text:
                    self.token = token_elem.text
                    self.token_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
                    logger.info("Authentication successful!")
                    return {
                        'success': True,
                        'message': '¡Autenticación exitosa con el SAT!',
                        'rfc': self.fiel.rfc,
                        'expires': self.token_expires.isoformat()
                    }
                
                # Check for fault
                fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
                if fault is not None:
                    faultstring = fault.find('.//faultstring')
                    error_msg = faultstring.text if faultstring is not None else 'Error desconocido'
                    logger.error(f"SOAP Fault: {error_msg}")
                    return {'success': False, 'error': f'Error SAT: {error_msg}'}
                
                return {'success': False, 'error': 'No se recibió token de autenticación'}
            
            else:
                error_text = response.text[:500] if response.text else 'Sin mensaje'
                logger.error(f"HTTP Error {response.status_code}: {error_text}")
                return {'success': False, 'error': f'Error HTTP {response.status_code}: {error_text}'}
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Tiempo de espera agotado al conectar con SAT'}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            return {'success': False, 'error': 'No se pudo conectar con el servidor del SAT'}
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return {'success': False, 'error': f'Error de autenticación: {str(e)}'}
    
    def _build_solicitud_soap(
        self,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_solicitud: str,
        rfc_emisor: str = None,
        rfc_receptor: str = None,
        tipo_comprobante: str = None,
        estado_comprobante: str = '1'
    ) -> bytes:
        """Build SOAP request for download solicitud"""
        
        # Build envelope
        envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope', nsmap={
            's': 'http://schemas.xmlsoap.org/soap/envelope/',
            'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
            'xd': 'http://www.w3.org/2000/09/xmldsig#',
        })
        
        # Header with token
        header = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
        
        # Body
        body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
        
        solicita = etree.SubElement(body, '{http://DescargaMasivaTerceros.sat.gob.mx}SolicitaDescarga')
        solicitud = etree.SubElement(solicita, '{http://DescargaMasivaTerceros.sat.gob.mx}solicitud')
        
        solicitud.set('RfcSolicitante', self.fiel.rfc)
        solicitud.set('FechaInicial', fecha_inicio.strftime('%Y-%m-%dT00:00:00'))
        solicitud.set('FechaFinal', fecha_fin.strftime('%Y-%m-%dT23:59:59'))
        solicitud.set('TipoSolicitud', tipo_solicitud)
        
        if rfc_emisor:
            emisores = etree.SubElement(solicitud, '{http://DescargaMasivaTerceros.sat.gob.mx}RfcEmisor')
            emisores.text = rfc_emisor
        
        if rfc_receptor:
            solicitud.set('RfcReceptores', rfc_receptor)
        
        if tipo_comprobante:
            solicitud.set('TipoComprobante', tipo_comprobante)
        
        solicitud.set('EstadoComprobante', estado_comprobante)
        
        # Sign the solicitud element
        sig_ns = 'http://www.w3.org/2000/09/xmldsig#'
        signature = etree.SubElement(solicitud, '{%s}Signature' % sig_ns, nsmap={None: sig_ns})
        
        signed_info = etree.SubElement(signature, '{%s}SignedInfo' % sig_ns)
        
        canon = etree.SubElement(signed_info, '{%s}CanonicalizationMethod' % sig_ns)
        canon.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')
        
        sig_method = etree.SubElement(signed_info, '{%s}SignatureMethod' % sig_ns)
        sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        
        reference = etree.SubElement(signed_info, '{%s}Reference' % sig_ns)
        reference.set('URI', '')
        
        transforms = etree.SubElement(reference, '{%s}Transforms' % sig_ns)
        transform = etree.SubElement(transforms, '{%s}Transform' % sig_ns)
        transform.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')
        
        digest_method = etree.SubElement(reference, '{%s}DigestMethod' % sig_ns)
        digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        # Calculate digest
        solicitud_copy = etree.Element(solicitud.tag, solicitud.attrib, nsmap=solicitud.nsmap)
        for child in solicitud:
            if not child.tag.endswith('Signature'):
                solicitud_copy.append(child)
        
        digest_value = etree.SubElement(reference, '{%s}DigestValue' % sig_ns)
        digest_value.text = base64.b64encode(hashlib.sha1(canonicalize(solicitud_copy)).digest()).decode()
        
        # Sign
        sig_value = etree.SubElement(signature, '{%s}SignatureValue' % sig_ns)
        sig_value.text = base64.b64encode(self.fiel.sign_sha1(canonicalize(signed_info))).decode()
        
        # KeyInfo
        key_info = etree.SubElement(signature, '{%s}KeyInfo' % sig_ns)
        x509_data = etree.SubElement(key_info, '{%s}X509Data' % sig_ns)
        x509_issuer = etree.SubElement(x509_data, '{%s}X509IssuerSerial' % sig_ns)
        
        issuer_name = etree.SubElement(x509_issuer, '{%s}X509IssuerName' % sig_ns)
        issuer = self.fiel.certificate.issuer
        issuer_parts = []
        for attr in reversed(list(issuer)):
            oid_name = attr.oid._name
            issuer_parts.append(f"{oid_name}={attr.value}")
        issuer_name.text = ','.join(issuer_parts)
        
        serial = etree.SubElement(x509_issuer, '{%s}X509SerialNumber' % sig_ns)
        serial.text = str(self.fiel.certificate.serial_number)
        
        return etree.tostring(envelope, xml_declaration=True, encoding='UTF-8')
    
    async def solicitar_descarga(
        self,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_solicitud: str = 'CFDI',
        tipo_comprobante: str = None,
        rfc_emisor: str = None,
        rfc_receptor: str = None,
        estado_comprobante: str = '1'
    ) -> Dict:
        """Request CFDI download from SAT"""
        
        if not self.token:
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            # Use FIEL RFC as receptor if not specified
            if not rfc_emisor and not rfc_receptor:
                rfc_receptor = self.fiel.rfc
            
            soap_request = self._build_solicitud_soap(
                fecha_inicio, fecha_fin, tipo_solicitud,
                rfc_emisor, rfc_receptor, tipo_comprobante, estado_comprobante
            )
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescarga',
                'Authorization': f'WRAP access_token="{self.token}"'
            }
            
            response = requests.post(SAT_SOLICITUD_URL, data=soap_request, headers=headers, timeout=30)
            
            if response.status_code == 200:
                root = etree.fromstring(response.content)
                
                result = root.find('.//{http://DescargaMasivaTerceros.sat.gob.mx}SolicitaDescargaResult')
                if result is not None:
                    id_solicitud = result.get('IdSolicitud')
                    cod_estatus = result.get('CodEstatus')
                    mensaje = result.get('Mensaje')
                    
                    success = cod_estatus == '5000'
                    
                    return {
                        'success': success,
                        'id_solicitud': id_solicitud,
                        'codigo': cod_estatus,
                        'mensaje': mensaje or ('Solicitud creada exitosamente' if success else 'Error en solicitud')
                    }
                
                return {'success': False, 'error': 'Respuesta inesperada del SAT'}
            else:
                return {'success': False, 'error': f'Error HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error requesting download: {e}")
            return {'success': False, 'error': str(e)}
    
    async def verificar_solicitud(self, id_solicitud: str) -> Dict:
        """Check status of a download request"""
        
        if not self.token:
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            # Build verification SOAP
            envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope', nsmap={
                's': 'http://schemas.xmlsoap.org/soap/envelope/',
                'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
            })
            
            header = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
            body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
            
            verifica = etree.SubElement(body, '{http://DescargaMasivaTerceros.sat.gob.mx}VerificaSolicitudDescarga')
            solicitud = etree.SubElement(verifica, '{http://DescargaMasivaTerceros.sat.gob.mx}solicitud')
            solicitud.set('IdSolicitud', id_solicitud)
            solicitud.set('RfcSolicitante', self.fiel.rfc)
            
            # Add signature to solicitud
            self._sign_element(solicitud)
            
            soap_request = etree.tostring(envelope, xml_declaration=True, encoding='UTF-8')
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga',
                'Authorization': f'WRAP access_token="{self.token}"'
            }
            
            response = requests.post(SAT_VERIFICA_URL, data=soap_request, headers=headers, timeout=30)
            
            if response.status_code == 200:
                root = etree.fromstring(response.content)
                
                result = root.find('.//{http://DescargaMasivaTerceros.sat.gob.mx}VerificaSolicitudDescargaResult')
                if result is not None:
                    estado = result.get('EstadoSolicitud')
                    cod_estatus = result.get('CodEstatus')
                    mensaje = result.get('Mensaje')
                    numero_cfdis = result.get('NumeroCFDIs', '0')
                    
                    # Get package IDs
                    paquetes = []
                    for paquete in result.findall('.//{http://DescargaMasivaTerceros.sat.gob.mx}IdsPaquetes'):
                        if paquete.text:
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
    
    def _sign_element(self, element):
        """Add XML Signature to an element"""
        sig_ns = 'http://www.w3.org/2000/09/xmldsig#'
        signature = etree.SubElement(element, '{%s}Signature' % sig_ns, nsmap={None: sig_ns})
        
        signed_info = etree.SubElement(signature, '{%s}SignedInfo' % sig_ns)
        
        canon = etree.SubElement(signed_info, '{%s}CanonicalizationMethod' % sig_ns)
        canon.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')
        
        sig_method = etree.SubElement(signed_info, '{%s}SignatureMethod' % sig_ns)
        sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        
        reference = etree.SubElement(signed_info, '{%s}Reference' % sig_ns)
        reference.set('URI', '')
        
        transforms = etree.SubElement(reference, '{%s}Transforms' % sig_ns)
        transform = etree.SubElement(transforms, '{%s}Transform' % sig_ns)
        transform.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')
        
        digest_method = etree.SubElement(reference, '{%s}DigestMethod' % sig_ns)
        digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        # Calculate digest without signature
        element_copy = etree.Element(element.tag, element.attrib, nsmap=element.nsmap)
        for child in element:
            if not child.tag.endswith('Signature'):
                element_copy.append(child)
        
        digest_value = etree.SubElement(reference, '{%s}DigestValue' % sig_ns)
        digest_value.text = base64.b64encode(hashlib.sha1(canonicalize(element_copy)).digest()).decode()
        
        # Sign
        sig_value = etree.SubElement(signature, '{%s}SignatureValue' % sig_ns)
        sig_value.text = base64.b64encode(self.fiel.sign_sha1(canonicalize(signed_info))).decode()
        
        # KeyInfo
        key_info = etree.SubElement(signature, '{%s}KeyInfo' % sig_ns)
        x509_data = etree.SubElement(key_info, '{%s}X509Data' % sig_ns)
        x509_issuer = etree.SubElement(x509_data, '{%s}X509IssuerSerial' % sig_ns)
        
        issuer_name = etree.SubElement(x509_issuer, '{%s}X509IssuerName' % sig_ns)
        issuer = self.fiel.certificate.issuer
        issuer_parts = []
        for attr in reversed(list(issuer)):
            issuer_parts.append(f"{attr.oid._name}={attr.value}")
        issuer_name.text = ','.join(issuer_parts)
        
        serial = etree.SubElement(x509_issuer, '{%s}X509SerialNumber' % sig_ns)
        serial.text = str(self.fiel.certificate.serial_number)
    
    async def descargar_paquete(self, id_paquete: str) -> Dict:
        """Download a package of CFDIs"""
        
        if not self.token:
            auth_result = await self.authenticate()
            if not auth_result.get('success'):
                return auth_result
        
        try:
            # Build download SOAP
            envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope', nsmap={
                's': 'http://schemas.xmlsoap.org/soap/envelope/',
                'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
            })
            
            header = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
            body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
            
            peticion = etree.SubElement(body, '{http://DescargaMasivaTerceros.sat.gob.mx}PeticionDescargaMasivaTercerosEntrada')
            pet_descarga = etree.SubElement(peticion, '{http://DescargaMasivaTerceros.sat.gob.mx}peticionDescarga')
            pet_descarga.set('IdPaquete', id_paquete)
            pet_descarga.set('RfcSolicitante', self.fiel.rfc)
            
            # Add signature
            self._sign_element(pet_descarga)
            
            soap_request = etree.tostring(envelope, xml_declaration=True, encoding='UTF-8')
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar',
                'Authorization': f'WRAP access_token="{self.token}"'
            }
            
            response = requests.post(SAT_DESCARGA_URL, data=soap_request, headers=headers, timeout=120)
            
            if response.status_code == 200:
                root = etree.fromstring(response.content)
                
                result = root.find('.//{http://DescargaMasivaTerceros.sat.gob.mx}RespuestaDescargaMasivaTercerosSalida')
                if result is not None:
                    cod_estatus = result.get('CodEstatus')
                    paquete_b64 = result.get('Paquete')
                    
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
        """Validate and save FIEL credentials"""
        try:
            # Validate FIEL
            fiel = FIELManager(cer_content, key_content, password)
            
            if not fiel.is_valid():
                return {
                    'success': False,
                    'error': f'El certificado FIEL ha expirado. Válido hasta: {fiel.not_after}'
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
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada para esta empresa'}
        
        if not fiel.is_valid():
            return {'success': False, 'error': 'El certificado FIEL ha expirado'}
        
        ws = SATWebService(fiel)
        result = await ws.authenticate()
        
        if result.get('success'):
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
        """Request CFDI download"""
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
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel)
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
        fiel = await self.credential_manager.get_fiel(company_id)
        if not fiel:
            return {'success': False, 'error': 'No hay FIEL configurada'}
        
        ws = SATWebService(fiel)
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
