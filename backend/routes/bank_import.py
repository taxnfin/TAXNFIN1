"""Bank transaction import (Excel and PDF) routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Form
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import uuid
import io
import re
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log
from models.enums import UserRole, BankTransactionType

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/bank-transactions/import")
async def import_bank_statement(request: Request, file: UploadFile = File(...), bank_account_id: str = Form(...), current_user: Dict = Depends(get_current_user)):
    """Import bank statement from Excel"""
    import pandas as pd
    import io
    
    company_id = await get_active_company_id(request, current_user)
    
    # Verify bank account
    account = await db.bank_accounts.find_one({'id': bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx, .xls)")
    
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    
    # Only require minimal columns - saldo is OPTIONAL
    required_cols = ['fecha_movimiento', 'descripcion', 'monto']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Columnas faltantes: {', '.join(missing)}")
    
    imported = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            # Parse fecha_movimiento - handle different formats
            fecha_mov = row['fecha_movimiento']
            if pd.isna(fecha_mov):
                errors.append(f"Fila {idx + 2}: fecha_movimiento vacía")
                continue
            
            # Convert to string and handle datetime objects
            if hasattr(fecha_mov, 'strftime'):
                fecha_str = fecha_mov.strftime('%Y-%m-%d')
            else:
                fecha_str = str(fecha_mov)[:19]
            
            # Parse monto
            monto = row['monto']
            if pd.isna(monto):
                errors.append(f"Fila {idx + 2}: monto vacío")
                continue
            monto = float(monto)
            
            # Determine tipo_movimiento from monto sign or column
            tipo_mov = 'credito'
            if 'tipo_movimiento' in df.columns and not pd.isna(row.get('tipo_movimiento')):
                tipo_mov = str(row['tipo_movimiento']).lower().strip()
                if tipo_mov in ['debito', 'débito', 'cargo', 'retiro', 'egreso']:
                    tipo_mov = 'debito'
                else:
                    tipo_mov = 'credito'
            elif monto < 0:
                tipo_mov = 'debito'
                monto = abs(monto)
            
            # Get description
            descripcion = row['descripcion']
            if pd.isna(descripcion):
                descripcion = 'Movimiento bancario'
            descripcion = str(descripcion)[:500]
            
            # Get optional saldo
            saldo = 0
            if 'saldo' in df.columns and not pd.isna(row.get('saldo')):
                try:
                    saldo = float(row['saldo'])
                except:
                    saldo = 0
            
            # Get optional fecha_valor
            fecha_valor = fecha_str
            if 'fecha_valor' in df.columns and not pd.isna(row.get('fecha_valor')):
                fv = row['fecha_valor']
                if hasattr(fv, 'strftime'):
                    fecha_valor = fv.strftime('%Y-%m-%d')
                else:
                    fecha_valor = str(fv)[:19]
            
            txn = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'bank_account_id': bank_account_id,
                'fecha_movimiento': fecha_str,
                'fecha_valor': fecha_valor,
                'descripcion': descripcion,
                'referencia': str(row.get('referencia', '')) if not pd.isna(row.get('referencia')) else '',
                'monto': monto,
                'tipo_movimiento': tipo_mov,
                'saldo': saldo,
                'conciliado': False,
                'estado_conciliacion': 'pendiente',
                'categoria': str(row.get('categoria', '')) if not pd.isna(row.get('categoria')) else '',
                'notas': str(row.get('notas', '')) if not pd.isna(row.get('notas')) else '',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            await db.bank_transactions.insert_one(txn)
            imported += 1
        except Exception as e:
            errors.append(f"Fila {idx + 2}: {str(e)}")
    
    return {
        'status': 'success',
        'importados': imported,
        'errores': len(errors),
        'detalle_errores': errors[:10]
    }


def parse_bank_statement_pdf(pdf_content: bytes, bank_name: str = "auto") -> List[Dict]:
    """
    Parse bank statement PDF and extract transactions.
    Supports: Banorte, BBVA, Santander, HSBC, and generic formats.
    """
    import pdfplumber
    import re
    from datetime import datetime
    
    transactions = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            full_text = ""
            all_tables = []
            
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"
                
                # Extract tables from each page
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
            
            # Try to detect bank from content
            detected_bank = bank_name
            if bank_name == "auto":
                text_lower = full_text.lower()
                if "banbajio" in text_lower or "bajio" in text_lower or "banco del bajio" in text_lower:
                    detected_bank = "banbajio"
                elif "banorte" in text_lower:
                    detected_bank = "banorte"
                elif "bbva" in text_lower or "bancomer" in text_lower:
                    detected_bank = "bbva"
                elif "santander" in text_lower:
                    detected_bank = "santander"
                elif "hsbc" in text_lower:
                    detected_bank = "hsbc"
                elif "scotiabank" in text_lower:
                    detected_bank = "scotiabank"
                elif "banamex" in text_lower or "citibanamex" in text_lower:
                    detected_bank = "banamex"
                else:
                    detected_bank = "generic"
            
            # Try extracting saldo inicial from text
            saldo_inicial = None
            saldo_patterns = [
                r'SALDO\s+INICIAL[:\s]+\$?\s*([\d,]+\.?\d*)',
                r'SALDO\s+ANTERIOR[:\s]+\$?\s*([\d,]+\.?\d*)',
                r'SALDO\s+AL\s+\d+[:\s]+\$?\s*([\d,]+\.?\d*)',
            ]
            for pattern in saldo_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    saldo_str = match.group(1).replace(',', '')
                    saldo_inicial = float(saldo_str)
                    break
            
            # Parse based on detected bank
            if detected_bank == "banbajio":
                transactions = parse_banbajio_pdf(full_text, all_tables, pdf, saldo_inicial)
            elif detected_bank in ["banorte", "bbva", "santander", "hsbc", "banamex", "scotiabank"]:
                transactions = parse_mexican_bank_pdf(full_text, all_tables, pdf, saldo_inicial)
            else:
                transactions = parse_mexican_bank_pdf(full_text, all_tables, pdf, saldo_inicial)
            
    except Exception as e:
        logging.error(f"Error parsing PDF: {str(e)}")
        raise
    
    return transactions


def parse_banbajio_pdf(text: str, tables: List, pdf, saldo_inicial: float = None) -> List[Dict]:
    """
    Parser específico para estados de cuenta de BanBajío.
    Formato: DD MMM | Descripción | Referencia | Depósitos | Retiros | Saldo
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    # Try to extract year from PDF text (look for patterns like "DICIEMBRE 2025" or "DIC 2025")
    year_match = re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[A-Z]*\s*(\d{4})', text.upper())
    if year_match:
        current_year = int(year_match.group(2))
    else:
        # Also try "PERIODO: ... 2025" pattern
        period_match = re.search(r'PERIODO[:\s]+.*?(\d{4})', text.upper())
        if period_match:
            current_year = int(period_match.group(1))
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    # Skip keywords for summary/header rows
    skip_keywords = [
        'SALDO INICIAL', 'SALDO ANTERIOR', 'SALDO FINAL', 'SALDO AL',
        'TOTAL', 'RESUMEN', 'MOVIMIENTOS', 'DESCRIPCION', 'FECHA',
        'REFERENCIA', 'ABONOS', 'CARGOS', 'DEPOSITOS', 'RETIROS',
        'PROMEDIO', 'PERIODO', 'ESTADO DE CUENTA', 'CLIENTE', 'RFC'
    ]
    
    def clean_description(desc: str) -> str:
        """Clean up description by removing extra spaces between characters"""
        # Remove pattern like "C O M I S I O N" -> "COMISION"
        # Also handle "CO MISION" -> "COMISION"
        
        # First, try to detect and fix space-separated text
        # Pattern: uppercase letters separated by single spaces at the start
        if re.match(r'^[A-Z][A-Z\s]{3,}', desc):
            # Count ratio of spaces to letters
            letters = len(re.findall(r'[A-Za-z]', desc[:20]))
            spaces = len(re.findall(r'\s', desc[:20]))
            
            if spaces > 0 and letters / (spaces + letters) < 0.6:
                # Lots of spaces - likely space-separated
                cleaned = re.sub(r'(\w)\s+(?=\w)', r'\1', desc)
                return cleaned
        
        # Also fix common patterns like "CO MISION" -> "COMISION"
        common_fixes = [
            (r'CO\s+MISION', 'COMISION'),
            (r'IVA\s+CO', 'IVA CO'),
            (r'EN\s+VÍO', 'ENVÍO'),
            (r'EN\s+VIO', 'ENVIO'),
            (r'DE\s+POSITO', 'DEPOSITO'),
            (r'PA\s+GO', 'PAGO'),
            (r'RE\s+TIRO', 'RETIRO'),
            (r'TRANS\s+FERENCIA', 'TRANSFERENCIA'),
        ]
        for pattern, replacement in common_fixes:
            desc = re.sub(pattern, replacement, desc, flags=re.IGNORECASE)
        
        return desc
    
    def extract_amount(val: str) -> float:
        """Extract numeric amount from string"""
        if not val:
            return 0
        val = re.sub(r'[^\d.,\-]', '', str(val))
        val = val.replace(',', '')
        try:
            return float(val)
        except:
            return 0
    
    # Process line by line - BanBajío format
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        line_upper = line.upper()
        
        # Skip header/summary rows
        if any(skip in line_upper for skip in skip_keywords):
            continue
        
        # BanBajío format: "DD MMM DESCRIPCION ... $MONTO $SALDO" or with reference
        # Pattern 1: DD MMM at start (e.g., "1 DIC", "15 ENE", "31 DIC")
        date_match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(.+)', line, re.IGNORECASE)
        
        if not date_match:
            continue
        
        day = int(date_match.group(1))
        month = date_match.group(2).upper()
        rest_of_line = date_match.group(3)
        
        # Validate date
        if day < 1 or day > 31 or month not in months_es:
            continue
        
        fecha = f"{current_year}-{months_es[month]}-{str(day).zfill(2)}"
        
        # Extract all amounts from the line (format: numbers with decimals like 1,234.56 or 1234.56)
        amounts = re.findall(r'([\d,]+\.\d{2})', rest_of_line)
        amounts = [float(a.replace(',', '')) for a in amounts]
        
        if len(amounts) < 1:
            continue
        
        # Extract description - everything before the first amount
        first_amount_pos = rest_of_line.find(str(int(amounts[0])).replace(',', '').split('.')[0] if amounts else '')
        if first_amount_pos == -1:
            first_amount_match = re.search(r'[\d,]+\.\d{2}', rest_of_line)
            first_amount_pos = first_amount_match.start() if first_amount_match else len(rest_of_line)
        
        descripcion = rest_of_line[:first_amount_pos].strip()
        
        # Clean description - remove trailing reference numbers
        descripcion = re.sub(r'\s+\d{5,}$', '', descripcion)  # Remove trailing long numbers
        descripcion = descripcion.strip()
        
        # Determine deposit vs withdrawal based on amounts
        deposito = 0
        retiro = 0
        saldo = 0
        
        # BanBajío typically has: DEPOSITO | RETIRO | SALDO (3 amounts)
        # or just: MONTO | SALDO (2 amounts)
        if len(amounts) >= 3:
            # Last amount is saldo, one of the previous two is the movement
            saldo = amounts[-1]
            
            # Check which column has the movement based on position in text
            # Find positions of amounts in text
            amount_positions = []
            for amt in amounts[:-1]:  # Exclude saldo
                amt_str = f"{amt:,.2f}".replace(',', '')
                pos = rest_of_line.rfind(amt_str[:6])  # Use first 6 chars to find
                amount_positions.append((amt, pos))
            
            # Sort by position
            amount_positions.sort(key=lambda x: x[1])
            
            if len(amount_positions) >= 2:
                # First non-zero is the movement
                for amt, pos in amount_positions:
                    if amt > 0:
                        # Determine if deposit or withdrawal by description
                        desc_upper = descripcion.upper()
                        if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'DEVOLUCION', 'SPEI:', 'TRASPASO DE RECURSOS A']):
                            if 'ENVÍO SPEI' in desc_upper or 'ENVIO SPEI' in desc_upper:
                                retiro = amt  # Envío SPEI es retiro
                            else:
                                deposito = amt
                        elif any(kw in desc_upper for kw in ['COMISION', 'IVA ', 'PAGO ', 'ENVÍO', 'ENVIO', 'RETIRO', 'COMPRA', 'CARGO']):
                            retiro = amt
                        else:
                            # If description has "POR OPERACION CAMBIOS" it's usually a deposit
                            if 'OPERACION CAMBIOS' in desc_upper:
                                deposito = amt
                            else:
                                retiro = amt
                        break
        elif len(amounts) == 2:
            # MONTO | SALDO
            monto = amounts[0]
            saldo = amounts[1]
            
            # Determine type by description
            desc_upper = descripcion.upper()
            deposit_keywords = ['DEPOSITO', 'DEPÓSITO', 'ABONO', 'DEVOLUCION', 'DEVOLUCIÓN']
            withdrawal_keywords = ['COMISION', 'COMISIÓN', 'IVA ', 'PAGO ', 'ENVÍO', 'ENVIO', 'RETIRO', 
                                   'COMPRA', 'CARGO', 'TRASPASO DE RECURSOS A', 'DOMICILIACION']
            
            # SPEI transactions
            if 'SPEI' in desc_upper:
                if 'ENVÍO SPEI' in desc_upper or 'ENVIO SPEI' in desc_upper:
                    retiro = monto  # Envío = outgoing
                elif 'DEPÓSITO SPEI' in desc_upper or 'DEPOSITO SPEI' in desc_upper:
                    deposito = monto
                elif 'DEVOLUCIÓN' in desc_upper or 'DEVOLUCION' in desc_upper:
                    deposito = monto
                else:
                    retiro = monto  # Default SPEI to withdrawal
            elif any(kw in desc_upper for kw in deposit_keywords):
                deposito = monto
            elif any(kw in desc_upper for kw in withdrawal_keywords):
                retiro = monto
            elif 'OPERACION CAMBIOS' in desc_upper:
                deposito = monto  # Currency exchange deposit
            else:
                retiro = monto  # Default to withdrawal for unclassified
        elif len(amounts) == 1:
            # Just one amount - try to determine from description
            monto = amounts[0]
            desc_upper = descripcion.upper()
            
            if any(kw in desc_upper for kw in ['DEPOSITO', 'DEPÓSITO', 'ABONO']):
                deposito = monto
            else:
                retiro = monto
            saldo = 0
        
        # Only add if we have a movement
        if deposito > 0 or retiro > 0:
            # Clean description
            descripcion_clean = clean_description(descripcion)
            transactions.append({
                'fecha': fecha,
                'descripcion': descripcion_clean[:300] or 'Movimiento bancario',
                'deposito': deposito,
                'retiro': retiro,
                'saldo': saldo,
                'referencia': ''
            })
    
    return transactions


