"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { LoadingState } from "@/components/ui/loading-state";
import { toast } from "sonner";
import { UserPlus, Trash2 } from "lucide-react";
import type { Membership, Invitation, Organization } from "@/types/api";

export default function TeamSettingsPage() {
  const queryClient = useQueryClient();
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");

  const { data: orgs, isLoading: orgsLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.listOrganizations(),
  });

  const organizations = (orgs ?? []) as Organization[];
  const orgId = organizations[0]?.id;

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ["members", orgId],
    queryFn: () => api.listMembers(orgId!),
    enabled: !!orgId,
  });

  const { data: invitations } = useQuery({
    queryKey: ["invitations", orgId],
    queryFn: () => api.listInvitations(orgId!),
    enabled: !!orgId,
  });

  const inviteMutation = useMutation({
    mutationFn: (data: { email: string; role: string }) =>
      api.inviteMember(orgId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", orgId] });
      queryClient.invalidateQueries({ queryKey: ["invitations", orgId] });
      setShowInvite(false);
      setInviteEmail("");
      toast.success("Invitation sent successfully");
    },
    onError: () => {
      toast.error("Failed to send invitation");
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userId: string) => api.removeMember(orgId!, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", orgId] });
      toast.success("Member removed");
    },
  });

  const changeRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.changeMemberRole(orgId!, userId, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", orgId] });
      toast.success("Role updated");
    },
  });

  if (orgsLoading || membersLoading) return <LoadingState />;

  if (!orgId) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No organization found. Create an organization first.
        </CardContent>
      </Card>
    );
  }

  const memberList = (members ?? []) as Membership[];
  const invitationList = (invitations ?? []) as Invitation[];

  const handleInvite = () => {
    if (!inviteEmail.trim()) return;
    inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Team Members</CardTitle>
            <Button size="sm" onClick={() => setShowInvite(!showInvite)}>
              <UserPlus className="mr-1 h-4 w-4" />
              Invite Member
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {showInvite && (
            <div className="rounded-md border p-4 space-y-3">
              <div className="grid grid-cols-[1fr_120px_auto] gap-2 items-end">
                <div className="space-y-2">
                  <Label>Email Address</Label>
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@company.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Role</Label>
                  <Select value={inviteRole} onValueChange={setInviteRole}>
                    <option value="viewer">Viewer</option>
                    <option value="analyst">Analyst</option>
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </Select>
                </div>
                <Button onClick={handleInvite} disabled={inviteMutation.isPending || !inviteEmail.trim()}>
                  {inviteMutation.isPending ? "Sending..." : "Send Invite"}
                </Button>
              </div>
            </div>
          )}

          {memberList.length === 0 ? (
            <p className="text-sm text-muted-foreground">No members found.</p>
          ) : (
            <div className="space-y-2">
              {memberList.map((member) => (
                <div key={member.id} className="flex items-center justify-between rounded-md border p-3">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
                      {member.user_id.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{member.user_id}</p>
                      <p className="text-xs text-muted-foreground">
                        Joined {new Date(member.joined_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select
                      value={member.role}
                      onValueChange={(role) =>
                        changeRoleMutation.mutate({ userId: member.user_id, role })
                      }
                    >
                      <option value="viewer">Viewer</option>
                      <option value="analyst">Analyst</option>
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </Select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (window.confirm("Remove this member?")) {
                          removeMemberMutation.mutate(member.user_id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {invitationList.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Pending Invitations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {invitationList.map((inv) => (
                <div key={inv.id} className="flex items-center justify-between rounded-md border p-3">
                  <div>
                    <p className="text-sm font-medium">{inv.email}</p>
                    <p className="text-xs text-muted-foreground">
                      Invited as <Badge variant="outline">{inv.role}</Badge> · Expires{" "}
                      {new Date(inv.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Badge variant="secondary">{inv.status}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
