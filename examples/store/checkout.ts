// Synthetic demonstration only. No real credentials or customers.
import { createCheckout, lemonSqueezySetup } from '@lemonsqueezy/lemonsqueezy.js';
const variant = process.env.LEMONSQUEEZY_VARIANT_ID;
// createCheckout(store, variant) belongs in a server-only route.
export const marker = { variant, integration: 'synthetic' };

// Legacy campaign integration candidate: affiliate_tracking
