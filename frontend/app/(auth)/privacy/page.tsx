import Link from "next/link";
import { Fragment, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Shield, Mail, Database, Lock, User, Globe, FileText } from "lucide-react";

export const metadata = {
  title: "Privacy Policy — RedOps",
  description:
    "RedOps Privacy Policy — how we collect, use, and protect your information when you use our AI evaluation and red teaming platform.",
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
    <div className="bg-background min-h-screen">
      <nav className="border-border bg-background/95 supports-[backdrop-filter]:bg-background/60 fixed top-0 right-0 left-0 z-50 border-b backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold">RedOps</span>
            </div>
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors"
              >
                Home
              </Link>
              <Link
                href="/login"
                className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors"
              >
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
            <div className="mb-12 text-center">
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Privacy Policy</h1>
              <p className="text-muted-foreground mx-auto mt-4 max-w-2xl text-lg">
                Last updated: January 2025. This policy describes how RedOps collects, uses, and
                protects your information.
              </p>
            </div>

            <div className="space-y-10">
              <PrivacySection
                number="1"
                title="Information We Collect"
                icon={<User className="h-6 w-6" />}
                content={[
                  "We collect information you provide directly when you create an account, configure evaluations, or interact with the platform:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="collect">
                    <li>
                      <strong>Account information:</strong> Email address, display name, hashed
                      password, and authentication tokens.
                    </li>
                    <li>
                      <strong>Organization &amp; project data:</strong> Organization names, project
                      descriptions, evaluation configurations, and run results.
                    </li>
                    <li>
                      <strong>Evaluation data:</strong> Prompts, model responses, metric scores,
                      costs, latency measurements, and traces.
                    </li>
                    <li>
                      <strong>Red team data:</strong> Attack definitions, campaign configurations,
                      attack prompts, target responses, and effectiveness judgments.
                    </li>
                    <li>
                      <strong>Usage metadata:</strong> IP address (for rate limiting), user agent,
                      timestamps, and feature usage.
                    </li>
                  </ul>,
                ]}
              />

              <PrivacySection
                number="2"
                title="How We Use Your Information"
                icon={<Lock className="h-6 w-6" />}
                content={[
                  "We use collected information to:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="use">
                    <li>
                      Provide and operate the RedOps platform (authentication, authorization,
                      evaluation execution).
                    </li>
                    <li>
                      Execute and manage evaluation runs, red team campaigns, and agent evaluations.
                    </li>
                    <li>Calculate and display metrics, costs, latency, and analytics.</li>
                    <li>Enforce organization/project boundaries and access control.</li>
                    <li>
                      Send operational notifications (run completion, failures, security alerts).
                    </li>
                    <li>
                      Improve platform reliability through error tracking and performance
                      monitoring.
                    </li>
                    <li>Comply with legal obligations and enforce our Terms of Service.</li>
                  </ul>,
                ]}
              />

              <PrivacySection
                number="3"
                title="Data Storage &amp; Retention"
                icon={<Database className="h-6 w-6" />}
                content={[
                  "Your data is stored in PostgreSQL databases hosted on infrastructure you control (self-hosted deployment) or on infrastructure we operate on your behalf (managed deployment).",
                  "Retention periods:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="retention">
                    <li>
                      <strong>Account data:</strong> Retained while your account is active. Deleted
                      within 30 days of account deletion.
                    </li>
                    <li>
                      <strong>Evaluation runs &amp; results:</strong> Retained indefinitely unless
                      you delete them. You can delete runs at any time.
                    </li>
                    <li>
                      <strong>Red team campaigns:</strong> Retained indefinitely unless you delete
                      them.
                    </li>
                    <li>
                      <strong>Audit logs:</strong> Retained for 1 year for security and compliance
                      purposes.
                    </li>
                    <li>
                      <strong>Rate limit / audit metadata:</strong> Retained for 90 days.
                    </li>
                  </ul>,
                ]}
              />

              <PrivacySection
                number="4"
                title="Third-Party Providers &amp; Data Sharing"
                icon={<Globe className="h-6 w-6" />}
                content={[
                  "RedOps integrates with third-party AI providers to execute evaluations. When you run an evaluation:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="third-party">
                    <li>
                      <strong>OpenAI:</strong> Prompts and responses sent to OpenAI API. Subject to{" "}
                      <a
                        href="https://openai.com/policies/privacy-policy"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        OpenAI Privacy Policy
                      </a>
                      .
                    </li>
                    <li>
                      <strong>Anthropic:</strong> Prompts and responses sent to Anthropic API.
                      Subject to{" "}
                      <a
                        href="https://www.anthropic.com/legal/privacy"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Anthropic Privacy Policy
                      </a>
                      .
                    </li>
                    <li>
                      <strong>Groq:</strong> Prompts and responses sent to Groq API. Subject to{" "}
                      <a
                        href="https://groq.com/privacy-policy"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Groq Privacy Policy
                      </a>
                      .
                    </li>
                  </ul>,
                  "We do not sell your data. We do not use your data to train our own models. Provider API keys are stored encrypted and only used to proxy your evaluation requests.",
                ]}
              />

              <PrivacySection
                number="5"
                title="Authentication &amp; Security"
                icon={<Shield className="h-6 w-6" />}
                content={[
                  "We implement industry-standard security practices:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="auth">
                    <li>
                      <strong>Passwords:</strong> Hashed with bcrypt (cost factor 12). Never stored
                      in plaintext.
                    </li>
                    <li>
                      <strong>Tokens:</strong> JWT access tokens (1 hour TTL) with rotating refresh
                      tokens (30 days). Refresh tokens are hashed (SHA-256) before storage.
                    </li>
                    <li>
                      <strong>Transport:</strong> TLS 1.2+ enforced in production. Secure, HttpOnly,
                      SameSite=Lax cookies not used — we use Bearer tokens in Authorization headers.
                    </li>
                    <li>
                      <strong>Rate limiting:</strong> Auth endpoints limited to 30 requests/minute
                      per IP.
                    </li>
                    <li>
                      <strong>Audit logging:</strong> Security-relevant actions (login, password
                      change, org changes) are logged.
                    </li>
                  </ul>,
                ]}
              />

              <PrivacySection
                number="6"
                title="Your Rights &amp; Choices"
                icon={<Lock className="h-6 w-6" />}
                content={[
                  "You can exercise the following rights through the platform or by contacting us:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="rights">
                    <li>
                      <strong>Access:</strong> View your account data, evaluations, and runs in the
                      dashboard.
                    </li>
                    <li>
                      <strong>Rectification:</strong> Update your display name, email, or password
                      in Settings.
                    </li>
                    <li>
                      <strong>Deletion:</strong> Delete individual runs, evaluations, or your entire
                      account (Settings → Danger Zone).
                    </li>
                    <li>
                      <strong>Portability:</strong> Export evaluation results and analytics as
                      JSON/CSV.
                    </li>
                    <li>
                      <strong>Withdraw consent:</strong> Disable or delete your account at any time.
                    </li>
                  </ul>,
                ]}
              />

              <PrivacySection
                number="7"
                title="Cookies &amp; Local Storage"
                icon={<Lock className="h-6 w-6" />}
                content={[
                  "RedOps uses browser storage for authentication only:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="cookies">
                    <li>
                      <strong>localStorage:</strong> Access token, refresh token, and user object
                      for session persistence.
                    </li>
                    <li>
                      <strong>No cookies</strong> are set by the application for authentication or
                      tracking.
                    </li>
                    <li>
                      <strong>No analytics/tracking cookies</strong> are used.
                    </li>
                    <li>
                      <strong>No third-party cookies</strong> are set.
                    </li>
                  </ul>,
                  "You can clear your session at any time by logging out, which removes all localStorage items.",
                ]}
              />

              <PrivacySection
                number="8"
                title="Children's Privacy"
                icon={<User className="h-6 w-6" />}
                content={[
                  "RedOps is not directed at individuals under 18. We do not knowingly collect personal information from children. If you believe a child has provided us with personal information, please contact us to have it deleted.",
                ]}
              />

              <PrivacySection
                number="9"
                title="Changes to This Policy"
                icon={<FileText className="h-6 w-6" />}
                content={[
                  'We may update this Privacy Policy from time to time. Material changes will be communicated via email (if you have a verified email) and/or a prominent notice in the platform. The "Last updated" date at the top of this page will be revised.',
                ]}
              />

              <PrivacySection
                number="10"
                title="Contact"
                icon={<Mail className="h-6 w-6" />}
                content={[
                  <>
                    Questions about this Privacy Policy or our data practices? Contact the RedOps
                    project maintainers via the GitHub repository:{" "}
                    <a
                      href="https://github.com/ANUBprad/redops"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      github.com/ANUBprad/redops
                    </a>
                    .
                  </>,
                ]}
              />
            </div>

            <div className="border-border mt-12 border-t pt-8">
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
  icon: ReactNode;
  content: (string | ReactNode)[];
}

function PrivacySection({ number, title, icon, content }: PrivacySectionProps) {
  return (
    <section>
      <div className="flex gap-4">
        <div className="bg-primary/10 text-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg font-bold">
          {number}
        </div>
        <div className="flex-1">
          <div className="mb-3 flex items-center gap-3">
            <div className="text-primary">{icon}</div>
            <h2 className="text-xl font-semibold">{title}</h2>
          </div>
          <div className="text-muted-foreground ml-10 space-y-3">
            {content.map((item, i) => (
              <Fragment key={i}>{typeof item === "string" ? <p>{item}</p> : item}</Fragment>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
