# LinkedinMechaWarrior

**`lmw`** is a command-line client for your own LinkedIn account: read your
profile and feed, write and publish posts, and explore LinkedIn's internal API.
It is a single static binary for Linux and Windows, with no browser
automation.

```bash
lmw auth import --har linkedin.har   # reuse your browser's LinkedIn session
lmw me                               # Ada Lovelace · Mathematician · ...
lmw feed -n 20                       # your feed in the terminal
lmw feed --json                      # ...or as JSON for other tools
lmw post publish --text-file post.txt  # publish, after you confirm
```

**[Read the documentation →](https://marczx100.github.io/LinkedinMechaWarrior/)** ([also in the repo](docs/README.md))
· [Getting started](docs/getting-started.md) (10 minutes)
· [Command reference](docs/reference/lmw.md)
· [Troubleshooting](docs/troubleshooting.md)

> [!WARNING]
> `lmw` uses LinkedIn's internal web API, which goes against LinkedIn's User
> Agreement and can get your account restricted. It is built to keep usage
> light and human-paced, but the risk is never zero. Use it on your own
> account, at your own risk. See [Stay safe](docs/guides/stay-safe.md).

## Why it is different

- **Plain HTTP that looks like your browser.** Requests use a real browser's
  TLS and HTTP/2 fingerprint (identical JA4 to Chromium), with matching
  User-Agent and client hints. Import a HAR file and it copies your own
  browser's exact headers. [More](docs/guides/browser-identity.md)
- **Never logs in.** It reuses the session of the browser you already use,
  with your 2FA, and stores it in the system keyring. [More](docs/guides/import-session.md)
- **Paced like a person.** Random pauses, hourly and daily request budgets,
  and automatic cooldowns the moment LinkedIn pushes back. [More](docs/guides/stay-safe.md)
- **Easy to extend.** `lmw har inspect` shows what LinkedIn's website calls,
  `lmw api get` reproduces it. [More](docs/guides/extend-lmw.md)

## Install

Download `lmw-linux` or `lmw.exe` from the **Releases** page. That's all; see
[Getting started](docs/getting-started.md#step-1-install-lmw) for details. With
Go installed, on any OS:

```bash
go install github.com/MarcZX100/LinkedinMechaWarrior/cmd/lmw@latest
```

## Status

| Command | What it does |
|---|---|
| `auth import / status / logout` | Reuse your browser's session, check it, remove it |
| `me`, `feed` | Your profile and home feed |
| `post draft / preview / publish` | Outline, check and publish text posts |
| `api get`, `har inspect` | Explore LinkedIn's internal API |
| `identity show / import / reset` | Which browser `lmw` presents itself as |
| `limits` | Request budgets and cooldowns |

The internal API is undocumented and changes without notice. The endpoints in
use come from community knowledge and have not been verified against a live
account yet; `post publish` in particular. Next up: notifications, messages,
profiles, invitations.

## Development

```bash
go test ./...                                        # tests never contact LinkedIn
go build -o lmw ./cmd/lmw
go test ./internal/cli -run TestReference -update    # regenerate docs/reference
```

The documentation website is built from `docs/` with Material for MkDocs and
published to GitHub Pages by `.github/workflows/docs.yml`. To preview it:

```bash
pip install -r .github/docs-requirements.txt
mkdocs serve        # http://127.0.0.1:8000
```

See [How it works](docs/how-it-works.md) and [Extend lmw](docs/guides/extend-lmw.md).
Every pushed commit is built and released by
`.github/workflows/release-on-push.yml`: regular releases from `main`,
prereleases from other branches.

## License

MIT
