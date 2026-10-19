import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Shield, Mail, Database, Lock, User, Globe, FileText } from "lucide-react";

export const metadata = {
  title: "Privacy Policy — RedOps",
  description: "RedOps Privacy Policy — how we collect, use, and protect your information when you use our AI evaluation and red teaming platform.",
  openGraph: {
    title: "Privacy Policy — RedOps",
    description: "How we collect, use, and protect your information.",
    type: "website",
    siteName: "RedOps",
  },
  twitter: {
    card: "summary",
    title: "Privacy Policy — RedOps",
    description: "How we collect, use, and protect your information.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b border-border">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold">RedOps</span>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Home
              </Link>
              <Link href="/login" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Sign In
              </Link>
              <Link href="/register">
                <Button className="gap-2" size="sm">
                  Get Started
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="pt-16">
        <section className="py-20 sm:py-24 lg:py-32">
          <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Privacy Policy</h1>
              <p className="mt-4 mx-auto max-w-2xl text-lg text-muted-foreground">
                Last updated: January 2025. This policy describes how RedOps collects, uses, and protects your information.
              </p>
            </div>

            <div className="space-y-10">
              <PrivacySection
                number="1"
                title="Information We Collect"
                icon={<User className="h-6 w-6" />}
                items={[
                  "We collect information you provide directly when you create an account, configure evaluations, or interact with the platform:",
                  "• Account information: Email address, display name, hashed password, and authentication tokens.",
                  "• Organization & project data: Organization names, project descriptions, evaluation configurations, and run results.",
                  "• Evaluation data: Prompts, model responses, metric scores, costs, latency measurements, and traces.",
                  "• Red team data: Attack definitions, campaign configurations, attack prompts, target responses, and effectiveness judgments.",
                  "• Usage metadata: IP address (for rate limiting), user agent, timestamps, and feature usage.",
                ]}
              />
              
              <PrivacySection
                number="2"
                title="How We Use Your Information"
                icon={<Lock className="h-6 w-6" />}
                items={[
                  "We use collected information to:",
                  "• Provide and operate the RedOps platform (authentication, authorization, evaluation execution).",
                  "• Execute and manage evaluation runs, red team campaigns, and agent evaluations.",
                  "• Calculate and display metrics, costs, latency, and analytics.",
                  "• Enforce organization/project boundaries and access control.",
                  "• Send operational notifications (run completion, failures, security alerts).",
                  "• Improve platform reliability through error tracking and performance monitoring.",
                  "• Comply with legal obligations and enforce our Terms of Service.",
                ]}
              />
              
              <PrivacySection
                number="3"
                title="Data Storage & Retention"
                icon={<Database className="h-6 w-6" />}
                items={[
                  "Your data is stored in PostgreSQL databases hosted on infrastructure you control (self-hosted deployment) or on infrastructure we operate on your behalf (managed deployment).",
                  "Retention periods:",
                  "• Account data: Retained while your account is active. Deleted within 30 days of account deletion.",
                  "• Evaluation runs & results: Retained indefinitely unless you delete them. You can delete runs at any time.",
                  "• Red team campaigns: Retained indefinitely unless you delete them.",
                  "• Audit logs: Retained for 1 year for security and compliance purposes.",
                  "• Rate limit / audit metadata: Retained for 90 days.",
                ]}
              />
              
              <PrivacySection
                number="4"
                title="Third-Party Providers & Data Sharing"
                icon={<Globe className="h-6 w-6" />}
                items={[
                  "RedOps integrates with third-party AI providers to execute evaluations. When you run an evaluation:",
                  "• OpenAI: Prompts and responses sent to OpenAI API. Subject to OpenAI Privacy Policy.",
                  "• Anthropic: Prompts and responses sent to Anthropic API. Subject to Anthropic Privacy Policy.",
                  "• Groq: Prompts and responses sent to Groq API. Subject to Groq Privacy Policy.",
                  "We do not sell your data. We do not use your data to train our own models. Provider API keys are stored encrypted and only used to proxy your evaluation requests.",
                ]}
              />
              
              <PrivacySection
                number="5"
                title="Authentication & Security"
                icon={<Shield className="h-6 w-6" />}
                items={[
                  "We implement industry-standard security practices:",
                  "• Passwords: Hashed with bcrypt (cost factor 12). Never stored in plaintext.",
                  "• Tokens: JWT access tokens (1 hour TTL) with rotating refresh tokens (30 days). Refresh tokens are hashed (SHA-256) before storage.",
                  "• Transport: TLS 1.2+ enforced in production. Secure, HttpOnly, SameSite=Lax cookies not used — we use Bearer tokens in Authorization headers.",
                  "• Rate limiting: Auth endpoints limited to 30 requests/minute per IP.",
                  "• Audit logging: Security-relevant actions (login, password change, org changes) are logged.",
                ]}
              />
              
              <PrivacySection
                number="6"
                title="Your Rights & Choices"
                icon={<Lock className="h-6 w-6" />}
                items={[
                  "You can exercise the following rights through the platform or by contacting us:",
                  "• Access: View your account data, evaluations, and runs in the dashboard.",
                  "• Rectification: Update your display name, email, or password in Settings.",
                  "• Deletion: Delete individual runs, evaluations, or your entire account (Settings → Danger Zone).",
                  "• Portability: Export evaluation results and analytics as JSON/CSV.",
                  "• Withdraw consent: Disable or delete your account at any time.",
                ]}
              />
              
              <PrivacySection
                number="7"
                title="Cookies & Local Storage"
                icon={<Lock className="h-6 w-6" />}
                items={[
                  "RedOps uses browser storage for authentication only:",
                  "• localStorage: Access token, refresh token, and user object for session persistence.",
                  "• No cookies are set by the application for authentication or tracking.",
                  "• No analytics/tracking cookies are used.",
                  "• No third-party cookies are set.",
                  "You can clear your session at any time by logging out, which removes all localStorage items.",
                ]}
              />
              
              <PrivacySection
                number="8"
                title="Children's Privacy"
                icon={<User className="h-6 w-6" />}
                items={[
                  "RedOps is not directed at individuals under 18. We do not knowingly collect personal information from children. If you believe a child has provided us with personal information, please contact us to have it deleted.",
                ]}
              />
              
              <PrivacySection
                number="9"
                title="Changes to This Policy"
                icon={<FileText className="h-6 w-6" />}
                items={[
                  "We may update this Privacy Policy from time to time. Material changes will be communicated via email (if you have a verified email) and/or a prominent notice in the platform. The \"Last updated\" date at the top of this page will be revised.",
                ]}
              />
              
              <PrivacySection
                number="10"
                title="Contact"
                icon={<Mail className="h-6 w-6" />}
                items={[
                  "Questions about this Privacy Policy or our data practices? Contact the RedOps project maintainers via the GitHub repository: github.com/ANUBprad/redops",
                ]}
              />
            </div>

            <div className="mt-12 pt-8 border-t border-border">
              <Link href="/terms" className="text-primary hover:underline">
                Read our Terms of Service →
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

interface PrivacySectionProps {
  number: string;
  title: string;
  icon: React.ReactNode;
  items: string[];
}

function PrivacySection({ number, title, icon, items }: PrivacySectionProps) {
  return (
    <section>
      <div className="flex gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-lg shrink-0">
          {number}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-3">
            <div className="text-primary">{icon}</div>
            <h2 className="text-xl font-semibold">{title}</h2>
          </div>
          <div className="ml-10 space-y-2 text-muted-foreground text-sm">
            {items.map((item, i) => (
              <p key={i} className="leading-relaxed">{item}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}