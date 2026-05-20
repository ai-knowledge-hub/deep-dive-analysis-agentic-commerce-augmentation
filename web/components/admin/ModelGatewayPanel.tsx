"use client";

import React from "react";
import type { AdminLLMConfigResponse } from "../../lib/types";

export type LlmProviderOption = {
  readonly id: string;
  readonly label: string;
};

export type LlmInputState = {
  apiKey: string;
  validationApiKey: string;
  model: string;
  validationModel: string;
};

type LlmInputField = keyof LlmInputState;

type Props = {
  userId?: string | null;
  llmConfig: AdminLLMConfigResponse | null;
  llmConfigError: string | null;
  llmInputs: Record<string, LlmInputState>;
  providers: readonly LlmProviderOption[];
  modelOptions: Record<string, string[]>;
  onInputChange: (provider: string, field: LlmInputField, value: string) => void;
  onSaveProvider: (provider: string) => void | Promise<void>;
  onActivateProvider: (provider: string) => void | Promise<void>;
};

export function ModelGatewayPanel({
  userId,
  llmConfig,
  llmConfigError,
  llmInputs,
  providers,
  modelOptions,
  onInputChange,
  onSaveProvider,
  onActivateProvider,
}: Props) {
  return (
    <details className="admin-ops__details">
      <summary>Model gateway</summary>
      {!userId ? (
        <p className="panel__empty">Sign in to manage model keys.</p>
      ) : (
        <div className="admin__form">
          {llmConfigError ? <p className="panel__error">{llmConfigError}</p> : null}
          <div className="panel__chips">
            {providers.map((provider) => {
              const summary = llmConfig?.providers?.[provider.id];
              const status = summary?.configured ? "ready" : "missing";
              return (
                <span
                  key={provider.id}
                  className={`panel__chip ${
                    summary?.is_active ? "is-ready" : summary?.configured ? "is-ready" : "is-missing"
                  }`}
                >
                  {provider.label}: {summary?.is_active ? "active" : status}
                </span>
              );
            })}
          </div>
          {providers.map((provider) => {
            const summary = llmConfig?.providers?.[provider.id];
            const baseOptions = modelOptions[provider.id] || [];
            const input = llmInputs[provider.id] || {
              apiKey: "",
              validationApiKey: "",
              model: summary?.model || baseOptions[0] || "",
              validationModel: summary?.validation_model || baseOptions[0] || "",
            };
            const chatOptions = input.model && !baseOptions.includes(input.model)
              ? [input.model, ...baseOptions]
              : baseOptions;
            const validationOptions =
              input.validationModel && !baseOptions.includes(input.validationModel)
                ? [input.validationModel, ...baseOptions]
                : baseOptions;

            return (
              <div key={provider.id} className="panel__card panel__card--compact">
                <div className="panel__header">
                  <h4>{provider.label}</h4>
                  <span className="panel__meta">
                    Chat: {summary?.chat_configured ? "set" : "missing"} · Validation:{" "}
                    {summary?.validation_configured ? "set" : "missing"}
                  </span>
                </div>
                <div className="panel__grid">
                  <label className="panel__label">
                    <span>Chat model</span>
                    <input
                      className="panel__input panel__input--neutral"
                      type="text"
                      list={`admin-llm-chat-models-${provider.id}`}
                      spellCheck={false}
                      autoCorrect="off"
                      autoCapitalize="none"
                      value={input.model}
                      onChange={(event) =>
                        onInputChange(provider.id, "model", event.target.value)
                      }
                    />
                    <datalist id={`admin-llm-chat-models-${provider.id}`}>
                      {chatOptions.map((option) => (
                        <option key={option} value={option} />
                      ))}
                    </datalist>
                  </label>
                  <label className="panel__label">
                    <span>Validation model</span>
                    <input
                      className="panel__input panel__input--neutral"
                      type="text"
                      list={`admin-llm-validation-models-${provider.id}`}
                      spellCheck={false}
                      autoCorrect="off"
                      autoCapitalize="none"
                      value={input.validationModel}
                      onChange={(event) =>
                        onInputChange(provider.id, "validationModel", event.target.value)
                      }
                    />
                    <datalist id={`admin-llm-validation-models-${provider.id}`}>
                      {validationOptions.map((option) => (
                        <option key={option} value={option} />
                      ))}
                    </datalist>
                  </label>
                  <label className="panel__label">
                    <span>Chat key (BYOK)</span>
                    <input
                      className="panel__input"
                      type="password"
                      value={input.apiKey}
                      onChange={(event) =>
                        onInputChange(provider.id, "apiKey", event.target.value)
                      }
                      placeholder={summary?.configured ? "Saved" : "Paste API key"}
                    />
                  </label>
                  <label className="panel__label">
                    <span>Validation key (BYOK)</span>
                    <input
                      className="panel__input"
                      type="password"
                      value={input.validationApiKey}
                      onChange={(event) =>
                        onInputChange(provider.id, "validationApiKey", event.target.value)
                      }
                      placeholder={summary?.configured ? "Saved (optional)" : "Paste API key"}
                    />
                  </label>
                </div>
                <div className="panel__actions">
                  <button
                    type="button"
                    className="button button--primary-subtle"
                    onClick={() => void onSaveProvider(provider.id)}
                  >
                    Save provider
                  </button>
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => void onActivateProvider(provider.id)}
                    disabled={!summary?.chat_configured}
                  >
                    Use for chat
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </details>
  );
}
