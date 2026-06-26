/**
 * sessionStore.js
 * 
 * Usa sessionStorage para datos de sesión (token, user, selectedCompany)
 * para que cada pestaña del browser pueda tener una sesión independiente.
 * 
 * Fallback a localStorage si sessionStorage no está disponible.
 * 
 * Preferencias de usuario (tema, idioma, etc.) siguen en localStorage.
 */

const SESSION_KEYS = ['token', 'user', 'selectedCompany'];

/**
 * Lee un valor — busca primero en sessionStorage, luego en localStorage
 * (compatibilidad con sesiones previas guardadas en localStorage).
 */
export function sessionGet(key) {
  try {
    // Primero sessionStorage (sesión actual de la pestaña)
    const val = sessionStorage.getItem(key);
    if (val !== null) return val;
    // Fallback: si existe en localStorage (sesión anterior), migrarlo
    const legacy = localStorage.getItem(key);
    if (legacy !== null && SESSION_KEYS.includes(key)) {
      // Migrar a sessionStorage y limpiar localStorage para esta clave
      sessionStorage.setItem(key, legacy);
      // NO borramos de localStorage aquí para no romper otras pestañas abiertas
      return legacy;
    }
    return null;
  } catch {
    return localStorage.getItem(key);
  }
}

/**
 * Guarda en sessionStorage (solo para la pestaña actual).
 */
export function sessionSet(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    localStorage.setItem(key, value);
  }
}

/**
 * Elimina de sessionStorage (cierre de sesión de esta pestaña).
 */
export function sessionRemove(key) {
  try {
    sessionStorage.removeItem(key);
    // También limpiar de localStorage por si quedó ahí
    localStorage.removeItem(key);
  } catch {
    localStorage.removeItem(key);
  }
}
