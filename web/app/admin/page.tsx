"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  AdminBrand,
  AdminClient,
  AdminClientUser,
  AdminProduct,
  SessionSummary,
} from "../../lib/types";
import {
  addAdminClientUser,
  createAdminBrand,
  createAdminClient,
  createAdminProduct,
  deleteConversationSession,
  listAdminBrands,
  listAdminClientUsers,
  listAdminClients,
  listAdminProducts,
  listConversationSessions,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";

const emptyForm = {
  id: "",
  name: "",
  description: "",
  role: "analyst",
  memberUserId: "",
};

export default function AdminPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const [clients, setClients] = useState<AdminClient[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [clientUsers, setClientUsers] = useState<AdminClientUser[]>([]);

  const [activeClientId, setActiveClientId] = useState<string>("");
  const [activeBrandId, setActiveBrandId] = useState<string>("");

  const [clientForm, setClientForm] = useState({ ...emptyForm });
  const [brandForm, setBrandForm] = useState({ ...emptyForm });
  const [productForm, setProductForm] = useState({ ...emptyForm });
  const [userForm, setUserForm] = useState({ ...emptyForm });

  useEffect(() => {
    if (!userId) return;
    void listAdminClients(userId).then((response) => {
      const items = response.clients ?? [];
      setClients(items);
      if (!activeClientId && items[0]?.id) {
        setActiveClientId(items[0].id);
      }
    });
  }, [activeClientId, userId]);

  useEffect(() => {
    if (!activeClientId || !userId) {
      setBrands([]);
      setProducts([]);
      setClientUsers([]);
      return;
    }
    void listAdminBrands(activeClientId, userId).then((response) => {
      const items = response.brands ?? [];
      setBrands(items);
      if (!activeBrandId && items[0]?.id) {
        setActiveBrandId(items[0].id);
      }
    });
    void listAdminClientUsers(activeClientId, userId).then((response) => {
      setClientUsers(response.users ?? []);
    });
  }, [activeBrandId, activeClientId, userId]);

  useEffect(() => {
    if (!activeBrandId || !userId) {
      setProducts([]);
      return;
    }
    void listAdminProducts(activeBrandId, userId).then((response) => {
      setProducts(response.products ?? []);
    });
  }, [activeBrandId, userId]);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
  }, [userId]);

  const selectedClient = useMemo(
    () => clients.find((client) => client.id === activeClientId),
    [clients, activeClientId],
  );

  const selectedBrand = useMemo(
    () => brands.find((brand) => brand.id === activeBrandId),
    [brands, activeBrandId],
  );

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await deleteConversationSession(deleteTargetId, userId);
      setSessions((current) => current.filter((item) => item.id !== deleteTargetId));
    } finally {
      setDeleteTargetId(null);
    }
  }, [deleteTargetId, userId]);

  const handleCreateClient = useCallback(async () => {
    if (!userId || !clientForm.id.trim() || !clientForm.name.trim()) return;
    const response = await createAdminClient(
      { id: clientForm.id.trim(), name: clientForm.name.trim() },
      userId,
    );
    setClients((current) => [...current, response.client]);
    setActiveClientId(response.client.id);
    setClientForm({ ...emptyForm });
  }, [clientForm, userId]);

  const handleCreateBrand = useCallback(async () => {
    if (!userId || !activeClientId || !brandForm.id.trim() || !brandForm.name.trim())
      return;
    const response = await createAdminBrand(
      activeClientId,
      { id: brandForm.id.trim(), name: brandForm.name.trim() },
      userId,
    );
    setBrands((current) => [...current, response.brand]);
    setActiveBrandId(response.brand.id);
    setBrandForm({ ...emptyForm });
  }, [activeClientId, brandForm, userId]);

  const handleCreateProduct = useCallback(async () => {
    if (!userId || !activeBrandId || !productForm.id.trim() || !productForm.name.trim())
      return;
    const response = await createAdminProduct(
      activeBrandId,
      {
        id: productForm.id.trim(),
        name: productForm.name.trim(),
        description: productForm.description?.trim() || undefined,
      },
      userId,
    );
    setProducts((current) => [...current, response.product]);
    setProductForm({ ...emptyForm });
  }, [activeBrandId, productForm, userId]);

  const handleAddClientUser = useCallback(async () => {
    if (!userId || !activeClientId || !userForm.memberUserId.trim()) return;
    const response = await addAdminClientUser(
      activeClientId,
      {
        member_user_id: userForm.memberUserId.trim(),
        role: userForm.role?.trim() || undefined,
      },
      userId,
    );
    setClientUsers((current) => [response.user, ...current]);
    setUserForm({ ...emptyForm });
  }, [activeClientId, userForm, userId]);

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/")}
        sessions={sessions}
        activeSessionId={null}
        onSelectSession={(sessionId) => router.push(`/?session=${sessionId}`)}
        onDeleteSession={(sessionId) => setDeleteTargetId(sessionId)}
        onOpenHistory={() => {
          setHistoryOpen(true);
          setHistoryClosing(false);
        }}
      />
      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay is-visible"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close menu"
        />
      )}
      {deleteTargetId && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal">
            <h4>Delete conversation?</h4>
            <p>This will permanently remove the chat history.</p>
            <div className="modal__actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setDeleteTargetId(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={confirmDeleteSession}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        isClosing={isHistoryClosing}
        sessions={sessions}
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(selectedId) => {
          router.push(`/?session=${selectedId}`);
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
      />
      <main className="main main--detail">
        <div className="detail admin">
          <DetailHeader title="Admin" onMenu={() => setSidebarOpen(true)} onBack={() => router.push("/")} />
          {!userId && (
            <div className="panel__card admin__panel">
              <h3>Sign in required</h3>
              <p className="panel__empty">
                Sign in with an admin account to manage clients, brands, and products.
              </p>
            </div>
          )}
          {userId && (
            <div className="admin__grid">
            <section className="panel__card admin__panel">
              <div className="panel__header">
                <h3>Clients</h3>
              </div>
              <div className="admin__selector">
                <label className="panel__label" htmlFor="admin-client-select">
                  Active client
                </label>
                <select
                  id="admin-client-select"
                  value={activeClientId}
                  onChange={(event) => {
                    setActiveClientId(event.target.value);
                    setActiveBrandId("");
                  }}
                >
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </select>
              </div>
              {clients.length === 0 ? (
                <p className="panel__empty">No clients yet.</p>
              ) : (
                <ul className="admin__list">
                  {clients.map((client) => (
                    <li key={client.id}>
                      <span>{client.name}</span>
                      <span className="admin__meta">{client.id}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="admin__form">
                <span className="panel__label">Create client</span>
                <input
                  type="text"
                  placeholder="client-id"
                  value={clientForm.id}
                  onChange={(event) =>
                    setClientForm((current) => ({ ...current, id: event.target.value }))
                  }
                />
                <input
                  type="text"
                  placeholder="Client name"
                  value={clientForm.name}
                  onChange={(event) =>
                    setClientForm((current) => ({ ...current, name: event.target.value }))
                  }
                />
                <button
                  type="button"
                  className="button button--primary"
                  onClick={handleCreateClient}
                >
                  Add client
                </button>
              </div>
            </section>

            <section className="panel__card admin__panel">
              <div className="panel__header">
                <h3>Brands</h3>
                <span className="panel__meta">
                  {selectedClient?.name ?? "Select a client"}
                </span>
              </div>
              {activeClientId ? (
                <>
                  <div className="admin__selector">
                    <label className="panel__label" htmlFor="admin-brand-select">
                      Active brand
                    </label>
                    <select
                      id="admin-brand-select"
                      value={activeBrandId}
                      onChange={(event) => setActiveBrandId(event.target.value)}
                    >
                      {brands.map((brand) => (
                        <option key={brand.id} value={brand.id}>
                          {brand.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  {brands.length === 0 ? (
                    <p className="panel__empty">No brands yet.</p>
                  ) : (
                    <ul className="admin__list">
                      {brands.map((brand) => (
                        <li key={brand.id}>
                          <span>{brand.name}</span>
                          <span className="admin__meta">{brand.id}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="admin__form">
                    <span className="panel__label">Create brand</span>
                    <input
                      type="text"
                      placeholder="brand-id"
                      value={brandForm.id}
                      onChange={(event) =>
                        setBrandForm((current) => ({ ...current, id: event.target.value }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Brand name"
                      value={brandForm.name}
                      onChange={(event) =>
                        setBrandForm((current) => ({ ...current, name: event.target.value }))
                      }
                    />
                    <button
                      type="button"
                      className="button button--primary"
                      onClick={handleCreateBrand}
                    >
                      Add brand
                    </button>
                  </div>
                </>
              ) : (
                <p className="panel__empty">Select a client first.</p>
              )}
            </section>

            <section className="panel__card admin__panel">
              <div className="panel__header">
                <h3>Products</h3>
                <span className="panel__meta">
                  {selectedBrand?.name ?? "Select a brand"}
                </span>
              </div>
              {activeBrandId ? (
                <>
                  {products.length === 0 ? (
                    <p className="panel__empty">No products yet.</p>
                  ) : (
                    <ul className="admin__list">
                      {products.map((product) => (
                        <li key={product.id}>
                          <span>{product.name}</span>
                          <span className="admin__meta">{product.id}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="admin__form">
                    <span className="panel__label">Create product</span>
                    <input
                      type="text"
                      placeholder="product-id"
                      value={productForm.id}
                      onChange={(event) =>
                        setProductForm((current) => ({ ...current, id: event.target.value }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Product name"
                      value={productForm.name}
                      onChange={(event) =>
                        setProductForm((current) => ({ ...current, name: event.target.value }))
                      }
                    />
                    <textarea
                      rows={2}
                      placeholder="Short description"
                      value={productForm.description}
                      onChange={(event) =>
                        setProductForm((current) => ({
                          ...current,
                          description: event.target.value,
                        }))
                      }
                    />
                    <button
                      type="button"
                      className="button button--primary"
                      onClick={handleCreateProduct}
                    >
                      Add product
                    </button>
                  </div>
                </>
              ) : (
                <p className="panel__empty">Select a brand first.</p>
              )}
            </section>

            <section className="panel__card admin__panel">
              <div className="panel__header">
                <h3>Client users</h3>
                <span className="panel__meta">
                  {selectedClient?.name ?? "Select a client"}
                </span>
              </div>
              {activeClientId ? (
                <>
                  {clientUsers.length === 0 ? (
                    <p className="panel__empty">No users yet.</p>
                  ) : (
                    <ul className="admin__list">
                      {clientUsers.map((member) => (
                        <li key={member.id}>
                          <span>{member.user_id}</span>
                          <span className="admin__meta">
                            {member.role ?? "analyst"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="admin__form">
                    <span className="panel__label">Add user</span>
                    <input
                      type="text"
                      placeholder="Clerk user id"
                      value={userForm.memberUserId}
                      onChange={(event) =>
                        setUserForm((current) => ({
                          ...current,
                          memberUserId: event.target.value,
                        }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Role (analyst, admin)"
                      value={userForm.role}
                      onChange={(event) =>
                        setUserForm((current) => ({ ...current, role: event.target.value }))
                      }
                    />
                    <button
                      type="button"
                      className="button button--primary"
                      onClick={handleAddClientUser}
                    >
                      Add user
                    </button>
                  </div>
                </>
              ) : (
                <p className="panel__empty">Select a client first.</p>
              )}
            </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
