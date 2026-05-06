export default function SendButton({ disabled, isLoading }) {
  return (
    <button className={`send-button ${isLoading ? "loading" : ""}`} type="submit" disabled={disabled} aria-label="Gửi tin nhắn">
      <span className="icon-wrapper">➤</span>
    </button>
  );
}
