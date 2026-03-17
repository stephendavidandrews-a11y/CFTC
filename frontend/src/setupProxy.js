/**
 * Dev proxy configuration for multiple backends.
 *
 * /tracker/*  → Tracker service (port 8004)
 * /pipeline/* → Pipeline service (port 8000)
 */
const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  // Tracker backend
  app.use(
    "/tracker",
    createProxyMiddleware({
      target: "http://localhost:8004",
      changeOrigin: true,
    })
  );

  // Pipeline backend
  app.use(
    "/pipeline",
    createProxyMiddleware({
      target: "http://localhost:8000",
      changeOrigin: true,
    })
  );
};
