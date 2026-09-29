#!/usr/bin/env bash
# Deploy the Death Plateau server. Link it as /opt/deathplateau/deploy.sh and use it instead of
# the by-hand chain - every step below exists because leaving it out broke something.
#
#   ./deploy.sh                  normal deploy: restarts the moment the build is done
#   ./deploy.sh --countdown      ...but warns players first: the "System update in" timer, 60 seconds
#   ./deploy.sh --countdown=300  ...5 minutes
#   ./deploy.sh --force-engine   deploy even if the engine has commits GitHub does not
#
# The options go in any order. With --countdown the build is done while the world is still up on the
# old code, and the timer starts only once it has succeeded, so players are warned about a restart
# that is certain to happen - and a build that fails leaves them playing, unwarned.
#
# THE DEV WORLD (World 2, staff only). A second engine in this same container, with its own checkouts
# of both repos under /opt/deathplateau/dev, its own .env, saves, database, clans, trading post and
# logs, and its own service, deathplateau-dev.service. It runs with NODE_PRODUCTION=false (the ::
# developer commands) and NODE_MIN_STAFF_LEVEL=3: administrators and up get in, everyone else is told
# "This world is full". A dev deploy never touches the live world, and a live deploy never touches dev.
# Its ports are live's plus one: game 43595, web/cache 8889 (and management 8899, loopback only) - the
# launcher's "Dev world" button connects to those, or to the dev world's own playit.gg tunnels.
#
#   ./deploy.sh --dev-setup                one time: the dev checkouts, dev .env and systemd unit.
#                                          Creates only what is missing, so it is safe to run again.
#   ./deploy.sh --dev                      build and restart ONLY the dev world, on live's branch
#   ./deploy.sh --dev --branch=feat-x      ...on another branch, in both repos
#   ./deploy.sh --dev --engine-branch=feat-x   ...another branch in one repo only
#   ./deploy.sh --dev --content-branch=feat-x  (the other stays on live's branch)
#   ./deploy.sh --dev --countdown          ...warn whoever is on dev first (60s, or --countdown=N)
#   ./deploy.sh --dev --resync-saves       ...and give staff their LIVE characters again, over their dev
#                                          ones (each old dev save kept as <name>.sav.bak)
#
# Unlike live, the dev world is stopped BEFORE its pull and build, not after: NODE_PRODUCTION=false
# runs a file watcher that rebuilds the packs by itself when content changes, and a pull would set it
# off in the middle of this script's own build. So dev is down while it builds, and a failed build
# leaves it down (fix, push, and run --dev again). Every dev deploy also copies the staff accounts
# (level 3+) from live's database into dev's, and live's login key - see tools/server/copy-staff.ts -
# and each staff member's live character, the first time only: a character with a dev save already
# keeps it (so what is done on dev stays on dev) unless --resync-saves is given.
#
#   systemctl status deathplateau-dev      journalctl -u deathplateau-dev -f
#   systemctl stop deathplateau-dev        (an idle dev world still holds most of a GB of RAM)
set -euo pipefail

# This script is tracked in the content repo, and it pulls that repo while running.
# bash reads a script lazily, so a file that changes mid-run has undefined behaviour -
# re-exec from a private copy first.
if [ "${DEPLOY_REEXEC:-}" != "1" ]; then
    SELF_COPY=$(mktemp /tmp/deathplateau-deploy.XXXXXX.sh)
    cp "$0" "$SELF_COPY"
    trap 'rm -f "$SELF_COPY"' EXIT
    DEPLOY_REEXEC=1 exec bash "$SELF_COPY" "$@"
fi

# /opt/deathplateau and deathplateau.service since the server was named (2026-09-23); a server not
# yet moved over still has /opt/lostcity and lostcity.service, and deploys the same.
ROOT=/opt/deathplateau
[ -d "$ROOT" ] || ROOT=/opt/lostcity
CONTENT=$ROOT/content
ENGINE=$ROOT/engine
BRANCH=377-wip
SERVICE=deathplateau.service
systemctl cat "$SERVICE" >/dev/null 2>&1 || SERVICE=lostcity.service
KEEP_BACKUPS=10
PORT=${WEB_MANAGEMENT_PORT:-8898}
BACKUP_DIR=$ROOT

