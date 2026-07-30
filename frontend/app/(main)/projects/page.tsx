import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const projects = [
  { id: "proj-001", name: "Customer Support AI", description: "Evaluations for customer support chatbot", evals: 5, runs: 23 },
  { id: "proj-002", name: "Code Assistant", description: "LLM code generation evaluation suite", evals: 8, runs: 41 },
  { id: "proj-003", name: "Research Assistant", description: "Academic research assistant evaluations", evals: 3, runs: 12 },
  { id: "proj-004", name: "Safety Testing", description: "Red team and safety evaluations", evals: 12, runs: 56 },
];

export default function NewProjectPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Projects</h1>
        <Button asChild>
          <Link href="/projects/new">
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Link>
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search projects..." className="pl-8" />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Link key={project.id} href={`/projects/${project.id}`}>
            <Card className="cursor-pointer transition-shadow hover:shadow-md">
              <CardHeader>
                <CardTitle>{project.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{project.description}</p>
                <div className="mt-4 flex gap-4 text-sm">
                  <span>{project.evals} evaluations</span>
                  <span>{project.runs} runs</span>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
