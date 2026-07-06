import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { isAdminEmail } from "@/lib/ensure-profile";
import { getServiceClient } from "@/lib/supabase/service";

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  if (isAdminEmail(user.email)) {
    const service = getServiceClient();
    if (service) {
      await service.from("profiles").upsert(
        {
          id: user.id,
          role: "admin",
          full_name:
            user.user_metadata?.full_name ||
            user.user_metadata?.name ||
            user.email?.split("@")[0] ||
            "Admin",
          email: user.email ?? "",
        },
        { onConflict: "id" },
      );
    }

    return NextResponse.json({ redirect: "/admin/handoffs" });
  }

  return NextResponse.json({ redirect: "/auth/redirect" });
}
