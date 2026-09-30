# Host Smell Panties and Soumission.VIP

You have two separate app ZIPs. Put each app in its own GitHub repository and create one Render Blueprint for each repository. GitHub stores the source; Render runs the app.

## 1. Unzip

Extract the outer bundle. Then extract each inner ZIP into its own folder. Each app folder has render.yaml, requirements.txt and README.md at its top level.

## 2. Upload to GitHub

Create two repositories named smell-panties and soumission-vip. Private repositories are fine when you grant Render access.

In each repository, use Add file > Upload files (or the new repository's upload-existing-files link). Drag in the extracted app files and folders, then commit. Upload the CONTENTS of the app folder, not the ZIP or an extra enclosing folder. Check that render.yaml appears at the repository root. Include hidden .python-version and .gitignore files; show hidden files in your file picker, use GitHub Desktop, or create these files in GitHub with their packaged contents if the picker omits them. These packages have fewer than 100 files each.

## 3. Deploy on Render

1. Sign in to Render and connect GitHub.
2. Choose New > Blueprint and select the first repository.
3. Use the branch containing your files; keep render.yaml as the Blueprint path and the repository root as the root directory.
4. Review the service and disk charges shown by Render. Each blueprint configures a paid Starter web service and a 1 GB disk. Persistent disks require paid services; removing the disk would make saved data vulnerable to loss on redeploy/restart.
5. Enter the requested secret (below), then deploy the Blueprint.
6. Repeat for the second repository. Wait until each service is Live and open the service URL displayed by Render.

| App | Secret you choose | First login |
|---|---|---|
| Smell Panties | APP_PASSWORD | Open the service URL and enter that password. |
| Soumission.VIP | DEV_PASSWORD | Open the service URL followed by /admin, enter this setup password, create your owner username/password, and finish setup. Use that owner account for later logins. |

Choose long, unique passwords. Enter secrets in Render, not in GitHub files. Render generates Smell Panties' SECRET_KEY automatically; keep it stable across deployments. Demo/default-password logins are disabled for Soumission.VIP.

The blueprints already set the build command, start command, health path and DATA_DIR. Keep the supplied one-worker setting because these apps use JSON storage and in-process locks.

## 4. Check the live apps

Visit /health on each service; expect JSON with ok: true. Then log in.

Smell Panties: create a test creator, edit it, and delete it. Soumission.VIP: finish owner setup; inspect the public site; create separate test client and business accounts; post a test job and submit a quote. Save a harmless test record, redeploy, and verify it remains; this checks the actual attached disk. Local packaging tests cannot verify your Render account or disk attachment.

## 5. Connect Soumission.VIP

If you control soumission.vip, open the Soumission service in Render, then Settings > Custom Domains > Add Custom Domain. Enter soumission.vip. At your domain provider, enter exactly the DNS records Render requests. Return to Render and verify the domain. Render issues TLS certificates after successful verification. Only after the domain works, set PUBLIC_BASE_URL to https://soumission.vip in the service's environment and redeploy so generated invite/payment links use it.

Use the same process for any domain you own for Smell Panties. Rebranding alone does not register or connect a domain.

## Updates and backups

Push source changes to the connected GitHub branch to deploy updates according to the service's auto-deploy settings. Keep the same persistent disk and DATA_DIR. Back up the data before changes and test restoration. Do not upload runtime records, secrets, .venv, or backups to GitHub. Changes to seed/config.json affect a fresh database; an existing Soumission installation keeps its saved branding, which the owner can update in Branding.

## Troubleshooting

- No render.yaml found: the repository contains the ZIP or an extra enclosing folder. Put the extracted files at the repository root.
- Module not found: check the build logs and requirements.txt; do not use a Static Site for these Python backends.
- Soumission setup password rejected: use the DEV_PASSWORD you set in this Render service. There is no admin default.
- Smell Panties password not configured: add APP_PASSWORD in Render's Environment settings and redeploy.
- Saved records disappear: confirm a disk is mounted at /var/data and the packaged DATA_DIR value is unchanged.
- Data unreadable: restore a verified backup; do not replace the file with an empty database to hide the problem.

## What is and is not included

Smell Panties is the existing owner operations dashboard. It is not yet a complete customer marketplace. Soumission.VIP includes the directory, roles, jobs and quotes; its optional payment adapters still need full payment-lifecycle implementation and testing before charging customers. These packages do not claim completion of the unavailable TSI1064880 or SAYF3691827 SOPs.

## Official instructions checked on 2026-09-30

- GitHub uploads: https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- Render Blueprints: https://render.com/docs/infrastructure-as-code
- Blueprint settings: https://render.com/docs/blueprint-spec
- Environment secrets: https://render.com/docs/configure-environment-variables
- Persistent disks: https://render.com/docs/disks
- Custom domains: https://render.com/docs/custom-domains
