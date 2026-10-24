import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { isInvited } from "./invites.ts";

const originalEnvironment = process.env.APP_ENV;
const originalInvites = process.env.INVITED_USER_EMAILS;

afterEach(() => {
  if (originalEnvironment === undefined) delete process.env.APP_ENV;
  else process.env.APP_ENV = originalEnvironment;
  if (originalInvites === undefined) delete process.env.INVITED_USER_EMAILS;
  else process.env.INVITED_USER_EMAILS = originalInvites;
});

test("local development does not require the hosted allowlist", () => {
  process.env.APP_ENV = "local";
  delete process.env.INVITED_USER_EMAILS;
  assert.equal(isInvited({}), true);
});

test("hosted access requires an exact allowlisted Google identity", () => {
  process.env.APP_ENV = "hosted";
  process.env.INVITED_USER_EMAILS = " priya@example.com,alex@example.co.uk ";

  assert.equal(isInvited({ email: "PRIYA@example.com", app_metadata: { provider: "google" } }), true);
  assert.equal(isInvited({ email: "other@example.com", app_metadata: { provider: "google" } }), false);
  assert.equal(isInvited({ email: "priya@example.com", app_metadata: { provider: "email" } }), false);
  assert.equal(isInvited({ email: "priya@example.com" }), false);
});
