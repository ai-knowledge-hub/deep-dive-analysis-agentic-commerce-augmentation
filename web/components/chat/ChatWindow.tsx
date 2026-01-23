"use client";

type Message = {
  role: "user" | "agent";
  content: string;
};

export function ChatWindow({ messages }: { messages: Message[] }) {
  if (messages.length === 0) {
    return (
      <div className="chat__empty">
        <p>Start a conversation to begin goal clarification.</p>
        <p className="chat__hint">
          Try: &quot;I need a better desk&quot; or &quot;Help me find running shoes&quot;
        </p>
      </div>
    );
  }

  return (
    <div className="chat__list">
      {messages.map((message, idx) => (
        <div
          key={`${message.role}-${idx}`}
          className={`message ${
            message.role === "user" ? "message--user" : "message--agent"
          }`}
        >
          <div className="message__avatar">
            {message.role === "user" ? "U" : "E"}
          </div>
          <div className="message__content">
            <span className="message__role">
              {message.role === "user" ? "You" : "Intentionality Agent"}
            </span>
            <p className="message__text">{message.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export type { Message };
