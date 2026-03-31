import CredentialsProvider from "next-auth/providers/credentials";
import type { NextAuthOptions } from "next-auth";

const DEFAULT_LOCAL_BACKEND_URL = "http://localhost:8000";
const DEFAULT_PRODUCTION_BACKEND_URL = "https://fortressflow-api.vercel.app";

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/+$/, "");
}

function getBackendUrl(): string {
  const configuredUrl =
    process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;

  if (configuredUrl) {
    return normalizeBaseUrl(configuredUrl);
  }

  return process.env.NODE_ENV === "production"
    ? DEFAULT_PRODUCTION_BACKEND_URL
    : DEFAULT_LOCAL_BACKEND_URL;
}

const BACKEND_URL = getBackendUrl();

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        try {
          const res = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });

          if (!res.ok) {
            return null;
          }

          const data = await res.json();

          return {
            id: data.user.id,
            name: data.user.full_name || data.user.email,
            email: data.user.email,
            role: data.user.role,
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60,
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = (user as any).role;
        token.accessToken = (user as any).accessToken;
        token.refreshToken = (user as any).refreshToken;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id = token.id;
        (session.user as any).role = token.role;
      }
      (session as any).accessToken = token.accessToken;
      return session;
    },
  },
  secret:
    process.env.NEXTAUTH_SECRET ||
    (process.env.NODE_ENV === "production" ? undefined : "dev-nextauth-secret"),
};
