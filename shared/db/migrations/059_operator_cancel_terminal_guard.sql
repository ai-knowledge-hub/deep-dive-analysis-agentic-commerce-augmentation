-- A durable v3 cancellation is terminal, including runs without completion governance.
-- Keep this additive so installations that already applied 058 receive protection.
CREATE TRIGGER IF NOT EXISTS operator_canceled_run_terminal_guard
BEFORE UPDATE OF status ON agent_runs
WHEN NEW.status IS NOT 'canceled'
 AND EXISTS (
    SELECT 1 FROM operator_cancel_receipts receipt
    WHERE receipt.tenant_id = OLD.client_id
      AND receipt.workflow_id = OLD.id
 )
BEGIN
    SELECT RAISE(ABORT, 'operator canceled run status is immutable');
END;
