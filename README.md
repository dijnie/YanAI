<h1 align="center">YanAI</h1>

<p align="center">YanAI is a self-hosted image creation and management system built around ChatGPT's image capabilities. It provides an OpenAI-compatible image API, an online drawing workbench, image-to-image presets, account pool rotation, personal user quotas, channel management, model management, pricing configuration, image archiving, logging, and Docker deployment.</p>

> [!WARNING]
> Disclaimer:
>
> This project involves reverse engineering of the ChatGPT website's text generation, image generation, and image editing APIs. It is intended solely for personal learning, technical research, and non-commercial technical exchange.
>
> - It is strictly forbidden to use this project for any commercial purpose, for-profit use, bulk operations, automated abuse, or large-scale invocation.
> - It is strictly forbidden to use this project to disrupt market order, engage in malicious competition, arbitrage or resale, resell related services, or commit any act that violates OpenAI's Terms of Service or local laws and regulations.
> - It is strictly forbidden to use this project to generate, distribute, or assist in generating illegal, violent, pornographic, or minor-related content, or for fraud, scams, harassment, or other illegal or improper purposes.
> - Users assume all risks, including but not limited to account restrictions, temporary suspensions, permanent bans, and any legal liability arising from misuse.
> - By using this project, you are deemed to have fully understood and agreed to this entire disclaimer; any consequences resulting from abuse, violations, or illegal use are solely the user's responsibility.

> [!IMPORTANT]
> This project is implemented through reverse engineering of features on the ChatGPT website, which carries the risk of account restrictions, temporary suspensions, or permanent bans. Do not use your own important, primary, or high-value accounts for testing.

## Quick Start

Published images support `linux/amd64` and `linux/arm64`; both x86 servers and Apple Silicon / ARM Linux devices will automatically pull the matching architecture.

```bash
git clone git@github.com:huaiyuechusan/YanAI.git
cd YanAI
docker build -t your-registry/yanai:latest .
docker push your-registry/yanai:latest
```

The Docker image built from this repository does not include `config.json`, `data/`, `.env`, database files, or local virtual environments. For server deployments, provide runtime configuration and data via host mounts:

```yaml
volumes:
  - ./data:/app/data
  - ./config.json:/app/config.json
```

Prepare the configuration and data directory on the server:

```bash
cp config.example.json config.json
# Edit config.json and change auth-key to your own long random secret
mkdir -p data
YANAI_IMAGE=your-registry/yanai:latest docker compose up -d
```

You can also use the environment variable `CHATGPT2API_AUTH_KEY` to override `auth-key` in `config.json`, but never put real secrets into the Dockerfile, image build args, or public compose files.

To run a container directly from the current local code:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

Local development startup
```bash
cd D:\Desktop\YanAI
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

cd D:\Desktop\YanAI\web
npm run dev
```

### Storage Backend Configuration

The storage backend can be switched via environment variables or the corresponding fields in `config.json`; environment variables take precedence, and redundant outer quotes around config values are stripped automatically:

- `json` - Local JSON files (default)
- `sqlite` - Local SQLite database
- `postgres` - External PostgreSQL (requires `DATABASE_URL`)
- `git` - Private Git repository (requires `GIT_REPO_URL` and `GIT_TOKEN`)

For stable multi-user concurrent deployments, `postgres` is recommended. `sqlite` suits local development and lightweight validation; `json` / `git` are better for single-instance low-concurrency use, backup import/export, or transitional scenarios, and are not recommended as the primary store for multi-user concurrent production. On startup, the PostgreSQL backend automatically checks the target database; if it does not exist, it attempts to create it via the `postgres` / `template1` maintenance databases, then continues to auto-initialize the business tables.

Example: using PostgreSQL
```yaml
environment:
  - STORAGE_BACKEND=postgres
  - DATABASE_URL=postgresql://user:password@host:5432/dbname
```

### Pre-Migration Protection and Auditing

Before migrating from the legacy JSON storage to SQLite, PostgreSQL, or Git, you must first stop all writes. For Docker deployments, stop the YanAI container first and confirm no background tasks are still writing to `data/*.json`:

```bash
docker compose stop app
# If managing by container name directly, you can also use: docker stop yanai
```

Run a read-only audit first to verify record counts, duplicate primary keys, missing primary keys, and malformed JSON in the legacy data:

