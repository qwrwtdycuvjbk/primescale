import { createClient } from "@/lib/supabase/server";
import { getServiceClient } from "@/lib/supabase/service";

/**
 * Admin data reads prefer the service role key when configured.
 * Otherwise use the signed-in admin session (RLS policies via is_admin()).
 */
export async function getAdminClient() {
  const service = getServiceClient();
  if (service) return service;
  return createClient();
}

export function hasServiceRoleKey() {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL &&
      process.env.SUPABASE_SERVICE_ROLE_KEY,
  );
}
