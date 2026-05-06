import { useChatContext } from "../../context/ChatContext.jsx";
import ConversationItem from "./ConversationItem.jsx";

function getGroupLabel(conversation) {
  const updatedAt = new Date(conversation.updatedAt || conversation.createdAt);
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startOfConversationDay = new Date(updatedAt.getFullYear(), updatedAt.getMonth(), updatedAt.getDate());
  const diffDays = Math.round((startOfToday - startOfConversationDay) / 86400000);

  if (diffDays <= 0) return "Hôm nay";
  if (diffDays === 1) return "Hôm qua";
  return "7 ngày trước";
}

function groupConversations(conversations) {
  return conversations.reduce((groups, conversation) => {
    const label = getGroupLabel(conversation);
    const existing = groups.find((group) => group.label === label);
    if (existing) {
      existing.items.push(conversation);
      return groups;
    }
    return [...groups, { label, items: [conversation] }];
  }, []);
}

export default function ConversationList({ onPick }) {
  const { conversations, activeConversationId, selectConversation, deleteConversation } = useChatContext();
  const groupedConversations = groupConversations(conversations);

  return (
    <nav className="conversation-list" aria-label="Lịch sử hội thoại">
      {groupedConversations.map((group) => (
        <section className="conversation-group" key={group.label}>
          <h2>{group.label}</h2>
          {group.items.map((conversation) => (
            <ConversationItem
              key={conversation.id}
              conversation={conversation}
              isActive={conversation.id === activeConversationId}
              onSelect={() => {
                selectConversation(conversation.id);
                onPick?.();
              }}
              onDelete={() => deleteConversation(conversation.id)}
            />
          ))}
        </section>
      ))}
    </nav>
  );
}
