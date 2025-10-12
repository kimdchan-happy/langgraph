"""Utility to convert ChatGPT conversation exports into Markdown files.

This script reads the `conversations.json` file that ChatGPT exports when a user
chooses *Export data* and converts each conversation inside the file into a
separate Markdown document that can be ingested by tools such as Obsidian's
Graph view.

Usage
-----

```bash
python chatgpt_export_to_markdown.py path/to/conversations.json -o output_dir
```

The script will create one Markdown file per conversation using a sanitized
version of the conversation title as the filename. Metadata and message
timestamps are preserved when present in the export.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Set


@dataclass
class Message:
    """Container for a single chat message."""

    id: Optional[str]
    role: str
    name: Optional[str]
    content: str
    create_time: Optional[float]

    @property
    def timestamp(self) -> Optional[str]:
        if self.create_time is None:
            return None
        try:
            # ChatGPT exports timestamps as seconds since the Unix epoch.
            return dt.datetime.fromtimestamp(self.create_time).isoformat()
        except (OSError, OverflowError, ValueError):
            return None


@dataclass
class Conversation:
    """Container for a single conversation."""

    id: str
    title: str
    create_time: Optional[float]
    update_time: Optional[float]
    messages: List[Message]

    @property
    def created_at(self) -> Optional[str]:
        return _format_timestamp(self.create_time)

    @property
    def updated_at(self) -> Optional[str]:
        return _format_timestamp(self.update_time)


def _format_timestamp(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    try:
        return dt.datetime.fromtimestamp(value).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert ChatGPT conversation exports to Markdown files for use in "
            "tools like Obsidian."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the conversations.json export file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("chatgpt-conversations"),
        help=(
            "Directory where Markdown files will be written. "
            "Defaults to './chatgpt-conversations'."
        ),
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Optional prefix to add to every generated filename.",
    )
    return parser.parse_args()


def load_conversations(path: Path) -> Iterable[Conversation]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    raw_conversations = payload.get("conversations")
    if not raw_conversations:
        raise ValueError("No conversations found in the provided JSON file.")

    for entry in raw_conversations:
        convo_id = entry.get("id") or "unknown"
        title = entry.get("title") or f"conversation-{convo_id}"
        messages = _extract_messages(entry.get("mapping", {}))
        yield Conversation(
            id=convo_id,
            title=title,
            create_time=entry.get("create_time"),
            update_time=entry.get("update_time"),
            messages=messages,
        )


def _extract_messages(mapping: dict) -> List[Message]:
    candidates: List[Message] = []
    for node in mapping.values():
        message = node.get("message")
        if not message:
            continue
        role = message.get("author", {}).get("role", "unknown")
        name = message.get("author", {}).get("name")
        create_time = message.get("create_time") or node.get("create_time")
        content = _render_content(message.get("content", []))
        candidates.append(
            Message(
                id=message.get("id") or node.get("id"),
                role=role,
                name=name,
                content=content,
                create_time=create_time,
            )
        )

    candidates.sort(key=lambda msg: (msg.create_time or float("inf"), msg.id or ""))
    return candidates


def _render_content(chunks: Iterable[dict]) -> str:
    parts: List[str] = []
    for chunk in chunks:
        content_type = chunk.get("content_type")
        if content_type == "text":
            raw_parts = chunk.get("parts", [])
            for part in raw_parts:
                if isinstance(part, str):
                    parts.append(part)
        elif content_type == "image_file":
            file_id = chunk.get("file_id", "unknown")
            parts.append(f"![Image: {file_id}]()")
        elif content_type == "code":
            # Some exports may include structured code blocks.
            text = chunk.get("text")
            language = chunk.get("language", "")
            if text:
                lang_spec = language or ""
                if lang_spec:
                    lang_spec = lang_spec.strip()
                parts.append(f"```{lang_spec}\n{text}\n```")
        else:
            serialized = json.dumps(chunk, ensure_ascii=False)
            parts.append(f"Unsupported content type {content_type}: {serialized}")
    return "\n\n".join(parts).strip()


def write_conversation(conversation: Conversation, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    with path.open("w", encoding="utf-8") as fh:
        fh.write(_conversation_to_markdown(conversation))
    return path


def _conversation_to_markdown(conversation: Conversation) -> str:
    lines = ["---"]
    lines.append(f"id: {conversation.id}")
    lines.append(f"title: {conversation.title}")
    if conversation.created_at:
        lines.append(f"created_at: {conversation.created_at}")
    if conversation.updated_at:
        lines.append(f"updated_at: {conversation.updated_at}")
    lines.append("---\n")
    lines.append(f"# {conversation.title}\n")

    for index, message in enumerate(conversation.messages, start=1):
        header = f"## {index}. {message.role.title()}"
        if message.name:
            header += f" ({message.name})"
        if message.timestamp:
            header += f" — {message.timestamp}"
        lines.append(header)
        lines.append("")
        if message.content:
            lines.append(message.content)
        else:
            lines.append("_No content available._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


_slugify_pattern = re.compile(r"[^a-zA-Z0-9-]+")


def _slugify(value: str, max_length: int = 80) -> str:
    value = value.strip().lower()
    value = value.replace(" ", "-")
    value = _slugify_pattern.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        value = "conversation"
    return value[:max_length]


def _build_filename(title: str, prefix: str, existing: Set[str]) -> str:
    base = _slugify(title)
    candidate = f"{prefix}{base}.md"
    counter = 1
    while candidate in existing:
        counter += 1
        candidate = f"{prefix}{base}-{counter}.md"
    existing.add(candidate)
    return candidate


def main() -> None:
    args = parse_arguments()
    conversations = list(load_conversations(args.input))
    written_files: List[Path] = []
    existing: Set[str] = set()
    for conversation in conversations:
        filename = _build_filename(conversation.title, args.prefix, existing)
        path = write_conversation(conversation, args.output, filename)
        written_files.append(path)
    print(f"Wrote {len(written_files)} conversations to '{args.output}'.")
    for path in written_files:
        print(f" - {path}")


if __name__ == "__main__":
    main()
