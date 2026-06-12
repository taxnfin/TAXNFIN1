"""Advanced features: AI predictive, auto-reconciliation, alerts, bank API routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log
from models.enums import UserRole
from advanced_services import PredictiveAnalysisService, AutoReconciliationService, AlertService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/ai/predictive-analysis")
async def get_predictive_analysis(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """An\u00e1lisis predictivo de cashflow con ML + LLM"""

    company_id = await get_active_company_id(request, current_user)
    service = PredictiveAnalysisService(db)

    analysis = await service.analyze_cashflow_trends(
        company_id=company_id,
        weeks_history=13
    )

    if analysis['status'] == 'insufficient_data':
        return analysis

    ai_insights = await service.generate_ai_insights(
        company_id=company_id,
        analysis_data=analysis
    )

    return {
        'status': 'success',
        'company_id': company_id,
        'analisis_cuantitativo': analysis['analisis'],
        'predicciones_8_semanas': analysis['predictions'],
        'insights_ia': ai_insights
    }

# ===== CONCILIACI\u00d3N AUTOM\u00c1TICA INTELIGENTE =====

@router.get("/reconciliation/auto-match/{bank_transaction_id}")
async def find_reconciliation_matches(
    bank_transaction_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Encuentra coincidencias autom\u00e1ticas para un movimiento bancario"""

    company_id = await get_active_company_id(request, current_user)
    service = AutoReconciliationService(db)
    matches = await service.find_matches(bank_transaction_id, company_id)

    return {
        'status': 'success',
        'bank_transaction_id': bank_transaction_id,
        'matches_found': len(matches),
        'matches': matches
    }

@router.post("/reconciliation/auto-reconcile-batch")
async def auto_reconcile_batch(
    request: Request,
    min_score: float = Query(85, ge=60, le=100),
    current_user: Dict = Depends(get_current_user)
):
    """Concilia autom\u00e1ticamente movimientos con alta confianza"""

    company_id = await get_active_company_id(request, current_user)
    service = AutoReconciliationService(db)
    result = await service.auto_reconcile_batch(
        company_id=company_id,
        user_id=current_user['id'],
        min_score=min_score
    )

    return result

# ===== SISTEMA DE ALERTAS =====

