// server.ts — Development proxy for Frontend (Vite) + FastAPI backend.
// Frontend serves at http://localhost:3000, proxies /api/* to http://localhost:8000
// Build output (npm run build) goes to ./dist — serve with any static server.

import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";
import crypto from "node:crypto";

dotenv.config();

const app = express();
const PORT = parseInt(process.env.PORT || "3000", 10);

if (process.env.NODE_ENV !== "production") {
  const vite = await createViteServer({
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
}

// Telegram token generation is handled by the backend FastAPI auth pipeline.
// The proxy will forward /api/telegram-token/generate to the FastAPI service.

// SPA fallback
app.use("*", async (req, res) => {
  if (req.path.startsWith("/")) {
    if (process.env.NODE_ENV !== "production") {
      const url = req.originalUrl;
      let html = await (await vite).transformIndexHtml(url);
      res.status(200).html(html);
    } else {
      res.sendFile(path.join(process.cwd(), "dist", "index.html"));
    }
  } else {
    res.status(404).end();
  }
});

// Health check (proxy to FastAPI)
app.get("/health", async (req, res) => {
  try {
    const apiRes = await fetch("http://localhost:8000/health", { timeout: 2000 });
    const data = await apiRes.json();
    res.json(data);
  } catch (err) {
    res.status(503).json({ error: "Backend unavailable" });
  }
});

// API proxy to FastAPI
app.use("/api", async (req, res, next) => {
  try {
    const targetUrl = `http://localhost:8000${req.url.slice(4)}`;
    const apiRes = await fetch(targetUrl, {
      method: req.method,
      headers: Object.fromEntries(req.headers),
      body: req.body,
    });
    const data = await apiRes.json();
    res.json(data);
  } catch (err) {
    next();
  }
});

app.listen(PORT, () => {
  console.log(`[SPA] Frontend server on http://localhost:${PORT}`);
  console.log(`[SPA] Proxying /api/* to http://localhost:8000 (FastAPI)`);
});