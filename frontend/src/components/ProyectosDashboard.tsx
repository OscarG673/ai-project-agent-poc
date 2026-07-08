import { useCallback, useEffect, useState } from "react";
import {
  createProyecto,
  deleteProyecto,
  fetchProyectos,
  Proyecto,
  ProyectoInput,
  updateProyecto,
} from "../api";
import RequerimientosPanel from "./RequerimientosPanel";

const EMPTY_FORM: ProyectoInput = {
  name: "",
  descripcion: "",
  init_date: "",
  end_date: "",
};

const PAGE_SIZE = 6;

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  // Parse date-only strings (YYYY-MM-DD) as local, not UTC, to avoid off-by-one.
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const date = y && m && d ? new Date(y, m - 1, d) : new Date(iso);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface ProyectosDashboardProps {
  refreshKey: number;
  onProjectsChanged: () => void;
}

export default function ProyectosDashboard({
  refreshKey,
  onProjectsChanged,
}: ProyectosDashboardProps) {
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<ProyectoInput>(EMPTY_FORM);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  const loadProyectos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProyectos(page, PAGE_SIZE);
      // If a delete emptied the last page, step back.
      if (data.items.length === 0 && data.total > 0 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
        return;
      }
      setProyectos(data.items);
      setTotal(data.total);
      setTotalPages(data.pages);
      setSelectedId((prev) =>
        prev !== null && data.items.some((p) => p.id === prev) ? prev : null
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los proyectos");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void loadProyectos();
  }, [loadProyectos, refreshKey]);

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) return;

    // omit empty date/desc strings so the API gets nulls, not ""
    const payload: ProyectoInput = {
      name: form.name.trim(),
      descripcion: form.descripcion?.trim() || null,
      init_date: form.init_date || null,
      end_date: form.end_date || null,
    };

    const isCreate = editingId === null;
    setError(null);
    try {
      if (editingId !== null) {
        await updateProyecto(editingId, payload);
      } else {
        await createProyecto(payload);
      }
      resetForm();
      // New project sorts to the top → jump to page 1; else reload current page.
      if (isCreate && page !== 1) setPage(1);
      else await loadProyectos();
      onProjectsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    }
  };

  const startEdit = (proyecto: Proyecto) => {
    setEditingId(proyecto.id);
    setForm({
      name: proyecto.name,
      descripcion: proyecto.descripcion ?? "",
      init_date: proyecto.init_date ?? "",
      end_date: proyecto.end_date ?? "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id: number) => {
    if (!confirm("¿Eliminar este proyecto y sus requerimientos?")) return;
    setError(null);
    try {
      await deleteProyecto(id);
      if (editingId === id) resetForm();
      if (selectedId === id) setSelectedId(null);
      await loadProyectos();
      onProjectsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar");
    }
  };

  const selected = proyectos.find((p) => p.id === selectedId) ?? null;

  return (
    <section className="panel dashboard">
      <div className="dashboard-header">
        <div>
          <h2>Proyectos</h2>
          <p className="muted dashboard-subtitle">
            {loading
              ? "Cargando…"
              : `${total} proyecto${total !== 1 ? "s" : ""}`}
          </p>
        </div>
      </div>

      <form className="project-form" onSubmit={handleSubmit}>
        <h3>{editingId !== null ? `Editar #${editingId}` : "Nuevo proyecto"}</h3>
        <div className="form-grid">
          <label className="form-field form-field-grow">
            <span className="field-label">Nombre</span>
            <input
              type="text"
              placeholder="Nombre del proyecto"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </label>
          <label className="form-field">
            <span className="field-label">Inicio</span>
            <input
              type="date"
              value={form.init_date ?? ""}
              onChange={(e) => setForm({ ...form, init_date: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span className="field-label">Fin</span>
            <input
              type="date"
              value={form.end_date ?? ""}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
          </label>
          <label className="form-field form-field-full">
            <span className="field-label">Descripción</span>
            <textarea
              placeholder="Descripción opcional"
              value={form.descripcion ?? ""}
              onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              rows={2}
            />
          </label>
        </div>
        <div className="form-actions">
          <button type="submit">
            {editingId !== null ? "Guardar cambios" : "Crear proyecto"}
          </button>
          {editingId !== null && (
            <button type="button" className="secondary" onClick={resetForm}>
              Cancelar
            </button>
          )}
        </div>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="project-cards-scroll">
        {!loading && proyectos.length === 0 && (
          <p className="muted project-empty">
            Aún no hay proyectos. Crea uno arriba o pídeselo al agente.
          </p>
        )}

        <ul className="project-cards">
          {proyectos.map((proyecto) => (
            <li
              key={proyecto.id}
              className={`project-card-h ${
                selectedId === proyecto.id ? "project-card-editing" : ""
              }`}
              onClick={() => setSelectedId(proyecto.id)}
              style={{ cursor: "pointer" }}
            >
              <span className="project-id">#{proyecto.id}</span>

              <div className="project-card-body">
                <h4 className="project-name">{proyecto.name}</h4>
                <p className="project-desc">
                  {proyecto.descripcion || <span className="muted">Sin descripción</span>}
                </p>

                <div className="project-meta">
                  <span>Inicio {formatDate(proyecto.init_date)}</span>
                  <span className="meta-dot">·</span>
                  <span>Fin {formatDate(proyecto.end_date)}</span>
                </div>
              </div>

              <div className="project-card-footer">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedId(proyecto.id);
                  }}
                >
                  Requerimientos
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(proyecto);
                  }}
                >
                  Editar
                </button>
                <button
                  type="button"
                  className="btn-ghost danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    void handleDelete(proyecto.id);
                  }}
                >
                  Eliminar
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {totalPages > 1 && (
        <div className="pager">
          <button
            type="button"
            className="btn-ghost"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← Anterior
          </button>
          <span className="pager-info">
            Página {page} de {totalPages}
          </span>
          <button
            type="button"
            className="btn-ghost"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Siguiente →
          </button>
        </div>
      )}

      {selected && (
        <RequerimientosPanel
          key={selected.id}
          proyecto={selected}
          onClose={() => setSelectedId(null)}
        />
      )}
    </section>
  );
}
