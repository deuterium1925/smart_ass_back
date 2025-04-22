import axios from "axios";

const apiUrl = import.meta.env.VITE_API_URL;

export const apiBase = axios.create({
  baseURL: apiUrl,
});

apiBase.interceptors.request.use(config => {
  return config;
});

export const getUser = async(phone_number) => apiBase.get(`/api/v1/customers/retrieve/${phone_number}`);

export const getDialog= async({phone_number, limit}) => apiBase.get(`/api/v1/history/${phone_number}?limit=${limit}`,);
export const sendDialog= async(body) => apiBase.post(`/api/v1/submit_operator_response`, body);

export const getAnalyze = async(body) => apiBase.post(`/api/v1/analyze`, body);