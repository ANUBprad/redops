import Link from "next/link";
import { Fragment, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  Shield,
  Mail,
  Database,
  Lock,
  User,
  Globe,
  FileText,
  Clock,
  AlertCircle,
} from "lucide-react";

export const metadata = {
  title: "Terms of Service — RedOps",
  description:
    "RedOps Terms of Service — governing the use of our AI evaluation, red teaming, and observability platform.",
  openGraph: {
    title: "Terms of Service — RedOps",
    description:
      "Terms of Service governing the use of our AI evaluation and red teaming platform.",
    type: "website",
    siteName: "RedOps",
  },
  twitter: {
    card: "summary",
    title: "Terms of Service — RedOps",
    description:
      "Terms of Service governing the use of our AI evaluation and red teaming platform.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function TermsPage() {
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
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Terms of Service</h1>
              <p className="text-muted-foreground mx-auto mt-4 max-w-2xl text-lg">
                Last updated: January 2025. By accessing or using RedOps, you agree to these terms.
              </p>
            </div>

            <div className="space-y-10">
              <TermsSection
                number="1"
                title="Acceptance of Terms"
                icon={<FileText className="h-6 w-6" />}
                content={[
                  'By creating an account, accessing, or using the RedOps platform ("RedOps", "the Platform", "we", "us", or "our"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, do not use the Platform.',
                  'These Terms apply to all users, including individual users, organization administrators, and any person accessing the Platform on behalf of an organization ("You", "Your").',
                ]}
              />

              <TermsSection
                number="2"
                title="Eligibility &amp; Accounts"
                icon={<User className="h-6 w-6" />}
                content={[
                  "You must be at least 18 years old to use the Platform. By registering, you represent and warrant that you are at least 18 years old and have the legal capacity to enter into these Terms.",
                  "You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account. You agree to notify us immediately of any unauthorized access.",
                  "We reserve the right to refuse service, terminate accounts, or remove content at our discretion, including for violations of these Terms.",
                ]}
              />

              <TermsSection
                number="3"
                title="Organizations &amp; Projects"
                icon={<Shield className="h-6 w-6" />}
                content={[
                  "RedOps supports multi-tenancy through Organizations. Each Organization may have multiple Projects. You may belong to multiple Organizations.",
                  "Organization administrators control membership, roles, and Project access. You are responsible for managing Your Organization's membership and ensuring compliance with these Terms by all members.",
                  "Projects are scoped to an Organization. Data and evaluations within a Project are accessible only to members of that Organization with appropriate roles.",
                ]}
              />

              <TermsSection
                number="4"
                title="Evaluation &amp; Red Team Services"
                icon={<Shield className="h-6 w-6" />}
                content={[
                  "The Platform provides evaluation, red teaming, and observability capabilities for AI systems. You are responsible for:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="eval">
                    <li>Providing accurate inputs, datasets, and configurations.</li>
                    <li>
                      Ensuring you have the right to use any data, prompts, or models submitted.
                    </li>
                    <li>
                      Complying with third-party provider terms when using integrated AI providers
                      (OpenAI, Anthropic, Groq).
                    </li>
                    <li>Reviewing and validating evaluation results before relying on them.</li>
                  </ul>,
                  "The Platform executes evaluations asynchronously via Temporal workflows. Results are provided as-is without warranty of accuracy, completeness, or fitness for a particular purpose.",
                ]}
              />

              <TermsSection
                number="5"
                title="Third-Party AI Providers"
                icon={<Globe className="h-6 w-6" />}
                content={[
                  "RedOps integrates with third-party AI providers (OpenAI, Anthropic, Groq) to execute evaluations. When you use these integrations:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="providers">
                    <li>You must provide your own API keys for each provider you wish to use.</li>
                    <li>
                      Your use of each provider is subject to that provider&apos;s terms of service
                      and privacy policy.
                    </li>
                    <li>
                      We do not store your provider API keys in plaintext. Keys are encrypted at
                      rest.
                    </li>
                    <li>
                      We are not responsible for provider availability, rate limits, pricing
                      changes, or service disruptions.
                    </li>
                    <li>
                      Costs incurred with providers are your responsibility. RedOps provides cost
                      estimates based on published pricing.
                    </li>
                  </ul>,
                ]}
              />

              <TermsSection
                number="6"
                title="Data &amp; Intellectual Property"
                icon={<Database className="h-6 w-6" />}
                content={[
                  <>
                    <strong>Your Data:</strong> You retain all rights to data you submit to the
                    Platform (prompts, datasets, evaluation results, red team campaigns). We do not
                    claim ownership of Your Data.
                  </>,
                  <>
                    <strong>Our Rights:</strong> We retain all rights to the Platform, including its
                    code, design, algorithms, metrics, and aggregated anonymized analytics.
                  </>,
                  <>
                    <strong>License to Us:</strong> You grant us a non-exclusive, worldwide,
                    royalty-free license to use, store, process, and display Your Data solely to
                    provide the Platform services.
                  </>,
                  <>
                    <strong>Anonymized Analytics:</strong> We may use anonymized, aggregated
                    evaluation data to improve the Platform, publish benchmarks, or publish
                    research. No identifiable information is included.
                  </>,
                ]}
              />

              <TermsSection
                number="7"
                title="Acceptable Use"
                icon={<AlertCircle className="h-6 w-6" />}
                content={[
                  "You agree not to use the Platform to:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="acceptable-use">
                    <li>Violate any applicable law or regulation.</li>
                    <li>Infringe intellectual property rights.</li>
                    <li>Generate harmful, illegal, or abusive content.</li>
                    <li>
                      Attempt to reverse engineer, decompile, or extract source code from the
                      Platform.
                    </li>
                    <li>
                      Interfere with platform security, rate limits, or other users&apos; access.
                    </li>
                    <li>
                      Use the Platform for cryptocurrency mining, spam, or distributed
                      denial-of-service attacks.
                    </li>
                    <li>Share your account credentials or API keys with unauthorized parties.</li>
                  </ul>,
                  "We may suspend or terminate Your access for violations.",
                ]}
              />

              <TermsSection
                number="8"
                title="Disclaimer of Warranties"
                icon={<AlertCircle className="h-6 w-6" />}
                content={[
                  'THE PLATFORM IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO:',
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="warranties">
                    <li>MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE</li>
                    <li>NON-INFRINGEMENT</li>
                    <li>ACCURACY, COMPLETENESS, OR RELIABILITY OF EVALUATION RESULTS</li>
                    <li>UNINTERRUPTED OR ERROR-FREE OPERATION</li>
                    <li>SECURITY FROM UNAUTHORIZED ACCESS</li>
                  </ul>,
                  "EVALUATION RESULTS ARE PROVIDED FOR INFORMATIONAL PURPOSES ONLY AND SHOULD NOT BE RELIED UPON FOR CRITICAL DECISIONS WITHOUT INDEPENDENT VERIFICATION.",
                ]}
              />

              <TermsSection
                number="9"
                title="Limitation of Liability"
                icon={<AlertCircle className="h-6 w-6" />}
                content={[
                  "TO THE MAXIMUM EXTENT PERMITTED BY LAW, IN NO EVENT SHALL REDOPS, ITS CONTRIBUTORS, OR ITS LICENSORS BE LIABLE FOR:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="liability">
                    <li>INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES</li>
                    <li>LOSS OF PROFITS, REVENUE, DATA, OR GOODWILL</li>
                    <li>SERVICE INTERRUPTION OR DATA LOSS</li>
                    <li>COSTS OF PROCUREMENT OF SUBSTITUTE SERVICES</li>
                  </ul>,
                  "OUR TOTAL AGGREGATE LIABILITY SHALL NOT EXCEED THE GREATER OF: (A) THE AMOUNT YOU PAID FOR THE SERVICE IN THE 12 MONTHS PRECEDING THE CLAIM, OR (B) $100 USD.",
                ]}
              />

              <TermsSection
                number="10"
                title="Indemnification"
                icon={<Shield className="h-6 w-6" />}
                content={[
                  "You agree to indemnify, defend, and hold harmless RedOps, its contributors, and licensors from and against any claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising from:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="indemnity">
                    <li>Your use of the Platform in violation of these Terms.</li>
                    <li>Your Data or any content you submit.</li>
                    <li>
                      Your violation of any third-party rights (including intellectual property).
                    </li>
                    <li>Your breach of these Terms.</li>
                  </ul>,
                ]}
              />

              <TermsSection
                number="11"
                title="Termination"
                icon={<Lock className="h-6 w-6" />}
                content={[
                  "You may terminate your account at any time by deleting it in Settings. We may suspend or terminate Your access immediately, with or without notice, for:",
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="termination">
                    <li>Breach of these Terms.</li>
                    <li>Security concerns or suspected unauthorized access.</li>
                    <li>Extended inactivity (12+ months).</li>
                    <li>Legal or regulatory requirements.</li>
                  </ul>,
                  "Upon termination, Your access ceases immediately. We will delete Your Data within 30 days unless retention is required by law. Provisions that should survive termination (IP rights, disclaimers, limitations of liability, indemnification) will survive.",
                ]}
              />

              <TermsSection
                number="12"
                title="Governing Law &amp; Disputes"
                icon={<FileText className="h-6 w-6" />}
                content={[
                  "These Terms are governed by the laws of the State of Delaware, USA, without regard to conflict of laws principles. Any disputes arising from these Terms will be resolved in the state or federal courts located in Delaware, and You consent to the exclusive jurisdiction of such courts.",
                ]}
              />

              <TermsSection
                number="13"
                title="Changes to Terms"
                icon={<Clock className="h-6 w-6" />}
                content={[
                  "We may modify these Terms at any time. Material changes will be communicated via email (if you have a verified email) and/or a prominent notice in the Platform at least 30 days before they take effect. Your continued use after the effective date constitutes acceptance of the revised Terms.",
                ]}
              />

              <TermsSection
                number="14"
                title="General Provisions"
                icon={<FileText className="h-6 w-6" />}
                content={[
                  <ul className="mt-2 ml-4 list-inside list-disc space-y-1" key="general">
                    <li>
                      <strong>Entire Agreement:</strong> These Terms, together with the Privacy
                      Policy, constitute the entire agreement between You and RedOps.
                    </li>
                    <li>
                      <strong>Severability:</strong> If any provision is found unenforceable, the
                      remaining provisions remain in effect.
                    </li>
                    <li>
                      <strong>No Waiver:</strong> Our failure to enforce any right does not waive
                      that right.
                    </li>
                    <li>
                      <strong>Assignment:</strong> You may not assign these Terms without our
                      consent. We may assign them freely.
                    </li>
                    <li>
                      <strong>Force Majeure:</strong> We are not liable for delays caused by events
                      beyond our reasonable control.
                    </li>
                  </ul>,
                ]}
              />

              <TermsSection
                number="15"
                title="Contact"
                icon={<Mail className="h-6 w-6" />}
                content={[
                  <>
                    Questions about these Terms? Contact the RedOps project maintainers via the
                    GitHub repository:{" "}
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
              <Link href="/privacy" className="text-primary hover:underline">
                Read our Privacy Policy →
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

interface TermsSectionProps {
  number: string;
  title: string;
  icon: ReactNode;
  content: (string | ReactNode)[];
}

function TermsSection({ number, title, icon, content }: TermsSectionProps) {
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