def parse_mexican_bank_pdf(text: str, tables: List, pdf, saldo_inicial: float = None) -> List[Dict]:
    """
    Universal parser for Mexican bank PDFs.
    Enhanced to better handle BanBajío and other Mexican bank formats.
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12',
        'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
        'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
        'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
    }
    
    def is_valid_date(day: int, month: str) -> bool:
        """Check if day and month are valid"""
        if month.upper() not in months_es:
            return False
        if day < 1 or day > 31:
            return False
        return True
    
    def parse_date(date_str: str) -> str:
        """Parse date from various formats: DD MMM, DD/MM/YYYY, YYYY-MM-DD"""
        date_str = date_str.strip()
        
        # Format: DD MMM (e.g., "1 DIC", "15 ENE")
        match = re.match(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', date_str.upper())
        if match:
            day = int(match.group(1))
            month = months_es.get(match.group(2), '01')
            return f"{current_year}-{month}-{str(day).zfill(2)}"
        
        # Format: DD/MM/YYYY or DD-MM-YYYY
        match = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_str)
        if match:
            day = match.group(1).zfill(2)
            month = match.group(2).zfill(2)
            year = match.group(3)
            if len(year) == 2:
                year = f"20{year}"
            return f"{year}-{month}-{day}"
        
        # Format: YYYY-MM-DD
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            return date_str
        
        return None
    
    def extract_amount(val: str) -> float:
        """Extract numeric amount from string, handling various formats"""
        if not val:
            return 0
        # Remove currency symbols and spaces
        val = re.sub(r'[^\d.,\-]', '', str(val))
        # Handle negative values
        is_negative = '-' in val
        val = val.replace('-', '')
        # Handle comma as thousands separator
        if ',' in val and '.' in val:
            val = val.replace(',', '')
        elif ',' in val:
            # Could be decimal separator or thousands
            parts = val.split(',')
            if len(parts[-1]) == 2:  # Likely decimal
                val = val.replace(',', '.')
            else:  # Thousands separator
                val = val.replace(',', '')
        try:
            amount = float(val)
            return -amount if is_negative else amount
        except:
            return 0
    
    # Words to skip - these are summary/header lines
    skip_keywords = [
        'SALDO INICIAL', 'SALDO ANTERIOR', 'SALDO FINAL', 'SALDO AL',
        'TOTAL', 'RESUMEN', 'DEPOSITOS', 'RETIROS', 'CARGOS',
        'FECHA', 'NO. REF', 'DESCRIPCION', 'OPERACION', 'CONCEPTO',
        '(+)', '(-)', 'PROMEDIO', 'MENSUAL', 'MINIMO', 'PERIODO',
        'ESTADO DE CUENTA', 'CUENTA', 'CLIENTE', 'RFC', 'DOMICILIO'
    ]
    
    # First try to extract from tables (more structured)
    if tables:
        for table in tables:
            if not table:
                continue
            for row in table:
                if not row or len(row) < 3:
                    continue
                
                # Convert all cells to strings
                row_str = [str(cell).strip() if cell else '' for cell in row]
                row_joined = ' '.join(row_str).upper()
                
                # Skip header/summary rows
                if any(skip in row_joined for skip in skip_keywords):
                    continue
                
                # Try to find date in first few cells
                fecha = None
                for i, cell in enumerate(row_str[:3]):
                    fecha = parse_date(cell)
                    if fecha:
                        break
                
                if not fecha:
                    continue
                
                # Extract description (usually longest non-numeric field)
                descripcion = ""
                amounts = []
                
                for cell in row_str:
                    # Check if it's a numeric value
                    cell_clean = re.sub(r'[^\d.,\-]', '', cell)
                    if cell_clean and re.match(r'^-?[\d,]+\.?\d*$', cell_clean.replace(',', '')):
                        amt = extract_amount(cell)
                        if amt != 0:
                            amounts.append(amt)
                    elif len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                        descripcion = cell
                
                if not amounts or not descripcion:
                    continue
                
                # Determine deposit vs withdrawal
                deposito = 0
                retiro = 0
                saldo = abs(amounts[-1]) if len(amounts) > 1 else 0
                
                if len(amounts) >= 3:
                    # Format: ... | DEPOSITO | RETIRO | SALDO
                    dep_val = amounts[-3]
                    ret_val = amounts[-2]
                    if dep_val > 0 and ret_val == 0:
                        deposito = dep_val
                    elif ret_val > 0 and dep_val == 0:
                        retiro = ret_val
                    elif dep_val > 0:
                        deposito = dep_val
                elif len(amounts) >= 2:
                    monto = amounts[-2]
                    # Use description to guess type
                    desc_upper = descripcion.upper()
                    deposit_keywords = ['DEPOSITO', 'ABONO', 'INGRESO', 'TRANSFERENCIA RECIBIDA', 'PAGO RECIBIDO', 'CREDITO']
                    withdrawal_keywords = ['RETIRO', 'CARGO', 'PAGO', 'COMISION', 'IVA', 'TRANSFERENCIA ENVIADA', 'DEBITO']
                    
                    if any(kw in desc_upper for kw in deposit_keywords):
                        deposito = abs(monto)
                    elif any(kw in desc_upper for kw in withdrawal_keywords):
                        retiro = abs(monto)
                    elif monto < 0:
                        retiro = abs(monto)
                    else:
                        deposito = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion[:200].strip() or 'Movimiento bancario',
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
    
    # If no transactions from tables, try line-by-line parsing
    if not transactions:
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            line_upper = line.upper()
            
            # Skip summary and header lines
            if any(skip in line_upper for skip in skip_keywords):
                continue
            
            # Try multiple date patterns
            fecha = None
            rest_of_line = line
            
            # Pattern 1: DD MMM at start
            match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(.+)', line, re.IGNORECASE)
            if match:
                day = int(match.group(1))
                month = match.group(2).upper()
                if is_valid_date(day, month):
                    fecha = f"{current_year}-{months_es[month]}-{str(day).zfill(2)}"
                    rest_of_line = match.group(3)
            
            # Pattern 2: DD/MM/YYYY at start
            if not fecha:
                match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s+(.+)', line)
                if match:
                    fecha = parse_date(f"{match.group(1)}/{match.group(2)}/{match.group(3)}")
                    rest_of_line = match.group(4)
            
            if not fecha:
                continue
            
            # Extract amounts
            amounts = re.findall(r'([\d,]+\.\d{2})', rest_of_line)
            amounts = [float(a.replace(',', '')) for a in amounts]
            
            if len(amounts) < 1:
                continue
            
            # Get description
            first_amount_match = re.search(r'[\d,]+\.\d{2}', rest_of_line)
            if first_amount_match:
                descripcion = rest_of_line[:first_amount_match.start()].strip()
            else:
                descripcion = rest_of_line[:50]
            
            # Clean description
            descripcion = re.sub(r'^\d+\s+', '', descripcion).strip()
            
            # Determine deposit vs withdrawal
            deposito = 0
            retiro = 0
            saldo = amounts[-1] if len(amounts) > 1 else 0
            
            if len(amounts) >= 3:
                dep_val = amounts[-3]
                ret_val = amounts[-2]
                if dep_val > 0 and (ret_val == 0 or ret_val == saldo):
                    deposito = dep_val
                elif ret_val > 0 and (dep_val == 0 or dep_val == saldo):
                    retiro = ret_val
            elif len(amounts) >= 2:
                monto = amounts[0]
                desc_upper = descripcion.upper()
                if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'INGRESO', 'RECIBID']):
                    deposito = monto
                else:
                    retiro = monto
            elif len(amounts) == 1:
                # Single amount - try to determine from description
                monto = amounts[0]
                desc_upper = descripcion.upper()
                if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'INGRESO', 'RECIBID', 'TRANSFERENCIA']):
                    deposito = monto
                else:
                    retiro = monto
                saldo = 0
            
            if deposito > 0 or retiro > 0:
                transactions.append({
                    'fecha': fecha,
                    'descripcion': descripcion[:200] or 'Movimiento bancario',
                    'deposito': deposito,
                    'retiro': retiro,
                    'saldo': saldo,
                    'referencia': ''
                })
    
    return transactions


def parse_banorte_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """
    Parse Banorte bank statement format.
    Column order: FECHA | NO. REF. | DESCRIPCION | DEPOSITOS | RETIROS | SALDO
    
    Key insight: Determine deposit vs withdrawal based on COLUMN POSITION,
    not by description keywords. If amount is in DEPOSITOS column -> deposit.
    If amount is in RETIROS column -> withdrawal.
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    def parse_amount(cell: str) -> float:
        """Parse a monetary amount from a cell"""
        if not cell or not cell.strip():
            return 0
        # Remove $ and spaces, replace comma thousands separator
        clean = re.sub(r'[\$\s]', '', str(cell))
        clean = clean.replace(',', '')
        try:
            val = float(clean) if clean else 0
            return val if val > 0 else 0
        except:
            return 0
    
    # Process tables - looking for transaction tables with DEPOSITOS/RETIROS columns
    for table in tables:
        if not table or len(table) < 2:
            continue
        
        # Find header row and identify column positions
        header_row = None
        header_idx = 0
        deposito_col = None
        retiro_col = None
        saldo_col = None
        
        # Search for header in first few rows
        for idx, row in enumerate(table[:3]):
            if not row:
                continue
            row_text = ' '.join([str(cell or '').upper() for cell in row])
            
            # Check if this row contains column headers
            if 'DEPOSITO' in row_text or 'RETIRO' in row_text:
                header_row = row
                header_idx = idx
                
                # Find exact column indices
                for col_idx, cell in enumerate(row):
                    cell_upper = str(cell or '').upper().strip()
                    if 'DEPOSITO' in cell_upper:
                        deposito_col = col_idx
                    elif 'RETIRO' in cell_upper or 'CARGO' in cell_upper:
                        retiro_col = col_idx
                    elif 'SALDO' in cell_upper:
                        saldo_col = col_idx
                break
        
        # If we found column positions, process data rows
        if deposito_col is not None or retiro_col is not None:
            for row in table[header_idx + 1:]:
                if not row or not any(row):
                    continue
                
                try:
                    row_cleaned = [str(cell or '').strip() for cell in row]
                    row_text = ' '.join(row_cleaned).upper()
                    
                    # Skip header-like rows
                    if 'SALDO INICIAL' in row_text or 'SALDO ANTERIOR' in row_text:
                        continue
                    if 'FECHA' in row_text and 'DEPOSITO' in row_text:
                        continue
                    
                    # Extract date from any cell
                    fecha = None
                    for cell in row_cleaned:
                        # Pattern: DD MMM (e.g., "01 DIC", "15 ENE", "1DIC")
                        date_match = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', cell.upper())
                        if date_match:
                            day = date_match.group(1).zfill(2)
                            month = months_es.get(date_match.group(2), '01')
                            fecha = f"{current_year}-{month}-{day}"
                            break
                        # Pattern: DD/MM/YYYY
                        date_match2 = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', cell)
                        if date_match2:
                            day = date_match2.group(1).zfill(2)
                            month = date_match2.group(2).zfill(2)
                            year = date_match2.group(3)
                            if len(year) == 2:
                                year = f"20{year}"
                            fecha = f"{year}-{month}-{day}"
                            break
                    
                    if not fecha:
                        continue
                    
                    # Extract amounts from specific columns
                    deposito = 0
                    retiro = 0
                    saldo = 0
                    
                    if deposito_col is not None and deposito_col < len(row_cleaned):
                        deposito = parse_amount(row_cleaned[deposito_col])
                    
                    if retiro_col is not None and retiro_col < len(row_cleaned):
                        retiro = parse_amount(row_cleaned[retiro_col])
                    
                    if saldo_col is not None and saldo_col < len(row_cleaned):
                        saldo = parse_amount(row_cleaned[saldo_col])
                    
                    # Get description - find the longest text that's not a number
                    descripcion = ""
                    for idx, cell in enumerate(row_cleaned):
                        # Skip amount columns
                        if idx in [deposito_col, retiro_col, saldo_col]:
                            continue
                        if cell and len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                            descripcion = cell
                    
                    # Only add if we have an actual movement
                    if deposito > 0 or retiro > 0:
                        transactions.append({
                            'fecha': fecha,
                            'descripcion': descripcion or 'Movimiento bancario',
                            'deposito': deposito,
                            'retiro': retiro,
                            'saldo': saldo,
                            'referencia': ''
                        })
                        
                except Exception:
                    continue
        
        else:
            # No clear column headers - try position-based parsing
            # In Banorte PDFs, columns are typically: FECHA | REF | DESC | DEPOSITOS | RETIROS | SALDO
            # The last 3 numeric columns are amounts
            for row in table[1:]:
                if not row or not any(row):
                    continue
                
                try:
                    row_cleaned = [str(cell or '').strip() for cell in row]
                    row_text = ' '.join(row_cleaned).upper()
                    
                    # Skip headers and saldo inicial
                    if any(kw in row_text for kw in ['SALDO INICIAL', 'SALDO ANTERIOR', 'FECHA', 'DEPOSITO']):
                        continue
                    
                    # Extract date
                    fecha = None
                    for cell in row_cleaned:
                        date_match = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', cell.upper())
                        if date_match:
                            day = date_match.group(1).zfill(2)
                            month = months_es.get(date_match.group(2), '01')
                            fecha = f"{current_year}-{month}-{day}"
                            break
                    
                    if not fecha:
                        continue
                    
                    # Find all amount cells and their positions
                    amount_cells = []
                    for idx, cell in enumerate(row_cleaned):
                        val = parse_amount(cell)
                        if val > 0:
                            amount_cells.append((idx, val))
                    
                    if len(amount_cells) < 1:
                        continue
                    
                    # Get description
                    descripcion = ""
                    for cell in row_cleaned:
                        if cell and len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                            descripcion = cell
                    
                    # With 3 amounts: DEPOSITO, RETIRO, SALDO
                    # With 2 amounts: either (DEPOSITO, SALDO) or (RETIRO, SALDO)
                    # With 1 amount: just SALDO (skip) or need keyword detection
                    
                    deposito = 0
                    retiro = 0
                    saldo = 0
                    
                    if len(amount_cells) >= 3:
                        # Last 3 are: DEPOSITO, RETIRO, SALDO
                        deposito = amount_cells[-3][1]
                        retiro = amount_cells[-2][1]
                        saldo = amount_cells[-1][1]
                    elif len(amount_cells) == 2:
                        # Could be (DEP, SALDO) or (RET, SALDO)
                        # Check column position - if first amount is more to the left, likely DEPOSITO column
                        first_col = amount_cells[0][0]
                        num_cols = len(row_cleaned)
                        
                        # If first amount is in first half, likely deposit
                        # If in second half (closer to SALDO), likely retiro
                        if first_col < num_cols * 0.6:
                            deposito = amount_cells[0][1]
                        else:
                            retiro = amount_cells[0][1]
                        saldo = amount_cells[-1][1]
                    
                    if deposito > 0 or retiro > 0:
                        transactions.append({
                            'fecha': fecha,
                            'descripcion': descripcion or 'Movimiento bancario',
                            'deposito': deposito,
                            'retiro': retiro,
                            'saldo': saldo,
                            'referencia': ''
                        })
                        
                except Exception:
                    continue
    
    # If no transactions from tables, try line-by-line text parsing
    if not transactions:
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(kw in line.upper() for kw in ['SALDO INICIAL', 'SALDO ANTERIOR', 'FECHA']):
                continue
            
            # Find date at start
            date_match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\b', line.upper())
            if not date_match:
                continue
            
            day = date_match.group(1).zfill(2)
            month = months_es.get(date_match.group(2), '01')
            fecha = f"{current_year}-{month}-{day}"
            
            rest = line[date_match.end():].strip()
            
            # Find all amounts
            amounts = re.findall(r'\$?\s*([\d,]+\.\d{2})', rest)
            amounts = [float(a.replace(',', '')) for a in amounts if a]
            
            if len(amounts) < 2:
                continue
            
            # Description is text before first amount
            first_amt = re.search(r'\$?\s*[\d,]+\.\d{2}', rest)
            descripcion = rest[:first_amt.start()].strip() if first_amt else rest[:50]
            
            # Parse based on number of amounts
            deposito = 0
            retiro = 0
            saldo = amounts[-1]
            
            if len(amounts) >= 3:
                deposito = amounts[-3]
                retiro = amounts[-2]
            elif len(amounts) == 2:
                # Single movement amount - use keyword detection as fallback
                monto = amounts[0]
                normalized_desc = normalize_text_for_keywords(descripcion)
                is_dep = is_deposit_transaction(normalized_desc)
                if is_dep is True:
                    deposito = monto
                else:
                    retiro = monto
            
            if deposito > 0 or retiro > 0:
                transactions.append({
                    'fecha': fecha,
                    'descripcion': descripcion or 'Movimiento bancario',
                    'deposito': deposito,
                    'retiro': retiro,
                    'saldo': saldo,
                    'referencia': ''
                })
    
    return transactions


