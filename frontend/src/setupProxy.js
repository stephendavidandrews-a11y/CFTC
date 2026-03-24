/**
 * Dev proxy configuration for multiple backends.
 *
 * /tracker/*  -> Tracker service (port 8004)
 * /ai/*       -> AI service (port 8006)
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

  // AI backend
  app.use(
    "/ai",
    createProxyMiddleware({
      target: "http://localhost:8006",
      changeOrigin: true,
    })
  );
};
