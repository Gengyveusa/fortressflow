"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { User, Save } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/lib/hooks/use-toast";
import api from "@/lib/api";

interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export default function ProfilePage() {
  const { data: session } = useSession();
  const { toast } = useToast();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Edit profile state
  const [fullName, setFullName] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // Change password state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    // Pre-populate name from session while we fetch the full profile
    if (session?.user?.name && !fullName) {
      setFullName(session.user.name);
    }

    async function fetchProfile() {
      try {
        const res = await api.get<UserProfile>("/auth/me");
        setProfile(res.data);
        setFullName(res.data.full_name || session?.user?.name || "");
      } catch {
        // Fall back to session data so page still renders
        if (session?.user) {
          const fallback: UserProfile = {
            id: "",
            email: session.user.email ?? "",
            full_name: session.user.name ?? null,
            role: (session.user as { role?: string }).role ?? "user",
            is_active: true,
            created_at: new Date().toISOString(),
            last_login_at: null,
          };
          setProfile(fallback);
          setFullName(fallback.full_name || "");
        }
        // Non-critical — session data is already shown
      } finally {
        setLoading(false);
      }
    }
    if (session) {
      fetchProfile();
    } else {
      // If no session yet, wait briefly — but don't block forever
      const timer = setTimeout(() => setLoading(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [session, toast]);
    if (session) fetchProfile();
  }, [session]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const res = await api.put<UserProfile>("/auth/me", {
        full_name: fullName,
      });
      setProfile(res.data);
      toast({ title: "Profile updated", variant: "success" });
    } catch {
      toast({ title: "Failed to update profile", variant: "destructive" });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      toast({
        title: "Password must be at least 8 characters",
        variant: "destructive",
      });
      return;
    }
    if (newPassword !== confirmNewPassword) {
      toast({ title: "Passwords do not match", variant: "destructive" });
      return;
    }

    setSavingPassword(true);
    try {
      await api.put("/auth/me", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast({ title: "Password changed successfully", variant: "success" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to change password";
      toast({ title: detail, variant: "destructive" });
    } finally {
      setSavingPassword(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800">
            <User className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          </div>
          <div>
            <h1 className="text-xl font-semibold dark:text-gray-100">Profile</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading your profile…</p>
          </div>
        </div>
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="pt-6 space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex justify-between items-center">
                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="pt-6 space-y-4">
            <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-10 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-9 w-28 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800">
            <User className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          </div>
          <div>
            <h1 className="text-xl font-semibold dark:text-gray-100">Profile</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Manage your account settings</p>
          </div>
        </div>
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-10 text-center">
            <User className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 font-medium">Unable to load profile</p>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Please sign in to view your profile.</p>
          </CardContent>
        </Card>
      </div>
    );
  }
  // Show session-based info immediately; overlay backend data when ready
  const displayEmail = profile?.email || session?.user?.email || "";
  const displayName = profile?.full_name || session?.user?.name || "";
  const displayRole = profile?.role || (session?.user as any)?.role || "user";

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800">
          <User className="h-5 w-5 text-gray-600 dark:text-gray-300" />
        </div>
        <div>
          <h1 className="text-xl font-semibold dark:text-gray-100">Profile</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Manage your account settings
          </p>
        </div>
      </div>

      <Separator className="dark:border-gray-800" />

      {/* User Info */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">
            Account Information
          </CardTitle>
          <CardDescription className="dark:text-gray-400">
            Your current account details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Email
            </span>
            <span className="text-sm font-medium dark:text-gray-200">
              {displayEmail}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Role
            </span>
            <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
              {displayRole}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Member since
            </span>
            <span className="text-sm dark:text-gray-300">
              {profile?.created_at
                ? new Date(profile.created_at).toLocaleDateString()
                : loading
                  ? "Loading..."
                  : "—"}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Edit Profile */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">
            Edit Profile
          </CardTitle>
          <CardDescription className="dark:text-gray-400">
            Update your display name
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpdateProfile} className="space-y-4">
            <div className="space-y-2">
              <Label className="dark:text-gray-300">Full Name</Label>
              <Input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your full name"
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <Button type="submit" disabled={savingProfile}>
              <Save className="h-4 w-4 mr-2" />
              {savingProfile ? "Saving..." : "Save Changes"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Change Password */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">
            Change Password
          </CardTitle>
          <CardDescription className="dark:text-gray-400">
            Update your password
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <Label className="dark:text-gray-300">Current Password</Label>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                required
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div className="space-y-2">
              <Label className="dark:text-gray-300">New Password</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div className="space-y-2">
              <Label className="dark:text-gray-300">
                Confirm New Password
              </Label>
              <Input
                type="password"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                placeholder="Re-enter new password"
                required
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
              {confirmNewPassword && newPassword !== confirmNewPassword && (
                <p className="text-xs text-red-500">Passwords do not match</p>
              )}
            </div>
            <Button type="submit" disabled={savingPassword}>
              <Save className="h-4 w-4 mr-2" />
              {savingPassword ? "Changing..." : "Change Password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
