"""Handles Zulip API interactions."""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

import zulip

logger = logging.getLogger(__name__)


class ZulipHandler:
    """Manages Zulip connection and message handling."""

    def __init__(
        self,
        zuliprc_path: str,
        config_path: str,
        llm_client,
        policy_engine,
        admin_handler,
    ):
        """Initialize Zulip handler.

        Args:
            zuliprc_path: Path to zuliprc file
            config_path: Path to configuration directory
            llm_client: LLM client instance
            policy_engine: Policy engine instance
            admin_handler: Admin command handler instance
        """
        self.client = zulip.Client(config_file=zuliprc_path)
        self.config_path = config_path
        self.llm_client = llm_client
        self.policy_engine = policy_engine
        self.admin_handler = admin_handler

        # PC client for history storage (may be None if not configured)
        self.pc_client = getattr(llm_client, "pc_client", None)
        if not self.pc_client:
            logger.warning("PC client not available - history functionality disabled")

        # Get bot's own email
        result = self.client.get_profile()
        if result["result"] == "success":
            self.bot_email: str = result["email"]
            self.bot_id: int = result["user_id"]
            self.bot_full_name: str = result.get("full_name", "Bot")
            logger.info(f"Bot email: {self.bot_email}")
            logger.info(f"Bot full name: {self.bot_full_name}")
        else:
            raise Exception(f"Failed to get bot profile: {result}")

        # Load subscribed streams from state
        self.subscribed_streams = self._load_subscriptions()

    def get_bot_email(self) -> str:
        """Get bot's email address.

        Returns:
            The bot's email address.
        """
        return self.bot_email

    def _hash_user_email(self, email: str) -> str:
        """Create a consistent hash for user email (for storage without exposing email).

        Args:
            email: User email address to hash.

        Returns:
            16-character hex hash of the email.
        """
        return hashlib.sha256(email.encode()).hexdigest()[:16]

    def _load_subscriptions(self) -> set:
        """Load previously subscribed streams from state file.

        Returns:
            Set of stream names the bot was previously subscribed to.
        """
        state_file = f"{self.config_path}/state.json"
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return set(state.get("subscriptions", []))
        except FileNotFoundError:
            return set()

    def _save_subscriptions(self) -> None:
        """Save subscribed streams to state file."""
        state_file = f"{self.config_path}/state.json"
        # Preserve other state keys (e.g., stream_policies)
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except FileNotFoundError:
            state = {}
        state["subscriptions"] = list(self.subscribed_streams)
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

    def subscribe_to_stream(self, stream_name: str) -> Dict[str, Any]:
        """Subscribe bot to a stream.

        Args:
            stream_name: Name of the stream to subscribe to.

        Returns:
            Dict containing the subscription result.
        """
        result = self.client.add_subscriptions([{"name": stream_name}])

        if result["result"] == "success":
            self.subscribed_streams.add(stream_name)
            self._save_subscriptions()
            logger.info(f"Subscribed to stream: {stream_name}")
        else:
            logger.error(f"Failed to subscribe to {stream_name}: {result}")

        return dict(result)

    def unsubscribe_from_stream(self, stream_name: str) -> Dict[str, Any]:
        """Unsubscribe bot from a stream.

        Args:
            stream_name: Name of the stream to unsubscribe from.

        Returns:
            Dict containing the unsubscription result.
        """
        result = self.client.remove_subscriptions([stream_name])

        if result["result"] == "success":
            self.subscribed_streams.discard(stream_name)
            self._save_subscriptions()
            logger.info(f"Unsubscribed from stream: {stream_name}")
        else:
            logger.error(f"Failed to unsubscribe from {stream_name}: {result}")

        return dict(result)

    def send_message(
        self, message_type: str, to: str, content: str, subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to Zulip.

        Args:
            message_type: Type of message ('private' or 'stream').
            to: Recipient (email for private, stream name for stream).
            content: Message content to send.
            subject: Optional subject/topic for stream messages.

        Returns:
            Dict containing the send result.
        """
        request = {
            "type": message_type,
            "to": to,
            "content": content,
        }

        if subject:
            request["subject"] = subject

        result = self.client.send_message(request)
        if result["result"] != "success":
            logger.error(f"Failed to send message: {result}")

        return dict(result)

    def handle_message(self, msg: Dict[str, Any]) -> None:
        """Process incoming message.

        Args:
            msg: The incoming Zulip message dict.

        Returns:
            None
        """
        # LOG EVERY MESSAGE RECEIVED
        sender_email_raw = msg.get("sender_email", "")
        sender_hash = self._hash_user_email(sender_email_raw) if sender_email_raw else "unknown"
        logger.info(f"=== RECEIVED MESSAGE === Type: {msg.get('type')}, From: {sender_hash}")
        logger.info(f"Message content preview: {msg.get('content', '')[:100]}")

        # Ignore own messages
        if msg.get("sender_email") == self.bot_email:
            logger.debug("Ignoring own message")
            return

        message_type = msg.get("type")
        sender_email = msg.get("sender_email", "")

        sender_hash = self._hash_user_email(sender_email) if sender_email else "unknown"
        logger.info(f"Processing {message_type} from {sender_hash}")

        # Handle DM (private messages)
        if message_type == "private":
            logger.info("Handling as DM")
            self._handle_dm(msg)

        # Handle stream messages
        elif message_type == "stream":
            logger.info("Handling as stream message")
            self._handle_stream_message(msg)
        else:
            logger.warning(f"Unknown message type: {message_type}")

    def _handle_dm(self, msg: Dict[str, Any]) -> None:
        """Handle direct messages (admin commands or conversation).

        Args:
            msg: The incoming DM message dict.
        """
        sender_email = msg["sender_email"]
        content = msg["content"].strip()

        logger.info(f"DM from {sender_email}: {content}")

        # Check if sender is admin
        if not self.admin_handler.is_admin(sender_email):
            logger.warning(f"Unauthorized command attempt from: {sender_email}")
            self.send_message(
                message_type="private",
                to=sender_email,
                content="❌ Unauthorized. Only admins can control this bot.",
            )
            return

        # Check if message is a command (starts with /)
        if content.startswith("/"):
            # Process admin command
            logger.info(f"Processing admin command: {content}")
            response = self.admin_handler.process_command(content, self, sender_email)

            if response:
                self.send_message(message_type="private", to=sender_email, content=response)
        else:
            # Handle as conversation
            logger.info(f"Processing DM conversation from {sender_email}")
            response = self._handle_dm_conversation(sender_email, content)

            if response:
                self.send_message(message_type="private", to=sender_email, content=response)

    def _store_dm_user_message(
        self, sender_email: str, content: str, policy: Dict[str, Any]
    ) -> None:
        """Store user DM message in PC history.

        Args:
            sender_email: Email address of the sender.
            content: Message content.
            policy: Policy configuration dict.
        """
        if not self.pc_client:
            return

        try:
            sender_display_name = sender_email.split("@")[0]
            memory_config = policy.get("memory", {})
            self.pc_client.add_private_message(
                user_email=sender_email,
                role="user",
                content=content,
                sender_id=self._hash_user_email(sender_email),
                config=memory_config,
                sender_full_name=sender_display_name,
            )
            logger.info(f"Stored user DM message in PC history for {sender_email}")
        except Exception as e:
            logger.error(f"Failed to store DM message in PC: {e}", exc_info=True)

    def _store_dm_bot_response(
        self, sender_email: str, response: str, policy: Dict[str, Any]
    ) -> None:
        """Store bot DM response in PC history.

        Args:
            sender_email: Email address of the sender.
            response: Bot's response text.
            policy: Policy configuration dict.
        """
        if not self.pc_client:
            return

        try:
            memory_config = policy.get("memory", {})
            self.pc_client.add_private_message(
                user_email=sender_email,
                role="assistant",
                content=response,
                sender_id="bot",
                config=memory_config,
                sender_full_name=self.bot_full_name,
            )
            logger.info(f"Stored bot DM response in PC history for {sender_email}")
        except Exception as e:
            logger.error(f"Failed to store bot DM response in PC: {e}", exc_info=True)

    def _generate_dm_response(self, sender_email: str, content: str, policy: Dict[str, Any]) -> str:
        """Generate LLM response for DM.

        Args:
            sender_email: Email address of the sender.
            content: Message content.
            policy: Policy configuration dict.

        Returns:
            Generated response text.
        """
        policy_name = self.policy_engine.get_policy_name_for_admin_dm(sender_email) or "pc-enabled"
        logger.info(f"Generating DM response for admin {sender_email} using policy: {policy_name}")

        llm_messages = [{"role": "user", "content": content}]
        response: str = self.llm_client.generate_response(
            messages=llm_messages,
            policy=policy,
            user=self._hash_user_email(sender_email),
            user_email=sender_email,
        )
        return response

    def _handle_dm_conversation(self, sender_email: str, content: str) -> str:
        """Handle DM conversation with admin using admin-specific DM policy.

        Args:
            sender_email: Email address of the sender.
            content: Message content.

        Returns:
            Response text from the bot.
        """
        try:
            policy = self.policy_engine.get_policy_for_admin_dm(sender_email)

            if not policy:
                logger.error(f"Policy for admin '{sender_email}' not found")
                return "⚠️ Sorry, I encountered an error processing your request."

            self._store_dm_user_message(sender_email, content, policy)
            llm_response = self._generate_dm_response(sender_email, content, policy)
            self._store_dm_bot_response(sender_email, llm_response, policy)

            return llm_response

        except Exception as e:
            logger.error(f"Error handling DM conversation: {e}", exc_info=True)
            return "⚠️ Sorry, I encountered an error processing your request."

    def _get_sender_display_name(self, msg: Dict[str, Any]) -> str:
        """Get sender's display name from message.

        Args:
            msg: The message dict containing sender info.

        Returns:
            Display name for the sender.
        """
        sender_full_name: Optional[str] = msg.get("sender_full_name")
        if sender_full_name:
            return sender_full_name
        sender_email: str = msg.get("sender_email", "")
        return sender_email.split("@")[0]

    def _store_user_message_in_pc(
        self,
        msg: Dict[str, Any],
        stream_name: str,
        subject: str,
        sender_email: str,
        policy: Dict[str, Any],
    ) -> None:
        """Store user message in PC history.

        Args:
            msg: The incoming stream message dict.
            stream_name: Name of the stream.
            subject: Topic/subject name.
            sender_email: Sender's email address.
            policy: Policy configuration dict.
        """
        if not self.pc_client:
            return

        try:
            sender_full_name = self._get_sender_display_name(msg)
            memory_config = policy.get("memory", {})
            self.pc_client.add_stream_message(
                stream_id=stream_name,
                topic=subject,
                role="user",
                content=msg.get("content", ""),
                sender_id=self._hash_user_email(sender_email),
                message_id=msg.get("id"),
                config=memory_config,
                sender_full_name=sender_full_name,
            )
            logger.info(f"Stored stream message in PC history for {stream_name}/{subject}")
        except Exception as e:
            logger.error(f"Failed to store stream message in PC: {e}", exc_info=True)

    def _store_bot_response_in_pc(
        self,
        stream_name: str,
        subject: str,
        response: str,
        policy: Dict[str, Any],
    ) -> None:
        """Store bot response in PC history.

        Args:
            stream_name: Name of the stream.
            subject: Topic/subject name.
            response: Bot's response text.
            policy: Policy configuration dict.
        """
        if not self.pc_client:
            return

        try:
            memory_config = policy.get("memory", {})
            self.pc_client.add_stream_message(
                stream_id=stream_name,
                topic=subject,
                role="assistant",
                content=response,
                sender_id="bot",
                config=memory_config,
                sender_full_name=self.bot_full_name,
            )
            logger.info(f"Stored bot response in PC history for {stream_name}/{subject}")
        except Exception as e:
            logger.error(f"Failed to store bot response in PC: {e}", exc_info=True)

    def _generate_and_send_response(
        self,
        msg: Dict[str, Any],
        stream_name: str,
        subject: str,
        policy: Dict[str, Any],
    ) -> None:
        """Generate LLM response and send it.

        Args:
            msg: The incoming stream message dict.
            stream_name: Name of the stream.
            subject: Topic/subject name.
            policy: Policy configuration dict.
        """
        try:
            logger.info("Generating LLM response...")

            content = msg.get("content", "")
            sender_email = msg.get("sender_email", "")
            llm_messages = [{"role": "user", "content": content}]

            llm_response = self.llm_client.generate_response(
                messages=llm_messages,
                policy=policy,
                user=self._hash_user_email(sender_email),
                stream_id=stream_name,
                topic=subject,
            )

            logger.info(f"LLM response received: {llm_response[:100]}")

            self._store_bot_response_in_pc(stream_name, subject, llm_response, policy)

            sender_full_name = self._get_sender_display_name(msg)
            mention = f"@**{sender_full_name}**"
            if llm_response.startswith(mention):
                reply_content = llm_response
            else:
                reply_content = f"{mention} {llm_response}"

            self.send_message(
                message_type="stream",
                to=stream_name,
                subject=subject,
                content=reply_content,
            )

            logger.info("Response sent successfully")

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)

    def _handle_stream_message(self, msg: Dict[str, Any]) -> None:
        """Handle messages in streams.

        Args:
            msg: The incoming stream message dict.
        """
        stream_name = msg.get("display_recipient", "")
        subject = msg.get("subject", "")
        sender_email = msg.get("sender_email", "")

        logger.info(f"Stream message - Channel: {stream_name}, Subject: {subject}")
        logger.info(f"Subscribed streams: {self.subscribed_streams}")

        if stream_name not in self.subscribed_streams:
            logger.info(f"Not subscribed to {stream_name}, ignoring")
            return

        logger.info(f"Processing message in subscribed stream: {stream_name}")

        policy = self.policy_engine.get_policy_for_stream(stream_name)
        if not policy:
            logger.warning(f"No policy set for stream: {stream_name}")
            return

        logger.info(f"Policy found for {stream_name}")

        self._store_user_message_in_pc(msg, stream_name, subject, sender_email, policy)

        if not self._should_respond(msg, policy):
            logger.info("Should respond: False")
            return

        logger.info("Should respond: True")
        self._generate_and_send_response(msg, stream_name, subject, policy)

    def _should_respond(self, msg: Dict[str, Any], policy: Dict[str, Any]) -> bool:
        """Determine if bot should respond to this message.

        Args:
            msg: The incoming message dict.
            policy: Policy configuration dict.

        Returns:
            True if the bot should respond, False otherwise.
        """
        content = msg.get("content", "")
        triggers = policy.get("triggers", {})

        logger.info(f"Checking triggers - mention_required: {triggers.get('mention_required')}")
        logger.info(f"Message content: {content}")

        # Check if mention is required
        if triggers.get("mention_required", True):
            # Check for @mention - try multiple formats
            mention_patterns = [
                f"@**{self.bot_full_name}**",  # Full name mention
                f"@**{self.bot_email.split('@')[0]}**",  # Email prefix mention
            ]

            found_mention = False
            for pattern in mention_patterns:
                if pattern in content:
                    found_mention = True
                    logger.info(f"Found mention pattern: {pattern}")
                    break

            if not found_mention:
                logger.info(f"No mention found. Tried patterns: {mention_patterns}")
                return False

        # Check keywords
        keywords = triggers.get("keywords", [])
        if keywords:
            content_lower = content.lower()
            if not any(keyword.lower() in content_lower for keyword in keywords):
                logger.info(f"No matching keywords found from: {keywords}")
                return False

        logger.info("All trigger conditions met, will respond")
        return True

    def start(self) -> None:
        """Start listening to messages.

        Returns:
            None
        """
        logger.info("Starting message listener...")

        # Subscribe to all previously subscribed streams
        for stream in self.subscribed_streams:
            logger.info(f"Re-subscribing to: {stream}")
            self.subscribe_to_stream(stream)

        logger.info("Starting event loop...")
        # Start event loop
        self.client.call_on_each_message(self.handle_message)
