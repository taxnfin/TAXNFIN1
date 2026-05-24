"""PDF Report generation routes — Resumen Ejecutivo + Dashboard KPIs"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict
import logging

from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class PDFRequest(BaseModel):
    empresa: str = "Mi Empresa"
    rfc: str = ""
    periodo: str = ""
    ingresos: float = 0
    costo_ventas: float = 0
    utilidad_bruta: float = 0
    gastos_op: float = 0
    ebitda: float = 0
    utilidad_neta: float = 0
    activo_total: float = 0
    activo_circ: float = 0
    activo_fijo: float = 0
    pasivo_total: float = 0
    pasivo_circ: float = 0
    pasivo_lp: float = 0
    capital: float = 0
    margen_bruto: float = 0
    margen_ebitda: float = 0
    margen_op: float = 0
    margen_neto: float = 0
    roic: float = 0
    roe: float = 0
    roa: float = 0
    roce: float = 0
    razon_circ: float = 0
    prueba_acida: float = 0
    razon_ef: float = 0
    capital_trabajo: float = 0
    cash_runway: float = 0
    dso: float = 0
    dpo: float = 0
    dio: float = 0
    ccc: float = 0
    deuda_capital: float = 0
    deuda_activos: float = 0
    deuda_ebitda: float = 0
    cobertura: float = 0
    apalancamiento: float = 0


@router.post("/reports/pdf-mejorado")
async def generate_pdf_mejorado(
    request: Request,
    data: PDFRequest,
    current_user: Dict = Depends(get_current_user),
):
    """Resumen Ejecutivo con gráficas — 5 páginas"""
    try:
        from services.pdf_generator import build_pdf_mejorado
        pdf_buffer = build_pdf_mejorado(data.dict())
        empresa_safe = data.empresa.replace(" ", "_").replace("/", "-")
        filename = f"Resumen_Ejecutivo_{empresa_safe}_{data.periodo}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generando Resumen Ejecutivo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")


@router.post("/reports/pdf-kpis")
async def generate_pdf_kpis(
    request: Request,
    data: PDFRequest,
    current_user: Dict = Depends(get_current_user),
):
    """Dashboard KPIs — 20 indicadores con semáforos en 1 página"""
    try:
        from services.kpi_pdf_generator import build_kpi_pdf
        pdf_buffer = build_kpi_pdf(data.dict())
        empresa_safe = data.empresa.replace(" ", "_").replace("/", "-")
        filename = f"Dashboard_KPIs_{empresa_safe}_{data.periodo}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generando Dashboard KPIs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando KPIs PDF: {str(e)}")


@router.post("/reports/excel-corporativo")
async def generate_excel_corporativo(
    request: Request,
    data: dict,
    current_user: Dict = Depends(get_current_user),
):
    """Excel corporativo con formato azul — 4 hojas"""
    try:
        from services.excel_report_generator import build_excel_report
        buffer = build_excel_report(data)
        empresa = data.get('empresa', 'Empresa').replace(' ', '_').replace('/', '-')
        periodo = data.get('periodo', '')
        filename = f"Reporte_Ejecutivo_{empresa}_{periodo}.xlsx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generando Excel corporativo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando Excel: {str(e)}")
