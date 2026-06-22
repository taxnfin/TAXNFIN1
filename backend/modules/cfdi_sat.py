"""
CFDI SAT Integration Module — CIEC (RFC + Contraseña)
Scraping del portal SAT con Selenium + Chromium headless
Selectores actualizados para portal SAT 2025
"""

import asyncio
import logging
import uuid as uuid_module
import os
import tempfile
import glob
import shutil
import re
from datetime import datetime, timezone
from typing import Optional, Dict, List
from cryptography.fernet import Fernet
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# ─── URLs del portal SAT 2025 ───────────────────────────────────────────────
SAT_LOGIN_URL      = "https://portalcfdi.facturaelectronica.sat.gob.mx/"
SAT_RECEPTOR_URL   = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaReceptor.aspx"
SAT_EMISOR_URL     = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaEmisor.aspx"
SAT_DECLARACIONES  = "https://www.sat.gob.mx/declaraciones-y-pagos/contribuyentes/persona-moral"
SAT_BUZONTRIB      = "https://buzontributario.sat.gob.mx/"
SAT_CIF_URL        = "https://rfc.siat.sat.gob.mx/PTSC/RFC/menu/index.jsf"


def get_encryption_key():
    key = os.environ.get('SAT_ENCRYPTION_KEY')
    if not key:
        key = Fernet.generate_key().decode()
        logger.warning("SAT_ENCRYPTION_KEY not set — usando clave generada. Configúrala en Railway.")
    return key.encode() if isinstance(key, str) else key


# ─── Credential Manager ──────────────────────────────────────────────────────

class SATCredentialManager:
    def __init__(self, db):
        self.db = db
        self.fernet = Fernet(get_encryption_key())

    def encrypt(self, data: str) -> str:
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()

    async def save_credentials(self, company_id: str, rfc: str, ciec: str) -> Dict:
        doc = {
            'company_id': company_id,
            'rfc': rfc.upper().strip(),
            'ciec_encrypted': self.encrypt(ciec),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'last_sync': None,
            'status': 'active',
        }
        await self.db.sat_credentials.update_one(
            {'company_id': company_id},
            {'$set': doc},
            upsert=True
        )
        return {'status': 'configured', 'rfc': rfc, 'message': 'Credenciales SAT guardadas correctamente'}

    async def get_credentials(self, company_id: str) -> Optional[Dict]:
        cred = await self.db.sat_credentials.find_one(
            {'company_id': company_id, 'status': 'active'}, {'_id': 0}
        )
        if not cred:
            return None
        try:
            return {'rfc': cred['rfc'], 'ciec': self.decrypt(cred['ciec_encrypted']),
                    'last_sync': cred.get('last_sync')}
        except Exception as e:
            logger.error(f"Error descifrando credenciales: {e}")
            return None

    async def get_credential_status(self, company_id: str) -> Optional[Dict]:
        return await self.db.sat_credentials.find_one(
            {'company_id': company_id}, {'_id': 0, 'ciec_encrypted': 0}
        )

    async def delete_credentials(self, company_id: str):
        await self.db.sat_credentials.delete_one({'company_id': company_id})

    async def update_last_sync(self, company_id: str, result: Dict = None):
        upd = {'last_sync': datetime.now(timezone.utc).isoformat(),
               'updated_at': datetime.now(timezone.utc).isoformat()}
        if result:
            upd['last_sync_result'] = result
        await self.db.sat_credentials.update_one({'company_id': company_id}, {'$set': upd})


# ─── SAT Portal Client ───────────────────────────────────────────────────────

