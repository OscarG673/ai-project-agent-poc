import { useCallback, useEffect, useState } from "react";
import {
  createProject,
  deleteProject,
  fetchProjects,
  Project,
  ProjectInput,
  updateProject,
} from "../api";

const EMPTY_FORM: ProjectInput = {
  name: "",
  description: "",
  status: "active",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  completed: "Completed",
  archived: "Archived",
  on_hold: "On hold",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface ProjectsDashboardProps {
  refreshKey: number;
  onProjectsChanged: () => void;
}

export default function ProjectsDashboard({
  refreshKey,
  onProjectsChanged,
}: ProjectsDashboardProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProjectInput>(EMPTY_FORM);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects, refreshKey]);

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) return;

    setError(null);
    try {
      if (editingId !== null) {
        await updateProject(editingId, form);
      } else {
        await createProject(form);
      }
      resetForm();
      await loadProjects();
      onProjectsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const startEdit = (project: Project) => {
    setEditingId(project.id);
    setForm({
      name: project.name,
      description: project.description,
      status: project.status,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this project?")) return;
    setError(null);
    try {
      await deleteProject(id);
      if (editingId === id) resetForm();
      await loadProjects();
      onProjectsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <section className="panel dashboard">
      <div className="dashboard-header">
        <div>
          <h2>Projects</h2>
          <p className="muted dashboard-subtitle">
            {loading ? "Loading…" : `${projects.length} project${projects.length !== 1 ? "s" : ""}`}
          </p>
        </div>
      </div>

      <form className="project-form" onSubmit={handleSubmit}>
        <h3>{editingId !== null ? `Edit #${editingId}` : "New project"}</h3>
        <div className="form-grid">
          <label className="form-field form-field-grow">
            <span className="field-label">Name</span>
            <input
              type="text"
              placeholder="Project name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </label>
          <label className="form-field">
            <span className="field-label">Status</span>
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
              <option value="on_hold">On hold</option>
            </select>
          </label>
          <label className="form-field form-field-full">
            <span className="field-label">Description</span>
            <textarea
              placeholder="Optional description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
            />
          </label>
        </div>
        <div className="form-actions">
          <button type="submit">{editingId !== null ? "Save changes" : "Create project"}</button>
          {editingId !== null && (
            <button type="button" className="secondary" onClick={resetForm}>
              Cancel
            </button>
          )}
        </div>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="project-cards-scroll">
        {!loading && projects.length === 0 && (
          <p className="muted project-empty">No projects yet. Create one above or ask the agent.</p>
        )}

        <ul className="project-cards">
          {projects.map((project) => (
            <li
              key={project.id}
              className={`project-card-h ${editingId === project.id ? "project-card-editing" : ""}`}
            >
              <span className="project-id">#{project.id}</span>

              <div className="project-card-body">
                <h4 className="project-name">{project.name}</h4>
                <span className={`status status-${project.status}`}>
                  {STATUS_LABELS[project.status] ?? project.status}
                </span>

                <p className="project-desc">
                  {project.description || (
                    <span className="muted">No description</span>
                  )}
                </p>

                <div className="project-meta">
                  <span title={project.created_at}>
                    Created {formatDate(project.created_at)}
                  </span>
                  <span className="meta-dot">·</span>
                  <span title={project.updated_at}>
                    Updated {formatDate(project.updated_at)}
                  </span>
                </div>
              </div>

              <div className="project-card-footer">
                <button type="button" className="btn-ghost" onClick={() => startEdit(project)}>
                  Edit
                </button>
                <button
                  type="button"
                  className="btn-ghost danger"
                  onClick={() => void handleDelete(project.id)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
