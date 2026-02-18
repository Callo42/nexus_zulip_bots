"""Client for interacting with LiteLLM gateway with PC tool support.

This module provides an interface to LiteLLM for generating responses and handling
tool calls with the PC sidecar. It supports conversation history, policy-based
model selection, and iterative tool execution.

Tool Calling Flow:
    The client supports iterative tool execution with the following flow:

    1. Initial Request: Send messages to LLM with available tools
    2. Tool Decision: LLM decides to either:
       - Return a direct response (no tools needed)
       - Request tool execution (returns tool_calls)
    3. Tool Execution: If tool_calls present:
       - Execute each tool via PC client
       - Collect results
       - Append results to conversation
    4. Iteration: Send updated conversation back to LLM
    5. Repeat: Continue until max_iterations reached or LLM returns final response

    Max iterations default is 3 (configurable via policy). When exceeded,
    system extracts error messages and returns user-friendly error.

Error Handling:
    - Malformed XML Detection: Some models output tool calls as XML tags
      (e.g., `<｜DSML｜function_calls>`) instead of proper JSON. System
      detects these patterns and falls back to regular generation without tools.

    - Tool Execution Failures: Errors extracted using regex pattern
      and returned with ❌ emoji prefix.

    - Fallback Mechanisms: If LLM calls fail or tool execution errors occur,
      system gracefully falls back to regular generation without tool support.

Security:
    - Command validation against dangerous patterns (rm -rf, mkfs, etc.)
    - Sensitive information filtering in logs (passwords, API keys)
    - All tool execution goes through PC client security controls

Example:
    >>> client = LLMClient(
    ...     litellm_url="http://litellm:4000",
    ...     pc_client=pc_client,
    ...     policy_engine=policy_engine
    ... )
    >>> response = client.generate_response_with_history_and_tools(
    ...     messages=[{"role": "user", "content": "Hello"}],
    ...     policy=policy,
    ...     stream_id="general",
    ...     topic="test"
    ... )
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from src.formatters import convert_latex_to_zulip_katex

logger = logging.getLogger(__name__)


class LLMClient:
    """Handles LLM API calls via LiteLLM."""

    def __init__(self, litellm_url: str, ollama_url: str, pc_client=None, policy_engine=None):
        """Initialize LLM client.

        Args:
            litellm_url: URL of the LiteLLM gateway
            ollama_url: URL of the Ollama API
            pc_client: Optional PC client for tool/history operations
            policy_engine: Optional policy engine for model formatting
        """
        self.litellm_url = litellm_url.rstrip("/")
        self.ollama_url = ollama_url
        self.pc_client = pc_client
        self.policy_engine = policy_engine

        # Get master key from environment
        self.master_key = os.getenv("LITELLM_MASTER_KEY", "")

        if not self.master_key:
            logger.warning("LITELLM_MASTER_KEY not set - requests may fail")
        else:
            logger.info("LiteLLM master key loaded")

        logger.info(f"LLM Client initialized: {self.litellm_url}")
        if pc_client:
            logger.info("PC client available for tool calls")
        if policy_engine:
            logger.info("Policy engine available for model formatting")

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        policy: Dict[str, Any],
        user: str = "unknown",
        stream_id: Optional[str] = None,
        topic: Optional[str] = None,
        user_email: Optional[str] = None,
        sender_full_name: Optional[str] = None,
    ) -> str:
        """Generate response from LLM based on policy.

        Args:
            messages: List of conversation messages.
            policy: Policy configuration dict.
            user: User identifier for audit logging.
            stream_id: Optional stream ID for history storage.
            topic: Optional topic name for history storage.
            user_email: Optional user email for private history.
            sender_full_name: Optional full name of the sender (for current user display).

        Returns:
            Generated response text from LLM.
        """
        # Use new history and tool enabled generation
        try:
            response = self.generate_response_with_history_and_tools(
                messages=messages,
                policy=policy,
                user=user,
                stream_id=stream_id,
                topic=topic,
                user_email=user_email,
                sender_full_name=sender_full_name,
            )
            return convert_latex_to_zulip_katex(response)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            # Don't expose internal error details to users
            return "⚠️ Sorry, I encountered an error processing your request."

    def _get_lookback_count(
        self,
        stream_id: Optional[str],
        user_email: Optional[str],
    ) -> Optional[int]:
        """Determine lookback count for history loading.

        Priority: dynamic config > policy default > 100

        Args:
            stream_id: Zulip stream ID for stream history
            user_email: User email for private DM history

        Returns:
            Lookback count or None to use policy default
        """
        if not self.policy_engine:
            return None

        lookback: Optional[int] = None

        if stream_id:
            lookback = self.policy_engine.get_lookback_for_stream(stream_id)
            logger.debug(f"Using lookback count {lookback} for stream {stream_id}")
        elif user_email:
            lookback = self.policy_engine.get_lookback_for_dm(user_email)
            logger.debug(f"Using lookback count {lookback} for DM with {user_email}")

        return lookback

    def _build_enhanced_system_prompt(
        self,
        policy: Dict[str, Any],
        user_map: Dict[str, str],
        history_lines: List[str],
        stats: Dict[str, Any],
    ) -> str:
        """Build enhanced system prompt with context.

        Args:
            policy: Policy configuration
            user_map: User mapping dict
            history_lines: Conversation history lines
            stats: Message statistics

        Returns:
            Enhanced system prompt string
        """
        base_system_prompt = policy.get("system_prompt", "You are a helpful assistant.")

        context_parts = [
            "=" * 60,
            "ZULIP CONVERSATION CONTEXT (Reference Only)",
            "=" * 60,
        ]

        if user_map:
            context_parts.append("\nUsers in this conversation:")
            for _sender_id, display_name in user_map.items():
                context_parts.append(f"  • {display_name}")

        if history_lines:
            context_parts.append("\nConversation History:")
            for line in history_lines:
                context_parts.append(f"  {line}")

        if stats.get("unique_user_count", 0) > 0:
            context_parts.append(
                f"\nStatistics: {stats.get('user_count', 0)} user messages from "
                f"{stats.get('unique_user_count', 0)} user(s), "
                f"{stats.get('assistant_count', 0)} bot responses."
            )

        context_parts.extend(
            [
                "",
                "-" * 60,
                "Note: The above is conversation context from Zulip. Use it as reference",
                "to understand the discussion, but always follow the instructions in",
                "[SYSTEM_INSTRUCTION] section above.",
                "-" * 60,
            ]
        )

        zulip_context = "\n".join(context_parts)
        return f"""[SYSTEM_INSTRUCTION - HIGHEST PRIORITY]
{"=" * 60}
{base_system_prompt}
{"=" * 60}

