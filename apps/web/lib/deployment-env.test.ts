import assert from "node:assert/strict";
import test from "node:test";

import { hostedConfigurationError } from "./deployment-env.ts";

test("local builds do not require hosted secrets", () => {
  assert.equal(hostedConfigurationError({ APP_ENV: "local" }), null);
});

test("hosted runtime fails closed when server configuration is incomplete", () => {
  assert.match(hostedConfigurationError({ APP_ENV: "hosted" }) ?? "", /API_URL/);
  assert.equal(hostedConfigurationError({
    APP_ENV: "hosted",
    API_URL: "https://api.example.invalid",
    NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "synthetic-publishable-key",
    INVITED_USER_EMAILS: "tester@example.invalid",
  }), null);
});
