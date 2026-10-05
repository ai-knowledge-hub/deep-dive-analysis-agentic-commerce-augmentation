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