```bash
python scripts/audit_storage.py --data-dir data
```

Create a full JSON backup directory and verify the backup is restorable:

```bash
python scripts/backup_storage.py --data-dir data --backup-dir data/backups/pre-migration
python scripts/backup_storage.py --verify data/backups/pre-migration
```

Restore drills can target a temporary directory to avoid overwriting production data:

```bash
python scripts/backup_storage.py --restore data/backups/pre-migration --target-dir .tmp/restore-check
python scripts/audit_storage.py --data-dir .tmp/restore-check --fail-on-issues
```

The migration script supports dry runs, pre-migration backups, and verify-only mode:

```bash
python scripts/migrate_storage.py --from json --to postgres --dry-run
python scripts/migrate_storage.py --from json --to postgres --backup-dir data/backups/pre-postgres
python scripts/migrate_storage.py --from json --to postgres --verify-only
```

## Features

### API Compatibility

- Compatible with the `POST /v1/images/generations` image generation endpoint
- Compatible with the `POST /v1/images/edits` image editing endpoint
- Admin keys can call `POST /v1/chat/completions`, `POST /v1/responses`, and `POST /v1/messages`
- `GET /v1/models` returns the upstream model list, supplemented with the built-in default models `gpt-5`, `gpt-5-1`, `gpt-5-2`, `gpt-5-3`, `gpt-5-3-mini`, `gpt-5-5`, `gpt-5-mini`, `gpt-image-2`, `codex-gpt-image-2`, `auto`
- Image endpoints support `n=1-4`; the frontend workbench splits tasks by image count
- Supports the built-in account pool plus OpenAI image-compatible external channels, with routing by model, weight, and priority
- The built-in account pool can be disabled in channel management to use only external OpenAI-compatible channels; if all external channels fail and the built-in pool is disabled, a clear unavailability error is returned
- Supports reverse-engineered image generation via Codex, available only with `Plus` / `Team` / `Pro` subscriptions; the model alias is `codex-gpt-image-2` to distinguish it from website-based drawing

### Online Drawing

- Built-in "Drawing" workbench supporting text-to-image, image-to-image, and multi-reference-image editing
- Preset prompts for eyewear matching, hairstyle reports, natural beautification, random portrait styles, photo enhancement, low-light repair, and HD detail restoration
- Supports reference image upload, image pasting, aspect ratio selection, and multi-image task queues
- The prompt input box can be vertically resized, with one-click clearing of the selected template or current prompt
- Supports copying and sharing the current prompt, as well as copying or sharing prompts from past generation records
- Image session history is saved locally, with support for reviewing, deleting, clearing, and continuing edits from a result image
- The server can cache generated images, browsable in "Image Management / My Images" with date filtering, previewing, and URL copying
- "My Images" supports select-all on the current page, multi-select, single download, batch download of selected images as an archive, batch deletion, and syncing selected images to WebDAV; regular users can only download, delete, and sync their own image records

### Prompt Management and Sharing

- Regular users can create, edit, and delete personal prompts in "My Prompts" and upload prompt example images
- Users can submit personal prompts for admin review; admins can review pending submissions in "Prompt Management", approving them into the public prompt library or rejecting them with a reason
- Share links can be generated for the current prompt, history prompts, or prompt library entries; other users can preview and import them into their personal prompt library via the link, and admins can import them as public prompts
- The drawing workbench's prompt library merges public prompts with the current user's visible personal prompts, making it easy to apply frequently used templates

### Account Pool Management

- Automatically refreshes account email, type, quota, and recovery time
- Rotates through available accounts for image generation and image editing
- Automatically removes invalid tokens when token-expiry errors occur
- Periodically checks rate-limited accounts and refreshes them automatically
- Supports configuring a global HTTP / HTTPS / SOCKS5 / SOCKS5H proxy from the web UI
- Supports searching, filtering, batch refresh, export, manual editing, and account cleanup
- Supports four import methods: local CPA JSON file import, remote CPA server import, `sub2api` server import, and `access_token` import
- Supports configuring a `sub2api` server on the settings page to filter and batch-import its OpenAI OAuth accounts

### Admin Console

