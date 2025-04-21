import axios from "axios";

export const apiBase = axios.create({
  baseURL: "http://89.169.2.93:8000",
});

apiBase.interceptors.request.use(config => {
//   const token = localStorage.getItem("token");
//   if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const getUser = async(phone_number) => apiBase.get(`/api/v1/customers/retrieve/${phone_number}`);

export const getDialog= async({phone_number, limit}) => apiBase.get(`/api/v1/history/${phone_number}?limit=${limit}`,);
export const sendDialog= async(body) => apiBase.post(`/api/v1/submit_operator_response`, body);

export const getAnalyze = async(body) => apiBase.post(`/api/v1/analyze`, body);