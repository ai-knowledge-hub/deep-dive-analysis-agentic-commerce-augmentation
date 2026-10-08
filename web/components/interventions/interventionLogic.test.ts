import { describe, expect, it } from 'vitest';
import { buildCommandItems, buildDetails, buildEscalationItem, commandNeedsIntervention } from './interventionLogic';
import type { AgentRun, AgentRunEvent } from '../../lib/types';
import type { OperatorCommandRecord } from '../../lib/operatorConversationTypes';

const run = { id: 'run-1', status: 'paused', state: 'ready', run_mode: 'plan_only' } as AgentRun;
const record = {
  proposal: { proposal_id: 'proposal-1', command_type: 'approve', principal_id: 'human:operator', proposal_digest: 'proposal-digest' },
  receipt: { receipt_id: 'receipt-1', action_id: 'action-1', approval_command_id: 'approval-command-1', approval_id: 'approval-1', approval_envelope_digest: 'envelope-1', outcome: 'approved', event_ids: { command: 'chat-audit' }, completed_at: '2026-10-04T09:00:00Z' },
} as unknown as OperatorCommandRecord;
const events = ['received', 'completed'].map((status) => ({
  id: `approval-${status}`, run_id: 'run-1', sequence: 1, event_type: 'operator_command_approve', status,
  capability_name: 'request_synthetic_validation',
  anchors: { approval_command_id: 'approval-command-1' },
})) as AgentRunEvent[];

describe('conversational action decision projections', () => {
  it('shows the durable decision once while preserving unrelated approval commands', () => {
    const unrelated = { ...events[0], id: 'unrelated-audit', anchors: { approval_command_id: 'unrelated-command' } };
    const items = buildCommandItems(buildDetails(run, [], [...events, unrelated], [], [record]));
    expect(items).toHaveLength(2);
    expect(items[0].operatorCommandRecord).toBe(record);
    expect(items[0].summary).toContain('recorded outcome approved');
    expect(items[0].summary).toContain('This decision did not execute the action');
    expect(items[1].event.id).toBe('unrelated-audit');
  });

  it('retains audit evidence when durable review history is unavailable', () => {
    const items = buildCommandItems(buildDetails(run, [], events, [], [], false));
    expect(items.map((item) => item.event.id)).toEqual(['approval-received', 'approval-completed']);
  });
});


describe('conversational retry projections', () => {
  const retryRecord = {
    proposal: { proposal_id: 'retry-proposal', command_type: 'retry', principal_id: 'human:operator', proposal_digest: 'retry-digest' },
    receipt: { command_type: 'retry', receipt_id: 'retry-receipt', action_id: 'new-action', source_action_id: 'failed-source', retry_count: 1, effect_idempotency_key: 'retry:failed-source:same_action:1', outcome: 'proposed', event_ids: { command: 'retry-command', lifecycle: 'retry-lifecycle' }, completed_at: '2026-10-05T09:00:00Z' },
  } as unknown as OperatorCommandRecord;
  const retryAudit = { id: 'retry-lifecycle', run_id: run.id, sequence: 2, event_type: 'action_retry_proposed', status: 'proposed', capability_name: 'request_synthetic_validation', anchors: { proposal_id: 'retry-proposal' } } as AgentRunEvent;

  it('shows the exact retry receipt once and preserves unrelated retry evidence', () => {
    const unrelated = { ...retryAudit, id: 'other-retry', anchors: { proposal_id: 'other-proposal' } };
    const items = buildCommandItems(buildDetails(run, [], [retryAudit, unrelated], [], [retryRecord]));
    expect(items).toHaveLength(2);
    expect(items[0].operatorCommandRecord).toBe(retryRecord);
    expect(items[0].risk).toBe('medium');
    expect(items[0].summary).toContain('Source action failed-source; proposed action new-action');
    expect(items[0].summary).toContain('effect identity retry:failed-source:same_action:1');
    expect(items[0].summary).toContain('No work was executed or resumed');
    expect(items[1].event.id).toBe('other-retry');
  });

  it('keeps retry audit evidence when history has no committed receipt', () => {
    for (const records of [[], [{ ...retryRecord, receipt: null }]]) {
      const items = buildCommandItems(buildDetails(run, [], [retryAudit], [], records));
      expect(items.some((item) => item.event.id === 'retry-lifecycle')).toBe(true);
    }
  });
});

