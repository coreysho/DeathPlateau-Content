#!/usr/bin/env bash
# Start the client's nightly mutation run from this box, because GitHub's own clock does not.
#
# The 25 mutation suites take about 40 minutes across 25 runners and exist to catch rot: a check
# that has quietly stopped CATCHING, which no amount of pushing will reveal. They were set to run
# at 07:00 UTC. The first two nights they started at 14:44 and 14:56 - near eight hours late, both
# times, and within twelve minutes of each other, which is a saturated queue rather than bad luck.
# GitHub queues scheduled workflows platform-wide and behind paid work, and every hand-written cron
# in the world sits on the hour. A run that lands mid-afternoon is still a run, but it is not a
# nightly: the point was an answer waiting in the morning.
#
# So the schedule moved here. This box is always on - it IS the game - and a workflow_dispatch is
# served immediately, whatever the queue is doing, because it is a request and not a cron. The
# workflow keeps its workflow_dispatch trigger and has no schedule of its own any more; if both
# existed we would get two 40-minute runs a day and a question about which one was real.
#
#   ./ci-nightly.sh              dispatch it now (what the timer runs)
#   ./ci-nightly.sh --check      say what the last run did, and dispatch nothing
#   ./ci-nightly.sh --install    as root, once: write and enable the systemd timer
#
# It needs a token, because a dispatch is a write. A fine-grained personal access token with
# Actions: Read and write on coreysho/DeathPlateau-Client, in a root-only file:
#
#   install -d -m 700 /etc/deathplateau
#   install -m 600 /dev/null /etc/deathplateau/ci-nightly.token
#   nano /etc/deathplateau/ci-nightly.token        # paste the token, nothing else
#
# WHAT IS LOST by moving the schedule off GitHub: if this box is down at 07:37 UTC there is no
# nightly. Persistent=true in the timer covers a reboot - systemd runs the missed one when it comes
# back - but a box that is down for a day misses a day. The box being down is a bigger problem than
# the nightly by then, so this is a trade worth making rather than a risk being ignored.
#
# The result is not read here. The run takes 40 minutes; this script starts it and goes away, and
# the NEXT night's dispatch prints what the last one did, so journalctl -u deathplateau-ci-nightly
# reads as a diary. For the real thing, in colour, with the failing suite named:
#
#   https://github.com/coreysho/DeathPlateau-Client/actions/workflows/mutations-nightly.yaml
set -u

REPO=${DP_CI_REPO:-coreysho/DeathPlateau-Client}
WORKFLOW=${DP_CI_WORKFLOW:-mutations-nightly.yaml}
REF=${DP_CI_REF:-dev-logging}
TOKEN_FILE=${DP_CI_TOKEN_FILE:-/etc/deathplateau/ci-nightly.token}

SERVICE=deathplateau-ci-nightly
# Overridable so --install can be rehearsed against a temp directory: the units are the one part of
# this script that a machine without systemd cannot try, and unread unit text is how a timer comes
# to never fire. On the box this is the default and nothing passes it.
UNIT_DIR=${DP_CI_UNIT_DIR:-/etc/systemd/system}
UNIT=$UNIT_DIR/$SERVICE.service
TIMER=$UNIT_DIR/$SERVICE.timer
# 07:37 and not 07:00, for the reason in the header. UTC spelled out, so this does not move with
# the box's timezone or with a timezone change.
WHEN=${DP_CI_WHEN:-*-*-* 07:37:00 UTC}
API=https://api.github.com/repos/$REPO/actions
PAGE=https://github.com/$REPO/actions/workflows/$WORKFLOW

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m!!! %s\033[0m\n' "$*" >&2; exit 1; }

read_token() {
    [ -r "$TOKEN_FILE" ] || die "no token at $TOKEN_FILE - the header of this script says how to make one"
    TOKEN=$(tr -d ' \t\r\n' < "$TOKEN_FILE")
    [ -n "$TOKEN" ] || die "$TOKEN_FILE is empty"
}

get() {
    curl -sS --max-time 30 \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Accept: application/vnd.github+json' \
        -H 'X-GitHub-Api-Version: 2022-11-28' \
        "$1"
}

# NO jq ON THIS BOX, AND NO NEED FOR ONE. Nothing below pairs two fields of the same run together,
# which is the only thing grepping JSON is actually bad at: "status" and "conclusion" each appear
# once per run, newest first, and a run in progress has `"conclusion": null` - a line that does not
# match `"conclusion": "..."` at all, so pairing the two lists by position would quietly attribute
# last night's verdict to tonight's run. So the statuses are read as a set, and the conclusion is
# read only in the one case where the newest run is the first match: when it has finished.
fetch_runs() {
    RUNS=$(get "$API/workflows/$WORKFLOW/runs?per_page=5") || return 1
    case "$RUNS" in
        *'"workflow_runs"'*) return 0;;
        *) printf 'the run list came back as something else:\n%s\n' "${RUNS:0:400}" >&2; return 1;;
    esac
}

statuses() { printf '%s' "$RUNS" | grep -oE '"status": "[a-z_]*"' | sed 's/.*: "//; s/"$//'; }

# A dispatch while one is already going would queue behind it - the workflow's concurrency group
# waits rather than cancelling - so the second 40-minute run would start the moment the first ended
# and both would show in the list. Refuse instead: a timer that fired twice is not a reason to run
# the suites twice.
busy() { statuses | grep -qv '^completed$'; }

