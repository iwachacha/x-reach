# Troubleshooting

## `twitter status` says unauthenticated

Set cookies again:

```powershell
x-reach configure twitter-cookies "auth_token=...; ct0=..."
twitter status
```

Or re-import from a browser:

```powershell
x-reach configure --from-browser chrome
```

## Browser import fails

- Close the browser first.
- Confirm you are already logged into `x.com`.
- Retry with a supported browser name: `chrome`, `firefox`, `edge`, `brave`, or `opera`.

## `doctor --json --probe` still warns

`twitter status` only proves that the session is authenticated. Twitter/X search can still fail even when profile lookups succeed.

Run targeted checks:

```powershell
x-reach collect --channel twitter --operation user --input "openai" --json
x-reach collect --channel twitter --operation search --input "OpenAI" --limit 1 --json
```

## Raw `twitter --help` fails with `UnicodeEncodeError` on Windows

Run the backend CLI with UTF-8 enabled:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
twitter --help
```

