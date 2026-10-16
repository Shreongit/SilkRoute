export type ProductCategory = 'Wallpapers' | 'Digital Art & Illustrations' | 'Canva Designs' | 'Mobile Icon Packs' | 'wallpaper' | 'icon' | 'art' | 'canva';
export interface Creator { id: string; name: string; handle: string; bio: string; avatar: string; location: string; }
export interface ProductResourceInfo { id: string; resource_type: 'file' | 'canva_url'; display_name: string; file_format?: string; }
export interface Product { id: string; digital_product_id?: string | null; s_no?: number | null; product_label?: 'wallpaper' | 'icon' | 'art' | 'canva'; slug?: string; title: string; creatorId: string; creatorName?: string; creatorHandle?: string; category: ProductCategory; description: string; price: number; currency?: string; image: string; images: string[]; createdAt: string; status?: 'draft' | 'published'; tags?: string[]; metadata?: Record<string, unknown>; resources?: ProductResourceInfo[]; featured?: boolean; }
export interface User { id: string; email: string; displayName: string; }
export interface CreatorProfile extends Creator { userId: string; }
export interface ProductAsset { id: string; productId: string; storageKey: string; fileType: string; }
export interface Order { id: string; buyerId: string; status: 'pending' | 'paid' | 'refunded'; }
export interface OrderItem { orderId: string; productId: string; unitPrice: number; }
export interface DownloadRecord { id: string; orderItemId: string; downloadedAt: string; }
export interface PaymentRecord { id: string; orderId: string; providerReference: string; amount: number; }
