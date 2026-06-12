# Upstream Conversation SSE Protocol

Conversation SSE is the streaming response protocol of the upstream conversation pipeline. Each SSE `data:` line is usually a JSON payload, but may also be a protocol marker or a termination marker. Clients must consume these payloads in order, maintaining the current conversation state, text content, tool-call status, and image result pointers.

## Basic Shapes

Common payload examples:

```text
"v1"
{"type":"resume_conversation_token",...}
{"p":"","o":"add","v":{...}}
{"v":{...}}
{"p":"/message/content/parts/0","o":"append","v":"..."}
{"type":"server_ste_metadata","metadata":{...}}
[DONE]
```

Handling recommendations:

| payload | Meaning | Handling |
|:--|:--|:--|
| `"v1"` | Protocol version marker | Can be logged; usually has no business impact |
| `[DONE]` | End of the current SSE stream | Stop reading |
| JSON object | Event, message, or patch | Update conversation state per its fields |
| JSON string | Short text patch or protocol marker | Handle based on context |
| Non-JSON content | Raw content | Keep as a raw event to avoid breaking the stream |

## Common Fields

| Field | Description |
|:--|:--|
| `type` | Upstream event type, e.g. `resume_conversation_token`, `input_message`, `message_marker`, `title_generation`, `server_ste_metadata` |
| `conversation_id` | Current conversation ID, obtainable from multiple events |
| `p` | Patch path, e.g. `/message/content/parts/0` |
| `o` | Patch operation, e.g. `add`, `append`, `replace`, `patch` |
| `v` | Patch value; may be a string, an array, or contain a full message |
| `c` | Message sequence number or cursor, common in add-type events |
| `message.id` | Message ID |
| `message.author.role` | Message role, typically `system`, `user`, `assistant`, `tool` |
| `message.content.content_type` | Content type, e.g. `text`, `multimodal_text`, `model_editable_context` |
| `message.content.parts` | Content parts; may contain text, image pointers, or multimodal objects |
| `message.status` | Message status, e.g. `in_progress`, `finished_successfully` |
| `message.end_turn` | Whether the current turn has ended |
| `metadata.tool_invoked` | Whether a tool was invoked this turn |
| `metadata.turn_use_case` | The purpose of this turn, e.g. `text`, `multimodal` |
| `metadata.async_task_type` | Async tool task type; image generation is usually `image_gen` |

## Conversation Startup Events

The upstream usually returns a resume token or conversation token first:

```json
{
  "type": "resume_conversation_token",
  "kind": "topic",
  "token": "...",
  "conversation_id": "..."
}
```

This event mainly identifies the conversation and its resumable context. The business layer typically only needs to store the `conversation_id`; the `token` must not be exposed to downstream users.

## Message Add Scenarios

A full message may appear via an `add` event or an event carrying `v.message`:

```json
{
  "p": "",
  "o": "add",
  "v": {
    "message": {
      "author": {"role": "assistant"},
      "content": {"content_type": "text", "parts": [""]},
      "status": "in_progress"
    },
    "conversation_id": "..."
  },
  "c": 3
}
```

Events of this kind are typically used to create a new message. If the message role is `assistant`, subsequent text is usually appended via patches.

## Incremental Text Scenarios

Text output usually consists of multiple patches:

```json
{"p":"/message/content/parts/0","o":"append","v":"Hello"}
{"v":" world"}
{"p":"","o":"patch","v":[
  {"p":"/message/content/parts/0","o":"append","v":"!"},
  {"p":"/message/status","o":"replace","v":"finished_successfully"},
  {"p":"/message/end_turn","o":"replace","v":true}
]}
```

Key handling points:

| Shape | Meaning |
|:--|:--|
| `p == "/message/content/parts/0"` and `o == "append"` | Append content to the current text |
| `o == "replace"` | Replace the target field with the new value |
| `o == "patch"` and `v` is an array | Batch patch; process in array order |
| Only `v`, and `v` is a string | Likely a text delta with the path omitted; handle in the context of the current text stream |

## Input Message Scenarios

User input appears as an `input_message` or a regular `user` message. Image editing requests include the user's uploaded reference image:

```json
{
  "type": "input_message",
  "input_message": {
    "author": {"role": "user"},
    "content": {
      "content_type": "multimodal_text",
      "parts": [
        {"asset_pointer": "sediment://file_input"},
        "edit prompt"
      ]
    }
  },
  "conversation_id": "..."
}
```