def parse_bbva_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse BBVA bank statement format"""
    return parse_generic_pdf(text, tables, saldo_inicial)


# Keywords for deposit/withdrawal detection (shared across parsers)
DEPOSIT_KEYWORDS = [
    'DEPOSITO', 'ABONO', 'TRANSFERENCIA RECIBIDA', 'SPEI REC', 
    'PAGO RECIBIDO', 'DEP ', 'COBRANZA', 'INGRESO', 'CREDITO',
    'RECEPCION', 'BONIFICACION', 'DEVOLUCION', 'REEMBOLSO',
    'TRANSFER IN', 'CREDIT', 'NOMINA', 'INTERES GANADO'
]

WITHDRAWAL_KEYWORDS = [
    'RETIRO', 'CARGO', 'COMISION', 'IVA ', 'PAGO ', 'TRANSFERENCIA ENV',
    'SPEI ENV', 'SERVICIO', 'ENVIO', 'DISPOSICION', 'CHEQUE',
    'DOMICILIACION', 'ANUALIDAD', 'MANEJO', 'TRASPASO', 'COMPRA',
    'TRANSFER OUT', 'DEBIT', 'FEE', 'PAYMENT'
]


def normalize_text_for_keywords(text: str) -> str:
    """
    Normalize text by removing single-space separations between letters.
    This handles PDFs that have 'D E P O S I T O' instead of 'DEPOSITO'.
    """
    import re
    
    if not text:
        return ""
    
    # Pattern to match single letters separated by single spaces
    # e.g., "D E P O S I T O" -> "DEPOSITO"
    # But preserve multi-letter words: "PAGO DE SERVICIO" stays as is
    
    result = text.upper()
    
    # Replace patterns like "A B C" (single letters with spaces) with "ABC"
    # This regex finds sequences of single letters separated by single spaces
    pattern = r'\b([A-Z])\s+(?=[A-Z]\b)'
    
    # Keep replacing until no more changes
    prev = ""
    while prev != result:
        prev = result
        result = re.sub(pattern, r'\1', result)
    
    return result


def is_deposit_transaction(desc: str) -> bool:
    """Determine if transaction is a deposit based on description keywords"""
    # Normalize text to handle spaced-out letters like "D E POSITO"
    normalized = normalize_text_for_keywords(desc)
    
    # Check for deposit keywords
    for kw in DEPOSIT_KEYWORDS:
        if kw in normalized:
            return True
    
    # Check for withdrawal keywords
    for kw in WITHDRAWAL_KEYWORDS:
        if kw in normalized:
            return False
    
    return None  # Unknown - will default to withdrawal


def parse_generic_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """
    Parse generic bank statement with common patterns.
    Uses column position detection first, then falls back to keyword detection.
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    def parse_amount(cell: str) -> float:
        """Parse a monetary amount from a cell"""
        if not cell or not cell.strip():
            return 0
        clean = re.sub(r'[\$\s]', '', str(cell))
        clean = clean.replace(',', '')
        try:
            val = float(clean) if clean else 0
            return val if val > 0 else 0
        except:
            return 0
    
    # Common date patterns
    date_patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # DD/MM/YYYY or DD-MM-YYYY
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',    # YYYY-MM-DD
    ]
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    # Try table extraction first
    for table in tables:
        if not table or len(table) < 2:
            continue
        
        # Look for header row with column names
        deposito_col = None
        retiro_col = None
        cargo_col = None
        abono_col = None
        saldo_col = None
        header_idx = 0
        
        for idx, row in enumerate(table[:3]):
            if not row:
                continue
            row_text = ' '.join([str(cell or '').upper() for cell in row])
            
            if any(kw in row_text for kw in ['DEPOSITO', 'RETIRO', 'CARGO', 'ABONO', 'SALDO']):
                header_idx = idx
                for col_idx, cell in enumerate(row):
                    cell_upper = str(cell or '').upper()
                    if 'DEPOSITO' in cell_upper or 'ABONO' in cell_upper:
                        deposito_col = col_idx
                    elif 'RETIRO' in cell_upper or 'CARGO' in cell_upper:
                        retiro_col = col_idx
                    elif 'SALDO' in cell_upper:
                        saldo_col = col_idx
                break
        
        # Process data rows
        for row in table[header_idx + 1:]:
            if not row or not any(row):
                continue
            
            try:
                row_str = ' '.join([str(cell or '') for cell in row])
                row_cleaned = [str(cell or '').strip() for cell in row]
                
                # Skip header-like rows
                if any(kw in row_str.upper() for kw in ['SALDO INICIAL', 'SALDO ANTERIOR', 'FECHA', 'DEPOSITO']):
                    continue
                
                # Find date
                fecha = None
                for cell in row_cleaned:
                    # Spanish month format
                    date_match = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', cell.upper())
                    if date_match:
                        day = date_match.group(1).zfill(2)
                        month = months_es.get(date_match.group(2), '01')
                        fecha = f"{current_year}-{month}-{day}"
                        break
                    
                    # Numeric date format
                    for pattern in date_patterns:
                        match = re.search(pattern, cell)
                        if match:
                            groups = match.groups()
                            if len(groups[0]) == 4:  # YYYY-MM-DD
                                fecha = f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                            else:  # DD-MM-YYYY
                                year = groups[2] if len(groups[2]) == 4 else f"20{groups[2]}"
                                fecha = f"{year}-{groups[1].zfill(2)}-{groups[0].zfill(2)}"
                            break
                    if fecha:
                        break
                
                if not fecha:
                    continue
                
                # Extract amounts based on column positions if available
                deposito = 0
                retiro = 0
                saldo = 0
                
                if deposito_col is not None and deposito_col < len(row_cleaned):
                    deposito = parse_amount(row_cleaned[deposito_col])
                
                if retiro_col is not None and retiro_col < len(row_cleaned):
                    retiro = parse_amount(row_cleaned[retiro_col])
                
                if saldo_col is not None and saldo_col < len(row_cleaned):
                    saldo = parse_amount(row_cleaned[saldo_col])
                
                # Find description
                descripcion = ""
                for idx, cell in enumerate(row_cleaned):
                    if idx in [deposito_col, retiro_col, saldo_col]:
                        continue
                    cell_str = str(cell or '').strip()
                    if cell_str and len(cell_str) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell_str):
                        descripcion = cell_str
                
                # If no column positions found, use position-based detection
                if deposito_col is None and retiro_col is None:
                    amounts = []
                    for cell in row_cleaned:
                        val = parse_amount(cell)
                        if val > 0:
                            amounts.append(val)
                    
                    if amounts:
                        saldo = amounts[-1] if len(amounts) > 1 else 0
                        monto = amounts[0] if amounts else 0
                        
                        # Use keyword detection
                        normalized_desc = normalize_text_for_keywords(descripcion)
                        is_dep = is_deposit_transaction(normalized_desc)
                        
                        if is_dep is True:
                            deposito = monto
                        else:
                            retiro = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion or 'Movimiento',
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
                    
            except Exception:
                continue
    
    return transactions


