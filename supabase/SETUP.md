# Setting up the report form (Supabase test project)

You do these steps; Claude Code never sees your keys. Everything here is free-tier.

1. Create a free account at supabase.com and a new project named `marxbase-test` (any region; choose a database password and keep it in your password manager; the site does not use it).
2. In the project's **SQL editor**, paste the whole of `supabase/schema.sql` and run it. It creates one table, `suggestion`, and the security rules.
3. In **Project settings → API**, copy the **Project URL** and the **anon public** key into `marxbase-site/site-config.json` (copy `site-config.example.json`; the file is git-ignored):
   `{ "supabaseUrl": "https://....supabase.co", "supabaseAnonKey": "..." }`
   The anon key is meant to be public. Never put the `service_role` key here.
4. In the research repository's `.env` (never shared), add two lines:
   `SUPABASE_URL=https://....supabase.co` and `SUPABASE_SERVICE_KEY=<the service_role key>`.
5. Rebuild the site: `python3 build.py --bundle ../releases/1.0-draft --out dist`, then reload `http://localhost:8765`. A "Report or suggest" box appears at the bottom of result, gene, paper, strain and product pages.
6. Run the security check: `cd marxbase-site && python3 supabase/rls_check.py` (all lines must say PASS).
7. Use the maintainer commands from the research repository: `python -m kmarx.curate suggestions pull`, then `... suggestions review`.

Notes: a free project pauses after about a week without activity; open the dashboard and press Restore if that happens. The offline copy never contains the form or the keys.
