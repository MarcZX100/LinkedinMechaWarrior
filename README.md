# LinkedinMechaWarrior

A command-line client for LinkedIn, for your own account.

It talks to LinkedIn's internal web API ("Voyager") from inside a real Chromium
browser that keeps your session in a persistent profile. Reading your feed or
your profile takes one command, and everything can be printed as JSON to pipe
into other tools.

> **Warning:** using LinkedIn's internal API goes against LinkedIn's User
> Agreement and can get your account restricted. This tool is built to keep
> usage light and human-paced (see [Staying under the radar](#staying-under-the-radar)),
> but the risk is never zero. Use it on your own account, at your own risk.

## Status

Early (0.2). Working today:

| Command | What it does |
|---|---|
| `auth login / status / logout / forget-password` | Session management |
| `open` | Open LinkedIn in the browser (e.g. to clear a security check) |
| `me` | Your profile |
| `feed` | Your home feed |
| `post draft / preview / compose` | Outline, check and publish posts |
| `api get` | Raw access to any internal API path |
| `capture` | Record the API calls the LinkedIn web app makes, to discover endpoints |
| `limits` | Request budgets and cooldowns |

Next up: notifications, messages, profiles, invitations.

The internal API is undocumented and changes without notice. If a command stops
working, see [When LinkedIn changes something](#when-linkedin-changes-something).

## Install

Download the binary for your platform from the releases page:

- Linux x86_64: `linkedin-cli-linux`
- Windows x86_64: `linkedin-cli.exe`

The binary includes Chromium; there is nothing else to install. On Linux, make it executable once:

```bash
chmod +x linkedin-cli-linux
./linkedin-cli-linux --help
```

Releases built from branches other than `main` are marked as prereleases.

## First use

Log in once. A browser window opens; type your password in the terminal (or use
`--manual` to type everything in the browser):

```bash
linkedin-cli auth login --email you@example.com
```

If LinkedIn asks for 2FA, a captcha or another check, complete it in the
browser window and press Enter in the terminal. The session stays in the
browser profile, so you don't need to log in again until LinkedIn ends it.

Add `--save-password` to store the password in the system keyring (macOS
Keychain, Windows Credential Manager, Secret Service on Linux). It is never
written to a file.

## Usage

```bash
linkedin-cli auth status          # are we logged in? (one API request)
linkedin-cli me
linkedin-cli feed -n 20           # 1-50 posts
linkedin-cli feed --full          # complete post texts
linkedin-cli feed --json | jq '.[] | {author, url}'
```

Global options work before or after the command:

- `--json`: machine-readable output
- `--headed`: show the browser window for API commands
- `-v` / `--verbose`: debug logs, including every API request

### Posts

```bash
linkedin-cli post draft "What I learned shipping a CLI" --tone technical --length short -o post.txt
# edit post.txt and fill in the [placeholders]
linkedin-cli post preview --text-file post.txt
linkedin-cli post compose --text-file post.txt
```

`post draft` builds an outline offline: a hook, sections to fill in, and a
closing question. Tones: `professional`, `technical`, `casual`, `founder`,
`educational`. Lengths: `short`, `medium`, `long`.

`post compose` refuses text that is empty, too long or still has
`[placeholders]`. It puts the text in LinkedIn's editor and waits. Type
`publish` to publish it, or press Enter and finish in the browser yourself.

## Staying under the radar

Restrictions are mostly triggered by volume, by machine-like regularity, and by
requests that don't look like they come from a real browser. So:

- **Requests come from the browser itself.** API calls are `fetch()` calls made
  from a linkedin.com page in your persistent Chromium profile, with its real
  cookies, headers and fingerprint. In headless mode, the "HeadlessChrome"
  markers in the User-Agent and client hints are removed, and
  `navigator.webdriver` is off.
- **No page load burst.** Commands don't load the LinkedIn web app; only the
  API calls you asked for are sent.
- **Randomized pacing.** Each request waits a random 2-6 s after the previous
  one, sometimes longer, also across separate commands.
- **Budgets.** At most 60 requests per hour and 300 per 24 h by default.
  `linkedin-cli limits` shows the current usage.
- **Back off when LinkedIn pushes back.** A security challenge pauses all
  requests for 6 h; HTTP 429/999 pauses them for 1 h. Check the account with
  `linkedin-cli open`, then lift the pause with `linkedin-cli limits --clear-cooldown`.
- **No automatic re-login.** An expired session is reported, never fixed
  behind your back. Logging in again and again is a red flag for LinkedIn.
- **No bulk features.** No mass profile views, search scraping, or bulk
  invitations or messages, by design.

Also avoid running it from datacenter or VPN IP addresses, and be careful with
brand-new accounts.

## Configuration

Nothing is required. Environment variables for advanced use:

| Variable | Default | Meaning |
|---|---|---|
| `HEADLESS` | `true` | Hide the browser for API commands (interactive commands always show it) |
| `REQUEST_MIN_DELAY` / `REQUEST_MAX_DELAY` | `2` / `6` | Seconds between requests (minimum 1) |
| `HOURLY_REQUEST_BUDGET` / `DAILY_REQUEST_BUDGET` | `60` / `300` | Request budgets |
| `DEFAULT_TIMEOUT_MS` | `30000` | Browser and request timeout |
| `MAX_POST_CHARS` | `3000` | Post length limit |
| `LINKEDIN_STATE_DIR` | see below | Where all local data lives |
| `BROWSER_PROFILE_DIR`, `DEBUG_DIR` | inside the state dir | Override single locations |

## Data on your computer

Everything lives in the state directory:

- Linux: `$XDG_STATE_HOME/linkedin-mecha-warrior` (usually `~/.local/state/linkedin-mecha-warrior`)
- Windows: `%LOCALAPPDATA%\LinkedinMechaWarrior`
- macOS: `~/Library/Application Support/LinkedinMechaWarrior`

| Path | Contents |
|---|---|
| `browser-profile/` | The Chromium profile. **Its cookies are your LinkedIn session; protect it like a password.** |
| `request-log.json` | Request timestamps and cooldowns, used for pacing |
| `captures/` | Output of `capture`. Can contain private data such as messages |
| `debug/` | Screenshots of the visible window when a browser flow fails |

`auth logout` deletes the LinkedIn cookies from the profile.

## When LinkedIn changes something

1. `linkedin-cli -v <command>` shows each request and LinkedIn's response status.
2. `linkedin-cli api get /some/path -p key=value` shows the raw JSON of any endpoint.
3. `linkedin-cli capture` opens the browser and records every API call the
   LinkedIn web app makes while you browse (request headers are never saved).
   Open the page whose data you want, press Enter, and read the `.jsonl` file
   to see the current endpoint, parameters and response shape.

That is also how new commands get built: capture what the web app does, then
add the endpoint and a parser in `linkedin_automation/api.py`.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
pytest
```

Tests never contact LinkedIn. The browser integration tests run a real
Chromium against a mocked linkedin.com in which unexpected requests are blocked;
they are skipped when Chromium is not installed.

```text
linkedin_automation/
  cli.py             command-line interface
  voyager.py         internal API client (in-browser fetch, error handling)
  pacing.py          randomized delays, budgets, cooldowns
  api.py             endpoints and response parsers
  normalized.py      helpers for Voyager's normalized JSON
  models.py          Profile, FeedPost
  browser.py         persistent Chromium session, fingerprint fixes
  ui.py              login and post composer flows in the web UI
  capture.py         API traffic recorder
  post_generator.py  offline post outlines
  credentials.py     system keyring
  config.py, runtime.py, output.py, errors.py, utils.py
```

### Building a binary

```bash
pip install -e ".[build]"
python scripts/build_binary.py --clean          # single file, Chromium included
python scripts/build_binary.py --onedir --clean # folder, easier to inspect
```

The binary is written to `dist/`. It contains no passwords, sessions or screenshots.

### Releases

`.github/workflows/release-on-push.yml` builds every pushed commit on Linux and
Windows, runs the tests, and publishes a release tagged
`v<version>-build.<run>.<commit-index>` with `linkedin-cli-linux` and
`linkedin-cli.exe`. Pushes to `main` create regular releases, while pushes to
other branches create prereleases. Only the release job has write access to the
repository.

## License

MIT
