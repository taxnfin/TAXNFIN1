import axios from 'axios';

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
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add selected company ID to all requests
    const selectedCompany = localStorage.getItem('selectedCompany');
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
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      localStorage.removeItem('selectedCompany');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