last_word() {
    local first conclusion started
    first=$(statuses | head -1)
    if [ -z "$first" ]; then
        echo 'no runs yet'
        return
    fi
    if [ "$first" != completed ]; then
        printf 'a run is %s already\n' "$first"
        return
    fi
    conclusion=$(printf '%s' "$RUNS" | grep -oE '"conclusion": "[a-z_]*"' | head -1 | sed 's/.*: "//; s/"$//')
    started=$(printf '%s' "$RUNS" | grep -oE '"run_started_at": "[^"]*"' | head -1 | sed 's/.*: "//; s/"$//')
    printf 'the last run %s (started %s)\n' "${conclusion:-finished, verdict unreadable}" "${started:-at an unknown time}"
}

dispatch() {
    local out code body
    out=$(mktemp) || die 'could not make a temporary file'
    code=$(curl -sS --max-time 30 -o "$out" -w '%{http_code}' \
        -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Accept: application/vnd.github+json' \
        -H 'X-GitHub-Api-Version: 2022-11-28' \
        "$API/workflows/$WORKFLOW/dispatches" \
        -d "{\"ref\":\"$REF\"}")
    body=$(cat "$out" 2>/dev/null)
    rm -f "$out"
    [ "$code" = 204 ] && return 0
    # Each of these is something somebody has to go and change, and a bare "it failed" names none
    # of them - so the code, GitHub's own words, and what they mean here.
    printf 'the dispatch was refused with HTTP %s\n%s\n' "$code" "${body:-(no body)}" >&2
    case "$code" in
        401) printf 'that is the token itself - expired, revoked, or mistyped.\n' >&2;;
        403) printf 'the token lacks Actions: Read and write on %s.\n' "$REPO" >&2;;
        404) printf 'either %s is not on the default branch, or ref %s does not exist.\n' "$WORKFLOW" "$REF" >&2;;
        422) printf '%s has no workflow_dispatch trigger to call.\n' "$WORKFLOW" >&2;;
    esac
    return 1
}

install_timer() {
    # Root is wanted because /etc is, so the check asks about the directory rather than assuming.
    case "$UNIT_DIR" in
        /etc/*) [ "$(id -u)" = 0 ] || die "--install writes to $UNIT_DIR - run it as root";;
        *) say "rehearsal: writing to $UNIT_DIR instead of /etc/systemd/system";;
    esac
    [ -d "$UNIT_DIR" ] || die "$UNIT_DIR does not exist"
    local self
    self=$(readlink -f "$0")
    say "Writing $UNIT"
    cat > "$UNIT" <<EOF
[Unit]
Description=Start the client's nightly mutation run on GitHub
Documentation=$PAGE
# Nothing to do without a network, and the whole job is one request.
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$self
# The suites run on GitHub's runners, not here, so this is one HTTPS request and has no business
# taking longer. If it hangs, the night is lost and the next night's line says so.
TimeoutStartSec=120
EOF
    # systemd's own parser, before anything is written: a timezone in OnCalendar needs systemd 240
    # or newer, and an OnCalendar it cannot read does not complain - it just never fires.
    if command -v systemd-analyze >/dev/null 2>&1; then
        systemd-analyze calendar "$WHEN" >/dev/null 2>&1 \
            || die "systemd does not understand the calendar '$WHEN' - too old for a timezone there? Try DP_CI_WHEN='*-*-* 07:37:00'"
        say "systemd reads '$WHEN' as:"
        systemd-analyze calendar "$WHEN" | sed 's/^/    /'
    fi
    say "Writing $TIMER"
    cat > "$TIMER" <<EOF
[Unit]
Description=The client's nightly mutation run, $WHEN
Documentation=$PAGE

[Timer]
OnCalendar=$WHEN
# A box that was off at 07:37 runs it when it comes back, rather than skipping the night.
Persistent=true
Unit=$SERVICE.service

[Install]
WantedBy=timers.target
EOF
    systemctl daemon-reload || die 'systemctl daemon-reload failed'
    systemctl enable --now "$SERVICE.timer" || die "could not enable $SERVICE.timer"
    say 'Enabled. The next run:'
    systemctl list-timers "$SERVICE.timer" --no-pager | sed 's/^/    /'
    printf '\n'
    say "Dispatch one now with: systemctl start $SERVICE.service"
    say "Read the diary with:   journalctl -u $SERVICE"
    if [ ! -r "$TOKEN_FILE" ]; then
        printf '\n\033[1;33m    The timer is set, but there is no token at %s yet, so the first\n' "$TOKEN_FILE"
        printf '    run will fail and say so. The header of this script says how to make one.\033[0m\n'
    fi
}

case "${1:-}" in
    --install) install_timer; exit 0;;
    --check)
        read_token
        fetch_runs || die 'could not read the run list'
        say "$(last_word)"
        printf '%s\n' "$PAGE"
        exit 0;;
    '') ;;
    *) die "unknown option $1 - see the top of this script";;
esac

read_token
fetch_runs || die 'could not read the run list - not dispatching blind'
# The diary line: what last night did, printed by tonight's dispatch.
say "$(last_word)"
if busy; then
    say 'not dispatching - one is already queued or running'
    exit 0
fi
say "Dispatching $WORKFLOW on $REF"
dispatch || die 'nothing was dispatched'
say "On its way. 25 suites, about 40 minutes: $PAGE"
