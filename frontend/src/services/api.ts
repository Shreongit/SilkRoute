import type { Product, ProductResourceInfo } from '../types';

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api/v1').replace(/\/$/, '');
const tokenKey = 'silk-route-access-token';
export const getToken = () => window.localStorage.getItem(tokenKey);
export const setToken = (token: string | null) => token ? window.localStorage.setItem(tokenKey, token) : window.localStorage.removeItem(tokenKey);
export const apiEnabled = import.meta.env.VITE_USE_MOCK_CATALOGUE !== 'true';

export class ApiError extends Error {
  status: number;
  details?: Record<string, string>;
  constructor(message: string, status: number, details?: Record<string, string>) { super(message); this.status = status; this.details = details; }
}

interface ApiEnvelope<T> { data: T; meta?: { count: number; page: number; per_page: number; pages: number }; error?: { message?: string; details?: Record<string, string> } }
async function apiEnvelope<T>(path: string, init: RequestInit = {}): Promise<ApiEnvelope<T>> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new ApiError('Could not reach the Silk Route API. Check that Flask is running and VITE_API_BASE_URL points to it.', 0);
  }
  let payload: ApiEnvelope<T>;
  try {
    payload = await response.json() as ApiEnvelope<T>;
  } catch {
    throw new ApiError('The API returned an unreadable response. Check the Flask server logs.', response.status);
  }
  if (!response.ok) throw new ApiError(payload.error?.message || 'The request could not be completed.', response.status, payload.error?.details);
  return payload;
}
export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> { return (await apiEnvelope<T>(path, init)).data; }

export interface ApiProduct extends Product { creator_id: string; creator?: string; creator_handle?: string; created_at?: string; resources?: ProductResourceInfo[]; }
export function normalizeProduct(item: ApiProduct): Product {
  const resolveImage = (path: string) => path.startsWith('/') ? `${new URL(baseUrl).origin}${path}` : path;
  const labels: Record<string, Product['product_label']> = { Wallpapers: 'wallpaper', 'Mobile Icon Packs': 'icon', 'Digital Art & Illustrations': 'art', 'Canva Designs': 'canva' };
  const product_label = item.product_label || labels[item.category] || undefined;
  return { ...item, product_label, creatorId: item.creator_id, creatorName: item.creator, creatorHandle: item.creator_handle, createdAt: item.created_at || new Date().toISOString(), images: (item.images || []).map(resolveImage), image: item.image ? resolveImage(item.image) : '', status: item.status || 'published' };
}

export async function listProducts(params = ''): Promise<Product[]> {
  const result = await apiRequest<ApiProduct[]>(`/products${params ? `?${params}` : ''}`);
  return result.map(normalizeProduct);
}
export async function searchProducts(filters: Record<string,string>): Promise<{items:Product[];count:number;page:number;pages:number}> {
  const query = new URLSearchParams(filters).toString();
  const result = await apiEnvelope<ApiProduct[]>(`/products?${query}`);
  return {items:result.data.map(normalizeProduct),count:result.meta?.count||0,page:result.meta?.page||1,pages:result.meta?.pages||0};
}
export async function getProduct(id: string): Promise<Product> { return normalizeProduct(await apiRequest<ApiProduct>(`/products/${encodeURIComponent(id)}`)); }
export interface ApiCreator { id: string; handle: string; display_name: string; bio: string; products?: Product[]; products_count?: number; }
export async function getCreator(handle: string): Promise<ApiCreator> { const result = await apiRequest<ApiCreator & {products?: ApiProduct[]}>(`/creators/${encodeURIComponent(handle)}`); return {...result, products: result.products?.map(normalizeProduct)}; }
export async function listCreators(): Promise<ApiCreator[]> { return apiRequest<ApiCreator[]>('/creators'); }
export async function login(email: string, password: string) { return apiRequest<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }); }
export async function register(input: { email: string; password: string; display_name: string; handle: string }) { return apiRequest<{ access_token: string }>('/auth/register', { method: 'POST', body: JSON.stringify(input) }); }
export async function logout() { try { await apiRequest('/auth/logout', { method: 'POST' }); } finally { setToken(null); } }
export async function myProducts() { const items = await apiRequest<ApiProduct[]>('/creator/products'); return items.map(normalizeProduct); }
export async function createDraft(body: Record<string, unknown>) { return normalizeProduct(await apiRequest<ApiProduct>('/creator/products', { method: 'POST', body: JSON.stringify(body) })); }
export async function updateDraft(id: string, body: Record<string, unknown>) { return normalizeProduct(await apiRequest<ApiProduct>(`/creator/products/${id}`, { method: 'PATCH', body: JSON.stringify(body) })); }
export async function productAction(id: string, action: 'publish' | 'unpublish') { return normalizeProduct(await apiRequest<ApiProduct>(`/creator/products/${id}/${action}`, { method: 'POST' })); }
export async function uploadPreview(id: string, file: File) { const data = new FormData(); data.set('file', file); return apiRequest(`/creator/products/${id}/previews`, { method: 'POST', body: data }); }
export async function uploadResource(id: string, file: File) { const data = new FormData(); data.set('file', file); return apiRequest(`/creator/products/${id}/resources`, { method: 'POST', body: data }); }
export async function registerCanvaResource(id: string, template_url: string) { return apiRequest(`/creator/products/${id}/resources`, { method: 'POST', body: JSON.stringify({ template_url }) }); }
