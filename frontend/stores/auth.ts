import { defineStore } from "pinia";
import type { CurrentUser, Permission, Role } from "~/types/api";

const MATRIX: Record<Role, Permission[]> = {
  VIEWER: ["indicators:read", "indicators:export"],
  ANALYST: ["indicators:read", "indicators:export", "import:run", "import:read"],
  ADMIN: [
    "indicators:read", "indicators:export", "indicators:edit", "indicators:publish",
    "import:run", "import:read", "users:manage", "audit:read", "settings:manage",
  ],
};

export const useAuthStore = defineStore("auth", () => {
  const token = useCookie<string | null>("central_access_token", { sameSite: "lax" });
  const user = ref<CurrentUser | null>(null);
  const loading = ref(false);

  const authenticated = computed(() => Boolean(token.value && user.value));
  const isAdmin = computed(() => user.value?.role === "ADMIN");
  const can = (permission: Permission) => Boolean(user.value && MATRIX[user.value.role].includes(permission));

  async function loadUser(): Promise<boolean> {
    if (!token.value) {
      user.value = null;
      return false;
    }
    loading.value = true;
    try {
      user.value = await useApi().get<CurrentUser>("/auth/me");
      return true;
    } catch {
      token.value = null;
      user.value = null;
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function loginDev(role: Role): Promise<void> {
    token.value = `dev-${role.toLowerCase()}`;
    if (!(await loadUser())) throw new Error("O backend não aceitou a autenticação de desenvolvimento.");
  }

  function acceptToken(accessToken: string): void {
    token.value = accessToken;
  }

  function clear(): void {
    token.value = null;
    user.value = null;
  }

  return { token, user, loading, authenticated, isAdmin, can, loadUser, loginDev, acceptToken, clear };
});
