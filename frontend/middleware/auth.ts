export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuthStore();
  if (!auth.user && !(await auth.loadUser())) return navigateTo("/login");
});
