export default function generateTitle(message) {
  const compact = message.replace(/\s+/g, " ").trim();
  if (!compact) return "Cuộc trò chuyện mới";
  return compact.length > 42 ? `${compact.slice(0, 42)}...` : compact;
}
