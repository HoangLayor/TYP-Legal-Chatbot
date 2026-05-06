import useAutoScroll from "../../hooks/useAutoScroll.js";
import MessageBubble from "./MessageBubble.jsx";
import WelcomeScreen from "./WelcomeScreen.jsx";

export default function MessageList({ conversation, onPickSuggestion }) {
  const messages = conversation?.messages || [];
  const bottomRef = useAutoScroll([messages.length, messages.at(-1)?.content]);

  if (!messages.length) {
    return (
      <div className="message-list">
        <WelcomeScreen onPickSuggestion={onPickSuggestion} />
      </div>
    );
  }

  return (
    <div className="message-list">
      <div className="messages-inner">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