class SATPortalClient:
    """
    Cliente Selenium para el portal SAT.
    Selectores verificados contra el portal CFDI 2024-2025.
    """

    def __init__(self):
        self.driver = None
        self.logged_in = False
        self.download_dir = None
        self._last_captcha_type = None  # rastreado por _solve_captcha para _inject_captcha_token

    # ── Driver setup ──────────────────────────────────────────────────────

    def _get_options(self):
        from selenium.webdriver.chrome.options import Options
        opts = Options()
        # Buscar chromium en paths comunes de Debian/Railway
        for path in ['/usr/bin/chromium', '/usr/bin/chromium-browser',
                     '/usr/bin/google-chrome', shutil.which('chromium'),
                     shutil.which('chromium-browser')]:
            if path and os.path.exists(path):
                opts.binary_location = path
                break

        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--disable-extensions')
        opts.add_argument('--disable-software-rasterizer')
        opts.add_argument('--window-size=1280,900')
        opts.add_argument('--lang=es-MX')
        opts.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        self.download_dir = tempfile.mkdtemp()
        opts.add_experimental_option('prefs', {
            'download.default_directory': self.download_dir,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': False,
        })
        return opts

    def _init_driver(self) -> bool:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        try:
            opts = self._get_options()
            # Buscar chromedriver del sistema (instalado con apt)
            driver_path = (shutil.which('chromedriver') or
                           shutil.which('chromium-driver') or
                           '/usr/bin/chromedriver')
            if driver_path and os.path.exists(driver_path):
                svc = Service(driver_path)
            else:
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.os_manager import ChromeType
                svc = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())

            self.driver = webdriver.Chrome(service=svc, options=opts)
            self.driver.set_page_load_timeout(120)
            self.driver.implicitly_wait(8)
            return True
        except Exception as e:
            logger.error(f"Error iniciando WebDriver: {e}")
            return False

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        self.logged_in = False
        if self.download_dir:
            try:
                shutil.rmtree(self.download_dir)
            except Exception:
                pass

    # ── Screenshot helper ─────────────────────────────────────────────────

    def _screenshot(self, tag: str) -> str:
        path = f"/tmp/sat_{tag}_{datetime.now().strftime('%H%M%S')}.png"
        try:
            self.driver.save_screenshot(path)
            logger.info(f"Screenshot guardado: {path}")
        except Exception:
            pass
        return path

    # ── CAPTCHA Solver (2captcha) ─────────────────────────────────────────

    def _extract_sitekey(self) -> Optional[str]:
        """Extrae el sitekey de reCAPTCHA via JS (más confiable que regex en page_source)."""
        try:
            sitekey = self.driver.execute_script("""
                var els = document.querySelectorAll('[data-sitekey]');
                if (els.length > 0) return els[0].getAttribute('data-sitekey');
                if (window.___grecaptcha_cfg) {
                    var clients = window.___grecaptcha_cfg.clients || {};
                    for (var k in clients) {
                        var c = clients[k];
                        if (!c) continue;
                        for (var p in c) {
                            if (c[p] && typeof c[p] === 'object' && c[p].sitekey) return c[p].sitekey;
                        }
                    }
                }
                var iframes = document.querySelectorAll('iframe[src*="recaptcha"]');
                if (iframes.length > 0) {
                    var m = iframes[0].src.match(/[?&]k=([^&]+)/);
                    if (m) return m[1];
                }
                return null;
            """)
            if sitekey and len(sitekey) > 20:
                return sitekey
        except Exception as e:
            logger.debug(f"[2captcha] JS sitekey extraction failed: {e}")

        # Fallback: buscar con regex más amplio en page_source
        import re as _re
        page_src = self.driver.page_source
        for pattern in [
            r'data-sitekey=["\']([A-Za-z0-9_\-]{20,})["\']',
            r'sitekey["\s:=\']+([A-Za-z0-9_\-]{20,})',
            r'render\(["\']([A-Za-z0-9_\-]{20,})["\']',
            r'["\']([6L][A-Za-z0-9_\-]{38,})["\']',  # reCAPTCHA sitekeys comienzan con "6L"
        ]:
            m = _re.search(pattern, page_src)
            if m:
                key = m.group(1)
                if len(key) > 20:
                    return key
        return None

    async def _solve_captcha(self) -> Optional[str]:
        import aiohttp
        api_key = os.environ.get('TWOCAPTCHA_API_KEY', '')
        if not api_key:
            logger.warning("[2captcha] TWOCAPTCHA_API_KEY no configurada")
            return None
        page_url = self.driver.current_url
        page_src = self.driver.page_source.lower()
        captcha_type = None
        site_key = None

        # Detectar tipo de captcha
        captcha_b64 = None
        if 'hcaptcha' in page_src:
            captcha_type = 'hcaptcha'
            site_key = self._extract_sitekey()
        elif 'recaptcha' in page_src or 'g-recaptcha' in page_src:
            captcha_type = 'recaptcha'
            site_key = self._extract_sitekey()
        else:
            from selenium.webdriver.common.by import By
            # SAT cfdiau: imagen base64 inline dentro de #divCaptcha
            for sel in ['#divCaptcha img', 'label[id*="aptcha"] img',
                        'img#captcha', 'img.captcha', 'img[src*="captcha"]',
                        '#captchaImg', '#imgCaptcha']:
                try:
                    img_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    img_src = img_el.get_attribute('src') or ''
                    if img_src.startswith('data:image'):
                        # Extraer base64 del data URL: "data:image/jpeg;base64,XXXX"
                        if ',' in img_src:
                            captcha_b64 = img_src.split(',', 1)[1]
                        captcha_type = 'sat_image'
                    else:
                        captcha_type = 'image'
                    break
                except Exception:
                    continue

        if not captcha_type:
            logger.warning("[2captcha] No se detectó tipo de captcha en la página")
            return None

        logger.info(f"[2captcha] Detectado: {captcha_type}, sitekey={site_key}, url={page_url}")
        self._last_captcha_type = captcha_type

        if captcha_type in ('recaptcha', 'hcaptcha') and not site_key:
            logger.error(f"[2captcha] {captcha_type} detectado pero no se pudo extraer sitekey")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                if captcha_type == 'recaptcha' and site_key:
                    data = {'key': api_key, 'method': 'userrecaptcha', 'googlekey': site_key,
                            'pageurl': page_url, 'json': 1}
                elif captcha_type == 'hcaptcha' and site_key:
                    data = {'key': api_key, 'method': 'hcaptcha', 'sitekey': site_key,
                            'pageurl': page_url, 'json': 1}
                elif captcha_type == 'sat_image' and captcha_b64:
                    # Imagen base64 inline del SAT cfdiau
                    data = {'key': api_key, 'method': 'base64', 'body': captcha_b64, 'json': 1}
                elif captcha_type == 'image':
                    from selenium.webdriver.common.by import By
                    img = self.driver.find_element(
                        By.CSS_SELECTOR, 'img#captcha,img.captcha,img[src*="captcha"],#captchaImg')
                    data = {'key': api_key, 'method': 'base64',
                            'body': img.screenshot_as_base64, 'json': 1}
                else:
                    logger.error(f"[2captcha] Tipo '{captcha_type}' sin datos suficientes para resolver")
                    return None

                async with session.post('https://2captcha.com/in.php', data=data) as r:
                    res = await r.json()
                    if res.get('status') != 1:
                        logger.error(f"[2captcha] Error al enviar: {res}")
                        return None
                    cid = res['request']
                    logger.info(f"[2captcha] ID={cid}, esperando solución...")

                for _ in range(24):
                    await asyncio.sleep(5)
                    async with session.get(
                        f'https://2captcha.com/res.php?key={api_key}&action=get&id={cid}&json=1'
                    ) as r:
                        res = await r.json()
                        if res.get('status') == 1:
                            logger.info("[2captcha] ✅ CAPTCHA resuelto")
                            return res['request']
                        elif res.get('request') != 'CAPCHA_NOT_READY':
                            logger.error(f"[2captcha] Error en polling: {res}")
                            return None
        except Exception as e:
            logger.error(f"[2captcha] Excepción: {e}")
        return None

    async def _inject_captcha_token(self, token: str, captcha_type: str = 'recaptcha'):
        try:
            from selenium.webdriver.common.by import By
            if captcha_type == 'sat_image':
                # Portal SAT cfdiau: escribe la solución en #userCaptcha
                inp = self.driver.find_element(By.ID, 'userCaptcha')
                inp.clear()
                inp.send_keys(token)
                logger.info(f"[2captcha] Token SAT imagen inyectado en #userCaptcha: {token}")
            elif captcha_type in ('recaptcha', 'hcaptcha'):
                self.driver.execute_script(
                    "document.getElementById('g-recaptcha-response').innerHTML = arguments[0];", token)
                self.driver.execute_script(
                    "try { ___grecaptcha_cfg.clients[0].aa.l.callback(arguments[0]); } catch(e) {}", token)
            elif captcha_type == 'image':
                for sel in ['#captchaInput', '#txtCaptcha', 'input[name*="captcha" i]', '#userCaptcha']:
                    try:
                        inp = self.driver.find_element(By.CSS_SELECTOR, sel)
                        inp.clear()
                        inp.send_keys(token)
                        break
                    except Exception:
                        continue
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[2captcha] Error inyectando token: {e}")

    # ── Login ─────────────────────────────────────────────────────────────

    async def login(self, rfc: str, ciec: str) -> Dict:
        """
        Login al Portal CFDI del SAT con RFC + CIEC.
        Devuelve {'success': True/False, 'message'/'error': ...}
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        if not self._init_driver():
            return {'success': False,
                    'error': 'No se pudo inicializar Chromium en el servidor.'}

        try:
            logger.info(f"[SAT] Login RFC={rfc}")
            self.driver.get(SAT_LOGIN_URL)
            await asyncio.sleep(3)

            # ── Paso 0: Resolver CAPTCHA en el page load (antes del submit) ──
            page_initial = self.driver.page_source.lower()
            if 'captcha' in page_initial:
                logger.info("[SAT] CAPTCHA detectado en page load, resolviendo antes del submit...")
                pre_token = await self._solve_captcha()
                if pre_token:
                    ptype_pre = self._last_captcha_type or 'recaptcha'
                    await self._inject_captcha_token(pre_token, ptype_pre)
                    logger.info(f"[SAT] Token pre-submit inyectado (tipo={ptype_pre})")
                else:
                    logger.warning("[SAT] No se pudo resolver CAPTCHA pre-submit, continuando de todas formas")

            wait = WebDriverWait(self.driver, 20)

            # ── Paso 1: RFC ───────────────────────────────────────────────
            # El portal SAT 2024+ usa un input con id="rfc" dentro de un form
            rfc_input = None
            for by, sel in [
                (By.ID,   'rfc'),
                (By.ID,   'Rfc'),
                (By.NAME, 'Rfc'),
                (By.CSS_SELECTOR, "input[placeholder*='RFC']"),
                (By.CSS_SELECTOR, "input[name*='rfc' i]"),
                (By.XPATH, "//input[contains(@id,'rfc') or contains(@name,'rfc')]"),
            ]:
                try:
                    rfc_input = wait.until(EC.presence_of_element_located((by, sel)))
                    break
                except Exception:
                    continue

            if not rfc_input:
                self._screenshot('no_rfc_field')
                return {'success': False,
                        'error': 'No se encontró el campo RFC en el portal SAT. El portal puede haber cambiado.'}

            rfc_input.clear()
            rfc_input.send_keys(rfc)
            await asyncio.sleep(0.5)

            # ── Paso 2: CIEC / Contraseña ─────────────────────────────────
            ciec_input = None
            for by, sel in [
                (By.ID,          'password'),
                (By.ID,          'contrasena'),
                (By.NAME,        'Password'),
                (By.CSS_SELECTOR,"input[type='password']"),
                (By.XPATH,       "//input[@type='password']"),
            ]:
                try:
                    ciec_input = self.driver.find_element(by, sel)
                    break
                except Exception:
                    continue

            if not ciec_input:
                self._screenshot('no_ciec_field')
                return {'success': False,
                        'error': 'No se encontró el campo CIEC/Contraseña en el portal SAT.'}

            ciec_input.clear()
            ciec_input.send_keys(ciec)
            await asyncio.sleep(0.5)

            # Verificar que los campos quedaron con valor antes de submit
            await asyncio.sleep(1)
            rfc_val  = self.driver.execute_script("return document.getElementById('rfc')?.value || ''")
            ciec_val = self.driver.execute_script("return document.getElementById('password')?.value || ''")
            logger.info(f"[SAT] Pre-submit check — RFC='{rfc_val}' CIEC_len={len(ciec_val)}")
            if not rfc_val or not ciec_val:
                logger.error("[SAT] Campos vacíos antes de submit — reintentando llenado")
                # Rellenar via JS directamente
                self.driver.execute_script(f"document.getElementById('rfc').value = '{rfc}'")
                self.driver.execute_script("document.getElementById('password').value = arguments[0]", ciec)
                await asyncio.sleep(0.5)

            # ── Paso 3: Botón Enviar ──────────────────────────────────────
            submit_btn = None
            for by, sel in [
                (By.ID,    'submit'),
                (By.ID,    'btnEntrar'),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//input[@value='Enviar' or @value='Entrar' or @value='Aceptar']"),
                (By.XPATH, "//button[contains(text(),'Entrar') or contains(text(),'Enviar')]"),
            ]:
                try:
                    submit_btn = self.driver.find_element(by, sel)
                    break
                except Exception:
                    continue

            if not submit_btn:
                self._screenshot('no_submit_btn')
                return {'success': False,
                        'error': 'No se encontró el botón de ingreso en el portal SAT.'}

            submit_btn.click()
            await asyncio.sleep(4)

            # ── Paso 4: Verificar resultado ───────────────────────────────
            page = self.driver.page_source.lower()
            url  = self.driver.current_url.lower()

            error_phrases = [
                'rfc o contraseña no válido', 'datos incorrectos',
                'contraseña incorrecta', 'el rfc es incorrecto',
                'datos de acceso no válidos', 'no válidos',
                'usuario bloqueado', 'cuenta bloqueada',
            ]
            for phrase in error_phrases:
                if phrase in page:
                    return {'success': False,
                            'error': 'RFC o CIEC incorrectos. Verifique sus credenciales en el portal SAT.'}

            if 'captcha' in page:
                logger.info("[SAT] CAPTCHA detectado post-submit, resolviendo con 2captcha...")
                token = await self._solve_captcha()
                if token:
                    ptype = self._last_captcha_type or (
                        'recaptcha' if 'recaptcha' in page
                        else 'hcaptcha' if 'hcaptcha' in page
                        else 'sat_image')
                    await self._inject_captcha_token(token, ptype)
                    try:
                        from selenium.webdriver.common.by import By
                        # Esperar a que el portal valide el token antes de submit
                        await asyncio.sleep(3)
                        # Intentar submit via JS primero (más confiable post-captcha)
                        submitted = False
                        try:
                            self.driver.execute_script(
                                "document.querySelector('form').submit();"
                            )
                            submitted = True
                        except Exception:
                            pass
                        if not submitted:
                            btn = self.driver.find_element(By.XPATH,
                                "//input[@type='submit'] | //button[@type='submit'] | //input[@id='submit']")
                            btn.click()
                        await asyncio.sleep(8)
                        page = self.driver.page_source.lower()
                        url  = self.driver.current_url.lower()
                        logger.info(f"[SAT] Post-submit-1 URL: {url}")

                        # ── Éxito en primer intento ───────────────────────────
                        if any(x in url for x in ['consulta','receptor','emisor','contribuyente','portalcfdi']):
                            self.logged_in = True
                            return {'success': True, 'message': f'Autenticación exitosa con SAT. RFC: {rfc}', 'rfc': rfc}

                        # ── Segundo CAPTCHA ───────────────────────────────────
                        if 'captcha' in page:
                            logger.info("[SAT] Segundo CAPTCHA detectado, resolviendo...")
                            token2 = await self._solve_captcha()
                            if token2:
                                await self._inject_captcha_token(token2, 'sat_image')
                                await asyncio.sleep(2)
                                # Submit #2
                                for by2, sel2 in [
                                    (By.ID,    'submit'),
                                    (By.XPATH, "//input[@type='submit']"),
                                    (By.XPATH, "//button[@type='submit']"),
                                ]:
                                    try:
                                        btn2 = self.driver.find_element(by2, sel2)
                                        self.driver.execute_script("arguments[0].click();", btn2)
                                        logger.info(f"[SAT] Submit #2 ejecutado: {sel2}")
                                        break
                                    except Exception:
                                        continue
                                await asyncio.sleep(8)
                                url2  = self.driver.current_url.lower()
                                page2 = self.driver.page_source.lower()
                                logger.info(f"[SAT] Post-submit-2 URL: {url2}")
                                if any(x in url2 for x in ['consulta','receptor','emisor','contribuyente','portalcfdi']):
                                    self.logged_in = True
                                    return {'success': True, 'message': f'Autenticación exitosa con SAT. RFC: {rfc}', 'rfc': rfc}
                                if 'captcha' in page2:
                                    return {'success': False, 'error': 'SAT requiere más de 2 CAPTCHAs — IP bloqueada temporalmente. Intenta en 10 minutos.'}
                                return {'success': False, 'error': 'CAPTCHA resuelto pero login falló tras 2 intentos. Reintenta.'}
                            else:
                                return {'success': False, 'error': 'No se pudo resolver el segundo CAPTCHA del SAT.'}

                        return {'success': False, 'error': 'Login falló — respuesta inesperada del portal SAT.'}
                    except Exception as ce:
                        logger.error(f"[SAT] Error post-captcha: {ce}")
                    return {'success': False, 'error': 'CAPTCHA resuelto pero login falló. Reintenta.'}
                else:
                    return {'success': False,
                            'error': 'CAPTCHA detectado. Agrega TWOCAPTCHA_API_KEY en Railway Variables.'}

            # Login exitoso si la URL cambió a consulta o al portal
            success_indicators = ['consulta', 'receptor', 'emisor', 'contribuyente', 'portalcfdi']
            if any(ind in url for ind in success_indicators) or 'portalcfdi' in url:
                self.logged_in = True
                logger.info(f"[SAT] Login exitoso: {url}")
                return {'success': True, 'message': f'Autenticación exitosa con SAT. RFC: {rfc}', 'rfc': rfc}

            # Si la URL no cambió significa posible error
            self._screenshot('login_unknown')
            return {'success': False,
                    'error': 'No se pudo verificar el login. El portal SAT puede estar en mantenimiento.',
                    'debug_url': self.driver.current_url[:200],
                    'debug_page_snippet': self.driver.page_source[500:1000]}

        except Exception as e:
            logger.error(f"[SAT] Error login: {e}")
            return {'success': False, 'error': f'Error inesperado: {str(e)}'}

    # ── Consulta y descarga de CFDIs ──────────────────────────────────────

    async def download_cfdis(
        self,
        tipo: str,            # 'recibidos' | 'emitidos'
        fecha_inicio: datetime,
        fecha_fin: datetime,
        tipo_comprobante: str = 'T',  # I=Ingreso E=Egreso P=Pago N=Nomina T=Traslado ''=Todos
    ) -> List[Dict]:
        """
        Descarga la lista de CFDIs del portal SAT para el rango de fechas dado.
        Retorna lista de dicts con uuid, tipo, y xml_content si se pudo descargar.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions as EC

        if not self.logged_in:
            logger.error("[SAT] download_cfdis llamado sin login")
            return []

        url = SAT_RECEPTOR_URL if tipo == 'recibidos' else SAT_EMISOR_URL
        self.driver.get(url)
        await asyncio.sleep(2)

        cfdis: List[Dict] = []
        wait = WebDriverWait(self.driver, 15)

        try:
            # ── Fecha Inicio ──────────────────────────────────────────────
            fi_str = fecha_inicio.strftime('%d/%m/%Y')
            ff_str = fecha_fin.strftime('%d/%m/%Y')

            fi_ids = [
                'ctl00_MainContent_CldFechaInicial2_Calendario_text',
                'txtFechaInicio', 'FechaInicio',
            ]
            ff_ids = [
                'ctl00_MainContent_CldFechaFinal2_Calendario_text',
                'txtFechaFin', 'FechaFin',
            ]

            for fid in fi_ids:
                try:
                    el = self.driver.find_element(By.ID, fid)
                    self.driver.execute_script("arguments[0].value = arguments[1]", el, fi_str)
                    break
                except Exception:
                    continue

            for fid in ff_ids:
                try:
                    el = self.driver.find_element(By.ID, fid)
                    self.driver.execute_script("arguments[0].value = arguments[1]", el, ff_str)
                    break
                except Exception:
                    continue

            await asyncio.sleep(0.5)

            # ── Tipo de Comprobante ───────────────────────────────────────
            if tipo_comprobante and tipo_comprobante != 'todos':
                try:
                    sel_el = self.driver.find_element(
                        By.XPATH,
                        "//select[contains(@id,'TipoComprobante') or contains(@name,'TipoComprobante')]"
                    )
                    Select(sel_el).select_by_value(tipo_comprobante)
                except Exception:
                    pass

            # ── Estado del CFDI → Vigente ────────────────────────────────
            try:
                est_el = self.driver.find_element(
                    By.XPATH,
                    "//select[contains(@id,'EstadoComprobante') or contains(@name,'Estado')]"
                )
                Select(est_el).select_by_value('1')  # 1 = Vigente
            except Exception:
                pass

            # ── Botón Buscar ──────────────────────────────────────────────
            buscar_btn = None
            for by, sel in [
                (By.ID,    'ctl00_MainContent_BtnBusqueda'),
                (By.XPATH, "//input[@value='Buscar CFDI']"),
                (By.XPATH, "//button[contains(text(),'Buscar')]"),
                (By.CSS_SELECTOR, "input[value*='Buscar']"),
            ]:
                try:
                    buscar_btn = self.driver.find_element(by, sel)
                    break
                except Exception:
                    continue

            if not buscar_btn:
                logger.error("[SAT] No se encontró el botón Buscar CFDI")
                self._screenshot(f'no_buscar_{tipo}')
                return []

            buscar_btn.click()
            await asyncio.sleep(4)

        except Exception as e:
            logger.error(f"[SAT] Error llenando formulario {tipo}: {e}")
            return []

        # ── Parsear resultados ────────────────────────────────────────────
        try:
            page = self.driver.page_source
            # UUIDs en la página
            uuid_re = re.compile(
                r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
            )
            uuids = set(uuid_re.findall(page))
            logger.info(f"[SAT] {tipo}: {len(uuids)} UUIDs encontrados")

            for uid in uuids:
                cfdis.append({'uuid': uid.upper(), 'tipo': tipo, 'xml_content': None})

            # Intentar descargar XMLs
            for cfdi in cfdis:
                xml = await self._try_download_xml(cfdi['uuid'])
                if xml:
                    cfdi['xml_content'] = xml

        except Exception as e:
            logger.error(f"[SAT] Error parseando resultados: {e}")

        return cfdis

    async def _try_download_xml(self, uuid: str) -> Optional[str]:
        """Intenta descargar el XML individual del CFDI."""
        from selenium.webdriver.common.by import By
        try:
            selectors = [
                f"//a[contains(@href,'{uuid}')]",
                f"//a[contains(@onclick,'{uuid.lower()}')]",
                f"//img[contains(@id,'{uuid}')]/parent::a",
            ]
            for sel in selectors:
                try:
                    link = self.driver.find_element(By.XPATH, sel)
                    link.click()
                    await asyncio.sleep(2)
                    # Buscar el XML en download_dir
                    for f in glob.glob(os.path.join(self.download_dir, '*.xml')):
                        with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                            content = fh.read()
                        os.remove(f)
                        if uuid.upper() in content.upper():
                            return content
                    break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[SAT] No se pudo descargar XML {uuid}: {e}")
        return None

    # ── Funciones adicionales del portal ─────────────────────────────────

    async def get_declaraciones_pendientes(self) -> List[Dict]:
        """Consulta declaraciones pendientes en el portal SAT."""
        from selenium.webdriver.common.by import By
        if not self.logged_in:
            return []
        try:
            self.driver.get(SAT_DECLARACIONES)
            await asyncio.sleep(3)
            page = self.driver.page_source
            # Extraer texto de obligaciones
            from selenium.webdriver.support.ui import WebDriverWait
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tr, .obligacion, .declaracion")
            result = []
            for row in rows:
                text = row.text.strip()
                if text and len(text) > 10:
                    result.append({'descripcion': text})
            return result[:20]
        except Exception as e:
            logger.error(f"[SAT] Error consultando declaraciones: {e}")
            return []

    async def get_opinion_cumplimiento(self, rfc: str) -> Dict:
        """
        Consulta la Opinión de Cumplimiento Fiscal (32-D) del SAT.
        Requiere estar logueado.
        """
        from selenium.webdriver.common.by import By
        if not self.logged_in:
            return {'error': 'No autenticado'}
        try:
            opinion_url = (
                "https://www.sat.gob.mx/aplicacion/53714/"
                "consulta-tu-opinion-del-cumplimiento-de-obligaciones-fiscales"
            )
            self.driver.get(opinion_url)
            await asyncio.sleep(3)
            page = self.driver.page_source.lower()
            if 'positiva' in page:
                return {'status': 'positiva', 'rfc': rfc,
                        'mensaje': 'Opinión de cumplimiento POSITIVA'}
            elif 'negativa' in page:
                return {'status': 'negativa', 'rfc': rfc,
                        'mensaje': 'Opinión de cumplimiento NEGATIVA'}
            else:
                return {'status': 'desconocido', 'rfc': rfc,
                        'mensaje': 'No se pudo determinar la opinión de cumplimiento'}
        except Exception as e:
            logger.error(f"[SAT] Error opinión cumplimiento: {e}")
            return {'error': str(e)}

    async def get_buzon_tributario(self) -> List[Dict]:
        """
        Lee los mensajes del Buzón Tributario SAT.
        """
        from selenium.webdriver.common.by import By
        if not self.logged_in:
            return []
        try:
            self.driver.get(SAT_BUZONTRIB)
            await asyncio.sleep(4)
            mensajes = []
            rows = self.driver.find_elements(
                By.CSS_SELECTOR,
                "table tr, .mensaje, .notificacion, .avisos tr"
            )
            for row in rows:
                text = row.text.strip()
                if text and len(text) > 15:
                    mensajes.append({'texto': text[:300]})
            return mensajes[:15]
        except Exception as e:
            logger.error(f"[SAT] Error Buzón Tributario: {e}")
            return []

    async def get_constancia_fiscal(self, rfc: str) -> Dict:
        """
        Descarga la Constancia de Situación Fiscal (CIF) del portal SAT autenticado.
        Requiere sesión activa (logged_in=True).
        """
        import base64
        from selenium.webdriver.common.by import By
        if not self.logged_in:
            return {'success': False, 'error': 'No autenticado'}
        try:
            self.driver.get(SAT_CIF_URL)
            await asyncio.sleep(5)

            btn = None
            for by, sel in [
                (By.XPATH,       "//a[contains(translate(text(),'constanciagenerar','CONSTANCIAGENERAR'),'CONSTANCIA') or contains(translate(text(),'constanciagenerar','CONSTANCIAGENERAR'),'GENERAR') or contains(translate(text(),'constanciagenerar','CONSTANCIAGENERAR'),'DESCARGAR')]"),
                (By.XPATH,       "//button[contains(translate(text(),'constanciagenerar','CONSTANCIAGENERAR'),'CONSTANCIA') or contains(translate(text(),'constanciagenerar','CONSTANCIAGENERAR'),'GENERAR')]"),
                (By.XPATH,       "//input[@value='Generar' or @value='Descargar' or @value='Constancia']"),
                (By.CSS_SELECTOR,"a[href*='constancia'], a[href*='pdf'], button[id*='constancia'], a[id*='constancia']"),
                (By.XPATH,       "//a[contains(@href,'pdf')] | //a[contains(@onclick,'pdf')]"),
            ]:
                try:
                    btn = self.driver.find_element(by, sel)
                    break
                except Exception:
                    continue

            if not btn:
                self._screenshot('cif_no_btn')
                return {'success': False, 'error': 'No se encontró el botón para generar la Constancia Fiscal en el portal SAT'}

            btn.click()
            await asyncio.sleep(8)

            pdf_files = glob.glob(os.path.join(self.download_dir, '*.pdf'))
            if not pdf_files:
                self._screenshot('cif_no_pdf')
                return {'success': False, 'error': 'No se descargó ningún PDF de Constancia Fiscal'}

            pdf_path = pdf_files[0]
            filename = f'Constancia_{rfc}.pdf'
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            os.remove(pdf_path)

            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            logger.info(f"[SAT] Constancia Fiscal descargada para RFC={rfc}, size={len(pdf_bytes)} bytes")
            return {'success': True, 'pdf_base64': pdf_base64, 'filename': filename}

        except Exception as e:
            logger.error(f"[SAT] Error descargando Constancia Fiscal: {e}")
            return {'success': False, 'error': str(e)}


