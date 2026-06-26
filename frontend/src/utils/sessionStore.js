/**
 * sessionStore.js
 * 
 * Usa sessionStorage para datos de sesión (token, user, selectedCompany)
 * para que cada pestaña del browser pueda tener una sesión independiente.
 * 
 * IMPORTANTE: Lee sessionStorage primero, luego localStorage como fallback
 * de solo lectura (compatibilidad con páginas que aún usan localStorage directamente).
 * Los WRITES siempre van a sessionStorage únicamente.
 * 
 * Preferencias de usuario (tema, idioma, etc.) siguen en localStorage.
 */

/**
 * Lee un valor de sessionStorage. Si no existe, lee de localStorage como fallback.
 * Esto permite compatibilidad con páginas que aún leen localStorage directamente.
 */
export function sessionGet(key) {
  try {
    const val = sessionStorage.getItem(key);
    if (val !== null) return val;
    // Fallback de solo lectura — no migra, solo lee
    return localStorage.getItem(key);
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
