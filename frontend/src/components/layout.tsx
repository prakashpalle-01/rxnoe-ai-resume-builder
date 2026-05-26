import { FileText, FileUp, LayoutDashboard, LogOut, Sparkles } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAppStore } from "../store/app-store";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/upload-resume", label: "Add Resume", icon: FileUp },
  { to: "/paste-job-description/latest", label: "Generate Resume", icon: FileText }
];

export function AppLayout() {
  const navigate = useNavigate();
  const { userEmail, setUserEmail } = useAppStore();

  function logout() {
    localStorage.removeItem("rxnoe_token");
    localStorage.removeItem("rxnoe_email");
    setUserEmail(null);
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-rx-soft">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-rx-line bg-white lg:block">
        <div className="flex h-16 items-center gap-3 border-b border-rx-line px-5">
          <div className="flex size-10 items-center justify-center rounded-md bg-rx-blue text-white">
            <Sparkles size={19} />
          </div>
          <div>
            <p className="text-lg font-bold tracking-tight">RxNoe</p>
            <p className="text-xs text-rx-muted">AI Resume Builder</p>
          </div>
        </div>
        <nav className="space-y-1 p-3">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium ${isActive ? "bg-blue-50 text-rx-blue" : "text-slate-700 hover:bg-slate-50"}`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 flex min-h-16 items-center justify-between border-b border-rx-line bg-white/95 px-4 backdrop-blur md:px-8">
          <div>
            <p className="text-sm font-semibold text-rx-ink">Build one targeted resume per job</p>
            <p className="text-xs text-rx-muted">{userEmail ?? "Local workspace"}</p>
          </div>
          <button className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50" onClick={logout}>
            <LogOut size={17} />
            Sign out
          </button>
        </header>
        <main className="px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
