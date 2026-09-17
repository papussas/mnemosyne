import { Routes, Route } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Clients from "./pages/Clients";
import Engagements from "./pages/Engagements";
import EngagementDetail from "./pages/EngagementDetail";
import Hosts from "./pages/Hosts";
import Services from "./pages/Services";
import Assets from "./pages/Assets";
import Credentials from "./pages/Credentials";
import Findings from "./pages/Findings";
import Agents from "./pages/Agents";
import Admin from "./pages/Admin";
import Docs from "./pages/Docs";
import Templates from "./pages/Templates";

export default function App() {
  const { me, loading } = useAuth();
  if (loading) return <div className="h-full grid place-items-center text-muted">Loading…</div>;
  if (!me) return <Login />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/clients" element={<Clients />} />
        <Route path="/engagements" element={<Engagements />} />
        <Route path="/engagements/:id" element={<EngagementDetail />} />
        <Route path="/hosts" element={<Hosts />} />
        <Route path="/services" element={<Services />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/credentials" element={<Credentials />} />
        <Route path="/findings" element={<Findings />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/docs" element={<Docs />} />
        <Route path="/finding-templates" element={<Templates />} />
      </Routes>
    </Layout>
  );
}
