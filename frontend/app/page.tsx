import { redirect } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";

export default function HomePage() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading...</div>;
  }

  if (!user) {
    redirect("/login");
  }

  redirect("/dashboard");
}