# ─── CFDI XML Parser ─────────────────────────────────────────────────────────

class CFDIParser:
    NS = {
        'cfdi4': 'http://www.sat.gob.mx/cfd/4',
        'cfdi3': 'http://www.sat.gob.mx/cfd/3',
        'tfd':   'http://www.sat.gob.mx/TimbreFiscalDigital',
    }
    TIPO_MAP = {'I': 'ingreso', 'E': 'egreso', 'P': 'pago', 'N': 'nomina', 'T': 'traslado'}

    @classmethod
    def parse_xml(cls, xml_string: str) -> Optional[Dict]:
        try:
            xml_string = xml_string.strip().lstrip('\ufeff')
            root = ET.fromstring(xml_string.encode('utf-8'))
            version = root.get('Version', root.get('version', '4.0'))
            ns = cls.NS['cfdi4'] if version.startswith('4') else cls.NS['cfdi3']

            def g(attr, default=''):
                return root.get(attr, default) or default

            data = {
                'version': version,
                'serie': g('Serie'), 'folio': g('Folio'),
                'fecha_emision': g('Fecha'),
                'forma_pago': g('FormaPago'),
                'metodo_pago': g('MetodoPago'),
                'moneda': g('Moneda', 'MXN'),
                'tipo_cambio': float(g('TipoCambio', '1') or 1),
                'tipo_comprobante': g('TipoDeComprobante'),
                'subtotal': float(g('SubTotal', '0') or 0),
                'descuento': float(g('Descuento', '0') or 0),
                'total': float(g('Total', '0') or 0),
            }
            data['tipo_cfdi'] = cls.TIPO_MAP.get(data['tipo_comprobante'], 'otro')

            emisor = root.find(f'.//{{{ns}}}Emisor')
            if emisor is not None:
                data.update({'emisor_rfc': emisor.get('Rfc', ''),
                             'emisor_nombre': emisor.get('Nombre', ''),
                             'regimen_fiscal': emisor.get('RegimenFiscal', '')})

            receptor = root.find(f'.//{{{ns}}}Receptor')
            if receptor is not None:
                data.update({'receptor_rfc': receptor.get('Rfc', ''),
                             'receptor_nombre': receptor.get('Nombre', ''),
                             'uso_cfdi': receptor.get('UsoCFDI', '')})

            for ns_uri in cls.NS.values():
                tfd = root.find(f'.//{{{ns_uri}}}TimbreFiscalDigital')
                if tfd is not None:
                    data.update({'uuid': tfd.get('UUID', ''),
                                 'fecha_timbrado': tfd.get('FechaTimbrado', '')})
                    break

            imp = root.find(f'.//{{{ns}}}Impuestos')
            data['iva_trasladado'] = float(getattr(imp, 'attrib', {}).get('TotalImpuestosTrasladados', 0) or 0)
            data['isr_retenido']   = float(getattr(imp, 'attrib', {}).get('TotalImpuestosRetenidos', 0) or 0)

            return data
        except Exception as e:
            logger.error(f"[CFDIParser] Error: {e}")
            return None


