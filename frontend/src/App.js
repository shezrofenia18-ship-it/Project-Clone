import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import OwnerDashboard from "@/pages/OwnerDashboard";
import POS from "@/pages/POS";
import Products from "@/pages/Products";
import Stock from "@/pages/Stock";
import Purchases from "@/pages/Purchases";
import Slaughter from "@/pages/Slaughter";
import Production from "@/pages/Production";
import Customers from "@/pages/Customers";
import Suppliers from "@/pages/Suppliers";
import Finance from "@/pages/Finance";
import Targets from "@/pages/Targets";
import Reports from "@/pages/Reports";
import AuditLog from "@/pages/AuditLog";
import Users from "@/pages/Users";
import Settings from "@/pages/Settings";
import SalesHistory from "@/pages/SalesHistory";

function Loader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
        <p className="text-muted-foreground text-sm">Memuat Berkah Ayam Mili...</p>
      </div>
    </div>
  );
}

function homeFor(role) {
  if (role === "kasir") return "/pos";
  if (role === "operator") return "/pemotongan";
  return "/dashboard";
}

function Protected({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading || user === null) return <Loader />;
  if (user === false) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Layout>{children}</Layout>;
}

function App() {
  const { user, loading } = useAuth();
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={
            (!loading && user && user !== false) ? <Navigate to={homeFor(user.role)} replace /> : <Login />
          } />
          <Route path="/" element={<Protected><RoleHome /></Protected>} />
          <Route path="/dashboard" element={<Protected roles={["owner", "admin"]}><OwnerDashboard /></Protected>} />
          <Route path="/pos" element={<Protected roles={["owner", "admin", "kasir"]}><POS /></Protected>} />
          <Route path="/riwayat" element={<Protected roles={["owner", "admin", "kasir"]}><SalesHistory /></Protected>} />
          <Route path="/produk" element={<Protected roles={["owner", "admin"]}><Products /></Protected>} />
          <Route path="/stok" element={<Protected roles={["owner", "admin", "operator"]}><Stock /></Protected>} />
          <Route path="/pembelian" element={<Protected roles={["owner", "admin", "operator"]}><Purchases /></Protected>} />
          <Route path="/pemotongan" element={<Protected roles={["owner", "admin", "operator"]}><Slaughter /></Protected>} />
          <Route path="/produksi" element={<Protected roles={["owner", "admin", "operator"]}><Production /></Protected>} />
          <Route path="/pelanggan" element={<Protected roles={["owner", "admin", "kasir"]}><Customers /></Protected>} />
          <Route path="/supplier" element={<Protected roles={["owner", "admin"]}><Suppliers /></Protected>} />
          <Route path="/keuangan" element={<Protected roles={["owner", "admin", "kasir"]}><Finance /></Protected>} />
          <Route path="/target" element={<Protected roles={["owner", "admin"]}><Targets /></Protected>} />
          <Route path="/laporan" element={<Protected roles={["owner", "admin"]}><Reports /></Protected>} />
          <Route path="/audit" element={<Protected roles={["owner", "admin"]}><AuditLog /></Protected>} />
          <Route path="/pengguna" element={<Protected roles={["owner"]}><Users /></Protected>} />
          <Route path="/pengaturan" element={<Protected roles={["owner"]}><Settings /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

function RoleHome() {
  const { user } = useAuth();
  return <Navigate to={homeFor(user.role)} replace />;
}

export default App;