it("reloads the exact reconciliation evidence and distinguishes its effect outcome from terminal run state", () => {
  const reconciliation = { ...record, proposal: { ...record.proposal, command_type: "reconcile_effect", source: { run_status: "canceled" }, parameters: { action_id: "action-1", action_status: "failed" } }, receipt: { ...record.receipt, command_type: "reconcile_effect", outcome: "succeeded", resulting_run_status: "canceled", control_state_preserved: true, reconciliation: { effect_execution_id: "effect-1", evidence_id: "job-1", approval_id: "original-approval", authorization_snapshot_digest: "start-digest", evidence_digest: "evidence-digest" } } } as unknown as OperatorCommandRecord;
  const items = buildCommandItems(buildDetails(run, [], [], [], [reconciliation]));
  expect(items).toHaveLength(1);
  expect(items[0].operatorCommandRecord).toBe(reconciliation);
  expect(items[0].summary).toContain("effect outcome recorded: succeeded; action executed; recorded run status canceled");
  expect(items[0].summary).toContain("effect effect-1; evidence job-1; original approval original-approval");
  expect(items[0].summary).toContain("No provider call or new effect start occurred");
  expect(items[0].summary).toContain("Effect success alone does not certify objective completion");
  expect(items[0].summary).not.toContain("undefined");
  expect(commandNeedsIntervention(items[0])).toBe(false);
  const pending = buildCommandItems(buildDetails(run, [], [], [], [{ ...reconciliation, receipt: null }]))[0];
  expect(commandNeedsIntervention(pending)).toBe(true);
});


it("reconciliation settles only its exact uncertainty and never an unrelated policy denial", () => {
  const settled = { ...record, receipt: { ...record.receipt, command_type: "reconcile_effect", run_id: run.id, effect_execution_id: "effect-1", outcome: "succeeded", reconciliation: { approval_id: "original-approval", effect_idempotency_key: "exact-key" } } } as unknown as OperatorCommandRecord;
  const audit = (type: string, status: string, effect = "effect-1") => ({ id: type + effect, run_id: run.id, action_id: "action-1", sequence: 1, event_type: type, status, is_policy_event: true, anchors: { effect_execution_id: effect } }) as AgentRunEvent;
  const governance = [audit("operator_command_approve", "approved"), audit("approval_effect_started", "started"), audit("approval_effect_uncertain", "uncertain"), audit("approval_fulfilled", "fulfilled"), audit("approval_effect_succeeded", "succeeded"), audit("action_executed", "executed")];
  const planned = { ...run, status: "planned" };
  expect(buildEscalationItem(buildDetails(planned, [], governance, [], [settled]))).toBeNull();
  const legacy = { ...audit("approval_effect_uncertain", "uncertain"), anchors: { approval_id: "original-approval", effect_idempotency_key: "exact-key" } };
  expect(buildEscalationItem(buildDetails(planned, [], [legacy], [], [settled]))).toBeNull();
  for (const changed of [
    { ...legacy, action_id: "other-action" }, { ...legacy, run_id: "other-run" },
    { ...legacy, anchors: { ...legacy.anchors, approval_id: "other-approval" } },
    { ...legacy, anchors: { ...legacy.anchors, effect_idempotency_key: "other-key" } },
    { ...legacy, anchors: { ...legacy.anchors, effect_execution_id: "contradictory-effect" } },
  ]) expect(buildEscalationItem(buildDetails(planned, [], [changed], [], [settled]))?.latestEvent).toBe(changed);

  expect(buildEscalationItem(buildDetails(planned, [], governance, [], []))?.latestEvent?.event_type).toBe("approval_effect_uncertain");
  const unrelated = audit("approval_effect_uncertain", "uncertain", "other-effect");
  expect(buildEscalationItem(buildDetails(planned, [], [...governance, unrelated], [], [settled]))?.latestEvent).toBe(unrelated);
  const denial = audit("policy_block", "failed");
  expect(buildEscalationItem(buildDetails(planned, [], [denial, ...governance], [], [settled]))?.latestEvent).toBe(denial);
  expect(buildEscalationItem(buildDetails({ ...planned, status: "failed" }, [], governance, [], [settled]))).not.toBeNull();
});
