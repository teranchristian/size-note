#!/usr/bin/env sh
set -eu

show_help() {
  printf '%s\n' \
    "Usage: ./install.sh [--profile NAME | --no-skill]" \
    "" \
    "  --profile NAME  Install the skill for a Hermes profile (default: default)." \
    "  --no-skill      Install the app and CLI without a Hermes skill." \
    "  --help          Show this help."
}

profile_name="default"
install_skill=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      [ "$#" -ge 2 ] || { printf '%s\n' "--profile requires a name." >&2; exit 2; }
      profile_name=$2
      shift 2
      ;;
    --no-skill)
      install_skill=0
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      show_help >&2
      exit 2
      ;;
  esac
done

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' "Docker Compose was not found." "Install Docker, then run this installer again." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "Python 3.11 or newer is required for the host CLI." >&2
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
  printf '%s\n' "Python 3.11 or newer is required for the host CLI." >&2
  exit 1
fi

venv_probe=$(mktemp -d "${TMPDIR:-/tmp}/size-note-venv.XXXXXX")
if ! python3 -m venv "$venv_probe" >/dev/null 2>&1; then
  rm -r -- "$venv_probe"
  printf '%s\n' \
    "Python's venv module is unavailable." \
    "Install the Python venv package, then run this installer again." >&2
  exit 1
fi
rm -r -- "$venv_probe"

profile_home=""
if [ "$install_skill" -eq 1 ]; then
  if ! command -v hermes >/dev/null 2>&1; then
    printf '%s\n' \
      "Hermes was not found." \
      "Install Hermes first, or run ./install.sh --no-skill." >&2
    exit 1
  fi
  case "$profile_name" in
    ""|*[!A-Za-z0-9_-]*)
      printf 'Invalid Hermes profile name: %s\n' "$profile_name" >&2
      exit 2
      ;;
  esac

  if ! profile_details=$(NO_COLOR=1 hermes profile show "$profile_name" 2>/dev/null); then
    printf 'Hermes profile not found: %s\n' "$profile_name" >&2
    printf '%s\n' "Run 'hermes profile list' to see available profiles." >&2
    exit 1
  fi
  profile_home=$(printf '%s\n' "$profile_details" | sed -n \
    's/^[[:space:]]*Path:[[:space:]]*//p' | tail -n 1 | tr -d '\r')
  case "$profile_home" in
    "~") profile_home=$HOME ;;
    "~/"*) profile_home="$HOME/${profile_home#\~/}" ;;
  esac
  if [ -z "$profile_home" ]; then
    if [ "$profile_name" = "default" ]; then
      profile_home="${HOME}/.hermes"
    else
      profile_home="${HOME}/.hermes/profiles/$profile_name"
    fi
  fi
  if [ ! -d "$profile_home" ]; then
    printf 'Hermes profile directory was not found: %s\n' "$profile_home" >&2
    exit 1
  fi

  backend=""
  if backend_output=$(NO_COLOR=1 hermes -p "$profile_name" \
    config get terminal.backend 2>/dev/null); then
    backend=$(printf '%s\n' "$backend_output" | tail -n 1 | tr -d '\r')
  fi

  if [ -z "$backend" ]; then
    backend=$(NO_COLOR=1 hermes -p "$profile_name" \
      config show 2>/dev/null \
      | sed -n '/Terminal/,${/Backend:[[:space:]]*/{s/.*Backend:[[:space:]]*//;p;q}}' \
      | tr -d '\r')
  fi

  if [ -z "$backend" ]; then
    printf 'Could not read terminal.backend for Hermes profile %s.\n' "$profile_name" >&2
    exit 1
  fi
  if [ "$backend" != "local" ]; then
    printf 'Hermes profile %s uses terminal.backend=%s.\n' "$profile_name" "$backend" >&2
    printf '%s\n' \
      "The Size Note skill requires the local terminal backend." \
      "Use --no-skill or select a Hermes profile with terminal.backend=local." >&2
    exit 1
  fi
fi

if [ ! -f "$project_dir/requirements.lock" ]; then
  printf '%s\n' "requirements.lock is missing; cannot perform a reproducible install." >&2
  exit 1
fi

mkdir -p "$project_dir/data"

if [ ! -f "$project_dir/.env" ]; then
  cp "$project_dir/.env.example" "$project_dir/.env"
fi

