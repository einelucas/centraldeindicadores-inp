export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuthStore();
  if (!auth.user && !(await auth.loadUser())) return navigateTo("/login");
  if (auth.user?.role !== "ADMIN") return navigateTo("/dashboard/scorecard");
});