def parse_santander_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse Santander bank statement format"""
    import re
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12',
        'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
        'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
        'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
    }
    
    # Santander typically has format: DD/MM/YYYY DESCRIPTION CARGO ABONO SALDO
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Pattern for date at start: DD/MM/YYYY or DD-MM-YYYY
        date_match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s+(.+)', line)
        if date_match:
            day = date_match.group(1).zfill(2)
            month = date_match.group(2).zfill(2)
            year = date_match.group(3)
            if len(year) == 2:
                year = f"20{year}"
            fecha = f"{year}-{month}-{day}"
            rest = date_match.group(4)
            
            # Extract amounts from the rest of the line
            amounts = re.findall(r'([\d,]+\.\d{2})', rest)
            if amounts:
                # Description is everything before the first amount
                desc_match = re.match(r'^(.+?)[\d,]+\.\d{2}', rest)
                descripcion = desc_match.group(1).strip() if desc_match else rest[:50]
                
                # Last amount is usually saldo, second to last could be the movement
                deposito = 0
                retiro = 0
                saldo = float(amounts[-1].replace(',', '')) if amounts else 0
                
                if len(amounts) >= 2:
                    monto = float(amounts[-2].replace(',', ''))
                    # Use shared keyword detection
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                elif len(amounts) == 1:
                    monto = float(amounts[0].replace(',', ''))
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion,
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
    
    return transactions


def parse_hsbc_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse HSBC bank statement format"""
    import re
    
    transactions = []
    current_year = datetime.now().year
    
    # HSBC format varies but often has: DATE REFERENCE DESCRIPTION WITHDRAWALS DEPOSITS BALANCE
    for table in tables:
        if not table or len(table) < 2:
            continue
        
        for row in table[1:]:
            if not row or len(row) < 4:
                continue
            
            try:
                row_str = [str(cell or '').strip() for cell in row]
                
                # Find date
                fecha = None
                for cell in row_str:
                    date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', cell)
                    if date_match:
                        day = date_match.group(1).zfill(2)
                        month = date_match.group(2).zfill(2)
                        year = date_match.group(3)
                        if len(year) == 2:
                            year = f"20{year}"
                        fecha = f"{year}-{month}-{day}"
                        break
                
                if not fecha:
                    continue
                
                # Get description (usually longest text field)
                descripcion = ""
                for cell in row_str:
                    if len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                        descripcion = cell
                
                # Extract amounts
                amounts = []
                for cell in row_str:
                    if re.match(r'^[\d,]+\.?\d*$', cell.replace(',', '').replace(' ', '')):
                        try:
                            amounts.append(float(cell.replace(',', '')))
                        except:
                            pass
                
                if amounts and descripcion:
                    deposito = 0
                    retiro = 0
                    saldo = amounts[-1] if len(amounts) > 1 else 0
                    monto = amounts[0] if amounts else 0
                    
                    # Use shared keyword detection
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                    
                    if deposito > 0 or retiro > 0:
                        transactions.append({
                            'fecha': fecha,
                            'descripcion': descripcion,
                            'deposito': deposito,
                            'retiro': retiro,
                            'saldo': saldo,
                            'referencia': ''
                        })
            except:
                continue
    
    return transactions