- Admins can create personal users, adjust quotas, disable accounts, and reset passwords
- Supports personal user registration, login, quota redemption via codes, and viewing personal image records
- Once a regular user configures a valid Personal Channel for image generation, they can use it even with a local image quota of 0; if the Personal Channel fails, requests do not fall back to the built-in account pool for free
- Supports batch generation, filtering, copying, batch deletion, and export of selected redemption codes
- Supports OpenAI image-compatible channel management: add, edit, enable/disable, and delete channels, with Base URL, API Key, models, weight, priority, and timeout settings
- External channel Base URLs accept either a root address or one already ending in `/v1`; image generation, image editing, and model list requests automatically normalize the OpenAI-compatible path to avoid duplicating `/v1`
- Channel management supports testing a channel's `/v1/models` availability after selecting models, showing passing models, missing models, error messages, and latency; testing does not overwrite the channel's configured models
- For external channels that do not support `GET /v1/models`, the channel test reports that the endpoint is unavailable, and the channel can still be saved and used for image generation with its configured models
- The built-in account pool is also displayed as a channel and can be toggled separately in the admin console, which is convenient for external-channel-only deployments or temporarily disabling the local account pool
- Supports model management: aggregate models per channel, fetch model lists from a channel's `/v1/models`, and configure pricing for each model
- Supports viewing system logs, call logs, and audit logs, filterable by type, status, date, request ID, user email / nickname / ID, or token information
- Supports configuring the image access URL, automatic cleanup retention days, account refresh interval, and model mapping

### Image Archiving and WebDAV

- Admins can configure global WebDAV storage in "Image Management", and regular users can configure their own WebDAV directory in "My Images"
- WebDAV supports enable/disable, URL, username, password, and remote directory settings; the password is shown as "already set", and leaving it blank during editing keeps the original password
- Newly generated images are automatically synced once WebDAV is enabled; historical images can also be synced manually by date, user, channel, or request ID
- Both admins and regular users can select images first and sync only the selected ones to WebDAV; when no images are selected, syncing follows the current filter scope
- Image records store the WebDAV sync status, sync time, and remote URL, and the Image Management and My Images pages display the synced status

### Model Management and Pricing

- Admins can view all channel models on the "Model Management" page; the built-in account pool provides 10 default models matching common New API integration configurations, while external channels read from their own `models` configuration.
- Each OpenAI-compatible external channel has a "Fetch" button that requests that channel's `/v1/models` and, on success, automatically writes the result back to the channel's model list.
- Model pricing is stored in the `model_pricing` system configuration, compatible with the existing JSON, SQLite, and PostgreSQL storage backends — no additional table migration is needed.
- Pricing supports both per-token and per-call modes; you can configure input price / 1M tokens, output price / 1M tokens, `model_ratio`, `completion_ratio`, `model_price`, currency, and enabled status, making it easy to integrate with New API-style ratio or fixed-price billing.

### Multi-User Concurrency Hardening

This repository has completed its multi-user stable concurrency overhaul, built on database transactions, row-level writes, leases, and request tracing.

- The storage layer is split along Repository boundaries with an adapter that remains compatible with the legacy Storage API; database backends cover accounts, admin keys, users, sessions, redemption codes, channels, the prompt library, image records, quota reservations, system configuration, system logs, and audit logs
- The SQLite / PostgreSQL backends automatically create all required business tables on initialization, reducing manual table-creation effort on first deployment and after migration
- PostgreSQL storage configuration can live in environment variables or `config.json`, with environment variables taking precedence; if the target database does not exist it is created automatically, reducing manual preparation for first deployments and remote database migrations
- Data migration and safety protections cover the full business dataset, providing read-only auditing, backup and restore, migration dry runs, migration verification, and duplicate primary key checks, supporting migration from legacy JSON data to SQLite / PostgreSQL; the migration scope includes accounts, keys, users, sessions, redemption codes, channels, the prompt library, image records, quota reservations, system settings, system logs, and audit logs
- Regular-user image quotas now use request-level pre-deduction: quota is reserved by `request_id` before a task starts, confirmed against the actual generated count on success, released on failure or empty results, and expired reservations are returned by a background watcher; admin calls do not consume personal quota
- A valid Personal Channel for image generation skips local quota reservation, and the image record's `quota_cost` is recorded as 0; if that Personal Channel is misconfigured, has a model mismatch, or its upstream call fails, the request returns the Personal Channel error directly without falling back to the built-in account pool
- The account pool now uses a lease model for image tasks, supporting `max_concurrency`, `inflight_count`, `lease_owner`, `lease_owners`, and `leased_until`; the upstream is called only after a lease is acquired, and on completion the lease is released and the success, failure, quota, and rate-limit states are updated; under PostgreSQL, row-level locks prevent multiple tasks from grabbing the same account
- Image records are now inserted one at a time with UUID record IDs, supporting paginated queries by user, date, channel, and `request_id`, preventing record loss from whole-table overwrites when multiple people generate images simultaneously
- Redemption code redemption, channel updates, prompt creation, and system settings are wired into the database Repository: a single redemption code can only be redeemed once under concurrency, and concurrent management operations on different channels or prompts no longer overwrite each other
- The request chain carries `x-request-id` / `request_id` through API calls, quota reservations, account leases, image records, system logs, and audit logs; `/api/storage/info` and the health check expose the current storage backend and dataset status

