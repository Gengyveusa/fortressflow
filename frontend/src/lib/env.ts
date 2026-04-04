export function validateEnv() {
  const required = ["NEXTAUTH_URL"];

  const missing = required.filter((key) => !process.env[key]);

  if (missing.length > 0) {
    console.error("❌ Missing env vars:", missing);
  }
}
