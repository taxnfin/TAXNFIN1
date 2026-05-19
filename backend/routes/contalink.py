

# ── Aging Import (CxC / CxP desde XLS de Contalink) ───────────────────────────

def _isna(val) -> bool:
    import math
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    return False


def _parse_money(val) -> float:
    """Convierte '$1,234.56' o 1234.56 a float"""
    if val is None:
        return 0.0
    s = str(val).replace(",", "").replace("$", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


def _parse_cxc_xls(content: bytes) -> dict:
    import io
    import pandas as pd
    df = pd.read_excel(io.BytesIO(content), engine="xlrd", header=None)
    empresa = str(df.iloc[1, 3]) if not _isna(df.iloc[1, 3]) else ""
    rfc     = str(df.iloc[2, 3]) if not _isna(df.iloc[2, 3]) else ""
    fecha   = str(df.iloc[1, 9])[:10] if not _isna(df.iloc[1, 9]) else ""
    items = []
    for i in range(4, len(df)):
        nombre = df.iloc[i, 1]
        total  = df.iloc[i, 12]
        if _isna(nombre) or _isna(total):
            continue
        nombre_s = str(nombre).strip()
        if not nombre_s or nombre_s == "nan" or "Total" in nombre_s or "Porcentaje" in nombre_s:
            continue
        items.append({
            "nombre":           nombre_s,
            "credito_anticipo": _parse_money(df.iloc[i, 2]),
            "por_vencer":       _parse_money(df.iloc[i, 3]),
            "dias_1_30":        _parse_money(df.iloc[i, 5]),
            "dias_31_60":       _parse_money(df.iloc[i, 7]),
            "dias_61_90":       _parse_money(df.iloc[i, 8]),
            "dias_91_120":      _parse_money(df.iloc[i, 10]),
            "sobre_120":        _parse_money(df.iloc[i, 11]),
            "total":            _parse_money(total),
        })
    total_general = sum(r["total"] for r in items)
    return {
        "empresa": empresa, "rfc": rfc, "fecha": fecha, "items": items,
        "totals": {
            "credito_anticipo": sum(r["credito_anticipo"] for r in items),
            "por_vencer":       sum(r["por_vencer"]       for r in items),
            "dias_1_30":        sum(r["dias_1_30"]        for r in items),
            "dias_31_60":       sum(r["dias_31_60"]       for r in items),
            "dias_61_90":       sum(r["dias_61_90"]       for r in items),
            "dias_91_120":      sum(r["dias_91_120"]      for r in items),
            "sobre_120":        sum(r["sobre_120"]        for r in items),
            "total":            total_general,
        },
    }


def _parse_cxp_xls(content: bytes) -> dict:
    import io
    import pandas as pd
    df = pd.read_excel(io.BytesIO(content), engine="xlrd", header=None)
    empresa = str(df.iloc[0, 0]) if not _isna(df.iloc[0, 0]) else ""
    rfc     = str(df.iloc[0, 1]) if not _isna(df.iloc[0, 1]) else ""
    fecha   = str(df.iloc[0, 2])[:10] if not _isna(df.iloc[0, 2]) else ""
    SKIP = {"TOTAL", "Porcentajes", "Porcentajes totales"}
    items = []
    for i in range(3, len(df)):
        nombre = df.iloc[i, 1]
        total  = df.iloc[i, 8]
        if _isna(nombre) or _isna(total):
            continue
        nombre_s = str(nombre).strip()
        if not nombre_s or nombre_s == "nan" or nombre_s in SKIP:
            continue
        items.append({
            "nombre":           nombre_s,
            "credito_anticipo": _parse_money(df.iloc[i, 2]),
            "por_vencer":       _parse_money(df.iloc[i, 3]),
            "dias_1_30":        _parse_money(df.iloc[i, 4]),
            "dias_31_60":       _parse_money(df.iloc[i, 5]),
            "dias_61_90":       _parse_money(df.iloc[i, 6]),
            "sobre_90":         _parse_money(df.iloc[i, 7]),
            "total":            _parse_money(total),
        })
    total_general = sum(r["total"] for r in items)
    return {
        "empresa": empresa, "rfc": rfc, "fecha": fecha, "items": items,
        "totals": {
            "credito_anticipo": sum(r["credito_anticipo"] for r in items),
            "por_vencer":       sum(r["por_vencer"]       for r in items),
            "dias_1_30":        sum(r["dias_1_30"]        for r in items),
            "dias_31_60":       sum(r["dias_31_60"]       for r in items),
            "dias_61_90":       sum(r["dias_61_90"]       for r in items),
            "sobre_90":         sum(r["sobre_90"]         for r in items),
            "total":            total_general,
        },
    }


@router.post("/import-aging")
async def import_aging_xls(
    file: UploadFile = File(...),
    tipo: str = Query(..., description="cxc | cxp"),
    request: Request = None,
    current_user: Dict = Depends(get_current_user),
):
    """Importa XLS de aging (CxC o CxP) exportado desde Contalink."""
    if tipo not in ("cxc", "cxp"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'cxc' o 'cxp'")
    company_id = await get_active_company_id(request, current_user)
    content = await file.read()
    try:
        parsed = _parse_cxc_xls(content) if tipo == "cxc" else _parse_cxp_xls(content)
    except Exception as e:
        logger.error(f"import_aging_xls parse error ({tipo}): {e}")
        raise HTTPException(status_code=400, detail=f"Error al parsear XLS: {str(e)}")
    doc = {
        "company_id": company_id,
        "tipo":        tipo,
        "fecha":       parsed["fecha"],
        "empresa":     parsed["empresa"],
        "rfc":         parsed["rfc"],
        "items":       parsed["items"],
        "totals":      parsed["totals"],
        "updated_at":  datetime.now(timezone.utc).isoformat(),
    }
    await db.contalink_aging.update_one(
        {"company_id": company_id, "tipo": tipo},
        {"$set": doc},
        upsert=True,
    )
    return {
        "success": True,
        "tipo":    tipo,
        "fecha":   parsed["fecha"],
        "empresa": parsed["empresa"],
        "count":   len(parsed["items"]),
        "total":   parsed["totals"]["total"],
        "totals":  parsed["totals"],
    }


@router.get("/aging-summary")
async def get_aging_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Devuelve CxC + CxP aging para el Dashboard."""
    company_id = await get_active_company_id(request, current_user)
    cxc_doc = await db.contalink_aging.find_one({"company_id": company_id, "tipo": "cxc"}, {"_id": 0})
    cxp_doc = await db.contalink_aging.find_one({"company_id": company_id, "tipo": "cxp"}, {"_id": 0})

    def aging_bands(doc, tipo):
        if not doc:
            return None
        t = doc.get("totals", {})
        bands = [
            {"label": "1-30",  "amount": t.get("dias_1_30",  0)},
            {"label": "31-60", "amount": t.get("dias_31_60", 0)},
            {"label": "61-90", "amount": t.get("dias_61_90", 0)},
        ]
        if tipo == "cxc":
            bands += [
                {"label": "91-120", "amount": t.get("dias_91_120", 0)},
                {"label": ">120",   "amount": t.get("sobre_120",   0)},
            ]
        else:
            bands += [{"label": ">90", "amount": t.get("sobre_90", 0)}]
        return {
            "total":      t.get("total", 0),
            "por_vencer": t.get("por_vencer", 0),
            "vencido":    t.get("total", 0) - t.get("por_vencer", 0) - t.get("credito_anticipo", 0),
            "bands":      bands,
            "fecha":      doc.get("fecha"),
            "count":      len(doc.get("items", [])),
            "top5":       sorted(doc.get("items", []), key=lambda x: x["total"], reverse=True)[:5],
        }

    return {
        "cxc": aging_bands(cxc_doc, "cxc"),
        "cxp": aging_bands(cxp_doc, "cxp"),
        "net_position": (
            (cxc_doc["totals"]["total"] if cxc_doc else 0)
            - (cxp_doc["totals"]["total"] if cxp_doc else 0)
        ),
    }
