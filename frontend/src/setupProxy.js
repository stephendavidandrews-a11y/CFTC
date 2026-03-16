/**
 * Dev proxy configuration for multiple backends.
 *
 * /tracker/*  → Tracker service (port 8004)
 * /pipeline/* → Pipeline service (port 8000)
 * /api/v1/*   → Comments/other backends (port 8000)
 */
const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  // Tracker backend (new)
  app.use(
    "/tracker",
    createProxyMiddleware({
      target: "http://localhost:8004",
      changeOrigin: true,
    })
  );

  // Pipeline backend (existing)
  app.use(
    "/pipeline",
    createProxyMiddleware({
      target: "http://localhost:8000",
      changeOrigin: true,
    })
  );

  // Comments / general API (existing)
  app.use(
    "/api/v1",
    createProxyMiddleware({
      target: "http://localhost:8000",
      changeOrigin: true,
    })
  );
};
