"use client";

type Message = {
  role: "user" | "agent";
  content: string;
};

export function ChatWindow({ messages }: { messages: Message[] }) {
  return (
    <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      {messages.map((message, idx) => (
        <div key={idx} className="flex gap-3">
          <div className="text-xs uppercase tracking-wide text-slate-400">{message.role}</div>
          <div className="text-sm text-slate-100 whitespace-pre-wrap">{message.content}</div>
        </div>
      ))}
      {messages.length === 0 && (
        <p className="text-sm text-slate-400">Start the conversation to see the values dialogue.</p>
      )}
    </div>
  );
}

export type { Message };
