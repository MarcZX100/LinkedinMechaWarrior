# LinkedinMechaWarrior

A command-line client for LinkedIn, for your own account. The command is
`lmw`, short for **L**inkedin**M**echa**W**arrior.

`lmw` talks to LinkedIn's internal web API ("Voyager") with plain HTTP
requests. There is no browser automation: requests carry the same TLS
fingerprint and headers as a real desktop browser, the session comes from
the browser you already use, and usage is kept light and irregular.

> **Warning:** using LinkedIn's internal API goes against LinkedIn's User
> Agreement and can get your account restricted. `lmw` is built to keep usage
> light and human-paced (see [Staying under the radar](#staying-under-the-radar)),
> but the risk is never zero. Use it on your own account, at your own risk.

## Status

| Command | What it does |
|---|---|
| `auth import / status / logout` | Reuse the session from your browser, check it, remove it |
| `me` | Your profile |
| `feed` | Your home feed |
| `post draft / preview` | Outline and check posts, offline |
| `post publish` | Publish a text post (**not yet verified against LinkedIn**) |
| `api get` | Raw access to any internal API path |
| `har inspect` | List the API calls in a HAR file recorded in your browser |
| `identity show / import / reset` | Which browser `lmw` presents itself as |
| `limits` | Request budgets and cooldowns |

Next up: notifications, messages, profiles, invitations.

The internal API is undocumented and changes without notice. The endpoints in
use (`/me`, `/feed/updatesV2`, `/contentcreation/normShares`) come from
community knowledge and have not been verified against a live account yet. If
a command fails, see [When LinkedIn changes something](#when-linkedin-changes-something).

## Install

Download the binary for your platform from the releases page:

- Linux x86_64: `lmw-linux`
- Windows x86_64: `lmw.exe`

It is a single static file; there is nothing else to install. On Linux, make
it executable once:

```bash
chmod +x lmw-linux
./lmw-linux --help
```

With Go installed, you can also build it yourself (any OS, including macOS):

```bash
go install github.com/MarcZX100/LinkedinMechaWarrior/cmd/lmw@latest
```

Releases built from branches other than `main` are marked as prereleases.

## First use

`lmw` never logs in by itself. Log in to LinkedIn in your browser as usual
(including 2FA), then import that session. Pick one:

**From a HAR file (recommended).** This also copies your browser's exact
identity, so `lmw`'s requests look like they come from the same browser.

1. Open LinkedIn in your browser and open the developer tools, Network tab.
2. Reload the page.
3. Chrome or Edge: right-click the request list > *Save all as HAR (with
   sensitive data)*. Firefox: gear icon > *Save All As HAR*.
4. Import it, then delete the file (it contains your session):

```bash
lmw auth import --har linkedin.har
```

**From the browser's cookie store.** This works well with Firefox. Chrome on
Windows encrypts cookies in a way other programs can't read, and some
browsers lock their cookie database while open, so close the browser first.

```bash
lmw auth import --browser            # any installed browser, newest session wins
lmw auth import --browser firefox
```

**By pasting the cookies.** Copy `li_at` and `JSESSIONID` from the developer
tools (Application > Cookies, or Storage in Firefox):

```bash
lmw auth import
```

The session is checked with one API request, then stored in the system
keyring (macOS Keychain, Windows Credential Manager, Secret Service on Linux),
or in a file only you can read if there is no keyring.

## Usage

```bash
lmw auth status          # is the session valid? (one API request)
lmw me
lmw feed -n 20           # 1-50 posts
lmw feed --full          # complete post texts
lmw feed --json | jq '.[] | {author, url}'
```

Global options: `--json` for machine-readable output, `-v` / `--verbose` for
debug logs, including every request.

### Posts

```bash
lmw post draft What I learned shipping a CLI --tone technical --length short -o post.txt
# edit post.txt and fill in the [placeholders]
lmw post preview --text-file post.txt
lmw post publish --text-file post.txt
```

`post draft` builds an outline offline: a hook, sections to fill in, and a
closing question. Tones: `professional`, `technical`, `casual`, `founder`,
`educational`. Lengths: `short`, `medium`, `long`.

`post publish` refuses text that is empty, too long or still has
`[placeholders]`, shows the post and publishes it only after you type
`publish`. Add `--connections-only` to limit who can see it.

## Staying under the radar

Restrictions are mostly triggered by volume, by machine-like regularity, and
by requests that don't look like they come from a real browser. So:

- **Real browser fingerprint.** Requests go through
  [tls-client](https://github.com/bogdanfinn/tls-client), whose TLS (JA4) and
  HTTP/2 fingerprints match Chrome's. The User-Agent and client hints
  (`sec-ch-ua`, generated with Chrome's own algorithm) agree with that
  fingerprint. `lmw identity show` displays what is sent.
- **Your browser's session.** You log in with your browser, on your network,
  with your 2FA. `lmw` reuses that session and never logs in, so there are no
  repeated logins from an unknown client.
- **Randomized pacing.** Each request waits a random 2-6 s after the previous
  one, sometimes longer, also across separate commands.
- **Budgets.** At most 60 requests per hour and 300 per 24 h by default.
  `lmw limits` shows the current usage.
- **Back off when LinkedIn pushes back.** A security challenge pauses all
  requests for 6 h; HTTP 429/999 pauses them for 1 h. Check the account in
  your browser, then lift the pause with `lmw limits --clear-cooldown`.
- **Session changes are followed.** Cookies that LinkedIn refreshes are saved;
  if LinkedIn ends the session, `lmw` drops it and asks you to import again.
- **No bulk features.** No mass profile views, search scraping, or bulk
  invitations or messages, by design.

Also avoid running it from datacenter or VPN IP addresses (use the same
network as your browser), and be careful with brand-new accounts.

## Configuration

Nothing is required. Environment variables for advanced use:

| Variable | Default | Meaning |
|---|---|---|
| `LMW_REQUEST_MIN_DELAY` / `LMW_REQUEST_MAX_DELAY` | `2` / `6` | Seconds between requests (minimum 1) |
| `LMW_HOURLY_REQUEST_BUDGET` / `LMW_DAILY_REQUEST_BUDGET` | `60` / `300` | Request budgets |
| `LMW_REQUEST_TIMEOUT` | `30` | Request timeout in seconds |
| `LMW_MAX_POST_CHARS` | `3000` | Post length limit |
| `LMW_SESSION_STORE` | `auto` | `keyring`, `file`, or `auto` (keyring, falling back to a file) |
| `LMW_STATE_DIR` | see below | Where local data lives |

## Data on your computer

Local data lives in the state directory:

- Linux: `$XDG_STATE_HOME/linkedin-mecha-warrior` (usually `~/.local/state/linkedin-mecha-warrior`)
- Windows: `%LOCALAPPDATA%\LinkedinMechaWarrior`
- macOS: `~/Library/Application Support/LinkedinMechaWarrior`

| Item | Contents |
|---|---|
| System keyring, or `session.json` | Your LinkedIn session cookies. **Treat them like a password.** |
| `identity.json` | The browser identity imported from a HAR file, if any |
| `request-log.json` | Request timestamps and cooldowns, used for pacing |

`lmw auth logout` removes the stored session. It stays valid on LinkedIn
until you log out in your browser.

## When LinkedIn changes something

1. `lmw -v <command>` shows each request and LinkedIn's response status.
2. `lmw api get /some/path -p key=value` shows the raw JSON of any endpoint.
3. Record a HAR in your browser while visiting the page whose data you want,
   then `lmw har inspect linkedin.har` lists the API calls the web app made
   (endpoint, parameters, entity types in the response), and
   `lmw har inspect linkedin.har --show INDEX` prints one of them.

That is also how new commands get built: see what the web app calls, then add
the endpoint and a parser in `internal/api`.

## Development

Requires Go (see `go.mod` for the version).

```bash
go test ./...
go build -o lmw ./cmd/lmw
CGO_ENABLED=0 GOOS=windows go build -o lmw.exe ./cmd/lmw   # cross-compile
```

Tests never contact LinkedIn: they use fake transports, a local HTTPS server
for the real TLS stack, and a Firefox cookie database fixture.

```text
cmd/lmw/           entry point
internal/
  cli/             commands
  voyager/         API client: TLS fingerprint, headers, cookies, error handling
  pacing/          randomized delays, budgets, cooldowns
  api/             endpoints and response parsers
  normalized/      helpers for Voyager's normalized JSON
  identity/        browser identity (User-Agent, client hints, header order)
  session/         session cookies in the keyring or a private file
  auth/            session import from installed browsers
  har/             HAR file reading
  postgen/         offline post outlines and validation
  config/, output/, errs/, version/
```

### Releases

`.github/workflows/release-on-push.yml` builds every pushed commit on Linux and
Windows, runs the tests, and publishes a release tagged
`v<version>-build.<run>.<commit-index>` with `lmw-linux` and `lmw.exe`. Pushes
to `main` create regular releases, while pushes to other branches create
prereleases. Only the release job has write access to the repository. The
version lives in `internal/version/version.go`.

## License

MIT
