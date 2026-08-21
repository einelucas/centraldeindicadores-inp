import { resolve, sep } from "node:path";

function posixResolve(...segments: string[]): string {
  return resolve(...segments).split(sep).join("/");
}

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@pinia/nuxt", "@nuxtjs/tailwindcss", "@nuxt/eslint"],
  components: [{ path: "~/components", pathPrefix: false }],
  css: [resolve(__dirname, "../src/app/globals.css"), "~/assets/css/vue.css"],
  dir: {
    public: resolve(__dirname, "../public"),
  },
  alias: {
    "@": posixResolve(__dirname, "../src"),
  },
  vite: {
    server: {
      fs: {
        allow: [posixResolve(__dirname, "..")],
      },
    },
  },
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1",
      oidcIssuer: process.env.NUXT_PUBLIC_OIDC_ISSUER || "",
      oidcClientId: process.env.NUXT_PUBLIC_OIDC_CLIENT_ID || "",
      oidcRedirectUri: process.env.NUXT_PUBLIC_OIDC_REDIRECT_URI || "http://localhost:3000/auth/callback",
      oidcPostLogoutRedirectUri:
        process.env.NUXT_PUBLIC_OIDC_POST_LOGOUT_REDIRECT_URI || "http://localhost:3000/login",
      devAuthEnabled: process.env.NUXT_PUBLIC_DEV_AUTH_ENABLED !== "false",
      importBatchSize: Number(process.env.NUXT_PUBLIC_IMPORT_BATCH_SIZE || 500),
    },
  },
  typescript: {
    strict: true,
    typeCheck: true,
  },
  app: {
    head: {
      htmlAttrs: { lang: "pt-BR" },
      title: "Central de Indicadores",
      meta: [
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { name: "theme-color", content: "#304f7e" },
      ],
      link: [
        { rel: "icon", type: "image/png", href: "/brand/favicon.png" },
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "anonymous" },
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
        },
      ],
    },
  },
});