@router.post("/alerts/check-and-send")
async def check_and_send_alerts(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Verifica condiciones y env\u00eda alertas autom\u00e1ticas"""

    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")

    company_id = await get_active_company_id(request, current_user)
    service = AlertService(db)
    alerts = await service.check_and_send_alerts(company_id)

    return {
        'status': 'success',
        'alerts_sent': len(alerts),
        'alerts': alerts
    }

# ===== SCRAPING SAT AUTOMATIZADO =====

@router.post("/sat/download-cfdis")
async def download_cfdis_from_sat(
    fecha_inicio: datetime,
    fecha_fin: datetime,
    tipo: str = Query("recibidos", regex="^(emitidos|recibidos)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Descarga autom\u00e1tica de CFDIs desde portal SAT"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = SATScraperService(db)
    result = await service.download_cfdis_by_date_range(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo=tipo
    )
    
    return result

@router.post("/sat/schedule-automatic")
async def schedule_sat_downloads(
    frequency: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Programa descargas autom\u00e1ticas de CFDIs"""
    
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = SATScraperService(db)
    result = await service.schedule_automatic_download(
        company_id=current_user['company_id'],
        frequency=frequency
    )
    
    return result

@router.post("/sat/credentials")
async def store_sat_credentials(
    rfc: str,
    certificado_file: UploadFile = File(...),
    llave_file: UploadFile = File(...),
    password: str = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Almacena credenciales CSD/e.firma para el SAT"""
    
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    certificado_bytes = await certificado_file.read()
    llave_bytes = await llave_file.read()
    
    manager = SATCredentialManager(db)
    result = await manager.store_csd_credentials(
        company_id=current_user['company_id'],
        rfc=rfc,
        certificado_cer=certificado_bytes,
        llave_key=llave_bytes,
        password=password
    )
    
    return result

# ===== INTEGRACI\u00d3N APIS BANCARIAS =====

@router.get("/bank-api/available-banks")
async def get_available_banks():
    """Lista de bancos con APIs disponibles"""
    
    service = BankAPIService(db)
    banks = await service.get_available_banks()
    
    return {
        'status': 'success',
        'banks': banks
    }

# ===== AN\u00c1LISIS DE ESCENARIOS "QU\u00c9 PASAR\u00cdA SI" =====

from scenario_service import ScenarioAnalysisService

class BankAPIConnection(BaseModel):
    bank_account_id: str
    bank_name: str
    credentials: Dict[str, str]

@router.post("/bank-api/connect")
async def connect_bank_api(
    connection_data: BankAPIConnection,
    current_user: Dict = Depends(get_current_user)
):
    """Conecta cuenta bancaria con su API"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = BankAPIService(db)
    result = await service.connect_bank_account(
        company_id=current_user['company_id'],
        bank_account_id=connection_data.bank_account_id,
        bank_name=connection_data.bank_name,
        credentials=connection_data.credentials
    )
    
    return result

@router.post("/bank-api/sync/{bank_account_id}")
async def sync_bank_transactions(
    bank_account_id: str,
    days_back: int = Query(30, ge=1, le=90),
    current_user: Dict = Depends(get_current_user)
):
    """Sincroniza transacciones desde API del banco"""
    
    service = BankAPIService(db)
    result = await service.sync_transactions(
        bank_account_id=bank_account_id,
        days_back=days_back
    )
    
    return result

# ===== DRILL-DOWN ENDPOINT: Week Transactions Detail =====

# ===== PDF EXPORT =====

@router.get("/ai/export-pdf")
async def export_ia_ejecutiva_pdf(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    import datetime

    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    nombre_empresa = (company or {}).get('nombre', 'Mi Empresa')
    rfc_empresa = (company or {}).get('rfc', '')

    # Fix 1 — fecha en español sin depender de locale del SO
    MESES = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',
             7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}
    hoy = datetime.date.today()
    fecha_str = f"{hoy.day} de {MESES[hoy.month]} de {hoy.year}"

    # Obtener análisis
    service = PredictiveAnalysisService(db)
    analysis = await service.analyze_cashflow_trends(company_id=company_id, weeks_history=13)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()
    GREEN = colors.HexColor('#10B981')
    NAVY = colors.HexColor('#0F172A')
    GRAY = colors.HexColor('#64748B')
    RED = colors.HexColor('#EF4444')
    PINK = colors.HexColor('#EC4899')

    story = []

    # ── Header con logo text + empresa ──
    header_data = [
        [Paragraph('<font color="#10B981"><b>TaxnFin</b></font> <font color="#0F172A">| IA Ejecutiva</font>',
                   ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=18)),
         Paragraph(f'<b>{nombre_empresa}</b><br/><font color="#64748B">RFC: {rfc_empresa}<br/>{fecha_str}</font>',
                   ParagraphStyle('r', fontName='Helvetica', fontSize=10, alignment=2))]
    ]
    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,0), 2, GREEN),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # ── Análisis Predictivo ──
    if analysis.get('status') == 'success':
        a = analysis['analisis']
        # Fix 2 — sin emoji
        story.append(Paragraph('Analisis Predictivo de Flujo de Efectivo',
                               ParagraphStyle('s', fontName='Helvetica-Bold', fontSize=13, textColor=GREEN)))
        story.append(Spacer(1, 0.15*inch))

        kpi_data = [
            ['Ingreso Promedio Semanal', 'Egreso Promedio Semanal', 'Flujo Neto Promedio'],
            [f"${a['ingresos_promedio_semanal']:,.0f}",
             f"${a['egresos_promedio_semanal']:,.0f}",
             f"${a['flujo_neto_promedio']:,.0f}"]
        ]
        kpi_table = Table(kpi_data, colWidths=[2.33*inch]*3)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F0FDF4')),
            ('TEXTCOLOR', (0,0), (-1,0), GRAY),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,1), (-1,1), 14),
            ('TEXTCOLOR', (0,1), (0,1), GREEN),
            ('TEXTCOLOR', (1,1), (1,1), RED),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0,1), (-1,1), [colors.white]),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 0.2*inch))

        # Predicciones
        story.append(Paragraph('Predicciones proximas 8 semanas:',
                               ParagraphStyle('p', fontName='Helvetica-Bold', fontSize=10, textColor=NAVY)))
        pred_data = [['Semana', 'Ingreso Predicho', 'Egreso Predicho', 'Flujo Neto', 'Confianza']]
        for p in analysis.get('predictions', []):
            pred_data.append([
                f"S+{p['semana_futura']}",
                f"${p['ingresos_predichos']:,.0f}",
                f"${p['egresos_predichos']:,.0f}",
                f"${p['flujo_neto_predicho']:,.0f}",
                p['confianza']
            ])
        pred_table = Table(pred_data, colWidths=[0.6*inch, 1.4*inch, 1.4*inch, 1.4*inch, 0.9*inch])
        pred_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(pred_table)

        # Insights IA — Fix 4: limpiar markdown antes de agregar al PDF
        ai_insights = await service.generate_ai_insights(company_id=company_id, analysis_data=analysis)
        if ai_insights and 'no disponible' not in ai_insights.lower():
            import re
            ai_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', ai_insights)
            ai_clean = re.sub(r'^#{1,3}\s*', '', ai_clean, flags=re.MULTILINE)
            ai_clean = re.sub(r'^>\s*', '', ai_clean, flags=re.MULTILINE)
            ai_clean = ai_clean.strip()
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph('Insights IA - Recomendaciones Ejecutivas',
                                   ParagraphStyle('ia', fontName='Helvetica-Bold', fontSize=11, textColor=NAVY)))
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(ai_clean,
                                   ParagraphStyle('iat', fontName='Helvetica', fontSize=9,
                                                  textColor=NAVY, leading=14)))

    # Recomendaciones CFO Virtual
    recomendaciones = await db.optimization_applied.find(
        {'company_id': company_id}
    ).sort('applied_at', -1).limit(10).to_list(10)

    if recomendaciones:
        story.append(Spacer(1, 0.3*inch))
        # Fix 5 — sin emoji
        story.append(Paragraph('CFO Virtual - Recomendaciones Aplicadas',
                               ParagraphStyle('cfo', fontName='Helvetica-Bold', fontSize=13,
                                              textColor=PINK)))
        story.append(Spacer(1, 0.1*inch))

        # Fix 1 — sin emojis en TIPOS
        TIPOS = {
            'retrasar_pago':   '[RETRASAR PAGO]',
            'adelantar_cobro': '[ADELANTAR COBRO]',
            'adelantar_pago':  '[ADELANTAR PAGO]',
            'retrasar_cobro':  '[RETRASAR COBRO]',
            'ajustar_monto':   '[AJUSTAR MONTO]',
        }

        rec_data = [['Accion', 'Cliente / Proveedor', 'Recomendacion']]
        for rec in recomendaciones:
            nombre = (rec.get('transaction_id', '')
                      .replace('cache_ingreso_', '').replace('cache_egreso_', '')
                      .rsplit('_', 1)[0])
            rec_data.append([
                TIPOS.get(rec.get('tipo', ''), rec.get('tipo', '')),
                nombre[:30],
                rec.get('recomendacion', '')[:60]
            ])

        rt = Table(rec_data, colWidths=[1.3*inch, 1.8*inch, 3.6*inch])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EC4899')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FDF2F8')]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        # Fix 3 — color por tipo en columna Accion
        for i, rec in enumerate(recomendaciones, start=1):
            tipo = rec.get('tipo', '')
            if tipo in ('adelantar_cobro', 'adelantar_pago'):
                rt.setStyle(TableStyle([('TEXTCOLOR', (0,i), (0,i), GREEN)]))
            elif tipo in ('retrasar_pago', 'retrasar_cobro'):
                rt.setStyle(TableStyle([('TEXTCOLOR', (0,i), (0,i), colors.HexColor('#F59E0B'))]))
            elif tipo == 'ajustar_monto':
                rt.setStyle(TableStyle([('TEXTCOLOR', (0,i), (0,i), RED)]))
        story.append(rt)

    story.append(Spacer(1, 0.3*inch))

    # ── Footer ──
    story.append(HRFlowable(width='100%', thickness=1, color=GREEN))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        f'<font color="#64748B">Generado por TaxnFin IA Ejecutiva · cashflow.taxnfin.com · {hoy.strftime("%d/%m/%Y")}</font>',
        ParagraphStyle('f', fontName='Helvetica', fontSize=8, alignment=1)
    ))

    doc.build(story)
    buffer.seek(0)
    filename = f"IA_Ejecutiva_{nombre_empresa.replace(' ','_')}_{hoy}.pdf"
    return StreamingResponse(buffer, media_type='application/pdf',
                             headers={'Content-Disposition': f'attachment; filename="{filename}"'})
