# G2.1 pre-launch refinement

G2.1 is based on G2 commit `20c6c5b` and does not authorize deployment or hosted database changes.

## Financial behavior

The existing signed-component and largest-remainder engine remains authoritative. Discount components now declare a fixed or percentage method, eligible earlier item indexes, optional cap, minimum eligible order, promotion reference, and participant eligibility. Items can be non-discountable. Promotions resolve in list order against remaining eligible value, cannot be duplicated, cannot exceed their eligible basis, and cannot create negative participant consumption. External cashback is rejected as a bill reduction until it is actually received.

Taxes and fees remain explicit recorded components. Inclusive tax stays in the item price; additional tax, service, delivery, packaging, tips, and rounding appear after discounts. The engine does not infer a taxable base.

## Appearance

Light, dark, and system themes plus Ocean, Emerald, Violet, Amber, Coral, and Slate accents use CSS tokens. A small pre-hydration script reads the versioned local cache to prevent an incorrect-theme flash; the authenticated profile remains the durable source. Positive, negative, and warning colors are independent from the accent.

## Private beta feedback

The global feedback dialog accepts a categorized description, optional reproduction steps, optional page path, optional contact permission, and an explicitly selected screenshot. Images are resized and re-encoded in the browser before submission. The UI warns against financial information. Tokens, cookies, full URLs, sessions, and financial records are never captured automatically.

Reports are owner-isolated. Review requires an email in server-only `FEEDBACK_ADMIN_EMAILS`; hosted PostgreSQL additionally requires the transaction-local `app.feedback_admin` RLS condition. Review is available at `/feedback` and reports are not converted to public GitHub issues.
