import "./globals.css";
import Navbar from "../components/Navbar";

export const metadata = {
  title: "KnowledgeHub | Enterprise Multi-Tenant RAG",
  description: "Secure, verified retrieval-augmented generation grounded strictly in your documents.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col selection:bg-indigo-500/30 selection:text-indigo-200">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
        <footer className="border-t border-gray-850 py-4 text-center text-xs text-gray-500">
          KnowledgeHub Enterprise RAG &bull; PostgreSQL pgvector &bull; FastAPI &bull; Hybrid Semantic & Keyword Retrieval
        </footer>
      </body>
    </html>
  );
}
