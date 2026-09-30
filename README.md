# Soumission.VIP

Home-services directory and quote marketplace, rebranded from House Service Pro.

Includes public listings, owner/staff administration, customer and business accounts, job posts, quotes, lead capture, and English/French UI.

Deploy this repository with Render **New > Blueprint**. Read HOSTING.md. The blueprint uses a paid web service and a 1 GB persistent disk. Choose DEV_PASSWORD during deployment. Open /admin after deployment, enter that setup password, create your own owner account, and finish onboarding. No default admin or demo login is enabled.

The public site is at /. Owner/staff/client/business login is at /admin. Invitation links use /invite?token=... . The health check is /health. On Windows, RUN_WINDOWS.bat uses an installed Python and asks for a setup password.

Records live in DATA_DIR. Keep one Gunicorn worker: the filesystem stores use process-local locks. Make verified backups before updates.

Payment adapters are optional and disabled in the starting configuration. They are not a complete payment lifecycle: signed webhooks, reconciliation and entitlement enforcement still require implementation and testing before paid marketplace launch. Optional STRIPE_SECRET_KEY, PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are set in Render only if those adapters are used. PUBLIC_BASE_URL can be set to your verified custom-domain URL; otherwise Render's service URL is used for generated links.

Changes in this package: Soumission.VIP branding; corrected Render /admin and /invite routes; removal of misleading demo/default-password prompts; automatic Render base-URL fallback; simplified deployment secrets; Python version pin; clean repository packaging.

The supplied Soumission.VIP logo is included unchanged in assets/soumission-vip-logo.png. It appears on the public site and access/owner screens. Fresh installations start with it automatically. For an existing database, upload the supplied image in the owner Branding page.
