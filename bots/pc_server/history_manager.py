"""History Manager for PC sidecar - handles conversation history storage and retrieval."""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import tiktoken

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages conversation history storage for streams and private messages."""

    encoder: Optional["tiktoken.Encoding"]

    def __init__(self, root_dir: str = "/pc"):
        """Initialize history manager with root directory."""
        self.root = Path(root_dir)
        self.history_dir = self.root / "history"
        self.streams_dir = self.history_dir / "streams"
        self.private_dir = self.history_dir / "private"

        for directory in [self.streams_dir, self.private_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to load tiktoken: {e}, using approximate token counting")
            self.encoder = None

    def _hash_id(self, identifier: str) -> str:
        """Create a consistent hash for stream/user identifiers."""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0

        if self.encoder:
            return len(self.encoder.encode(text))
        else:
            return len(text) // 4

    def _get_stream_file_path(self, stream_id: str, topic: Optional[str] = None) -> Path:
        """Get file path for stream history."""
        stream_hash = self._hash_id(stream_id)
        stream_dir = self.streams_dir / stream_hash

        if topic:
            topic_hash = self._hash_id(topic)
            return stream_dir / f"{topic_hash}.json"
        else:
            return stream_dir / "config.json"

    def _get_private_file_path(self, user_email: str) -> Path:
        """Get file path for private DM history."""
        user_hash = self._hash_id(user_email)
        return self.private_dir / f"{user_hash}.json"

    def _load_history_file(self, file_path: Path) -> Dict[str, Any]:
        """Load history from JSON file."""
        try:
            if file_path.exists():
                with open(file_path, "r") as f:
                    return cast(Dict[str, Any], json.load(f))
        except Exception as e:
            logger.error(f"Failed to load history file {file_path}: {e}")

        return {
            "messages": [],
            "total_tokens": 0,
            "last_updated": time.time(),
            "config": {},
        }

    def _save_history_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save history to JSON file."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            data["last_updated"] = time.time()
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history file {file_path}: {e}")

    def _cleanup_messages(
        self, messages: List[Dict[str, Any]], max_tokens: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Cleanup messages if total tokens exceed max_tokens.

        NOTE: Currently disabled - all messages are retained permanently unless manually deleted.
        Manual cleanup available via delete_stream_history() / delete_private_history().
        """
        total_tokens = sum(msg.get("tokens", 0) for msg in messages)
        return messages, total_tokens

    def add_stream_message(
        self,
        stream_id: str,
        topic: str,
        role: str,
        content: str,
        sender_id: str,
        message_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        sender_full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a message to stream/topic history.

        Args:
            stream_id: Zulip stream ID or name
            topic: Topic name
            role: 'user' or 'assistant'
            content: Message content
            sender_id: User email or identifier
            message_id: Optional Zulip message ID
            config: Optional history configuration
            sender_full_name: Display name of the sender

        Returns:
            Dict with status and token info
        """
        file_path = self._get_stream_file_path(stream_id, topic)
        history = self._load_history_file(file_path)

        message = {
            "role": role,
            "content": content,
            "sender_id": sender_id,
            "sender_full_name": sender_full_name,
            "message_id": message_id,
            "timestamp": time.time(),
            "tokens": self._count_tokens(content),
        }

        history["messages"].append(message)
        history["total_tokens"] += message["tokens"]

        self._save_history_file(file_path, history)

        return {
            "success": True,
            "tokens_added": message["tokens"],
            "total_tokens": history["total_tokens"],
            "message_count": len(history["messages"]),
        }

    def add_private_message(
        self,
        user_email: str,
        role: str,
        content: str,
        sender_id: str,
        message_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        sender_full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a message to private DM history.

        Args:
            user_email: User email (conversation identifier)
            role: 'user' or 'assistant'
            content: Message content
            sender_id: Sender email or identifier
            message_id: Optional Zulip message ID
            config: Optional history configuration
            sender_full_name: Display name of the sender

        Returns:
            Dict with status and token info
        """
        file_path = self._get_private_file_path(user_email)
        history = self._load_history_file(file_path)

        message = {
            "role": role,
            "content": content,
            "sender_id": sender_id,
            "sender_full_name": sender_full_name,
            "message_id": message_id,
            "timestamp": time.time(),
            "tokens": self._count_tokens(content),
        }

        history["messages"].append(message)
        history["total_tokens"] += message["tokens"]

        self._save_history_file(file_path, history)

        return {
            "success": True,
            "tokens_added": message["tokens"],
            "total_tokens": history["total_tokens"],
            "message_count": len(history["messages"]),
        }

    def get_stream_messages(
        self, stream_id: str, topic: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent messages from stream/topic history.

        Args:
            stream_id: Zulip stream ID or name
            topic: Topic name
            limit: Optional limit on number of messages

        Returns:
            List of messages (most recent first)
        """
        file_path = self._get_stream_file_path(stream_id, topic)
        history = self._load_history_file(file_path)

        messages: List[Dict[str, Any]] = history.get("messages", [])

        if limit and limit > 0:
            messages = messages[-limit:]

        return messages[::-1]

    def get_private_messages(
        self, user_email: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent messages from private DM history.

        Args:
            user_email: User email
            limit: Optional limit on number of messages

        Returns:
            List of messages (most recent first)
        """
        file_path = self._get_private_file_path(user_email)
        history = self._load_history_file(file_path)

        messages: List[Dict[str, Any]] = history.get("messages", [])

        if limit and limit > 0:
            messages = messages[-limit:]

        return messages[::-1]

    def get_stream_history_info(self, stream_id: str, topic: str) -> Dict[str, Any]:
        """Get history info for a stream/topic.

        Args:
            stream_id: Zulip stream ID or name
            topic: Topic name

        Returns:
            Dict with message_count, total_tokens, config, and last_updated
        """
        file_path = self._get_stream_file_path(stream_id, topic)
        history = self._load_history_file(file_path)

        return {
            "message_count": len(history.get("messages", [])),
            "total_tokens": history.get("total_tokens", 0),
            "config": history.get("config", {}),
            "last_updated": history.get("last_updated", 0),
        }

    def get_private_history_info(self, user_email: str) -> Dict[str, Any]:
        """Get history info for a private DM.

        Args:
            user_email: User email

        Returns:
            Dict with message_count, total_tokens, config, and last_updated
        """
        file_path = self._get_private_file_path(user_email)
        history = self._load_history_file(file_path)

        return {
            "message_count": len(history.get("messages", [])),
            "total_tokens": history.get("total_tokens", 0),
            "config": history.get("config", {}),
            "last_updated": history.get("last_updated", 0),
        }

    def list_stream_topics(self, stream_id: str) -> List[Dict[str, Any]]:
        """List all topics with history for a stream.

        Args:
            stream_id: Zulip stream ID or name

        Returns:
            List of topic info dicts with name, message_count, etc.
        """
        stream_hash = self._hash_id(stream_id)
        stream_dir = self.streams_dir / stream_hash

        if not stream_dir.exists():
            return []

        topics = []
        for file_path in stream_dir.iterdir():
            if file_path.suffix == ".json":
                try:
                    history = self._load_history_file(file_path)
                    messages = history.get("messages", [])

                    topics.append(
                        {
                            "topic_hash": file_path.stem,
                            "message_count": len(messages),
                            "total_tokens": history.get("total_tokens", 0),
                            "last_updated": history.get("last_updated", 0),
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to load topic file {file_path}: {e}")

        topics.sort(key=lambda x: x.get("last_updated", 0), reverse=True)
        return topics

    def cleanup_stream_history(
        self, stream_id: str, topic: str, force: bool = False
    ) -> Dict[str, Any]:
        """Cleanup stream history (manual trigger).

        NOTE: Automatic cleanup is disabled. Use delete_stream_history() for manual deletion.

        Args:
            stream_id: Zulip stream ID or name
            topic: Topic name
            force: Unused - kept for API compatibility

        Returns:
            Dict with info message
        """
        file_path = self._get_stream_file_path(stream_id, topic)
        history = self._load_history_file(file_path)

        messages = history.get("messages", [])
        total_tokens = history.get("total_tokens", 0)

        return {
            "success": True,
            "message": (
                "Automatic cleanup is disabled. All messages retained permanently. "
                "Use /pc clear to delete manually."
            ),
            "total_tokens": total_tokens,
            "message_count": len(messages),
        }

    def cleanup_private_history(self, user_email: str, force: bool = False) -> Dict[str, Any]:
        """Cleanup private history (manual trigger).

        NOTE: Automatic cleanup is disabled. Use delete_private_history() for manual deletion.

        Args:
            user_email: User email
            force: Unused - kept for API compatibility

        Returns:
            Dict with info message
        """
        file_path = self._get_private_file_path(user_email)
        history = self._load_history_file(file_path)

        messages = history.get("messages", [])
        total_tokens = history.get("total_tokens", 0)

        return {
            "success": True,
            "message": (
                "Automatic cleanup is disabled. All messages retained permanently. "
                "Use /pc clear to delete manually."
            ),
            "total_tokens": total_tokens,
            "message_count": len(messages),
        }

    def delete_stream_history(self, stream_id: str, topic: Optional[str] = None) -> bool:
        """Delete stream history file(s).

        Args:
            stream_id: Zulip stream ID or name
            topic: Optional topic name. If None, deletes entire stream.

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            if topic:
                file_path = self._get_stream_file_path(stream_id, topic)
                if file_path.exists():
                    file_path.unlink()
                    return True
            else:
                stream_hash = self._hash_id(stream_id)
                stream_dir = self.streams_dir / stream_hash
                if stream_dir.exists():
                    import shutil

                    shutil.rmtree(stream_dir)
                    return True
        except Exception as e:
            logger.error(f"Failed to delete stream history: {e}")

        return False

    def delete_private_history(self, user_email: str) -> bool:
        """Delete private history file.

        Args:
            user_email: User email

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            file_path = self._get_private_file_path(user_email)
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception as e:
            logger.error(f"Failed to delete private history: {e}")

        return False

    def _process_topic_file(self, topic_file: Path) -> tuple[int, int] | None:
        """Process a single topic file and return message/token counts.

        Args:
            topic_file: Path to the topic file

        Returns:
            Tuple of (message_count, token_count) or None if failed
        """
        try:
            history = self._load_history_file(topic_file)
            msg_count = len(history.get("messages", []))
            token_count = history.get("total_tokens", 0)
            return msg_count, token_count
        except Exception as e:
            logger.error(f"Failed to load topic file {topic_file}: {e}")
            return None

    def _collect_stream_topics(self, stream_dir: Path) -> tuple[int, int, int]:
        """Collect statistics for all topics in a stream directory.

        Args:
            stream_dir: Path to the stream directory

        Returns:
            Tuple of (total_messages, total_tokens, topic_count)
        """
        stream_messages = 0
        stream_tokens = 0
        topic_count = 0

        for topic_file in stream_dir.glob("*.json"):
            if topic_file.name == "config.json":
                continue
            result = self._process_topic_file(topic_file)
            if result:
                msg_count, token_count = result
                stream_messages += msg_count
                stream_tokens += token_count
                topic_count += 1

        return stream_messages, stream_tokens, topic_count

    def _collect_stream_stats(self, limit: int, total_files: int) -> tuple[Dict[str, Any], int]:
        """Collect statistics for stream history.

        Args:
            limit: Maximum number of entries to return
            total_files: Current total files count

        Returns:
            Tuple of (stream stats dict, updated total_files count)
        """
        stats: Dict[str, Any] = {
            "count": 0,
            "total_messages": 0,
            "total_tokens": 0,
            "entries": [],
        }

        if not self.streams_dir.exists():
            return stats, total_files

        for stream_dir in self.streams_dir.iterdir():
            if not stream_dir.is_dir():
                continue

            stream_hash = stream_dir.name
            stream_messages, stream_tokens, topic_count = self._collect_stream_topics(stream_dir)
            total_files += topic_count

            if topic_count > 0:
                stats["count"] += 1
                stats["total_messages"] += stream_messages
                stats["total_tokens"] += stream_tokens

                if len(stats["entries"]) < limit:
                    stats["entries"].append(
                        {
                            "stream_hash": stream_hash,
                            "topics": topic_count,
                            "messages": stream_messages,
                            "tokens": stream_tokens,
                        }
                    )

        stats["entries"].sort(key=lambda x: x["messages"], reverse=True)
        return stats, total_files

    def _collect_private_stats(self, limit: int, total_files: int) -> tuple[Dict[str, Any], int]:
        """Collect statistics for private history.

        Args:
            limit: Maximum number of entries to return
            total_files: Current total files count

        Returns:
            Tuple of (private stats dict, updated total_files count)
        """
        stats: Dict[str, Any] = {
            "count": 0,
            "total_messages": 0,
            "total_tokens": 0,
            "entries": [],
        }

        if not self.private_dir.exists():
            return stats, total_files

        for user_file in self.private_dir.glob("*.json"):
            try:
                history = self._load_history_file(user_file)
                msg_count = len(history.get("messages", []))
                token_count = history.get("total_tokens", 0)

                stats["count"] += 1
                stats["total_messages"] += msg_count
                stats["total_tokens"] += token_count
                total_files += 1

                if len(stats["entries"]) < limit:
                    stats["entries"].append(
                        {
                            "user_hash": user_file.stem,
                            "messages": msg_count,
                            "tokens": token_count,
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to load private history file {user_file}: {e}")

        stats["entries"].sort(key=lambda x: x["messages"], reverse=True)
        return stats, total_files

    def get_storage_stats(self, limit: int = 30) -> Dict[str, Any]:
        """Get storage statistics for observability.

        Args:
            limit: Maximum number of entries to return in detailed lists

        Returns:
            Dict containing storage statistics
        """
        total_files = 0

        stream_stats, total_files = self._collect_stream_stats(limit, total_files)
        private_stats, total_files = self._collect_private_stats(limit, total_files)

        return {
            "streams": stream_stats,
            "private": private_stats,
            "total_files": total_files,
            "storage_path": str(self.history_dir),
        }
