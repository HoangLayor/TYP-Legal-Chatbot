import { useState } from "react";
import { useChatContext } from "../../context/ChatContext.jsx";
import InputArea from "../Input/InputArea.jsx";
import MessageList from "./MessageList.jsx";
import TopBar from "./TopBar.jsx";

export default function ChatLayout({ onOpenSidebar }) {
  const { activeConversation } = useChatContext();
  const [draft, setDraft] = useState("");

  return (
    <section className="chat-layout">
      <TopBar onOpenSidebar={onOpenSidebar} />
      <MessageList conversation={activeConversation} onPickSuggestion={setDraft} />
      <InputArea draft={draft} onDraftChange={setDraft} />
    </section>
  );
}
