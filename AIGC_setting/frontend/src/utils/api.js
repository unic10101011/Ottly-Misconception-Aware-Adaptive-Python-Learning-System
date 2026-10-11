import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DeviceInfo from 'react-native-device-info';

const api = axios.create({
  baseURL: 'https://api.example.com/api/v1', // Should use HTTPS in production
  timeout: 5000,
});

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Anti-replay: timestamp + nonce
  const timestamp = Date.now().toString();
  const nonce = Math.random().toString(36).substring(7);
  config.headers['X-Timestamp'] = timestamp;
  config.headers['X-Nonce'] = nonce;

  // Device info
  const deviceId = await DeviceInfo.getUniqueId();
  config.headers['X-Device-ID'] = deviceId;

  // Idempotency: generate a unique key for non-GET requests if not provided
  if (config.method !== 'get' && !config.headers['X-Idempotency-Key']) {
    config.headers['X-Idempotency-Key'] = `${timestamp}-${nonce}`;
  }

  return config;
}, (error) => {
  return Promise.reject(error);
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response && error.response.status === 401) {
      // Token expired or device logged out
      await AsyncStorage.removeItem('access_token');
      // Force redirect to login (should be handled by navigation)
    }
    return Promise.reject(error);
  }
);

export default api;
