# Feature Status

This document is based on the current implementation in this repository and helps users quickly understand which features are available, which are still being refined, and which are pending.

| Feature | Status | Notes |
|:----------------------------------------|:--:|:--------------------------------------------------------------|
| OpenAI-compatible `POST /v1/images/generations` | ✅  | Supported, used for image generation; multiple images can be returned via `n`. |
| OpenAI-compatible `POST /v1/images/edits` | ✅  | Supported; images can be uploaded for editing. |
| Image-workflow-oriented `POST /v1/chat/completions` | ✅  | Image-related requests are supported. |
| Image-workflow-oriented `POST /v1/responses` | ✅  | Image generation tool calls are supported. |
| `GET /v1/models` endpoint | ✅  | Currently returns `gpt-image-2`, `codex-gpt-image-2`, `auto`, `gpt-5`, `gpt-5-1`, `gpt-5-2`, `gpt-5-3`, `gpt-5-3-mini`, `gpt-5-mini`. |
| Generating multiple images at once | ✅  | Supported; both the backend and frontend can generate multiple images. |
| Frontend image workbench | ✅  | Supports image generation, image editing, model selection, history, and full-size viewing. |
| Frontend image input / reference image interaction | ✅  | Supports reference image upload, preview, removal, and the edit-mode workflow. |
| Reverse-engineered Codex image API | ✅  | Supported, available only with `Plus` / `Team` / `Pro` subscriptions; the model alias is `codex-gpt-image-2`, and you can map it back to `gpt-image-2` in other scenarios if needed. This is the Codex reverse-engineered pipeline, distinguished from website-based drawing; the same account usually carries both the website and Codex image generation quotas. |
| Cherry Studio integration | ✅  | Supported as a drawing API for Cherry Studio. |
| New API integration | ✅  | Supported as a New API integration. |
| Account pool management | ✅  | Supports listing, filtering, batch operations, export, manual editing, refresh, and deletion. |
| Account quota refresh and recovery time sync | ✅  | Account info refresh is supported; rate-limited accounts also continue to be checked automatically. |
| Automatic cleanup of expired tokens | ✅  | Invalid tokens are removed automatically. |
| CPA connection management | ✅  | Supports adding, modifying, querying, and deleting CPA connections. |
| CPA file browsing and on-demand import | ✅  | Supports reading the remote file list, filtering, selecting, and importing into the local account pool. |
| CPA import progress tracking | ✅  | Supports import progress display with polling updates. |
| `sub2api` connection management and account browsing | ✅  | Supports adding, modifying, and deleting `sub2api` servers, querying by group, and listing OpenAI OAuth accounts. |
| `sub2api` import | ✅  | Supports selecting OpenAI OAuth accounts in `sub2api`, batch-fetching their `access_token`s into the local account pool, and displaying import progress. |
| Self-hosted Docker deployment | ✅  | Docker Compose deployment is supported, with multi-architecture images. |
| Multi-reference-image support in compatible endpoints | ✅  | Implemented; multiple reference images can be passed through the compatible endpoints. |
| More advanced token scheduling strategies | ⚠️ | Basic rotation and rate-limit refresh are in place; more sophisticated scheduling strategies are still being refined. |
| Render / Vercel deployment guidance | ⚠️ | Docker is the primary deployment method; other platforms are not yet a documentation focus. |
| `/v1/complete` text completion with streaming | ✅  | Implemented. |
| Streaming output support | ✅  | Implemented. |
| Image size parameter | ❌  | Pending. |
| Server-side image URL caching | ✅  | Implemented. |
| `rt_token` refresh | ❌  | Pending. |
| Proxy configuration | ✅  | Supports configuring a global HTTP / HTTPS / SOCKS5 / SOCKS5H proxy from the web UI, applied to outbound requests. |
| Anthropic protocol support | ❌  | Pending. |
