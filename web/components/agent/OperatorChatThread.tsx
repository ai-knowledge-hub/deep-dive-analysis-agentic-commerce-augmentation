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
          Ask a free-form question or use a prompt. Answers are grounded in the selected run’s
          server-verified run context.
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