def parse_banamex_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse Citibanamex bank statement format"""
    import re
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    # Banamex often uses: DD MMM DESCRIPTION CARGOS ABONOS SALDO
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Pattern: DD MMM or DD/MM/YYYY
        date_match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(.+)', line, re.IGNORECASE)
        if date_match:
            day = date_match.group(1).zfill(2)
            month = months_es.get(date_match.group(2).upper(), '01')
            fecha = f"{current_year}-{month}-{day}"
            rest = date_match.group(3)
            
            # Extract amounts
            amounts = re.findall(r'([\d,]+\.\d{2})', rest)
            if amounts:
                desc_match = re.match(r'^(.+?)[\d,]+\.\d{2}', rest)
                descripcion = desc_match.group(1).strip() if desc_match else rest[:50]
                
                deposito = 0
                retiro = 0
                saldo = float(amounts[-1].replace(',', '')) if amounts else 0
                
                if len(amounts) >= 2:
                    monto = float(amounts[0].replace(',', ''))
                    # Use shared keyword detection
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion,
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
    
    return transactions



@router.post("/bank-transactions/preview-pdf")
async def preview_bank_statement_pdf(
    request: Request, 
    file: UploadFile = File(...), 
    banco: str = Form(default="auto"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Preview transactions from PDF without importing.
    Returns detected bank, transactions found, and summary.
    """
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    try:
        content = await file.read()
        
        # Detect bank type
        import pdfplumber
        detected_bank = banco
        saldo_inicial_detected = None
        
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
            
            if banco == "auto":
                text_lower = full_text.lower()
                if "banbajio" in text_lower or "bajio" in text_lower or "banco del bajio" in text_lower:
                    detected_bank = "Banco del Bajío"
                elif "banorte" in text_lower:
                    detected_bank = "Banorte"
                elif "bbva" in text_lower or "bancomer" in text_lower:
                    detected_bank = "BBVA"
                elif "santander" in text_lower:
                    detected_bank = "Santander"
                elif "hsbc" in text_lower:
                    detected_bank = "HSBC"
                elif "scotiabank" in text_lower:
                    detected_bank = "Scotiabank"
                elif "banamex" in text_lower or "citibanamex" in text_lower:
                    detected_bank = "Citibanamex"
                else:
                    detected_bank = "Genérico"
            
            # Try to extract saldo inicial
            import re
            saldo_patterns = [
                r'SALDO\s+INICIAL[:\s]+\$?\s*([\d,]+\.?\d*)',
                r'SALDO\s+ANTERIOR[:\s]+\$?\s*([\d,]+\.?\d*)',
            ]
            for pattern in saldo_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    saldo_inicial_detected = float(match.group(1).replace(',', ''))
                    break
        
        # Parse transactions
        transactions = parse_bank_statement_pdf(content, banco)
        
        # Calculate summary
        total_depositos = sum(t.get('deposito', 0) for t in transactions)
        total_retiros = sum(t.get('retiro', 0) for t in transactions)
        
        # Format for frontend display
        preview_transactions = []
        for txn in transactions:
            monto = txn['deposito'] if txn['deposito'] > 0 else txn['retiro']
            tipo = 'credito' if txn['deposito'] > 0 else 'debito'
            preview_transactions.append({
                'fecha': txn['fecha'],
                'descripcion': txn['descripcion'][:100],
                'monto': monto,
                'tipo': tipo,
                'tipo_display': 'Depósito' if tipo == 'credito' else 'Retiro',
                'saldo': txn.get('saldo', 0),
                'referencia': txn.get('referencia', '')
            })
        
        return {
            'status': 'success',
            'banco_detectado': detected_bank,
            'saldo_inicial_detectado': saldo_inicial_detected,
            'total_movimientos': len(transactions),
            'total_depositos': total_depositos,
            'total_retiros': total_retiros,
            'flujo_neto': total_depositos - total_retiros,
            'transactions': preview_transactions,
            'message': f'Se detectaron {len(transactions)} movimientos del banco {detected_bank}'
        }
        
    except Exception as e:
        logging.error(f"Error previewing PDF: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error procesando PDF: {str(e)}")


