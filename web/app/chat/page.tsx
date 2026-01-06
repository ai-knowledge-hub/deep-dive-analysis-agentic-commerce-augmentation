"use client";

import { useCallback, useState } from "react";
import { startConversation, sendConversationMessage } from "../../lib/api";
import type { ConversationResponse } from "../../lib/types";
import { ChatWindow, type Message } from "../../components/chat/ChatWindow";
import { ProductReasoning } from "../../components/products/ProductReasoning";
import { WorldAvsB } from "../../components/empowerment/WorldAvsB";

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<ConversationResponse["plan"]>();
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [productReasoning, setProductReasoning] = useState<
    ConversationResponse["product_explanations"]
  >([]);
  const [valuesState, setValuesState] = useState<ConversationResponse["values_state"]>();
  const [loading, setLoading] = useState(false);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setLoading(true);
      try {
        let response: ConversationResponse;
        if (!sessionId) {
          response = await startConversation(text);
          setSessionId(response.session_id);
        } else {
          response = await sendConversationMessage(sessionId, text);
        }

        const clarification = response.clarification;
        if (clarification) {
          setMessages((prev) => [...prev, { role: "agent", content: clarification }]);
          setClarifications(response.plan?.clarifications ?? []);
          setValuesState(response.values_state);
          return;
        }

        if (response.explanation) {
          setMessages((prev) => [...prev, { role: "agent", content: response.explanation! }]);
        }
        setPlan(response.plan);
        setClarifications(response.plan?.clarifications ?? []);
        setProductReasoning(response.product_explanations ?? []);
        setValuesState(response.values_state);
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Error: ${(error as Error).message}` },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [sessionId],
  );

  return (
    <section className="space-y-6">
      <h1 className="text-3xl font-semibold">Gemini Empowerment Chat</h1>
      <ChatWindow messages={messages} />
      <form
        className="flex gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const input = form.elements.namedItem("message") as HTMLInputElement;
          const value = input.value;
          input.value = "";
          void sendMessage(value);
        }}
      >
        <input
          name="message"
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-slate-100"
          placeholder="Describe your goal or ask for help..."
          disabled={loading}
        />
        <button
          type="submit"
          className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-black hover:bg-emerald-400 disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Thinking..." : "Send"}
        </button>
      </form>

      <WorldAvsB
        clarifications={clarifications}
        empowermentScore={plan?.empowerment?.goal_alignment?.score}
      />

      <ProductReasoning products={plan?.products} />

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
        <h2 className="text-lg font-semibold text-slate-100">Values Clarification State</h2>
        {valuesState ? (
          <>
            <p className="text-sm text-slate-400">Query: {valuesState.query}</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-100">
              {valuesState.extracted_goals.map((goal, idx) => (
                <li key={idx}>{goal}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-sm text-slate-400">No clarification yet.</p>
        )}
      </section>
    </section>
  );
}