A `sediment://...` here represents an input attachment, not a generated result. Even if it is downloadable, it must not be returned as an output image.

## Image Tool Success Scenarios

When image generation or image editing succeeds, the upstream typically emits a tool message:

```json
{
  "v": {
    "message": {
      "author": {"role": "tool"},
      "content": {
        "content_type": "multimodal_text",
        "parts": [
          {"asset_pointer": "file-service://file_result"},
          {"asset_pointer": "sediment://file_result"}
        ]
      },
      "metadata": {"async_task_type": "image_gen"}
    }
  },
  "conversation_id": "..."
}
```

Only image pointers that meet all of the following conditions should be treated as output results:

| Condition | Description |
|:--|:--|
| `message.author.role == "tool"` | The source is a tool message |
| `metadata.async_task_type == "image_gen"` | The tool task is image generation |
| `asset_pointer` is `file-service://...` or `sediment://...` | Points to a resolvable image resource |

## Image Pointer Types

| Pointer | Typical Source | Description |
|:--|:--|:--|
| `file-service://file_xxx` | Image tool output | Resolvable via the file download API |
| `sediment://file_xxx` | Input attachment or image tool output | Source must be determined from the message role |
| `file_upload` | Upload-in-progress placeholder | Usually must not be treated as output |

Never classify something as an output image just because the string contains `file_` or `sediment://`. Always combine the message role and task type.

## Policy Refusal Scenarios

When the upstream refuses a request, it usually produces no image tool message and instead returns plain assistant text:

```text
I can't assist with that request. If you have another type of modification...
```

Common accompanying events:

```json
{"type":"title_generation","title":"Request Denied","conversation_id":"..."}
```

```json
{
  "type": "server_ste_metadata",
  "metadata": {
    "tool_invoked": false,
    "turn_use_case": "multimodal",
    "did_prompt_contain_image": true
  },
  "conversation_id": "..."
}
```

Key handling points:

| Condition | Behavior |
|:--|:--|
| Assistant refusal text is present | Return the text message |
| `tool_invoked == false` | No actual tool result was produced |
| No message with `role=tool` and `async_task_type=image_gen` | Do not collect output images |
| Image pointers appear in the user's input message | Still treat them only as input attachments |

## Moderation Scenarios

Some requests may return a moderation event:

```json
{
  "type": "moderation",
  "moderation_response": {
    "blocked": true
  },
  "conversation_id": "..."
}
```

If `blocked == true`, treat this turn as blocked by policy. If assistant text follows, prefer returning that text; if there is no text, return an appropriate error message.

## Marker and Title Events

The upstream returns a few auxiliary events:

```json
{"type":"message_marker","marker":"user_visible_token","event":"first"}
{"type":"message_marker","marker":"last_token","event":"last"}
{"type":"title_generation","title":"...","conversation_id":"..."}
```

These events are typically used for frontend display, title generation, or streaming state markers; they do not represent actual text content or image results.

## Metadata Events

`server_ste_metadata` describes the scheduling and tool status of the current turn:

```json
{
  "type": "server_ste_metadata",
  "metadata": {
    "tool_invoked": true,
    "turn_use_case": "multimodal",
    "model_slug": "i-mini-m",
    "did_prompt_contain_image": true
  }
}
```

Common checks:

| Field | Description |
|:--|:--|
| `tool_invoked == true` | The upstream considers a tool to have been invoked this turn |
| `tool_invoked == false` | No tool was invoked; common in refusals or text-only responses |
| `turn_use_case == "text"` | Handle as a text response |
| `turn_use_case == "multimodal"` | Multimodal request; does not guarantee image output |
| `did_prompt_contain_image == true` | The input contained an image; does not mean the output contains one |

## Determining Results After Completion

After the SSE stream ends, determine the result in this order:

1. If image tool output pointers have been collected, resolve and download the output images.
2. If there are no output image pointers but there is assistant text, and the turn was blocked or no tool was invoked, return the text message.
3. If there are no output image pointers but a `conversation_id` is available, query the full conversation detail and keep looking for image tool output.
4. When querying the full conversation, still read only messages with `role=tool` and `async_task_type=image_gen`.
5. If there is neither an image result nor text, return an upstream error or an empty-result error.
