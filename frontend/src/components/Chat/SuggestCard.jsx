export default function SuggestCard({ children, onClick }) {
  return (
    <button className="suggest-card" onClick={onClick}>
      <span>{children}</span>
    </button>
  );
}
