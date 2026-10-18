# Bookleaf author portal

The author portal reads author and book data from
`frontend/FULLSTACK-SAMPLEDATA (1).json`. Passwords are not stored in that
file. An administrator must provision each author's password through the
protected API before that author can sign in.

## Configure and start

Set a private bootstrap token before starting the API. For local PowerShell:

```powershell
$env:AUTHOR_BOOTSTRAP_TOKEN = "replace-with-a-long-random-secret"
$env:AUTH_COOKIE_SECURE = "false"
uvicorn main:app --reload --port 8000
```

`AUTH_COOKIE_SECURE` defaults to `true`; set it to `false` only for local
development over plain HTTP. Optionally set `AUTHOR_DATA_PATH` or
`AUTH_DATABASE_PATH` to use different file locations.

Support requests, attachments, categories, and priorities are stored in SQLite
in `backend/support_requests.db`. The `categories` and `priorities` tables are
seeded from the `Category` and `Priority` enums, and each support request
references its classification through foreign keys. Tables are created
automatically when the API starts. Set `SUPPORT_DATABASE_PATH` to use a
different database file.

`GET /api/support-requests` returns all support tickets and requires HTTP Basic
authentication for `abhaysingh480shiv@gmail.com`. Set `ADMIN_PASSWORD` in the
backend environment before starting the API; the password is verified by the
server and is not embedded in the frontend.

## Provision an author password

Send an administrator-only request to `POST /api/auth/provision`, using the
author's email from the sample data and a unique password of at least 12
characters:

```powershell
$headers = @{ "X-Bootstrap-Token" = $env:AUTHOR_BOOTSTRAP_TOKEN }
$body = @{
  email = "author@example.com"
  password = "use-a-unique-password-of-at-least-12-characters"
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/auth/provision `
  -Headers $headers -ContentType "application/json" -Body $body
```

The database stores a salted scrypt password hash, not the password. Authors
sign in through `POST /api/auth/login`; the API sets an HTTP-only session
cookie. `GET /api/auth/author-data` uses that session to return only the
signed-in author's profile and books in an `author` property.
`GET /api/auth/me` is an alias that returns the same response. The browser
never chooses an author ID for these lookups.
