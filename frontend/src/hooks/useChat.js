import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { useChatContext } from "../context/ChatContext.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_VERSION = import.meta.env.VITE_API_VERSION || "v1";

function extractReply(payload) {
  if (!payload) return "";
  if (typeof payload === "string") return payload;
  return payload.reply || payload.response || payload.answer || payload.content || payload.message || "";
}

function parseSseEvents(buffer) {
  const events = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() || "";

  blocks.forEach((block) => {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("");

    if (!data) return;

    try {
      events.push(JSON.parse(data));
    } catch {
      events.push({ type: "chunk", content: data });
    }
  });

  return { events, rest };
}

async function readSseResponse(response, onChunk) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalText = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseEvents(buffer);
    buffer = parsed.rest;

    parsed.events.forEach((event) => {
      if (event.type === "chunk") {
        const content = event.content || "";
        finalText += content;
        onChunk(content);
      }

      if (event.type === "error") {
        throw new Error(event.message || "Backend trả về lỗi khi xử lý câu hỏi.");
      }
    });
  }

  return finalText;
}

async function callPrimaryChatApi({ message, conversationId, signal }) {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Primary chat endpoint failed with ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return extractReply(await response.json());
  }

  return response.text();
}

async function callStreamFallback({ message, conversationId, signal, onChunk }) {
  const response = await fetch(`${API_URL}/api/${API_VERSION}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      session_id: conversationId,
      query: message,
      use_web_search: true,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Stream chat endpoint failed with ${response.status}`);
  }

  if (!response.body) {
    return response.text();
  }

  return readSseResponse(response, onChunk);
}

export default function useChat() {
  const { activeConversationId, appendMessage, updateMessage } = useChatContext();
  const [isSending, setIsSending] = useState(false);

  async function sendMessage(message) {
    const trimmed = message.trim();
    if (!trimmed || isSending || !activeConversationId) return;

    const assistantMessageId = uuidv4();

    appendMessage(activeConversationId, {
      id: uuidv4(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
      status: "sent",
    });
    appendMessage(activeConversationId, {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
      status: "typing",
    });

    const controller = new AbortController();
    setIsSending(true);

    try {
      const reply = await callPrimaryChatApi({
        message: trimmed,
        conversationId: activeConversationId,
        signal: controller.signal,
      }).catch(() =>
        callStreamFallback({
          message: trimmed,
          conversationId: activeConversationId,
          signal: controller.signal,
          onChunk: (chunk) =>
            updateMessage(activeConversationId, assistantMessageId, (current) => ({
              content: `${current.content}${chunk}`,
              status: "streaming",
            })),
        }),
      );

      updateMessage(activeConversationId, assistantMessageId, (current) => ({
        content: current.content || reply || "Tôi đã nhận câu hỏi, nhưng chưa có nội dung phản hồi.",
        status: "sent",
      }));
      return reply;
    } catch {
      const errorMessage = "⚠️ Không thể kết nối tới hệ thống tư vấn. Vui lòng kiểm tra backend hoặc thử lại sau.";
      updateMessage(activeConversationId, assistantMessageId, {
        content: errorMessage,
        status: "error",
      });
      return errorMessage;
    } finally {
      setIsSending(false);
    }
  }

  return { sendMessage, isSending };
}
