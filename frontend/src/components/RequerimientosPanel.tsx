import { useCallback, useEffect, useState } from "react";
import {
  createRequerimiento,
  deleteRequerimiento,
  EstadoRequerimiento,
  fetchRequerimientos,
  Proyecto,
  Requerimiento,
  RequerimientoInput,
  updateRequerimiento,
} from "../api";

const ESTADOS: EstadoRequerimiento[] = [
  "pendiente",
  "en_progreso",
  "completado",
  "descartado",
];

const ESTADO_LABELS: Record<EstadoRequerimiento, string> = {
  pendiente: "Pendiente",
  en_progreso: "En progreso",
  completado: "Completado",
  descartado: "Descartado",
};

const EMPTY_FORM: RequerimientoInput = {
  name: "",
  descripcion: "",
  prioridad: 3,
  estado: "pendiente",
};

const PAGE_SIZE = 8;

interface RequerimientosPanelProps {
  proyecto: Proyecto;
  onClose: () => void;
}

export default function RequerimientosPanel({
  proyecto,
  onClose,
}: RequerimientosPanelProps) {
  const [items, setItems] = useState<Requerimiento[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<RequerimientoInput>(EMPTY_FORM);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRequerimientos(proyecto.id, page, PAGE_SIZE);
      if (data.items.length === 0 && data.total > 0 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
        return;
      }
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar requerimientos");
    } finally {
      setLoading(false);
    }
  }, [proyecto.id, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) return;
    setError(null);
    try {
      await createRequerimiento(proyecto.id, {
        name: form.name.trim(),
        descripcion: form.descripcion?.trim() || null,
        prioridad: form.prioridad,
        estado: form.estado,
      });
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear");
    }
  };

  const changeEstado = async (id: number, estado: EstadoRequerimiento) => {
    setError(null);
    try {
      await updateRequerimiento(id, { estado });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("¿Eliminar este requerimiento?")) return;
    setError(null);
    try {
      await deleteRequerimiento(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar");
    }
  };

  return (
    <div className="req-panel">
      <div className="req-header">
        <h3>
          Requerimientos · <span className="muted">{proyecto.name}</span>
          {total > 0 && <span className="muted"> ({total})</span>}
        </h3>
        <button type="button" className="bubble-icon-btn" onClick={onClose}>
          ✕
        </button>
      </div>

      <form className="req-form" onSubmit={handleCreate}>
        <input
          type="text"
          placeholder="Nuevo requerimiento"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />
        <select
          value={form.prioridad}
          onChange={(e) => setForm({ ...form, prioridad: Number(e.target.value) })}
          title="Prioridad (1 más alta)"
        >
          {[1, 2, 3, 4, 5].map((p) => (
            <option key={p} value={p}>
              P{p}
            </option>
          ))}
        </select>
        <select
          value={form.estado}
          onChange={(e) =>
            setForm({ ...form, estado: e.target.value as EstadoRequerimiento })
          }
        >
          {ESTADOS.map((s) => (
            <option key={s} value={s}>
              {ESTADO_LABELS[s]}
            </option>
          ))}
        </select>
        <button type="submit">Añadir</button>
      </form>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Cargando…</p>
      ) : items.length === 0 ? (
        <p className="muted">Sin requerimientos todavía.</p>
      ) : (
        <ul className="req-list">
          {items.map((req) => (
            <li key={req.id} className="req-item">
              <span className={`prioridad prioridad-${req.prioridad}`}>P{req.prioridad}</span>
              <div className="req-body">
                <span className="req-name">{req.name}</span>
                {req.descripcion && <span className="req-desc">{req.descripcion}</span>}
              </div>
              <select
                className={`estado-select estado-${req.estado}`}
                value={req.estado}
                onChange={(e) =>
                  void changeEstado(req.id, e.target.value as EstadoRequerimiento)
                }
              >
                {ESTADOS.map((s) => (
                  <option key={s} value={s}>
                    {ESTADO_LABELS[s]}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-ghost danger req-del"
                onClick={() => void handleDelete(req.id)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

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
    </div>
  );
}