port_from_file=$(sed -n 's/^SIZE_NOTE_PORT=//p' "$project_dir/.env" | tail -n 1 | tr -d '\r')
port=${SIZE_NOTE_PORT:-${port_from_file:-3010}}
case "$port" in
  ""|*[!0-9]*)
    printf 'Invalid SIZE_NOTE_PORT: %s\n' "$port" >&2
    exit 2
    ;;
esac
if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
  printf 'SIZE_NOTE_PORT must be between 1 and 65535: %s\n' "$port" >&2
  exit 2
fi

printf '%s\n' "Building and starting Size Note..."
SIZE_NOTE_PORT=$port docker compose \
  --project-directory "$project_dir" \
  -f "$project_dir/compose.yaml" \
  up -d --build

data_root=${XDG_DATA_HOME:-${HOME}/.local/share}
cli_root="$data_root/size-note/cli"
bin_root=${XDG_BIN_HOME:-${HOME}/.local/bin}
python3 -m venv "$cli_root"
"$cli_root/bin/python" -m pip install --quiet --upgrade -r "$project_dir/requirements.lock"
"$cli_root/bin/python" -m pip install \
  --quiet --upgrade --no-deps --no-build-isolation "$project_dir"
mkdir -p "$bin_root"

cli_link="$bin_root/size-note"
cli_target="$cli_root/bin/size-note"
cli_real_link="$bin_root/.size-note-real"
wrapper_marker="# Managed by the Size Note installer."

if [ -e "$cli_real_link" ] || [ -L "$cli_real_link" ]; then
  existing_target=$(readlink "$cli_real_link" 2>/dev/null || true)
  if [ ! -L "$cli_real_link" ] || [ "$existing_target" != "$cli_target" ]; then
    printf 'Refusing to replace existing command helper: %s\n' "$cli_real_link" >&2
    exit 1
  fi
else
  ln -s "$cli_target" "$cli_real_link"
fi

if [ -e "$cli_link" ] || [ -L "$cli_link" ]; then
  existing_target=$(readlink "$cli_link" 2>/dev/null || true)
  if [ -L "$cli_link" ] && [ "$existing_target" = "$cli_target" ]; then
    rm -- "$cli_link"
  elif [ ! -f "$cli_link" ] || ! grep -Fqx "$wrapper_marker" "$cli_link"; then
    printf 'Refusing to replace existing command: %s\n' "$cli_link" >&2
    exit 1
  fi
fi

wrapper_tmp="$cli_link.tmp.$$"
{
  printf '%s\n' '#!/usr/bin/env sh' "$wrapper_marker" 'set -eu'
  printf 'SIZE_NOTE_URL=${SIZE_NOTE_URL:-http://127.0.0.1:%s}\n' "$port"
  printf '%s\n' \
    'export SIZE_NOTE_URL' \
    'bin_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)' \
    'exec "$bin_dir/.size-note-real" "$@"'
} >"$wrapper_tmp"
chmod 755 "$wrapper_tmp"
mv -f -- "$wrapper_tmp" "$cli_link"

attempt=0
until "$cli_link" health >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    printf '%s\n' "Size Note did not become healthy. Run docker compose logs for details." >&2
    exit 1
  fi
  sleep 1
done

if [ "$install_skill" -eq 1 ]; then
  skill_root="$profile_home/skills/size-note"
  mkdir -p "$skill_root"
  cp "$project_dir/integrations/hermes/SKILL.md" "$skill_root/SKILL.md"
  if ! skills_output=$(NO_COLOR=1 hermes -p "$profile_name" skills list 2>/dev/null); then
    printf 'Hermes could not scan skills for profile %s.\n' "$profile_name" >&2
    exit 1
  fi
  if ! printf '%s\n' "$skills_output" \
    | grep -E '(^|[[:space:]])size-note([[:space:]]|$)' >/dev/null; then
    printf 'Hermes did not discover the Size Note skill for profile %s.\n' "$profile_name" >&2
    exit 1
  fi
  printf 'Installed and verified Hermes skill at %s\n' "$skill_root"
fi

printf '%s\n' \
  "" \
  "Size Note is ready." \
  "Website: http://127.0.0.1:$port" \
  "CLI: $bin_root/size-note health" \
  "Data: $project_dir/data/size-note.db"
if [ "$install_skill" -eq 1 ]; then
  printf 'Hermes: start a new session in profile %s, then ask it to remember a size.\n' \
    "$profile_name"
fi