### Registration Bot Email Providers

The registration bot supports configuring multiple temporary email providers on the `/register` page, rotating through them in enabled order. Example `moemail` configuration:

```json
{
  "enable": true,
  "type": "moemail",
  "api_base": "https://moemail.app",
  "api_key": "YOUR_MOEMAIL_API_KEY",
  "default_domain": "moemail.app",
  "expiry_time": 3600000
}
```

`api_base` can be changed to your self-hosted MoeMail address; `expiry_time` is in milliseconds, so `3600000` means 1 hour.

### Experimental / Notes

- The text-oriented compatibility endpoints are mainly for admin keys and debugging scenarios; personal users only have access to image-related capabilities
- Streaming image and text output should still be tested with caution
- For detailed status, see the [Feature Status](./docs/feature-status.en.md)

## Screenshots

### Drawing
![image-20260604221114171](README.assets/image-20260604221114171.png)

### User Management
![image-20260604221129930](README.assets/image-20260604221129930.png)

### Account Pool Management (with RT-based account import)
![image-20260604221249125](README.assets/image-20260604221249125.png)

### Registration Bot Management
![image-20260604221336677](README.assets/image-20260604221336677.png)

### Prompt Management
![image-20260604221403230](README.assets/image-20260604221403230.png)

### Image Management

![image-20260604221416836](README.assets/image-20260604221416836.png)

### Channel Management (third-party channels added on top of the original project)
![image-20260604221426835](README.assets/image-20260604221426835.png)

### Model Management (can be connected to New API as a channel)

![image-20260604221442002](README.assets/image-20260604221442002.png)

### Redemption Code Management

![image-20260604221532803](README.assets/image-20260604221532803.png)

### User Login and Registration (with LinuxDO login and email verification)
![image-20260604221546536](README.assets/image-20260604221546536.png)

## API

All AI endpoints require the request header:

```http
Authorization: Bearer <auth-key>
```

<details>
<summary><code>GET /v1/models</code></summary>
<br>

Returns the upstream model list, supplemented with the current built-in default models.

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer <auth-key>"
```

<details>
<summary>Notes</summary>
<br>

| Field | Description |
|:-----|:-----------------------------------------------------------------------------------------------------------------------------------|
| Returned models | The upstream model list, supplemented with `gpt-5`, `gpt-5-1`, `gpt-5-2`, `gpt-5-3`, `gpt-5-3-mini`, `gpt-5-5`, `gpt-5-mini`, `gpt-image-2`, `codex-gpt-image-2`, `auto` |
| Integration scenarios | Can be integrated with upstreams or clients such as Cherry Studio and New API |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/generations</code></summary>
<br>

OpenAI-compatible image generation endpoint, used for text-to-image.

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "A cat floating in outer space",
    "n": 1,
    "response_format": "b64_json"
  }'
```

<details>
<summary>Field Descriptions</summary>
<br>

| Field | Description |
|:------------------|:---------------------------------------------------|
| `model`           | Image model; available values follow what `/v1/models` returns, `gpt-image-2` is recommended |
| `prompt`          | Image generation prompt |
| `n`               | Number of images to generate; the current backend limit is `1-4` |
| `response_format` | Included in the current request model, defaults to `b64_json` |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/edits</code></summary>
<br>

