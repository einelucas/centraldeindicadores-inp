import { UserManager, WebStorageStateStore, type UserManagerSettings } from "oidc-client-ts";

function oidcManager(): UserManager | null {
  if (!import.meta.client) return null;
  const config = useRuntimeConfig().public;
  if (!config.oidcIssuer || !config.oidcClientId) return null;
  const settings: UserManagerSettings = {
    authority: config.oidcIssuer,
    client_id: config.oidcClientId,
    redirect_uri: config.oidcRedirectUri,
    post_logout_redirect_uri: config.oidcPostLogoutRedirectUri,
    response_type: "code",
    scope: "openid profile email",
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  };
  return new UserManager(settings);
}

export function useAuth() {
  const store = useAuthStore();
  const config = useRuntimeConfig();

  async function login(): Promise<void> {
    const manager = oidcManager();
    if (!manager) throw new Error("OIDC não está configurado neste ambiente.");
    await manager.signinRedirect();
  }

  async function completeLogin(): Promise<void> {
    const manager = oidcManager();
    if (!manager) throw new Error("OIDC não está configurado neste ambiente.");
    const user = await manager.signinRedirectCallback();
    store.acceptToken(user.access_token);
    if (!(await store.loadUser())) throw new Error("A API recusou o token OIDC recebido.");
  }

  async function logout(): Promise<void> {
    const manager = oidcManager();
    store.clear();
    if (manager) await manager.signoutRedirect();
    else await navigateTo("/login");
  }

  return { store, login, completeLogin, logout, devAuthEnabled: config.public.devAuthEnabled };
}
