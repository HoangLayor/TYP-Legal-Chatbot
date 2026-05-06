import SuggestCard from "./SuggestCard.jsx";

const suggestions = [
  "Thủ tục ly hôn thuận tình như thế nào?",
  "Quyền lợi người lao động khi bị sa thải?",
  "Hợp đồng thuê nhà cần có điều khoản gì?",
  "Tôi cần làm gì khi bị tranh chấp đất đai?",
];

export default function WelcomeScreen({ onPickSuggestion }) {
  return (
    <section className="welcome-screen">
      <div className="welcome-orb" aria-hidden="true">
        ⚖️
      </div>
      <h2>Xin chào! Tôi có thể giúp gì cho bạn?</h2>
      <p>Hỏi về thủ tục, quyền lợi, hợp đồng hoặc định hướng xử lý ban đầu cho tình huống pháp lý của bạn.</p>
      <div className="suggest-grid">
        {suggestions.map((suggestion) => (
          <SuggestCard key={suggestion} onClick={() => onPickSuggestion(suggestion)}>
            {suggestion}
          </SuggestCard>
        ))}
      </div>
    </section>
  );
}
