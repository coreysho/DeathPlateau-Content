#!/bin/sh
# Launch day, in order - and where the box says you are in it.
#
#   ./launch-day.sh              the sequence, with what this box reports about each step
#   ./launch-day.sh --quick      ...without the wipe's dry run, which is the slow part
#
# IT CHANGES NOTHING. Every command it runs itself is a read: a git branch, a count of rows, a
# listing of a backup directory, and the wipe's OWN DRY RUN, which prints what it would do and then
# says "Nothing was changed." The steps that act are printed for you to run, never run from here. A
# launch has one irreversible step in the middle of it, and a script that offers to do the whole
# thing unattended is a script that will one day wipe a world nobody meant to wipe.
#
# WHY THE ORDER IS THIS ORDER, which is the part worth reading once before the day:
#
#   the backup goes first        Everything after it is recoverable except the wipe.
#                                backup-offsite.sh takes the four things nothing else protects -
#                                the trading post, the clans, the vote ledger, and login-rsa.pem,
#                                whose modulus is baked into every released client - and puts them
#                                on another machine. The wipe takes its own backups, onto the disk
#                                it is protecting.
#
#   the deploy goes before       The wipe reads every character's save to count the vote points it
#   the wipe                     carries over, and reading a save needs data/pack. It also needs
#                                the schema the deploy migrates to: it checks its tables first and
#                                refuses on an old one, rather than reporting "0 rows" for a table
#                                that is not there. So the code and the packs have to be the launch
#                                ones before anything is cleared.
#
#   the world comes down         The wipe refuses while anybody is logged in, and it is right to:
#   between them                 the server holds a character in memory and writes the file at
#                                logout, so a save taken away underneath a live player comes
#                                straight back at the next logout. deploy.sh ENDS by restarting the
#                                world, so the stop is a step after it, not before.
#
#   the website goes last        A successful web deploy publishes the news post and announces it to
#                                Discord in the same run. The post says the trading post feeds
#                                Discord and that the boards start empty, and both are claims about
#                                an engine that has to be deployed and restarted first. Publish
#                                before that and the notes are briefly wrong.
#
#   the veteran grant has        It writes one column, read at login, and nothing in it reads a live
#   no place in the order        character - so it is safe with the world up, and correct before the
#                                wipe, straight after it, or in a week. It qualifies people by their
#                                save file, and the wipe MOVES saves to wiped-<stamp>/ rather than
#                                deleting them, so the wipe itself produces the roster it reads. It
#                                only ever grants.
#
# WHAT IS NOT HERE: anything the CI already answers. Both repos build, pack, lint and sim on every
# push, and the build runs CacheCheck at the end of every run - that is the corrupt-pack fault which
# shows up as a client stuck at 30% on "Connection error". If GitHub is green on 377-wip, the code
# is not the thing to worry about on the day.
set -u

QUICK=0
for a in "$@"; do
    case "$a" in
        --quick) QUICK=1 ;;
        *) echo "launch-day: unknown option $a" >&2; exit 2 ;;
    esac
done

# /opt/deathplateau and deathplateau.service since the server was named (2026-09-23); a box not yet
# moved over still has /opt/lostcity and lostcity.service. Same two fallbacks deploy.sh uses.
ROOT=${DP_ROOT:-/opt/deathplateau}
[ -d "$ROOT" ] || ROOT=/opt/lostcity
CONTENT=$ROOT/content
ENGINE=$ROOT/engine
WEB=$ROOT/web
PROFILE=${NODE_PROFILE:-main}
SERVICE=deathplateau.service
systemctl cat "$SERVICE" >/dev/null 2>&1 || SERVICE=lostcity.service

step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
cmd()  { printf '    \033[36m%s\033[0m\n' "$*"; }
note() { printf '      %s\n' "$*"; }

printf '\033[1mDeath Plateau - launch day\033[0m   (%s, profile %s, %s)\n' "$ROOT" "$PROFILE" "$SERVICE"
printf 'Nothing here acts. The commands are printed for you to run.\n'

# ---------------------------------------------------------------- before the day

step "0. Before the day. None of this is launch-day work, and all of it wants doing early"

cmd "cd $ENGINE && sh tools/server/rehearse-wipe.sh"
note "The real wipe against a consistent copy of the live data, with the world still up."
note "The only thing that proves the wipe against YOUR data rather than against a fixture."

