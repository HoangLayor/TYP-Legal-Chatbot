export default function Avatar({ label = "U", icon, className = "", variant = "default" }) {
  return <div className={`avatar ${variant === "user" ? "user-avatar" : ""} ${className}`}>{icon || label.slice(0, 1).toUpperCase()}</div>;
}
