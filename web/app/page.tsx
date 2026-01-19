"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { startConversation, sendConversationMessage } from "../lib/api";
import type { ConversationResponse } from "../lib/types";
import { ChatWindow, type Message } from "../components/chat/ChatWindow";
import { ProductReasoning } from "../components/products/ProductReasoning";
import { Sidebar } from "../components/layout/Sidebar";
import { ValuesPanel } from "../components/values/ValuesPanel";
import { IntentionalityProfileCard } from "../components/products/IntentionalityProfileCard";
import { IntentDisplay } from "../components/intent/IntentDisplay";

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<ConversationResponse["plan"]>();
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [productReasoning, setProductReasoning] = useState<
    ConversationResponse["product_explanations"]
  >([]);
  const [researchResults, setResearchResults] = useState<
    ConversationResponse["plan"]["research_results"]
  >([]);
  const [valuesState, setValuesState] = useState<ConversationResponse["values_state"]>();
  const [intent, setIntent] = useState<ConversationResponse["intent"]>();
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  const resetConversation = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setPlan(undefined);
    setClarifications([]);
    setProductReasoning([]);
    setValuesState(undefined);
    setIntent(undefined);
    setResearchResults([]);
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
        setIntent(response.intent);
        setResearchResults(response.plan?.research_results ?? []);
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
    intent?.primary_goal;

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
            <IntentDisplay intent={intent} />
            <IntentionalityProfileCard
              product={plan?.products?.[0]}
              alignmentScore={plan?.alignment?.goal_alignment?.score}
              baselineScore={plan?.alignment?.goal_alignment?.baseline_score}
            />
            <ValuesPanel state={valuesState} />
            <ProductReasoning
              title="Catalog Recommendations"
              products={plan?.catalog_results ?? plan?.products}
              explanations={productReasoning}
            />
            <ProductReasoning
              title="Research Insights"
              badge="Research"
              products={researchResults}
              disclaimer="Synthesized findings from external sources; verify details before purchasing."
            />
          </aside>
        )}
      </main>
    </div>
  );
}
