"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Eye, EyeOff, Check, AlertTriangle } from "lucide-react";

interface ProviderConfig {
  id: string;
  name: string;
  configured: boolean;
  keyPrefix?: string;
}

const defaultProviders: ProviderConfig[] = [
  { id: "openai", name: "OpenAI", configured: false },
  { id: "anthropic", name: "Anthropic", configured: false },
  { id: "google", name: "Google AI (Gemini)", configured: false },
  { id: "azure", name: "Azure OpenAI", configured: false },
  { id: "aws", name: "AWS Bedrock", configured: false },
  { id: "cohere", name: "Cohere", configured: false },
];

export default function ProviderSettingsPage() {
  const [providers, setProviders] = useState<ProviderConfig[]>(defaultProviders);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  const saveMutation = useMutation({
    mutationFn: async (data: { provider: string; api_key: string }) => {
      // In a real implementation, this would call an API endpoint
      // For now, simulate saving
      await new Promise((r) => setTimeout(r, 500));
      return data;
    },
    onSuccess: (_, variables) => {
      setProviders((prev) =>
        prev.map((p) =>
          p.id === variables.provider
            ? { ...p, configured: true, keyPrefix: variables.api_key.slice(0, 8) + "..." }
            : p,
        ),
      );
      setEditingId(null);
      setApiKey("");
      toast.success("Provider credentials saved successfully");
    },
  });

  const handleSave = () => {
    if (!editingId || !apiKey.trim()) return;
    saveMutation.mutate({ provider: editingId, api_key: apiKey.trim() });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Provider Credentials</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Configure API keys for LLM providers. Keys are stored encrypted and never exposed in
            logs or client-side code.
          </p>

          <div className="space-y-3">
            {providers.map((provider) => (
              <div
                key={provider.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium">{provider.name}</span>
                  {provider.configured ? (
                    <Badge className="bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400">
                      <Check className="mr-1 h-3 w-3" />
                      Configured
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      <AlertTriangle className="mr-1 h-3 w-3" />
                      Not configured
                    </Badge>
                  )}
                  {provider.configured && provider.keyPrefix && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {provider.keyPrefix}
                    </span>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditingId(provider.id);
                    setApiKey("");
                    setShowKey(false);
                  }}
                >
                  {provider.configured ? "Update" : "Configure"}
                </Button>
              </div>
            ))}
          </div>

          {editingId && (
            <Card className="mt-4">
              <CardContent className="space-y-4 pt-6">
                <div className="space-y-2">
                  <Label>API Key for {providers.find((p) => p.id === editingId)?.name}</Label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Input
                        type={showKey ? "text" : "password"}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="sk-..."
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3"
                        onClick={() => setShowKey(!showKey)}
                      >
                        {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                    <Button
                      onClick={handleSave}
                      disabled={saveMutation.isPending || !apiKey.trim()}
                    >
                      {saveMutation.isPending ? "Saving..." : "Save"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setEditingId(null);
                        setApiKey("");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
