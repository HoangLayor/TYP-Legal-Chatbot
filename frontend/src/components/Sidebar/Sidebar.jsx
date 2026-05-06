import { useChatContext } from "../../context/ChatContext.jsx";
import ConversationList from "./ConversationList.jsx";
import NewChatButton from "./NewChatButton.jsx";
import SidebarFooter from "./SidebarFooter.jsx";
import SidebarHeader from "./SidebarHeader.jsx";

export default function Sidebar({ isOpen, onClose, onOpenSettings }) {
  const { createNewConversation } = useChatContext();

  function handleNewChat() {
    createNewConversation();
    onClose?.();
  }

  return (
    <>
      <aside className={`sidebar ${isOpen ? "open" : ""}`}>
        <SidebarHeader />
        <NewChatButton onClick={handleNewChat} />
        <ConversationList onPick={onClose} />
        <SidebarFooter onOpenSettings={onOpenSettings} />
      </aside>
      <button className={`sidebar-overlay ${isOpen ? "visible" : ""}`} onClick={onClose} aria-label="Đóng menu" />
    </>
  );
}
