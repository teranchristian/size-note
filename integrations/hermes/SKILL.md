---
name: size-note
description: Save, update, or retrieve clothing, footwear, ring, hat, and other wearable sizes for people using the local Size Note CLI. Use when the user asks Hermes to remember what fits someone or check a saved size.
---

# Size Note

Use the `size-note` CLI with `--json`. Size Note owns person matching, aliases, current sizes, and history; do not substitute conversational memory for it.

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

Use `child` when the user says the person is a child or wants growth-aware reviews. Otherwise use `adult`; do not infer age from relationship context. Relationship context belongs in optional `--notes`, not in structured fields.

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

Do not estimate size conversions unless Size Note explicitly returns an estimate. Version 1 stores confirmed values only.
