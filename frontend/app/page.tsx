"use client";

import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { useEffect, useState } from "react";
import {
  BarChart3,
  Bot,
  CheckCircle,
  Code,
  Github,
  Lock,
  PlayCircle,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LandingPage() {
  const { isLoading } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || isLoading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="bg-background min-h-screen">
      <nav className="border-border bg-background/95 supports-[backdrop-filter]:bg-background/60 fixed top-0 right-0 left-0 z-50 border-b backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-8">
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold">RedOps</span>
                <span className="text-muted-foreground hidden text-xs sm:inline">
                  AI Evaluation Platform
                </span>
              </div>
              <div className="hidden items-center gap-6 text-sm font-medium md:flex">
                <a
                  href="#platform"
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  Platform
                </a>
                <a
                  href="#architecture"
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  Architecture
                </a>
                <a
                  href="https://github.com/ANUBprad/redops"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                >
                  <Github className="h-4 w-4" />
                  GitHub
                </a>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Link
                href="/login"
                className="text-muted-foreground hover:text-foreground text-sm font-medium transition-colors"
              >
                Sign In
              </Link>
              <Link href="/register">
                <Button className="gap-2">
                  <Sparkles className="h-4 w-4" />
                  Get Started
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="pt-16">
        <section className="relative overflow-hidden py-20 sm:py-32 lg:py-40 xl:py-48">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center">
              <div className="bg-primary/10 text-primary mb-6 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium">
                <Sparkles className="h-4 w-4" />
                <span>Production-grade AI Evaluation & Red Teaming</span>
              </div>
              <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
                Evaluate AI systems <span className="text-primary">before your users do</span>
              </h1>
              <p className="text-muted-foreground mx-auto mt-6 max-w-2xl text-lg">
                RedOps combines evaluation, adversarial testing, execution orchestration,
                provenance, and observability into a single platform. Run evaluations you can trust,
                red-team campaigns that adapt, and observability that makes failures explainable.
              </p>
              <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
                <Link href="/register">
                  <Button size="lg" className="w-full gap-2 sm:w-auto">
                    <Sparkles className="h-5 w-5" />
                    Start Evaluating
                  </Button>
                </Link>
                <Link href="/login">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    Sign In
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section id="platform" className="py-20 sm:py-24 lg:py-32">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-16 text-center">
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Core Capabilities</h2>
              <p className="text-muted-foreground mx-auto mt-4 max-w-2xl">
                Verified capabilities built for production AI engineering teams
              </p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <CapabilityCard
                icon={<Target className="h-6 w-6" />}
                title="Evaluation Engine"
                description="Dataset-driven LLM evaluation with pluggable metrics, LLM-as-a-Judge, and full cost/token provenance"
                features={[
                  "25+ built-in metrics",
                  "LLM-as-a-Judge with structured parsing",
                  "Provider-neutral execution (OpenAI, Anthropic, Groq)",
                  "Cost & token provenance",
                ]}
              />
              <CapabilityCard
                icon={<Shield className="h-6 w-6" />}
                title="Red Teaming"
                description="Adaptive adversarial campaigns with mutation strategies, semantic judging, and durable round persistence"
                features={[
                  "Generate→Execute→Evaluate→Mutate loops",
                  "Template-based & LLM-driven mutations",
                  "Semantic effectiveness judging",
                  "Durable round checkpointing",
                ]}
              />
              <CapabilityCard
                icon={<Bot className="h-6 w-6" />}
                title="Agent Evaluation"
                description="Trajectory-based assessment of tool-calling agents with tool selection correctness and error recovery metrics"
                features={[
                  "Tool selection correctness",
                  "Error recovery evaluation",
                  "Efficiency & completeness metrics",
                  "Provider-agnostic tool calling",
                ]}
              />
              <CapabilityCard
                icon={<TrendingUp className="h-6 w-6" />}
                title="Experiments"
                description="Versioned evaluation configurations for reproducible comparison with regression analysis"
                features={[
                  "Profile & baseline management",
                  "Fingerprint-based compatibility checks",
                  "Metric delta computation",
                  "Statistical tolerance thresholds",
                ]}
              />
              <CapabilityCard
                icon={<BarChart3 className="h-6 w-6" />}
                title="Observability"
                description="Execution traces, replay, metric provenance, and replay-based comparison with cost certainty"
                features={[
                  "Full item-level traces",
                  "Replay & comparison",
                  "Metric provenance & versioning",
                  "Cost certainty tracking",
                ]}
              />
              <CapabilityCard
                icon={<Zap className="h-6 w-6" />}
                title="Execution Integrity"
                description="Temporal orchestration with durable execution, retry/idempotency, provenance, and provider abstraction"
                features={[
                  "Temporal orchestration",
                  "Retry/idempotency semantics",
                  "Circuit breaker & rate limiting",
                  "Provider abstraction layer",
                ]}
              />
            </div>
          </div>
        </section>

        <section id="architecture" className="bg-muted/30 py-20 sm:py-24 lg:py-32">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-16 text-center">
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">How It Works</h2>
              <p className="text-muted-foreground mx-auto mt-4 max-w-2xl">
                From dataset to red-team findings — a unified workflow
              </p>
            </div>

            <div className="relative">
              <div className="bg-border absolute top-0 bottom-0 left-1/2 hidden w-0.5 -translate-x-1/2 lg:block" />
              <div className="space-y-12">
                <WorkflowStep
                  number="01"
                  title="Dataset / Inputs"
                  description="Define evaluation datasets with prompts, references, and context. Support for single items, datasets, and templated prompts."
                  icon={<FileText className="h-8 w-8" />}
                />
                <WorkflowStep
                  number="02"
                  title="Model / Provider"
                  description="Select provider (OpenAI, Anthropic, Groq) and model. Configure temperature, max tokens, and system prompts."
                  icon={<Bot className="h-8 w-8" />}
                />
                <WorkflowStep
                  number="03"
                  title="Evaluation Runtime"
                  description="Temporal orchestrates durable execution with retries, circuit breakers, rate limiting, and provider timeouts."
                  icon={<PlayCircle className="h-8 w-8" />}
                />
                <WorkflowStep
                  number="04"
                  title="Metrics / Judges"
                  description="25+ built-in metrics plus LLM-as-a-Judge semantic evaluation. All results persisted with full provenance."
                  icon={<BarChart3 className="h-8 w-8" />}
                />
                <WorkflowStep
                  number="05"
                  title="Results / Analytics"
                  description="Aggregated metrics, cost tracking, latency analysis, safety trends, and leaderboard comparisons."
                  icon={<TrendingUp className="h-8 w-8" />}
                />
                <WorkflowStep
                  number="06"
                  title="Red-Team / Reliability"
                  description="Adaptive campaigns with mutation strategies, semantic judging, and durable round persistence for adversarial testing."
                  icon={<Shield className="h-8 w-8" />}
                />
              </div>
            </div>
          </div>
        </section>

        <section className="py-20 sm:py-24 lg:py-32">
          <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Trust & Execution Integrity
            </h2>
            <p className="text-muted-foreground mx-auto mt-4 max-w-2xl">
              Evidence-backed engineering qualities for production AI systems
            </p>
            <div className="mt-16 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              <TrustCard
                icon={<CheckCircle className="h-6 w-6" />}
                title="Temporal Orchestration"
                description="Durable workflow execution with automatic checkpointing, retries, and exactly-once semantics"
              />
              <TrustCard
                icon={<Code className="h-6 w-6" />}
                title="Idempotent Execution"
                description="Provider calls recorded before metric evaluation; retries reuse durable records, never re-call providers"
              />
              <TrustCard
                icon={<Lock className="h-6 w-6" />}
                title="Provenance & Audit"
                description="Environment capture (git commit, Python version, requirements hash), metric versioning, threshold evaluations"
              />
              <TrustCard
                icon={<Zap className="h-6 w-6" />}
                title="Provider Abstraction"
                description="Unified interface across OpenAI, Anthropic, Groq with automatic registration via API keys"
              />
              <TrustCard
                icon={<Shield className="h-6 w-6" />}
                title="Tenant Isolation"
                description="Organization/project ownership enforced on all mutating operations with cross-tenant denial"
              />
              <TrustCard
                icon={<PlayCircle className="h-6 w-6" />}
                title="Deterministic Contracts"
                description="Fingerprint captures config+code+environment; regression analysis validates compatibility before comparison"
              />
            </div>
          </div>
        </section>

        <section className="bg-muted/30 py-20 sm:py-24 lg:py-32">
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ready to Start Evaluating?
            </h2>
            <p className="text-muted-foreground mt-4">
              Join teams evaluating AI systems before their users do.
            </p>
            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Link href="/register">
                <Button size="lg" className="w-full gap-2 sm:w-auto">
                  <Sparkles className="h-5 w-5" />
                  Create Account
                </Button>
              </Link>
              <Link href="/login">
                <Button size="lg" variant="outline" className="w-full sm:w-auto">
                  Sign In
                </Button>
              </Link>
            </div>
          </div>
        </section>

        <footer className="bg-background border-t py-12">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center gap-6 md:flex-row md:justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold">RedOps</span>
              </div>
              <div className="flex flex-col items-center gap-4 gap-6 md:flex-row md:items-center md:justify-between">
                <div className="text-muted-foreground flex items-center gap-6 text-sm">
                  <Link href="/privacy" className="hover:text-foreground transition-colors">
                    Privacy
                  </Link>
                  <Link href="/terms" className="hover:text-foreground transition-colors">
                    Terms
                  </Link>
                </div>
                <div className="text-muted-foreground flex items-center gap-6 text-sm">
                  <a
                    href="https://github.com/ANUBprad/redops"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-foreground flex items-center gap-1 transition-colors"
                  >
                    <Github className="h-4 w-4" />
                    GitHub
                  </a>
                  <span>Apache 2.0 License</span>
                </div>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

interface CapabilityCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  features: string[];
}

function CapabilityCard({ icon, title, description, features }: CapabilityCardProps) {
  return (
    <Card className="border-border bg-card hover:border-primary/50 transition-colors">
      <CardHeader>
        <div className="text-primary">{icon}</div>
        <CardTitle className="text-lg">{title}</CardTitle>
        <CardDescription className="text-sm">{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="text-muted-foreground space-y-2 text-sm">
          {features.map((feature, i) => (
            <li key={i} className="flex items-center gap-2">
              <CheckCircle className="text-primary h-4 w-4" />
              {feature}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

interface WorkflowStepProps {
  number: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}

function WorkflowStep({ number, title, description, icon }: WorkflowStepProps) {
  return (
    <div className="relative flex gap-6 lg:gap-8">
      <div className="bg-primary/10 text-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg font-bold">
        {number}
      </div>
      <div className="flex-1 pt-1">
        <div className="flex items-center gap-3">
          <div className="text-primary">{icon}</div>
          <h3 className="text-xl font-semibold">{title}</h3>
        </div>
        <p className="text-muted-foreground mt-2 ml-11">{description}</p>
      </div>
    </div>
  );
}

interface TrustCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function TrustCard({ icon, title, description }: TrustCardProps) {
  return (
    <Card className="border-border bg-card hover:border-primary/50 transition-colors">
      <CardContent className="pt-6">
        <div className="text-primary mb-3">{icon}</div>
        <h3 className="mb-2 font-semibold">{title}</h3>
        <p className="text-muted-foreground text-sm">{description}</p>
      </CardContent>
    </Card>
  );
}
