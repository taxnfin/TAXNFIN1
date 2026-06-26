/**
 * sessionStore.js
 * 
 * Usa sessionStorage para datos de sesión (token, user, selectedCompany)
 * para que cada pestaña del browser pueda tener una sesión independiente.
 * 
 * IMPORTANTE: NO hereda de localStorage — cada pestaña nueva debe hacer login.
 * Esto permite tener múltiples cuentas abiertas simultáneamente en pestañas distintas.
 * 
 * Preferencias de usuario (tema, idioma, etc.) siguen en localStorage.
 */

/**
 * Lee un valor de sessionStorage (solo de la pestaña actual).
 * Si no existe, devuelve null — NO hace fallback a localStorage.
 */
export function sessionGet(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Guarda en sessionStorage (solo para la pestaña actual).
 */
export function sessionSet(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // fallback silencioso
  }
}

/**
 * Elimina de sessionStorage y localStorage (cierre de sesión).
 */
export function sessionRemove(key) {
  try {
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
  } catch {
    localStorage.removeItem(key);
  }
}
