---
name: size-note
description: Save, update, retrieve, correct, or delete clothing, footwear, ring, hat, and other wearable sizes for people using the local Size Note CLI. Use when the user asks Hermes to remember what fits someone, check a saved size, correct a mistake, or remove Size Note data.
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

## Update a person

For an existing person, use `person-update` for person-level corrections. It can change the display name, notes, or growth stage:

```bash
size-note person-update --person "Haru" --notes "My son; born in 2024" --json
size-note person-update --person "Haru" --name "Haru Teran" --growth-stage child --json
```

`person-update` uses the same safe name resolution rules as retrieval. If the result is `confirmation_required`, `multiple_matches`, or `not_found`, do not guess or update anything; ask the user to resolve the person first.

Do not overwrite useful existing person notes with a shorter fragment when the user is adding context. Read the current person data first when necessary and preserve existing useful context in the replacement note.

## Correct an existing size record

When the user is correcting a mistake in a specific saved record, do not call `remember`, because that can intentionally create history. First retrieve the person's sizes with IDs:

```bash
size-note get --person "Haru" --json
```

Identify the exact intended record from the returned `sizes` array. If more than one record could match the user's wording, ask which one they mean. Then update that stable record ID:

```bash
size-note size-update --person "Haru" --size-id "SIZE_ID" --size "95" --system "Japan" --json
```

You may also correct `--item`, `--brand`, `--model`, `--fit-notes`, `--notes`, or `--measured-on`. Use `--clear-measured-on` only when the user explicitly wants that date removed.

Use `remember` for a genuine new/current size observation; use `size-update` for correcting an existing saved record.

## Delete data

Deletion is destructive. **Always obtain explicit user confirmation immediately before deleting.** Never infer confirmation from an earlier general request to clean up data.

To delete one size, first run `get --json`, identify the exact record ID, and ask for confirmation. After the user confirms:

```bash
size-note size-delete --person "Haru" --size-id "SIZE_ID" --confirm --json
```

If the deleted record was current and had an older version of the same item/system/brand/model, Size Note restores the most recent previous version as current.

To delete a person, explain that all aliases and all size history for that person will also be deleted, then ask for confirmation. Only after explicit confirmation run:

```bash
size-note person-delete --person "NAME" --confirm --json
```

Never pass `--confirm` before the user has explicitly confirmed the specific deletion.

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