cmd "cd $ROOT && ./deploy.sh --dev"
note "Builds the launch branch into World 2 - staff only, its own saves and database."
note "Play a fresh character there before doing it on the world people are watching."

cmd "cd $ENGINE && npx tsx tools/server/veteran.ts --list"
note "A read. Names the roster the grant would give the rank to, while there is still time"
note "to disagree with it."

for pair in "$CONTENT:content" "$ENGINE:engine" "$WEB:web"; do
    dir=${pair%:*}
    what=${pair#*:}
    if [ -d "$dir/.git" ]; then
        branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
        tip=$(git -C "$dir" log --oneline -1 2>/dev/null)
        dirty=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
        note "$what: $branch, $dirty local change(s), at $tip"
    else
        note "$what: no checkout at $dir"
    fi
done
note "green on 377-wip? github.com/coreysho/DeathPlateau-Content/actions"
note "                  github.com/coreysho/DeathPlateau-Engine/actions"

# ---------------------------------------------------------------- the day itself

step "1. Everything that cannot be rebuilt, off the box"
cmd "cd $ENGINE && sh tools/server/backup-offsite.sh"
for d in /var/backups/dp-offsite /var/backups/dp-players; do
    if [ -d "$d" ]; then
        newest=$(ls -1t "$d" 2>/dev/null | head -1)
        note "$d: ${newest:-empty}"
    else
        note "$d: not there yet"
    fi
done

step "2. The launch build, with players warned first"
cmd "cd $ROOT && ./deploy.sh --countdown=300"
note "Pulls 377-wip in BOTH repos, builds, migrates the database, restarts the world. The"
note "build runs while the world is still up on the old code and the timer starts only once"
note "it has succeeded, so a build that fails leaves people playing, unwarned and unharmed."

step "3. The world down, because the wipe will not run otherwise"
cmd "systemctl stop $SERVICE"
if command -v systemctl > /dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE"; then note "now: UP"; else note "now: down"; fi
fi

# IS THERE A SECOND PROCESS? With LOGIN_SERVER=true and EASY_STARTUP unset, app.ts does NOT
# spawn the login worker in-process - the engine talks over a socket to a login server that
# was started separately, and deploy.sh knows of no unit but the world and dev.
#
# Why that matters today rather than in general. LoginServer loads data/pack in its
# CONSTRUCTOR - InvType and VarPlayerType - and updateHiscores in that process reads varps by
# NAME. A login server left running across a deploy keeps the pack it started with, and the
# comment at that load says what happens when the ids no longer line up: every figure it
# writes is skipped in silence. It also reads and writes save files directly, which is the
# other half of what the wipe is moving.
#
# These two are booleans, not secrets, so they are printed as read.
if [ -f "$ENGINE/.env" ]; then
    login=$(grep -E "^[[:space:]]*LOGIN_SERVER=" "$ENGINE/.env" 2>/dev/null | head -1 | cut -d= -f2-)
    easy=$(grep -E "^[[:space:]]*EASY_STARTUP=" "$ENGINE/.env" 2>/dev/null | head -1 | cut -d= -f2-)
    note "LOGIN_SERVER=${login:-unset, so false}   EASY_STARTUP=${easy:-unset, so false}"
    case "${login:-}:${easy:-}" in
        true:true)
            note "in-process: the login, friend and logger workers run inside the world, so the"
            note "stop above takes them with it. Nothing more to do." ;;
        true:*)
            note "SEPARATE PROCESS. Stop it for the wipe, and make sure the deploy restarts it -"
            note "otherwise it serves the launch on the pack it held BEFORE the deploy, and"
            note "writes its hiscore figures with the old ids." ;;
        *)
            note "the world runs its own login thread, so there is no second process." ;;
    esac
fi
if command -v systemctl > /dev/null 2>&1; then
    units=$(systemctl list-units --type=service --state=running --no-legend --plain 2>/dev/null | grep -oE "(deathplateau|lostcity)[a-z-]*[.]service" | sort -u | xargs)
    note "running now: ${units:-none that name this server}"
fi

