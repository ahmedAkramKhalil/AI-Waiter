export default function TypingDots() {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1.5">
      <span className="w-2 h-2 rounded-full bg-gold-300 animate-dot" style={{ animationDelay: "0s" }} />
      <span className="w-2 h-2 rounded-full bg-gold-300 animate-dot" style={{ animationDelay: "0.15s" }} />
      <span className="w-2 h-2 rounded-full bg-gold-300 animate-dot" style={{ animationDelay: "0.3s" }} />
    </div>
  );
}
