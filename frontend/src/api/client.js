import axios from "axios";

const baseURL = process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";
export const api = axios.create({ baseURL });

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response && err.response.status === 401) {
      // TODO: 统一未登录处理（跳转到 /login）
    }
    return Promise.reject(err);
  }
);