OpenAI-compatible image editing endpoint, used to upload an image and generate an edited result.

```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer <auth-key>" \
  -F "model=gpt-image-2" \
  -F "prompt=Turn this image into a cyberpunk night scene" \
  -F "n=1" \
  -F "image=@./input.png"
```

<details>
<summary>Field Descriptions</summary>
<br>

| Field | Description |
|:---------|:------------------------------------|
| `model`  | Image model, `gpt-image-2` |
| `prompt` | Image editing prompt |
| `n`      | Number of images to generate; the current backend limit is `1-4` |
| `image`  | The image file to edit, uploaded via multipart/form-data |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/chat/completions</code></summary>
<br>

A Chat Completions-compatible endpoint oriented toward image scenarios — not a full general-purpose chat proxy.

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "messages": [
      {
        "role": "user",
        "content": "Generate a cyberpunk cat on a rainy Tokyo street at night"
      }
    ],
    "n": 1
  }'
```

<details>
<summary>Field Descriptions</summary>
<br>

| Field | Description |
|:-----------|:------------------|
| `model`    | Image model; requests are handled as image generation by default |
| `messages` | Message array; must contain image-related request content |
| `n`        | Number of images; interpreted as the image count in the current implementation |
| `stream`   | Implemented, but still under testing |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/responses</code></summary>
<br>

A Responses API-compatible endpoint oriented toward image generation tool calls — not a full general-purpose Responses API proxy.

```bash
curl http://localhost:8000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-5",
    "input": "Generate a futuristic city skyline image",
    "tools": [
      {
        "type": "image_generation"
      }
    ]
  }'
```

<details>
<summary>Field Descriptions</summary>
<br>

| Field | Description |
|:---------|:------------------------------|
| `model`  | The model field is echoed back in the response, but image generation still goes through the image-generation compatibility logic |
| `input`  | Input content; an image generation prompt must be extractable from it |
| `tools`  | Must include an `image_generation` tool request |
| `stream` | Implemented, but still under testing |

<br>
</details>
</details>

## ToDoList

- [x] After selecting a default prompt template, it could not be deselected; added a one-click clear-template button
- [x] Freely resizable prompt input box
- [x] Prompt sharing and user import; each user can also manage their own prompts independently
- [x] Users can configure their own API
- [x] Page lag: the site was still embedding large images directly as base64. Fixed by changing the site code / backend API to image URLs + thumbnails + lazy-loaded originals
- [x] Batch export of redemption codes
- [ ] Payment integration
- [x] Automatic table creation for the PostgreSQL knowledge base
- [x] Custom channels without a balance showed a quota of 0
- [x] Log search by user
- [x] WebDAV configuration for saving images
- [x] Users can manage their own generated photos, with selection, download, archive download, deletion, and WebDAV sync of selected images
- [x] Channel model availability testing, with model selection and visibility into missing models and latency
- [x] Custom channel Base URL compatibility with both root and `/v1` addresses, plus improved error messages when the model list endpoint is unsupported
- [x] PostgreSQL environment configuration read from config, with all JSON data migrated to PostgreSQL (including quota reservations, system settings, system logs, and audit logs)

## Community Support

Learn AI on LinuxDO: [LinuxDO](https://linux.do)

## Acknowledgements

Thanks to the [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api) project for its exploration and open-source sharing of ChatGPT reverse engineering, OpenAI-compatible API wrapping, and self-hosted deployment approaches. YanAI's direction and parts of its implementation were inspired by it.<br>
Thanks to the community post [A prompt that even sends chills down designers' spines](https://linux.do/t/topic/532495)<br>
Thanks to the [🍌Banana Prompt Quicker](https://linux.do/t/topic/1244563) project for its open-source sharing and inspiration on quick prompt workflows.<br>

## Contributors

Thanks to all the developers who have contributed to this project:

<a href="https://github.com/huaiyuechusan/YanAI/graphs/contributors">
  <img alt="Contributors" src="https://contrib.rocks/image?repo=huaiyuechusan/YanAI" />
</a>

## Star History

[![Star History Chart](https://api.star-history.com/chart?repos=huaiyuechusan/YanAI&type=date&legend=top-left)](https://www.star-history.com/?repos=huaiyuechusan%2FYanAI&type=date&legend=top-left)