{zulip_context}"""

    def _log_system_prompt(self, prompt: str) -> None:
        """Log system prompt for debugging.

        Args:
            prompt: System prompt to log
        """
        logger.info("=" * 80)
        logger.info("GENERATED SYSTEM PROMPT (for debugging)")
        logger.info("=" * 80)
        for line in prompt.split("\n"):
            logger.info(f"  {line}")
        logger.info("=" * 80)

    def _prepare_llm_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        user_map: Dict[str, str],
        user: str,
        sender_full_name: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Prepare LLM messages with system prompt and user prefixes.

        Args:
            messages: Current conversation messages
            system_prompt: Enhanced system prompt
            user_map: User mapping dict
            user: Current user identifier
            sender_full_name: Optional full name of the current sender.

        Returns:
            List of messages for LLM
        """
        llm_messages = [{"role": "system", "content": system_prompt}]
        # Use provided sender_full_name if available, otherwise look up from user_map
        current_user_name = sender_full_name if sender_full_name else user_map.get(user, user)

        for msg in messages:
            if msg["role"] == "user":
                prefixed_content = f"{current_user_name}: {msg['content']}"
                llm_messages.append({"role": "user", "content": prefixed_content})

        return llm_messages

    def generate_response_with_history_and_tools(
        self,
        messages: List[Dict[str, str]],
        policy: Dict[str, Any],
        user: str = "unknown",
        stream_id: Optional[str] = None,
        topic: Optional[str] = None,
        user_email: Optional[str] = None,
        sender_full_name: Optional[str] = None,
    ) -> str:
        """Generate response with history and tool support.

        Args:
            messages: Current conversation messages
            policy: Policy configuration
            user: User identifier (for audit)
            stream_id: Zulip stream ID (for stream history)
            topic: Topic name (for stream history)
            user_email: User email (for private DM history)
            sender_full_name: Optional full name of the sender (for current user display).

        Returns:
            Response text
        """
        original_messages = messages.copy()

        if not self.pc_client:
            logger.warning("PC client not available, falling back to regular generation")
            return self._regular_generate(original_messages, policy)

        lookback_count = self._get_lookback_count(stream_id, user_email)
        history_lines, user_map, stats = self._load_history_from_pc(
            stream_id, topic, user_email, policy, lookback_count=lookback_count
        )

        enhanced_system_prompt = self._build_enhanced_system_prompt(
            policy, user_map, history_lines, stats
        )
        self._log_system_prompt(enhanced_system_prompt)

        llm_messages = self._prepare_llm_messages(
            messages, enhanced_system_prompt, user_map, user, sender_full_name
        )

        tools_enabled = policy.get("tools", {}).get("enabled", False)
        max_iterations = policy.get("tools", {}).get("max_iterations", 10)

        if tools_enabled:
            tools_response = self.pc_client.list_tools_openai(allowed_only=True)
            tools = tools_response.get("tools", [])

            if tools:
                return self._generate_with_tool_calls(
                    llm_messages, policy, tools, max_iterations, user
                )

        return self._regular_generate(llm_messages, policy)

    def _load_history_from_pc(
        self,
        stream_id: Optional[str],
        topic: Optional[str],
        user_email: Optional[str],
        policy: Dict[str, Any],
        lookback_count: Optional[int] = None,
    ) -> tuple[List[str], Dict[str, str], Dict[str, Any]]:
        """Load conversation history from PC and format as history lines.

        Loads historical messages from PC sidecar history storage and formats
        them as text lines for inclusion in the system prompt.

        Args:
            stream_id: Zulip stream ID for stream history.
            topic: Topic name for stream history.
            user_email: User email for private DM history.
            policy: Policy configuration containing history settings.
            lookback_count: Optional override for number of messages to load.
                Defaults to policy's lookback_messages or 100.

        Returns:
            Tuple of (history_lines, user_map, stats):
            - history_lines: List of formatted history text lines (oldest first).
            - user_map: Dict mapping sender identifiers to display names.
            - stats: Dict with message counts by role.

        Raises:
            No exceptions raised; errors are logged and empty list returned.
        """
        if not self.pc_client:
            return [], {}, {}

        memory_config = policy.get("memory", {})
        if not memory_config.get("enabled", True):
            return [], {}, {}

        # Priority: explicit lookback_count > policy default > 100
        lookback = (
            lookback_count
            if lookback_count is not None
            else memory_config.get("lookback_messages", 100)
        )

        try:
            messages = self._fetch_messages(stream_id, topic, user_email, lookback)
            if not messages:
                return [], {}, {}

            return self._process_messages(messages)

        except Exception as e:
            logger.error(f"Failed to load history from PC: {e}", exc_info=True)
            return [], {}, {}

    def _fetch_messages(
        self,
        stream_id: Optional[str],
        topic: Optional[str],
        user_email: Optional[str],
        lookback: int,
    ) -> List[Dict[str, Any]]:
        """Fetch messages from PC based on history type."""
        assert self.pc_client is not None, "PC client must be available"  # nosec
        if stream_id and topic:
            stream_result: List[Dict[str, Any]] = self.pc_client.get_stream_messages(
                stream_id, topic, limit=lookback
            )
            return stream_result
        elif user_email:
            private_result: List[Dict[str, Any]] = self.pc_client.get_private_messages(
                user_email, limit=lookback
            )
            return private_result
        return []

    def _process_messages(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[List[str], Dict[str, str], Dict[str, Any]]:
        """Process messages to build user map, stats, and history lines."""
        user_map: Dict[str, str] = {}
        stats: Dict[str, Any] = {
            "user_count": 0,
            "assistant_count": 0,
            "unique_users": set(),
        }

        # First pass: build user map from all messages
        for msg in messages:
            if msg.get("role") == "system":
                continue
            sender = msg.get("sender") or msg.get("user", "unknown")
            sender_full_name = msg.get("sender_full_name")
            if sender_full_name and sender != "bot":
                user_map[sender] = sender_full_name

        # Convert to history text lines (oldest first for chronological order)
        history_lines = []
        for msg in reversed(messages):
            if msg.get("role") == "system":
                continue

            sender_id = msg.get("sender") or msg.get("user", "unknown")
            sender_name = user_map.get(sender_id, sender_id)
            original_content = msg.get("content", "")

            # Update stats
            if msg.get("role") == "user":
                stats["user_count"] += 1
                stats["unique_users"].add(sender_id)
            else:
                stats["assistant_count"] += 1

            # Format timestamp
            timestamp = msg.get("timestamp")
            time_prefix = ""
            if timestamp:
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
                time_prefix = f"[{time_str}] "

            # Format history line
            if msg.get("role") == "user":
                history_line = f"{time_prefix}{sender_name}: {original_content}"
            else:
                history_line = f"{time_prefix}Bot: {original_content}"

            history_lines.append(history_line)

        stats["unique_user_count"] = len(stats["unique_users"])
        del stats["unique_users"]

        return history_lines, user_map, stats

    def _is_reasoning_enabled(self, model: str, policy: Dict[str, Any]) -> bool:
        """Check if reasoning should be enabled for the model.

        Args:
            model: Model identifier.
            policy: Policy configuration dict.

        Returns:
            True if reasoning is enabled for the model.
        """
        if self.policy_engine:
            model_config = self.policy_engine.get_model_config(model)
            if model_config:
                formatting = model_config.get("formatting", {})
                reasoning_config = formatting.get("reasoning", {})
                is_reasoning_enabled: bool = reasoning_config.get("enabled", False)
                return is_reasoning_enabled
        # Fallback to old field (temporary)
        fallback_enabled: bool = policy.get("reasoning_enabled", False)
        return fallback_enabled

    def _check_xml_tool_calls(self, content: str) -> bool:
        """Check if content contains malformed XML tool calls.

        Args:
            content: Content string to check.

        Returns:
            True if content contains XML tool call patterns.
        """
        return "<｜DSML｜function_calls>" in content or "<｜DSML｜invoke>" in content

    def _execute_tool_calls(
        self, tool_calls: List[Dict[str, Any]], user: str
    ) -> List[Dict[str, Any]]:
        """Execute tool calls via PC client and return results.

        Args:
            tool_calls: List of tool call definitions.
            user: User identifier for audit logging.

        Returns:
            List of tool execution results.
        """
        assert self.pc_client is not None, "PC client must be available"  # nosec
        tool_results = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])

            # Execute tool via PC
            tool_result = self.pc_client.execute_tool_call(tool_name, tool_args, user)

            # If tool execution failed, create error result for LLM
            if not tool_result.get("success", False):
                error_msg = tool_result.get("error", "Unknown error")
                tool_result = {
                    "success": False,
                    "error": error_msg,
                    "note": "Tool execution failed",
                }

            tool_results.append(
                {
                    "tool_call_id": tool_call.get("id"),
                    "tool_name": tool_name,
                    "result": tool_result,
                }
            )

        return tool_results

    def _add_tool_results_to_messages(
        self,
        current_messages: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
    ) -> None:
        """Add tool call and results to messages for next iteration.

        Args:
            current_messages: Current message list to append to.
            tool_calls: List of tool call definitions.
            tool_results: List of tool execution results.
        """
        # Add tool call to messages
        current_messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": tool_calls,
            }
        )

        # Add tool results as user messages
        for result in tool_results:
            result_str = json.dumps(result["result"], indent=2)
            current_messages.append(
                {
                    "role": "user",
                    "content": f"Tool {result['tool_name']} result: {result_str}",
                }
            )

    def _format_final_response(
        self, response: Dict[str, Any], model: str, reasoning_enabled: bool
    ) -> str:
        """Format the final LLM response.

        Args:
            response: Raw LLM response dict.
            model: Model identifier.
            reasoning_enabled: Whether reasoning is enabled.

        Returns:
            Formatted response text.
        """
        if self.policy_engine:
            formatter = self.policy_engine.get_formatter(model)
            if formatter:
                formatted: str = formatter.format_response(response)
                return formatted
            response_content: str = response.get("content", "")
            return response_content

        # Fallback formatting
        content: str = response.get("content", "")
        if reasoning_enabled:
            reasoning_content = response.get("reasoning")
            if reasoning_content and reasoning_content.strip():
                lines = reasoning_content.strip().split("\n")
                quoted_lines = [f"> {line}" for line in lines]
                formatted_reasoning = "> **Reasoning Process**\n> \n" + "\n".join(quoted_lines)
                content = f"{formatted_reasoning}\n\n{content}"
        return content

    def _extract_tool_errors(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract tool errors from messages.

        Args:
            messages: List of messages to extract errors from.

        Returns:
            List of error messages found in tool results.
        """
        tool_errors = []
        for msg in messages:
            content = msg.get("content", "")
            if "Tool " in content and "result" in content:
                # Try to extract error from tool result
                error_match = re.search(r'"error":\s*"([^"]+)"', content)
                if error_match:
                    tool_errors.append(error_match.group(1))
        return tool_errors

    def _has_tool_calls(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if any message contains tool calls.

        Args:
            messages: List of messages to check.

        Returns:
            True if any message contains tool calls.
        """
        return any("tool_calls" in msg or "Tool " in msg.get("content", "") for msg in messages)

    def _build_max_iter_error_response(
        self,
        current_messages: List[Dict[str, Any]],
        policy: Dict[str, Any],
    ) -> str:
        """Build error response when max iterations reached.

        Args:
            current_messages: Current conversation messages.
            policy: Policy configuration dict.

        Returns:
            Error response message.
        """
        last_few_messages = current_messages[-5:] if len(current_messages) > 5 else current_messages

        tool_errors = self._extract_tool_errors(last_few_messages)

        if tool_errors:
            # We have tool errors, return user-friendly error
            if len(tool_errors) == 1:
                return f"❌ 抱歉，操作失败: {tool_errors[0]}"
            return f"❌ 抱歉，操作失败。最后一个错误: {tool_errors[-1]}"

        if self._has_tool_calls(last_few_messages):
            # We have tool calls but reached max iterations
            return "❌ 抱歉，我在处理您的请求时遇到了困难。工具调用达到了最大尝试次数。请尝试简化您的问题或联系管理员。"

        # Regular generation without tool artifacts
        return self._regular_generate(current_messages, policy)

    def _generate_with_tool_calls(
        self,
        messages: List[Dict[str, str]],
        policy: Dict[str, Any],
        tools: List[Dict[str, Any]],
        max_iterations: int,
        user: str = "unknown",
    ) -> str:
        """Generate response with iterative tool calling.

        Args:
            messages: Initial conversation messages.
            policy: Policy configuration dict.
            tools: List of available tools.
            max_iterations: Maximum number of tool call iterations.
            user: User identifier for audit logging.

        Returns:
            Generated response text.
        """
        if not self.pc_client:
            logger.warning("PC client not available, falling back to regular generation")
            return self._regular_generate(messages, policy)

        model = policy.get("model", "gpt-4o-mini")
        temperature = policy.get("temperature", 0.7)
        max_tokens = policy.get("max_tokens", 500)
        reasoning_enabled = self._is_reasoning_enabled(model, policy)

        iteration = 0
        current_messages = messages.copy()

        while iteration < max_iterations:
            iteration += 1

            # Prepare request with tools
            payload = {
                "model": model,
                "messages": current_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools,
            }
            if reasoning_enabled:
                payload["reasoning"] = {"enabled": True}

            # Call LiteLLM
            try:
                response = self._call_litellm_with_tools(payload)
            except Exception as e:
                logger.error(f"LLM call failed in tool iteration {iteration}: {e}", exc_info=True)
                return self._regular_generate(current_messages, policy)

            # Detect malformed XML tool calls in content
            content = response.get("content", "")
            if content and self._check_xml_tool_calls(content):
                logger.warning(
                    "Model returned XML-like tool call in content. "
                    "Falling back to regular generation."
                )
                return self._regular_generate(current_messages, policy)

            # Check if tool calls are present
            if "tool_calls" in response:
                # Execute tool calls
                tool_results = self._execute_tool_calls(response["tool_calls"], user)

                # Add tool call results to messages for next iteration
                self._add_tool_results_to_messages(
                    current_messages, response["tool_calls"], tool_results
                )
                continue

            # No tool calls, we have the final response
            return self._format_final_response(response, model, reasoning_enabled)

        # Max iterations reached
        logger.warning(f"Max tool iterations ({max_iterations}) reached")
        return self._build_max_iter_error_response(current_messages, policy)

    def _call_litellm_with_tools(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call LiteLLM with tools support and return raw response.

        Args:
            payload: Request payload for LiteLLM API.

        Returns:
            Raw response dict from LiteLLM.

        Raises:
            ValueError: If response format is unexpected.
        """
        url = f"{self.litellm_url}/chat/completions"

        # Prepare headers with authentication
        headers = {"Content-Type": "application/json"}
        if self.master_key:
            headers["Authorization"] = f"Bearer {self.master_key}"

        logger.debug(f"Calling LiteLLM with tools: {payload.get('model')}")

        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        result = response.json()

        # Extract assistant message
        if "choices" in result and len(result["choices"]) > 0:
            message_data: Dict[str, Any] = result["choices"][0]["message"]
            return message_data
        else:
            raise ValueError(f"Unexpected response format: {result}")

    def store_bot_response(
        self,
        response: str,
        stream_id: Optional[str] = None,
        topic: Optional[str] = None,
        user_email: Optional[str] = None,
        policy: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store bot response in PC history.

        This is a convenience method for external callers to store bot responses.
        User messages should be stored separately by the caller before calling
        generate_response.

        Args:
            response: The bot's response text
            stream_id: Zulip stream ID for stream history
            topic: Topic name for stream history
            user_email: User email for private DM history
            policy: Policy configuration with history settings

        Returns:
            None.
        """
        if not self.pc_client:
            return

        if not policy:
            policy = {}

        memory_config = policy.get("memory", {})
        if not memory_config.get("enabled", True):
            return

        try:
            if stream_id and topic:
                self.pc_client.add_stream_message(
                    stream_id=stream_id,
                    topic=topic,
                    role="assistant",
                    content=response,
                    sender_id="bot",
                    config=memory_config,
                )
            elif user_email:
                self.pc_client.add_private_message(
                    user_email=user_email,
                    role="assistant",
                    content=response,
                    sender_id="bot",
                    config=memory_config,
                )
        except Exception as e:
            logger.error(f"Failed to store bot response in PC: {e}", exc_info=True)

    def _regular_generate(self, messages: List[Dict[str, str]], policy: Dict[str, Any]) -> str:
        """Regular LLM generation without PC tool processing.

        Args:
            messages: List of conversation messages.
            policy: Policy configuration dict.

        Returns:
            Generated response text.
        """
        # Build system message from policy
        system_prompt = policy.get("system_prompt", "You are a helpful assistant.")

        # Prepare messages for LLM
        llm_messages = [{"role": "system", "content": system_prompt}]

        # Add context messages
        llm_messages.extend(messages)

        # Get model parameters
        model = policy.get("model", "gpt-4o-mini")
        temperature = policy.get("temperature", 0.7)
        max_tokens = policy.get("max_tokens", 500)

        # Determine if reasoning should be enabled
        reasoning_enabled = False
        if self.policy_engine:
            model_config = self.policy_engine.get_model_config(model)
            if model_config:
                formatting = model_config.get("formatting", {})
                reasoning_config = formatting.get("reasoning", {})
                reasoning_enabled = reasoning_config.get("enabled", False)
        else:
            # Fallback to old field (temporary)
            reasoning_enabled = policy.get("reasoning_enabled", False)

        # Call LLM
        raw_response = self._call_litellm(
            model, llm_messages, temperature, max_tokens, reasoning_enabled
        )

        # Format response
        if self.policy_engine:
            formatter = self.policy_engine.get_formatter(model)
            if formatter:
                formatted: str = formatter.format_response(raw_response)
                return formatted

        # Fallback formatting (no formatter available)
        content: str = raw_response.get("content", "")
        if reasoning_enabled:
            reasoning_content = raw_response.get("reasoning")
            if reasoning_content and reasoning_content.strip():
                lines = reasoning_content.strip().split("\n")
                quoted_lines = [f"> {line}" for line in lines]
                formatted_reasoning = "> **Reasoning Process**\n> \n" + "\n".join(quoted_lines)
                content = f"{formatted_reasoning}\n\n{content}"

        return content

    def _call_litellm(
        self,
        model: str,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        reasoning_enabled: bool = False,
    ) -> Dict[str, Any]:
        """Make API call to LiteLLM and return raw response.

        Args:
            model: Model identifier.
            messages: List of conversation messages.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            reasoning_enabled: Whether to enable reasoning.

        Returns:
            Raw response dict from LiteLLM.

        Raises:
            ValueError: If response format is unexpected.
        """
        url = f"{self.litellm_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if reasoning_enabled:
            payload["reasoning"] = {"enabled": True}

        # Prepare headers with authentication
        headers = {"Content-Type": "application/json"}

        # Add authorization if master key is available
        if self.master_key:
            headers["Authorization"] = f"Bearer {self.master_key}"

        logger.debug(f"Calling LiteLLM: {model}")

        # DEBUG: Log full payload being sent to LLM
        logger.info("=" * 80)
        logger.info("FULL REQUEST PAYLOAD TO LLM")
        logger.info("=" * 80)
        payload_str = json.dumps(payload, ensure_ascii=False, indent=2)
        for line in payload_str.split("\n"):
            logger.info(line)
        logger.info("=" * 80)

        response = requests.post(url, json=payload, headers=headers, timeout=120)

        response.raise_for_status()

        result = response.json()

        # Extract assistant message
        if "choices" in result and len(result["choices"]) > 0:
            message_data2: Dict[str, Any] = result["choices"][0]["message"]
            return message_data2
        else:
            raise ValueError(f"Unexpected response format: {result}")
