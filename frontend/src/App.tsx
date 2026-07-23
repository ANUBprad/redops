import { BrowserRouter, Routes, Route } from "react-router-dom";

function HomePage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-foreground">
          RedOps Eval
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Production-grade LLM Evaluation & Red Teaming Platform
        </p>
      </div>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </BrowserRouter>
  );
}
