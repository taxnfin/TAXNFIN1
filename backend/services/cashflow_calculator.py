"""Lee cashflow_weeks de MongoDB y distribuye CFDIs por fecha_emision (igual que Cash Flow)."""
import re
import uuid as _uuid
from datetime import date, timedelta
from typing import Dict, List

from core.database import db


def _date_str(val) -> str:
    """Extrae YYYY-MM-DD de cualquier formato de fecha."""
    m = re.search(r'(\d{4}-\d{2}-\d{2})', str(val))
    return m.group(1) if m else ''


async def calcular_semanas_cashflow(company_id: str, num_weeks: int = 52) -> List[Dict]:
    weeks_raw = await db.cashflow_weeks.find(
        {'company_id': company_id}, {'_id': 0}
    ).sort('numero_semana', 1).to_list(200)

    # Leer todos los CFDIs una sola vez
    all_cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'id': 1, 'tipo_cfdi': 1, 'total': 1,
         'receptor_nombre': 1, 'emisor_nombre': 1, 'concepto': 1,
         'categoria': 1, 'fecha_emision': 1}
    ).to_list(10000)

    result = []
    for week in weeks_raw:
        fi = str(week.get('fecha_inicio', ''))[:10]
        ff = str(week.get('fecha_fin', ''))[:10]
        num = week.get('numero_semana', len(result) + 1)
        week_id = week.get('id', '')

        ingresos = []
        egresos = []

        if fi and ff:
            for c in all_cfdis:
                fecha_str = _date_str(c.get('fecha_emision', ''))
                if not fecha_str or fecha_str < fi or fecha_str > ff:
                    continue
                monto = float(c.get('total', 0) or 0)
                if monto <= 0:
                    continue
                tipo = str(c.get('tipo_cfdi', '') or '').lower()
                nombre = (c.get('receptor_nombre') or c.get('emisor_nombre') or
                          c.get('concepto') or 'Sin nombre')
                item = {
                    'id': c.get('id', ''),
                    'concepto': nombre,
                    'monto': monto,
                    'fecha': fecha_str,
                    'categoria': c.get('categoria', 'otros'),
                }
                if tipo in ('i', 'ingreso'):
                    ingresos.append(item)
                else:
                    egresos.append(item)

        total_ing = sum(i['monto'] for i in ingresos)
        total_egr = sum(e['monto'] for e in egresos)

        # Fallback a totales guardados si no hay CFDIs en rango
        if total_ing == 0:
            total_ing = float(week.get('total_ingresos', 0) or 0)
        if total_egr == 0:
            total_egr = float(week.get('total_egresos', 0) or 0)

        # Si hay total pero no detalle (datos de sync), crear item resumen
        if not ingresos and total_ing > 0:
            ingresos = [{'id': '', 'concepto': 'Ingresos del período', 'monto': total_ing,
                         'fecha': fi, 'categoria': 'sync', 'es_resumen': True}]
        if not egresos and total_egr > 0:
            egresos = [{'id': '', 'concepto': 'Egresos del período', 'monto': total_egr,
                        'fecha': fi, 'categoria': 'sync', 'es_resumen': True}]

        result.append({
            'id': week_id,
            'company_id': company_id,
            'numero_semana': num,
            'label': f'S{num}',
            'fecha_inicio': fi,
            'fecha_fin': ff,
            'date_range': f"{fi[8:10]}/{fi[5:7]} - {ff[8:10]}/{ff[5:7]}" if fi and ff else '',
            'week_start': fi,
            'week_end': ff,
            'es_real': week.get('es_real', False),
            'saldo_inicial': float(week.get('saldo_inicial', 0) or 0),
            'total_ingresos': total_ing,
            'total_egresos': total_egr,
            'total_ingresos_reales': total_ing,
            'total_egresos_reales': total_egr,
            'total_ingresos_proyectados': float(week.get('total_ingresos_proyectados', 0) or 0),
            'total_egresos_proyectados': float(week.get('total_egresos_proyectados', 0) or 0),
            'saldo_final_real': float(week.get('saldo_final_real', 0) or 0),
            'saldo_final_proyectado': float(week.get('saldo_final_proyectado', 0) or 0),
            'flujo_neto': total_ing - total_egr,
            'ingresos_detalle': sorted(ingresos, key=lambda x: x['monto'], reverse=True),
            'egresos_detalle': sorted(egresos, key=lambda x: x['monto'], reverse=True),
            'top_ingresos': sorted(ingresos, key=lambda x: x['monto'], reverse=True)[:5],
            'top_egresos': sorted(egresos, key=lambda x: x['monto'], reverse=True)[:5],
            'proyecciones_ingreso': [],
            'proyecciones_egreso': [],
            'notas': week.get('notas', ''),
        })

    # Generar semanas futuras si hay menos de num_weeks
    if len(result) < num_weeks and result:
        ultima = result[-1]
        try:
            next_start = date.fromisoformat(ultima['fecha_fin']) + timedelta(days=1)
        except Exception:
            next_start = date.today()
        num_inicial = ultima['numero_semana'] + 1

        for i in range(num_weeks - len(result)):
            ws = next_start + timedelta(weeks=i)
            we = ws + timedelta(days=6)
            num = num_inicial + i
            fi = ws.isoformat()
            ff = we.isoformat()

            ingresos = []
            egresos = []
            for c in all_cfdis:
                fecha_str = _date_str(c.get('fecha_emision', ''))
                if not fecha_str or fecha_str < fi or fecha_str > ff:
                    continue
                monto = float(c.get('total', 0) or 0)
                if monto <= 0:
                    continue
                tipo = str(c.get('tipo_cfdi', '') or '').lower()
                nombre = (c.get('receptor_nombre') or c.get('emisor_nombre') or
                          c.get('concepto') or 'Sin nombre')
                item = {
                    'id': c.get('id', ''),
                    'concepto': nombre,
                    'monto': monto,
                    'fecha': fecha_str,
                    'categoria': c.get('categoria', 'otros'),
                }
                if tipo in ('i', 'ingreso'):
                    ingresos.append(item)
                else:
                    egresos.append(item)

            total_ing = sum(i['monto'] for i in ingresos)
            total_egr = sum(e['monto'] for e in egresos)

            result.append({
                'id': str(_uuid.uuid4()),
                'company_id': company_id,
                'numero_semana': num,
                'label': f'S{num}',
                'fecha_inicio': fi,
                'fecha_fin': ff,
                'date_range': f"{ws.strftime('%d/%m')} - {we.strftime('%d/%m')}",
                'week_start': fi,
                'week_end': ff,
                'es_real': False,
                'es_generada': True,
                'saldo_inicial': 0,
                'total_ingresos': total_ing,
                'total_egresos': total_egr,
                'total_ingresos_reales': total_ing,
                'total_egresos_reales': total_egr,
                'total_ingresos_proyectados': 0,
                'total_egresos_proyectados': 0,
                'saldo_final_real': 0,
                'saldo_final_proyectado': 0,
                'flujo_neto': total_ing - total_egr,
                'ingresos_detalle': sorted(ingresos, key=lambda x: x['monto'], reverse=True),
                'egresos_detalle': sorted(egresos, key=lambda x: x['monto'], reverse=True),
                'top_ingresos': sorted(ingresos, key=lambda x: x['monto'], reverse=True)[:5],
                'top_egresos': sorted(egresos, key=lambda x: x['monto'], reverse=True)[:5],
                'proyecciones_ingreso': [],
                'proyecciones_egreso': [],
                'notas': '',
            })

    return result
