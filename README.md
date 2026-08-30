# Size Note

Size Note is a private, self-hosted place to remember clothing, footwear, ring, hat, and other wearable sizes for the people you shop for. It includes a phone-friendly website, a JSON API, a CLI designed for AI agents, and a small Hermes skill. It does not use MCP.

## Current scope

- Stores a canonical person name, confirmed aliases, an adult/child fallback, optional partial birth information, and optional notes.
- Accepts birth information as `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`; unknown month/day values are never invented.
- Uses birth information, when present, to determine whether a person is effectively a child or adult. Partial dates stay conservative until the person is definitely 18.
- Keeps relationship and preference context in optional notes instead of building a family model.
- Stores general or brand-specific sizes, sizing systems, models, and fit notes.
- Groups confirmed equivalent sizing systems into one physical fit record.
- Preserves previous sizes when a value changes.
- Treats re-entering the same size as verification rather than a duplicate.
- Suggests age-aware reviews for children, using each size record's last verification time.
- Requires confirmation before a similar name becomes an alias.

Automatic size conversion is intentionally outside the initial scope. Saved values are confirmed values.

## People, birth information, and review timing

A person's birth information is optional. Store only the precision you actually know:

- `2024` — year only
- `2024-05` — year and month
- `2024-05-12` — exact date

Size Note does not convert an unknown birthday to January 1 or the first day of a month. When the exact age is uncertain, it uses the younger possible age so reminders do not stop too early.

Birth information drives the effective child/adult stage when present. A person becomes effectively adult only when they are definitely 18. For example, someone stored only as born in `2008` remains effectively a child through 2026 and becomes an adult from 1 January 2027 without a scheduled database update. The stored `growth_stage` remains a fallback for people without birth information.

For children with birth information, review intervals are intentionally simple:

- under 3 years: every 90 days
- 3–6 years: every 120 days
- 7–12 years: every 180 days
- 13–17 years: every 270 days
- definitely 18+: no automatic child review

If a child has no birth information, the fallback remains 90 days for shoes and 180 days for other items.

Each size has its own `verified_at` timestamp. Choosing **Still correct** updates that timestamp without creating history, so one person's shoes can be recently checked while an older T-shirt record is already due for review.

## Creating people

Size Note no longer silently assumes a new person is an adult.

- If birth information is supplied, the effective stage can be inferred automatically.
- If the user explicitly says adult, no birth information is needed.
- If the user explicitly says child, birth information is useful for better reminders but remains optional.
- If neither birth information nor an adult/child stage is known, ask which one applies before creating the person.

Relationship words such as `my son` or `my mother` are person notes; they do not by themselves determine age.

## Install on a Hermes host

Linux or macOS, Docker Compose, Python 3.11+ with `venv`, and Hermes are prerequisites. The Hermes profile must use `terminal.backend=local` because the skill calls a CLI installed on the host. The installer checks these requirements but does not install them or change Hermes configuration.

```bash
git clone https://github.com/teranchristian/size-note.git
cd size-note
hermes profile list
./install.sh --profile my-profile
```

Use `./install.sh --profile default` for the default Hermes profile. The installer rejects unknown profiles instead of creating new profile directories.

This builds and starts the container, creates the persistent `data/` directory, installs the host CLI into `~/.local/bin`, copies the skill into the selected Hermes profile, verifies CLI health and Hermes skill discovery, and then asks you to start a new Hermes session. Rerunning the installer upgrades the application while preserving the SQLite database. Alembic applies schema upgrades automatically, so adding fields such as birth information does not require deleting the database.

For a non-Hermes installation:

```bash
./install.sh --no-skill
```

The website listens at `http://127.0.0.1:3010` by default. Keep that private binding and publish it through Tailscale Serve or an existing trusted reverse proxy for phone access. To use another port, edit `SIZE_NOTE_PORT` in `.env` or set it while installing:

```bash
SIZE_NOTE_PORT=3210 ./install.sh --profile my-profile
```

The installer configures the CLI to use the same port. An explicit `SIZE_NOTE_URL` environment variable can still override it.

Verify the installation from the host:

```bash
size-note health
hermes -p my-profile skills list
```

Then start a new Hermes session and ask it to remember or retrieve a size.

## CLI

Create people:

```bash
size-note person-add "Alexandra" --growth-stage adult
size-note person-add "Haru" --birth 2024 --notes "My son"
size-note person-add "Sam" --growth-stage child --notes "Prefers soft fabrics"
```

Update birth information later without changing the person's size history:

```bash
size-note person-update --person "Haru" --birth 2024-05
size-note person-update --person "Haru" --birth 2024-05-12
```

Save and retrieve sizes:

```bash
size-note remember --person "Sam" --item shoes --size "15 cm" --system JP
size-note remember --person "Alexandra" --item tshirt --size M --brand "Example Brand"
size-note get --person "Alexandra" --current-only
size-note review
```

A single physical fit can carry multiple confirmed representations:

```bash
size-note remember \
  --person "Alexandra" \
  --item shoes \
  --size "25.25" \
  --system CM \
  --equivalent EU:40 \
  --equivalent US:7
```

Every command supports `--json`. Expected identity outcomes such as `confirmation_required`, `multiple_matches`, and `not_found` return structured data without changing anything.

After a user confirms that `Alex` means the suggested Alexandra record:

```bash
size-note remember \
  --person "Alex" \
  --confirm-person-id "PERSON_ID_FROM_THE_RESULT" \
  --remember-alias \
  --item tshirt \
  --size M \
  --json
```

## Local development

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn size_note.main:app --reload --port 3010
```

Run checks:

```bash
uv run ruff check .
uv run pytest
./scripts/requirements-lock.sh
```

`tests/api_contract.json` locks the public routes and schemas. An intentional API change must be reviewed for CLI and Hermes compatibility before updating that contract snapshot.

`requirements.lock` is exported from `uv.lock` and is used by both Docker and the host installer, so fresh installations use the dependency versions tested by CI.

## Architecture

The website and JSON API call the same Python service layer. The CLI calls the API, and Hermes calls the CLI through its existing terminal capability.

```mermaid
flowchart TD
    Hermes["Hermes skill"] --> CLI["Size Note CLI"]
    CLI --> API["JSON API"]
    Web["Mobile website"] --> Rules["Shared rules"]
    API --> Rules
    Rules --> DB["SQLite"]
```

SQLite data lives at `data/size-note.db` and is mounted outside the container. Database upgrades use Alembic migrations.

## API

Interactive API documentation is available at `/docs` while the service is running. Core routes are:

- `POST /api/people/resolve`
- `POST /api/people`
- `PATCH /api/people/{id}`
- `POST /api/people/{id}/aliases`
- `POST /api/sizes`
- `POST /api/sizes/{id}/verify`
- `GET /api/people/{id}/sizes`
- `GET /api/reviews`
- `GET /health`

## License

MIT
