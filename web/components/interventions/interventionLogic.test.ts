import { describe, expect, it } from 'vitest';
import { buildCommandItems, buildDetails } from './interventionLogic';
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
