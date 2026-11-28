# DeathPlateau Content

Game content for DeathPlateau: RuneScript (`.rs2`), configs, maps, models and client assets.
The sibling repo DeathPlateau-Engine packs and runs it; bugs and decisions live on DeathPlateau-Bugs.

## Working rules (all DeathPlateau repos)

- Write a short plain-language TLDR for the owner at the top of every PR and report.
- Game behaviour follows 2006 RuneScape where it is documented; otherwise follow Old School.
  Say which source you used in the PR.
- Merge order across repos: Content, then Engine, then Client.
- Merge a PR only when every check is green. Never skip, disable or loosen a check to get green.
- Post owner decisions on the tracker issue, first line bold and verbatim:
  `**Decision from the owner, 24 Nov 2026: "<owner's words>"**`
- Claim a tracker issue with the `claude-working` label before working it; remove it when you stop.
- Use subagents for read-heavy sweeps.

## Layout

- `scripts/` is grouped by feature (`skill_*`, `quests/quest_*`, `areas/area_*`, `shop/`, ...),
  each with its own `configs/` and `scripts/`. Bulk unpacked cache data is in `scripts/_unpack/`.
- `pack/*.pack` map ids to names. `maps/`, `models/`, `sprites/`, etc. are client assets.
- `tools/` holds the checkers, batteries (`*_battery.py`), mutation harnesses and generators.

## Branches

`377-wip` is the integration branch. Branch from it, PR into it. The engine builds against the matching branch.

## Checks

```bash
cd scripts && python ../tools/rs2check.py
python tools/invtransmit.py
python tools/<name>_battery.py
```

Full build, from a sibling Engine checkout that reads this repo as `../content`:

```bash
BUILD_VERIFY=false npm run build
```

After a build: `tools/pouchpacked.py`, `tools/poh_battery.py`, `tools/mutate_labels.py`.
Batteries need `pip install pillow numpy`.

## Pack and generated files

- Add a new pack entry by hand as `<max id + 1>=<name>`. Never renumber or reuse an id.
- Keep `.pack` files sorted by id, LF endings, no blank lines, final newline (rs2check enforces this).
- Every `.ob2` model has a `model.pack` entry, and every entry has a file.
- Never commit the generated packs listed in `.gitignore`.
- Never hand-edit blocks marked `do not hand-edit, regenerate`; rerun the `gen*.py` tool that owns them.

## Conventions

- PR titles are Conventional Commits: `fix(scope): plain-English outcome`.
- Cite tracker issues as `DeathPlateau-Bugs#N` and cross-repo halves as `DeathPlateau-Engine#N`.

## Security

- Read secrets only from environment variables or GitHub secrets. Never write a secret value into code, workflows, PRs, issues or logs.
- Do not add hostnames, IP addresses, server paths or secret names to code, commits, PR text or issues.
- Change `tools/deploy.sh`, `tools/ci-nightly.sh`, `tools/restart.sh` and `tools/launch-day.sh` only when an issue asks for it, and say so in the PR TLDR.
