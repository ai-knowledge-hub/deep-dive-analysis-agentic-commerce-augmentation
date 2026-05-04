import React from "react";
import type { ChatMessage } from "./operatorChatTypes";

type Props = {
  messages: ChatMessage[];
};

export function OperatorChatThread({ messages }: Props) {
  return (
    <div className="operator-chat__thread">
      {messages.length === 0 ? (
        <div className="panel__muted">
          Ask through the quick prompts first. This first slice focuses on explain, summarize,
          navigate, and recommendation flows.
        </div>
      ) : (
        messages.map((message) => (
          <div
            key={message.id}
            className={`operator-chat__message operator-chat__message--${message.role}`}
          >
            <div className="operator-chat__role">
              {message.role === "assistant" ? "Execution agent" : "Operator"}
            </div>
            <div>{message.content}</div>
          </div>
        ))
      )}
    </div>
  );
}
