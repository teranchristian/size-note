---
name: size-note
description: Save, update, retrieve, correct, or delete wearable sizes and person aliases using the local Size Note CLI. Use when the user asks Hermes to remember what fits someone, identify a person by another name or phrase, check a saved size, correct a mistake, or remove Size Note data.
version: 0.4.0
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

Use the `size-note` CLI with `--json`. Size Note owns person matching, aliases, structured birth information, person notes, current sizes, history, and review timing; do not substitute conversational memory for it.

Before the first operation in a session, run `size-note health --json`. If it is unavailable, tell the user that Size Note is not running or the CLI is not installed. Do not fall back to conversational memory.

## Route information to the right field

Keep identity, person facts, and size-specific context separate:

- **Aliases**: another name or phrase the user can use to identify the same person. Examples: `Alex`, `me`, `myself`, `my son`, `my manager`. Self-references and relationship phrases belong here when they unambiguously refer to that person.
- **Birth information** (`person-add/person-update --birth`): a known birth year, year-month, or exact date. Examples: `2024`, `2024-05`, `2024-05-12`.
- **Person notes** (`person-add/person-update --notes`): stable facts or preferences about the person that are not used to identify them. Examples: `prefers soft fabrics`, `usually likes a relaxed fit`.
- **Size notes** (`remember --notes`): context about that specific size record. Examples: `bought in Tokyo`, `measured at school`, `winter uniform`.
- **Fit notes** (`remember --fit-notes`): observations about how the item fits. Examples: `runs small`, `a little loose`, `sleeves are short`.

Never put an identity phrase such as `me`, `myself`, or `my son` in person notes merely because it describes a relationship. If the phrase is how the user refers to the person, store it as an alias.

Aliases must identify one person safely. If a phrase such as `my son`, `my daughter`, `my manager`, or another relationship could refer to more than one person, ask which person the user means before saving that alias. Do not silently assign an ambiguous relationship phrase.

Never store known birth information in notes when the structured `--birth` field can represent it. Never store aliases, relationship identity phrases, or birth information in a size record just because they appeared in the same sentence as a size.

If a user gives an alias, person facts, birth information, and a size in one request, route each part separately and then save the size.

## Manage aliases

When the user explicitly says that another name or phrase refers to an existing person, save it as an alias:

```bash
size-note person-alias-add --person "Riley" --alias "my son" --json
size-note person-alias-add --person "Alex" --alias "myself" --json
```

Use `person-alias-list` when you need to inspect the aliases currently stored for one person:

```bash
size-note person-alias-list --person "Riley" --json
```

To correct an alias, use the existing alias text and its replacement:

```bash
size-note person-alias-update --person "Riley" --alias "my kid" --new-alias "my son" --json
```

Deleting an alias removes an identity shortcut. Ask for explicit confirmation immediately before deleting it, then run:

```bash
size-note person-alias-delete --person "Riley" --alias "my son" --confirm --json
```

Do not add an alias merely because two names look similar. Similar-name matching still requires confirmation that both references are the same person.

## Birth information and growth stage

Birth information is optional and may be partial. Accept exactly what the user knows:

- `2024` when only the year is known.
- `2024-05` when year and month are known.
- `2024-05-12` when the full date is known.

Never invent an unknown month or day. Do not turn `2024` into `2024-01-01`, and do not turn `2024-05` into `2024-05-01`.

When birth information exists, Size Note uses it to determine the effective child/adult stage and review timing. Partial dates are handled conservatively: when the exact age is uncertain, Size Note uses the younger possible age. A person becomes effectively adult only when they are definitely 18. For example, someone stored only as born in `2008` remains child through 2026 and becomes adult from 1 January 2027 without editing the record.

The saved `growth_stage` is a fallback for people without birth information. Do not repeatedly update a person's stored stage just because a birthday passed.

A relationship alias such as `my son`, `my daughter`, `my friend`, or `my mother` does not by itself determine age. Do not infer growth stage only from an alias.

## One physical fit = one size record

A label may express the same fit in several sizing systems. Store those values together in one Size Note record, not as separate current sizes.

Choose one confirmed value as the primary `--size`/`--system`, then pass every other confirmed representation with a repeatable `--equivalent "SYSTEM:SIZE"` option.

Equivalent relationships are bidirectional representations of the same fit. If AU XS is stored with Japan S as an equivalent, treat Japan S as equivalent to AU XS as well. Do not ask to save the reverse direction as a separate equivalent or record, and never create duplicate reverse equivalents.

For example, if an ASICS label says the same shoe is 25.25 cm, EU 40, and US 7, run one command:

```bash
size-note remember --person "Alex" --item "Shoes" --size "25.25" --system "CM" --equivalent "EU:40" --equivalent "US:7" --brand "ASICS" --model "1011B004" --json
```

Do **not** run `remember` three times for CM, EU, and US. They are representations of one physical fit.

Use the same rule for clothing. Examples include a T-shirt marked `JP 90` plus `US 2T`, or pants marked in both a regional size and an equivalent size. `T-shirt`, `Pants`, `Trousers`, `Jacket`, and other wearable item names are valid; do not force everything into shoes.

Only store equivalents explicitly provided by the user, label, manufacturer, or another trusted source. Do not calculate or guess conversions.

## Save a size

Run:

```bash
size-note remember --person "NAME OR ALIAS" --item "ITEM" --size "SIZE" --system "SYSTEM" --json
```

