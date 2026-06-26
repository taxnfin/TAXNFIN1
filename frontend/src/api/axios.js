import axios from 'axios';
import { sessionGet, sessionRemove } from '../utils/sessionStore';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    // sessionGet busca en sessionStorage primero (por pestaña), luego localStorage
    const token = sessionGet('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    const selectedCompany = sessionGet('selectedCompany');
    if (selectedCompany) {
      try {
        const company = JSON.parse(selectedCompany);
        config.headers['X-Company-ID'] = company.id;
      } catch (e) {
        // Ignore parse errors
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionRemove('token');
      sessionRemove('user');
      sessionRemove('selectedCompany');
      window.location.href = '/login';
    }
    if (error.response?.status === 402) {
      window.location.href = '/account-suspended';
    }
    return Promise.reject(error);
  }
);

export default api;
