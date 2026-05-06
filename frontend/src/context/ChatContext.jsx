import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import useLocalStorage from "../hooks/useLocalStorage.js";
import generateTitle from "../utils/generateTitle.js";

const ChatContext = createContext(null);
const STORAGE_KEY = "legai.conversations";

function createConversation(title = "Cuộc trò chuyện mới") {
  const timestamp = new Date().toISOString();
  return {
    id: uuidv4(),
    title,
    messages: [],
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

function normalizeConversations(value) {
  if (Array.isArray(value) && value.length > 0) {
    return value;
  }
  return [createConversation()];
}

export function ChatProvider({ children }) {
  const [conversations, setConversations] = useLocalStorage(STORAGE_KEY, [createConversation()]);
  const [activeConversationId, setActiveConversationId] = useState(() => normalizeConversations(conversations)[0].id);

  useEffect(() => {
    setConversations((current) => normalizeConversations(current));
  }, [setConversations]);

  useEffect(() => {
    if (conversations.length && !conversations.some((conversation) => conversation.id === activeConversationId)) {
      setActiveConversationId(conversations[0].id);
    }
  }, [activeConversationId, conversations]);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) || conversations[0],
    [activeConversationId, conversations],
  );

  function createNewConversation() {
    const conversation = createConversation();
    setConversations((current) => [conversation, ...normalizeConversations(current)]);
    setActiveConversationId(conversation.id);
    return conversation.id;
  }

  function selectConversation(conversationId) {
    setActiveConversationId(conversationId);
  }

  function deleteConversation(conversationId) {
    setConversations((current) => {
      const next = current.filter((conversation) => conversation.id !== conversationId);
      if (conversationId === activeConversationId) {
        setActiveConversationId(next[0]?.id || null);
      }
      return next.length ? next : [createConversation()];
    });
  }

  function appendMessage(conversationId, message) {
    setConversations((current) =>
      current.map((conversation) => {
        if (conversation.id !== conversationId) return conversation;

        const shouldGenerateTitle = conversation.messages.length === 0 && message.role === "user";
        return {
          ...conversation,
          title: shouldGenerateTitle ? generateTitle(message.content) : conversation.title,
          messages: [...conversation.messages, message],
          updatedAt: new Date().toISOString(),
        };
      }),
    );
  }

  function updateMessage(conversationId, messageId, patch) {
    setConversations((current) =>
      current.map((conversation) => {
        if (conversation.id !== conversationId) return conversation;

        return {
          ...conversation,
          messages: conversation.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  ...(typeof patch === "function" ? patch(message) : patch),
                }
              : message,
          ),
          updatedAt: new Date().toISOString(),
        };
      }),
    );
  }

  const value = useMemo(
    () => ({
      conversations,
      activeConversation,
      activeConversationId: activeConversation?.id,
      createNewConversation,
      selectConversation,
      deleteConversation,
      appendMessage,
      updateMessage,
    }),
    [conversations, activeConversation, activeConversationId],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChatContext must be used inside ChatProvider");
  }
  return context;
}