# ─── SAT Sync Service ────────────────────────────────────────────────────────

class SATSyncService:
    def __init__(self, db):
        self.db = db
        self.credential_manager = SATCredentialManager(db)

    async def validate_credentials(self, rfc: str, ciec: str) -> Dict:
        client = SATPortalClient()
        try:
            return await client.login(rfc, ciec)
        finally:
            client.close()

    async def sync_cfdis(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        incluir_emitidos: bool = True,
        incluir_recibidos: bool = True,
        tipo_comprobante: str = '',   # '' = todos
    ) -> Dict:
        creds = await self.credential_manager.get_credentials(company_id)
        if not creds:
            return {'success': False, 'error': 'No hay credenciales SAT configuradas'}

        results = {
            'success': True,
            'emitidos':  {'downloaded': 0, 'new': 0, 'updated': 0, 'errors': 0},
            'recibidos': {'downloaded': 0, 'new': 0, 'updated': 0, 'errors': 0},
            'total_new': 0, 'total_updated': 0,
            'errors': [], 'sync_date': datetime.now(timezone.utc).isoformat(),
        }

        client = SATPortalClient()
        try:
            login_res = await client.login(creds['rfc'], creds['ciec'])
            if not login_res.get('success'):
                return {'success': False, 'error': login_res.get('error', 'Error de autenticación')}

            for tipo, flag in [('recibidos', incluir_recibidos), ('emitidos', incluir_emitidos)]:
                if not flag:
                    continue
                items = await client.download_cfdis(tipo, fecha_inicio, fecha_fin, tipo_comprobante)
                results[tipo]['downloaded'] = len(items)
                for item in items:
                    try:
                        saved = await self._save_cfdi(item, company_id,
                                                       'recibido' if tipo == 'recibidos' else 'emitido')
                        if saved == 'new':
                            results[tipo]['new'] += 1
                        elif saved == 'updated':
                            results[tipo]['updated'] += 1
                    except Exception as e:
                        results[tipo]['errors'] += 1
                        results['errors'].append(f"{tipo} {item.get('uuid','?')}: {e}")

            results['total_new']     = results['emitidos']['new']     + results['recibidos']['new']
            results['total_updated'] = results['emitidos']['updated'] + results['recibidos']['updated']

            await self.credential_manager.update_last_sync(company_id, {
                'total_new': results['total_new'],
                'total_updated': results['total_updated'],
                'errors_count': len(results['errors']),
            })
            return results

        except Exception as e:
            logger.error(f"[SAT] sync_cfdis error: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            client.close()

    async def sync_extras(self, company_id: str) -> Dict:
        """
        Sincroniza datos adicionales: Opinión de Cumplimiento y Buzón Tributario.
        """
        creds = await self.credential_manager.get_credentials(company_id)
        if not creds:
            return {'success': False, 'error': 'No hay credenciales SAT configuradas'}

        client = SATPortalClient()
        result = {'success': True, 'opinion': {}, 'buzon': [], 'declaraciones': []}
        try:
            login_res = await client.login(creds['rfc'], creds['ciec'])
            if not login_res.get('success'):
                return {'success': False, 'error': login_res.get('error')}

            result['opinion']       = await client.get_opinion_cumplimiento(creds['rfc'])
            result['buzon']         = await client.get_buzon_tributario()
            result['declaraciones'] = await client.get_declaraciones_pendientes()

            # Guardar en MongoDB
            await self.db.sat_extras.update_one(
                {'company_id': company_id},
                {'$set': {
                    'company_id': company_id,
                    'opinion_cumplimiento': result['opinion'],
                    'buzon_mensajes': result['buzon'],
                    'declaraciones_pendientes': result['declaraciones'],
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True
            )
            return result
        finally:
            client.close()

    async def sync_constancia(self, company_id: str) -> Dict:
        """Descarga la Constancia de Situación Fiscal y la guarda en MongoDB."""
        creds = await self.credential_manager.get_credentials(company_id)
        if not creds:
            return {'success': False, 'error': 'No hay credenciales SAT configuradas'}

        client = SATPortalClient()
        try:
            login_res = await client.login(creds['rfc'], creds['ciec'])
            if not login_res.get('success'):
                return {'success': False, 'error': login_res.get('error')}

            result = await client.get_constancia_fiscal(creds['rfc'])
            if result.get('success'):
                await self.db.sat_constancia.update_one(
                    {'company_id': company_id},
                    {'$set': {
                        'company_id': company_id,
                        'rfc': creds['rfc'],
                        'pdf_base64': result['pdf_base64'],
                        'filename': result['filename'],
                        'fecha_descarga': datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
            return result
        finally:
            client.close()

    async def _save_cfdi(self, cfdi_info: Dict, company_id: str, origen: str) -> str:
        uid = cfdi_info.get('uuid', '').upper()
        if not uid:
            raise ValueError('CFDI sin UUID')

        existing = await self.db.cfdis.find_one(
            {'uuid': uid, 'company_id': company_id}, {'_id': 0, 'id': 1}
        )

        parsed = CFDIParser.parse_xml(cfdi_info['xml_content']) if cfdi_info.get('xml_content') else None

        if existing:
            if parsed:
                await self.db.cfdis.update_one(
                    {'id': existing['id']},
                    {'$set': {'xml_original': cfdi_info['xml_content'],
                              'updated_at': datetime.now(timezone.utc).isoformat()}}
                )
                return 'updated'
            return 'exists'

        now = datetime.now(timezone.utc)
        doc = {
            'id': str(uuid_module.uuid4()),
            'company_id': company_id,
            'uuid': uid,
            'origen': origen,
            'source': 'sat_ciec_sync',
            'estado_conciliacion': 'pendiente',
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'moneda': 'MXN',
            'total': 0, 'subtotal': 0,
            'tipo_cfdi': 'ingreso' if origen == 'recibido' else 'egreso',
            'fecha_emision': now.isoformat(),
        }
        if parsed:
            doc.update({k: v for k, v in parsed.items() if v is not None})
        if cfdi_info.get('xml_content'):
            doc['xml_original'] = cfdi_info['xml_content']

        await self.db.cfdis.insert_one(doc)
        return 'new'