step "4. The wipe. Read the dry run, and decide about --orphans before the day"
cmd "cd $ENGINE && npx tsx tools/server/wipe.ts --profile $PROFILE"
cmd "cd $ENGINE && npx tsx tools/server/wipe.ts --profile $PROFILE --confirm"
note "An orphan save is a character whose account row is gone: unreachable until somebody"
note "registers that username, when the login server hands them whatever is in it. The dry"
note "run counts them, and they are LEFT ALONE unless you add --orphans."
note "Saves move to data/players/$PROFILE/wiped-<stamp>/ and all three databases are backed"
note "up first. Nothing is deleted."

if [ "$QUICK" = "1" ]; then
    note "(--quick: the dry run was not run)"
elif [ -d "$ENGINE" ]; then
    printf '\n'
    note "the wipe's own dry run follows. It changes nothing:"
    printf '\n'
    # CAPTURED, NOT PIPED STRAIGHT INTO sed. A pipeline reports the status of its LAST
    # command, so `wipe.ts | sed` always succeeded and the branch below never ran - which is
    # the one branch that matters, because the dry run REFUSING is the check.
    out=$( cd "$ENGINE" && npx tsx tools/server/wipe.ts --profile "$PROFILE" 2>&1 )
    rc=$?
    sed 's/^/      /' <<INDENTED
$out
INDENTED
    [ "$rc" -eq 0 ] || note "it exited $rc, and that IS the check - read it now, not on the day."
else
    note "no engine checkout at $ENGINE, so there is nothing to dry run here"
fi

step "5. The world back up, and looked at"
cmd "systemctl start $SERVICE"
cmd "journalctl -u $SERVICE -f"
note "Log in once as a player: the character is new, and the clerk owes them their tickets."
note "Then list something at the trading post and watch for the card in Discord. That path"
note "has only ever been proved with tools/market/cardpreview.ts --post, which deliberately"
note "skips the queue, the value threshold, and the hook the game itself fires."
if [ -f "$ENGINE/.env" ]; then
    # NAMES ONLY, NEVER VALUES. A webhook URL is a password - whoever holds it can post to that
    # channel as the server - and a diagnostic that prints one has published it to a terminal, a
    # scrollback, and whatever that terminal is being watched on.
    for name in MARKET_FEED_WEBHOOK MARKET_CARD_ICONS MARKET_FEED_MIN; do
        if grep -qE "^[[:space:]]*$name=." "$ENGINE/.env" 2>/dev/null; then
            note "$name: set"
        else
            note "$name: not set - the feed is off, or the cards come out with an empty slot"
        fi
    done
    # cut, then the quotes dotenv would have stripped: a quoted path read as a missing one.
    icons=$(grep -E "^[[:space:]]*MARKET_CARD_ICONS=" "$ENGINE/.env" 2>/dev/null | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')
    if [ -n "${icons:-}" ] && [ -d "$icons" ]; then
        note "icons: $(ls -1 "$icons" 2>/dev/null | wc -l | tr -d ' ') files in $icons"
    elif [ -n "${icons:-}" ]; then
        note "icons: nothing at $icons, so every card will have an empty slot"
    fi
fi

step "6. The website, which publishes the notes and announces them"
cmd "$WEB/deploy/deploy-web.sh"
note "Pulls, builds, restarts, then posts whatever news has gone up since the last deploy."
note "A failed build leaves the old site running and stops."
if [ -d "$WEB/content/news" ]; then
    latest=$(ls -1t "$WEB/content/news"/*.md 2> /dev/null | head -1)
    if [ -n "${latest:-}" ]; then note "newest post: $(basename "$latest")"; fi
    if [ -f "$WEB/.news-announced" ]; then
        note "announced so far: $(wc -l < "$WEB/.news-announced" 2>/dev/null | tr -d ' ') on record"
    else
        note "no $WEB/.news-announced yet, so the next deploy decides what counts as new"
    fi
fi

step "7. The Veteran rank. Whenever - it is safe with the world up"
cmd "cd $ENGINE && npx tsx tools/server/veteran.ts --profile $PROFILE"
cmd "cd $ENGINE && npx tsx tools/server/veteran.ts --profile $PROFILE --confirm"
note "Qualifies on a save file - live, or in any wiped-* folder - AND a registration before"
note "the cutoff, which is Eastern midnight on November 15 2026. It only ever grants, so"
note "running it again later picks up anybody missed without taking anything back."

printf '\n'
