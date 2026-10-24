const requiredHostedVariables = [
  "API_URL",
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  "INVITED_USER_EMAILS",
] as const;

type Environment = Record<string, string | undefined>;

export function hostedConfigurationError(environment: Environment = process.env) {
  if (environment.APP_ENV !== "hosted") return null;
  const missing = requiredHostedVariables.filter(name => !environment[name]?.trim());
  return missing.length ? `Missing hosted configuration: ${missing.join(", ")}` : null;
}
