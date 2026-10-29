import { redirect } from "next/navigation";

// La landing est une page statique autonome (SEO, RTL, formulaire waitlist
// direct vers Supabase) : "/" y redirige simplement.
export default function Home() {
  redirect("/landing.html");
}
