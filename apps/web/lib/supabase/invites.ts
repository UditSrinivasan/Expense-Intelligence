type Claims = { email?: unknown; app_metadata?: { provider?: unknown } };

export function invitedEmailSet() {
  return new Set((process.env.INVITED_USER_EMAILS ?? "").split(",").map(value => value.trim().toLowerCase()).filter(Boolean));
}

export function isInvited(claims: Claims) {
  if (process.env.APP_ENV !== "hosted") return true;
  const email = typeof claims.email === "string" ? claims.email.trim().toLowerCase() : "";
  return claims.app_metadata?.provider === "google" && Boolean(email) && invitedEmailSet().has(email);
}
