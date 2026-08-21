/**
 * Cookie names, with no runtime dependencies.
 *
 * Separate from `lib/session.ts` because that module is `server-only` and
 * reads `next/headers`, neither of which is available to `proxy.ts` — it runs
 * before rendering, in the edge runtime.
 */

/** Holds the access token. httpOnly: unreadable by page scripts. */
export const SESSION_COOKIE = "atlas_session";

/** Display-only identity. Readable, and never trusted for authorisation. */
export const PROFILE_COOKIE = "atlas_profile";
