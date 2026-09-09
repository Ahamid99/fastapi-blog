# FastAPI Blog

A blogging application built with FastAPI, SQLAlchemy 2.0 and an async SQLite backend. It started as a way for me to learn how a real backend fits together, so instead of stopping at a handful of JSON endpoints I went ahead and gave it a working frontend too: server rendered Jinja templates for the pages, and vanilla JavaScript that talks to the same REST API a mobile client would use.

Users can register, log in, write and edit posts, upload a profile picture, and reset a forgotten password over email. Everything the browser does goes through the public API, so the API is not a demo bolted on the side, it is the actual application.

## What is in here

**Authentication and accounts**

- Registration and login with JWT bearer tokens
- Passwords hashed with Argon2 through `pwdlib`
- Login is deliberately vague about whether it was the email or the password that was wrong
- Forgot password flow: a single use token is generated, only its SHA256 hash is stored, it expires after an hour, and any leftover tokens for that user are wiped once it is used
- Change password while logged in, which also invalidates outstanding reset tokens
- Ownership checks on every write, so you cannot edit or delete somebody else's post or account

**Posts**

- Full CRUD with both `PUT` and `PATCH` so partial updates do not force the client to resend the whole object
- Pagination with `skip` and `limit`, and a response that reports `total` and `has_more` so the frontend knows when to stop asking
- Posts are eager loaded with their author using `selectinload`, which keeps the list views off the N+1 query path

**Profile pictures**

- Uploads are validated, size capped, resized to a 300x300 square and re encoded to JPEG with Pillow
- EXIF orientation is corrected, otherwise phone photos come out sideways
- Image processing is CPU bound, so it is pushed to a threadpool with `run_in_threadpool` instead of blocking the event loop
- The old file on disk is deleted after the new one is committed, not before

**Email**

- Password reset emails are sent asynchronously with `aiosmtplib`
- Both an HTML version, rendered from a Jinja template, and a plain text fallback
- Sending happens in a `BackgroundTasks` job so the request returns immediately

**Everything else**

- Async all the way down: `aiosqlite`, async sessions, async route handlers
- Settings loaded and validated by `pydantic-settings`, with secrets wrapped in `SecretStr` so they do not show up in logs or tracebacks
- Custom exception handlers that return JSON for `/api` routes and a rendered error page for everything else
- A seed script that drives the real API with `httpx` to create users, posts and uploads, so the sample data goes through the same validation as anything else

## Stack

Python 3.13, FastAPI, SQLAlchemy 2.0 with the async engine, SQLite via aiosqlite, Pydantic v2, PyJWT, pwdlib with Argon2, Pillow, aiosmtplib, Jinja2. Dependencies and the lockfile are managed with `uv`.

## Project layout

```
main.py           app setup, HTML page routes, error handlers
config.py         settings loaded from .env
database.py       async engine, session factory, Base
models.py         User, Post, PasswordResetToken
schemas.py        Pydantic request and response models
auth.py           hashing, JWT creation and verification, current user dependency
email_utils.py    SMTP sending and the password reset email
image_utils.py    profile picture processing and cleanup
routers/
  users.py        user, auth and password endpoints
  posts.py        post endpoints
templates/        Jinja pages plus the email template
static/           CSS, JavaScript, icons
populatedb.py     seed script
```

## Running it locally

You need Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
git clone <your repo url>
cd fastapi_blog
uv sync
```

Copy the example environment file and fill it in:

```bash
cp .env.example .env
```

At minimum you need a `SECRET_KEY`. Generate one with:

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

The mail settings are optional. Without them the app runs fine, the password reset email just fails to send. For local testing any SMTP catcher such as Mailpit or Mailtrap works.

Start the server:

```bash
uv run fastapi dev main.py
```

The site is at `http://localhost:8000` and the interactive API docs are at `http://localhost:8000/docs`. Tables are created on startup, so there is no migration step yet.

To load sample content, leave the server running and in a second terminal:

```bash
uv run python populatedb.py
```

That wipes the existing data and recreates six users and a set of posts. The seeded accounts all use throwaway credentials that are listed in the script.

## API overview

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/users` | Register |
| POST | `/api/users/token` | Log in, returns a JWT |
| GET | `/api/users/me` | Current user |
| POST | `/api/users/forgot-password` | Request a reset link |
| POST | `/api/users/reset-password` | Reset using the token |
| PATCH | `/api/users/me/password` | Change password while logged in |
| GET | `/api/users/{id}` | Public profile |
| PATCH | `/api/users/{id}` | Update username or email |
| DELETE | `/api/users/{id}` | Delete account |
| GET | `/api/users/{id}/posts` | That user's posts, paginated |
| PATCH | `/api/users/{id}/picture` | Upload a profile picture |
| DELETE | `/api/users/{id}/picture` | Remove it |
| GET | `/api/posts` | All posts, paginated |
| POST | `/api/posts` | Create a post |
| GET | `/api/posts/{id}` | One post |
| PUT | `/api/posts/{id}` | Replace a post |
| PATCH | `/api/posts/{id}` | Update part of a post |
| DELETE | `/api/posts/{id}` | Delete a post |

## Things I would do next

- A real test suite with pytest and httpx
- Alembic for migrations instead of creating tables at startup
- Postgres instead of SQLite once concurrent writes actually matter
- Rate limiting on login and the forgot password endpoint
- Comments and likes
- Docker and a deployment somewhere public

## Notes

The database file is intentionally not committed. It is created the first time you run the app. The `.env` file is not committed either, which is why `.env.example` exists.
