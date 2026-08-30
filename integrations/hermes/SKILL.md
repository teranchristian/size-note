---
name: size-note
description: Save, update, or retrieve clothing, footwear, ring, hat, and other wearable sizes for people using the local Size Note CLI. Use when the user asks Hermes to remember what fits someone or check a saved size.
version: 0.1.0
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [size-note]
metadata:
  hermes:
    category: productivity
    tags: [sizes, clothing, footwear, shopping]
    requires_toolsets: [terminal]
---

# Size Note

Use the `size-note` CLI with `--json`. Size Note owns person matching, aliases, person notes, current sizes, and history; do not substitute conversational memory for it.

Before the first operation in a session, run `size-note health --json`. If it is unavailable, tell the user that Size Note is not running or the CLI is not installed. Do not fall back to conversational memory.

## Route information to the right field

Keep person context separate from size-specific context:

- **Person notes**: relationship, birth year/date, general preferences, or stable facts about the person. Examples: `my son`, `born in 2024`, `prefers soft fabrics`.
- **Size notes** (`remember --notes`): context about that specific size record. Examples: `bought in Tokyo`, `measured at school`, `winter uniform`.
- **Fit notes** (`remember --fit-notes`): observations about how the item fits. Examples: `runs small`, `a little loose`, `sleeves are short`.

Never store relationship or birth information in a size record just because it appeared in the same sentence as a size.

If a user gives both person context and a size in one request, save/update the person context separately and then save the size.

## Save a size

Run:

```bash
size-note remember --person "NAME" --item "ITEM" --size "SIZE" --system "SYSTEM" --json
```

`--system`, `--brand`, `--model`, `--fit-notes`, and `--notes` are optional.

Handle the returned `status` safely:

- An exact name or known alias saves immediately.
- `confirmation_required` means nothing was saved. Ask whether the candidate is the intended person.
- `multiple_matches` means nothing was saved. Ask the user to choose a candidate.
- `not_found` means nothing was saved. Ask whether to create a new person.

After the user confirms a suggested candidate, rerun with its returned stable ID. Save the new wording as an alias only when the user confirmed it refers to the same person:

```bash
size-note remember --person "Alex" --confirm-person-id "PERSON_ID" --remember-alias --item "T-shirt" --size "M" --json
```

Never silently choose a similar person.

## Create a person

Only create a person after the user confirms that no existing candidate is correct:

```bash
size-note person-add "NAME" --growth-stage adult --json
```

Use `child` when the user explicitly says the person is a child or wants growth-aware reviews. Otherwise use `adult`; do not infer age from relationship context.

When the user supplies person-level context during creation, put it in `--notes`:

```bash
size-note person-add "Haru" --growth-stage child --notes "My son; born in 2024" --json
```

## Update person notes

For an existing person, use `person-update` for person-level notes instead of attaching them to a size record:

```bash
size-note person-update --person "Haru" --notes "My son; born in 2024" --json
```

`person-update` uses the same safe name resolution rules as retrieval. If the result is `confirmation_required`, `multiple_matches`, or `not_found`, do not guess or update anything; ask the user to resolve the person first.

You may also update an explicitly stated growth stage:

```bash
size-note person-update --person "Haru" --growth-stage child --json
```

Do not overwrite useful existing person notes with a shorter fragment when the user is adding context. Read the current person data first when necessary and preserve existing useful context in the replacement note.

## Retrieve sizes

Run:

```bash
size-note get --person "NAME OR ALIAS" --current-only --json
```

Mention the sizing system and brand when present. If an item is due for review, state that the saved value may be outdated instead of presenting it as certainly current.

To check all child review reminders, run:

```bash
size-note review --json
```

Do not estimate size conversions unless Size Note explicitly returns an estimate. The initial release stores confirmed values only.