`--system`, repeatable `--equivalent`, `--brand`, `--model`, `--fit-notes`, and `--notes` are optional.

Handle the returned `status` safely:

- An exact name or known alias saves immediately.
- `confirmation_required` means nothing was saved. Ask whether the candidate is the intended person.
- `multiple_matches` means nothing was saved. Ask the user to choose a candidate.
- `not_found` means nothing was saved. Ask whether to create a new person.

After the user confirms a suggested candidate, rerun with its returned stable ID. Save the new wording as an alias only when the user confirmed it refers to the same person:

```bash
size-note remember --person "Alex" --confirm-person-id "PERSON_ID" --remember-alias --item "T-shirt" --size "M" --json
```

For a standalone identity statement, prefer `person-alias-add` rather than attaching alias creation to an unrelated size save.

Never silently choose a similar person.

## Create a person

Only create a person after the user confirms that no existing candidate is correct.

If the user supplied birth information, it is enough to infer the effective child/adult stage; do not ask the stage again. If the user also supplied an unambiguous identity phrase, save it with `--alias`:

```bash
size-note person-add "Riley" --birth "2024" --alias "my son" --json
```

If the user explicitly said the person is an adult, create them as an adult. Do not ask for a birth date unless the user already supplied one:

```bash
size-note person-add "Alex" --growth-stage adult --alias "myself" --json
```

If the user explicitly said the person is a child but gave no birth information, birth information is useful for better reminders. Ask once whether they know the birth year/date, making clear that it is optional. If they do not know it or prefer not to provide it, create the child anyway:

```bash
size-note person-add "Sam" --growth-stage child --json
```

If neither birth information nor an explicit child/adult stage is available, ask **whether the person is a child or an adult before creating them**. Do not silently default to adult.

## Update a person

For an existing person, use `person-update` for person-level facts and corrections. It can change the display name, notes, growth-stage fallback, or birth information. Alias changes use the dedicated `person-alias-*` commands instead.

```bash
size-note person-update --person "Riley" --birth "2024-05" --json
size-note person-update --person "Riley" --notes "Prefers soft fabrics" --json
size-note person-update --person "Riley" --name "Riley A." --json
```

Use `--clear-birth` only when the user explicitly wants the stored birth information removed.

`person-update` uses the same safe name resolution rules as retrieval. If the result is `confirmation_required`, `multiple_matches`, or `not_found`, do not guess or update anything; ask the user to resolve the person first.

Do not overwrite useful existing person notes with a shorter fragment when the user is adding context. Read the current person data first when necessary and preserve existing useful context in the replacement note.

## Correct an existing size record

When the user is correcting a mistake in a specific saved record, do not call `remember`, because that can intentionally create history. First retrieve the person's sizes with IDs:

```bash
size-note get --person "Riley" --json
```

Identify the exact intended record from the returned `sizes` array. If more than one record could match the user's wording, ask which one they mean. Then update that stable record ID:

```bash
size-note size-update --person "Riley" --size-id "SIZE_ID" --size "95" --system "Japan" --json
```

To replace its equivalent representations, repeat `--equivalent "SYSTEM:SIZE"`. To remove all equivalents, use `--clear-equivalents`.

You may also correct `--item`, `--brand`, `--model`, `--fit-notes`, `--notes`, or `--measured-on`. Use `--clear-measured-on` only when the user explicitly wants that date removed.

Use `remember` for a genuine new/current size observation; use `size-update` for correcting an existing saved record.

## Delete data

Deletion is destructive. **Always obtain explicit user confirmation immediately before deleting.** Never infer confirmation from an earlier general request to clean up data.

To delete one size, first run `get --json`, identify the exact record ID, and ask for confirmation. After the user confirms:

```bash
size-note size-delete --person "Riley" --size-id "SIZE_ID" --confirm --json
```

If the deleted record was current and had an older version of the same item/brand/model fit, Size Note restores the most recent previous version as current.

To delete a person, explain that all aliases and all size history for that person will also be deleted, then ask for confirmation. Only after explicit confirmation run:

```bash
size-note person-delete --person "NAME OR ALIAS" --confirm --json
```

Never pass `--confirm` before the user has explicitly confirmed the specific deletion.

## Retrieve sizes

Run:

```bash
size-note get --person "NAME OR ALIAS" --current-only --json
```

Mention the primary sizing system, confirmed equivalents, and brand when present. Treat every confirmed equivalent as bidirectional when answering. A query phrased using either system in an equivalent pair should resolve to the same fit record; for example, asking for `Japan S` or `AU XS` should return the same T-shirt fit rather than prompting for a reverse mapping.

If an item is due for review, state that the saved value may be outdated instead of presenting it as certainly current.

## Review reminders

Run:

```bash
size-note review --json
```

When birth information is known, Size Note uses conservative age bands for automatic child reviews:

- younger than 3: every 90 days
- 3 through 6: every 120 days
- 7 through 12: every 180 days
- 13 through 17: every 270 days
- definitely 18 or older: no automatic child review

If a child has no birth information, Size Note falls back to the original generic rule: shoes every 90 days and other sizes every 180 days.

When reporting a due or soon review, include the person's exact or approximate age when returned and say roughly how long it has been since `verified_at`. Example: `Riley is about 2 years old. Their T-shirt size was last checked 4 months ago, so it may be worth checking again.`

A successful `Still correct` verification updates `verified_at`, restarting that specific size's review timer without creating history.

Do not estimate size conversions unless Size Note explicitly returns an estimate. Size Note stores confirmed values only.
