// Shared helpers for AI quota (402) handling and the register-to-unlock funnel.

// Open the auth modal from anywhere (UserMenu listens for this global event).
export function openAuthModal(mode = 'register') {
    window.dispatchEvent(new CustomEvent('open-auth-modal', { detail: { mode } }));
}

// Interpret a FastAPI 402 `detail` payload into a user-facing prompt.
// Returns null if `detail` isn't a recognized quota error.
export function interpretQuota(detail) {
    if (detail && typeof detail === 'object' && detail.reason) {
        if (detail.reason === 'anon_limit') {
            return {
                reason: 'anon_limit',
                canRegister: true,
                message: `You've reached the free usage limit for Matrix AI. `
                    + `Create a free account to unlock 100 monthly AI credits and continue exploring with full AI-powered insights.`,
            };
        }
        if (detail.reason === 'insufficient_credits') {
            return {
                reason: 'insufficient_credits',
                canRegister: false,
                message: `You're out of Matrix Credits. They refresh at the start of next `
                    + `month — or invite friends to earn boost credits.`,
            };
        }
    }
    return null;
}

// Normalize any error `detail` (string or object) into display text.
export function errorText(detail, fallback = 'Something went wrong') {
    if (typeof detail === 'string') return detail;
    const q = interpretQuota(detail);
    if (q) return q.message;
    return fallback;
}