# the dev world
LIVE_ENGINE=$ENGINE
LIVE_SERVICE=$SERVICE
DEV_ROOT=$ROOT/dev
DEV_SERVICE=deathplateau-dev.service
DEV_UNIT=/etc/systemd/system/$DEV_SERVICE
DEV_DROPIN_DIR=/etc/systemd/system/$DEV_SERVICE.d
DEV_DROPIN=$DEV_DROPIN_DIR/dev-world.conf
# The settings the dev world must own. Everything else it inherits from live's .env, and these are
# the ones that would make dev a second live world if they leaked across.
DEV_OWN_KEYS='NODE_ID|NODE_PORT|WEB_PORT|WEB_MANAGEMENT_PORT|NODE_PROFILE|NODE_PRODUCTION|NODE_MIN_STAFF_LEVEL|LOGIN_SERVER|FRIEND_SERVER|LOGGER_SERVER|EASY_STARTUP|DB_BACKEND|DISCORD_TOKEN|DISCORD_GUILD_ID|LOGIN_RSA_KEY_PATH|BUILD_SRC_DIR|BUILD_STARTUP|NODE_BOTS'
DEV_NODE_ID=11          # World 2 - the client shows nodeId - 9
DEV_MIN_STAFF_LEVEL=3   # administrator
DEV_KEEP_BACKUPS=5

FORCE_ENGINE=
COUNTDOWN=
DEV=
DEV_SETUP=
RESYNC_SAVES=
ENGINE_BRANCH=
CONTENT_BRANCH=
for arg in "$@"; do
    case "$arg" in
        --force-engine) FORCE_ENGINE=1 ;;
        --countdown)    COUNTDOWN=60 ;;
        --countdown=*)  COUNTDOWN=${arg#--countdown=} ;;
        --dev)          DEV=1 ;;
        --dev-setup)    DEV_SETUP=1 ;;
        --resync-saves) RESYNC_SAVES=1 ;;
        --branch=*)     ENGINE_BRANCH=${arg#--branch=}; CONTENT_BRANCH=${arg#--branch=} ;;
        --engine-branch=*)  ENGINE_BRANCH=${arg#--engine-branch=} ;;
        --content-branch=*) CONTENT_BRANCH=${arg#--content-branch=} ;;
        *) printf 'unknown option: %s\n' "$arg" >&2; exit 1 ;;
    esac
done
case "$COUNTDOWN" in
    ''|*[!0-9]*) [ -z "$COUNTDOWN" ] || { printf 'bad --countdown: %s\n' "$COUNTDOWN" >&2; exit 1; } ;;
esac
# the live world only ever deploys its own branch
if [ -z "$DEV" ] && [ -n "$ENGINE_BRANCH$CONTENT_BRANCH" ]; then
    printf -- '--branch, --engine-branch and --content-branch are for the dev world: add --dev\n' >&2; exit 1
fi
if [ -z "$DEV" ] && [ -n "$RESYNC_SAVES" ]; then
    printf -- '--resync-saves is for the dev world: add --dev\n' >&2; exit 1
