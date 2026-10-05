"""Savepoint ownership for atomic adapters composed inside a caller transaction."""

import sqlite3


class JoinedTransaction:
    def __init__(self, conn: sqlite3.Connection, savepoint: str) -> None:
        if not savepoint.replace("_", "").isalnum():
            raise ValueError("Savepoint must be an internal identifier")
        self.conn, self.savepoint = conn, savepoint
        self.owns_transaction = not conn.in_transaction
        if self.owns_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(f"SAVEPOINT {savepoint}")

    def rollback(self) -> None:
        if self.owns_transaction:
            self.conn.rollback()
        else:
            self.conn.execute(f"ROLLBACK TO {self.savepoint}")
            self.conn.execute(f"RELEASE {self.savepoint}")

    def commit(self) -> None:
        if self.owns_transaction:
            self.conn.commit()
        else:
            self.conn.execute(f"RELEASE {self.savepoint}")
