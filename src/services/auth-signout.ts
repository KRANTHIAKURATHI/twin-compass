/**
 * Sign-out signalling. No browser or framework imports at module level (unit-tested in Node).
 *
 * Two small, NON-credential pieces of state:
 *
 *  - A cross-tab "SIGNED_OUT" event over BroadcastChannel. The message is the literal `{ type: "SIGNED_OUT" }`
 *    and nothing else: never an access token, refresh token, session, user, cookie or timestamp. A receiving tab
 *    clears its own in-memory state. Without BroadcastChannel the event is simply not delivered (other tabs
 *    sign out when their in-memory access token expires, as before).
 *
 *  - A "logout pending" marker (one boolean-ish localStorage entry). It records that THIS browser's user chose to
 *    sign out and the server-side revocation has not been confirmed yet (the logout request failed, or the tab
 *    was closed mid-request). The refresh cookie is HttpOnly, so the page cannot delete it; without the marker a
 *    reload would silently sign the user back in through the still-valid cookie. While it is set, startup and 401
 *    recovery do not refresh; startup retries the logout instead. It holds no secret and cannot sign anyone in.
 */
export const SIGNED_OUT_CHANNEL = "oncotwin:auth-signout";
export const SIGNED_OUT_EVENT = "SIGNED_OUT";
export const LOGOUT_PENDING_KEY = "oncotwin.logout_pending";

interface ChannelLike {
  postMessage(message: unknown): void;
  close(): void;
  onmessage: ((event: { data: unknown }) => void) | null;
}
type ChannelFactory = ((name: string) => ChannelLike) | null;

function defaultChannelFactory(): ChannelFactory {
  const BC = (globalThis as { BroadcastChannel?: new (name: string) => ChannelLike }).BroadcastChannel;
  return typeof BC === "function" ? (name) => new BC(name) : null;
}

export interface SignOutBus {
  /** Tell the other tabs to sign out. Carries no data. Never throws. */
  broadcastSignedOut(): void;
  /** Run `cb` when another tab signs out. Returns an unsubscribe function. Never throws. */
  onSignedOut(cb: () => void): () => void;
  /** False when the browser has no BroadcastChannel. */
  readonly available: boolean;
}

export function createSignOutBus(factory: ChannelFactory | undefined = undefined): SignOutBus {
  const make = factory === undefined ? defaultChannelFactory() : factory;
  let sender: ChannelLike | null = null;
  return {
    available: make !== null,
    broadcastSignedOut() {
      if (!make) return;
      try {
        sender ??= make(SIGNED_OUT_CHANNEL);
        sender.postMessage({ type: SIGNED_OUT_EVENT }); // the entire payload
      } catch {
        /* a failed broadcast must never block sign-out */
      }
    },
    onSignedOut(cb) {
      if (!make) return () => {};
      let channel: ChannelLike | null = null;
      try {
        channel = make(SIGNED_OUT_CHANNEL);
        channel.onmessage = (event) => {
          const data = event?.data as { type?: unknown } | null;
          if (data && typeof data === "object" && data.type === SIGNED_OUT_EVENT) cb(); // anything else is ignored
        };
      } catch {
        return () => {};
      }
      return () => {
        try {
          channel?.close();
        } catch {
          /* ignore */
        }
      };
    },
  };
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface LogoutMarker {
  isSet(): boolean;
  set(): void;
  clear(): void;
}

/** Storage can be missing or throw (private mode, blocked site data): the marker then degrades to "not set". */
export function createLogoutMarker(storage: StorageLike | null | undefined = undefined): LogoutMarker {
  const resolve = (): StorageLike | null => {
    if (storage !== undefined) return storage;
    try {
      return (globalThis as { localStorage?: StorageLike }).localStorage ?? null;
    } catch {
      return null;
    }
  };
  return {
    isSet() {
      try {
        return resolve()?.getItem(LOGOUT_PENDING_KEY) === "1";
      } catch {
        return false;
      }
    },
    set() {
      try {
        resolve()?.setItem(LOGOUT_PENDING_KEY, "1");
      } catch {
        /* ignore */
      }
    },
    clear() {
      try {
        resolve()?.removeItem(LOGOUT_PENDING_KEY);
      } catch {
        /* ignore */
      }
    },
  };
}