fi
if [ -n "$DEV_SETUP" ] && [ $# -ne 1 ]; then
    printf -- '--dev-setup takes no other options\n' >&2; exit 1
fi
ENGINE_BRANCH=${ENGINE_BRANCH:-$BRANCH}
CONTENT_BRANCH=${CONTENT_BRANCH:-$BRANCH}

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!!! %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- dev world helpers
# A .env value: the last assignment wins (as dotenv), quotes and a trailing CR stripped.
env_get() {
    [ -f "$1" ] || return 0
    sed -n "s/^[[:space:]]*$2[[:space:]]*=//p" "$1" | tail -n 1 | tr -d '\r' \
        | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

# The login RSA key live runs with. The client has ONE public key built in, so every world must use
# the same private half - dev gets a copy (never a path into live's directory).
live_key() {
    local k
    k=$(env_get "$LIVE_ENGINE/.env" LOGIN_RSA_KEY_PATH)
    k=${k:-data/config/login-rsa.pem}
    case "$k" in /*) ;; *) k=$LIVE_ENGINE/$k ;; esac
    printf '%s' "$k"
}
sync_dev_key() {
    local from to
    from=$(live_key)
    to=$DEV_ROOT/engine/data/config/login-rsa.pem
    if [ ! -f "$from" ]; then
        printf '  \033[1;33mno login key at %s - dev logins will fail until LOGIN_RSA_KEY_PATH is sorted\033[0m\n' "$from"
        return 0
    fi
    if ! cmp -s "$from" "$to" 2>/dev/null; then
        mkdir -p "$(dirname "$to")"
        install -m 600 "$from" "$to"
        printf '  copied the login key from %s\n' "$from"
    fi
}

# Everything under dev/ belongs to the user the dev world runs as: the running engine writes saves and
# databases, and its file watcher rebuilds packs in both checkouts. This script runs as root.
chown_dev() {
    local user
    user=$(systemctl show -p User --value "$DEV_SERVICE" 2>/dev/null || true)
    if [ -n "$user" ] && [ "$user" != "root" ]; then
        chown -R "$user:" "$DEV_ROOT"
    fi
}

# SYSTEMD BEATS THE .env, and that is not obvious from either file. The engine reads its
# configuration with plain dotenv (Engine-TS src/util/Environment.ts, `import 'dotenv/config'`),
# and dotenv does NOT overwrite a variable that is already in the environment. The dev unit is a
# copy of live's, so every Environment= line live carries arrives in dev and silently wins over
# dev/engine/.env - which cannot be fixed by editing that file, because nothing is wrong with it.
#
# That is how the dev world ran with NODE_PRODUCTION=true while its own .env said false
# (found 2026-09-29, when the fuzzing bots refused to start on it and said why). Nothing else
# announced it: dev had quietly lost the developer commands and the content file-watcher too.
#
# Two defences. New units are written without those lines at all (see the grep -vE below). Units
# written before this - or written by hand, or by a future change to live's unit - are pinned
# back to dev's own values here, in a drop-in, which systemd reads after the unit and which
# therefore wins. It runs on every --dev-setup AND every --dev, so a change to live's unit is
# caught the next time dev is touched rather than whenever somebody happens to notice.
dev_unit_env_guard() {
    [ -f "$DEV_UNIT" ] || return 0
    local env=$DEV_ROOT/engine/.env pinned='' line key want
    if grep -qE "^EnvironmentFile=.*$LIVE_ENGINE(/|\$)" "$DEV_UNIT"; then
        die "$DEV_UNIT reads live's .env (EnvironmentFile) - dev would take live's ports and profile. Point it at $DEV_ROOT/engine/.env"
    fi
    while IFS= read -r line; do
        key=${line#Environment=}
        key=${key%%=*}
        printf '%s' "$key" | grep -qE "^($DEV_OWN_KEYS)\$" || continue
        want=$(env_get "$env" "$key")
        [ -n "$want" ] || die "$DEV_UNIT sets $key, which the dev world must own, but $env does not set it - remove that line from the unit"
        pinned=$pinned$key=$want$'\n'
    done < <(grep '^Environment=' "$DEV_UNIT" 2>/dev/null || true)
    if [ -n "$pinned" ]; then
        mkdir -p "$DEV_DROPIN_DIR"
        {
            printf '# Written by deploy.sh (dev_unit_env_guard). %s sets these itself, and\n' "$DEV_UNIT"
            printf '# systemd Environment= beats dev/engine/.env because dotenv does not overwrite a\n'
            printf '# variable that is already set. These pin dev back to its own values.\n'
            printf '[Service]\n'
            printf '%s' "$pinned" | while IFS= read -r line; do
                [ -n "$line" ] && printf 'Environment=%s\n' "$line"
            done
        } > "$DEV_DROPIN"
        systemctl daemon-reload
        say "Pinned dev's own values over what $DEV_SERVICE inherited from live's unit:"
        printf '%s' "$pinned" | sed 's/^/    /'
        printf '  (the unit itself still sets these - %s overrides it)\n' "$DEV_DROPIN"
    elif [ -f "$DEV_DROPIN" ]; then
        rm -f "$DEV_DROPIN"
        rmdir "$DEV_DROPIN_DIR" 2>/dev/null || true
        systemctl daemon-reload
        printf '  %s is no longer needed - removed\n' "$DEV_DROPIN"
    fi
}


dev_setup() {
    [ "$(id -u)" = 0 ] || die "--dev-setup makes a systemd unit - run it as root"
    [ -d "$LIVE_ENGINE/.git" ] && [ -d "$CONTENT/.git" ] || die "no live checkouts under $ROOT"
    mkdir -p "$DEV_ROOT"

    # 1. the checkouts - cloned from live's (no download), then pointed at GitHub like live's
    # Live's checkouts belong to the service's user, and root's git refuses to clone from a repo it does
    # not own ("detected dubious ownership" - a local clone reads <repo>/.git, a path the entry for the
    # working tree does not cover). Both spellings are trusted, the same way as the dev checkouts below.
    for repo in engine content; do
        for dir in "$ROOT/$repo" "$ROOT/$repo/.git"; do
            git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$dir" \
                || git config --global --add safe.directory "$dir"
        done
    done
    for repo in engine content; do
        if [ -d "$DEV_ROOT/$repo/.git" ]; then
            printf '  %s/%s exists\n' "$DEV_ROOT" "$repo"
            continue
        fi
        say "Cloning $repo into $DEV_ROOT/$repo"
        git clone -q --no-hardlinks --branch "$BRANCH" "$ROOT/$repo" "$DEV_ROOT/$repo"
        git -C "$DEV_ROOT/$repo" remote set-url origin "$(git -C "$ROOT/$repo" remote get-url origin)"
        git -C "$DEV_ROOT/$repo" fetch origin --quiet
    done
    # the checkouts will belong to the service's user, and root's git refuses a repo it does not own
    for repo in engine content; do
        git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$DEV_ROOT/$repo" \
            || git config --global --add safe.directory "$DEV_ROOT/$repo"
    done

    # 2. the engine's dependencies - live's copied if the lockfiles match (no download)
    if [ ! -d "$DEV_ROOT/engine/node_modules" ]; then
        if cmp -s "$LIVE_ENGINE/package-lock.json" "$DEV_ROOT/engine/package-lock.json" && [ -d "$LIVE_ENGINE/node_modules" ]; then
            say "Copying live's node_modules"
            cp -a "$LIVE_ENGINE/node_modules" "$DEV_ROOT/engine/"
        else
            say "Installing engine dependencies"
            (cd "$DEV_ROOT/engine" && npm ci)
        fi
    fi

    # 3. the dev .env - live's, with every value that must differ replaced. Ports are live's plus one.
    local env=$DEV_ROOT/engine/.env
    if [ -f "$env" ]; then
        printf '  %s exists - left as it is\n' "$env"
        # a dev .env written before the Wilderness bots existed: switch them on (dev only)
        if ! grep -qE '^[[:space:]]*NODE_BOTS[[:space:]]*=' "$env"; then
            printf '\n# the Wilderness bots (src/engine/bot) - dev only, never live\nNODE_BOTS=true\n' >> "$env"
            printf '  added NODE_BOTS=true to %s\n' "$env"
        fi
    else
        say "Writing $env from live's"
        local live_env=$LIVE_ENGINE/.env port web mgmt
        port=$(env_get "$live_env" NODE_PORT); port=${port:-43594}
        web=$(env_get "$live_env" WEB_PORT); web=${web:-8888}
        mgmt=$(env_get "$live_env" WEB_MANAGEMENT_PORT); mgmt=${mgmt:-8898}
        local keys=$DEV_OWN_KEYS
        {
            if [ -f "$live_env" ]; then
                printf '# ---- from live (%s) on %s\n' "$live_env" "$(date +%F)"
                tr -d '\r' < "$live_env" | grep -vE "^[[:space:]]*($keys)[[:space:]]*="
                printf '\n'
            fi
            cat <<EOF
# ---- the dev world (deploy.sh --dev-setup). These must differ from live's - leave them here.
# World 2 in the client's friends list (nodeId - 9); the launcher's "Dev world" connects to these ports.
NODE_ID=$DEV_NODE_ID
NODE_PORT=$((port + 1))
WEB_PORT=$((web + 1))
WEB_MANAGEMENT_PORT=$((mgmt + 1))
# own saves (data/players/dev), clans, trading post and discord databases
NODE_PROFILE=dev
# the :: developer commands, and a file watcher that rebuilds when content/ changes
NODE_PRODUCTION=false
# administrators and up only - everyone else is told "This world is full"
NODE_MIN_STAFF_LEVEL=$DEV_MIN_STAFF_LEVEL
# the Wilderness bots (src/engine/bot; ::bots, ::bot spawn ...) - dev only, never live
NODE_BOTS=true
# its own db.sqlite in this directory - accounts are copied in by deploy.sh --dev, never shared
DB_BACKEND=sqlite
LOGIN_SERVER=false
FRIEND_SERVER=false
LOGGER_SERVER=false
EASY_STARTUP=false
BUILD_STARTUP=false
BUILD_SRC_DIR=../content
# a copy of live's key (the client knows only one), refreshed by every deploy.sh --dev
LOGIN_RSA_KEY_PATH=data/config/login-rsa.pem
# no Discord relay: one bot token cannot be logged in twice, and dev's trades are not real
DISCORD_TOKEN=
DISCORD_GUILD_ID=
EOF
        } > "$env"
        chmod 600 "$env"
        if grep -v "^#" "$env" | grep -qE "$LIVE_ENGINE|$CONTENT"; then
            printf '  \033[1;33mthe dev .env still names a path in the live world - check these lines:\033[0m\n'
            grep -nE "$LIVE_ENGINE|$CONTENT" "$env" | grep -v "^[0-9]*:#" | sed 's/^/    /'
        fi
    fi
    sync_dev_key

    # 4. the unit - live's own, pointed at dev/. Whatever live's needs (user, PATH, node) dev has too.
    #    Everything live's unit sets for one of DEV_OWN_KEYS is dropped on the way across, because
    #    systemd's Environment= beats the .env - see dev_unit_env_guard, which catches the ones that
    #    got across before this did.
    if [ -f "$DEV_UNIT" ]; then
        printf '  %s exists - left as it is\n' "$DEV_UNIT"
    else
        say "Writing $DEV_UNIT from $LIVE_SERVICE"
        systemctl cat "$LIVE_SERVICE" \
            | sed -e '/^# /d' -e '/^Alias=/d' -e '/^OOMScoreAdjust=/d' \
                  -e "s#$LIVE_ENGINE#$DEV_ROOT/engine#g" -e "s#$CONTENT#$DEV_ROOT/content#g" \
                  -e 's/^Description=.*/Description=Death Plateau dev world (World 2, staff only)/' \
                  -e '0,/^\[Service\]$/s//[Service]\n# if memory runs out, the kernel kills the dev world before live\nOOMScoreAdjust=500/' \
            | grep -vE "^Environment=($DEV_OWN_KEYS)=" \
            > "$DEV_UNIT.tmp"
        if ! grep -q "^WorkingDirectory=$DEV_ROOT/engine" "$DEV_UNIT.tmp"; then
            rm -f "$DEV_UNIT.tmp"
            die "$LIVE_SERVICE has no WorkingDirectory=$LIVE_ENGINE to point at dev - write $DEV_UNIT by hand (systemctl cat $LIVE_SERVICE is the model)"
        fi
        mv "$DEV_UNIT.tmp" "$DEV_UNIT"
        systemctl daemon-reload
        systemctl enable "$DEV_SERVICE"
        sed 's/^/    /' "$DEV_UNIT"
    fi
    dev_unit_env_guard
    chown_dev

    say "Dev world set up. Build and start it with:  $ROOT/deploy.sh --dev"
    printf '  The first dev build is a clean one (no packs yet) and takes a good while longer than usual.\n'
    printf '  Game port %s, web port %s - see the launcher'"'"'s "Dev world" for how players reach them.\n' \
        "$(env_get "$env" NODE_PORT)" "$(env_get "$env" WEB_PORT)"
}

if [ -n "$DEV_SETUP" ]; then
    dev_setup
    exit 0
fi

if [ -n "$DEV" ]; then
    [ -d "$DEV_ROOT/engine/.git" ] && [ -f "$DEV_UNIT" ] || die "no dev world yet - run: $ROOT/deploy.sh --dev-setup"
    CONTENT=$DEV_ROOT/content
    ENGINE=$DEV_ROOT/engine
    SERVICE=$DEV_SERVICE
    KEEP_BACKUPS=$DEV_KEEP_BACKUPS
    BACKUP_DIR=$DEV_ROOT
    # What the unit exports beats what the .env says, so settle that before reading the .env at all -
    # otherwise these checks pass on a file the running world is not using. See dev_unit_env_guard.
    dev_unit_env_guard
    # the one thing that must never be shared is a port: check dev's .env before anything stops
    for key in NODE_PORT WEB_PORT WEB_MANAGEMENT_PORT; do
        dev_value=$(env_get "$ENGINE/.env" "$key")
        [ -n "$dev_value" ] || die "$ENGINE/.env does not set $key - dev would take live's"
        [ "$dev_value" != "$(env_get "$LIVE_ENGINE/.env" "$key")" ] || die "$ENGINE/.env has live's $key ($dev_value)"
    done
    [ "$(env_get "$ENGINE/.env" NODE_PROFILE)" = dev ] || die "$ENGINE/.env must say NODE_PROFILE=dev"
    PORT=$(env_get "$ENGINE/.env" WEB_MANAGEMENT_PORT)
    printf '\033[1;35m  DEV WORLD: %s (engine %s, content %s) - the live world is not touched\033[0m\n' \
        "$DEV_ROOT" "$ENGINE_BRANCH" "$CONTENT_BRANCH"
fi

# ---------------------------------------------------------------- 1. save backup
# Save format v8 is ONE WAY: once the new engine writes a save, the old engine refuses
# it ("Unsupported save version"). Backing up is not optional and must happen before
# anything else, because a failed build can still leave a restarted server.
say "Backing up player saves"
STAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP=$BACKUP_DIR/players-backup-$STAMP
[ -z "$DEV" ] || mkdir -p "$ENGINE/data/players"   # nobody has played on a new dev world yet
cp -r "$ENGINE/data/players" "$BACKUP"
printf '  %s (%s files)\n' "$BACKUP" "$(find "$BACKUP" -type f | wc -l)"
ls -1dt "$BACKUP_DIR"/players-backup-* 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | while read -r old; do
    printf '  pruning %s\n' "$old"; rm -rf "$old"
done

# ---------------------------------------------------------------- 1b. (dev) stop the dev world
# Before the pull - see the header. With --countdown, the world's own reboot, as live's below.
if [ -n "$DEV" ] && systemctl is-active --quiet "$SERVICE"; then
    if [ -n "$COUNTDOWN" ]; then
        say "Warning the dev world: restart in ${COUNTDOWN}s"
        curl -sS -f -X POST "http://127.0.0.1:${PORT}/reboot?seconds=${COUNTDOWN}" \
            || die "the dev world did not accept the countdown (is one already under way?) - nothing has changed"
        pid=$(systemctl show -p MainPID --value "$SERVICE")
        deadline=$(( $(date +%s) + COUNTDOWN + 120 ))
        while [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; do
            [ "$(date +%s)" -le "$deadline" ] \
                || die "still running two minutes after the countdown - check: journalctl -u $SERVICE -n 50"
            sleep 2
        done
    fi
    # Restart=always may have brought it straight back - stop it for the build either way
    say "Stopping $SERVICE for the build"
    systemctl stop "$SERVICE"
fi

# ---------------------------------------------------------------- 2. pull both repos
# content/ and engine/ are SEPARATE repos. Pushing one does not push the other, and it
# is easy to deploy content while the engine silently stays behind.
say "Updating repositories"

# pack/inv.pack is tracked but a build appends to it, so the server always has a local
# edit that blocks the pull. The committed version is the right one.
if ! git -C "$CONTENT" diff --quiet -- pack/inv.pack 2>/dev/null; then
    printf '  discarding local edit to pack/inv.pack (a build appended to it)\n'
    git -C "$CONTENT" checkout -- pack/inv.pack
fi

# (dev) the dev world's watcher rebuilds into pack/ too, and --branch switches branch: dev's
# checkouts carry nothing of their own, so any local edit to a tracked pack goes, and each repo is
# put on the branch asked for (live's unless --branch said otherwise) before the pull.
if [ -n "$DEV" ]; then
    git -C "$CONTENT" checkout -- pack
    for pair in "$ENGINE:$ENGINE_BRANCH" "$CONTENT:$CONTENT_BRANCH"; do
        repo=${pair%%:*}; want=${pair#*:}
        git -C "$repo" fetch origin "$want" --quiet || die "$repo: no branch $want on GitHub"
        if [ "$(git -C "$repo" rev-parse --abbrev-ref HEAD)" != "$want" ]; then
            git -C "$repo" checkout "$want" 2>/dev/null || git -C "$repo" checkout -b "$want" "origin/$want"
        fi
    done
fi

LOCK_BEFORE=$(git -C "$ENGINE" rev-parse HEAD:package-lock.json 2>/dev/null || echo none)
git -C "$ENGINE"  pull origin "$ENGINE_BRANCH"
git -C "$CONTENT" pull origin "$CONTENT_BRANCH"

# (dev) an engine from before staff-only worlds ignores NODE_MIN_STAFF_LEVEL - and with
# NODE_PRODUCTION=false it would hand every player who logs in the developer commands
if [ -n "$DEV" ] && ! grep -q NODE_MIN_STAFF_LEVEL "$ENGINE/src/util/Environment.ts"; then
    die "engine $ENGINE_BRANCH has no NODE_MIN_STAFF_LEVEL: the dev world would let everybody in, as developers. It is left stopped - deploy a branch that has it."
fi

# A pull that changes the engine's dependencies needs them installed before the build, or the
# server dies at startup on an import (discord.js, when the Discord relay arrived). npm ci only
# when package-lock.json actually changed - it reinstalls everything and takes a minute.
LOCK_AFTER=$(git -C "$ENGINE" rev-parse HEAD:package-lock.json)
if [ "$LOCK_BEFORE" != "$LOCK_AFTER" ] || [ ! -d "$ENGINE/node_modules" ]; then
    say "Engine dependencies changed - installing"
    (cd "$ENGINE" && npm ci)
fi

# The engine running here must exist on GitHub. It has not, twice - commits applied by
# hand on the server are invisible to everyone else and are lost the moment this
# directory is re-cloned.
say "Checking the engine is not ahead of GitHub"
git -C "$ENGINE" fetch origin "$ENGINE_BRANCH" --quiet
AHEAD=$(git -C "$ENGINE" rev-list --count "origin/$ENGINE_BRANCH..HEAD")
if [ "$AHEAD" -gt 0 ]; then
    printf '  \033[1;33mThis engine has %s commit(s) that are NOT on GitHub:\033[0m\n' "$AHEAD"
    git -C "$ENGINE" log --oneline "origin/$ENGINE_BRANCH..HEAD" | sed 's/^/    /'
    if [ -z "$FORCE_ENGINE" ]; then
        die "Push these from whichever machine has them, or re-run with --force-engine.
    From the server itself:  cd $ENGINE && git push origin $ENGINE_BRANCH"
    fi
    printf '  --force-engine given, continuing anyway\n'
fi

# ---------------------------------------------------------------- 3. clear stale packs
# Generated packs are name maps rebuilt from the configs. A stale one silently keeps the
# old name list, and the error it produces names the config value, not the pack - so it
# reads as a data problem. Clearing costs a few seconds; not clearing costs a debug round.
# map.pack / midi.pack / animset.pack are deliberately NOT cleared (media indexes, and
# animset regeneration has a known anim_0 bug). varp.pack is TRACKED - never delete it.
say "Clearing generated packs"
cd "$CONTENT"
rm -f pack/script.pack pack/param.pack pack/category.pack pack/enum.pack \
      pack/struct.pack pack/mesanim.pack pack/dbtable.pack pack/dbrow.pack \
      pack/hunt.pack pack/varn.pack pack/vars.pack

# Trips shouldRebuildInterfacePack()'s mtime check. Without it the server reports
# "World ready" while serving stale interface data.
touch pack/interface.pack

# Trips the outer rebuild gate in app.ts.
rm -f "$ENGINE/data/pack/server/script.dat"

# THE ONE THAT BIT HARDEST. packConfigs() saves each type's SERVER .dat as it goes, but
# only writes the CLIENT config jag at the very end. A build that throws part-way leaves
# the jag permanently behind: the next build sees server/seq.dat is newer than every
# .seq source, skips seq, and reuses the old jag. The client then runs a stale seq table
# and throws ArrayIndexOutOfBounds on any new animation. Deleting it forces a full
# client-config rebuild and costs seconds.
rm -f "$ENGINE/data/pack/client/config"

# ---------------------------------------------------------------- 4. build, then restart
# Chained so a compile error stops the deploy with the live world still up on old code.
# npm run build is its own step; npm start packs as a side effect of booting, which makes
# a content compile error indistinguishable from a failed start.
say "Building"
cd "$ENGINE"
if [ -n "$DEV" ]; then
    npm run build || die "the build failed - the dev world is left stopped. Fix it, push, and run --dev again."

    # dev's own database: made on the first deploy, migrated on every one (idempotent), and given
    # live's staff accounts - the only way anybody can log in to a staff-only world
    say "Dev database: migrations and staff accounts"
    CHECKPOINT_DISABLE=1 npm run sqlite:migrate
    if [ -f "$LIVE_ENGINE/db.sqlite" ]; then
        # the level: dev .env's NODE_MIN_STAFF_LEVEL (3 if that is 0)
        # and their live characters, where dev has none of its own yet (--resync-saves: over dev's)
        LIVE_PROFILE=$(env_get "$LIVE_ENGINE/.env" NODE_PROFILE); LIVE_PROFILE=${LIVE_PROFILE:-main}
        npx tsx tools/server/copy-staff.ts "$LIVE_ENGINE/db.sqlite" \
            --saves "$LIVE_ENGINE/data/players/$LIVE_PROFILE" ${RESYNC_SAVES:+--refresh-saves}
    else
        printf '  \033[1;33mno %s to copy staff from - nobody can log in until an account is made here:\033[0m\n' "$LIVE_ENGINE/db.sqlite"
        printf '    cd %s && npx tsx tools/server/account.ts set NAME account.staffmodlevel 3\n' "$ENGINE"
    fi
    sync_dev_key
    chown_dev

    say "Starting $SERVICE"
    systemctl start "$SERVICE"

    say "Deployed the dev world. Tailing its log - Ctrl-C to stop (the server keeps running)."
    exec journalctl -u "$SERVICE" -f
fi
npm run build

# systemctl, never a manual npm start - that starts a second unsupervised world that
# collides on port 43594 and dies with the SSH session.
if [ -n "$COUNTDOWN" ] && systemctl is-active --quiet "$SERVICE"; then
    # The world's own reboot (engine/src/web.ts, POST /reboot, this machine only): the "System update
    # in" countdown, then every player saved and a clean shutdown - restart.sh's way. systemd's
    # Restart=always, or the start below, brings it back on what was just built.
    say "Warning players: restart in ${COUNTDOWN}s"
    curl -sS -f -X POST "http://127.0.0.1:${PORT}/reboot?seconds=${COUNTDOWN}" \
        || die "the server did not accept the countdown (is one already under way?) - the build is done; restart with: systemctl restart $SERVICE"
    say "Waiting for the world to save and shut down"
    # the process, not the unit: with Restart=always the unit can be back before is-active is asked
    pid=$(systemctl show -p MainPID --value "$SERVICE")
    deadline=$(( $(date +%s) + COUNTDOWN + 120 ))
    while [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; do
        [ "$(date +%s)" -le "$deadline" ] \
            || die "still running two minutes after the countdown - check: journalctl -u $SERVICE -n 50"
        sleep 2
    done
    systemctl is-active --quiet "$SERVICE" || systemctl start "$SERVICE"
else
    say "Restarting $SERVICE"
    systemctl restart "$SERVICE"
fi

say "Deployed. Tailing the log - Ctrl-C to stop (the server keeps running)."
journalctl -u "$SERVICE" -f
