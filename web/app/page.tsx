"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { startConversation, sendConversationMessage } from "../lib/api";
import type { ConversationResponse } from "../lib/types";
import { ChatWindow, type Message } from "../components/chat/ChatWindow";
import { ProductReasoning } from "../components/products/ProductReasoning";
import { WorldAvsB } from "../components/empowerment/WorldAvsB";
import { Sidebar } from "../components/layout/Sidebar";
import { ValuesPanel } from "../components/values/ValuesPanel";

const STATUS_QUO_KEYS = [
  "world_a_example",
  "status_quo_example",
  "status_quo_prompt",
  "world_a_pitch",
  "baseline_prompt",
];

function extractStatusQuo(source?: Record<string, unknown>): string | undefined {
  if (!source) return undefined;
  for (const key of STATUS_QUO_KEYS) {
    const candidate = source[key];
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate;
    }
  }
  return undefined;
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<ConversationResponse["plan"]>();
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [productReasoning, setProductReasoning] = useState<
    ConversationResponse["product_explanations"]
  >([]);
  const [valuesState, setValuesState] = useState<ConversationResponse["values_state"]>();
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [worldAExample, setWorldAExample] = useState<string>();
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  const resetConversation = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setPlan(undefined);
    setClarifications([]);
    setProductReasoning([]);
    setValuesState(undefined);
    setWorldAExample(undefined);
  }, []);

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

        const guardrailStatusQuo = extractStatusQuo(response.guardrails);
        const valuesMetadataStatusQuo = response.values_state
          ? extractStatusQuo(response.values_state.metadata)
          : undefined;
        const nextWorldAExample =
          response.plan?.world_a_example ?? guardrailStatusQuo ?? valuesMetadataStatusQuo;
        if (nextWorldAExample) {
          setWorldAExample(nextWorldAExample);
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
        setMessages((prev) => [...prev, { role: "agent", content: `Error: ${(error as Error).message}` }]);
      } finally {
        setLoading(false);
      }
    },
    [sessionId],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      void sendMessage(inputValue);
      setInputValue("");
    }
  };

  const hasInsights =
    clarifications.length > 0 ||
    valuesState ||
    (plan?.products?.length ?? 0) > 0 ||
    !!worldAExample;

  useEffect(() => {
    const el = chatContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="app">
      <Sidebar mobileOpen={isSidebarOpen} onMobileClose={() => setSidebarOpen(false)} />
      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay is-visible"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close menu"
        />
      )}
      <main className="main">
        <div className="main__content">
          <div className="main__toolbar">
            <button
              type="button"
              className="mobile-toggle"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              Menu
            </button>
          </div>
          <div className="chat">
            <div className="chat__messages" ref={chatContainerRef}>
              <ChatWindow messages={messages} />
            </div>

            <form className="chat__input" onSubmit={handleSubmit}>
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="What are you looking for?"
                disabled={loading}
                autoComplete="off"
              />
              <button
                type="submit"
                className="chat__send"
                disabled={loading || !inputValue.trim()}
              >
                {loading ? "..." : "Send"}
              </button>
            </form>
          </div>
        </div>

        {hasInsights && (
          <aside className="insights">
            <WorldAvsB
              clarifications={clarifications}
              empowermentScore={plan?.empowerment?.goal_alignment?.score}
              worldAExample={worldAExample}
            />
            <ValuesPanel state={valuesState} />
            <ProductReasoning products={plan?.products} explanations={productReasoning} />
          </aside>
        )}
      </main>
    </div>
  );
}
