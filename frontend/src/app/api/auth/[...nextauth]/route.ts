import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email", placeholder: "admin@fortressflow.io" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        // Stub: accept admin@fortressflow.io / fortressflow
        if (
          credentials?.email === "admin@fortressflow.io" &&
          credentials?.password === "fortressflow"
        ) {
          return {
            id: "1",
            name: "Admin",
            email: "admin@fortressflow.io",
          };
        }
        return null;
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET || (process.env.NODE_ENV === "production" ? undefined : "dev-nextauth-secret"),
});

export { handler as GET, handler as POST };