@router.post("/bank-transactions/import-pdf")
async def import_bank_statement_pdf(
    request: Request, 
    file: UploadFile = File(...), 
    bank_account_id: str = Form(...),
    banco: str = Form(default="auto"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Import bank statement from PDF file.
    Supports Banorte, BBVA, Santander, HSBC and other Mexican banks.
    """
    import io
    
    company_id = await get_active_company_id(request, current_user)
    
    # Verify bank account
    account = await db.bank_accounts.find_one({'id': bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    try:
        content = await file.read()
        
        # Parse the PDF
        transactions = parse_bank_statement_pdf(content, banco)
        
        if not transactions:
            return {
                'status': 'warning',
                'message': 'No se encontraron movimientos en el PDF. Intenta con otro formato o usa la plantilla Excel.',
                'importados': 0,
                'errores': 0,
                'transactions_preview': []
            }
        
        # Import transactions
        imported = 0
        duplicates = 0
        auto_conciliados = 0   # Duplicados auto-conciliados con certeza alta
        requieren_revision = 0  # Duplicados sin conciliar que el usuario debe revisar manualmente
        errors = []

        for txn in transactions:
            try:
                # Calculate amount and type
                if txn['deposito'] > 0:
                    monto = txn['deposito']
                    tipo = 'credito'
                else:
                    monto = txn['retiro']
                    tipo = 'debito'

                if monto == 0:
                    continue

                # Check for duplicates
                existing = await db.bank_transactions.find_one({
                    'company_id': company_id,
                    'bank_account_id': bank_account_id,
                    'descripcion': txn['descripcion'],
                    'monto': monto,
                    'fecha_movimiento': {'$regex': f"^{txn['fecha']}"}
                }, {'_id': 0, 'id': 1, 'conciliado': 1, 'requiere_revision': 1})

                if existing:
                    # ¿Ya está conciliado? → omitir limpiamente
                    if existing.get('conciliado'):
                        duplicates += 1
                        continue

                    # ¿Ya está marcado para revisión? → no volver a procesar
                    if existing.get('requiere_revision'):
                        duplicates += 1
                        continue

                    # NO conciliado → aplicar reglas de certeza alta para auto-conciliar
                    bank_txn_id = existing['id']
                    tipo_cfdi_buscar = 'ingreso' if tipo == 'credito' else 'egreso'

                    # REGLA 1: monto EXACTO (no ±2%, sin tolerancia)
                    # REGLA 2: UN SOLO candidato (sin ambigüedad)
                    # REGLA 3: saldo pendiente del CFDI >= monto del movimiento
                    candidatos = await db.cfdis.find({
                        'company_id': company_id,
                        'tipo_cfdi': tipo_cfdi_buscar,
                        'estado_cancelacion': {'$ne': 'cancelado'},
                        'total': monto,  # monto exacto
                        '$or': [
                            {'estado_conciliacion': {'$in': [None, 'pendiente', 'parcial']}},
                            {'estado_conciliacion': {'$exists': False}}
                        ]
                    }, {'_id': 0}).to_list(10)  # traemos hasta 10 para detectar ambigüedad

                    # Filtrar candidatos con saldo pendiente suficiente
                    candidatos_validos = []
                    for c in candidatos:
                        cfdi_total = float(c.get('total', 0) or 0)
                        if tipo_cfdi_buscar == 'ingreso':
                            ya_cubierto = float(c.get('monto_cobrado', 0) or 0)
                        else:
                            ya_cubierto = float(c.get('monto_pagado', 0) or 0)
                        saldo_pendiente = cfdi_total - ya_cubierto
                        if saldo_pendiente >= monto - 0.01:
                            candidatos_validos.append(c)

                    certeza_alta = len(candidatos_validos) == 1  # único candidato válido

                    if certeza_alta:
                        cfdi_match = candidatos_validos[0]
                        tipo_pago = 'cobro' if tipo_cfdi_buscar == 'ingreso' else 'pago'
                        if tipo_cfdi_buscar == 'ingreso':
                            beneficiario = cfdi_match.get('receptor_nombre', '') or cfdi_match.get('emisor_nombre', '')
                        else:
                            beneficiario = cfdi_match.get('emisor_nombre', '') or cfdi_match.get('receptor_nombre', '')

                        # Evitar payment duplicado
                        pay_exists = await db.payments.find_one({
                            'company_id': company_id,
                            'bank_transaction_id': bank_txn_id,
                            'cfdi_id': cfdi_match['id']
                        }, {'_id': 0, 'id': 1})

                        if not pay_exists:
                            payment_doc = {
                                'id': str(uuid.uuid4()),
                                'company_id': company_id,
                                'bank_account_id': bank_account_id,
                                'cfdi_id': cfdi_match['id'],
                                'tipo': tipo_pago,
                                'concepto': f"Auto-conciliación PDF - {beneficiario}",
                                'monto': monto,
                                'moneda': account.get('moneda', 'MXN'),
                                'metodo_pago': 'transferencia',
                                'fecha_vencimiento': f"{txn['fecha']}T12:00:00",
                                'fecha_pago': f"{txn['fecha']}T12:00:00",
                                'estatus': 'completado',
                                'referencia': txn.get('referencia', ''),
                                'beneficiario': beneficiario,
                                'es_real': True,
                                'bank_transaction_id': bank_txn_id,
                                'cfdi_uuid': cfdi_match.get('uuid'),
                                'cfdi_emisor': cfdi_match.get('emisor_nombre'),
                                'cfdi_receptor': cfdi_match.get('receptor_nombre'),
                                'category_id': cfdi_match.get('category_id'),
                                'subcategory_id': cfdi_match.get('subcategory_id'),
                                'auto_created_from_reconciliation': True,
                                'fuente': 'pdf_import_autoconciliacion',
                                'created_at': datetime.now(timezone.utc).isoformat()
                            }
                            await db.payments.insert_one(payment_doc)

                            # Actualizar CFDI
                            cfdi_total = float(cfdi_match.get('total', 0) or 0)
                            if tipo_pago == 'cobro':
                                ya_cobrado = float(cfdi_match.get('monto_cobrado', 0) or 0)
                                nuevo = min(ya_cobrado + monto, cfdi_total)
                                nuevo_estado = 'conciliado' if nuevo >= cfdi_total - 0.01 else 'parcial'
                                await db.cfdis.update_one(
                                    {'id': cfdi_match['id']},
                                    {'$set': {'monto_cobrado': nuevo, 'estado_conciliacion': nuevo_estado}}
                                )
                            else:
                                ya_pagado = float(cfdi_match.get('monto_pagado', 0) or 0)
                                nuevo = min(ya_pagado + monto, cfdi_total)
                                nuevo_estado = 'conciliado' if nuevo >= cfdi_total - 0.01 else 'parcial'
                                await db.cfdis.update_one(
                                    {'id': cfdi_match['id']},
                                    {'$set': {'monto_pagado': nuevo, 'estado_conciliacion': nuevo_estado}}
                                )

                            # Marcar banco como conciliado
                            await db.bank_transactions.update_one(
                                {'id': bank_txn_id},
                                {'$set': {
                                    'conciliado': True,
                                    'tipo_conciliacion': 'con_uuid',
                                    'payment_id': payment_doc['id']
                                }}
                            )
                            auto_conciliados += 1
                            logger.info(
                                f"Auto-conciliado (certeza alta): bank_txn={bank_txn_id} "
                                f"→ CFDI={cfdi_match['id']} ({tipo_pago} ${monto})"
                            )
                    else:
                        # Ambigüedad (0 o 2+ candidatos) → marcar para revisión manual
                        # El movimiento ya existe en DB, solo le agregamos el flag
                        motivo = (
                            'sin_cfdi_match' if len(candidatos_validos) == 0
                            else f'multiples_candidatos_{len(candidatos_validos)}'
                        )
                        await db.bank_transactions.update_one(
                            {'id': bank_txn_id},
                            {'$set': {
                                'requiere_revision': True,
                                'motivo_revision': motivo,
                                # Guardar IDs de candidatos para mostrarlos en el modal de la UI
                                'cfdi_candidatos': [c['id'] for c in candidatos_validos[:5]]
                            }}
                        )
                        requieren_revision += 1
                        logger.info(
                            f"Marcado para revisión: bank_txn={bank_txn_id} "
                            f"motivo={motivo} monto=${monto}"
                        )
                    continue

                # Transacción nueva → insertar normalmente
                new_txn = {
                    'id': str(uuid.uuid4()),
                    'company_id': company_id,
                    'bank_account_id': bank_account_id,
                    'fecha_movimiento': f"{txn['fecha']}T12:00:00",
                    'fecha_valor': f"{txn['fecha']}T12:00:00",
                    'descripcion': txn['descripcion'][:500],
                    'referencia': txn.get('referencia', '')[:100],
                    'monto': monto,
                    'tipo_movimiento': tipo,
                    'saldo': txn.get('saldo', 0),
                    'moneda': account.get('moneda', 'MXN'),
                    'fuente': 'pdf_import',
                    'conciliado': False,
                    'created_at': datetime.now(timezone.utc).isoformat()
                }

                await db.bank_transactions.insert_one(new_txn)
                imported += 1

            except Exception as e:
                errors.append(f"Error en transacción: {str(e)}")
                logger.error(f"Error procesando txn del PDF: {str(e)}", exc_info=True)

        await audit_log(company_id, 'BankTransaction', 'PDF_IMPORT', 'IMPORT', current_user['id'])

        msg_parts = [f'Se importaron {imported} movimientos.']
        if auto_conciliados:
            msg_parts.append(f'{auto_conciliados} auto-conciliados con CFDI.')
        if requieren_revision:
            msg_parts.append(f'{requieren_revision} requieren revisión manual.')
        if duplicates:
            msg_parts.append(f'{duplicates} duplicados omitidos.')

        return {
            'status': 'success',
            'message': ' '.join(msg_parts),
            'importados': imported,
            'auto_conciliados': auto_conciliados,
            'requieren_revision': requieren_revision,
            'duplicados_omitidos': duplicates,
            'errores': len(errors),
            'detalle_errores': errors[:10],
            'total_encontrados': len(transactions)
        }
        
    except Exception as e:
        logging.error(f"Error importing PDF: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error procesando PDF: {str(e)}")


