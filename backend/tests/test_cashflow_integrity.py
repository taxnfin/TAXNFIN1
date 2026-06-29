"""
Cashflow integrity checks — verifica invariantes críticos del motor de cálculo.

Uso:
    python backend/tests/test_cashflow_integrity.py
    python backend/tests/test_cashflow_integrity.py --url http://localhost:8001

Variables de entorno (opcionales):
    REACT_APP_BACKEND_URL   URL base del backend (default: http://localhost:8001)
    TEST_EMAIL              Usuario de prueba  (default: admin@demo.com)
    TEST_PASSWORD           Contraseña         (default: admin123)

Checks:
    1. S1  saldo_inicial  ≈ 305,849
    2. Semana que contiene 2026-01-31 → saldo_final ≈ 387,509
    3. Semana que contiene 2026-02-28 → saldo_final ≈ 665,865
    4. Ninguna semana tiene ids duplicados en ingresos_detalle
    5. Ninguna semana tiene ids duplicados en egresos_detalle
"""

import argparse
import os
import sys
from typing import Optional

# Forzar UTF-8 en stdout para que ✅/❌ y caracteres Unicode funcionen en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests

# ── Configuración ─────────────────────────────────────────────────────────────
BASE_URL    = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
TEST_EMAIL  = os.environ.get("TEST_EMAIL",    "admin@demo.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "admin123")

TOLERANCE_PCT = 2.0   # % de tolerancia para comparaciones aproximadas

# Valores esperados
EXPECTED = {
    "s1_saldo_inicial":           305_849,
    "jan31_saldo_inicial":        387_509,   # ancla bancaria 2026-01-31 → saldo_inicial de S4
    "feb28_saldo_inicial":        665_865,   # ancla bancaria 2026-02-28 → saldo_inicial de S8
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def approx_equal(actual: float, expected: float, tol_pct: float = TOLERANCE_PCT) -> bool:
    """True si |actual - expected| / expected <= tol_pct %."""
    if expected == 0:
        return abs(actual) < 1
    return abs(actual - expected) / abs(expected) * 100 <= tol_pct


def fmt(value: float) -> str:
    return f"{value:,.0f}"


def check(label: str, passed: bool, expected, actual) -> bool:
    icon = "✅" if passed else "❌"
    exp_str = fmt(expected) if isinstance(expected, (int, float)) else str(expected)
    act_str = fmt(actual)   if isinstance(actual,   (int, float)) else str(actual)
    print(f"  {icon}  {label}")
    if not passed:
        print(f"       esperado ≈ {exp_str}   real = {act_str}")
    else:
        print(f"       esperado ≈ {exp_str}   real = {act_str}")
    return passed


def week_containing(weeks: list, date_str: str) -> Optional[dict]:
    """Devuelve la semana cuyo rango [fecha_inicio, fecha_fin] contiene date_str."""
    for w in weeks:
        fi = (w.get("fecha_inicio") or "")[:10]
        ff = (w.get("fecha_fin")    or "")[:10]
        if fi and ff and fi <= date_str <= ff:
            return w
    return None


def find_duplicate_ids(detalle: list) -> list:
    """
    Retorna lista de ids que aparecen más de una vez en detalle.
    Ignora items sin id o con id vacío (proyecciones manuales).
    """
    seen: dict = {}
    dupes: list = []
    for item in detalle:
        item_id = item.get("id", "")
        if not item_id:
            continue
        if item_id in seen:
            if item_id not in dupes:
                dupes.append(item_id)
        else:
            seen[item_id] = True
    return dupes


# ── Login + company ID ────────────────────────────────────────────────────────

def login() -> tuple[str, str]:
    """Retorna (token, company_id)."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"❌  Login falló ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    data  = resp.json()
    token = data.get("access_token") or data.get("token", "")
    if not token:
        print("❌  No se encontró access_token en la respuesta de login")
        sys.exit(1)

    # Intentar obtener company_id del payload
    user        = data.get("user") or data
    company_id  = (
        (user.get("company_ids") or [None])[0]
        or user.get("company_id")
        or ""
    )

    # Si no viene en el login, consultar /api/companies
    if not company_id:
        headers = {"Authorization": f"Bearer {token}"}
        cr = requests.get(f"{BASE_URL}/api/companies", headers=headers, timeout=10)
        if cr.status_code == 200:
            companies = cr.json()
            if companies:
                company_id = (companies[0].get("id") or "")

    return token, company_id


# ── Main ──────────────────────────────────────────────────────────────────────

def run_checks(base_url: str = BASE_URL, jwt_token: str = "") -> bool:
    global BASE_URL
    BASE_URL = base_url.rstrip("/")

    print(f"\n{'─'*60}")
    print(f"  Cashflow Integrity Checks")
    print(f"  URL  : {BASE_URL}")
    print(f"{'─'*60}\n")

    # ── Auth ──────────────────────────────────────────────────────────────────
    if jwt_token:
        token = jwt_token
        print(f"Usando token externo: {token[:20]}…")
        # Resolver company_id desde /api/companies con el token dado
        company_id = ""
        cr = requests.get(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if cr.status_code == 200:
            companies = cr.json()
            if companies:
                company_id = (companies[0].get("id") or "")
    else:
        print(f"Autenticando como {TEST_EMAIL}…")
        token, company_id = login()

    print(f"  token       : {token[:20]}…")
    print(f"  company_id  : {company_id or '(vacío — backend usará empresa del JWT)'}\n")

    headers: dict = {"Authorization": f"Bearer {token}"}
    if company_id:
        headers["X-Company-ID"] = company_id

    # ── Llamar a /api/cashflow/weeks ──────────────────────────────────────────
    print("Obteniendo /api/cashflow/weeks?num_weeks=52…")
    resp = requests.get(
        f"{BASE_URL}/api/cashflow/weeks",
        params={"num_weeks": 52},
        headers=headers,
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"❌  GET /api/cashflow/weeks falló ({resp.status_code}): {resp.text[:300]}")
        return False

    weeks = resp.json()
    if not weeks:
        print("❌  La respuesta es una lista vacía — no hay semanas que verificar.")
        return False

    print(f"  {len(weeks)} semanas recibidas\n")
    print("Verificaciones:\n")

    results: list[bool] = []

    # ── Check 1: S1 saldo_inicial ─────────────────────────────────────────────
    s1 = next((w for w in weeks if w.get("label") == "S1" or w.get("numero_semana") == 1), weeks[0])
    s1_si = float(s1.get("saldo_inicial") or 0)
    exp1   = EXPECTED["s1_saldo_inicial"]
    results.append(check(
        f"S1 saldo_inicial ({s1.get('fecha_inicio','?')[:10]})",
        approx_equal(s1_si, exp1),
        exp1,
        s1_si,
    ))

    # ── Check 2: semana que contiene 2026-01-31 → saldo_inicial (ancla bancaria) ─
    # El calculador aplica el ancla como saldo_inicial de la semana que la contiene,
    # no como saldo_final. El ancla de 2026-01-31 aparece en S4 (2026-01-26).
    DATE_JAN31 = "2026-01-31"
    w_jan = week_containing(weeks, DATE_JAN31)
    if w_jan is None:
        print(f"  ❌  No se encontró semana que contenga {DATE_JAN31}")
        results.append(False)
    else:
        si_jan = float(w_jan.get("saldo_inicial") or 0)
        exp2   = EXPECTED["jan31_saldo_inicial"]
        results.append(check(
            f"Semana que contiene {DATE_JAN31} ({w_jan.get('label','?')}) saldo_inicial (ancla)",
            approx_equal(si_jan, exp2),
            exp2,
            si_jan,
        ))

    # ── Check 3: semana que contiene 2026-02-28 → saldo_inicial (ancla bancaria) ─
    DATE_FEB28 = "2026-02-28"
    w_feb = week_containing(weeks, DATE_FEB28)
    if w_feb is None:
        print(f"  ❌  No se encontró semana que contenga {DATE_FEB28}")
        results.append(False)
    else:
        si_feb = float(w_feb.get("saldo_inicial") or 0)
        exp3   = EXPECTED["feb28_saldo_inicial"]
        results.append(check(
            f"Semana que contiene {DATE_FEB28} ({w_feb.get('label','?')}) saldo_inicial (ancla)",
            approx_equal(si_feb, exp3),
            exp3,
            si_feb,
        ))

    # ── Check 4: sin ids duplicados en ingresos_detalle ───────────────────────
    ing_dupes_total = 0
    ing_worst: Optional[str] = None
    for w in weeks:
        dupes = find_duplicate_ids(w.get("ingresos_detalle") or [])
        if dupes:
            ing_dupes_total += len(dupes)
            if ing_worst is None:
                ing_worst = f"{w.get('label','?')} ids={dupes[:3]}"

    ing_ok = ing_dupes_total == 0
    results.append(check(
        "Sin ids duplicados en ingresos_detalle (todas las semanas)",
        ing_ok,
        "0 duplicados",
        f"{ing_dupes_total} duplicado(s){' — ej: ' + ing_worst if ing_worst else ''}",
    ))

    # ── Check 5: sin ids duplicados en egresos_detalle ────────────────────────
    egr_dupes_total = 0
    egr_worst: Optional[str] = None
    for w in weeks:
        dupes = find_duplicate_ids(w.get("egresos_detalle") or [])
        if dupes:
            egr_dupes_total += len(dupes)
            if egr_worst is None:
                egr_worst = f"{w.get('label','?')} ids={dupes[:3]}"

    egr_ok = egr_dupes_total == 0
    results.append(check(
        "Sin ids duplicados en egresos_detalle (todas las semanas)",
        egr_ok,
        "0 duplicados",
        f"{egr_dupes_total} duplicado(s){' — ej: ' + egr_worst if egr_worst else ''}",
    ))

    # ── Resumen ───────────────────────────────────────────────────────────────
    passed = sum(results)
    total  = len(results)
    print(f"\n{'─'*60}")
    icon = "✅" if passed == total else "❌"
    print(f"  {icon}  {passed}/{total} checks pasaron")
    print(f"{'─'*60}\n")

    # ── Detalle de saldos por si falla para ajustar expected values ────────────
    if passed < total:
        print("Saldos reales por semana (primeras 13):\n")
        print(f"  {'Label':<6}  {'fecha_inicio':<12}  {'saldo_inicial':>14}  {'flujo_neto':>12}  {'saldo_final':>14}")
        print(f"  {'─'*6}  {'─'*12}  {'─'*14}  {'─'*12}  {'─'*14}")
        for w in weeks[:13]:
            si  = float(w.get("saldo_inicial") or 0)
            fn  = float(w.get("flujo_neto")    or 0)
            sf  = float(w.get("saldo_final")   or (si + fn))
            lbl = w.get("label") or f"S{w.get('numero_semana','?')}"
            fi  = (w.get("fecha_inicio") or "")[:10]
            print(f"  {lbl:<6}  {fi:<12}  {si:>14,.0f}  {fn:>12,.0f}  {sf:>14,.0f}")
        print()

    return passed == total


# ── Pytest hook ───────────────────────────────────────────────────────────────

def test_cashflow_integrity():
    """pytest entry point — falla si cualquier check falla."""
    url   = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    token = os.environ.get("TEST_JWT_TOKEN", "")
    assert run_checks(url, token), "Uno o más checks de integridad fallaron (ver salida arriba)"


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cashflow integrity checks")
    parser.add_argument(
        "--url",
        default=os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001"),
        help="URL base del backend (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("TEST_JWT_TOKEN", ""),
        help="JWT token ya obtenido (omite el paso de login)",
    )
    args = parser.parse_args()
    ok = run_checks(args.url, args.token)
    sys.exit(0 if ok else 1)
